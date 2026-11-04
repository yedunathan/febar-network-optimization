#!/usr/bin/env bash
# One-time workspace setup for Northstar Network Optimization (everything the bundle can't declare).
# Usage: PROFILE=<profile> WAREHOUSE_ID=<id> ./scripts/setup_once.sh
set -euo pipefail
P="--profile ${PROFILE:?set PROFILE}"
WH="${WAREHOUSE_ID:?set WAREHOUSE_ID}"
CAT=cpg_demos
APP=northstar-network-opt
PROJECT=network-opt
cd "$(dirname "$0")/.."

# 1. Unity Catalog: one schema per layer + the raw landing volume
for s in netopt_raw netopt_bronze netopt_silver netopt_gold netopt_ml netopt_serving; do
  databricks schemas create "$s" "$CAT" $P >/dev/null 2>&1 || echo "schema $CAT.$s exists"
done
databricks volumes create "$CAT" netopt_raw landing MANAGED $P >/dev/null 2>&1 || echo "volume exists"

# 2. Lakebase Autoscaling project (production branch + primary endpoint are auto-created)
databricks postgres create-project "$PROJECT" \
  --json '{"spec": {"display_name": "Northstar Network Optimization - operational store"}}' $P >/dev/null 2>&1 \
  || echo "lakebase project exists"

# 3. Pipeline + job (Lakeflow, ML, GenAI, Lakebase sync, Genie checks)
databricks bundle deploy $P

# 4. Genie Agent (space-as-code) -> genie/space_id.txt; put the id in databricks.yml var genie_space_id
python3 genie/build_space.py --profile "$PROFILE" --warehouse "$WH" $( [ -s genie/space_id.txt ] && echo --space-id "$(cat genie/space_id.txt)" )

# 5. Databricks App with warehouse + Genie + Lakebase resources
SPACE=$(cat genie/space_id.txt)
databricks apps create --json "{\"name\":\"$APP\",
  \"resources\":[{\"name\":\"sql-warehouse\",\"sql_warehouse\":{\"id\":\"$WH\",\"permission\":\"CAN_USE\"}},
                 {\"name\":\"genie-space\",\"genie_space\":{\"space_id\":\"$SPACE\",\"permission\":\"CAN_RUN\"}},
                 {\"name\":\"postgres\",\"postgres\":{\"branch\":\"projects/$PROJECT/branches/production\",
                   \"database\":\"projects/$PROJECT/branches/production/databases/databricks-postgres\",
                   \"permission\":\"CAN_CONNECT_AND_CREATE\"}}]}" $P >/dev/null 2>&1 || echo "app exists"
SP=$(databricks apps get "$APP" $P -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['service_principal_client_id'])")
for g in "GRANT USE CATALOG ON CATALOG $CAT TO \`$SP\`" \
         "GRANT USE SCHEMA, SELECT ON SCHEMA $CAT.netopt_gold TO \`$SP\`" \
         "GRANT USE SCHEMA, SELECT ON SCHEMA $CAT.netopt_silver TO \`$SP\`"; do
  databricks experimental aitools tools query "$g" $P >/dev/null
done

# 6. Deploy the app FIRST (its service principal creates + owns the netopt_ops Postgres schema on startup)
WS="/Workspace/Users/$(databricks current-user me $P -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['userName'])")/$APP"
(cd app && databricks sync . "$WS" $P && databricks apps deploy "$APP" --source-code-path "$WS" $P)

# 7. Run the end-to-end job: creates/refreshes the Lakebase synced tables and grants the app SP read access
databricks bundle run netopt_end_to_end $P
echo "done: $(databricks apps get "$APP" $P -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['url'])")"
