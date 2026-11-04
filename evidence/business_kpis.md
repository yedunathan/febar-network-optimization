# Business KPIs (computed from the gold tables)

_Generated 2026-11-04 02:49 UTC by `scripts/business_kpis.py` against the Databricks SQL warehouse. All data synthetic._

## Freight spend, volume and cost per case (all 16 months and trailing 12 months)

```sql
SELECT CASE WHEN year_month >= '2025-05' THEN 'trailing_12m (2025-05..2026-04)' ELSE 'prior (2025-01..2025-04)' END AS period,
       ROUND(SUM(freight_cost_usd), 0) AS freight_spend_usd, SUM(cases) AS cases,
       ROUND(SUM(freight_cost_usd) / SUM(cases), 3) AS cost_per_case_usd, COUNT(DISTINCT load_id) AS loads
FROM cpg_demos.netopt_silver.freight_shipments WHERE is_product_material AND NOT is_self_loop GROUP BY 1 ORDER BY 1
```

| cases | cost_per_case_usd | freight_spend_usd | loads | period |
|---|---|---|---|---|
| 17415956 | 1.68 | 2.9259517E7 | 19112 | prior (2025-01..2025-04) |
| 46664089 | 1.656 | 7.7255489E7 | 51473 | trailing_12m (2025-05..2026-04) |

## Out-of-route (OOR) share of shipped volume and spend, trailing 12 months

```sql
SELECT ROUND(100 * SUM(CASE WHEN lane_type = 'out_of_lane_transport' THEN total_cases END) / SUM(total_cases), 2) AS oor_case_pct,
       ROUND(SUM(CASE WHEN lane_type = 'out_of_lane_transport' THEN total_freight_usd END), 0) AS oor_freight_usd,
       ROUND(100 * SUM(CASE WHEN lane_type = 'out_of_lane_transport' THEN total_freight_usd END) / SUM(total_freight_usd), 2) AS oor_spend_pct,
       COUNT(DISTINCT CASE WHEN lane_type = 'out_of_lane_transport' THEN directed_lane_id END) AS lanes_with_oor
FROM cpg_demos.netopt_gold.lane_material_sot
WHERE material_number <> 'SHUTTLE' AND total_cases IS NOT NULL AND year_month >= '2025-05'
```

| lanes_with_oor | oor_case_pct | oor_freight_usd | oor_spend_pct |
|---|---|---|---|
| 1068 | 34.99 | 4.1160447E7 | 53.28 |

## Freight leakage = extra cost of costly OOR moves vs planned baseline, trailing 12 months

```sql
SELECT ROUND(SUM(CASE WHEN drill_tab = 'costly_oor' THEN total_cost_impact END), 0) AS leakage_usd_12m,
       ROUND(SUM(CASE WHEN drill_tab = 'cheaper_oor' THEN total_cost_impact END), 0) AS cheaper_oor_savings_usd_12m,
       ROUND(SUM(CASE WHEN drill_tab IN ('costly_oor', 'cheaper_oor') THEN total_cost_impact END), 0) AS net_oor_impact_usd_12m,
       ROUND(AVG(CASE WHEN drill_tab = 'costly_oor' THEN extra_cost_per_case END), 3) AS avg_extra_cost_per_case_usd,
       COUNT(CASE WHEN drill_tab = 'costly_oor' THEN 1 END) AS costly_oor_lane_material_months,
       ROUND(100 * COUNT(CASE WHEN drill_tab = 'costly_oor' THEN 1 END) /
             COUNT(CASE WHEN drill_tab IN ('costly_oor', 'cheaper_oor') THEN 1 END), 1) AS costly_share_of_oor_pct
FROM cpg_demos.netopt_gold.oor_analysis WHERE year_month >= '2025-05'
```

| avg_extra_cost_per_case_usd | cheaper_oor_savings_usd_12m | costly_oor_lane_material_months | costly_share_of_oor_pct | leakage_usd_12m | net_oor_impact_usd_12m |
|---|---|---|---|---|---|
| 9.027 | -6911286.0 | 11256 | 56.6 | 2.3591058E7 | 1.6679772E7 |

## Freight as % of net sales (GL), trailing 12 months

```sql
WITH f AS (SELECT SUM(freight_cost_usd) fr FROM cpg_demos.netopt_silver.freight_shipments WHERE is_product_material AND year_month >= '2025-05'),
     s AS (SELECT SUM(sales_usd) sa FROM cpg_demos.netopt_gold.sales_monthly WHERE year_month >= '2025-05')
SELECT ROUND(s.sa, 0) AS net_sales_usd, ROUND(f.fr, 0) AS freight_usd, ROUND(100 * f.fr / s.sa, 2) AS freight_pct_of_sales FROM f, s
```

| freight_pct_of_sales | freight_usd | net_sales_usd |
|---|---|---|
| 1.86 | 7.7258608E7 | 4.1448218E9 |

## ML targeting: share of out-of-time (2026) leakage captured by the riskiest lanes

```sql
WITH lane AS (
  SELECT directed_lane_id, SUM(expected_leakage_usd) exp_leak, SUM(GREATEST(total_cost_impact, 0)) real_leak
  FROM cpg_demos.netopt_gold.oor_risk_scores WHERE year_month >= '2026-01' GROUP BY 1),
r AS (SELECT *, PERCENT_RANK() OVER (ORDER BY exp_leak DESC) pr FROM lane)
SELECT COUNT(*) AS lanes_with_oor_2026,
       ROUND(100 * SUM(CASE WHEN pr < 0.10 THEN real_leak END) / SUM(real_leak), 1) AS top10pct_lanes_share_of_leakage_pct,
       ROUND(100 * SUM(CASE WHEN pr < 0.20 THEN real_leak END) / SUM(real_leak), 1) AS top20pct_lanes_share_of_leakage_pct,
       ROUND(SUM(real_leak), 0) AS realised_leakage_2026_usd
FROM r
```

| lanes_with_oor_2026 | realised_leakage_2026_usd | top10pct_lanes_share_of_leakage_pct | top20pct_lanes_share_of_leakage_pct |
|---|---|---|---|
| 816 | 8494718.0 | 34.8 | 54.1 |

## Planner action queue (ML-ranked, GenAI-recommended) served from Lakebase

```sql
SELECT COUNT(*) AS lanes_in_queue, COUNT(CASE WHEN risk_tier = 'HIGH' THEN 1 END) AS high_risk_lanes,
       ROUND(SUM(expected_monthly_leakage_usd), 0) AS queue_expected_monthly_leakage_usd,
       ROUND(12 * SUM(expected_monthly_leakage_usd), 0) AS queue_annualised_leakage_usd,
       ROUND(SUM(realized_leakage_usd), 0) AS queue_realised_leakage_3m_usd,
       MIN(window_start) AS window_start, MAX(window_end) AS window_end
FROM cpg_demos.netopt_gold.lane_action_queue
```

| high_risk_lanes | lanes_in_queue | queue_annualised_leakage_usd | queue_expected_monthly_leakage_usd | queue_realised_leakage_3m_usd | window_end | window_start |
|---|---|---|---|---|---|---|
| 12 | 40 | 1.0342836E7 | 861903.0 | 1445125.0 | 2026-04 | 2026-02 |

## Queue by recommended action type

```sql
SELECT action_type, action_owner, COUNT(*) AS lanes, ROUND(SUM(expected_monthly_leakage_usd), 0) AS exp_monthly_leakage_usd
FROM cpg_demos.netopt_gold.lane_action_queue GROUP BY 1, 2 ORDER BY 4 DESC
```

| action_owner | action_type | exp_monthly_leakage_usd | lanes |
|---|---|---|---|
| Supply planner | FIX_MRP_PLAN | 569063.0 | 26 |
| DC transportation planner | REROUTE_TO_PLAN | 163668.0 | 8 |
| Supply planner | REROUTE_TO_PLAN | 129171.0 | 6 |

## Leakage by product family, trailing 12 months

```sql
SELECT family, ROUND(SUM(total_cost_impact), 0) AS leakage_usd, COUNT(*) AS costly_oor_rows
FROM cpg_demos.netopt_gold.oor_analysis WHERE drill_tab = 'costly_oor' AND year_month >= '2025-05' GROUP BY 1 ORDER BY 2 DESC
```

| costly_oor_rows | family | leakage_usd |
|---|---|---|
| 1759 | Frozen Bread Dough | 3697284.0 |
| 1423 | Pizza Crust | 3216064.0 |
| 1585 | Cakes & Desserts | 3151713.0 |
| 1510 | Sweet Dough | 2959948.0 |
| 1325 | Toppings | 2838836.0 |
| 1197 | Icing & Glaze | 2565216.0 |
| 885 | Appetizers | 1917237.0 |
| 814 | Rolls & Biscuits | 1631438.0 |
| 758 | Barquettes & Shells | 1613321.0 |
