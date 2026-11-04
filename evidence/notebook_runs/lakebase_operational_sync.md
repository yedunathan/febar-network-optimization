# Executed notebook: `lakebase_operational_sync`

_Task run `890569713959104` of job run `285440164007553` · result **SUCCESS** · 63s_


# 06 · Lakebase — operational serving
Analytics live in Delta; the planner app needs **millisecond OLTP reads and transactional writes**
(approve / reject / snooze a lane). Lakebase (serverless Postgres, project `network-opt`) provides both:

| Postgres object | Kind | Fed by |
|---|---|---|
| `netopt_serving.lane_action_queue` | **synced table** (UC → Postgres, SNAPSHOT refreshed every job run) | `netopt_gold.lane_action_queue` (ML + GenAI) |
| `netopt_serving.plant_stats` | synced table (SNAPSHOT) | `netopt_gold.plant_stats` |
| `netopt_ops.planner_actions` | native OLTP table, owned by the app service principal | app writes |

This task (a) creates the synced tables if missing, (b) triggers a refresh so Postgres reflects this run's
ML/GenAI output, and (c) connects with an OAuth database credential and **queries Postgres directly** to prove it.

```python
%pip install -q "psycopg[binary]>=3.2"
```

**Output:**
```text
Note: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.
```

```python
dbutils.widgets.text("catalog", "cpg_demos")
dbutils.widgets.text("lakebase_project", "network-opt")
dbutils.widgets.text("app_name", "northstar-network-opt")
CAT = dbutils.widgets.get("catalog")
PROJECT = dbutils.widgets.get("lakebase_project")
APP = dbutils.widgets.get("app_name")
BRANCH = f"projects/{PROJECT}/branches/production"
ENDPOINT = f"{BRANCH}/endpoints/primary"
SERVING = f"{CAT}.netopt_serving"

import time
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
api = w.api_client

SYNCED = {
    "lane_action_queue": {"source": f"{CAT}.netopt_gold.lane_action_queue", "pk": ["directed_lane_id"], "policy": "SNAPSHOT"},
    "plant_stats": {"source": f"{CAT}.netopt_gold.plant_stats", "pk": ["plant_s4"], "policy": "SNAPSHOT"},
}


def get_synced(name: str):
    try:
        return api.do("GET", f"/api/2.0/postgres/synced_tables/{SERVING}.{name}")
    except Exception as e:
        if "does not exist" in str(e).lower() or "not found" in str(e).lower():
            return None
        raise
```

## 1. Ensure synced tables exist, then refresh them

```python
pipelines = {}
for name, cfg in SYNCED.items():
    st = get_synced(name)
    if st is None:
        print(f"creating synced table {SERVING}.{name} <- {cfg['source']} ({cfg['policy']})")
        api.do("POST", "/api/2.0/postgres/synced_tables", query={"synced_table_id": f"{SERVING}.{name}"}, body={
            "spec": {"source_table_full_name": cfg["source"], "primary_key_columns": cfg["pk"],
                     "scheduling_policy": cfg["policy"], "branch": BRANCH, "postgres_database": "databricks_postgres",
                     "create_database_objects_if_missing": True,
                     "new_pipeline_spec": {"storage_catalog": CAT, "storage_schema": "netopt_serving"}}})
        for _ in range(60):
            st = get_synced(name)
            if st and st.get("status", {}).get("pipeline_id"):
                break
            time.sleep(10)
    pipelines[name] = st["status"]["pipeline_id"]
    print(f"{SERVING}.{name}: state={st['status'].get('detailed_state')} pipeline={pipelines[name]}")
```

**Output:**
```text
cpg_demos.netopt_serving.lane_action_queue: state=SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE pipeline=6d347f8c-fca1-484b-a384-fb18093e4b38
cpg_demos.netopt_serving.plant_stats: state=SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE pipeline=5a2e8c6e-0fb9-48ea-853e-468c0eaf6961
```

```python
def wait_idle(pid: str, timeout_s: int = 1200):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        p = w.pipelines.get(pid)
        active = [u for u in (p.latest_updates or []) if u.state and u.state.value not in ("COMPLETED", "FAILED", "CANCELED")]
        if not active:
            return p.latest_updates[0] if p.latest_updates else None
        time.sleep(15)
    raise TimeoutError(pid)


for name, pid in pipelines.items():
    wait_idle(pid)  # first sync after creation may still be running
    # source tables are rebuilt with CREATE OR REPLACE each run -> full refresh keeps Postgres exactly in step
    upd = w.pipelines.start_update(pid, full_refresh=True)
    print(f"refresh {name}: update {upd.update_id}")

for name, pid in pipelines.items():
    last = wait_idle(pid)
    print(f"{name}: last update {last.update_id} -> {last.state.value}")
    assert last.state.value == "COMPLETED", f"sync failed for {name}"
    print(f"   {get_synced(name)['status'].get('detailed_state')}")
```

**Output:**
```text
refresh lane_action_queue: update e40ae43b-6dc8-411f-b8d0-fcd5d9945683
refresh plant_stats: update c393a3b8-fefc-42cf-8fa1-faea3f223097
lane_action_queue: last update e40ae43b-6dc8-411f-b8d0-fcd5d9945683 -> COMPLETED
   SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE
plant_stats: last update c393a3b8-fefc-42cf-8fa1-faea3f223097 -> COMPLETED
   SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE
```

## 2. Query Lakebase Postgres directly (OAuth database credential)

```python
import psycopg

ep = api.do("GET", f"/api/2.0/postgres/{ENDPOINT}")
host = ep["status"]["hosts"]["host"]
token = api.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": ENDPOINT})["token"]
user = w.current_user.me().user_name
print(f"connecting to {host} as {user}")

with psycopg.connect(host=host, dbname="databricks_postgres", user=user, password=token, sslmode="require") as conn:
    cur = conn.cursor()
    cur.execute("SELECT version()")
    print(cur.fetchone()[0])

    # least privilege for the app: read-only on the synced serving schema (it owns netopt_ops itself)
    app_sp = w.apps.get(APP).service_principal_client_id
    cur.execute(f'GRANT USAGE ON SCHEMA netopt_serving TO "{app_sp}"')
    cur.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA netopt_serving TO "{app_sp}"')
    cur.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA netopt_serving GRANT SELECT ON TABLES TO "{app_sp}"')
    conn.commit()
    print(f"granted app service principal {app_sp} USAGE + SELECT on netopt_serving")
    cur.execute("""SELECT table_schema, table_name FROM information_schema.tables
                   WHERE table_schema IN ('netopt_serving', 'netopt_ops') ORDER BY 1, 2""")
    for r in cur.fetchall():
        print("  table:", ".".join(r))
    cur.execute("SELECT count(*), sum(expected_monthly_leakage_usd), max(generated_at) FROM netopt_serving.lane_action_queue")
    n, leak, gen = cur.fetchone()
    print(f"\nlane_action_queue rows={n}  expected monthly leakage=${leak:,.0f}  generated_at={gen}")

    t0 = time.perf_counter()
    cur.execute("""SELECT priority_rank, directed_lane_id, origin_name, dest_name, risk_tier,
                          round(avg_p_costly::numeric, 2), round(expected_monthly_leakage_usd::numeric, 0), action_type
                   FROM netopt_serving.lane_action_queue ORDER BY priority_rank LIMIT 10""")
    rows = cur.fetchall()
    print(f"top-10 queue read in {1000 * (time.perf_counter() - t0):.1f} ms:")
    for r in rows:
        print("  ", r)

    cur.execute("""SELECT to_regclass('netopt_ops.planner_actions') IS NOT NULL""")
    if cur.fetchone()[0]:
        cur.execute("SELECT decision, count(*), round(sum(expected_monthly_savings_usd)::numeric, 0) "
                    "FROM netopt_ops.planner_actions GROUP BY 1 ORDER BY 1")
        print("\nplanner decisions written by the app:", cur.fetchall())
    else:
        print("\nnetopt_ops.planner_actions not created yet (the app's service principal creates it on first start)")
```

**Output:**
```text
connecting to ep-hidden-voice-d2nas437.database.us-east-1.cloud.databricks.com as build-user@[redacted]
PostgreSQL 17.11 (0bfbbeb) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit
granted app service principal d6934596-b345-4b96-99ee-2607791d1fb8 USAGE + SELECT on netopt_serving
  table: netopt_ops.planner_actions
  table: netopt_serving.lane_action_queue
  table: netopt_serving.plant_stats

lane_action_queue rows=40  expected monthly leakage=$861,903  generated_at=2026-11-04 02:41:46.416706+00:00
top-10 queue read in 3.1 ms:
   (1, '2508-2552', 'Drummondville Plant', 'Eagan DC', 'MEDIUM', Decimal('0.64'), Decimal('46693'), 'FIX_MRP_PLAN')
   (2, '2508-2542', 'Drummondville Plant', 'Bolingbrook DC', 'MEDIUM', Decimal('0.62'), Decimal('43001'), 'FIX_MRP_PLAN')
   (3, '2508-2551', 'Drummondville Plant', 'Columbus DC', 'MEDIUM', Decimal('0.60'), Decimal('41503'), 'FIX_MRP_PLAN')
   (4, '2507-2540', 'Joliet Plant', 'Atlanta DC', 'HIGH', Decimal('0.67'), Decimal('36909'), 'REROUTE_TO_PLAN')
   (5, '2503-2545', 'McAllen Plant', 'Aurora DC', 'HIGH', Decimal('0.68'), Decimal('31931'), 'FIX_MRP_PLAN')
   (6, '2502-2553', 'Dayton Plant', 'Memphis DC', 'MEDIUM', Decimal('0.62'), Decimal('31846'), 'REROUTE_TO_PLAN')
   (7, '2501-2540', 'Rochester Plant', 'Atlanta DC', 'HIGH', Decimal('0.70'), Decimal('30289'), 'FIX_MRP_PLAN')
   (8, '2508-2550', 'Drummondville Plant', 'Charlotte DC', 'MEDIUM', Decimal('0.60'), Decimal('29681'), 'REROUTE_TO_PLAN')
   (9, '2507-2551', 'Joliet Plant', 'Columbus DC', 'LOW', Decimal('0.48'), Decimal('26826'), 'FIX_MRP_PLAN')
   (10, '2502-2542', 'Dayton Plant', 'Bolingbrook DC', 'LOW', Decimal('0.42'), Decimal('25557'), 'FIX_MRP_PLAN')

planner decisions written by the app: []
```
