# Stop paying for freight the plan never asked for
### Northstar Frozen Foods · Out-of-route freight leakage · Business case & solution
*Prepared for: VP Supply Chain (executive sponsor) and Director, Transportation & Network Planning (domain owner)*
*Northstar Frozen Foods is a fictional frozen bakery & foodservice manufacturer; all figures come from a synthetic dataset built for this prototype and computed live on Databricks (see `evidence/business_kpis.md`).*

---

## 1 · The outcome: $5.2M a year back from freight, starting with 40 lanes

| | |
|---|---|
| **$23.6M** | gross freight leakage in the last 12 months: out-of-route (OOR) moves that cost more than the planned lane (**30.5% of $77.3M freight spend**) |
| **$10.3M / yr** | ML-expected leakage on the **40 lanes** now in the planner queue (4% of the 1,068 lanes with OOR, ≈44% of the $1.97M/month leakage run-rate) |
| **$5.2M / yr** | target recovery at 50% capture of the queue → **cost per case $1.656 → $1.545 (−6.7%)**, freight-to-sales **1.86% → 1.74%** |
| **Daily, not month-end** | leakage is flagged the morning after the load moves, with a named owner and an action, instead of a GL variance 4–6 weeks later |

**The ask:** a 90-day pilot on the Drummondville, McAllen and Joliet origins (7 of the top 10 queued lanes), with success measured against the KPIs on slide 9.

---

## 2 · The problem: a third of freight runs off-plan, and nobody sees which third costs money

- **35% of shipped cases** (53% of freight spend) moved on a lane that was **not in that month's MRP plan** for that SKU.
- Not all of it is bad: **56.6%** of OOR lane-SKU-months cost more than plan (avg **+$9.03 per case**), and the rest were opportunistically cheaper (−$6.9M). Treating all OOR the same buries planners in noise.
- The signal is scattered across three systems that don't agree with each other:
  - the **TMS** carries legacy ECC plant codes on ~30% of stops and strips leading zeros from ~40% of SKUs,
  - Canadian freight is invoiced in **CAD**,
  - the **MRP** plan is a monthly snapshot in procurement direction,
  - and **Finance** sees only a GL freight variance at month end.
- **Result today:** leakage is discovered late, attributed to "freight rates", and argued about in spreadsheets. The real root cause is often a stale plan.

---

## 3 · For the executive sponsor (VP Supply Chain / CFO): a P&L lever you can bank

| Capture of queued leakage | Annual savings | Cost per case | Freight % of sales |
|---|---|---|---|
| Today | – | $1.656 | 1.86% |
| 25% (conservative) | **$2.6M** | $1.601 | 1.80% |
| **50% (pilot target)** | **$5.2M** | **$1.545** | **1.74%** |
| 75% (stretch) | $7.8M | $1.490 | 1.68% |

- That's **$2.6–7.8M of EBITDA** from the first 40 lanes alone. The full network leakage pool is **$23.6M gross / $16.7M net** a year.
- **No new freight contracts, no new headcount:** it uses the planners and supply planners you already have, pointed at the right lanes.
- **Governed by design:** carrier contract rates are column-masked, gold tables are certified and tagged, and every recommendation and decision is auditable.

---

## 4 · For the domain owner (Director, Transportation & Network Planning): from 1,068 lanes to a 40-lane queue

- **Prioritised:** an ML model ranks every OOR lane by P(costly) × expected extra $/case × volume. The **top 20% of lanes hold 54%** of out-of-time leakage, so effort goes where the dollars are.
- **Explained:** for each lane, generative AI writes the action, the owner and the $ at stake. It uses only that lane's facts, for example:
  > *"[REROUTE_TO_PLAN] Reroute the 116 out-of-route shipments (142,459 cases) from Joliet Plant to Columbus DC instead of Atlanta DC, using the planned alternative lane 2507-2551 at $0.47/case. This will eliminate the $54,174 realized leakage caused by shipping 573.9 miles instead of the planned 346.2 miles."* (verbatim model output, lane #4)
- **Actionable in one click:** Approve / Reject / Snooze in the Ops Console. Each decision is written to the operational database with who, when and the $ at stake.
- **Insight the data surfaced: 66% of queued $ is a planning problem, not a carrier problem.** 26 of the 40 lanes are `FIX_MRP_PLAN` ($569K/month), owned by supply planning. The cross-border Drummondville plant sits on 3 of the top 5 lanes.

---

## 5 · What the planner sees

1. **Ops Console** (`/ops`): KPI strip with queue leakage $/month, realised leakage, high-risk lanes, lanes actioned and $ addressed. Below it, the ranked lane queue with risk tier, P(costly), expected $/month, the GenAI action and owner, and Approve / Reject / Snooze.
2. **3D network map**: plants, DCs and partners with planned vs out-of-route lanes, drill-downs (costly / cheaper / loops / no baseline), route reconstruction per SKU, and sales & stock overlays.
3. **Ask Genie**: *"Which 10 lanes have the highest expected monthly leakage?"* or *"Which product families drive the most costly out-of-route moves?"* returns an answer, the SQL behind it and the table, in seconds.

*A morning in the life:* the planner opens the queue (served in ~250 ms), approves 5 reroutes and sends 3 plan fixes to supply planning. The KPI strip shows $ addressed, and Finance sees the same number.

---

## 6 · Why you can trust the numbers

- **Model quality:** validated **out-of-time**, trained on 2025 and tested on Jan–Apr 2026. **AUC 0.917, PR-AUC 0.932, precision 0.82, recall 0.84.** Lane distance vs plan and the planned baseline $/case are the top drivers, which are physical, explainable signals. Realised invoice cost is never used as a feature.
- **Data quality:** 8 pipeline expectations (valid plant codes and coordinates, non-negative cost, valid GL period, lane classification) are enforced on every run, with **0 rows dropped**. Code mismatches are fixed at the source and not in spreadsheets.
- **Grounded AI:** the LLM sees only one lane's facts and must return a fixed JSON schema (action type, recommendation, owner). Outputs are stored, versioned and reviewable.
- **Natural-language answers checked against SQL:** Genie's answers to benchmark questions were compared with hand-written SQL. **2/2 PASS** (high-risk lane count; 2026 leakage $8.49M).

---

## 7 · How it works on Databricks: one governed flow, not six tools

| Stage | What it does for the business |
|---|---|
| **Lakeflow** | Ingests raw ERP, MRP and TMS extracts (16 feeds) with Auto Loader. The declarative bronze → silver → gold pipeline fixes plant codes, SKU keys and currency, and classifies each lane × SKU × month as planned / out-of-route / theoretical |
| **Unity Catalog** | One catalog for every layer: governed tags, a column mask on carrier contract rates, least-privilege grants, data-quality results and lineage |
| **ML (MLflow + UC model registry)** | OOR cost-risk model `oor_cost_risk@champion` scores every out-of-route move and rolls up a lane watchlist |
| **Gen AI (AI Functions → Claude)** | `ai_query` writes the action, owner and $ rationale for the top-risk lanes |
| **Lakebase** | Serverless Postgres serves the queue in milliseconds via synced tables and stores planner decisions transactionally |
| **Genie Agent** | Natural-language Q&A over gold, ML and GenAI tables, with curated instructions and benchmarks |
| **Databricks App** | Map + Genie + Ops Console in one secure app. Users sign in with workspace identity, and the app runs as its own service principal |

The whole flow runs as **one scheduled job** (generate/ingest → transform → routes → govern → ML → GenAI → Lakebase sync → Genie checks), last run **SUCCESS** in about 12 minutes on serverless compute.

---

## 8 · Rollout plan: 30 / 60 / 90 days

| | Scope | Exit criteria |
|---|---|---|
| **Days 0–30** | Connect production ERP/MRP/TMS extracts, re-baseline leakage, train on real history, onboard 3 pilot origins | Leakage baseline signed off by Finance; model AUC ≥ 0.85 out-of-time |
| **Days 31–60** | Daily queue live for pilot planners; supply-planning workflow for `FIX_MRP_PLAN`; weekly review with Finance | ≥ 80% of queued lanes actioned within 7 days |
| **Days 61–90** | Measure realised vs expected savings on actioned lanes; extend to all origins; add a carrier-rate renegotiation feed | ≥ 25% reduction in leakage on pilot lanes vs baseline; go/no-go for network rollout |

---

## 9 · KPIs we will hold ourselves to

| KPI | Owner | Baseline (synthetic TTM) | 90-day target |
|---|---|---|---|
| Gross OOR leakage $ / month (pilot lanes) | Dir. Transportation | queue: $862K expected / month | −25% to −50% |
| Freight cost per case | VP Supply Chain | $1.656 | $1.545 at 50% capture |
| Freight % of net sales | CFO | 1.86% | 1.74% |
| OOR share of shipped cases | Dir. Transportation | 35.0% | −5 pts on pilot origins |
| Queue actioned within 7 days | Transportation planners | n/a (no queue today) | ≥ 80% |
| Time to detect a costly OOR move | Finance + Logistics | month-end GL (4–6 weeks) | next day |

---

## Appendix · Data & assumptions

- Synthetic network: 55 nodes (8 plants, 16 DCs, 31 fulfillment/partner/outlet nodes), ~2,100 SKUs, 16 months (2025-01 to 2026-04), 70.6K loads, 64.1M cases. Generated with `numpy` seed 42. No customer data.
- "Leakage" = (actual $/case − planned baseline $/case) × cases, for OOR moves above baseline. The baseline cascades lane×SKU → SKU → lane → destination averages.
- "Expected leakage" = ML-predicted extra $/case (floored at 0) × cases, averaged per month over the trailing 3 months (2026-02 to 2026-04).
- Savings scenarios apply a capture rate to the 40-lane queue only. Network-wide upside is larger and not counted.
- All figures and the SQL that produced them: `evidence/business_kpis.md`. Model metrics: `evidence/notebook_runs/ml_oor_cost_risk.md`.
