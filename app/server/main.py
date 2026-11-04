"""Northstar Network Optimization — FastAPI backend for the Databricks App.

Queries the netopt gold tables through a serverless SQL warehouse
(statement execution API) with a small TTL cache, proxies Genie
conversations for the natural-language panel, and serves the Ops Console
(ML + GenAI lane action queue) from Lakebase.
"""
import os
import json
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from databricks.sdk import WorkspaceClient

from server import lakebase

CAT = os.environ.get("NETOPT_CATALOG", "cpg_demos")
GOLD = f"{CAT}.{os.environ.get('NETOPT_GOLD_SCHEMA', 'netopt_gold')}"
SILVER = f"{CAT}.{os.environ.get('NETOPT_SILVER_SCHEMA', 'netopt_silver')}"
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")

app = FastAPI(title="Northstar Network Optimization API")
_w: Optional[WorkspaceClient] = None
_lock = threading.Lock()


def w() -> WorkspaceClient:
    global _w
    with _lock:
        if _w is None:
            _w = WorkspaceClient()
        return _w


_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 3600  # gold tables change only on pipeline runs


def query(sql: str) -> list[dict]:
    now = time.time()
    hit = _cache.get(sql)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    resp = w().statement_execution.execute_statement(
        statement=sql, warehouse_id=WAREHOUSE_ID, wait_timeout="50s"
    )
    state = resp.status.state.value if resp.status and resp.status.state else "FAILED"
    while state in ("PENDING", "RUNNING"):
        time.sleep(1.0)
        resp = w().statement_execution.get_statement(resp.statement_id)
        state = resp.status.state.value
    if state != "SUCCEEDED":
        msg = resp.status.error.message if resp.status and resp.status.error else state
        raise HTTPException(status_code=500, detail=f"SQL failed: {msg}")
    cols = [c.name for c in resp.manifest.schema.columns]
    rows = [dict(zip(cols, r)) for r in (resp.result.data_array or [])] if resp.result else []
    _cache[sql] = (now, rows)
    return rows


def esc(v: str) -> str:
    return v.replace("'", "''")


def month_filter(start: str, end: str, col: str = "year_month") -> str:
    return f"{col} >= '{esc(start)}' AND {col} <= '{esc(end)}'"


# ------------------------------------------------------------------ bootstrap

@app.get("/api/bootstrap")
def bootstrap():
    months = [r["year_month"] for r in query(
        f"SELECT DISTINCT year_month FROM {GOLD}.lane_material_sot ORDER BY year_month")]
    plants = query(f"""
        WITH fam AS (
            SELECT s.origin_plant AS plant_s4, m.family, sum(coalesce(s.total_cases, 0)) AS cases
            FROM {GOLD}.lane_material_sot s
            JOIN {SILVER}.enterprise_material_master m ON s.material_number = m.material_number
            GROUP BY s.origin_plant, m.family
        ),
        top_fam AS (
            SELECT plant_s4,
                   concat_ws(', ', slice(transform(array_sort(collect_list(struct(-cases AS neg, family))),
                                                   x -> x.family), 1, 3)) AS top_families
            FROM fam WHERE cases > 0 GROUP BY plant_s4
        )
        SELECT p.plant_s4, p.plant_ecc, p.plant_name, p.plant_type, p.city, p.region, p.country,
               p.lat, p.lon, p.inbound_lanes, p.outbound_lanes, p.inbound_cases, p.outbound_cases,
               f.top_families
        FROM {GOLD}.plant_stats p LEFT JOIN top_fam f ON p.plant_s4 = f.plant_s4
        ORDER BY p.plant_s4""")
    materials = query(f"""
        SELECT material_number, first(material_desc) AS material_desc, first(family) AS family,
               sort_array(collect_set(CASE WHEN has_freight = 1 THEN year_month END)) AS freight_months,
               max(has_any) AS has_any
        FROM {GOLD}.material_period_status
        GROUP BY material_number ORDER BY material_number""")
    return {"months": months, "plants": plants, "materials": materials}


# ------------------------------------------------------------------ lanes

@app.get("/api/lanes")
def lanes(start: str, end: str, material: Optional[str] = None):
    mat = f"AND material_number = '{esc(material)}'" if material else ""
    rows = query(f"""
        SELECT directed_lane_id, origin_plant, dest_plant,
               any_value(origin_lat) origin_lat, any_value(origin_lon) origin_lon,
               any_value(dest_lat) dest_lat, any_value(dest_lon) dest_lon,
               max(CASE WHEN lane_type = 'planned_transport' THEN 1 ELSE 0 END) has_planned,
               max(CASE WHEN lane_type = 'out_of_lane_transport' THEN 1 ELSE 0 END) has_oor,
               max(CASE WHEN lane_type = 'theoretical_transport' THEN 1 ELSE 0 END) has_theoretical,
               sum(CASE WHEN lane_type != 'theoretical_transport' THEN coalesce(total_cases, 0) ELSE 0 END) total_cases,
               sum(CASE WHEN lane_type != 'theoretical_transport' THEN coalesce(allocated_cases, 0) ELSE 0 END) allocated_cases,
               round(sum(coalesce(total_freight_usd, 0)), 2) total_freight_usd,
               count(DISTINCT material_number) n_materials,
               sum(coalesce(distinct_shipments, 0)) shipments
        FROM {GOLD}.lane_material_sot
        WHERE origin_lat IS NOT NULL AND dest_lat IS NOT NULL
          AND (({month_filter(start, end)}) OR lane_type = 'theoretical_transport')
          {mat}
        GROUP BY directed_lane_id, origin_plant, dest_plant
    """)
    return {"lanes": rows}


@app.get("/api/plant_materials")
def plant_materials(plant: str):
    rows = query(f"""
        SELECT DISTINCT material_number FROM {GOLD}.lane_material_sot
        WHERE (origin_plant = '{esc(plant)}' OR dest_plant = '{esc(plant)}')
          AND material_number != 'SHUTTLE'
    """)
    return {"materials": [r["material_number"] for r in rows]}


# ------------------------------------------------------------------ details

@app.get("/api/plant/{plant_id}")
def plant_detail(plant_id: str, start: str, end: str, material: Optional[str] = None):
    mat = f"AND material_number = '{esc(material)}'" if material else ""
    p = esc(plant_id)
    period = query(f"""
        SELECT sum(CASE WHEN origin_plant = '{p}' THEN 1 ELSE 0 END) outbound_lane_months,
               sum(CASE WHEN dest_plant = '{p}' THEN 1 ELSE 0 END) inbound_lane_months,
               count(DISTINCT CASE WHEN origin_plant = '{p}' THEN directed_lane_id END) outbound_lanes,
               count(DISTINCT CASE WHEN dest_plant = '{p}' THEN directed_lane_id END) inbound_lanes,
               sum(CASE WHEN origin_plant = '{p}' THEN coalesce(total_cases, 0) ELSE 0 END) outbound_cases,
               sum(CASE WHEN dest_plant = '{p}' THEN coalesce(total_cases, 0) ELSE 0 END) inbound_cases,
               count(DISTINCT material_number) n_materials
        FROM {GOLD}.lane_material_sot
        WHERE (origin_plant = '{p}' OR dest_plant = '{p}') AND ({month_filter(start, end)}) {mat}
    """)
    monthly = query(f"""
        SELECT year_month,
               sum(CASE WHEN origin_plant = '{p}' THEN coalesce(total_cases, 0) ELSE 0 END) outbound_cases,
               sum(CASE WHEN dest_plant = '{p}' THEN coalesce(total_cases, 0) ELSE 0 END) inbound_cases
        FROM {GOLD}.lane_material_sot
        WHERE (origin_plant = '{p}' OR dest_plant = '{p}') {mat}
        GROUP BY year_month ORDER BY year_month
    """)
    return {"period": period[0] if period else {}, "monthly": monthly}


@app.get("/api/lane/{lane_id}")
def lane_detail(lane_id: str, material: Optional[str] = None):
    l = esc(lane_id)
    mat = f"AND material_number = '{esc(material)}'" if material else ""
    alltime = query(f"""
        SELECT count(DISTINCT material_number) n_materials,
               sum(coalesce(total_cases, 0)) total_cases,
               sum(coalesce(allocated_cases, 0)) allocated_cases,
               round(sum(coalesce(total_freight_usd, 0)), 2) total_freight_usd,
               sum(coalesce(distinct_shipments, 0)) shipments,
               round(avg(avg_cost_per_case), 2) avg_cost_per_case,
               min(year_month) first_month, max(year_month) last_month
        FROM {GOLD}.lane_material_sot
        WHERE directed_lane_id = '{l}' AND lane_type != 'theoretical_transport' {mat}
    """)
    monthly = query(f"""
        SELECT year_month,
               sum(coalesce(total_cases, 0)) cases,
               round(sum(coalesce(total_freight_usd, 0)), 2) freight_usd,
               max(CASE WHEN lane_type = 'planned_transport' THEN 1 ELSE 0 END) has_planned,
               max(CASE WHEN lane_type = 'out_of_lane_transport' THEN 1 ELSE 0 END) has_oor
        FROM {GOLD}.lane_material_sot
        WHERE directed_lane_id = '{l}' {mat}
        GROUP BY year_month ORDER BY year_month
    """)
    breakdown = query(f"""
        SELECT lane_type, count(*) rows, sum(coalesce(total_cases, 0)) cases,
               round(sum(coalesce(total_freight_usd, 0)), 2) freight_usd
        FROM {GOLD}.lane_material_sot WHERE directed_lane_id = '{l}' {mat} GROUP BY lane_type
    """)
    top_materials = query(f"""
        SELECT s.material_number, any_value(m.material_desc) material_desc,
               sum(coalesce(s.total_cases, 0)) cases,
               round(sum(coalesce(s.total_freight_usd, 0)), 2) freight_usd,
               array_join(array_sort(array_distinct(flatten(collect_list(s.transport_modes)))), ', ') modes
        FROM {GOLD}.lane_material_sot s
        LEFT JOIN {SILVER}.enterprise_material_master m ON s.material_number = m.material_number
        WHERE s.directed_lane_id = '{l}' AND s.lane_type != 'theoretical_transport'
        GROUP BY s.material_number ORDER BY cases DESC LIMIT 10
    """)
    return {"alltime": alltime[0] if alltime else {}, "monthly": monthly,
            "breakdown": breakdown, "top_materials": top_materials}


# ------------------------------------------------------------------ routes & drilldown

@app.get("/api/routes")
def routes(material: Optional[str] = None):
    where = f"WHERE material_number = '{esc(material)}'" if material else ""
    limit = "" if material else "LIMIT 300"
    rows = query(f"""
        SELECT * FROM {GOLD}.material_routes {where}
        ORDER BY CASE category WHEN 'Happened Not Planned' THEN 0 WHEN 'Loop' THEN 1
                 WHEN 'Planned + Happened' THEN 2 ELSE 3 END,
                 total_cost_impact DESC NULLS LAST {limit}
    """)
    return {"routes": rows}


def _drill_filters(start: str, end: str, material: Optional[str], plant: Optional[str]) -> list[str]:
    f = [month_filter(start, end)]
    if material:
        f.append(f"material_number = '{esc(material)}'")
    if plant:
        p = esc(plant)
        f.append(f"(origin_plant = '{p}' OR dest_plant = '{p}')")
    return f


@app.get("/api/drilldown_counts")
def drilldown_counts(start: str, end: str, material: Optional[str] = None, plant: Optional[str] = None):
    f = _drill_filters(start, end, material, plant)
    rows = query(f"""
        SELECT drill_tab, count(*) n FROM {GOLD}.oor_analysis
        WHERE {' AND '.join(f)} GROUP BY drill_tab
    """)
    return {"counts": {r["drill_tab"]: int(r["n"]) for r in rows}}


@app.get("/api/drilldown/{tab}")
def drilldown(tab: str, start: str, end: str, material: Optional[str] = None,
              plant: Optional[str] = None, sort: Optional[str] = None,
              origin: Optional[str] = None, dest: Optional[str] = None):
    if tab not in ("costly_oor", "cheaper_oor", "no_baseline", "loops"):
        raise HTTPException(status_code=400, detail="bad tab")
    f = [f"drill_tab = '{tab}'"] + _drill_filters(start, end, material, plant)
    if origin:
        f.append(f"origin_plant = '{esc(origin)}'")
    if dest:
        f.append(f"dest_plant = '{esc(dest)}'")
    default_order = {"costly_oor": "total_cost_impact DESC NULLS LAST",
                     "cheaper_oor": "total_cost_impact ASC NULLS LAST",
                     "no_baseline": "total_freight_usd DESC",
                     "loops": "total_freight_usd DESC"}[tab]
    order = {"impact": "abs(total_cost_impact) DESC NULLS LAST",
             "delta": "abs(extra_cost_per_case) DESC NULLS LAST",
             "cases": "total_cases DESC",
             "freight": "total_freight_usd DESC",
             "month": "year_month DESC"}.get(sort or "", default_order)
    rows = query(f"""
        SELECT year_month, directed_lane_id, origin_plant, dest_plant, material_number,
               material_desc, family, total_cases,
               round(total_freight_usd, 2) total_freight_usd,
               round(avg_cost_per_case, 2) avg_cost_per_case,
               round(baseline_cost_per_case, 2) baseline_cost_per_case, baseline_tier,
               round(extra_cost_per_case, 2) extra_cost_per_case,
               round(total_cost_impact, 2) total_cost_impact, distinct_shipments
        FROM {GOLD}.oor_analysis WHERE {' AND '.join(f)} ORDER BY {order} LIMIT 500
    """)
    summary = query(f"""
        SELECT count(*) n, round(sum(total_cost_impact), 2) impact,
               sum(total_cases) cases, round(sum(total_freight_usd), 2) freight,
               count(DISTINCT material_number) n_materials
        FROM {GOLD}.oor_analysis WHERE {' AND '.join(f)}
    """)
    plants_n = query(f"""
        SELECT count(DISTINCT p) n_plants FROM (
            SELECT origin_plant p FROM {GOLD}.oor_analysis WHERE {' AND '.join(f)}
            UNION SELECT dest_plant FROM {GOLD}.oor_analysis WHERE {' AND '.join(f)}
        )
    """)
    s = summary[0] if summary else {}
    s["n_plants"] = plants_n[0]["n_plants"] if plants_n else 0
    return {"rows": rows, "summary": s}


# ------------------------------------------------------------------ overlays

@app.get("/api/sales")
def sales(start: str, end: str, material: Optional[str] = None):
    mat = f"AND material_number = '{esc(material)}'" if material else ""
    rows = query(f"""
        SELECT plant_s4, round(sum(sales_usd), 2) sales_usd, sum(sales_cases) sales_cases
        FROM {GOLD}.sales_monthly WHERE ({month_filter(start, end)}) {mat}
        GROUP BY plant_s4
    """)
    return {"sales": rows}


@app.get("/api/inventory")
def inventory(start: str, end: str, material: Optional[str] = None):
    mat = f"AND material_number = '{esc(material)}'" if material else ""
    rows = query(f"""
        SELECT plant_s4, round(avg(qty_on_hand_cases), 0) qty_on_hand_cases,
               round(avg(safety_stock_cases), 0) safety_stock_cases
        FROM {GOLD}.inventory_monthly WHERE ({month_filter(start, end)}) {mat}
        GROUP BY plant_s4
    """)
    return {"inventory": rows}


# ------------------------------------------------------------------ executive view

@app.get("/api/exec_summary")
def exec_summary(month: Optional[str] = None):
    """One-shot payload for the Executive 3D view, scoped to one month (default: latest)."""
    if not month:
        latest = query(f"SELECT max(year_month) m FROM {GOLD}.lane_material_sot WHERE total_cases IS NOT NULL")
        month = latest[0]["m"] if latest else "2026-04"
    m = esc(month)
    yy, mm = map(int, month.split("-"))
    t = yy * 12 + (mm - 1) - 11  # trailing-12-month window start
    lo = f"{t // 12}-{t % 12 + 1:02d}"
    # fire all queries in parallel — one warehouse round-trip of wall time, not eight
    ex = ThreadPoolExecutor(max_workers=8)
    planned_f = ex.submit(query, f"""
        SELECT directed_lane_id, origin_plant, dest_plant,
               any_value(origin_lat) origin_lat, any_value(origin_lon) origin_lon,
               any_value(dest_lat) dest_lat, any_value(dest_lon) dest_lon,
               sum(coalesce(total_cases, 0)) total_cases,
               round(sum(coalesce(total_freight_usd, 0)), 0) freight_usd
        FROM {GOLD}.lane_material_sot
        WHERE lane_type = 'planned_transport' AND year_month = '{m}'
          AND origin_lat IS NOT NULL AND dest_lat IS NOT NULL
        GROUP BY directed_lane_id, origin_plant, dest_plant
    """)
    top_oor_f = ex.submit(query, f"""
        WITH leaks AS (
            SELECT directed_lane_id, origin_plant, dest_plant,
                   round(sum(total_cost_impact), 0) impact, sum(total_cases) total_cases
            FROM {GOLD}.oor_analysis WHERE drill_tab = 'costly_oor' AND year_month = '{m}'
            GROUP BY directed_lane_id, origin_plant, dest_plant
            ORDER BY impact DESC LIMIT 10
        )
        SELECT l.*, po.lat origin_lat, po.lon origin_lon, pd.lat dest_lat, pd.lon dest_lon
        FROM leaks l
        JOIN {GOLD}.plant_stats po ON l.origin_plant = po.plant_s4
        JOIN {GOLD}.plant_stats pd ON l.dest_plant = pd.plant_s4
    """)
    kpis_f = ex.submit(query, f"""
        SELECT count(DISTINCT CASE WHEN lane_type = 'planned_transport' THEN directed_lane_id END) planned_lanes,
               round(sum(coalesce(total_freight_usd, 0)), 0) total_freight,
               round(sum(CASE WHEN lane_type = 'planned_transport' THEN coalesce(total_freight_usd, 0) ELSE 0 END)
                     / nullif(sum(coalesce(total_freight_usd, 0)), 0) * 100, 1) on_plan_pct,
               round(sum(CASE WHEN lane_type = 'out_of_lane_transport' THEN coalesce(total_freight_usd, 0) ELSE 0 END), 0) month_oor_freight,
               round(sum(CASE WHEN lane_type = 'out_of_lane_transport' THEN coalesce(total_freight_usd, 0) ELSE 0 END)
                     / nullif(sum(coalesce(total_freight_usd, 0)), 0) * 100, 1) month_oor_pct,
               count(DISTINCT CASE WHEN material_number != 'SHUTTLE' THEN material_number END) n_materials
        FROM {GOLD}.lane_material_sot WHERE year_month = '{m}'
    """)
    trend_f = ex.submit(query, f"""
        SELECT year_month,
               round(sum(coalesce(total_freight_usd, 0)), 0) total_freight,
               round(sum(CASE WHEN lane_type = 'out_of_lane_transport' THEN coalesce(total_freight_usd, 0) ELSE 0 END), 0) oor_freight,
               round(sum(CASE WHEN lane_type = 'out_of_lane_transport' THEN coalesce(total_freight_usd, 0) ELSE 0 END)
                     / nullif(sum(coalesce(total_freight_usd, 0)), 0) * 100, 1) oor_pct
        FROM {GOLD}.lane_material_sot
        WHERE total_cases IS NOT NULL
        GROUP BY year_month ORDER BY year_month
    """)
    impact_f = ex.submit(query, f"SELECT round(sum(total_cost_impact), 0) oor_impact FROM {GOLD}.oor_analysis WHERE drill_tab = 'costly_oor' AND year_month = '{m}'")
    yearly_f = ex.submit(query, f"""
        SELECT round(sum(total_cost_impact), 0) yearly_impact
        FROM {GOLD}.oor_analysis
        WHERE drill_tab = 'costly_oor' AND year_month BETWEEN '{lo}' AND '{m}'
    """)
    yearly_freight_f = ex.submit(query, f"""
        SELECT round(sum(coalesce(total_freight_usd, 0)), 0) yearly_freight,
               round(sum(CASE WHEN lane_type = 'out_of_lane_transport' THEN coalesce(total_freight_usd, 0) ELSE 0 END), 0) yearly_oor_freight,
               round(sum(CASE WHEN lane_type = 'out_of_lane_transport' THEN coalesce(total_freight_usd, 0) ELSE 0 END)
                     / nullif(sum(coalesce(total_freight_usd, 0)), 0) * 100, 1) yearly_oor_pct
        FROM {GOLD}.lane_material_sot WHERE year_month BETWEEN '{lo}' AND '{m}'
    """)
    plants_f = ex.submit(query, f"""
        WITH fam AS (
            SELECT s.origin_plant AS plant_s4, mm.family, sum(coalesce(s.total_cases, 0)) AS cases
            FROM {GOLD}.lane_material_sot s
            JOIN {SILVER}.enterprise_material_master mm ON s.material_number = mm.material_number
            GROUP BY s.origin_plant, mm.family
        ),
        top_fam AS (
            SELECT plant_s4,
                   concat_ws(', ', slice(transform(array_sort(collect_list(struct(-cases AS neg, family))),
                                                   x -> x.family), 1, 3)) AS top_families
            FROM fam WHERE cases > 0 GROUP BY plant_s4
        )
        SELECT p.plant_s4, p.plant_name, p.plant_type, p.city, p.region, p.lat, p.lon,
               p.inbound_cases + p.outbound_cases AS throughput, f.top_families
        FROM {GOLD}.plant_stats p LEFT JOIN top_fam f ON p.plant_s4 = f.plant_s4
    """)
    planned, top_oor, kpis, trend, impact, yearly, yearly_freight, plants = (
        f.result() for f in (planned_f, top_oor_f, kpis_f, trend_f, impact_f,
                             yearly_f, yearly_freight_f, plants_f))
    ex.shutdown(wait=False)
    k = kpis[0] if kpis else {}
    k["oor_impact"] = impact[0]["oor_impact"] if impact else 0
    k["yearly_impact"] = yearly[0]["yearly_impact"] if yearly else 0
    k.update(yearly_freight[0] if yearly_freight else {})
    k["n_plants"] = len(plants)
    return {"month": month, "window_start": lo, "kpis": k, "trend": trend,
            "planned_lanes": planned, "top_oor": top_oor, "plants": plants}


@app.on_event("startup")
def prewarm():
    """Warm the exec-summary queries (and the warehouse) so the landing view's
    data is served from cache — pillars appear fast even for the first visitor."""
    def _warm():
        try:
            exec_summary()
        except Exception:
            pass  # best-effort: first request will populate the cache instead
    threading.Thread(target=_warm, daemon=True).start()
    if lakebase.enabled():
        try:
            lakebase.init_schema(w)
        except Exception as e:  # app still serves the map/Genie if Lakebase is unavailable
            print(f"lakebase init failed: {e}")


# ------------------------------------------------------------------ Genie

class GenieMsg(BaseModel):
    message: str
    conversation_id: Optional[str] = None


# --- Pre-recorded Genie answers (for demos): served instantly, no live call ---
_GENIE_CACHE_PATH = os.path.join(os.path.dirname(__file__), "genie_cache.json")


def _norm_q(s: str) -> str:
    """Normalize a question for cache matching: case/space/dash/trailing-punctuation insensitive."""
    s = (s or "").strip().lower()
    s = s.replace("—", "-").replace("–", "-")  # em/en dash -> hyphen
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ?.!")


def _load_genie_cache() -> dict:
    try:
        with open(_GENIE_CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError):
        return {}
    out: dict[str, dict] = {}
    for entry in data.get("entries", []):
        resp = entry.get("response", {})
        for q in entry.get("questions", []):
            out[_norm_q(q)] = resp
    return out


_GENIE_CACHE = _load_genie_cache()


@app.post("/api/genie/chat")
def genie_chat(body: GenieMsg):
    # Serve a pre-recorded answer instantly when the question matches the cache.
    cached = _GENIE_CACHE.get(_norm_q(body.message))
    if cached is not None:
        return {
            "conversation_id": body.conversation_id or "cached",
            "text": cached.get("text", ""),
            "columns": cached.get("columns", []),
            "rows": cached.get("rows", []),
            "query": cached.get("query"),
        }
    if not GENIE_SPACE_ID:
        raise HTTPException(status_code=503, detail="Genie space not configured")
    g = w().genie
    if body.conversation_id:
        msg = g.create_message_and_wait(GENIE_SPACE_ID, body.conversation_id, body.message)
    else:
        msg = g.start_conversation_and_wait(GENIE_SPACE_ID, body.message)
    out = {"conversation_id": msg.conversation_id, "text": "", "columns": [], "rows": [], "query": None}
    for att in (msg.attachments or []):
        if att.text and att.text.content:
            out["text"] += att.text.content + "\n"
        if att.query is not None:
            out["query"] = att.query.query
            if att.query.description:
                out["text"] += att.query.description + "\n"
            try:
                qr = g.get_message_attachment_query_result(
                    GENIE_SPACE_ID, msg.conversation_id, msg.message_id, att.attachment_id)
                sr = qr.statement_response
                if sr and sr.manifest and sr.manifest.schema:
                    out["columns"] = [c.name for c in sr.manifest.schema.columns]
                    out["rows"] = (sr.result.data_array or [])[:100] if sr.result else []
            except Exception as e:  # result fetch is best-effort
                out["text"] += f"(could not fetch query result: {e})\n"
    out["text"] = out["text"].strip()
    return out


# ------------------------------------------------------------------ Ops Console (Lakebase)

LANE_RE = re.compile(r"^[0-9]{4}-[0-9]{4}$")
Q = lakebase.SERVING_SCHEMA
OPS = lakebase.OPS_SCHEMA


def _require_lakebase():
    if not lakebase.enabled():
        raise HTTPException(status_code=503, detail="Lakebase resource not configured")


@app.get("/api/ops/queue")
def ops_queue(tier: Optional[str] = None, status: Optional[str] = None):
    """ML-ranked lane action queue (synced from UC gold) joined with each lane's latest planner decision."""
    _require_lakebase()
    where, params = [], []
    if tier:
        where.append("q.risk_tier = %s")
        params.append(tier.upper())
    if status == "open":
        where.append("a.decision IS NULL")
    elif status:
        where.append("a.decision = %s")
        params.append(status.upper())
    sql = f"""
        SELECT q.*, a.decision, a.note AS decision_note, a.decided_by, a.decided_at
        FROM {Q}.lane_action_queue q
        LEFT JOIN LATERAL (
            SELECT decision, note, decided_by, decided_at FROM {OPS}.planner_actions p
            WHERE p.directed_lane_id = q.directed_lane_id ORDER BY decided_at DESC LIMIT 1) a ON TRUE
        {'WHERE ' + ' AND '.join(where) if where else ''}
        ORDER BY q.priority_rank"""
    with lakebase.cursor(w) as cur:
        cur.execute(sql, params)
        return {"rows": cur.fetchall()}


@app.get("/api/ops/summary")
def ops_summary():
    _require_lakebase()
    with lakebase.cursor(w) as cur:
        cur.execute(f"""
            WITH latest AS (
                SELECT DISTINCT ON (directed_lane_id) directed_lane_id, decision
                FROM {OPS}.planner_actions ORDER BY directed_lane_id, decided_at DESC)
            SELECT count(*) AS lanes,
                   count(*) FILTER (WHERE q.risk_tier = 'HIGH') AS high_risk_lanes,
                   round(sum(q.expected_monthly_leakage_usd)::numeric, 0) AS queue_monthly_leakage_usd,
                   round(sum(q.realized_leakage_usd)::numeric, 0) AS queue_realized_leakage_usd,
                   count(l.decision) AS decided,
                   round(coalesce(sum(q.expected_monthly_leakage_usd) FILTER (WHERE l.decision = 'APPROVED'), 0)::numeric, 0)
                       AS approved_monthly_savings_usd,
                   max(q.window_end) AS window_end, max(q.generated_at) AS generated_at
            FROM {Q}.lane_action_queue q LEFT JOIN latest l USING (directed_lane_id)""")
        return cur.fetchone()


class OpsDecision(BaseModel):
    directed_lane_id: str
    decision: str
    note: Optional[str] = None


@app.post("/api/ops/decision")
def ops_decision(body: OpsDecision, request: Request):
    """Persist a planner decision (approve / reject / snooze) as an OLTP write in Lakebase."""
    _require_lakebase()
    decision = body.decision.upper()
    if decision not in ("APPROVED", "REJECTED", "SNOOZED") or not LANE_RE.match(body.directed_lane_id):
        raise HTTPException(status_code=400, detail="invalid decision or lane id")
    user = request.headers.get("X-Forwarded-Email") or request.headers.get("X-Forwarded-User") or "unknown"
    with lakebase.cursor(w) as cur:
        cur.execute(f"""
            INSERT INTO {OPS}.planner_actions
                (directed_lane_id, decision, action_type, note, expected_monthly_savings_usd, decided_by)
            SELECT %s, %s, q.action_type, %s, q.expected_monthly_leakage_usd, %s
            FROM {Q}.lane_action_queue q WHERE q.directed_lane_id = %s
            RETURNING *""", (body.directed_lane_id, decision, (body.note or "")[:500], user, body.directed_lane_id))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="lane not in action queue")
    return row


@app.get("/api/ops/decisions")
def ops_decisions(limit: int = 50):
    _require_lakebase()
    with lakebase.cursor(w) as cur:
        cur.execute(f"SELECT * FROM {OPS}.planner_actions ORDER BY decided_at DESC LIMIT %s", (min(limit, 500),))
        return {"rows": cur.fetchall()}


@app.get("/api/ops/health")
def ops_health():
    if not lakebase.enabled():
        return {"lakebase": "not configured"}
    with lakebase.cursor(w) as cur:
        cur.execute(f"SELECT current_user AS pg_user, version() AS pg_version, "
                    f"(SELECT count(*) FROM {Q}.lane_action_queue) AS queue_rows, "
                    f"(SELECT count(*) FROM {OPS}.planner_actions) AS decisions")
        return {"lakebase": "ok", **cur.fetchone()}


# ------------------------------------------------------------------ static frontend

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/ops")
    def ops_console():
        return FileResponse(os.path.join(STATIC_DIR, "ops.html"), headers={"Cache-Control": "no-cache, must-revalidate"})

    @app.get("/")
    def index():
        # no-cache so browsers always pick up the latest hashed bundle after a deploy
        return FileResponse(os.path.join(STATIC_DIR, "index.html"),
                            headers={"Cache-Control": "no-cache, must-revalidate"})
