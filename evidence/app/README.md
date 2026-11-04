# App API evidence — `northstar-network-opt`

- URL: https://northstar-network-opt-3381193768081108.aws.databricksapps.com
- Captured: 2026-11-04 02:50 UTC (calls made with the presenter's OAuth token)

## `GET /api/bootstrap` → HTTP 200 in 618 ms

```json
{
 "months": [
  "2025-01",
  "2025-02",
  "2025-03",
  "2025-04",
  "2025-05",
  "2025-06",
  "2025-07",
  "2025-08",
  "2025-09",
  "2025-10",
  "2025-11",
  "2025-12",
  "2026-01",
  "2026-02",
  "2026-03",
  "2026-04"
 ],
 "n_plants": 55,
 "plants_sample": [
  {
   "plant_s4": "2501",
   "plant_ecc": "1501",
   "plant_name": "Rochester Plant",
   "plant_type": "MFG",
   "city": "Rochester",
   "region": "NY",
   "country": "US",
   "lat": "43.1566",
   "lon": "-77.6088",
   "inbound_lanes": "0",
   "outbound_lanes": "44",
   "inbound_cases": "0",
   "outbound_cases": "3968948",
   "top_families": "Frozen Bread Dough, Sweet Dough, Pizza Crust"
  },
  {
   "plant_s4": "2502",
   "plant_ecc": "1502",
   "plant_name": "Dayton Plant",
   "plant_type": "MFG",
   "city": "Dayton",
   "region": "OH",
   "country": "US",
   "lat": "39.7589",
   "lon": "-84.1916",
   "inbound_lanes": "0",
   "outbound_lanes": "43",
   "inbound_cases": "0",
   "outbound_cases": "5467856",
   "top_families": "Sweet Dough, Cakes & Desserts, Frozen Bread Dough"
  },
  {
   "plant_s4": "2503",
   "plant_ecc": "1503",
   "plant_name": "McAllen Plant",
   "plant_type": "MFG",
   "city": "McAllen",
   "region": "TX",
   "country": "US",
   "lat": "26.2034",
   "lon": "-98.23",
   "inbound_lanes": "0",
   "outbound_lanes": "42",
   "inbound_cases": "0",
   "outbound_cases": "2615618",
   "top_families": "Pizza Crust, Cakes & Desserts, Sweet Dough"
  }
 ],
 "materials": "2100 items"
}
```

## `GET /api/exec_summary` → HTTP 200 in 380 ms

```json
{
 "month": "2026-04",
 "window_start": "2025-05",
 "kpis": {
  "planned_lanes": "187",
  "total_freight": "7154747.0",
  "on_plan_pct": "40.2",
  "month_oor_freight": "4275367.0",
  "month_oor_pct": "59.8",
  "n_materials": "2081",
  "oor_impact": "2218070.0",
  "yearly_impact": "2.3591058E7",
  "yearly_freight": "7.7255489E7",
  "yearly_oor_freight": "4.1160447E7",
  "yearly_oor_pct": "53.3",
  "n_plants": 55
 },
 "trend": [
  {
   "year_month": "2025-01",
   "total_freight": "6548555.0",
   "oor_freight": "1827071.0",
   "oor_pct": "27.9"
  },
  {
   "year_month": "2025-02",
   "total_freight": "7251211.0",
   "oor_freight": "2262909.0",
   "oor_pct": "31.2"
  },
  {
   "year_month": "2025-03",
   "total_freight": "7805777.0",
   "oor_freight": "2527382.0",
   "oor_pct": "32.4"
  },
  {
   "year_month": "2025-04",
   "total_freight": "7653974.0",
   "oor_freight": "2815068.0",
   "oor_pct": "36.8"
  },
  {
   "year_month": "2025-05",
   "total_freight": "7713135.0",
   "oor_freight": "2987674.0",
   "oor_pct": "38.7"
  }
 ],
 "planned_lanes": [
  {
   "directed_lane_id": "2501-2547",
   "origin_plant": "2501",
   "dest_plant": "2547",
   "origin_lat": "43.1566",
   "origin_lon": "-77.6088",
   "dest_lat": "40.5187",
   "dest_lon": "-74.4121",
   "total_cases": "15488",
   "freight_usd": "12954.0"
  },
  {
   "directed_lane_id": "2502-2550",
   "origin_plant": "2502",
   "dest_plant": "2550",
   "origin_lat": "39.7589",
   "origin_lon": "-84.1916",
   "dest_lat": "35.2271",
   "dest_lon": "-80.8431",
   "total_cases": "24616",
   "freight_usd": "30394.0"
  },
  {
   "directed_lane_id": "2506-2553",
   "origin_plant": "2506",
   "dest_plant": "2553",
   "origin_lat": "35.0456",
   "origin_lon": "-85.3097",
   "dest_lat": "35.1495",
   "dest_lon": "-90.049",
   "total_cases": "15627",
   "freight_usd": "16478.0"
  },
  {
   "directed_lane_id": "2507-2548",
   "origin_plant": "2507",
   "dest_plant": "2548",
   "origin_lat": "41.525",
   "origin_lon": "-88.0817",
   "dest_lat": "39.0997",
   "dest_lon": "-94.5786",
   "total_cases": "41447",
   "freight_usd": "48394.0"
  },
  {
   "directed_lane_id": "2507-2551",
   "origin_plant": "2507",
   "dest_plant": "2551",
   "origin_lat": "41.525",
   "origin_lon": "-88.0817",
   "dest_lat": "39.9612",
   "dest_lon": "-82.9988",
   "total_cases": "39420",
   "freight_usd": "30017.0"
  }
 ],
 "top_oor": [
  {
   "directed_lane_id": "2508-2552",
   "origin_plant": "2508",
   "dest_plant": "2552",
   "impact": "63256.0",
   "total_cases": "27629",
   "origin_lat": "45.8838",
   "origin_lon": "-72.4843",
   "dest_lat": "44.8041",
   "dest_lon": "-93.1669"
  },
  {
   "directed_lane_id": "2503-2548",
   "origin_plant": "2503",
   "dest_plant": "2548",
   "impact": "22979.0",
   "total_cases": "15372",
   "origin_lat": "26.2034",
   "origin_lon": "-98.23",
   "dest_lat": "39.0997",
   "dest_lon": "-94.5786"
  },
  {
   "directed_lane_id": "2502-2553",
   "origin_plant": "2502",
   "dest_plant": "2553",
   "impact": "24316.0",
   "total_cases": "27538",
   "origin_lat": "39.7589",
   "origin_lon": "-84.1916",
   "dest_lat": "35.1495",
   "dest_lon": "-90.049"
  },
  {
   "directed_lane_id": "2555-2544",
   "origin_plant": "2555",
   "dest_plant": "2544",
   "impact": "22986.0",
   "total_cases": "446",
   "origin_lat": "39.2904",
   "origin_lon": "-76.6122",
   "dest_lat": "47.3809",
   "dest_lon": "-122.2348"
  },
  {
   "directed_lane_id": "2551-2543",
   "origin_plant": "2551",
   "dest_plant": "2543",
   "impact": "31186.0",
   "total_cases": "1316",
   "origin_lat": "39.9612",
   "origin_lon": "-82.9988",
   "dest_lat": "34.0633",
   "dest_lon": "-117.6509"
  }
 ],
 "plants": [
  {
   "plant_s4": "2563",
   "plant_name": "Salt Lake Ext DC",
   "plant_type": "EXT_DC",
   "city": "Salt Lake City",
   "region": "UT",
   "lat": "40.7608",
   "lon": "-111.891",
   "throughput": "365251",
   "top_families": "Pizza Crust, Icing & Glaze"
  },
  {
   "plant_s4": "2592",
   "plant_name": "Boise Partner",
   "plant_type": "EXT_VP",
   "city": "Boise",
   "region": "ID",
   "lat": "43.615",
   "lon": "-116.2023",
   "throughput": "85680",
   "top_families": null
  },
  {
   "plant_s4": "2560",
   "plant_name": "Houston Ext DC",
   "plant_type": "EXT_DC",
   "city": "Houston",
   "region": "TX",
   "lat": "29.7604",
   "lon": "-95.3698",
   "throughput": "311808",
   "top_families": "Toppings, Sweet Dough"
  },
  {
   "plant_s4": "2503",
   "plant_name": "McAllen Plant",
   "plant_type": "MFG",
   "city": "McAllen",
   "region": "TX",
   "lat": "26.2034",
   "lon": "-98.23",
   "throughput": "2615618",
   "top_families": "Pizza Crust, Cakes & Desserts, Sweet Dough"
  },
  {
   "plant_s4": "2572",
   "plant_name": "Oklahoma City Ext DC",
   "plant_type": "EXT_DC",
   "city": "Oklahoma City",
   "region": "OK",
   "lat": "35.4676",
   "lon": "-97.5164",
   "throughput": "856303",
   "top_families": "Rolls & Biscuits, Cakes & Desserts, Icing & Glaze"
  }
 ]
}
```

## `GET /api/drilldown_counts?start=2026-01&end=2026-04` → HTTP 200 in 1189 ms

```json
{
 "counts": {
  "cheaper_oor": 3766,
  "costly_oor": 4231,
  "loops": 7
 }
}
```

## `POST /api/genie/chat` → HTTP 200 in 18773 ms

Request body:
```json
{
 "message": "Which 5 lanes have the highest expected monthly leakage according to the ML model?"
}
```
```json
{
 "conversation_id": "01f1d7fa821a1eca89fd442dbf418b99",
 "text": "You want to see the top 5 lanes with the highest expected monthly leakage in dollars according to the machine learning model. The results include the lane identifier, origin and destination names, risk tier, expected leakage, and realized leakage, all rounded to whole dollars.\nThe **5 lanes with the highest expected monthly leakage** are:\n- **2508-2552** \u2014 Drummondville Plant to Eagan DC: **$46,693/month** expected leakage, **MEDIUM** risk\n- **2508-2542** \u2014 Drummondville Plant to Bolingbrook DC: **$43,001/month** expected leakage, **MEDIUM** risk\n- **2508-2551** \u2014 Drummondville Plant to Columbus DC: **$41,503/month** expected leakage, **MEDIUM** risk\n- **2507-2540** \u2014 Joliet Plant to Atlanta DC: **$36,909/month** expected leakage, **HIGH** risk\n- **2503-2545** \u2014 McAllen Plant to Aurora DC: **$31,931/month** expected leakage, **HIGH** risk\n\nAcross these 5 lanes, expected monthly leakage ranges from **$31,931** to **$46,693**, and **Drummondville Plant** appears on **3 of the 5** highest-risk lanes.",
 "columns": [
  "directed_lane_id",
  "origin_name",
  "dest_name",
  "risk_tier",
  "expected_monthly_leakage_usd",
  "realized_leakage_usd"
 ],
 "rows": [
  [
   "2508-2552",
   "Drummondville Plant",
   "Eagan DC",
   "MEDIUM",
   "46693.0",
   "180662.0"
  ],
  [
   "2508-2542",
   "Drummondville Plant",
   "Bolingbrook DC",
   "MEDIUM",
   "43001.0",
   "55424.0"
  ],
  [
   "2508-2551",
   "Drummondville Plant",
   "Columbus DC",
   "MEDIUM",
   "41503.0",
   "87130.0"
  ],
  [
   "2507-2540",
   "Joliet Plant",
   "Atlanta DC",
   "HIGH",
   "36909.0",
   "54174.0"
  ],
  [
   "2503-2545",
   "McAllen Plant",
   "Aurora DC",
   "HIGH",
   "31931.0",
   "68488.0"
  ]
 ],
 "query": "WITH ranked_lanes AS (\n  SELECT\n    `directed_lane_id`,\n    `origin_name`,\n    `dest_name`,\n    `risk_tier`,\n    ROUND(`expected_monthly_leakage_usd`, 0) AS `expected_monthly_leakage_usd`,\n    ROUND(`realized_leakage_usd`, 0) AS `realized_leakage_usd`,\n    RANK() OVER (ORDER BY `expected_monthly_leakage_usd` DESC) AS `rnk`\n  FROM `cpg_demos`.`netopt_gold`.`lane_watchlist`\n  WHERE `expected_monthly_leakage_usd` IS NOT NULL\n    AND `directed_lane_id` IS NOT NULL\n)\nSELECT\n  `directed_lane_id`,\n  `origin_name`,\n  `dest_name`,\n  `risk_tier`,\n  `expected_monthly_leakage_usd`,\n  `realized_leakage_usd`\nFROM ranked_lanes\nWHERE `rnk` <= 5\nORDER BY `expected_monthly_leakage_usd` DESC, `directed_lane_id` ASC"
}
```

## `GET /api/ops/health` → HTTP 200 in 246 ms

```json
{
 "lakebase": "ok",
 "pg_user": "d6934596-b345-4b96-99ee-2607791d1fb8",
 "pg_version": "PostgreSQL 17.11 (0bfbbeb) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit",
 "queue_rows": 40,
 "decisions": 0
}
```

## `GET /api/ops/summary` → HTTP 200 in 275 ms

```json
{
 "lanes": 40,
 "high_risk_lanes": 12,
 "queue_monthly_leakage_usd": 861903,
 "queue_realized_leakage_usd": 1445125,
 "decided": 0,
 "approved_monthly_savings_usd": 0,
 "window_end": "2026-04",
 "generated_at": "2026-11-04T02:41:46.416706+00:00"
}
```

## `GET /api/ops/queue?tier=HIGH` → HTTP 200 in 319 ms

```json
{
 "n": 12,
 "rows": [
  {
   "directed_lane_id": "2507-2540",
   "origin_plant": "2507",
   "dest_plant": "2540",
   "origin_name": "Joliet Plant",
   "dest_name": "Atlanta DC",
   "origin_type": "MFG",
   "dest_type": "INT_DC",
   "top_family": "Cakes & Desserts",
   "top_material": "000000000300030241",
   "top_material_desc": "CAKES & DESS CUPCAKE 32OZ 24CT",
   "oor_events": 116,
   "skus": 67,
   "oor_cases": 142459.0,
   "avg_p_costly": 0.6709,
   "expected_monthly_leakage_usd": 36909.03,
   "realized_leakage_usd": 54173.93,
   "net_cost_impact_usd": 22285.6,
   "lane_miles": 573.9,
   "planned_miles": 346.2,
   "alt_lane_id": "2507-2551",
   "alt_dest_plant": "2551",
   "alt_dest_name": "Columbus DC",
   "alt_cost_per_case": 0.467,
   "risk_tier": "HIGH",
   "window_start": "2026-02",
   "window_end": "2026-04",
   "action_type": "REROUTE_TO_PLAN",
   "recommendation": "Reroute the 116 out-of-route shipments (142,459 cases) from Joliet Plant to Columbus DC instead of Atlanta DC, using the planned alternative lane 2507-2551 at $0.47/case. This will eliminate the $54,174 realized leakage caused by shipping 573.9 miles instead of the planned 346.2 miles.",
   "action_owner": "Supply planner",
   "llm_error": null,
   "llm_endpoint": "databricks-claude-sonnet-4-5",
   "priority_rank": 4,
   "generated_at": "2026-11-04T02:41:46.416706+00:00",
   "decision": null,
   "decision_note": null,
   "decided_by": null,
   "decided_at": null
  },
  {
   "directed_lane_id": "2503-2545",
   "origin_plant": "2503",
   "dest_plant": "2545",
   "origin_name": "McAllen Plant",
   "dest_name": "Aurora DC",
   "origin_type": "MFG",
   "dest_type": "INT_DC",
   "top_family": "Sweet Dough",
   "top_material": "000000000300011412",
   "top_material_desc": "SWEET DOUGH STICKY BUN 64OZ 48CT",
   "oor_events": 63,
   "skus": 27,
   "oor_cases": 87503.0,
   "avg_p_costly": 0.6804,
   "expected_monthly_leakage_usd": 31930.96,
   "realized_leakage_usd": 68488.44,
   "net_cost_impact_usd": 42143.01,
   "lane_miles": 1009.1,
   "planned_miles": 598.2,
   "alt_lane_id": "2503-2548",
   "alt_dest_plant": "2548",
   "alt_dest_name": "Kansas City DC",
   "alt_cost_per_case": 1.866,
   "risk_tier": "HIGH",
   "window_start": "2026-02",
   "window_end": "2026-04",
   "action_type": "FIX_MRP_PLAN",
   "recommendation": "Correct the MRP plan to route Sweet Dough products to Kansas City DC (lane 2503-2548 at $1.87/case) instead of Aurora DC, as the 63 out-of-route events across 27 SKUs resulted in $68,488 realized leakage over three months due to unplanned miles (1009 vs 598 planned). This will eliminate the high-probability cost overruns (ML probability 0.68) and prevent the expected $31,931 monthly leakage.",
   "action_owner": "Supply planner",
   "llm_error": null,
   "llm_endpoint": "databricks-claude-sonnet-4-5",
   "priority_rank": 5,
   "generated_at": "2026-11-04T02:41:46.416706+00:00",
   "decision": null,
   "decision_note": null,
   "decided_by": null,
   "decided_at": null
  },
  {
   "directed_lane_id": "2501-2540",
   "origin_plant": "2501",
   "dest_plant": "2540",
   "origin_name": "Rochester Plant",
   "dest_name": "Atlanta DC",
   "origin_type": "MFG",
   "dest_type": "INT_DC",
   "top_family": "Pizza Crust",
   "top_material": "000000000300012001",
   "top_material_desc": "PIZZA CRUST GLUTEN FREE 64OZ 48CT",
   "oor_events": 75,
   "skus": 37,
   "oor_cases": 71001.0,
   "avg_p_costly": 0.7012,
   "expected_monthly_leakage_usd": 30288.68,
   "realized_leakage_usd": 32734.44,
   "net_cost_impact_usd": 954.72,
   "lane_miles": 745.7,
   "planned_miles": 364.1,
   "alt_lane_id": "2501-2550",
   "alt_dest_plant": "2550",
   "alt_dest_name": "Charlotte DC",
   "alt_cost_per_case": 1.019,
   "risk_tier": "HIGH",
   "window_start": "2026-02",
   "window_end": "2026-04",
   "action_type": "FIX_MRP_PLAN",
   "recommendation": "Correct the MRP plan to route Pizza Crust and other SKUs to the planned Charlotte DC (lane 2501-2550 at $1.02/case) instead of Atlanta DC, which is causing 745.7 miles vs 364.1 planned miles. This will eliminate the $32,734 realized leakage and prevent the expected $30,289 monthly leakage going forward.",
   "action_owner": "Supply planner",
   "llm_error": null,
   "llm_endpoint": "databricks-claude-sonnet-4-5",
   "priority_rank": 7,
   "generated_at": "2026-11-04T02:41:46.416706+00:00",
   "decision": null,
   "decision_note": null,
   "decided_by": null,
   "decided_at": null
  },
  {
   "directed_lane_id": "2508-2544",
   "origin_plant": "2508",
   "dest_plant": "2544",
   "origin_name": "Drummondville Plant",
   "dest_name": "Kent DC",
   "origin_type": "MFG",
   "dest_type": "INT_DC",
   "top_family": "Toppings",
   "top_material": "000000000300026015",
   "top_material_desc": "TOPPINGS WHIPPED ICING CHOCOLATE 64OZ 24CT",
   "oor_events": 7,
   "skus": 7,
   "oor_cases": 1978.0,
   "avg_p_costly": 0.9988,
   "expected_monthly_leakage_usd": 17824.08,
   "realized_leakage_usd": 50602.75,
   "net_cost_impact_usd": 50602.75,
   "lane_miles": 2322.0,
   "planned_miles": 548.1,
   "alt_lane_id": "2508-2551",
   "alt_dest_plant": "2551",
   "alt_dest_name": "Columbus DC",
   "alt_cost_per_case": 1.128,
   "risk_tier": "HIGH",
   "window_start": "2026-02",
   "window_end": "2026-04",
   "action_type": "FIX_MRP_PLAN",
   "recommendation": "Stop routing shipments from Drummondville Plant to Kent DC, which is generating $50,603 in realized leakage by traveling 2322 miles instead of the planned 548 miles. Reroute these 7 SKUs (primarily Toppings family) to the planned alternative Columbus DC at $1.13/case via lane 2508-2551.",
   "action_owner": "Supply planner",
   "llm_error": null,
   "llm_endpoint": "databricks-claude-sonnet-4-5",
   "priority_rank": 22,
   "generated_at": "2026-11-04T02:41:46.416706+00:00",
   "decision": null,
   "decision_note": null,
   "decided_by": null,
   "decided_at": null
  },
  {
   "directed_lane_id": "2503-2540",
   "origin_plant": "2503",
   "dest_plant": "2
```

## `POST /api/ops/decision` → HTTP 200 in 274 ms

Request body:
```json
{
 "directed_lane_id": "2507-2540",
 "decision": "APPROVED",
 "note": "Evidence capture: approved GenAI recommendation for the top HIGH-risk lane"
}
```
```json
{
 "action_id": 1,
 "directed_lane_id": "2507-2540",
 "decision": "APPROVED",
 "action_type": "REROUTE_TO_PLAN",
 "note": "Evidence capture: approved GenAI recommendation for the top HIGH-risk lane",
 "expected_monthly_savings_usd": 36909.03,
 "decided_by": "build-user@[redacted]",
 "decided_at": "2026-11-04T02:50:54.445276+00:00"
}
```

## `GET /api/ops/decisions?limit=5` → HTTP 200 in 257 ms

```json
{
 "rows": [
  {
   "action_id": 1,
   "directed_lane_id": "2507-2540",
   "decision": "APPROVED",
   "action_type": "REROUTE_TO_PLAN",
   "note": "Evidence capture: approved GenAI recommendation for the top HIGH-risk lane",
   "expected_monthly_savings_usd": 36909.03,
   "decided_by": "build-user@[redacted]",
   "decided_at": "2026-11-04T02:50:54.445276+00:00"
  }
 ]
}
```

## `GET /api/ops/summary` → HTTP 200 in 252 ms

```json
{
 "lanes": 40,
 "high_risk_lanes": 12,
 "queue_monthly_leakage_usd": 861903,
 "queue_realized_leakage_usd": 1445125,
 "decided": 1,
 "approved_monthly_savings_usd": 36909,
 "window_end": "2026-04",
 "generated_at": "2026-11-04T02:41:46.416706+00:00"
}
```
