# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Unity Catalog — govern it
# MAGIC Every layer of the journey lives in one governed catalog (`cpg_demos`):
# MAGIC
# MAGIC | Schema | Role |
# MAGIC |---|---|
# MAGIC | `netopt_raw` | landing **volume** for raw source extracts |
# MAGIC | `netopt_bronze` | Lakeflow Auto Loader streaming tables (raw, + `_source_file`, `_ingested_at`) |
# MAGIC | `netopt_silver` | conformed enterprise entities (expectations enforced) |
# MAGIC | `netopt_gold` | business-ready lane/OOR/route tables + ML scores + GenAI recommendations |
# MAGIC | `netopt_ml` | registered model `oor_cost_risk` |
# MAGIC
# MAGIC This notebook applies and **prints** the governance controls: classification tags, a column mask protecting
# MAGIC commercially-sensitive carrier contract rates, least-privilege grants, data-quality expectation results from the
# MAGIC Lakeflow event log, and lineage from system tables.

# COMMAND ----------

dbutils.widgets.text("catalog", "cpg_demos")
dbutils.widgets.text("warehouse_id", "")
CAT = dbutils.widgets.get("catalog")
RAW, BRONZE, SILVER, GOLD, ML = (f"{CAT}.netopt_{s}" for s in ("raw", "bronze", "silver", "gold", "ml"))


def run(sql: str, show: bool = False):
    """Execute a governance statement and log it, so the run output is a readable audit trail."""
    try:
        df = spark.sql(sql)
        print(f"OK    {' '.join(sql.split())[:150]}")
        if show:
            df.show(100, truncate=False)
        return None if show else df
    except Exception as e:  # keep going: one unsupported statement shouldn't hide the rest of the audit
        print(f"SKIP  {' '.join(sql.split())[:150]}\n      -> {str(e).splitlines()[0][:200]}")
        return None

# COMMAND ----------
# MAGIC %md ## 1. Classification tags (schema + table level)

# COMMAND ----------

# Tag keys below are governed by workspace tag policies (allowed values enforced by Unity Catalog):
#   domain in {supply_chain,...}, layer in {bronze,silver,gold}, owner_team in {analytics,...}, classification, certified
SCHEMA_TAGS = {
    RAW: ("bronze", "landing"), BRONZE: ("bronze", "ingest"), SILVER: ("silver", "conformed"),
    GOLD: ("gold", "business"), ML: ("gold", "models"),
}
for schema, (layer, purpose) in SCHEMA_TAGS.items():
    run(f"""ALTER SCHEMA {schema} SET TAGS ('domain' = 'supply_chain', 'layer' = '{layer}',
            'purpose' = '{purpose}', 'data_origin' = 'synthetic', 'owner_team' = 'analytics')""")

GOLD_TABLES = {
    "lane_material_sot": "internal", "oor_analysis": "confidential", "lane_monthly": "internal",
    "plant_stats": "internal", "material_period_status": "internal", "sales_monthly": "confidential",
    "inventory_monthly": "internal",
}
for t, cls in GOLD_TABLES.items():
    run(f"ALTER MATERIALIZED VIEW {GOLD}.{t} SET TAGS ('classification' = '{cls}', 'certified' = 'true')")
run(f"ALTER TABLE {GOLD}.material_routes SET TAGS ('classification' = 'confidential', 'certified' = 'true')")
run(f"ALTER STREAMING TABLE {BRONZE}.tms_rate SET TAGS ('classification' = 'restricted', 'contains' = 'carrier_contract_rates')")
run(f"ALTER STREAMING TABLE {BRONZE}.tms_freight SET TAGS ('classification' = 'confidential', 'contains' = 'freight_invoices')")

# COMMAND ----------
# MAGIC %md ## 2. Column-level protection — carrier contract rates are masked unless you are in `netopt-procurement`

# COMMAND ----------

run(f"""CREATE OR REPLACE FUNCTION {GOLD}.mask_contract_rate(rate DOUBLE)
        RETURNS DOUBLE
        COMMENT 'Column mask: contracted $/mile visible only to members of the netopt-procurement group'
        RETURN CASE WHEN is_account_group_member('netopt-procurement') THEN rate ELSE NULL END""")

run(f"""CREATE OR REPLACE TABLE {GOLD}.carrier_rate_card
        COMMENT 'Published carrier rate card per lane (rate_per_mile is column-masked)'
        AS SELECT lane_id, carrier, contract_id, CAST(rate_per_mile AS DOUBLE) AS rate_per_mile
        FROM {BRONZE}.tms_rate""")
run(f"ALTER TABLE {GOLD}.carrier_rate_card ALTER COLUMN rate_per_mile SET MASK {GOLD}.mask_contract_rate")
run(f"ALTER TABLE {GOLD}.carrier_rate_card ALTER COLUMN rate_per_mile SET TAGS ('classification' = 'restricted', 'contains' = 'carrier_contract_rates')")
run(f"ALTER TABLE {GOLD}.carrier_rate_card SET TAGS ('classification' = 'restricted')")

print("\nWhat a non-procurement user (this job's identity) sees — rate_per_mile is masked to NULL:")
run(f"SELECT lane_id, carrier, contract_id, rate_per_mile FROM {GOLD}.carrier_rate_card ORDER BY lane_id LIMIT 5", show=True)
run(f"""SELECT count(*) AS rows, count(rate_per_mile) AS visible_rates FROM {GOLD}.carrier_rate_card""", show=True)

# COMMAND ----------
# MAGIC %md ## 3. Column documentation on the business-facing route table

# COMMAND ----------

ROUTE_COLS = {
    "route_path": "Plant sequence of the reconstructed route, e.g. 2501>2547>2580",
    "category": "Planned + Happened | Happened Not Planned | Planned Not Happened | Loop",
    "route_cost_per_case": "Transport + storage cost per case along the whole route (USD)",
    "baseline_cost_per_case": "Cheapest comparable planned route cost per case (5-tier cascade)",
    "baseline_tier": "1 = same origin/dest planned route ... 4 = network-average fallback; NULL = no baseline",
    "extra_cost_per_case": "route_cost_per_case - baseline_cost_per_case (positive = leakage)",
    "total_cost_impact": "extra_cost_per_case x route_cases (USD)",
}
for c, cm in ROUTE_COLS.items():
    run(f"ALTER TABLE {GOLD}.material_routes ALTER COLUMN {c} COMMENT '{cm}'")

# COMMAND ----------
# MAGIC %md ## 4. Least-privilege access — business readers get gold only; raw/bronze stay with engineering

# COMMAND ----------

run(f"GRANT USE SCHEMA, SELECT ON SCHEMA {GOLD} TO `account users`")
run(f"GRANT EXECUTE ON FUNCTION {GOLD}.mask_contract_rate TO `account users`")
for s in (GOLD, BRONZE):
    print(f"\nGrants on {s}:")
    run(f"SHOW GRANTS ON SCHEMA {s}", show=True)

# COMMAND ----------
# MAGIC %md ## 5. Data quality — Lakeflow expectation results from the pipeline event log

# COMMAND ----------

dq = run(f"""
  WITH ev AS (
    SELECT origin.flow_name AS flow, explode(from_json(details:flow_progress:data_quality:expectations,
           'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS e
    FROM event_log(TABLE({SILVER}.freight_shipments))
    WHERE event_type = 'flow_progress' AND details:flow_progress:data_quality:expectations IS NOT NULL
      AND origin.update_id = (SELECT origin.update_id FROM event_log(TABLE({SILVER}.freight_shipments))
                              WHERE event_type = 'create_update' ORDER BY timestamp DESC LIMIT 1))
  SELECT e.dataset, e.name AS expectation, sum(e.passed_records) AS passed, sum(e.failed_records) AS failed_dropped
  FROM ev GROUP BY 1, 2 ORDER BY 1, 2""", show=True)

run(f"""
  SELECT timestamp, event_type, message FROM event_log(TABLE({SILVER}.freight_shipments))
  WHERE event_type IN ('create_update', 'update_progress') ORDER BY timestamp DESC LIMIT 8""", show=True)

# COMMAND ----------
# MAGIC %md ## 6. Lineage (system.access.table_lineage) and the resulting tag inventory

# COMMAND ----------

run(f"""
  SELECT DISTINCT source_table_full_name, target_table_full_name
  FROM system.access.table_lineage
  WHERE target_table_catalog = '{CAT}' AND target_table_schema LIKE 'netopt_%'
    AND source_table_full_name IS NOT NULL
  ORDER BY target_table_full_name, source_table_full_name LIMIT 60""", show=True)

run(f"""SELECT schema_name, tag_name, tag_value FROM {CAT}.information_schema.schema_tags
        WHERE schema_name LIKE 'netopt_%' ORDER BY schema_name, tag_name""", show=True)
run(f"""SELECT schema_name, table_name, tag_name, tag_value FROM {CAT}.information_schema.table_tags
        WHERE schema_name LIKE 'netopt_%' ORDER BY schema_name, table_name, tag_name""", show=True)
run(f"""SELECT table_name, column_name, tag_name, tag_value FROM {CAT}.information_schema.column_tags
        WHERE schema_name LIKE 'netopt_%'""", show=True)
