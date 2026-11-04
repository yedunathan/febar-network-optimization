# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Material routes — end-to-end route reconstruction
# MAGIC Reconstructs every plant→customer-node route each SKU actually travelled (DFS from manufacturing plants through
# MAGIC the gold lane graph, max 8 hops), categorises it (Planned + Happened / Happened Not Planned / Planned Not Happened /
# MAGIC Loop), and prices it against a 5-tier baseline cascade so each unplanned route carries an **extra cost per case**
# MAGIC and a **total $ impact**. Output: `netopt_gold.material_routes` (feeds the app's route explorer and Genie).

# COMMAND ----------

from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "cpg_demos")
dbutils.widgets.text("gold_schema", "netopt_gold")
CAT = dbutils.widgets.get("catalog")
GOLD_SCHEMA = dbutils.widgets.get("gold_schema")
GOLD = f"{CAT}.{GOLD_SCHEMA}"

sot = (
    spark.read.table(f"{GOLD}.lane_material_sot")
    .filter("material_number != 'SHUTTLE'")
    .groupBy("material_number", "directed_lane_id", "origin_plant", "dest_plant", "origin_type", "dest_type")
    .agg(
        F.max(F.when(F.col("lane_type") == "planned_transport", 1).otherwise(0)).alias("ever_planned"),
        F.max(F.when(F.col("lane_type") == "out_of_lane_transport", 1).otherwise(0)).alias("ever_oor"),
        F.max(F.when(F.col("lane_type") == "theoretical_transport", 1).otherwise(0)).alias("ever_theoretical"),
        F.sum(F.coalesce(F.col("total_cases"), F.lit(0))).alias("total_cases"),
        F.sum(F.coalesce(F.col("total_freight_usd"), F.lit(0.0))).alias("total_freight_usd"),
    )
    .withColumn("cost_per_case", F.when(F.col("total_cases") > 0, F.col("total_freight_usd") / F.col("total_cases")))
)
rows = sot.collect()

# lane-level baselines for the cascade (any material)
lane_planned_cost = {}
from collections import defaultdict
lane_costs = defaultdict(list)
for r in rows:
    if r.ever_planned and r.cost_per_case:
        lane_costs[r.directed_lane_id].append(r.cost_per_case)
lane_planned_cost = {k: sum(v) / len(v) for k, v in lane_costs.items()}
network_avg = (sum(lane_planned_cost.values()) / len(lane_planned_cost)) if lane_planned_cost else 0.0

by_mat = defaultdict(list)
for r in rows:
    by_mat[r.material_number].append(r)

STORAGE_PER_HOP = 0.35
out = []
for matno, lanes in by_mat.items():
    adj = defaultdict(list)
    for r in lanes:
        if r.origin_plant != r.dest_plant:
            adj[r.origin_plant].append(r)
    starts = sorted({r.origin_plant for r in lanes if r.origin_type == "MFG" and r.origin_plant != r.dest_plant})
    routes = []

    def dfs(node, path_lanes, visited):
        if len(path_lanes) >= 8:
            routes.append((list(path_lanes), "max_hops"))
            return
        nxt = [e for e in adj.get(node, []) if e.dest_plant not in visited]
        loops = [e for e in adj.get(node, []) if e.dest_plant in visited]
        if loops and path_lanes:
            routes.append((list(path_lanes), "loop"))
        if not nxt:
            if path_lanes:
                routes.append((list(path_lanes), None))
            return
        for e in nxt:
            path_lanes.append(e)
            visited.add(e.dest_plant)
            dfs(e.dest_plant, path_lanes, visited)
            visited.discard(e.dest_plant)
            path_lanes.pop()

    for s in starts:
        dfs(s, [], {s})

    # material-level planned route costs (baseline tiers 1-2)
    planned_route_costs = {}
    for legs, anomaly in routes:
        if all(l.ever_planned for l in legs):
            cost = sum((l.cost_per_case or lane_planned_cost.get(l.directed_lane_id, 0)) for l in legs) + STORAGE_PER_HOP * len(legs)
            key = (legs[0].origin_plant, legs[-1].dest_plant)
            planned_route_costs[key] = min(cost, planned_route_costs.get(key, float("inf")))
    min_planned = min(planned_route_costs.values()) if planned_route_costs else None

    seen = set()
    for ri, (legs, anomaly) in enumerate(routes):
        path = legs[0].origin_plant + ">" + ">".join(l.dest_plant for l in legs)
        if path in seen:
            continue
        seen.add(path)
        all_planned = all(l.ever_planned for l in legs)
        any_shipped = any(l.total_cases > 0 for l in legs)
        all_shipped = all(l.total_cases > 0 for l in legs)
        any_oor = any(l.ever_oor and not l.ever_planned for l in legs)
        if anomaly == "loop":
            category = "Loop"
        elif all_planned and all_shipped:
            category = "Planned + Happened"
        elif any_oor and any_shipped:
            category = "Happened Not Planned"
        elif not any_shipped:
            category = "Planned Not Happened"
        else:
            category = "Planned + Happened"

        transport_cost = sum((l.cost_per_case or lane_planned_cost.get(l.directed_lane_id) or network_avg) for l in legs)
        storage_cost = STORAGE_PER_HOP * len(legs)
        route_cost = transport_cost + storage_cost
        route_cases = min((l.total_cases for l in legs if l.total_cases > 0), default=0)

        baseline, tier = None, None
        if category in ("Happened Not Planned", "Loop"):
            key = (legs[0].origin_plant, legs[-1].dest_plant)
            if key in planned_route_costs:
                baseline, tier = planned_route_costs[key], 1
            elif min_planned is not None:
                baseline, tier = min_planned, 2
            else:
                lane_bases = [lane_planned_cost.get(l.directed_lane_id) for l in legs]
                if all(b is not None for b in lane_bases) and lane_bases:
                    baseline, tier = sum(lane_bases) + storage_cost, 3
                elif any(b is not None for b in lane_bases):
                    baseline, tier = sum(b or network_avg for b in lane_bases) + storage_cost, 4
                # tier 5 = no baseline found -> stays None
        extra = (route_cost - baseline) if baseline is not None else None
        out.append({
            "route_id": f"RT-{matno[-7:]}-{ri}",
            "material_number": matno,
            "route_path": path,
            "n_hops": len(legs),
            "category": category,
            "is_loop": anomaly == "loop",
            "is_max_hops": anomaly == "max_hops",
            "transport_cost_per_case": round(transport_cost, 4),
            "storage_cost_per_case": round(storage_cost, 4),
            "route_cost_per_case": round(route_cost, 4),
            "baseline_cost_per_case": round(baseline, 4) if baseline is not None else None,
            "baseline_tier": tier,
            "extra_cost_per_case": round(extra, 4) if extra is not None else None,
            "route_cases": int(route_cases),
            "total_cost_impact": round(extra * route_cases, 2) if extra is not None and route_cases else None,
            **{f"lane_{i+1}_id": (legs[i].directed_lane_id if i < len(legs) else None) for i in range(8)},
        })

from pyspark.sql.types import (StructType, StructField, StringType, IntegerType, DoubleType, BooleanType)
schema = StructType([
    StructField("route_id", StringType()), StructField("material_number", StringType()),
    StructField("route_path", StringType()), StructField("n_hops", IntegerType()),
    StructField("category", StringType()), StructField("is_loop", BooleanType()),
    StructField("is_max_hops", BooleanType()),
    StructField("transport_cost_per_case", DoubleType()), StructField("storage_cost_per_case", DoubleType()),
    StructField("route_cost_per_case", DoubleType()), StructField("baseline_cost_per_case", DoubleType()),
    StructField("baseline_tier", IntegerType()), StructField("extra_cost_per_case", DoubleType()),
    StructField("route_cases", IntegerType()), StructField("total_cost_impact", DoubleType()),
    *[StructField(f"lane_{i+1}_id", StringType()) for i in range(8)],
])
df = spark.createDataFrame(out, schema)
spark.sql(f"USE CATALOG {CAT}")
spark.sql(f"USE SCHEMA {GOLD_SCHEMA}")
df.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable("material_routes")
spark.sql(f"COMMENT ON TABLE {GOLD}.material_routes IS 'Reconstructed end-to-end SKU routes with category, baseline cost cascade and extra cost per case'")
print(f"wrote {GOLD}.material_routes: {spark.read.table(f'{GOLD}.material_routes').count():,} rows")

# COMMAND ----------

display(spark.sql(f"""
  SELECT category, count(*) routes, sum(route_cases) cases,
         round(sum(coalesce(total_cost_impact, 0)), 0) total_cost_impact_usd
  FROM {GOLD}.material_routes GROUP BY category ORDER BY routes DESC"""))
