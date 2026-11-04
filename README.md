# Northstar Network Optimization: stopping out-of-route freight leakage

**Industry:** CPG / food manufacturing (frozen bakery & foodservice) · **Function:** Supply chain / transportation
**Customer problem:** Loads move on lanes the MRP plan never intended (DC to the wrong DC, plant to a non-adjacent
fulfillment node). About 60% of these **out-of-route (OOR)** moves cost more than the planned lane. Finance sees the
overspend weeks later as a GL variance, and logistics never learns *which lane / SKU / decision* caused it.
**This build** turns raw ERP + MRP + TMS extracts into a daily, ML-ranked, GenAI-explained planner queue served from
Lakebase, with a Genie Agent for ad-hoc questions and a 3D network map for executives.

> *Northstar Frozen Foods* is a fictional company. **All data is synthetic**, generated from `numpy` seed 42 in
> [`src/notebooks/01_generate_raw_data.py`](src/notebooks/01_generate_raw_data.py). No customer data is used.

**Headline (synthetic, trailing 12 months):** $23.6M gross freight leakage on $77.3M spend · ML model AUC 0.917 out-of-time · 40-lane Lakebase queue covering $10.3M/yr · **$5.2M/yr** recovery at 50% capture. Details in [Business KPIs](#business-kpis).

---

## The data journey (one integrated flow, one job)

```
 01 synthetic ERP/MRP/TMS extracts ──► UC Volume /Volumes/cpg_demos/netopt_raw/landing/*.parquet
                                             │  Lakeflow Auto Loader (streaming tables)
 Lakeflow Spark Declarative Pipeline ───────►│  bronze (16 feeds) → silver (6, expectations) → gold (7 MVs)
                                             ▼
 02 route reconstruction ────────────► netopt_gold.material_routes
 03 Unity Catalog governance ────────► tags (governed policies) · column mask on contract rates · grants · DQ · lineage
 04 ML  (MLflow → UC model oor_cost_risk@champion) ─► oor_risk_scores ─► lane_watchlist
 05 GenAI (ai_query → Claude)  ──────► lane_action_queue  (action_type, recommendation, owner)
 06 Lakebase ─ synced tables ────────► Postgres netopt_serving.lane_action_queue / plant_stats
              app-owned OLTP table ◄── netopt_ops.planner_actions  (approve / reject / snooze)
 07 Genie Agent (space-as-code) ─────► NL questions over gold + ML + GenAI tables, answers checked vs SQL
    Databricks App northstar-network-opt ─► 3D network map + Genie panel + /ops Ops Console (Lakebase)
```

All eight stages run as one Lakeflow Job, `netopt-end-to-end` ([`resources/job.yml`](resources/job.yml)), deployed with
a Declarative Automation Bundle ([`databricks.yml`](databricks.yml)).

## Required stages: where each one lives, and the proof it ran

| Stage | What it does here | Code | Execution evidence (text) |
|---|---|---|---|
| **Lakeflow**: ingest | Auto Loader streams 16 raw parquet feeds from a UC volume into bronze; declarative silver/gold with expectations (ECC→S4 plant mapping, leading-zero SKU fix, CAD→USD, non-product exclusion, self-loops) | [`src/pipeline/transform_pipeline.py`](src/pipeline/transform_pipeline.py), [`resources/pipeline.yml`](resources/pipeline.yml), [`01_generate_raw_data`](src/notebooks/01_generate_raw_data.py) | [`evidence/pipeline/lakeflow_pipeline_events.md`](evidence/pipeline/lakeflow_pipeline_events.md), [`evidence/notebook_runs/generate_raw_data.md`](evidence/notebook_runs/generate_raw_data.md) |
| **Unity Catalog**: govern | Layered schemas, governed tags (`domain`, `layer`, `classification`, `certified`), **column mask** on carrier contract rates, least-privilege grants, DQ expectation results from the event log, lineage from `system.access.table_lineage` | [`03_unity_catalog_governance`](src/notebooks/03_unity_catalog_governance.py) | [`evidence/notebook_runs/unity_catalog_governance.md`](evidence/notebook_runs/unity_catalog_governance.md) |
| **Lakebase**: operational serving | Lakebase Autoscaling project `network-opt`; UC→Postgres **synced tables** for the queue; app-owned `netopt_ops.planner_actions` OLTP write-back; OAuth credential + direct Postgres query | [`06_lakebase_operational_sync`](src/notebooks/06_lakebase_operational_sync.py), [`app/server/lakebase.py`](app/server/lakebase.py) | [`evidence/notebook_runs/lakebase_operational_sync.md`](evidence/notebook_runs/lakebase_operational_sync.md), [`evidence/lakebase/01_setup_log.txt`](evidence/lakebase/01_setup_log.txt), [`evidence/app/README.md`](evidence/app/README.md) |
| **ML / Gen AI**: make it intelligent | **ML:** gradient-boosted classifier + regressor (P(costly), extra $/case), out-of-time validation, MLflow tracking, registered in UC as `netopt_ml.oor_cost_risk@champion`, batch scored. **GenAI:** `ai_query` + Claude with structured output writes the action, owner and $ rationale per lane | [`04_ml_oor_cost_risk_model`](src/notebooks/04_ml_oor_cost_risk_model.py), [`05_genai_reroute_recommendations`](src/notebooks/05_genai_reroute_recommendations.py) | [`evidence/notebook_runs/ml_oor_cost_risk.md`](evidence/notebook_runs/ml_oor_cost_risk.md), [`evidence/notebook_runs/genai_reroute_recommendations.md`](evidence/notebook_runs/genai_reroute_recommendations.md) |
| **Genie Agent**: natural language | *Northstar Network Optimization Genie* defined as code (tables, column configs, instructions, example SQL, benchmarks); validated by asking 8 business questions and checking 2 answers against hand-written SQL | [`genie/build_space.py`](genie/build_space.py), [`genie/space.json`](genie/space.json), [`07_genie_validation`](src/notebooks/07_genie_validation.py) | [`evidence/notebook_runs/genie_validation.md`](evidence/notebook_runs/genie_validation.md) |
| **Databricks App**: surface to the business | FastAPI + React app: 3D network map & OOR drill-downs (SQL warehouse over gold), Genie chat panel, and **Ops Console** (`/ops`): ML-ranked GenAI queue from Lakebase with approve/reject/snooze written back to Lakebase | [`app/`](app) ([`server/main.py`](app/server/main.py), [`static/ops.html`](app/static/ops.html), [`app.yaml`](app/app.yaml)) | [`evidence/app/README.md`](evidence/app/README.md): live API responses incl. a Lakebase write + read-back |

Run-level summary with every task's result and duration: [`evidence/job_run_summary.md`](evidence/job_run_summary.md).
Each executed notebook is committed twice, as `.ipynb` with outputs and as `.md` for reading on GitHub.

## Business KPIs

All values were computed from the gold tables by [`scripts/business_kpis.py`](scripts/business_kpis.py). The SQL and its
results are in [`evidence/business_kpis.md`](evidence/business_kpis.md). Trailing 12 months = 2025-05..2026-04.

| KPI | Value |
|---|---|
| Freight spend (TTM) / cost per case | **$77.3M** / **$1.656** on 46.7M cases, 51.5K loads |
| Freight as % of net sales (TTM) | **1.86%** of $4.14B |
| Share of shipped cases moving out-of-route | **35.0%** of cases (53.3% of freight $), on 1,068 lanes |
| Gross freight leakage (costly OOR vs planned baseline, TTM) | **$23.6M** (30.5% of freight); net of cheaper OOR **$16.7M** |
| Costly share of OOR moves / avg extra cost | **56.6%** / **+$9.03 per case** |
| ML model `oor_cost_risk@champion`, out-of-time test (2026-01..04) | **AUC 0.917**, PR-AUC 0.932, precision 0.825, recall 0.841 |
| Leakage captured by the riskiest 20% of lanes (2026) | **54.1%** of $8.49M |
| Planner action queue (Lakebase) | **40 lanes**, 12 HIGH risk, **$862K/month** expected leakage (**$10.3M/yr**) |
| GenAI action mix | `FIX_MRP_PLAN` 26 lanes ($569K/mo, 66%), `REROUTE_TO_PLAN` 14 lanes ($293K/mo) |
| Genie answer checks vs hand-written SQL | **2/2 PASS** |
| Value at 50% capture of the queue | **$5.2M/yr**, cost per case to $1.545 (−6.7%), freight-to-sales to 1.74% |

The business case is in [`deck/northstar_oor_freight_leakage_deck.pdf`](deck/northstar_oor_freight_leakage_deck.pdf)
(Markdown source: [`deck/northstar_oor_freight_leakage_deck.md`](deck/northstar_oor_freight_leakage_deck.md)).

**Run notes, stated plainly:** in the evidence run, the `lakebase_operational_sync` task's first attempt was killed
by a serverless platform error (`SIGABRT`, logged in [`evidence/job_run_summary.md`](evidence/job_run_summary.md)).
It retried automatically and succeeded, and the job finished **SUCCESS**. The pass counts in the governance notebook's
data-quality table were summed over the two pipeline updates in the event log, so they're 2× the per-run row counts.
The query is now scoped to the latest update. `CREATE CATALOG` was not permitted for the build user, so Lakebase
synced tables are registered in the standard `cpg_demos.netopt_serving` schema rather than a dedicated Lakebase catalog.

## Repository layout

```
databricks.yml, resources/       bundle: Lakeflow pipeline + end-to-end job
src/notebooks/01..07             generate → routes → govern → ML → GenAI → Lakebase → Genie checks
src/pipeline/                    Lakeflow Spark Declarative Pipeline (bronze/silver/gold)
genie/                           Genie Agent as code (build_space.py → space.json, space_id.txt)
app/                             Databricks App (FastAPI backend, prebuilt React map, Ops Console)
scripts/                         one-time setup, evidence exporters, KPI calculator
evidence/                        text-readable proof of execution (notebook outputs, event logs, API responses, KPIs)
deck/                            business presentation (Markdown + PDF)
```

## Reproduce

```bash
PROFILE=<profile> WAREHOUSE_ID=<serverless warehouse id> ./scripts/setup_once.sh   # schemas, Lakebase, bundle, Genie, app, run
python3 scripts/export_run_evidence.py --run-id <job run id> --profile <profile>   # notebook outputs → evidence/
python3 scripts/business_kpis.py --profile <profile>                               # deck KPIs → evidence/business_kpis.md
python3 scripts/capture_app_evidence.py --profile <profile>                        # live app API calls → evidence/app/
```

Built on Databricks (serverless compute, Lakeflow, Unity Catalog, MLflow 3, AI Functions, Lakebase Autoscaling, Genie,
Databricks Apps) with Claude Code as the build assistant.

_Evidence files are unedited tool output, with one exception: the build user's e-mail/name was replaced with
`build-user@[redacted]` / `[build user]` before publishing._
