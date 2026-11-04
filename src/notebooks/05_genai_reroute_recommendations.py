# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Gen AI — planner-ready reroute recommendations (`ai_query`)
# MAGIC The ML model says *which* lanes leak money; transportation planners still need to know *what to do* on Monday.
# MAGIC For the top-risk lanes in `netopt_gold.lane_watchlist`, Databricks AI Functions (`ai_query` → Claude on Model
# MAGIC Serving) turn the numbers into a short, grounded action: the action type, the planned lane to move volume back to,
# MAGIC and the $ at stake. Only facts from the row are passed to the LLM (no free-form data access), and the response is
# MAGIC constrained to a JSON schema so it can be stored, filtered and actioned.
# MAGIC
# MAGIC Output: `netopt_gold.lane_action_queue` (CDF on, PK `directed_lane_id`) → synced to **Lakebase** for the app.

# COMMAND ----------

dbutils.widgets.text("catalog", "cpg_demos")
dbutils.widgets.text("llm_endpoint", "databricks-claude-sonnet-4-5")
dbutils.widgets.text("top_n", "40")
CAT = dbutils.widgets.get("catalog")
LLM = dbutils.widgets.get("llm_endpoint")
TOP_N = int(dbutils.widgets.get("top_n"))
GOLD = f"{CAT}.netopt_gold"
print(f"endpoint={LLM}  top_n={TOP_N}")

# COMMAND ----------

PROMPT = """You are a senior transportation planner at a frozen-food manufacturer. Write a recommendation for ONE freight lane
that keeps receiving out-of-route (unplanned) shipments. Use ONLY the facts below; do not invent numbers.

Lane: {lane} ({origin} -> {dest}), {origin_type} to {dest_type}
Window: {window}
Out-of-route events: {events} across {skus} SKUs, {cases} cases. Top family: {family} ({top_sku})
ML probability a move on this lane costs more than plan: {p}
Expected leakage per month (ML): ${exp_leak}
Realised leakage in window: ${real_leak}
Lane miles vs the material's planned miles: {miles} vs {planned_miles}
Closest planned alternative: {alt}

Return JSON with:
- action_type: one of REROUTE_TO_PLAN, CONSOLIDATE_LOADS, FIX_MRP_PLAN, RENEGOTIATE_RATE, MONITOR
- recommendation: 2 sentences max, imperative voice, name the planned alternative node if rerouting, cite the $ figure
- owner: the role that should act (e.g. "DC transportation planner", "Supply planner", "Procurement - freight")"""

spark.sql(f"""
CREATE OR REPLACE TEMP VIEW recs_input AS
SELECT *, format_string(
  '{PROMPT.replace("'", "''").replace("{lane}", "%1$s").replace("{origin}", "%2$s").replace("{dest}", "%3$s")
    .replace("{origin_type}", "%4$s").replace("{dest_type}", "%5$s").replace("{window}", "%6$s")
    .replace("{events}", "%7$s").replace("{skus}", "%8$s").replace("{cases}", "%9$s").replace("{family}", "%10$s")
    .replace("{top_sku}", "%11$s").replace("{p}", "%12$s").replace("{exp_leak}", "%13$s").replace("{real_leak}", "%14$s")
    .replace("{miles}", "%15$s").replace("{planned_miles}", "%16$s").replace("{alt}", "%17$s")}',
  directed_lane_id, origin_name, dest_name, origin_type, dest_type, concat(window_start, ' to ', window_end),
  oor_events, skus, oor_cases, top_family, top_material_desc, format_number(avg_p_costly, 2),
  format_number(expected_monthly_leakage_usd, 0), format_number(realized_leakage_usd, 0),
  cast(lane_miles AS string), coalesce(cast(planned_miles AS string), 'n/a'),
  coalesce(concat(alt_dest_name, ' (lane ', alt_lane_id, ', $', format_number(alt_cost_per_case, 2), '/case)'), 'none on plan')
) AS prompt
FROM {GOLD}.lane_watchlist
ORDER BY expected_monthly_leakage_usd DESC
LIMIT {TOP_N}
""")
print(spark.table("recs_input").select("prompt").first()[0])

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {GOLD}.lane_action_queue
COMMENT 'Top-risk OOR lanes with ML scores + GenAI (ai_query) recommended action; synced to Lakebase for the planner app'
TBLPROPERTIES (delta.enableChangeDataFeed = true)
AS
WITH gen AS (
  SELECT *, ai_query('{LLM}', prompt,
      responseFormat => 'STRUCT<rec:STRUCT<action_type:STRING, recommendation:STRING, owner:STRING>>',
      failOnError => false) AS llm
  FROM recs_input),
parsed AS (  -- structured output may come back wrapped ({{"rec": {{...}}}}) or flat ({{...}}); accept both
  SELECT *, coalesce(from_json(llm.result, 'rec STRUCT<action_type STRING, recommendation STRING, owner STRING>').rec,
                     from_json(llm.result, 'action_type STRING, recommendation STRING, owner STRING')) AS rec
  FROM gen)
SELECT directed_lane_id, origin_plant, dest_plant, origin_name, dest_name, origin_type, dest_type,
       top_family, top_material, top_material_desc, oor_events, skus, oor_cases,
       avg_p_costly, expected_monthly_leakage_usd, realized_leakage_usd, net_cost_impact_usd,
       lane_miles, planned_miles, alt_lane_id, alt_dest_plant, alt_dest_name, alt_cost_per_case, risk_tier,
       window_start, window_end,
       rec.action_type AS action_type, rec.recommendation AS recommendation, rec.owner AS action_owner,
       llm.errorMessage AS llm_error,
       '{LLM}' AS llm_endpoint,
       row_number() OVER (ORDER BY expected_monthly_leakage_usd DESC) AS priority_rank,
       current_timestamp() AS generated_at
FROM parsed
""")
spark.sql(f"ALTER TABLE {GOLD}.lane_action_queue ALTER COLUMN directed_lane_id SET NOT NULL")
spark.sql(f"ALTER TABLE {GOLD}.lane_action_queue ADD CONSTRAINT lane_action_queue_pk PRIMARY KEY (directed_lane_id)")

q = spark.table(f"{GOLD}.lane_action_queue")
print(f"rows={q.count()}  llm_errors={q.filter('llm_error IS NOT NULL OR recommendation IS NULL').count()}")
display(spark.sql(f"SELECT action_type, count(*) lanes, round(sum(expected_monthly_leakage_usd)) exp_monthly_leakage_usd "
                  f"FROM {GOLD}.lane_action_queue GROUP BY 1 ORDER BY 3 DESC"))

# COMMAND ----------

# MAGIC %md ### Generated recommendations (top 10, verbatim model output)

# COMMAND ----------

for r in q.orderBy("priority_rank").limit(10).collect():
    print(f"#{r.priority_rank} {r.directed_lane_id} {r.origin_name} -> {r.dest_name} | p_costly={r.avg_p_costly:.2f} "
          f"| exp ${r.expected_monthly_leakage_usd:,.0f}/mo | {r.risk_tier}")
    print(f"   [{r.action_type}] owner: {r.action_owner}")
    print(f"   {r.recommendation}\n")
