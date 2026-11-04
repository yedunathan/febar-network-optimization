#!/usr/bin/env python3
"""Create or update the Northstar Network Optimization Genie Agent (space-as-code).

Usage:
  python genie/build_space.py --profile fe-vm-vdm --warehouse d190b568810b2c60 [--space-id <id>]

Writes the resulting space id to genie/space_id.txt and the serialized config to genie/space.json.
"""
import argparse
import json
import os
import subprocess
import sys

CAT = "cpg_demos"
G = f"{CAT}.netopt_gold"
S = f"{CAT}.netopt_silver"
HERE = os.path.dirname(os.path.abspath(__file__))


def hid(prefix: int, n: int) -> str:
    return f"{prefix:02d}{n:030d}"


TABLES = [
    (f"{G}.lane_action_queue", [
        ("action_type", "GenAI recommended action: REROUTE_TO_PLAN, CONSOLIDATE_LOADS, FIX_MRP_PLAN, RENEGOTIATE_RATE, MONITOR", True),
        ("risk_tier", "ML risk tier HIGH / MEDIUM / LOW", True),
        ("recommendation", "GenAI (ai_query) planner recommendation text", False),
    ]),
    (f"{G}.lane_material_sot", [
        ("lane_type", "planned_transport | out_of_lane_transport (OOR, out-of-route) | theoretical_transport", True),
        ("origin_type", "Node type: MFG, INT_DC, EXT_DC, VDC, EXT_VP, OUTLET, ECOM, CORP", True),
        ("dest_type", "Node type: MFG, INT_DC, EXT_DC, VDC, EXT_VP, OUTLET, ECOM, CORP", True),
        ("origin_name", "Origin plant / DC name", True),
        ("dest_name", "Destination plant / DC name", True),
    ]),
    (f"{G}.lane_watchlist", [("risk_tier", "ML risk tier HIGH / MEDIUM / LOW", True)]),
    (f"{G}.material_routes", [("category", "Planned + Happened | Happened Not Planned | Planned Not Happened | Loop", True)]),
    (f"{G}.oor_analysis", [
        ("drill_tab", "costly_oor (cost more than plan) | cheaper_oor | no_baseline | loops", True),
        ("family", "Product family", True),
    ]),
    (f"{G}.oor_risk_scores", [("family", "Product family", True)]),
    (f"{G}.plant_stats", [("plant_name", "Plant / DC name", True), ("plant_type", "Node type", True)]),
    (f"{S}.enterprise_material_master", [("family", "Product family", True)]),
]

INSTRUCTIONS = """This agent analyses freight out-of-route (OOR) cost leakage for Northstar Frozen Foods (fictional frozen bakery manufacturer; all data synthetic).
Key concepts:
- lane_material_sot: one row per directed lane x material x month. lane_type: planned_transport (shipped as planned), out_of_lane_transport (shipped but NOT in the MRP plan = out-of-route / OOR), theoretical_transport (planned, never shipped). Exclude material_number = 'SHUTTLE' (private fleet) unless asked.
- directed_lane_id is ORIGIN-DEST plant codes, e.g. 2501-2542. Plant names/types are in plant_stats (plant_s4) or in origin_name/dest_name.
- oor_analysis: OOR rows vs planned baseline. total_cost_impact = extra USD vs plan (positive = leakage). "Leakage" or "wasted freight" = SUM(total_cost_impact) WHERE drill_tab = 'costly_oor'.
- material_routes: reconstructed end-to-end routes; category in ('Planned + Happened','Happened Not Planned','Planned Not Happened','Loop').
- oor_risk_scores: ML model (oor_cost_risk@champion) scores per OOR row: p_costly = probability the move costs more than plan, expected_leakage_usd = predicted leakage.
- lane_watchlist: trailing-3-month lane-level ML risk; lane_action_queue: top-risk lanes with GenAI recommended action_type, recommendation and action_owner.
- year_month is a string 'YYYY-MM' from 2025-01 to 2026-04; "latest month" = max(year_month) with freight.
Always include directed_lane_id when answering about lanes and round dollars to whole numbers. Keep answers concise."""

EXAMPLES = [
    ("What was total out-of-route freight leakage by month?",
     f"SELECT year_month, ROUND(SUM(total_cost_impact), 0) AS leakage_usd, COUNT(*) AS costly_oor_rows FROM {G}.oor_analysis "
     f"WHERE drill_tab = 'costly_oor' GROUP BY year_month ORDER BY year_month"),
    ("Which lanes have the highest expected monthly leakage according to the ML model?",
     f"SELECT directed_lane_id, origin_name, dest_name, risk_tier, avg_p_costly, expected_monthly_leakage_usd, realized_leakage_usd "
     f"FROM {G}.lane_watchlist ORDER BY expected_monthly_leakage_usd DESC LIMIT 10"),
    ("What share of shipped cases moved out of route in the latest month?",
     f"WITH m AS (SELECT MAX(year_month) AS ym FROM {G}.lane_material_sot WHERE total_cases IS NOT NULL) "
     f"SELECT ROUND(100 * SUM(CASE WHEN lane_type = 'out_of_lane_transport' THEN total_cases END) / SUM(total_cases), 2) AS oor_case_pct "
     f"FROM {G}.lane_material_sot, m WHERE year_month = m.ym AND material_number <> 'SHUTTLE' AND total_cases IS NOT NULL"),
    ("What actions are recommended for the high risk lanes?",
     f"SELECT priority_rank, directed_lane_id, origin_name, dest_name, action_type, recommendation, action_owner, expected_monthly_leakage_usd "
     f"FROM {G}.lane_action_queue WHERE risk_tier = 'HIGH' ORDER BY priority_rank"),
]

SAMPLE_QUESTIONS = [
    "How much did out-of-route freight cost us in excess of plan over the last 3 months?",
    "Which 10 lanes have the highest expected monthly leakage?",
    "Which product families drive the most costly out-of-route moves?",
    "What actions are recommended for the high risk lanes?",
]

BENCHMARKS = [
    ("Total out-of-route leakage in 2026",
     f"SELECT ROUND(SUM(total_cost_impact), 0) FROM {G}.oor_analysis WHERE drill_tab = 'costly_oor' AND year_month >= '2026-01'"),
    ("How many HIGH risk lanes are in the action queue?",
     f"SELECT COUNT(*) FROM {G}.lane_action_queue WHERE risk_tier = 'HIGH'"),
    ("Top 5 product families by costly out-of-route leakage",
     f"SELECT family, ROUND(SUM(total_cost_impact), 0) AS leakage_usd FROM {G}.oor_analysis WHERE drill_tab = 'costly_oor' "
     f"GROUP BY family ORDER BY leakage_usd DESC LIMIT 5"),
]


def build() -> dict:
    tables = []
    for ident, cols in sorted(TABLES):
        cc = [{"column_name": c, "description": [d], **({"enable_format_assistance": True, "enable_entity_matching": True} if em else {})}
              for c, d, em in cols]
        tables.append({"identifier": ident, "column_configs": sorted(cc, key=lambda x: x["column_name"])})
    return {
        "version": 2,
        "config": {"sample_questions": [{"id": hid(10, i), "question": [q]} for i, q in enumerate(SAMPLE_QUESTIONS, 1)]},
        "data_sources": {"tables": tables},
        "instructions": {
            "text_instructions": [{"id": hid(30, 1), "content": [l + "\n" for l in INSTRUCTIONS.splitlines()]}],
            "example_question_sqls": [{"id": hid(20, i), "question": [q], "sql": [s]} for i, (q, s) in enumerate(EXAMPLES, 1)],
        },
        "benchmarks": {"questions": [{"id": hid(40, i), "question": [q], "answer": [{"format": "SQL", "content": [s]}]}
                                     for i, (q, s) in enumerate(BENCHMARKS, 1)]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--space-id")
    a = ap.parse_args()
    space = build()
    with open(os.path.join(HERE, "space.json"), "w") as f:
        json.dump(space, f, indent=1)
    body = {"title": "Northstar Network Optimization Genie",
            "description": "Ask about out-of-route freight leakage, lane risk (ML) and recommended actions (GenAI). Synthetic data.",
            "warehouse_id": a.warehouse, "serialized_space": json.dumps(space)}
    cmd = ["databricks", "genie"] + (["update-space", a.space_id] if a.space_id else ["create-space"])
    out = subprocess.run(cmd + ["--json", json.dumps(body), "--profile", a.profile, "-o", "json"], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(out.stderr)
    sid = json.loads(out.stdout)["space_id"]
    open(os.path.join(HERE, "space_id.txt"), "w").write(sid + "\n")
    print(f"genie space: {sid}")


if __name__ == "__main__":
    main()
