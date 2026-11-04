# Databricks notebook source
# MAGIC %md
# MAGIC # 06 · Lakebase — operational serving
# MAGIC Analytics live in Delta; the planner app needs **millisecond OLTP reads and transactional writes**
# MAGIC (approve / reject / snooze a lane). Lakebase (serverless Postgres, project `network-opt`) provides both:
# MAGIC
# MAGIC | Postgres object | Kind | Fed by |
# MAGIC |---|---|---|
# MAGIC | `netopt_serving.lane_action_queue` | **synced table** (UC → Postgres, SNAPSHOT refreshed every job run) | `netopt_gold.lane_action_queue` (ML + GenAI) |
# MAGIC | `netopt_serving.plant_stats` | synced table (SNAPSHOT) | `netopt_gold.plant_stats` |
# MAGIC | `netopt_ops.planner_actions` | native OLTP table, owned by the app service principal | app writes |
# MAGIC
# MAGIC This task (a) creates the synced tables if missing, (b) triggers a refresh so Postgres reflects this run's
# MAGIC ML/GenAI output, and (c) connects with an OAuth database credential and **queries Postgres directly** to prove it.

# COMMAND ----------

# MAGIC %pip install -q "psycopg[binary]>=3.2"

# COMMAND ----------

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

# COMMAND ----------
# MAGIC %md ## 1. Ensure synced tables exist, then refresh them

# COMMAND ----------

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

# COMMAND ----------

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

# COMMAND ----------
# MAGIC %md ## 2. Query Lakebase Postgres directly (OAuth database credential)

# COMMAND ----------

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
