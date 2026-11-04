# Executed notebook: `genai_reroute_recommendations`

_Task run `39331546981006` of job run `285440164007553` · result **SUCCESS** · 37s_


# 05 · Gen AI — planner-ready reroute recommendations (`ai_query`)
The ML model says *which* lanes leak money; transportation planners still need to know *what to do* on Monday.
For the top-risk lanes in `netopt_gold.lane_watchlist`, Databricks AI Functions (`ai_query` → Claude on Model
Serving) turn the numbers into a short, grounded action: the action type, the planned lane to move volume back to,
and the $ at stake. Only facts from the row are passed to the LLM (no free-form data access), and the response is
constrained to a JSON schema so it can be stored, filtered and actioned.

Output: `netopt_gold.lane_action_queue` (CDF on, PK `directed_lane_id`) → synced to **Lakebase** for the app.

```python
dbutils.widgets.text("catalog", "cpg_demos")
dbutils.widgets.text("llm_endpoint", "databricks-claude-sonnet-4-5")
dbutils.widgets.text("top_n", "40")
CAT = dbutils.widgets.get("catalog")
LLM = dbutils.widgets.get("llm_endpoint")
TOP_N = int(dbutils.widgets.get("top_n"))
GOLD = f"{CAT}.netopt_gold"
print(f"endpoint={LLM}  top_n={TOP_N}")
```

**Output:**
```text
endpoint=databricks-claude-sonnet-4-5  top_n=40
```

```python
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
```

**Output:**
```text
You are a senior transportation planner at a frozen-food manufacturer. Write a recommendation for ONE freight lane
that keeps receiving out-of-route (unplanned) shipments. Use ONLY the facts below; do not invent numbers.

Lane: 2508-2552 (Drummondville Plant -> Eagan DC), MFG to INT_DC
Window: 2026-02 to 2026-04
Out-of-route events: 94 across 46 SKUs, 115434.0 cases. Top family: Toppings (TOPPINGS DAIRY TOPPING 12OZ 24CT)
ML probability a move on this lane costs more than plan: 0.64
Expected leakage per month (ML): $46,693
Realised leakage in window: $180,662
Lane miles vs the materials planned miles: 1004.3 vs 520.8
Closest planned alternative: Columbus DC (lane 2508-2551, $1.69/case)

Return JSON with:
- action_type: one of REROUTE_TO_PLAN, CONSOLIDATE_LOADS, FIX_MRP_PLAN, RENEGOTIATE_RATE, MONITOR
- recommendation: 2 sentences max, imperative voice, name the planned alternative node if rerouting, cite the $ figure
- owner: the role that should act (e.g. "DC transportation planner", "Supply planner", "Procurement - freight")
```

```python
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
```

**Output:**
```text
rows=40  llm_errors=0
```

**Output:**
```text
action_type     | lanes | exp_monthly_leakage_usd
----------------+-------+------------------------
FIX_MRP_PLAN    | 26    | 569063.0               
REROUTE_TO_PLAN | 14    | 292840.0               
[2 rows]
```

### Generated recommendations (top 10, verbatim model output)

```python
for r in q.orderBy("priority_rank").limit(10).collect():
    print(f"#{r.priority_rank} {r.directed_lane_id} {r.origin_name} -> {r.dest_name} | p_costly={r.avg_p_costly:.2f} "
          f"| exp ${r.expected_monthly_leakage_usd:,.0f}/mo | {r.risk_tier}")
    print(f"   [{r.action_type}] owner: {r.action_owner}")
    print(f"   {r.recommendation}\n")
```

**Output:**
```text
#1 2508-2552 Drummondville Plant -> Eagan DC | p_costly=0.64 | exp $46,693/mo | MEDIUM
   [FIX_MRP_PLAN] owner: Supply planner
   Correct the MRP plan to route shipments to Columbus DC (lane 2508-2551) at $1.69/case instead of sending unplanned moves to Eagan DC, which travels 1004 miles versus the planned 521 miles. This will eliminate the $180,662 realized leakage across 94 out-of-route events involving 115,434 cases.

#2 2508-2542 Drummondville Plant -> Bolingbrook DC | p_costly=0.62 | exp $43,001/mo | MEDIUM
   [FIX_MRP_PLAN] owner: Supply planner
   Add lane 2508-2542 (Drummondville Plant to Bolingbrook DC) to the materials plan, as 98 out-of-route events across 55 SKUs generated $55,424 in realized leakage with no planned alternative available. The lane is running 827.6 miles versus 489.5 planned miles, indicating systematic demand that should be formalized in the network plan.

#3 2508-2551 Drummondville Plant -> Columbus DC | p_costly=0.60 | exp $41,503/mo | MEDIUM
   [FIX_MRP_PLAN] owner: Supply planner
   Add lane 2508-2551 (Drummondville Plant to Columbus DC) to the materials plan, as 114 out-of-route events across 63 SKUs resulted in $87,130 realized leakage over the three-month window. The lane is running 200 miles longer than planned (670.2 vs 470.0 miles) with no planned alternative available, indicating a systematic planning gap rather than execution error.

#4 2507-2540 Joliet Plant -> Atlanta DC | p_costly=0.67 | exp $36,909/mo | HIGH
   [REROUTE_TO_PLAN] owner: Supply planner
   Reroute the 116 out-of-route shipments (142,459 cases) from Joliet Plant to Columbus DC instead of Atlanta DC, using the planned alternative lane 2507-2551 at $0.47/case. This will eliminate the $54,174 realized leakage caused by shipping 573.9 miles instead of the planned 346.2 miles.

#5 2503-2545 McAllen Plant -> Aurora DC | p_costly=0.68 | exp $31,931/mo | HIGH
   [FIX_MRP_PLAN] owner: Supply planner
   Correct the MRP plan to route Sweet Dough products to Kansas City DC (lane 2503-2548 at $1.87/case) instead of Aurora DC, as the 63 out-of-route events across 27 SKUs resulted in $68,488 realized leakage over three months due to unplanned miles (1009 vs 598 planned). This will eliminate the high-probability cost overruns (ML probability 0.68) and prevent the expected $31,931 monthly leakage.

#6 2502-2553 Dayton Plant -> Memphis DC | p_costly=0.62 | exp $31,846/mo | MEDIUM
   [REROUTE_TO_PLAN] owner: DC transportation planner
   Reroute the 125 out-of-route shipments from Dayton Plant to Charlotte DC (lane 2502-2550) instead of Memphis DC to eliminate the 452.2-mile deviation from the planned 307.5-mile route. This will address the $79,762 realized leakage and prevent the expected $31,846 monthly leakage going forward.

#7 2501-2540 Rochester Plant -> Atlanta DC | p_costly=0.70 | exp $30,289/mo | HIGH
   [FIX_MRP_PLAN] owner: Supply planner
   Correct the MRP plan to route Pizza Crust and other SKUs to the planned Charlotte DC (lane 2501-2550 at $1.02/case) instead of Atlanta DC, which is causing 745.7 miles vs 364.1 planned miles. This will eliminate the $32,734 realized leakage and prevent the expected $30,289 monthly leakage going forward.

#8 2508-2550 Drummondville Plant -> Charlotte DC | p_costly=0.60 | exp $29,681/mo | MEDIUM
   [REROUTE_TO_PLAN] owner: DC transportation planner
   Reroute the 100 out-of-route shipments (117,640 cases) from Drummondville Plant to the planned alternative Eagan DC (lane 2508-2552) at $1.89/case instead of continuing unplanned moves to Charlotte DC. This will eliminate the $75,146 realized leakage and prevent future monthly losses of $29,681.

#9 2507-2551 Joliet Plant -> Columbus DC | p_costly=0.48 | exp $26,826/mo | LOW
   [FIX_MRP_PLAN] owner: Supply planner
   Fix the MRP plan to route Cakes & Desserts shipments directly to Columbus DC instead of triggering 112 out-of-route events across 59 SKUs. This will eliminate the $26,826 expected monthly leakage and prevent the 147,330 cases from being misrouted.

#10 2502-2542 Dayton Plant -> Bolingbrook DC | p_costly=0.42 | exp $25,557/mo | LOW
   [FIX_MRP_PLAN] owner: Supply planner
   Add lane 2502-2542 (Dayton Plant to Bolingbrook DC) to the materials plan, as 96 out-of-route events across 50 SKUs (150,828 cases) indicate a systematic demand pattern with no planned alternative currently available. This will prevent the expected monthly leakage of $25,557 and formalize this 243-mile lane that is operationally necessary.
```
