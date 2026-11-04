#!/usr/bin/env python3
"""Exercise the deployed Databricks App end to end and save its real API responses to evidence/app/.

Calls the same endpoints the UI calls: map bootstrap + exec summary (SQL warehouse over gold), Genie chat,
and the Ops Console (Lakebase: read synced ML/GenAI queue, write a planner decision, read it back).
Usage: python scripts/capture_app_evidence.py --profile <profile> --app northstar-network-opt
"""
import argparse
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timezone

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence", "app")


def cli(args, profile):
    return json.loads(subprocess.run(["databricks", *args, "--profile", profile, "-o", "json"],
                                     capture_output=True, text=True, check=True).stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--app", default="northstar-network-opt")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    url = cli(["apps", "get", a.app], a.profile)["url"]
    token = cli(["auth", "token"], a.profile)["access_token"]

    def call(method, path, body=None):
        req = urllib.request.Request(url + path, method=method, data=json.dumps(body).encode() if body else None,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read())
            return r.status, round(1000 * (time.perf_counter() - t0)), data

    log = [f"# App API evidence — `{a.app}`", "", f"- URL: {url}",
           f"- Captured: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} (calls made with the presenter's OAuth token)", ""]

    def record(name, method, path, body=None, trim=None):
        status, ms, data = call(method, path, body)
        shown = trim(data) if trim else data
        with open(os.path.join(OUT, f"{name}.json"), "w") as f:
            json.dump(shown, f, indent=1, default=str)
        log.extend([f"## `{method} {path}` → HTTP {status} in {ms} ms", ""])
        if body:
            log.extend(["Request body:", "```json", json.dumps(body, indent=1), "```"])
        log.extend(["```json", json.dumps(shown, indent=1, default=str)[:6000], "```", ""])
        print(f"{method} {path} -> {status} ({ms} ms)")
        return data

    record("01_bootstrap", "GET", "/api/bootstrap",
           trim=lambda d: {"months": d["months"], "n_plants": len(d["plants"]), "plants_sample": d["plants"][:3],
                           **{k: (v if not isinstance(v, list) else f"{len(v)} items") for k, v in d.items() if k not in ("months", "plants")}})
    record("02_exec_summary", "GET", "/api/exec_summary",
           trim=lambda d: {k: (v[:5] if isinstance(v, list) else v) for k, v in d.items()})
    record("03_drilldown_counts", "GET", "/api/drilldown_counts?start=2026-01&end=2026-04")
    record("04_genie_chat", "POST", "/api/genie/chat",
           {"message": "Which 5 lanes have the highest expected monthly leakage according to the ML model?"})
    record("05_ops_health", "GET", "/api/ops/health")
    record("06_ops_summary_before", "GET", "/api/ops/summary")
    q = record("07_ops_queue_high", "GET", "/api/ops/queue?tier=HIGH", trim=lambda d: {"n": len(d["rows"]), "rows": d["rows"][:5]})
    lane = q["rows"][0]["directed_lane_id"]
    record("08_ops_decision_write", "POST", "/api/ops/decision",
           {"directed_lane_id": lane, "decision": "APPROVED",
            "note": "Evidence capture: approved GenAI recommendation for the top HIGH-risk lane"})
    record("09_ops_decisions_readback", "GET", "/api/ops/decisions?limit=5")
    record("10_ops_summary_after", "GET", "/api/ops/summary")
    with open(os.path.join(OUT, "README.md"), "w") as f:
        f.write("\n".join(log))


if __name__ == "__main__":
    main()
