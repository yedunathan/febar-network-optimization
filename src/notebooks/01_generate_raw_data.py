# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Generate raw source extracts (synthetic)
# MAGIC **Customer problem:** *Northstar Frozen Foods* (fictional North American frozen bakery & foodservice
# MAGIC manufacturer, ~55 nodes, ~2,100 SKUs) leaks freight spend on **out-of-route (OOR) shipments** — loads that move on a
# MAGIC lane the MRP plan never intended (DC → wrong DC, plant → non-adjacent fulfillment node). Finance sees the cost
# MAGIC weeks later in GL; logistics never sees which lane/SKU caused it.
# MAGIC
# MAGIC This notebook fabricates PRD-scale **synthetic** extracts of the three source systems involved and drops them as
# MAGIC parquet files into a Unity Catalog **landing volume**, where the Lakeflow pipeline (`src/pipeline`) ingests them
# MAGIC with Auto Loader. No customer data is used — everything is generated from `numpy` seed 42.
# MAGIC
# MAGIC | Source system | Extracts |
# MAGIC |---|---|
# MAGIC | ERP (S/4-style) | plant master, ECC→S4 plant cross-reference, material master, GL sales postings, monthly inventory |
# MAGIC | MRP / supply planning | monthly planned route legs (procurement direction), multi-hop supply paths |
# MAGIC | TMS (3PL freight platform) | loads, stops, line items, line-item detail, freight invoices, contract lane rates |
# MAGIC | Reference | FX rates, private-fleet shuttle lanes, plant coordinates |
# MAGIC
# MAGIC Deliberate source-system "messiness" the pipeline must clean up:
# MAGIC - ~30% of TMS stops carry **legacy ECC plant codes** instead of S4 codes (needs cross-reference mapping)
# MAGIC - ~40% of TMS line items have **leading zeros stripped** from material numbers
# MAGIC - Canadian-origin freight is invoiced in **CAD** (needs FX conversion)
# MAGIC - ~3% of line items are **non-product materials** (racks/pallets/dunnage) to be excluded
# MAGIC - GL `posting_period` is a **3-char string** (`'004'`) that must be normalised to a month
# MAGIC - A handful of **self-loop** loads (origin == destination)
# MAGIC - ~12% of material-months contain **out-of-route** moves (the business problem), 60% of which cost more than plan

# COMMAND ----------

dbutils.widgets.text("catalog", "cpg_demos")
dbutils.widgets.text("raw_schema", "netopt_raw")
dbutils.widgets.text("volume", "landing")
CATALOG = dbutils.widgets.get("catalog")
RAW_SCHEMA = dbutils.widgets.get("raw_schema")
VOLUME = dbutils.widgets.get("volume")
LANDING = f"/Volumes/{CATALOG}/{RAW_SCHEMA}/{VOLUME}"

import os
import shutil
from math import radians, sin, cos, asin, sqrt

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

MONTHS = pd.period_range("2025-01", "2026-04", freq="M")
MONTH_STRS = [str(m) for m in MONTHS]  # 'YYYY-MM'
print(f"landing zone: {LANDING}  months: {MONTH_STRS[0]} .. {MONTH_STRS[-1]} ({len(MONTH_STRS)})")

# COMMAND ----------
# MAGIC %md ## 1. Network nodes (55) — plant master, coordinates, ECC↔S4 cross-reference

# COMMAND ----------

PLANTS = [
    # s4, name, type, city, region, country, lat, lon
    ("2501", "Rochester Plant", "MFG", "Rochester", "NY", "US", 43.1566, -77.6088),
    ("2502", "Dayton Plant", "MFG", "Dayton", "OH", "US", 39.7589, -84.1916),
    ("2503", "McAllen Plant", "MFG", "McAllen", "TX", "US", 26.2034, -98.2300),
    ("2504", "Jackson Plant", "MFG", "Jackson", "TN", "US", 35.6145, -88.8139),
    ("2505", "Harrisonburg Plant", "MFG", "Harrisonburg", "VA", "US", 38.4496, -78.8689),
    ("2506", "Chattanooga Plant", "MFG", "Chattanooga", "TN", "US", 35.0456, -85.3097),
    ("2507", "Joliet Plant", "MFG", "Joliet", "IL", "US", 41.5250, -88.0817),
    ("2508", "Drummondville Plant", "MFG", "Drummondville", "QC", "CA", 45.8838, -72.4843),
    ("2540", "Atlanta DC", "INT_DC", "Atlanta", "GA", "US", 33.7490, -84.3880),
    ("2541", "Dallas DC", "INT_DC", "Dallas", "TX", "US", 32.7767, -96.7970),
    ("2542", "Bolingbrook DC", "INT_DC", "Bolingbrook", "IL", "US", 41.6986, -88.0684),
    ("2543", "Ontario DC", "INT_DC", "Ontario", "CA", "US", 34.0633, -117.6509),
    ("2544", "Kent DC", "INT_DC", "Kent", "WA", "US", 47.3809, -122.2348),
    ("2545", "Aurora DC", "INT_DC", "Aurora", "CO", "US", 39.7294, -104.8319),
    ("2546", "Orlando DC", "INT_DC", "Orlando", "FL", "US", 28.5383, -81.3792),
    ("2547", "Edison DC", "INT_DC", "Edison", "NJ", "US", 40.5187, -74.4121),
    ("2548", "Kansas City DC", "INT_DC", "Kansas City", "MO", "US", 39.0997, -94.5786),
    ("2549", "Phoenix DC", "INT_DC", "Phoenix", "AZ", "US", 33.4484, -112.0740),
    ("2550", "Charlotte DC", "INT_DC", "Charlotte", "NC", "US", 35.2271, -80.8431),
    ("2551", "Columbus DC", "INT_DC", "Columbus", "OH", "US", 39.9612, -82.9988),
    ("2552", "Eagan DC", "INT_DC", "Eagan", "MN", "US", 44.8041, -93.1669),
    ("2553", "Memphis DC", "INT_DC", "Memphis", "TN", "US", 35.1495, -90.0490),
    ("2554", "Las Vegas DC", "INT_DC", "Las Vegas", "NV", "US", 36.1699, -115.1398),
    ("2555", "Baltimore DC", "INT_DC", "Baltimore", "MD", "US", 39.2904, -76.6122),
    ("2560", "Houston Ext DC", "EXT_DC", "Houston", "TX", "US", 29.7604, -95.3698),
    ("2561", "Nashville Ext DC", "EXT_DC", "Nashville", "TN", "US", 36.1627, -86.7816),
    ("2562", "Indianapolis Ext DC", "EXT_DC", "Indianapolis", "IN", "US", 39.7684, -86.1581),
    ("2563", "Salt Lake Ext DC", "EXT_DC", "Salt Lake City", "UT", "US", 40.7608, -111.8910),
    ("2564", "Portland Ext DC", "EXT_DC", "Portland", "OR", "US", 45.5152, -122.6784),
    ("2565", "Mansfield Ext DC", "EXT_DC", "Mansfield", "MA", "US", 42.0334, -71.2189),
    ("2566", "Miami Ext DC", "EXT_DC", "Miami", "FL", "US", 25.7617, -80.1918),
    ("2567", "San Antonio Ext DC", "EXT_DC", "San Antonio", "TX", "US", 29.4241, -98.4936),
    ("2568", "Sacramento Ext DC", "EXT_DC", "Sacramento", "CA", "US", 38.5816, -121.4944),
    ("2569", "Pittsburgh Ext DC", "EXT_DC", "Pittsburgh", "PA", "US", 40.4406, -79.9959),
    ("2570", "St. Louis Ext DC", "EXT_DC", "St. Louis", "MO", "US", 38.6270, -90.1994),
    ("2571", "Jacksonville Ext DC", "EXT_DC", "Jacksonville", "FL", "US", 30.3322, -81.6557),
    ("2572", "Oklahoma City Ext DC", "EXT_DC", "Oklahoma City", "OK", "US", 35.4676, -97.5164),
    ("2573", "Louisville Ext DC", "EXT_DC", "Louisville", "KY", "US", 38.2527, -85.7585),
    ("2580", "Allentown VDC", "VDC", "Allentown", "PA", "US", 40.6023, -75.4714),
    ("2581", "Rockford VDC", "VDC", "Rockford", "IL", "US", 42.2711, -89.0940),
    ("2582", "Fresno VDC", "VDC", "Fresno", "CA", "US", 36.7378, -119.7871),
    ("2583", "Tampa VDC", "VDC", "Tampa", "FL", "US", 27.9506, -82.4572),
    ("2584", "Reno VDC", "VDC", "Reno", "NV", "US", 39.5296, -119.8138),
    ("2585", "Toronto VDC", "VDC", "Toronto", "ON", "CA", 43.6532, -79.3832),
    ("2586", "Spokane VDC", "VDC", "Spokane", "WA", "US", 47.6588, -117.4260),
    ("2590", "Grand Rapids Partner", "EXT_VP", "Grand Rapids", "MI", "US", 42.9634, -85.6681),
    ("2591", "Tulsa Partner", "EXT_VP", "Tulsa", "OK", "US", 36.1540, -95.9928),
    ("2592", "Boise Partner", "EXT_VP", "Boise", "ID", "US", 43.6150, -116.2023),
    ("2593", "Albany Partner", "EXT_VP", "Albany", "NY", "US", 42.6526, -73.7562),
    ("2594", "Richmond Partner", "EXT_VP", "Richmond", "VA", "US", 37.5407, -77.4360),
    ("2595", "Des Moines Partner", "EXT_VP", "Des Moines", "IA", "US", 41.5868, -93.6250),
    ("2596", "Dallas Outlet", "OUTLET", "Dallas", "TX", "US", 32.8140, -96.9489),
    ("2597", "Louisville Ecom", "ECOM", "Louisville", "KY", "US", 38.1740, -85.7365),
    ("2598", "Rochester Outlet", "OUTLET", "Rochester", "NY", "US", 43.1700, -77.6200),
    ("2599", "Rochester Corporate", "CORP", "Rochester", "NY", "US", 43.1610, -77.6110),
]

plants = pd.DataFrame(PLANTS, columns=["plant_s4", "plant_name", "plant_type", "city", "region", "country", "lat", "lon"])
plants["plant_ecc"] = (plants["plant_s4"].astype(int) - 1000).astype(str)
plants["currency"] = np.where(plants["country"] == "CA", "CAD", "USD")

PLANT_COORD = {r.plant_s4: (r.lat, r.lon) for r in plants.itertuples()}
S4_TO_ECC = dict(zip(plants["plant_s4"], plants["plant_ecc"]))

def haversine_miles(a, b):
    (la1, lo1), (la2, lo2) = PLANT_COORD[a], PLANT_COORD[b]
    la1, lo1, la2, lo2 = map(radians, [la1, lo1, la2, lo2])
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return max(2 * 3958.8 * asin(sqrt(h)), 25.0)  # floor for same-metro lanes

# ERP plant master (S4 field names)
t001w = plants.rename(columns={"plant_s4": "werks", "plant_name": "name1", "city": "ort01", "region": "regio", "country": "land1"})[
    ["werks", "name1", "ort01", "regio", "land1", "currency"]
].copy()
t001w["ekorg"] = "NS01"

plant_map = plants[["plant_ecc", "plant_s4", "plant_name"]].copy()
plant_coords = plants[["plant_s4", "plant_type", "lat", "lon"]].copy()

# COMMAND ----------
# MAGIC %md ## 2. Materials (~2,100 finished goods) — frozen bakery & foodservice portfolio

# COMMAND ----------

FAMILIES = [
    ("Frozen Bread Dough", ["White", "Wheat", "Sourdough", "Italian", "French", "Multigrain", "Rye"], 300),
    ("Sweet Dough", ["Cinnamon Roll", "Danish", "Croissant", "Brioche", "Sticky Bun"], 260),
    ("Pizza Crust", ["Thin", "Pan", "Rising", "Cauliflower", "Gluten Free", "Sheeted"], 280),
    ("Icing & Glaze", ["Buttercream", "Cream Cheese", "Fudge", "Whipped", "Donut Glaze"], 220),
    ("Toppings", ["Whipped Topping", "Whipped Icing Vanilla", "Whipped Icing Chocolate", "Dairy Topping", "Cocoa Whip"], 240),
    ("Cakes & Desserts", ["Layer Cake", "Sheet Cake", "Cheesecake", "Brownie", "Cupcake", "Tres Leches"], 300),
    ("Barquettes & Shells", ["Tart Shell", "Barquette", "Eclair Shell", "Cannoli Shell"], 150),
    ("Appetizers", ["Mozzarella Stick", "Jalapeno Popper", "Onion Ring", "Mac & Cheese Bite"], 180),
    ("Rolls & Biscuits", ["Yeast Roll", "Dinner Roll", "Buttermilk Biscuit", "Telera Roll", "Hawaiian Roll"], 170),
]

mat_rows = []
mat_num = 300000000
for fam, variants, count in FAMILIES:
    for i in range(count):
        v = variants[i % len(variants)]
        size = int(rng.choice([8, 12, 16, 20, 24, 32, 48, 64]))
        pack = int(rng.choice([6, 8, 12, 24, 36, 48]))
        mat_rows.append({
            "material_number": str(mat_num).zfill(18),
            "material_desc": f"{fam.upper()[:12]} {v.upper()} {size}OZ {pack}CT",
            "material_type": "ZFRT",
            "family": fam,
            "gross_weight_kg": round(float(rng.uniform(4, 22)), 2),
            "net_weight_kg": round(float(rng.uniform(3, 20)), 2),
            "cases_per_pallet": int(rng.choice([40, 56, 64, 72, 90, 120])),
            "shelf_life_days": int(rng.choice([180, 270, 365, 450, 540])),
            "base_uom": "CS",
            "status": "ACTIVE",
        })
        mat_num += int(rng.integers(3, 40))

materials = pd.DataFrame(mat_rows)
N_MAT = len(materials)
print(f"materials: {N_MAT}")

# non-product logistics materials (racks, dunnage) that sneak into TMS line items
nonprod = pd.DataFrame([
    {"material_number": str(900000000 + i).zfill(18), "material_desc": d, "material_type": "ZPKG",
     "family": "Logistics", "gross_weight_kg": 50.0, "net_weight_kg": 50.0, "cases_per_pallet": 1,
     "shelf_life_days": 9999, "base_uom": "EA", "status": "ACTIVE"}
    for i, d in enumerate(["RACK RETURNABLE STEEL", "PALLET POOL B GRADE", "DUNNAGE AIRBAG", "SLIP SHEET PLASTIC"])
])
materials_all = pd.concat([materials, nonprod], ignore_index=True)

# COMMAND ----------
# MAGIC %md ## 3. Planned network — route families per material

# COMMAND ----------

MFG = plants.loc[plants.plant_type == "MFG", "plant_s4"].tolist()
INT_DC = plants.loc[plants.plant_type == "INT_DC", "plant_s4"].tolist()
FULFILL = plants.loc[plants.plant_type.isin(["EXT_DC", "VDC", "EXT_VP"]), "plant_s4"].tolist()

# geographic adjacency: each MFG serves its 6 nearest INT DCs; each INT DC serves its 4 nearest fulfillment nodes
def nearest(src, candidates, k):
    return sorted(candidates, key=lambda c: haversine_miles(src, c))[:k]

MFG_DCS = {m: nearest(m, INT_DC, 6) for m in MFG}
DC_FULFILL = {d: nearest(d, FULFILL, 4) for d in INT_DC}

mat_weights = rng.dirichlet(np.ones(len(MFG)) * 2.0)
materials["home_mfg"] = rng.choice(MFG, size=N_MAT, p=mat_weights)
materials["volume_class"] = rng.choice(["A", "B", "C"], size=N_MAT, p=[0.2, 0.5, 0.3])
VOL_LAMBDA = {"A": 9.0, "B": 3.5, "C": 1.2}

# ~8% of materials are theoretical-only: planned routes but never shipped
materials["is_theoretical_only"] = rng.random(N_MAT) < 0.08

route_legs = {}   # material -> list[(origin, dest)]
route_paths = {}  # material -> list[path tuple]
for r in materials.itertuples():
    mfg = r.home_mfg
    n_dc = int(rng.integers(1, 4))
    dcs = list(rng.choice(MFG_DCS[mfg], size=min(n_dc, len(MFG_DCS[mfg])), replace=False))
    legs, paths = set(), []
    for dc in dcs:
        legs.add((mfg, dc))
        if rng.random() < 0.75:  # extend to fulfillment
            f = str(rng.choice(DC_FULFILL[dc]))
            legs.add((dc, f))
            if rng.random() < 0.15:  # 4-hop: fulfillment relays to a partner
                f2 = str(rng.choice([p for p in FULFILL if p != f]))
                legs.add((f, f2))
                paths.append((mfg, dc, f, f2))
            else:
                paths.append((mfg, dc, f))
        else:
            paths.append((mfg, dc))
    route_legs[r.material_number] = sorted(legs)
    route_paths[r.material_number] = paths

all_planned_lanes = sorted({l for legs in route_legs.values() for l in legs})
print(f"distinct planned directed lanes: {len(all_planned_lanes)}")

# COMMAND ----------
# MAGIC %md ## 4. MRP — monthly planned route-leg snapshots (procurement direction) + multi-hop supply paths

# COMMAND ----------

# Plan churn: each month ~5% of materials swap one DC; ~3% of material-months lose their plan rows entirely
mrp_rows = []
current_legs = {m: list(v) for m, v in route_legs.items()}
for mi, month in enumerate(MONTH_STRS):
    churn = rng.random(N_MAT) < (0.05 if mi > 0 else 0.0)
    dropped = rng.random(N_MAT) < 0.03
    for idx, r in enumerate(materials.itertuples()):
        m = r.material_number
        if churn[idx]:
            mfg = r.home_mfg
            dc_new = str(rng.choice(MFG_DCS[mfg]))
            legs = [l for l in current_legs[m] if l[0] != mfg][:2]
            legs.append((mfg, dc_new))
            if rng.random() < 0.6:
                legs.append((dc_new, str(rng.choice(DC_FULFILL[dc_new]))))
            current_legs[m] = sorted(set(legs))
        if dropped[idx]:
            continue
        for (o, d) in current_legs[m]:
            mrp_rows.append((month, m, d, o))  # PROCUREMENT direction: receiving_plant, supplying_plant

mrp = pd.DataFrame(mrp_rows, columns=["snapshot_month", "material_number", "receiving_plant", "supplying_plant"])
mrp["source_system"] = "S4_MRP"
print(f"mrp route legs: {len(mrp):,}")

spk_rows = []
for r in materials.itertuples():
    for pi, path in enumerate(route_paths[r.material_number]):
        spk_rows.append({
            "path_id": f"SP-{r.material_number[-7:]}-{pi}",
            "material_number": r.material_number,
            "path_plants": ">".join(path),
            "n_hops": len(path) - 1,
            "valid_from": "2025-01-01",
            "valid_to": "2026-12-31",
        })
spk = pd.DataFrame(spk_rows)
print(f"supply paths: {len(spk):,}")

# COMMAND ----------
# MAGIC %md ## 5. TMS — shipment events → loads / stops / line items / freight invoices / contract rates

# COMMAND ----------

CARRIERS = ["BLUELINE", "IRONHORSE", "REDTAIL", "SUMMIT", "PRAIRIE", "COASTAL",
            "KEYSTONE", "FRONTIER", "PINNACLE", "MERIDIAN", "ATLAS", "HARBOR"]
lane_rate = {l: float(rng.normal(2.6, 0.35)) for l in all_planned_lanes}
PLANT_CURR = dict(zip(plants.plant_s4, plants.currency))
PLANT_CITY = dict(zip(plants.plant_s4, plants.city))

events = []  # (month, material, origin, dest, cases, oor_flag, cost_mult)
current_legs = {m: list(v) for m, v in route_legs.items()}
theo_only = dict(zip(materials.material_number, materials.is_theoretical_only))
lam = materials.volume_class.map(VOL_LAMBDA).values

for mi, month in enumerate(MONTH_STRS):
    churn = rng.random(N_MAT) < (0.05 if mi > 0 else 0.0)
    n_ship = rng.poisson(lam)
    oor_hit = rng.random(N_MAT) < 0.12
    seasonal = 1.0 + 0.25 * np.sin(2 * np.pi * (mi % 12) / 12.0)
    for idx, r in enumerate(materials.itertuples()):
        m = r.material_number
        if churn[idx]:
            mfg = r.home_mfg
            dc_new = str(rng.choice(MFG_DCS[mfg]))
            legs = [l for l in current_legs[m] if l[0] != mfg][:2]
            legs.append((mfg, dc_new))
            if rng.random() < 0.6:
                legs.append((dc_new, str(rng.choice(DC_FULFILL[dc_new]))))
            current_legs[m] = sorted(set(legs))
        if theo_only[m]:
            continue
        k = int(round(n_ship[idx] * seasonal))
        legs = current_legs[m]
        for _ in range(k):
            o, d = legs[int(rng.integers(0, len(legs)))]
            events.append((month, m, o, d, int(rng.integers(80, 900)), False, 1.0))
        if oor_hit[idx]:
            for _ in range(int(rng.integers(1, 4))):
                o = legs[int(rng.integers(0, len(legs)))][0]
                d = str(rng.choice([p for p in INT_DC + FULFILL if p != o and (o, p) not in legs]))
                mult = float(rng.uniform(1.3, 2.2)) if rng.random() < 0.6 else float(rng.uniform(0.55, 0.9))
                events.append((month, m, o, d, int(rng.integers(60, 500)), True, mult))

# ~30 self-loop anomaly events
for _ in range(30):
    m = materials.material_number.iloc[int(rng.integers(0, N_MAT))]
    p = str(rng.choice(INT_DC))
    events.append((MONTH_STRS[int(rng.integers(0, len(MONTH_STRS)))], m, p, p, int(rng.integers(40, 200)), True, 1.5))

ev = pd.DataFrame(events, columns=["month", "material_number", "origin", "dest", "cases", "is_oor", "cost_mult"])
print(f"shipment events: {len(ev):,}  (of which out-of-route: {int(ev.is_oor.sum()):,})")

# group events into loads: same (lane, month) chunks of 1-3 line items (co-loading)
ev = ev.sample(frac=1.0, random_state=7).sort_values(["month", "origin", "dest"], kind="stable").reset_index(drop=True)
grp = ev.groupby(["month", "origin", "dest"], sort=False)
load_rows, stop_rows, li_rows, lid_rows, fr_rows = [], [], [], [], []
load_seq = 1000000
li_seq = 5000000

for (month, o, d), g in grp:
    idxs = g.index.tolist()
    i = 0
    while i < len(idxs):
        chunk = idxs[i: i + int(rng.integers(1, 4))]
        i += len(chunk)
        load_seq += 1
        load_id = f"LD{load_seq}"
        day = int(rng.integers(1, 28))
        ship_date = f"{month}-{day:02d}"
        carrier = CARRIERS[int(rng.integers(0, len(CARRIERS)))]
        mode = str(rng.choice(["TL", "LTL", "INTERMODAL"], p=[0.72, 0.2, 0.08]))
        dist = haversine_miles(o, d)
        rate = lane_rate.get((o, d), float(rng.normal(2.9, 0.5)))
        mult = float(ev.loc[chunk, "cost_mult"].mean())
        linehaul = dist * max(rate, 1.2) * mult
        fuel = linehaul * 0.18
        curr = "CAD" if PLANT_CURR[o] == "CAD" else "USD"
        fx = 1.38 if curr == "CAD" else 1.0  # invoiced in local currency
        load_rows.append((load_id, carrier, mode, ship_date, "DELIVERED"))
        # stops — ~30% emitted with legacy ECC plant codes
        for seq, (plant, st) in enumerate([(o, "PU"), (d, "DO")], start=1):
            code = S4_TO_ECC[plant] if rng.random() < 0.30 else plant
            stop_rows.append((f"{load_id}-S{seq}", load_id, seq, code, PLANT_CITY[plant], st))
        for ci in chunk:
            li_seq += 1
            e = ev.loc[ci]
            matno = e.material_number
            if rng.random() < 0.40:
                matno = matno.lstrip("0")  # leading zeros stripped by the TMS
            li_rows.append((f"LI{li_seq}", load_id, matno, int(e.cases), round(float(e.cases) * rng.uniform(6, 18), 1)))
            lid_rows.append((f"LI{li_seq}", int(e.cases), int(round(e.cases * rng.uniform(0.85, 1.0))), "FG"))
        # occasional rack/packaging line item (excluded by pipeline)
        if rng.random() < 0.03:
            li_seq += 1
            nm = nonprod.material_number.iloc[int(rng.integers(0, len(nonprod)))]
            li_rows.append((f"LI{li_seq}", load_id, nm.lstrip("0"), 1, 45.0))
            lid_rows.append((f"LI{li_seq}", 1, 1, "PKG"))
        fr_rows.append((load_id, round(linehaul * fx, 2), round(fuel * fx, 2), curr))

tms_load = pd.DataFrame(load_rows, columns=["load_id", "carrier", "transport_mode", "ship_date", "status"])
tms_stop = pd.DataFrame(stop_rows, columns=["stop_id", "load_id", "stop_seq", "plant_code", "city", "stop_type"])
tms_lineitem = pd.DataFrame(li_rows, columns=["lineitem_id", "load_id", "material_number", "cases", "weight_kg"])
tms_lineitem_detail = pd.DataFrame(lid_rows, columns=["lineitem_id", "total_cases", "allocated_cases", "material_category"])
tms_freight = pd.DataFrame(fr_rows, columns=["load_id", "linehaul_cost", "fuel_surcharge", "currency"])
tms_rate = pd.DataFrame(
    [(f"{o}-{d}", c, round(lane_rate[(o, d)], 3), f"CTR-{i:05d}")
     for i, (o, d) in enumerate(all_planned_lanes) for c in rng.choice(CARRIERS, 2, replace=False)],
    columns=["lane_id", "carrier", "rate_per_mile", "contract_id"],
)
print(f"loads={len(tms_load):,} stops={len(tms_stop):,} lineitems={len(tms_lineitem):,} "
      f"freight={len(tms_freight):,} rates={len(tms_rate):,}")

# COMMAND ----------
# MAGIC %md ## 6. ERP GL sales, inventory, FX, private-fleet shuttle lanes

# COMMAND ----------

# GL: sales recorded at fulfillment endpoints (posting_period is a 3-char string, e.g. '004')
gl_rows = []
doc = 4700000
for r in materials.itertuples():
    if r.is_theoretical_only:
        continue
    endpoints = sorted({d for (_, d) in route_legs[r.material_number]})
    sell_plants = endpoints[:3] if endpoints else [r.home_mfg]
    base = {"A": 220000, "B": 80000, "C": 20000}[r.volume_class]
    for mi, month in enumerate(MONTH_STRS):
        yy, mm = month.split("-")
        for p in sell_plants:
            if rng.random() < 0.25:
                continue
            doc += 1
            amt = base * float(rng.uniform(0.5, 1.5)) * (1.0 + 0.25 * np.sin(2 * np.pi * (mi % 12) / 12.0))
            gl_rows.append((f"DOC{doc}", "1000", "0000400000", yy, f"{int(mm):03d}", p,
                            r.material_number, round(amt, 2), int(amt / rng.uniform(40, 120))))
gl = pd.DataFrame(gl_rows, columns=["document_id", "company_code", "gl_account", "fiscal_year",
                                    "posting_period", "plant", "material_number", "amount_usd", "quantity_cases"])
print(f"gl rows: {len(gl):,}")

inv_rows = []
for r in materials.itertuples():
    net_plants = sorted({p for leg in route_legs[r.material_number] for p in leg})
    for month in MONTH_STRS:
        for p in net_plants:
            if rng.random() < 0.3:
                continue
            inv_rows.append((month, p, r.material_number,
                             int(rng.integers(50, 5000)), int(rng.integers(40, 400))))
inv = pd.DataFrame(inv_rows, columns=["year_month", "plant", "material_number", "qty_on_hand_cases", "safety_stock_cases"])
print(f"inventory rows: {len(inv):,}")

fx = pd.DataFrame([(m, "CAD", "USD", round(float(rng.uniform(0.715, 0.755)), 4)) for m in MONTH_STRS],
                  columns=["year_month", "from_currency", "to_currency", "rate"])

shuttle = pd.DataFrame([
    ("2501", "2598", "ALL", 1200, "Private fleet shuttle - Rochester plant to outlet"),
    ("2501", "2593", "ALL", 800, "Private fleet shuttle - Rochester to Albany partner"),
    ("2507", "2581", "ALL", 950, "Private fleet shuttle - Joliet to Rockford VDC"),
    ("2541", "2596", "ALL", 600, "Private fleet shuttle - Dallas DC to outlet"),
    ("2508", "2585", "ALL", 700, "Private fleet shuttle - Drummondville to Toronto VDC"),
], columns=["origin_plant", "dest_plant", "material_pattern", "monthly_cases", "note"])

# COMMAND ----------
# MAGIC %md ## 7. Land raw extracts as parquet in the UC volume (one folder per source feed)

# COMMAND ----------

FEEDS = {
    "erp_plant_master": t001w,
    "erp_plant_xref": plant_map,
    "ref_plant_coordinates": plant_coords,
    "erp_material_master": materials_all.drop(columns=["home_mfg", "volume_class", "is_theoretical_only"], errors="ignore"),
    "mrp_route_legs": mrp,
    "mrp_supply_paths": spk,
    "tms_load": tms_load,
    "tms_stop": tms_stop,
    "tms_lineitem": tms_lineitem,
    "tms_lineitem_detail": tms_lineitem_detail,
    "tms_freight": tms_freight,
    "tms_rate": tms_rate,
    "erp_gl_line_items": gl,
    "erp_inventory_monthly": inv,
    "ref_exchange_rates": fx,
    "ref_shuttle_lanes": shuttle,
}

# clean landing zone so the (full-refresh) pipeline run ingests exactly this generation
for feed in FEEDS:
    shutil.rmtree(f"{LANDING}/{feed}", ignore_errors=True)

total = 0
for feed, pdf in FEEDS.items():
    os.makedirs(f"{LANDING}/{feed}", exist_ok=True)
    pdf.to_parquet(f"{LANDING}/{feed}/{feed}_extract.parquet", index=False)
    total += len(pdf)
    print(f"landed {feed:<24} {len(pdf):>9,} rows -> {LANDING}/{feed}/")
print(f"TOTAL raw rows landed: {total:,}")
