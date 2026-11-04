# Executed notebook: `unity_catalog_governance`

_Task run `759731482583924` of job run `285440164007553` · result **SUCCESS** · 49s_


# 03 · Unity Catalog — govern it
Every layer of the journey lives in one governed catalog (`cpg_demos`):

| Schema | Role |
|---|---|
| `netopt_raw` | landing **volume** for raw source extracts |
| `netopt_bronze` | Lakeflow Auto Loader streaming tables (raw, + `_source_file`, `_ingested_at`) |
| `netopt_silver` | conformed enterprise entities (expectations enforced) |
| `netopt_gold` | business-ready lane/OOR/route tables + ML scores + GenAI recommendations |
| `netopt_ml` | registered model `oor_cost_risk` |

This notebook applies and **prints** the governance controls: classification tags, a column mask protecting
commercially-sensitive carrier contract rates, least-privilege grants, data-quality expectation results from the
Lakeflow event log, and lineage from system tables.

```python
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
        return df
    except Exception as e:  # keep going: one unsupported statement shouldn't hide the rest of the audit
        print(f"SKIP  {' '.join(sql.split())[:150]}\n      -> {str(e).splitlines()[0][:200]}")
        return None
```

## 1. Classification tags (schema + table level)

```python
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
```

**Output:**
```text
OK    ALTER SCHEMA cpg_demos.netopt_raw SET TAGS ('domain' = 'supply_chain', 'layer' = 'bronze', 'purpose' = 'landing', 'data_origin' = 'synthetic', 'owner_
OK    ALTER SCHEMA cpg_demos.netopt_bronze SET TAGS ('domain' = 'supply_chain', 'layer' = 'bronze', 'purpose' = 'ingest', 'data_origin' = 'synthetic', 'owne
OK    ALTER SCHEMA cpg_demos.netopt_silver SET TAGS ('domain' = 'supply_chain', 'layer' = 'silver', 'purpose' = 'conformed', 'data_origin' = 'synthetic', 'o
OK    ALTER SCHEMA cpg_demos.netopt_gold SET TAGS ('domain' = 'supply_chain', 'layer' = 'gold', 'purpose' = 'business', 'data_origin' = 'synthetic', 'owner_
OK    ALTER SCHEMA cpg_demos.netopt_ml SET TAGS ('domain' = 'supply_chain', 'layer' = 'gold', 'purpose' = 'models', 'data_origin' = 'synthetic', 'owner_team
OK    ALTER MATERIALIZED VIEW cpg_demos.netopt_gold.lane_material_sot SET TAGS ('classification' = 'internal', 'certified' = 'true')
OK    ALTER MATERIALIZED VIEW cpg_demos.netopt_gold.oor_analysis SET TAGS ('classification' = 'confidential', 'certified' = 'true')
OK    ALTER MATERIALIZED VIEW cpg_demos.netopt_gold.lane_monthly SET TAGS ('classification' = 'internal', 'certified' = 'true')
OK    ALTER MATERIALIZED VIEW cpg_demos.netopt_gold.plant_stats SET TAGS ('classification' = 'internal', 'certified' = 'true')
OK    ALTER MATERIALIZED VIEW cpg_demos.netopt_gold.material_period_status SET TAGS ('classification' = 'internal', 'certified' = 'true')
OK    ALTER MATERIALIZED VIEW cpg_demos.netopt_gold.sales_monthly SET TAGS ('classification' = 'confidential', 'certified' = 'true')
OK    ALTER MATERIALIZED VIEW cpg_demos.netopt_gold.inventory_monthly SET TAGS ('classification' = 'internal', 'certified' = 'true')
OK    ALTER TABLE cpg_demos.netopt_gold.material_routes SET TAGS ('classification' = 'confidential', 'certified' = 'true')
OK    ALTER STREAMING TABLE cpg_demos.netopt_bronze.tms_rate SET TAGS ('classification' = 'restricted', 'contains' = 'carrier_contract_rates')
OK    ALTER STREAMING TABLE cpg_demos.netopt_bronze.tms_freight SET TAGS ('classification' = 'confidential', 'contains' = 'freight_invoices')
```

**Output:**
```text
DataFrame[]
```

## 2. Column-level protection — carrier contract rates are masked unless you are in `netopt-procurement`

```python
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
```

**Output:**
```text
OK    CREATE OR REPLACE FUNCTION cpg_demos.netopt_gold.mask_contract_rate(rate DOUBLE) RETURNS DOUBLE COMMENT 'Column mask: contracted $/mile visible only t
OK    CREATE OR REPLACE TABLE cpg_demos.netopt_gold.carrier_rate_card COMMENT 'Published carrier rate card per lane (rate_per_mile is column-masked)' AS SEL
OK    ALTER TABLE cpg_demos.netopt_gold.carrier_rate_card ALTER COLUMN rate_per_mile SET MASK cpg_demos.netopt_gold.mask_contract_rate
OK    ALTER TABLE cpg_demos.netopt_gold.carrier_rate_card ALTER COLUMN rate_per_mile SET TAGS ('classification' = 'restricted', 'contains' = 'carrier_contra
OK    ALTER TABLE cpg_demos.netopt_gold.carrier_rate_card SET TAGS ('classification' = 'restricted')

What a non-procurement user (this job's identity) sees — rate_per_mile is masked to NULL:
OK    SELECT lane_id, carrier, contract_id, rate_per_mile FROM cpg_demos.netopt_gold.carrier_rate_card ORDER BY lane_id LIMIT 5
+---------+--------+-----------+-------------+
|lane_id  |carrier |contract_id|rate_per_mile|
+---------+--------+-----------+-------------+
|2501-2540|HARBOR  |CTR-00000  |NULL         |
|2501-2540|BLUELINE|CTR-00000  |NULL         |
|2501-2542|ATLAS   |CTR-00001  |NULL         |
|2501-2542|SUMMIT  |CTR-00001  |NULL         |
|2501-2547|REDTAIL |CTR-00002  |NULL         |
+---------+--------+-----------+-------------+

OK    SELECT count(*) AS rows, count(rate_per_mile) AS visible_rates FROM cpg_demos.netopt_gold.carrier_rate_card
+----+-------------+
|rows|visible_rates|
+----+-------------+
|764 |0            |
+----+-------------+
```

**Output:**
```text
DataFrame[rows: bigint, visible_rates: bigint]
```

## 3. Column documentation on the business-facing route table

```python
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
```

**Output:**
```text
OK    ALTER TABLE cpg_demos.netopt_gold.material_routes ALTER COLUMN route_path COMMENT 'Plant sequence of the reconstructed route, e.g. 2501>2547>2580'
OK    ALTER TABLE cpg_demos.netopt_gold.material_routes ALTER COLUMN category COMMENT 'Planned + Happened | Happened Not Planned | Planned Not Happened | Lo
OK    ALTER TABLE cpg_demos.netopt_gold.material_routes ALTER COLUMN route_cost_per_case COMMENT 'Transport + storage cost per case along the whole route (U
OK    ALTER TABLE cpg_demos.netopt_gold.material_routes ALTER COLUMN baseline_cost_per_case COMMENT 'Cheapest comparable planned route cost per case (5-tier
OK    ALTER TABLE cpg_demos.netopt_gold.material_routes ALTER COLUMN baseline_tier COMMENT '1 = same origin/dest planned route ... 4 = network-average fallb
OK    ALTER TABLE cpg_demos.netopt_gold.material_routes ALTER COLUMN extra_cost_per_case COMMENT 'route_cost_per_case - baseline_cost_per_case (positive = l
OK    ALTER TABLE cpg_demos.netopt_gold.material_routes ALTER COLUMN total_cost_impact COMMENT 'extra_cost_per_case x route_cases (USD)'
```

## 4. Least-privilege access — business readers get gold only; raw/bronze stay with engineering

```python
run(f"GRANT USE SCHEMA, SELECT ON SCHEMA {GOLD} TO `account users`")
run(f"GRANT EXECUTE ON FUNCTION {GOLD}.mask_contract_rate TO `account users`")
for s in (GOLD, BRONZE):
    print(f"\nGrants on {s}:")
    run(f"SHOW GRANTS ON SCHEMA {s}", show=True)
```

**Output:**
```text
OK    GRANT USE SCHEMA, SELECT ON SCHEMA cpg_demos.netopt_gold TO `account users`
OK    GRANT EXECUTE ON FUNCTION cpg_demos.netopt_gold.mask_contract_rate TO `account users`

Grants on cpg_demos.netopt_gold:
OK    SHOW GRANTS ON SCHEMA cpg_demos.netopt_gold
+-----------------------------------------+--------------+----------+-----------------------+
|Principal                                |ActionType    |ObjectType|ObjectKey              |
+-----------------------------------------+--------------+----------+-----------------------+
|d6934596-b345-4b96-99ee-2607791d1fb8     |SELECT        |SCHEMA    |cpg_demos.netopt_gold  |
|d6934596-b345-4b96-99ee-2607791d1fb8     |USE SCHEMA    |SCHEMA    |cpg_demos.netopt_gold  |
|account users                            |SELECT        |SCHEMA    |cpg_demos.netopt_gold  |
|account users                            |USE SCHEMA    |SCHEMA    |cpg_demos.netopt_gold  |
|account users                            |READ METADATA |METASTORE |metastore_aws_us_east_1|
|sathish.gangichetty@databricks.com       |ALL PRIVILEGES|CATALOG   |cpg_demos              |
|saurabh.aggarwal@databricks.com          |ALL PRIVILEGES|CATALOG   |cpg_demos              |
|build-user@[redacted]|ALL PRIVILEGES|CATALOG   |cpg_demos              |
|build-user@[redacted]|MANAGE        |CATALOG   |cpg_demos              |
|suraj.bang@databricks.com                |READ METADATA |METASTORE |metastore_aws_us_east_1|
+-----------------------------------------+--------------+----------+-----------------------+


Grants on cpg_demos.netopt_bronze:
OK    SHOW GRANTS ON SCHEMA cpg_demos.netopt_bronze
+-----------------------------------------+--------------+----------+-----------------------+
|Principal                                |ActionType    |ObjectType|ObjectKey              |
+-----------------------------------------+--------------+----------+-----------------------+
|account users                            |READ METADATA |METASTORE |metastore_aws_us_east_1|
|sathish.gangichetty@databricks.com       |ALL PRIVILEGES|CATALOG   |cpg_demos              |
|saurabh.aggarwal@databricks.com          |ALL PRIVILEGES|CATALOG   |cpg_demos              |
|build-user@[redacted]|ALL PRIVILEGES|CATALOG   |cpg_demos              |
|build-user@[redacted]|MANAGE        |CATALOG   |cpg_demos              |
|suraj.bang@databricks.com                |READ METADATA |METASTORE |metastore_aws_us_east_1|
+-----------------------------------------+--------------+----------+-----------------------+
```

## 5. Data quality — Lakeflow expectation results from the pipeline event log

```python
dq = run(f"""
  WITH ev AS (
    SELECT origin.flow_name AS flow, explode(from_json(details:flow_progress:data_quality:expectations,
           'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS e
    FROM event_log(TABLE({SILVER}.freight_shipments))
    WHERE event_type = 'flow_progress' AND details:flow_progress:data_quality:expectations IS NOT NULL)
  SELECT e.dataset, e.name AS expectation, sum(e.passed_records) AS passed, sum(e.failed_records) AS failed_dropped
  FROM ev GROUP BY 1, 2 ORDER BY 1, 2""", show=True)

run(f"""
  SELECT timestamp, event_type, message FROM event_log(TABLE({SILVER}.freight_shipments))
  WHERE event_type IN ('create_update', 'update_progress') ORDER BY timestamp DESC LIMIT 8""", show=True)
```

**Output:**
```text
OK    WITH ev AS ( SELECT origin.flow_name AS flow, explode(from_json(details:flow_progress:data_quality:expectations, 'array<struct<name:string,dataset:str
+--------------------------------------------------+--------------+------+--------------+
|dataset                                           |expectation   |passed|failed_dropped|
+--------------------------------------------------+--------------+------+--------------+
|cpg_demos.netopt_gold.lane_material_sot           |valid_class   |276588|0             |
|cpg_demos.netopt_silver.enterprise_gl_line_item   |valid_period  |121274|0             |
|cpg_demos.netopt_silver.enterprise_material_master|valid_material|4208  |0             |
|cpg_demos.netopt_silver.enterprise_plant          |valid_code    |110   |0             |
|cpg_demos.netopt_silver.enterprise_plant          |valid_coords  |110   |0             |
|cpg_demos.netopt_silver.freight_shipments         |nonneg_cost   |272564|0             |
|cpg_demos.netopt_silver.freight_shipments         |valid_dest    |272564|0             |
|cpg_demos.netopt_silver.freight_shipments         |valid_origin  |272564|0             |
+--------------------------------------------------+--------------+------+--------------+

OK    SELECT timestamp, event_type, message FROM event_log(TABLE(cpg_demos.netopt_silver.freight_shipments)) WHERE event_type IN ('create_update', 'update_p
+-----------------------+---------------+---------------------------------------+
|timestamp              |event_type     |message                                |
+-----------------------+---------------+---------------------------------------+
|2026-11-04 02:39:16.128|update_progress|Update a4f427 is COMPLETED.            |
|2026-11-04 02:38:36.106|update_progress|Update a4f427 is RUNNING.              |
|2026-11-04 02:38:18.436|update_progress|Update a4f427 is SETTING_UP_TABLES.    |
|2026-11-04 02:38:14.942|update_progress|Update a4f427 is RESETTING.            |
|2026-11-04 02:37:11.867|update_progress|Update a4f427 is INITIALIZING.         |
|2026-11-04 02:36:59.888|update_progress|Update a4f427 is WAITING_FOR_RESOURCES.|
|2026-11-04 02:36:57.589|create_update  |Update a4f427 started by JOB_TASK.     |
|2026-11-04 01:37:27.771|update_progress|Update 181b03 is COMPLETED.            |
+-----------------------+---------------+---------------------------------------+
```

**Output:**
```text
DataFrame[timestamp: timestamp, event_type: string, message: string]
```

## 6. Lineage (system.access.table_lineage) and the resulting tag inventory

```python
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
```

**Output:**
```text
OK    SELECT DISTINCT source_table_full_name, target_table_full_name FROM system.access.table_lineage WHERE target_table_catalog = 'cpg_demos' AND target_ta
+--------------------------------------------------+--------------------------------------------------+
|source_table_full_name                            |target_table_full_name                            |
+--------------------------------------------------+--------------------------------------------------+
|cpg_demos.netopt_bronze.tms_rate                  |cpg_demos.netopt_gold.carrier_rate_card           |
|cpg_demos.netopt_bronze.erp_inventory_monthly     |cpg_demos.netopt_gold.inventory_monthly           |
|cpg_demos.netopt_gold.lane_watchlist              |cpg_demos.netopt_gold.lane_action_queue           |
|cpg_demos.netopt_bronze.ref_exchange_rates        |cpg_demos.netopt_gold.lane_material_sot           |
|cpg_demos.netopt_bronze.ref_shuttle_lanes         |cpg_demos.netopt_gold.lane_material_sot           |
|cpg_demos.netopt_silver.enterprise_plant          |cpg_demos.netopt_gold.lane_material_sot           |
|cpg_demos.netopt_silver.enterprise_route_leg      |cpg_demos.netopt_gold.lane_material_sot           |
|cpg_demos.netopt_silver.freight_shipments         |cpg_demos.netopt_gold.lane_material_sot           |
|cpg_demos.netopt_gold.lane_material_sot           |cpg_demos.netopt_gold.lane_monthly                |
|cpg_demos.netopt_gold.lane_material_sot           |cpg_demos.netopt_gold.lane_watchlist              |
|cpg_demos.netopt_gold.oor_risk_scores             |cpg_demos.netopt_gold.lane_watchlist              |
|cpg_demos.netopt_silver.enterprise_plant          |cpg_demos.netopt_gold.lane_watchlist              |
|cpg_demos.netopt_gold.lane_material_sot           |cpg_demos.netopt_gold.material_period_status      |
|cpg_demos.netopt_silver.enterprise_material_master|cpg_demos.netopt_gold.material_period_status      |
|cpg_demos.netopt_gold.lane_material_sot           |cpg_demos.netopt_gold.oor_analysis                |
|cpg_demos.netopt_silver.enterprise_material_master|cpg_demos.netopt_gold.oor_analysis                |
|cpg_demos.netopt_silver.freight_shipments         |cpg_demos.netopt_gold.oor_analysis                |
|cpg_demos.netopt_gold.lane_material_sot           |cpg_demos.netopt_gold.plant_stats                 |
|cpg_demos.netopt_silver.enterprise_plant          |cpg_demos.netopt_gold.plant_stats                 |
|cpg_demos.netopt_silver.enterprise_gl_line_item   |cpg_demos.netopt_gold.sales_monthly               |
|cpg_demos.netopt_gold.plant_stats                 |cpg_demos.netopt_serving.plant_stats              |
|cpg_demos.netopt_bronze.erp_gl_line_items         |cpg_demos.netopt_silver.enterprise_gl_line_item   |
|cpg_demos.netopt_bronze.erp_material_master       |cpg_demos.netopt_silver.enterprise_material_master|
|cpg_demos.netopt_bronze.erp_plant_master          |cpg_demos.netopt_silver.enterprise_plant          |
|cpg_demos.netopt_bronze.erp_plant_xref            |cpg_demos.netopt_silver.enterprise_plant          |
|cpg_demos.netopt_bronze.ref_plant_coordinates     |cpg_demos.netopt_silver.enterprise_plant          |
|cpg_demos.netopt_bronze.mrp_route_legs            |cpg_demos.netopt_silver.enterprise_route_leg      |
|cpg_demos.netopt_bronze.erp_material_master       |cpg_demos.netopt_silver.freight_shipments         |
|cpg_demos.netopt_bronze.erp_plant_xref            |cpg_demos.netopt_silver.freight_shipments         |
|cpg_demos.netopt_bronze.ref_exchange_rates        |cpg_demos.netopt_silver.freight_shipments         |
|cpg_demos.netopt_bronze.tms_freight               |cpg_demos.netopt_silver.freight_shipments         |
|cpg_demos.netopt_bronze.tms_lineitem              |cpg_demos.netopt_silver.freight_shipments         |
|cpg_demos.netopt_bronze.tms_lineitem_detail       |cpg_demos.netopt_silver.freight_shipments         |
|cpg_demos.netopt_bronze.tms_load                  |cpg_demos.netopt_silver.freight_shipments         |
|cpg_demos.netopt_bronze.tms_stop                  |cpg_demos.netopt_silver.freight_shipments         |
|cpg_demos.netopt_bronze.mrp_supply_paths          |cpg_demos.netopt_silver.transport_lane_paths      |
+--------------------------------------------------+--------------------------------------------------+

OK    SELECT schema_name, tag_name, tag_value FROM cpg_demos.information_schema.schema_tags WHERE schema_name LIKE 'netopt_%' ORDER BY schema_name, tag_name
+-------------+-----------+------------+
|schema_name  |tag_name   |tag_value   |
+-------------+-----------+------------+
|netopt_bronze|data_origin|synthetic   |
|netopt_bronze|domain     |supply_chain|
|netopt_bronze|layer      |bronze      |
|netopt_bronze|owner_team |analytics   |
|netopt_bronze|purpose    |ingest      |
|netopt_gold  |data_origin|synthetic   |
|netopt_gold  |domain     |supply_chain|
|netopt_gold  |layer      |gold        |
|netopt_gold  |owner_team |analytics   |
|netopt_gold  |purpose    |business    |
|netopt_ml    |data_origin|synthetic   |
|netopt_ml    |domain     |supply_chain|
|netopt_ml    |layer      |gold        |
|netopt_ml    |owner_team |analytics   |
|netopt_ml    |purpose    |models      |
|netopt_raw   |data_origin|synthetic   |
|netopt_raw   |domain     |supply_chain|
|netopt_raw   |layer      |bronze      |
|netopt_raw   |owner_team |analytics   |
|netopt_raw   |purpose    |landing     |
|netopt_silver|data_origin|synthetic   |
|netopt_silver|domain     |supply_chain|
|netopt_silver|layer      |silver      |
|netopt_silver|owner_team |analytics   |
|netopt_silver|purpose    |conformed   |
+-------------+-----------+------------+

OK    SELECT schema_name, table_name, tag_name, tag_value FROM cpg_demos.information_schema.table_tags WHERE schema_name LIKE 'netopt_%' ORDER BY schema_nam
+-------------+----------------------+--------------+----------------------+
|schema_name  |table_name            |tag_name      |tag_value             |
+-------------+----------------------+--------------+----------------------+
|netopt_bronze|tms_freight           |classification|confidential          |
|netopt_bronze|tms_freight           |contains      |freight_invoices      |
|netopt_bronze|tms_rate              |classification|restricted            |
|netopt_bronze|tms_rate              |contains      |carrier_contract_rates|
|netopt_gold  |carrier_rate_card     |classification|restricted            |
|netopt_gold  |inventory_monthly     |certified     |true                  |
|netopt_gold  |inventory_monthly     |classification|internal              |
|netopt_gold  |lane_material_sot     |certified     |true                  |
|netopt_gold  |lane_material_sot     |classification|internal              |
|netopt_gold  |lane_monthly          |certified     |true                  |
|netopt_gold  |lane_monthly          |classification|internal              |
|netopt_gold  |material_period_status|certified     |true                  |
|netopt_gold  |material_period_status|classification|internal              |
|netopt_gold  |material_routes       |certified     |true                  |
|netopt_gold  |material_routes       |classification|confidential          |
|netopt_gold  |oor_analysis          |certified     |true                  |
|netopt_gold  |oor_analysis          |classification|confidential          |
|netopt_gold  |plant_stats           |certified     |true                  |
|netopt_gold  |plant_stats           |classification|internal              |
|netopt_gold  |sales_monthly         |certified     |true                  |
|netopt_gold  |sales_monthly         |classification|confidential          |
+-------------+----------------------+--------------+----------------------+

OK    SELECT table_name, column_name, tag_name, tag_value FROM cpg_demos.information_schema.column_tags WHERE schema_name LIKE 'netopt_%'
+-----------------+-------------+--------------+----------------------+
|table_name       |column_name  |tag_name      |tag_value             |
+-----------------+-------------+--------------+----------------------+
|carrier_rate_card|rate_per_mile|classification|restricted            |
|carrier_rate_card|rate_per_mile|contains      |carrier_contract_rates|
+-----------------+-------------+--------------+----------------------+
```

**Output:**
```text
DataFrame[table_name: string, column_name: string, tag_name: string, tag_value: string]
```
