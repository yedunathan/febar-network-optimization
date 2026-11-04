# Executed notebook: `ml_oor_cost_risk`

_Task run `1096369819184461` of job run `285440164007553` · result **SUCCESS** · 99s_


# 04 · ML — out-of-route (OOR) cost-risk model
**Question the business asks:** *"When a load leaves the plan, will it cost us more than the planned lane — and by how much?"*

Only ~60% of out-of-route moves are actually more expensive than plan; the rest are opportunistic and cheaper.
Treating every OOR the same floods planners with noise. This model scores each OOR lane-material-month with:
- `p_costly` — probability the move costs more per case than its planned baseline (classifier)
- `pred_extra_cost_per_case` — expected $/case delta vs plan (regressor)

Features use only what is known **before the freight invoice arrives** (lane geometry, node types, product family,
volume, planned-baseline cost) — the realised cost per case is never a feature. Validation is **out-of-time**
(train ≤ 2025-12, test 2026-01..2026-04). Model is logged to MLflow, registered in Unity Catalog as
`netopt_ml.oor_cost_risk` (alias `champion`), and used to batch-score `netopt_gold.oor_risk_scores` and the
lane-level `netopt_gold.lane_watchlist` that drives the app's planner queue.

```python
dbutils.widgets.text("catalog", "cpg_demos")
CAT = dbutils.widgets.get("catalog")
SILVER, GOLD, ML = f"{CAT}.netopt_silver", f"{CAT}.netopt_gold", f"{CAT}.netopt_ml"
MODEL_NAME = f"{ML}.oor_cost_risk"
SPLIT_MONTH = "2026-01"

import numpy as np
import pandas as pd
import mlflow
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import (roc_auc_score, average_precision_score, accuracy_score, precision_score,
                             recall_score, mean_absolute_error, r2_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

mlflow.set_registry_uri("databricks-uc")
print("mlflow", mlflow.__version__)
```

**Output:**
```text
mlflow 3.12.0
```

## 1. Feature set (lane geometry vs. the material's own plan)

```python
spark.sql(f"""
CREATE OR REPLACE TEMP VIEW oor_features AS
WITH p AS (SELECT plant_s4, plant_type, country, lat, lon FROM {SILVER}.enterprise_plant),
miles AS (
  SELECT s.*,
         2 * 3958.8 * asin(sqrt(pow(sin(radians(s.dest_lat - s.origin_lat) / 2), 2) +
           cos(radians(s.origin_lat)) * cos(radians(s.dest_lat)) * pow(sin(radians(s.dest_lon - s.origin_lon) / 2), 2))) AS lane_miles
  FROM {GOLD}.lane_material_sot s WHERE s.material_number != 'SHUTTLE'),
plan_geo AS (   -- how far this material's *planned* lanes from the same origin travel that month
  SELECT material_number, origin_plant, year_month, avg(lane_miles) AS planned_miles_same_origin,
         count(*) AS planned_lanes_same_origin
  FROM miles WHERE lane_type = 'planned_transport' GROUP BY ALL),
plan_geo_mat AS (
  SELECT material_number, avg(lane_miles) AS planned_miles_material FROM miles
  WHERE lane_type = 'planned_transport' GROUP BY ALL)
SELECT o.directed_lane_id, o.origin_plant, o.dest_plant, o.material_number, o.year_month,
       o.family, o.material_desc, o.total_cases, o.distinct_shipments,
       o.baseline_cost_per_case, o.baseline_tier, o.extra_cost_per_case, o.total_cost_impact, o.drill_tab,
       po.plant_type AS origin_type, pd.plant_type AS dest_type,
       CAST(po.country != pd.country AS INT) AS cross_border,
       CAST(substr(o.year_month, 6, 2) AS INT) AS month_of_year,
       m.lane_miles,
       coalesce(g.planned_miles_same_origin, gm.planned_miles_material) AS planned_miles,
       m.lane_miles / greatest(coalesce(g.planned_miles_same_origin, gm.planned_miles_material, m.lane_miles), 25) AS miles_vs_plan,
       coalesce(g.planned_lanes_same_origin, 0) AS planned_lanes_same_origin,
       o.total_cases / greatest(o.distinct_shipments, 1) AS cases_per_shipment
FROM {GOLD}.oor_analysis o
JOIN p po ON o.origin_plant = po.plant_s4
JOIN p pd ON o.dest_plant = pd.plant_s4
JOIN miles m ON m.directed_lane_id = o.directed_lane_id AND m.material_number = o.material_number
            AND m.year_month = o.year_month AND m.lane_type = 'out_of_lane_transport'
LEFT JOIN plan_geo g ON g.material_number = o.material_number AND g.origin_plant = o.origin_plant AND g.year_month = o.year_month
LEFT JOIN plan_geo_mat gm ON gm.material_number = o.material_number
WHERE o.drill_tab IN ('costly_oor', 'cheaper_oor')
""")
df = spark.table("oor_features").toPandas()
df["is_costly"] = (df["extra_cost_per_case"] > 0).astype(int)
print(f"labelled OOR lane-material-months: {len(df):,}   costly share: {df.is_costly.mean():.1%}")
print(df.groupby("year_month").agg(rows=("is_costly", "size"), costly_rate=("is_costly", "mean")).round(3).to_string())
```

**Output:**
```text
labelled OOR lane-material-months: 23,086   costly share: 59.0%
            rows  costly_rate
year_month                   
2025-01      534        0.835
2025-02      727        0.765
2025-03      913        0.716
2025-04     1037        0.692
2025-05     1216        0.629
2025-06     1323        0.607
2025-07     1408        0.602
2025-08     1470        0.598
2025-09     1485        0.595
2025-10     1568        0.559
2025-11     1654        0.581
2025-12     1754        0.575
2026-01     1843        0.553
2026-02     1977        0.547
2026-03     2066        0.512
2026-04     2111        0.509
```

```python
NUM = ["lane_miles", "planned_miles", "miles_vs_plan", "baseline_cost_per_case", "baseline_tier", "total_cases",
       "distinct_shipments", "cases_per_shipment", "planned_lanes_same_origin", "cross_border", "month_of_year"]
CAT_COLS = ["origin_type", "dest_type", "family"]
FEATURES = NUM + CAT_COLS
for c in NUM:
    df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
for c in CAT_COLS:
    df[c] = df[c].fillna("UNKNOWN").astype(str)

train, test = df[df.year_month < SPLIT_MONTH], df[df.year_month >= SPLIT_MONTH]
print(f"train={len(train):,} ({train.year_month.min()}..{train.year_month.max()})   "
      f"test={len(test):,} ({test.year_month.min()}..{test.year_month.max()})")


def make_pre():
    return ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_COLS),
        ("num", "passthrough", NUM),
    ])
```

**Output:**
```text
train=15,089 (2025-01..2025-12)   test=7,997 (2026-01..2026-04)
```

## 2. Train + evaluate (out-of-time), log to MLflow

```python

class OORCostRisk(mlflow.pyfunc.PythonModel):
    """Wraps classifier + regressor so one UC model returns both scores the planner queue needs."""

    def __init__(self, clf, reg):
        self.clf, self.reg = clf, reg

    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        X = model_input[FEATURES].copy()
        for c in NUM:
            X[c] = pd.to_numeric(X[c], errors="coerce").astype("float64")
        for c in CAT_COLS:
            X[c] = X[c].fillna("UNKNOWN").astype(str)
        return pd.DataFrame({
            "p_costly": self.clf.predict_proba(X)[:, 1],
            "pred_extra_cost_per_case": self.reg.predict(X),
        })


user = spark.sql("SELECT current_user()").first()[0]
mlflow.set_experiment(f"/Users/{user}/netopt_oor_cost_risk")

with mlflow.start_run(run_name="hgb_oor_cost_risk") as run:
    clf = Pipeline([("pre", make_pre()), ("m", HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=1.0, random_state=42))])
    reg = Pipeline([("pre", make_pre()), ("m", HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=1.0, random_state=42))])
    clf.fit(train[FEATURES], train.is_costly)
    reg.fit(train[FEATURES], train.extra_cost_per_case)

    p = clf.predict_proba(test[FEATURES])[:, 1]
    yhat = (p >= 0.5).astype(int)
    pred_extra = reg.predict(test[FEATURES])
    base_rate = test.is_costly.mean()
    # business metric: of the leakage $ in the test window, how much sits in the top-20% riskiest rows by expected $?
    t = test.assign(exp_leak=np.clip(pred_extra, 0, None) * test.total_cases,
                    leak=np.clip(test.total_cost_impact, 0, None)).sort_values("exp_leak", ascending=False)
    top = t.head(int(len(t) * 0.2))
    metrics = {
        "test_auc": roc_auc_score(test.is_costly, p),
        "test_pr_auc": average_precision_score(test.is_costly, p),
        "test_accuracy": accuracy_score(test.is_costly, yhat),
        "test_precision": precision_score(test.is_costly, yhat),
        "test_recall": recall_score(test.is_costly, yhat),
        "test_base_rate_costly": base_rate,
        "test_mae_extra_cost_per_case": mean_absolute_error(test.extra_cost_per_case, pred_extra),
        "test_r2_extra_cost_per_case": r2_score(test.extra_cost_per_case, pred_extra),
        "test_naive_mae_extra_cost_per_case": mean_absolute_error(
            test.extra_cost_per_case, np.full(len(test), train.extra_cost_per_case.mean())),
        "top20pct_rows_share_of_leakage": top.leak.sum() / t.leak.sum(),
        "test_total_leakage_usd": float(t.leak.sum()),
        "train_rows": len(train), "test_rows": len(test),
    }
    mlflow.log_params({"split_month": SPLIT_MONTH, "features": ",".join(FEATURES), "algo": "HistGradientBoosting",
                       "max_iter": 300, "learning_rate": 0.06})
    mlflow.log_metrics(metrics)

    sample = test[FEATURES].head(20)
    model = OORCostRisk(clf, reg)
    mlflow.pyfunc.log_model(
        name="model", python_model=model, input_example=sample,
        signature=infer_signature(sample, model.predict(None, sample)),
        registered_model_name=MODEL_NAME,
        pip_requirements=["scikit-learn", "pandas", "numpy"],
    )
    run_id = run.info.run_id

print(f"MLflow run: {run_id}")
for k, v in metrics.items():
    print(f"  {k:<40} {v:,.4f}" if isinstance(v, float) else f"  {k:<40} {v:,}")
```

**Output:**
```text
🔗 View Logged Model at: https://fe-vm-vdm-serverless-jpckvw.cloud.databricks.com/ml/experiments/1059371947298685/models/m-26b9d519eb414e2d89b3f3cea2e2be41?o=3381193768081108
2026/11/04 02:40:33 INFO mlflow.pyfunc: Validating input example against model signature
Registered model 'cpg_demos.netopt_ml.oor_cost_risk' already exists. Creating a new version of this model...
```

**Output:**
```text
🔗 Created version '2' of model 'cpg_demos.netopt_ml.oor_cost_risk': https://fe-vm-vdm-serverless-jpckvw.cloud.databricks.com/explore/data/models/cpg_demos/netopt_ml/oor_cost_risk/version/2?o=3381193768081108
```

**Output:**
```text
MLflow run: 7f58be48298045bcabb3a4c370ca1632
  test_auc                                 0.9166
  test_pr_auc                              0.9321
  test_accuracy                            0.8216
  test_precision                           0.8248
  test_recall                              0.8414
  test_base_rate_costly                    0.5291
  test_mae_extra_cost_per_case             3.1903
  test_r2_extra_cost_per_case              0.6444
  test_naive_mae_extra_cost_per_case       8.0061
  top20pct_rows_share_of_leakage           0.7716
  test_total_leakage_usd                   8,494,718.0694
  train_rows                               15,089
  test_rows                                7,997
```

```python
# feature importance via permutation on the test window (classifier AUC drop)
from sklearn.inspection import permutation_importance
imp = permutation_importance(clf, test[FEATURES], test.is_costly, scoring="roc_auc", n_repeats=5, random_state=42)
imp_df = pd.DataFrame({"feature": FEATURES, "auc_drop": imp.importances_mean}).sort_values("auc_drop", ascending=False)
print(imp_df.round(4).to_string(index=False))
with mlflow.start_run(run_id=run_id):
    mlflow.log_table(imp_df, "permutation_importance.json")
```

**Output:**
```text
                  feature  auc_drop
               lane_miles    0.1779
   baseline_cost_per_case    0.1298
       cases_per_shipment    0.0474
            miles_vs_plan    0.0317
              origin_type    0.0093
                dest_type    0.0081
            baseline_tier    0.0045
              total_cases    0.0029
            planned_miles    0.0015
       distinct_shipments    0.0012
             cross_border    0.0004
planned_lanes_same_origin    0.0003
                   family   -0.0000
            month_of_year   -0.0001
```

## 3. Promote in Unity Catalog (`@champion`)

```python
from mlflow import MlflowClient
client = MlflowClient(registry_uri="databricks-uc")
latest = max(client.search_model_versions(f"name='{MODEL_NAME}'"), key=lambda v: int(v.version))
client.set_registered_model_alias(MODEL_NAME, "champion", latest.version)
client.update_registered_model(MODEL_NAME, description=(
    "Out-of-route freight cost-risk model. Input: OOR lane-material-month features (lane miles vs plan, node types, "
    "family, volume, planned baseline $/case). Output: p_costly, pred_extra_cost_per_case. Trained by netopt-end-to-end job."))
client.update_model_version(MODEL_NAME, latest.version, description=(
    f"AUC={metrics['test_auc']:.3f}, PR-AUC={metrics['test_pr_auc']:.3f}, MAE $/case={metrics['test_mae_extra_cost_per_case']:.3f} "
    f"(out-of-time test {SPLIT_MONTH}+). run_id={run_id}"))
print(f"registered {MODEL_NAME} v{latest.version} -> alias @champion")
```

**Output:**
```text
registered cpg_demos.netopt_ml.oor_cost_risk v2 -> alias @champion
```

## 4. Batch scoring with the registered `@champion` model

```python
champion = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@champion")
scores = champion.predict(df[FEATURES])
scored = pd.concat([df.reset_index(drop=True), scores], axis=1)
scored["expected_leakage_usd"] = np.clip(scored.pred_extra_cost_per_case, 0, None) * scored.total_cases
scored["model_version"] = int(latest.version)
keep = ["directed_lane_id", "origin_plant", "dest_plant", "material_number", "material_desc", "family", "year_month",
        "total_cases", "lane_miles", "planned_miles", "miles_vs_plan", "baseline_cost_per_case", "extra_cost_per_case",
        "total_cost_impact", "is_costly", "p_costly", "pred_extra_cost_per_case", "expected_leakage_usd", "model_version"]
(spark.createDataFrame(scored[keep]).write.mode("overwrite").option("overwriteSchema", "true")
 .saveAsTable(f"{GOLD}.oor_risk_scores"))
spark.sql(f"COMMENT ON TABLE {GOLD}.oor_risk_scores IS 'ML scores (oor_cost_risk@champion) per out-of-route lane x material x month'")
print(f"wrote {GOLD}.oor_risk_scores: {len(scored):,} rows")
```

**Output:**
```text
wrote cpg_demos.netopt_gold.oor_risk_scores: 23,086 rows
```

## 5. Lane watchlist — trailing-3-month risk per OOR lane + nearest planned alternative

```python
spark.sql(f"""
CREATE OR REPLACE TABLE {GOLD}.lane_watchlist
COMMENT 'Lane-level OOR risk over the trailing 3 months with the closest planned alternative lane (feeds GenAI + Lakebase)'
TBLPROPERTIES (delta.enableChangeDataFeed = true)
AS
WITH win AS (SELECT max(year_month) AS m_end, date_format(add_months(to_date(max(year_month) || '-01'), -2), 'yyyy-MM') AS m_start
             FROM {GOLD}.oor_risk_scores),
s AS (SELECT r.* FROM {GOLD}.oor_risk_scores r, win WHERE r.year_month BETWEEN win.m_start AND win.m_end),
lane AS (
  SELECT directed_lane_id, first(origin_plant) origin_plant, first(dest_plant) dest_plant,
         count(*) oor_events, count(DISTINCT material_number) skus, sum(total_cases) oor_cases,
         round(sum(greatest(total_cost_impact, 0)), 2) realized_leakage_usd,
         round(sum(total_cost_impact), 2) net_cost_impact_usd,
         round(avg(p_costly), 4) avg_p_costly,
         round(sum(expected_leakage_usd) / 3, 2) expected_monthly_leakage_usd,
         round(avg(lane_miles), 1) lane_miles, round(avg(planned_miles), 1) planned_miles,
         max_by(family, total_cases) top_family, max_by(material_number, total_cases) top_material,
         max_by(material_desc, total_cases) top_material_desc
  FROM s GROUP BY directed_lane_id),
-- closest planned destination from the same origin for the lane's top material (what the plan says should happen)
alt AS (
  SELECT l.directed_lane_id, p.dest_plant AS alt_dest_plant, p.directed_lane_id AS alt_lane_id,
         p.avg_cost_per_case AS alt_cost_per_case,
         row_number() OVER (PARTITION BY l.directed_lane_id ORDER BY
           pow(p.dest_lat - d.lat, 2) + pow(p.dest_lon - d.lon, 2), p.avg_cost_per_case) rn
  FROM lane l
  JOIN {SILVER}.enterprise_plant d ON d.plant_s4 = l.dest_plant
  JOIN {GOLD}.lane_material_sot p ON p.material_number = l.top_material AND p.origin_plant = l.origin_plant
       AND p.lane_type = 'planned_transport' AND p.avg_cost_per_case IS NOT NULL AND p.dest_plant != l.dest_plant),
win2 AS (SELECT * FROM win)
SELECT l.*, po.plant_name origin_name, pd.plant_name dest_name, po.plant_type origin_type, pd.plant_type dest_type,
       a.alt_lane_id, a.alt_dest_plant, pa.plant_name alt_dest_name, round(a.alt_cost_per_case, 3) alt_cost_per_case,
       CASE WHEN l.avg_p_costly >= 0.65 AND l.expected_monthly_leakage_usd >= percentile_approx(l.expected_monthly_leakage_usd, 0.8) OVER () THEN 'HIGH'
            WHEN l.avg_p_costly >= 0.5 THEN 'MEDIUM' ELSE 'LOW' END risk_tier,
       w.m_start window_start, w.m_end window_end, current_timestamp() scored_at
FROM lane l
CROSS JOIN win2 w
JOIN {SILVER}.enterprise_plant po ON po.plant_s4 = l.origin_plant
JOIN {SILVER}.enterprise_plant pd ON pd.plant_s4 = l.dest_plant
LEFT JOIN alt a ON a.directed_lane_id = l.directed_lane_id AND a.rn = 1
LEFT JOIN {SILVER}.enterprise_plant pa ON pa.plant_s4 = a.alt_dest_plant
""")
spark.sql(f"ALTER TABLE {GOLD}.lane_watchlist ALTER COLUMN directed_lane_id SET NOT NULL")
spark.sql(f"ALTER TABLE {GOLD}.lane_watchlist ADD CONSTRAINT lane_watchlist_pk PRIMARY KEY (directed_lane_id)")

display(spark.sql(f"""SELECT risk_tier, count(*) lanes, sum(oor_events) oor_events,
                             round(sum(realized_leakage_usd)) realized_leakage_usd,
                             round(sum(expected_monthly_leakage_usd)) expected_monthly_leakage_usd
                      FROM {GOLD}.lane_watchlist GROUP BY risk_tier ORDER BY 4 DESC"""))
display(spark.sql(f"""SELECT directed_lane_id, origin_name, dest_name, top_family, oor_events, avg_p_costly,
                             expected_monthly_leakage_usd, realized_leakage_usd, alt_dest_name, risk_tier
                      FROM {GOLD}.lane_watchlist ORDER BY expected_monthly_leakage_usd DESC LIMIT 15"""))
```

**Output:**
```text
risk_tier | lanes | oor_events | realized_leakage_usd | expected_monthly_leakage_usd
----------+-------+------------+----------------------+-----------------------------
MEDIUM    | 540   | 2370       | 3899456.0            | 1255248.0                   
HIGH      | 85    | 655        | 2144201.0            | 772234.0                    
LOW       | 130   | 3129       | 438032.0             | 600294.0                    
[3 rows]
```

**Output:**
```text
directed_lane_id | origin_name         | dest_name      | top_family          | oor_events | avg_p_costly | expected_monthly_leakage_usd | realized_leakage_usd | alt_dest_name  | risk_tier
-----------------+---------------------+----------------+---------------------+------------+--------------+------------------------------+----------------------+----------------+----------
2508-2552        | Drummondville Plant | Eagan DC       | Toppings            | 94         | 0.635        | 46693.45                     | 180661.72            | Columbus DC    | MEDIUM   
2508-2542        | Drummondville Plant | Bolingbrook DC | Pizza Crust         | 98         | 0.6186       | 43001.43                     | 55424.09             |                | MEDIUM   
2508-2551        | Drummondville Plant | Columbus DC    | Cakes & Desserts    | 114        | 0.5968       | 41503.2                      | 87129.56             |                | MEDIUM   
2507-2540        | Joliet Plant        | Atlanta DC     | Cakes & Desserts    | 116        | 0.6709       | 36909.03                     | 54173.93             | Columbus DC    | HIGH     
2503-2545        | McAllen Plant       | Aurora DC      | Sweet Dough         | 63         | 0.6804       | 31930.96                     | 68488.44             | Kansas City DC | HIGH     
2502-2553        | Dayton Plant        | Memphis DC     | Pizza Crust         | 125        | 0.624        | 31845.91                     | 79762.01             | Charlotte DC   | MEDIUM   
2501-2540        | Rochester Plant     | Atlanta DC     | Pizza Crust         | 75         | 0.7012       | 30288.68                     | 32734.44             | Charlotte DC   | HIGH     
2508-2550        | Drummondville Plant | Charlotte DC   | Cakes & Desserts    | 100        | 0.5955       | 29680.95                     | 75146.26             | Eagan DC       | MEDIUM   
2507-2551        | Joliet Plant        | Columbus DC    | Cakes & Desserts    | 112        | 0.4808       | 26826.28                     | 18761.87             | Memphis DC     | LOW      
2502-2542        | Dayton Plant        | Bolingbrook DC | Rolls & Biscuits    | 96         | 0.4188       | 25556.84                     | 14601.23             |                | LOW      
2508-2547        | Drummondville Plant | Edison DC      | Rolls & Biscuits    | 113        | 0.4662       | 25041.69                     | 27652.53             |                | LOW      
2507-2548        | Joliet Plant        | Kansas City DC | Barquettes & Shells | 106        | 0.5624       | 25033.06                     | 25879.02             | Eagan DC       | MEDIUM   
2502-2540        | Dayton Plant        | Atlanta DC     | Cakes & Desserts    | 91         | 0.642        | 24919.73                     | 24686.65             | Bolingbrook DC | MEDIUM   
2507-2542        | Joliet Plant        | Bolingbrook DC | Barquettes & Shells | 121        | 0.2167       | 24604.67                     | 446.53               |                | LOW      
2503-2549        | McAllen Plant       | Phoenix DC     | Appetizers          | 47         | 0.6048       | 24272.17                     | 52626.67             |                | MEDIUM   
[15 rows]
```
