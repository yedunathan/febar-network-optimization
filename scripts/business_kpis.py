#!/usr/bin/env python3
"""Compute the business KPIs quoted in the deck straight from the gold tables and write them, with the SQL,
to evidence/business_kpis.md. Usage: python scripts/business_kpis.py --profile <profile>"""
import argparse
import json
import os
import subprocess
from datetime import datetime, timezone

G = "cpg_demos.netopt_gold"
S = "cpg_demos.netopt_silver"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence", "business_kpis.md")

QUERIES = [
    ("Freight spend, volume and cost per case (all 16 months and trailing 12 months)", f"""
SELECT CASE WHEN year_month >= '2025-05' THEN 'trailing_12m (2025-05..2026-04)' ELSE 'prior (2025-01..2025-04)' END AS period,
       ROUND(SUM(freight_cost_usd), 0) AS freight_spend_usd, SUM(cases) AS cases,
       ROUND(SUM(freight_cost_usd) / SUM(cases), 3) AS cost_per_case_usd, COUNT(DISTINCT load_id) AS loads
FROM {S}.freight_shipments WHERE is_product_material AND NOT is_self_loop GROUP BY 1 ORDER BY 1"""),
    ("Out-of-route (OOR) share of shipped volume and spend, trailing 12 months", f"""
SELECT ROUND(100 * SUM(CASE WHEN lane_type = 'out_of_lane_transport' THEN total_cases END) / SUM(total_cases), 2) AS oor_case_pct,
       ROUND(SUM(CASE WHEN lane_type = 'out_of_lane_transport' THEN total_freight_usd END), 0) AS oor_freight_usd,
       ROUND(100 * SUM(CASE WHEN lane_type = 'out_of_lane_transport' THEN total_freight_usd END) / SUM(total_freight_usd), 2) AS oor_spend_pct,
       COUNT(DISTINCT CASE WHEN lane_type = 'out_of_lane_transport' THEN directed_lane_id END) AS lanes_with_oor
FROM {G}.lane_material_sot
WHERE material_number <> 'SHUTTLE' AND total_cases IS NOT NULL AND year_month >= '2025-05'"""),
    ("Freight leakage = extra cost of costly OOR moves vs planned baseline, trailing 12 months", f"""
SELECT ROUND(SUM(CASE WHEN drill_tab = 'costly_oor' THEN total_cost_impact END), 0) AS leakage_usd_12m,
       ROUND(SUM(CASE WHEN drill_tab = 'cheaper_oor' THEN total_cost_impact END), 0) AS cheaper_oor_savings_usd_12m,
       ROUND(SUM(CASE WHEN drill_tab IN ('costly_oor', 'cheaper_oor') THEN total_cost_impact END), 0) AS net_oor_impact_usd_12m,
       ROUND(AVG(CASE WHEN drill_tab = 'costly_oor' THEN extra_cost_per_case END), 3) AS avg_extra_cost_per_case_usd,
       COUNT(CASE WHEN drill_tab = 'costly_oor' THEN 1 END) AS costly_oor_lane_material_months,
       ROUND(100 * COUNT(CASE WHEN drill_tab = 'costly_oor' THEN 1 END) /
             COUNT(CASE WHEN drill_tab IN ('costly_oor', 'cheaper_oor') THEN 1 END), 1) AS costly_share_of_oor_pct
FROM {G}.oor_analysis WHERE year_month >= '2025-05'"""),
    ("Freight as % of net sales (GL), trailing 12 months", f"""
WITH f AS (SELECT SUM(freight_cost_usd) fr FROM {S}.freight_shipments WHERE is_product_material AND year_month >= '2025-05'),
     s AS (SELECT SUM(sales_usd) sa FROM {G}.sales_monthly WHERE year_month >= '2025-05')
SELECT ROUND(s.sa, 0) AS net_sales_usd, ROUND(f.fr, 0) AS freight_usd, ROUND(100 * f.fr / s.sa, 2) AS freight_pct_of_sales FROM f, s"""),
    ("ML targeting: share of out-of-time (2026) leakage captured by the riskiest lanes", f"""
WITH lane AS (
  SELECT directed_lane_id, SUM(expected_leakage_usd) exp_leak, SUM(GREATEST(total_cost_impact, 0)) real_leak
  FROM {G}.oor_risk_scores WHERE year_month >= '2026-01' GROUP BY 1),
r AS (SELECT *, PERCENT_RANK() OVER (ORDER BY exp_leak DESC) pr FROM lane)
SELECT COUNT(*) AS lanes_with_oor_2026,
       ROUND(100 * SUM(CASE WHEN pr < 0.10 THEN real_leak END) / SUM(real_leak), 1) AS top10pct_lanes_share_of_leakage_pct,
       ROUND(100 * SUM(CASE WHEN pr < 0.20 THEN real_leak END) / SUM(real_leak), 1) AS top20pct_lanes_share_of_leakage_pct,
       ROUND(SUM(real_leak), 0) AS realised_leakage_2026_usd
FROM r"""),
    ("Planner action queue (ML-ranked, GenAI-recommended) served from Lakebase", f"""
SELECT COUNT(*) AS lanes_in_queue, COUNT(CASE WHEN risk_tier = 'HIGH' THEN 1 END) AS high_risk_lanes,
       ROUND(SUM(expected_monthly_leakage_usd), 0) AS queue_expected_monthly_leakage_usd,
       ROUND(12 * SUM(expected_monthly_leakage_usd), 0) AS queue_annualised_leakage_usd,
       ROUND(SUM(realized_leakage_usd), 0) AS queue_realised_leakage_3m_usd,
       MIN(window_start) AS window_start, MAX(window_end) AS window_end
FROM {G}.lane_action_queue"""),
    ("Queue by recommended action type", f"""
SELECT action_type, action_owner, COUNT(*) AS lanes, ROUND(SUM(expected_monthly_leakage_usd), 0) AS exp_monthly_leakage_usd
FROM {G}.lane_action_queue GROUP BY 1, 2 ORDER BY 4 DESC"""),
    ("Leakage by product family, trailing 12 months", f"""
SELECT family, ROUND(SUM(total_cost_impact), 0) AS leakage_usd, COUNT(*) AS costly_oor_rows
FROM {G}.oor_analysis WHERE drill_tab = 'costly_oor' AND year_month >= '2025-05' GROUP BY 1 ORDER BY 2 DESC"""),
]


def run(sql: str, profile: str):
    out = subprocess.run(["databricks", "experimental", "aitools", "tools", "query", sql, "--profile", profile, "-o", "json"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def table(rows) -> str:
    if not rows:
        return "_no rows_"
    cols = list(rows[0].keys())
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] +
                     ["| " + " | ".join("" if r.get(c) is None else str(r[c]) for c in cols) + " |" for r in rows])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    a = ap.parse_args()
    md = ["# Business KPIs (computed from the gold tables)", "",
          f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by `scripts/business_kpis.py` against the "
          f"Databricks SQL warehouse. All data synthetic._", ""]
    for title, sql in QUERIES:
        rows = run(sql, a.profile)
        md += [f"## {title}", "", "```sql", sql.strip(), "```", "", table(rows), ""]
        print(title, "->", rows)
    with open(OUT, "w") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    main()
