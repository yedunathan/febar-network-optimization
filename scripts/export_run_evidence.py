#!/usr/bin/env python3
"""Export a netopt-end-to-end job run as text-readable execution evidence.

For every notebook task: pulls the executed notebook (with outputs) via `jobs export-run`, then writes
  evidence/notebook_runs/<task>.ipynb   (Jupyter notebook, outputs embedded as text)
  evidence/notebook_runs/<task>.md      (same content as plain Markdown, easy to read on GitHub)
For pipeline tasks: writes the Lakeflow update's event log (flows, row counts, expectations) to
  evidence/pipeline/<task>_events.md
And a run summary evidence/job_run_summary.md.

Usage: python scripts/export_run_evidence.py --run-id <job_run_id> --profile <profile>
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
EVID = os.path.join(ROOT, "evidence")
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# session-policy / token-ish noise that Spark Connect prints; not useful as evidence
NOISE = re.compile(r'^\{"ts": .*"logger": "pyspark\.sql\.connect\.logging".*$', re.M)


def cli(args, profile):
    out = subprocess.run(["databricks", *args, "--profile", profile, "-o", "json"], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"CLI failed: {' '.join(args)}\n{out.stderr}")
    return json.loads(out.stdout)


def clean(text: str) -> str:
    return NOISE.sub("", ANSI.sub("", text or "")).strip("\n")


def fmt_table(res) -> str:
    cols = [c.get("name", "") for c in res.get("schema", [])]
    rows = res.get("data", [])
    cells = [cols] + [["" if v is None else str(v) for v in r] for r in rows]
    width = [max(len(r[i]) for r in cells) for i in range(len(cols))] if cols else []
    lines = [" | ".join(c.ljust(width[i]) for i, c in enumerate(r)) for r in cells]
    if lines:
        lines.insert(1, "-+-".join("-" * w for w in width))
    trunc = " (truncated)" if res.get("truncated") else ""
    return "\n".join(lines) + f"\n[{len(rows)} rows{trunc}]"


def outputs_of(cmd) -> list[str]:
    res = cmd.get("results") or {}
    parts = res.get("data") if res.get("type") == "listResults" else ([res] if res else [])
    texts = []
    for p in parts:
        t, data = p.get("type"), p.get("data")
        if t == "table":
            texts.append(fmt_table(p))
        elif t in ("ansi", "text", "raw"):
            texts.append(clean(data if isinstance(data, str) else json.dumps(data)))
        elif t == "mimeBundle" and isinstance(data, dict) and "application/vnd.jupyter.widget-view+json" not in data:
            texts.append(clean(data.get("text/plain", "")))
        elif t == "html" and isinstance(data, str) and "<table" not in data:
            texts.append(clean(re.sub(r"<[^>]+>", "", data)))
    if cmd.get("error"):
        texts.append("ERROR:\n" + clean(cmd.get("error") if isinstance(cmd.get("error"), str) else json.dumps(cmd["error"])))
    return [t for t in texts if t.strip()]


def export_notebook(task_key: str, run_id: int, profile: str, outdir: str, header: str):
    d = cli(["jobs", "export-run", str(run_id), "--views-to-export", "CODE"], profile)
    html = d["views"][0]["content"]
    raw = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html).group(1)
    nb = json.loads(urllib.parse.unquote(base64.b64decode(raw).decode()))
    cells, md = [], [f"# Executed notebook: `{task_key}`\n", header, ""]
    for c in sorted(nb["commands"], key=lambda c: c.get("position", 0)):
        src = c.get("command") or ""
        if src.lstrip().startswith("%md"):
            body = re.sub(r"^\s*%md ?", "", src, count=1)
            cells.append({"cell_type": "markdown", "metadata": {}, "source": body})
            md += [body, ""]
            continue
        outs = outputs_of(c)
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "source": src,
                      "outputs": [{"output_type": "stream", "name": "stdout", "text": o + "\n"} for o in outs]})
        md += ["```python", src.rstrip(), "```", ""]
        for o in outs:
            md += ["**Output:**", "```text", o, "```", ""]
    ipynb = {"nbformat": 4, "nbformat_minor": 5, "cells": cells,
             "metadata": {"language_info": {"name": "python"}, "databricks_task": task_key, "databricks_run_id": run_id}}
    with open(os.path.join(outdir, f"{task_key}.ipynb"), "w") as f:
        json.dump(ipynb, f, indent=1)
    with open(os.path.join(outdir, f"{task_key}.md"), "w") as f:
        f.write("\n".join(md))


def export_pipeline(task_key: str, task: dict, profile: str, outdir: str, header: str):
    pid = task["pipeline_task"]["pipeline_id"]
    upd = cli(["pipelines", "list-updates", pid, "--max-results", "5"], profile).get("updates", [])
    events = cli(["pipelines", "list-pipeline-events", pid, "--max-results", "250"], profile)
    lines = [f"# Lakeflow pipeline run: `{task_key}`\n", header, "", f"Pipeline id: `{pid}`", "", "## Recent updates", "",
             "| update_id | state | full_refresh | created |", "|---|---|---|---|"]
    for u in upd:
        ts = datetime.fromtimestamp(u.get("creation_time", 0) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        lines.append(f"| {u['update_id']} | {u.get('state')} | {u.get('full_refresh')} | {ts} |")
    latest = upd[0]["update_id"] if upd else None
    lines += ["", f"## Event log for update `{latest}` (oldest first)", "", "```text"]
    rows = [e for e in events if (e.get("origin") or {}).get("update_id") == latest]
    for e in reversed(rows):
        msg = e.get("message", "")
        dq = ((e.get("details") or {}).get("flow_progress") or {}).get("data_quality") or {}
        metrics = ((e.get("details") or {}).get("flow_progress") or {}).get("metrics") or {}
        extra = ""
        if metrics.get("num_output_rows") is not None:
            extra += f"  output_rows={metrics['num_output_rows']}"
        if dq.get("dropped_records"):
            extra += f"  dropped_by_expectations={dq['dropped_records']}"
        for x in dq.get("expectations", []) or []:
            extra += f"\n      expectation {x.get('name')}: passed={x.get('passed_records')} failed={x.get('failed_records')}"
        lines.append(f"{e.get('timestamp')}  {e.get('event_type'):<16} {msg}{extra}")
    lines.append("```")
    with open(os.path.join(outdir, f"{task_key}_events.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True, type=int)
    ap.add_argument("--profile", required=True)
    a = ap.parse_args()
    run = cli(["jobs", "get-run", str(a.run_id)], a.profile)
    os.makedirs(os.path.join(EVID, "notebook_runs"), exist_ok=True)
    os.makedirs(os.path.join(EVID, "pipeline"), exist_ok=True)
    summary = [f"# Job run summary — `{run.get('run_name')}`", "",
               f"- Job run id: `{a.run_id}` (job `{run.get('job_id')}`)",
               f"- Started: {datetime.fromtimestamp(run['start_time'] / 1000, timezone.utc):%Y-%m-%d %H:%M:%SZ}",
               f"- Result: **{run['state'].get('result_state')}**", "",
               "| task | result | duration (s) | evidence |", "|---|---|---|---|"]
    tasks = sorted(run["tasks"], key=lambda t: t.get("start_time", 0))
    for t in tasks:
        key, st = t["task_key"], t["state"]
        dur = round((t.get("end_time", 0) - t.get("start_time", 0)) / 1000) if t.get("end_time") else ""
        header = f"_Task run `{t['run_id']}` of job run `{a.run_id}` · result **{st.get('result_state')}** · {dur}s_"
        if "notebook_task" in t and st.get("result_state") in ("SUCCESS", "FAILED"):
            export_notebook(key, t["run_id"], a.profile, os.path.join(EVID, "notebook_runs"), header)
            ev = f"[notebook_runs/{key}.md](notebook_runs/{key}.md)"
        elif "pipeline_task" in t:
            export_pipeline(key, t, a.profile, os.path.join(EVID, "pipeline"), header)
            ev = f"[pipeline/{key}_events.md](pipeline/{key}_events.md)"
        else:
            ev = ""
        summary.append(f"| {key} | {st.get('result_state')} | {dur} | {ev} |")
        print(f"{key:<32} {st.get('result_state')}")
    with open(os.path.join(EVID, "job_run_summary.md"), "w") as f:
        f.write("\n".join(summary) + "\n")


if __name__ == "__main__":
    main()
