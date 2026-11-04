## The problem: $23.6M of freight the plan never asked for

| | |
|---|---|
| **35%** | of shipped cases moved on a lane that wasn't in that month's supply plan |
| **$23.6M** | extra freight in the last 12 months from off-plan moves that cost more than plan (**30.5% of $77.3M** spend) |
| **4–6 weeks** | before Finance sees it, as a single freight variance with no lane, product or root cause |

- **Why it stays hidden:** the supply plan, the freight system and the finance ledger don't agree. They use different plant codes and product numbers, and Canadian freight is billed in CAD.
- **Why it's hard to act on:** 43% of off-plan moves are actually *cheaper*, so planners can't tell which of 1,068 lanes to chase.
- **Who feels it:** the VP Supply Chain (cost per case, freight-to-sales) and the Director of Transportation (OOR rate, planner time).

---

## The solution: next-day visibility into every costly off-plan move

- **One trusted view of every lane:** each lane × product × month is labelled *planned*, *out-of-route* or *never shipped*, and priced against the planned cost.
- **Ranked by dollars, not volume:** an ML model predicts which off-plan moves will cost more and by how much. The **top 20% of lanes hold 54%** of the leakage, so 1,068 lanes come down to a **40-lane queue worth $10.3M a year**.
- **Explained in plain English:** for each lane, Gen AI writes the action ("reroute to the planned DC" or "fix the supply plan"), the owner and the dollars at stake.
- **Acted on in one place:** planners approve, reject or snooze each action in the Ops Console, and every decision is logged. Leaders ask Genie *"Which lanes leak the most this month?"* and get the answer with the SQL behind it.
- **What we found:** **66%** of the queued dollars trace to a stale supply plan, not to carriers. The fix is a planning conversation, not a rate negotiation.

---

## The architecture: one governed platform, raw data to decision

| Stage | Databricks capability | What it does |
|---|---|---|
| **Ingest** | Lakeflow (Auto Loader + declarative pipeline) | 16 raw feeds from the ERP, supply plan and freight system. Fixes plant codes, product numbers and currency, and enforces 8 data-quality checks (0 rows dropped) |
| **Govern** | Unity Catalog | One catalog for every layer: certified tables, tags, a mask on carrier contract rates, least-privilege access and lineage |
| **Predict** | MLflow + Unity Catalog model registry | Out-of-route cost-risk model `@champion`, **AUC 0.917** on months it never saw |
| **Explain** | AI Functions (`ai_query` → Claude) | Grounded action, owner and $ rationale per lane, returned as structured output |
| **Serve** | Lakebase (serverless Postgres) | Queue served to the app in milliseconds; planner decisions written back |
| **Ask** | Genie Agent | Plain-English questions over the same governed tables, checked against SQL |
| **Act** | Databricks App | Ops Console + 3D network map + Genie panel, with workspace sign-in |

**One job runs it end to end:** about 12 minutes on serverless compute, with no data copied into other tools.

---

## Call to action: a 90-day pilot to bank $5.2M a year

| Capture of the 40-lane queue | Annual savings | Cost per case |
|---|---|---|
| 25% (conservative) | $2.6M | $1.656 → $1.601 |
| **50% (pilot target)** | **$5.2M** | **$1.656 → $1.545 (−6.7%)** |
| 75% (stretch) | $7.8M | $1.656 → $1.490 |

- **Scope:** 3 origins (Drummondville, McAllen, Joliet), which cover 7 of the top 10 queued lanes, plus their planners and supply planners.
- **Success criteria:** ≥ 80% of queued lanes actioned within 7 days; ≥ 25% less leakage on pilot lanes vs. baseline; Finance signs off on the baseline.
- **What we need from you:** (1) an executive sponsor, (2) read access to production ERP, supply-plan and freight extracts, (3) one transportation planner and one supply planner for 2 hours a week.
- **Next steps:** baseline workshop with Finance and Logistics **next week** → production data connected and the model retrained by **day 30** → go/no-go review for network rollout at **day 90**.
