"""
Northstar Network Optimization — Lakeflow Spark Declarative Pipeline

bronze (Auto Loader streaming tables over the UC landing volume):
        erp_plant_master, erp_plant_xref, ref_plant_coordinates, erp_material_master,
        mrp_route_legs, mrp_supply_paths, tms_load, tms_stop, tms_lineitem,
        tms_lineitem_detail, tms_freight, tms_rate, erp_gl_line_items,
        erp_inventory_monthly, ref_exchange_rates, ref_shuttle_lanes
silver: enterprise_plant, enterprise_material_master, enterprise_route_leg,
        enterprise_gl_line_item, freight_shipments, transport_lane_paths
gold:   lane_material_sot (source of truth), oor_analysis, lane_monthly, plant_stats,
        material_period_status, sales_monthly, inventory_monthly

Schemas and landing path come from pipeline configuration (see resources/pipeline.yml).
"""
import dlt
from pyspark.sql import functions as F

CAT = spark.conf.get("netopt.catalog", "cpg_demos")
BRONZE = f"{CAT}.{spark.conf.get('netopt.bronze_schema', 'netopt_bronze')}"
SILVER = f"{CAT}.{spark.conf.get('netopt.silver_schema', 'netopt_silver')}"
GOLD = f"{CAT}.{spark.conf.get('netopt.gold_schema', 'netopt_gold')}"
LANDING = spark.conf.get("netopt.landing_path", "/Volumes/cpg_demos/netopt_raw/landing")

QUALITY = {"quality": "bronze", "source": "synthetic"}

# ---------------------------------------------------------------- BRONZE (Lakeflow ingest)

FEEDS = {
    "erp_plant_master": "ERP plant master (T001W-style): plant code, name, city, region, country, currency",
    "erp_plant_xref": "ERP legacy ECC -> S4 plant code realignment cross-reference",
    "ref_plant_coordinates": "Network node type and lat/lon reference",
    "erp_material_master": "ERP material master: finished goods (ZFRT) + logistics materials (ZPKG)",
    "mrp_route_legs": "MRP monthly planned route-leg snapshots (procurement direction)",
    "mrp_supply_paths": "MRP multi-hop supply paths per material",
    "tms_load": "TMS loads: carrier, mode, ship date",
    "tms_stop": "TMS stops: pick-up / drop-off plant codes (mixed ECC/S4)",
    "tms_lineitem": "TMS load line items: material (zeros sometimes stripped), cases, weight",
    "tms_lineitem_detail": "TMS line-item allocation detail",
    "tms_freight": "TMS freight invoice per load: linehaul + fuel, local currency",
    "tms_rate": "TMS contracted lane rates per carrier (commercially sensitive)",
    "erp_gl_line_items": "ERP GL sales postings (posting_period is a 3-char string)",
    "erp_inventory_monthly": "ERP month-end inventory by plant x material",
    "ref_exchange_rates": "Monthly CAD->USD FX rates",
    "ref_shuttle_lanes": "Private-fleet shuttle lanes not visible in the TMS",
}


def make_bronze(feed: str, comment: str):
    @dlt.table(name=f"{BRONZE}.{feed}", comment=f"[bronze] {comment}", table_properties=QUALITY)
    def _bronze():
        return (
            spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "parquet")
            .option("cloudFiles.inferColumnTypes", "true")
            .load(f"{LANDING}/{feed}/")
            .withColumn("_ingested_at", F.current_timestamp())
            .withColumn("_source_file", F.col("_metadata.file_path"))
        )
    return _bronze


for _feed, _comment in FEEDS.items():
    make_bronze(_feed, _comment)


def bronze(feed: str):
    return spark.read.table(f"{BRONZE}.{feed}").drop("_ingested_at", "_source_file")

# ---------------------------------------------------------------- SILVER

@dlt.table(name=f"{SILVER}.enterprise_plant", comment="Unified plant master with coordinates and ECC/S4 cross-reference",
           table_properties={"quality": "silver"})
@dlt.expect_all_or_drop({
    "valid_coords": "lat BETWEEN 20 AND 60 AND lon BETWEEN -130 AND -60",
    "valid_code": "plant_s4 IS NOT NULL",
})
def enterprise_plant():
    t001w = bronze("erp_plant_master")
    xref = bronze("erp_plant_xref")
    coords = bronze("ref_plant_coordinates")
    return (
        t001w.alias("t")
        .join(xref.alias("x"), F.col("t.werks") == F.col("x.plant_s4"))
        .join(coords.alias("c"), F.col("t.werks") == F.col("c.plant_s4"))
        .select(
            F.col("t.werks").alias("plant_s4"),
            F.col("x.plant_ecc"),
            F.col("x.plant_name"),
            F.col("c.plant_type"),
            F.col("t.ort01").alias("city"),
            F.col("t.regio").alias("region"),
            F.col("t.land1").alias("country"),
            F.col("c.lat"), F.col("c.lon"),
            F.col("t.currency"),
        )
    )


@dlt.table(name=f"{SILVER}.enterprise_material_master", comment="Material metadata with canonical + stripped keys for leading-zero normalization",
           table_properties={"quality": "silver"})
@dlt.expect_all_or_drop({"valid_material": "material_number IS NOT NULL"})
def enterprise_material_master():
    return (
        bronze("erp_material_master")
        .withColumn("material_stripped", F.regexp_replace("material_number", "^0+", ""))
        .withColumn("is_product_material", F.col("material_type") == "ZFRT")
    )


@dlt.table(name=f"{SILVER}.enterprise_route_leg", comment="Monthly MRP snapshot route legs, swapped from procurement to goods-flow direction",
           table_properties={"quality": "silver"})
def enterprise_route_leg():
    return (
        bronze("mrp_route_legs")
        .select(
            F.col("snapshot_month").alias("year_month"),
            F.col("material_number"),
            F.col("supplying_plant").alias("origin_plant"),   # swap: procurement -> goods flow
            F.col("receiving_plant").alias("dest_plant"),
        )
        .withColumn("directed_lane_id", F.concat_ws("-", "origin_plant", "dest_plant"))
        .dropDuplicates(["year_month", "material_number", "directed_lane_id"])
    )


@dlt.table(name=f"{SILVER}.enterprise_gl_line_item", comment="GL postings with posting_period normalized (3-char string -> month int)",
           table_properties={"quality": "silver"})
@dlt.expect_all_or_drop({"valid_period": "period_month BETWEEN 1 AND 12"})
def enterprise_gl_line_item():
    return (
        bronze("erp_gl_line_items")
        .withColumn("period_month", F.col("posting_period").cast("int"))
        .withColumn("year_month", F.concat_ws("-", "fiscal_year", F.lpad(F.col("period_month").cast("string"), 2, "0")))
    )


@dlt.table(name=f"{SILVER}.freight_shipments", comment="Unified shipment records: TMS joins, ECC->S4 mapping, leading-zero material fix, CAD->USD conversion, per-line cost allocation",
           table_properties={"quality": "silver"})
@dlt.expect_all_or_drop({
    "valid_origin": "origin_plant IS NOT NULL",
    "valid_dest": "dest_plant IS NOT NULL",
    "nonneg_cost": "freight_cost_usd >= 0",
})
def freight_shipments():
    loads = bronze("tms_load")
    stops = bronze("tms_stop")
    items = bronze("tms_lineitem")
    detail = bronze("tms_lineitem_detail")
    freight = bronze("tms_freight")
    xref = bronze("erp_plant_xref")
    fx = bronze("ref_exchange_rates")
    mat = bronze("erp_material_master").withColumn(
        "material_stripped", F.regexp_replace("material_number", "^0+", "")
    )

    # ECC -> S4 plant code normalization on stops
    stops_n = (
        stops.alias("s")
        .join(xref.alias("x"), F.col("s.plant_code") == F.col("x.plant_ecc"), "left")
        .withColumn("plant_s4_resolved", F.coalesce(F.col("x.plant_s4"), F.col("s.plant_code")))
    )
    pu = stops_n.filter("stop_type = 'PU'").select("load_id", F.col("plant_s4_resolved").alias("origin_plant"))
    do = stops_n.filter("stop_type = 'DO'").select("load_id", F.col("plant_s4_resolved").alias("dest_plant"))

    # canonical material via stripped-key match (handles stripped leading zeros in TMS)
    items_n = (
        items.alias("i")
        .join(mat.alias("m"), F.regexp_replace(F.col("i.material_number"), "^0+", "") == F.col("m.material_stripped"), "left")
        .select(
            F.col("i.lineitem_id"), F.col("i.load_id"), F.col("i.cases"), F.col("i.weight_kg"),
            F.coalesce(F.col("m.material_number"), F.col("i.material_number")).alias("material_number"),
            F.coalesce(F.col("m.material_type") == "ZFRT", F.lit(False)).alias("is_product_material"),
        )
    )
    load_cases = items_n.groupBy("load_id").agg(F.sum("cases").alias("load_total_cases"))

    return (
        items_n.alias("i")
        .join(loads.alias("l"), "load_id")
        .join(pu, "load_id").join(do, "load_id")
        .join(freight.alias("f"), "load_id")
        .join(load_cases, "load_id")
        .join(detail.alias("d").select("lineitem_id", "allocated_cases"), "lineitem_id", "left")
        .withColumn("year_month", F.substring("ship_date", 1, 7))
        .join(fx.filter("from_currency = 'CAD'").select(F.col("year_month").alias("fx_month"), "rate"),
              F.col("year_month") == F.col("fx_month"), "left")
        .withColumn("fx_rate", F.when(F.col("currency") == "CAD", F.coalesce(F.col("rate"), F.lit(0.73))).otherwise(F.lit(1.0)))
        .withColumn("load_cost_usd", (F.col("linehaul_cost") + F.col("fuel_surcharge")) * F.col("fx_rate"))
        .withColumn("freight_cost_usd", F.col("load_cost_usd") * F.col("cases") / F.col("load_total_cases"))
        .withColumn("directed_lane_id", F.concat_ws("-", "origin_plant", "dest_plant"))
        .withColumn("lane_material_period_id", F.concat_ws("|", "directed_lane_id", "material_number", "year_month"))
        .withColumn("is_self_loop", F.col("origin_plant") == F.col("dest_plant"))
        .select(
            "lineitem_id", "load_id", "carrier", "transport_mode", "ship_date", "year_month",
            "origin_plant", "dest_plant", "directed_lane_id", "material_number", "is_product_material",
            "cases", F.col("allocated_cases"), "weight_kg", "freight_cost_usd",
            "lane_material_period_id", "is_self_loop",
        )
    )


@dlt.table(name=f"{SILVER}.transport_lane_paths", comment="Multi-hop supply paths decomposed into individual directed lane legs",
           table_properties={"quality": "silver"})
def transport_lane_paths():
    spk = bronze("mrp_supply_paths")
    hops = (
        spk.withColumn("plants_arr", F.split("path_plants", ">"))
        .withColumn("hop_index", F.explode(F.sequence(F.lit(0), F.size("plants_arr") - F.lit(2))))
        .withColumn("origin_plant", F.col("plants_arr")[F.col("hop_index")])
        .withColumn("dest_plant", F.col("plants_arr")[F.col("hop_index") + 1])
    )
    return hops.select(
        "path_id", "material_number", "hop_index", "n_hops",
        "origin_plant", "dest_plant",
        F.concat_ws("-", "origin_plant", "dest_plant").alias("directed_lane_id"),
        (F.col("hop_index") == 0).alias("is_manufacturing_leg"),
        (F.col("hop_index") == F.col("n_hops") - 1).alias("is_fulfillment_leg"),
        (F.col("origin_plant") == F.col("dest_plant")).alias("is_self_loop"),
    )

# ---------------------------------------------------------------- GOLD

@dlt.table(name=f"{GOLD}.lane_material_sot", comment="Source of truth: one row per lane x material x month, time-aware classified as planned / out_of_lane / theoretical",
           table_properties={"quality": "gold"})
@dlt.expect_all({
    "valid_class": "lane_type IN ('planned_transport','out_of_lane_transport','theoretical_transport')",
})
def lane_material_sot():
    freight = (
        spark.read.table(f"{SILVER}.freight_shipments")
        .filter("is_product_material AND NOT is_self_loop")
        .groupBy("directed_lane_id", "origin_plant", "dest_plant", "material_number", "year_month")
        .agg(
            F.sum("cases").alias("total_cases"),
            F.sum("allocated_cases").alias("allocated_cases"),
            F.sum("freight_cost_usd").alias("total_freight_usd"),
            F.countDistinct("load_id").alias("distinct_shipments"),
            F.array_sort(F.collect_set("transport_mode")).alias("transport_modes"),
        )
        .withColumn("avg_cost_per_case", F.col("total_freight_usd") / F.col("total_cases"))
    )
    plan = spark.read.table(f"{SILVER}.enterprise_route_leg").select(
        "directed_lane_id", "origin_plant", "dest_plant", "material_number", "year_month", F.lit(True).alias("in_plan")
    )
    joined = (
        freight.alias("f")
        .join(plan.alias("p"), ["directed_lane_id", "origin_plant", "dest_plant", "material_number", "year_month"], "full_outer")
        .withColumn(
            "lane_type",
            F.when(F.col("in_plan").isNotNull() & F.col("total_cases").isNotNull(), "planned_transport")
            .when(F.col("total_cases").isNotNull(), "out_of_lane_transport")
            .otherwise("theoretical_transport"),
        )
    )

    # shuttle lane injection: private-fleet lanes invisible to the TMS
    months = bronze("ref_exchange_rates").select("year_month").distinct()
    shuttle = (
        bronze("ref_shuttle_lanes").crossJoin(months)
        .select(
            F.concat_ws("-", "origin_plant", "dest_plant").alias("directed_lane_id"),
            "origin_plant", "dest_plant",
            F.lit("SHUTTLE").alias("material_number"), "year_month",
            F.col("monthly_cases").cast("long").alias("total_cases"),
            F.col("monthly_cases").cast("long").alias("allocated_cases"),
            F.lit(0.0).alias("total_freight_usd"),
            F.lit(1).cast("long").alias("distinct_shipments"),
            F.array(F.lit("SHUTTLE")).alias("transport_modes"),
            F.lit(0.0).alias("avg_cost_per_case"),
            F.lit(True).alias("in_plan"),
            F.lit("planned_transport").alias("lane_type"),
        )
    )
    plants = spark.read.table(f"{SILVER}.enterprise_plant").select(
        "plant_s4", "plant_type", "plant_name", "lat", "lon"
    )
    return (
        joined.unionByName(shuttle, allowMissingColumns=True)
        .join(plants.select(F.col("plant_s4").alias("origin_plant"), F.col("plant_type").alias("origin_type"),
                            F.col("plant_name").alias("origin_name"), F.col("lat").alias("origin_lat"), F.col("lon").alias("origin_lon")),
              "origin_plant", "left")
        .join(plants.select(F.col("plant_s4").alias("dest_plant"), F.col("plant_type").alias("dest_type"),
                            F.col("plant_name").alias("dest_name"), F.col("lat").alias("dest_lat"), F.col("lon").alias("dest_lon")),
              "dest_plant", "left")
        .withColumn("lane_material_period_id", F.concat_ws("|", "directed_lane_id", "material_number", "year_month"))
    )


@dlt.table(name=f"{GOLD}.oor_analysis", comment="Out-of-route (OOR) lane-material-months vs planned baseline cost: costly / cheaper / no_baseline / loop",
           table_properties={"quality": "gold"})
def oor_analysis():
    sot = spark.read.table(f"{GOLD}.lane_material_sot")
    planned = sot.filter("lane_type = 'planned_transport' AND avg_cost_per_case IS NOT NULL")
    lane_mat_base = planned.groupBy("directed_lane_id", "material_number").agg(F.avg("avg_cost_per_case").alias("b1"))
    mat_base = planned.groupBy("material_number").agg(F.avg("avg_cost_per_case").alias("b2"))
    lane_base = planned.groupBy("directed_lane_id").agg(F.avg("avg_cost_per_case").alias("b3"))
    dest_base = planned.groupBy("dest_plant").agg(F.avg("avg_cost_per_case").alias("b4"))

    self_loops = (
        spark.read.table(f"{SILVER}.freight_shipments")
        .filter("is_self_loop AND is_product_material")
        .groupBy("directed_lane_id", "origin_plant", "dest_plant", "material_number", "year_month")
        .agg(F.sum("cases").alias("total_cases"), F.sum("freight_cost_usd").alias("total_freight_usd"),
             F.countDistinct("load_id").alias("distinct_shipments"))
        .withColumn("avg_cost_per_case", F.col("total_freight_usd") / F.col("total_cases"))
        .withColumn("lane_type", F.lit("out_of_lane_transport"))
        .withColumn("is_loop", F.lit(True))
    )
    oor = (
        sot.filter("lane_type = 'out_of_lane_transport'")
        .select("directed_lane_id", "origin_plant", "dest_plant", "material_number", "year_month",
                "total_cases", "total_freight_usd", "distinct_shipments", "avg_cost_per_case", "lane_type")
        .withColumn("is_loop", F.col("origin_plant") == F.col("dest_plant"))
        .unionByName(self_loops.select("directed_lane_id", "origin_plant", "dest_plant", "material_number",
                                       "year_month", "total_cases", "total_freight_usd", "distinct_shipments",
                                       "avg_cost_per_case", "lane_type", "is_loop"))
    )
    mat = spark.read.table(f"{SILVER}.enterprise_material_master").select("material_number", "material_desc", "family")
    return (
        oor
        .join(lane_mat_base, ["directed_lane_id", "material_number"], "left")
        .join(mat_base, "material_number", "left")
        .join(lane_base, "directed_lane_id", "left")
        .join(dest_base, "dest_plant", "left")
        .withColumn("baseline_cost_per_case", F.coalesce("b1", "b2", "b3", "b4"))
        .withColumn("baseline_tier",
                    F.when(F.col("b1").isNotNull(), 1).when(F.col("b2").isNotNull(), 2)
                    .when(F.col("b3").isNotNull(), 3).when(F.col("b4").isNotNull(), 4))
        .withColumn("extra_cost_per_case", F.col("avg_cost_per_case") - F.col("baseline_cost_per_case"))
        .withColumn("total_cost_impact", F.col("extra_cost_per_case") * F.col("total_cases"))
        .withColumn("drill_tab",
                    F.when(F.col("is_loop"), "loops")
                    .when(F.col("baseline_cost_per_case").isNull(), "no_baseline")
                    .when(F.col("extra_cost_per_case") > 0, "costly_oor")
                    .otherwise("cheaper_oor"))
        .join(mat, "material_number", "left")
        .drop("b1", "b2", "b3", "b4")
    )


@dlt.table(name=f"{GOLD}.lane_monthly", comment="Lane-level monthly rollup across materials for the default map view",
           table_properties={"quality": "gold"})
def lane_monthly():
    sot = spark.read.table(f"{GOLD}.lane_material_sot").filter("material_number != 'SHUTTLE'")
    return (
        sot.groupBy("directed_lane_id", "origin_plant", "dest_plant", "year_month",
                    "origin_lat", "origin_lon", "dest_lat", "dest_lon")
        .agg(
            F.sum(F.when(F.col("lane_type") == "planned_transport", 1).otherwise(0)).alias("n_planned"),
            F.sum(F.when(F.col("lane_type") == "out_of_lane_transport", 1).otherwise(0)).alias("n_oor"),
            F.sum(F.when(F.col("lane_type") == "theoretical_transport", 1).otherwise(0)).alias("n_theoretical"),
            F.sum(F.coalesce("total_cases", F.lit(0))).alias("total_cases"),
            F.sum(F.coalesce("allocated_cases", F.lit(0))).alias("allocated_cases"),
            F.sum(F.coalesce("total_freight_usd", F.lit(0.0))).alias("total_freight_usd"),
            F.sum(F.coalesce("distinct_shipments", F.lit(0))).alias("shipments"),
            F.countDistinct("material_number").alias("n_materials"),
        )
    )


@dlt.table(name=f"{GOLD}.plant_stats", comment="Per-plant network stats for map + detail panel",
           table_properties={"quality": "gold"})
def plant_stats():
    sot = spark.read.table(f"{GOLD}.lane_material_sot")
    outb = sot.groupBy(F.col("origin_plant").alias("plant_s4")).agg(
        F.countDistinct("directed_lane_id").alias("outbound_lanes"),
        F.sum(F.coalesce("total_cases", F.lit(0))).alias("outbound_cases"))
    inb = sot.groupBy(F.col("dest_plant").alias("plant_s4")).agg(
        F.countDistinct("directed_lane_id").alias("inbound_lanes"),
        F.sum(F.coalesce("total_cases", F.lit(0))).alias("inbound_cases"))
    return (
        spark.read.table(f"{SILVER}.enterprise_plant")
        .join(outb, "plant_s4", "left").join(inb, "plant_s4", "left")
        .fillna(0, ["outbound_lanes", "outbound_cases", "inbound_lanes", "inbound_cases"])
    )


@dlt.table(name=f"{GOLD}.material_period_status", comment="Material x month data-availability for dropdown color coding",
           table_properties={"quality": "gold"})
def material_period_status():
    sot = spark.read.table(f"{GOLD}.lane_material_sot").filter("material_number != 'SHUTTLE'")
    per_month = sot.groupBy("material_number", "year_month").agg(
        F.max(F.when(F.col("lane_type") != "theoretical_transport", 1).otherwise(0)).alias("has_freight"),
        F.max(F.lit(1)).alias("has_any"),
    )
    mat = spark.read.table(f"{SILVER}.enterprise_material_master").filter("is_product_material")
    return mat.select("material_number", "material_desc", "family").join(per_month, "material_number", "left")


@dlt.table(name=f"{GOLD}.sales_monthly", comment="GL sales rollup at plant x material x month (Show Sales overlay)",
           table_properties={"quality": "gold"})
def sales_monthly():
    return (
        spark.read.table(f"{SILVER}.enterprise_gl_line_item")
        .groupBy(F.col("plant").alias("plant_s4"), "material_number", "year_month")
        .agg(F.sum("amount_usd").alias("sales_usd"), F.sum("quantity_cases").alias("sales_cases"))
    )


@dlt.table(name=f"{GOLD}.inventory_monthly", comment="Stock levels at plant x material x month (Show Stock overlay)",
           table_properties={"quality": "gold"})
def inventory_monthly():
    return (
        bronze("erp_inventory_monthly")
        .select(F.col("plant").alias("plant_s4"), "material_number", "year_month",
                "qty_on_hand_cases", "safety_stock_cases")
    )
