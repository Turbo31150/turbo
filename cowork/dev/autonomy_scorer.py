#!/usr/bin/env python3
"""autonomy_scorer.py — Calculate global JARVIS autonomy score (0-100).

Aggregates five weighted dimensions: services uptime, scripts passing,
cluster nodes online, scheduled tasks active, cycle success rate.
Saves score to etoile.db memories table.
CLI:
    --once    : compute score once and output JSON
    --history : show last 10 scores from DB

Stdlib-only (sqlite3, json, argparse, subprocess, urllib).
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import datetime
from _paths import ETOILE_DB

CLUSTER_NODES = [
    ("M1", "http://127.0.0.1:1234/api/v1/models"),
    ("M2", "http://192.168.1.26:1234/api/v1/models"),
    ("M3", "http://192.168.1.113:1234/api/v1/models"),
    ("OL1", "http://127.0.0.1:11434/api/tags"),
]
WEIGHTS = {"services": 25, "scripts": 20, "cluster": 25, "tasks": 15, "cycles": 15}


def get_conn():
    conn = sqlite3.connect(str(ETOILE_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def check_node(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def score_cluster() -> tuple:
    res = {n: check_node(u) for n, u in CLUSTER_NODES}
    pct = sum(res.values()) / len(CLUSTER_NODES) * 100 if CLUSTER_NODES else 0
    return round(pct, 1), res


def score_services() -> tuple:
    targets = ["python", "node", "ollama"]
    try:
        out = subprocess.check_output(["tasklist", "/FO", "CSV", "/NH"],
                                      text=True, timeout=5, stderr=subprocess.DEVNULL).lower()
        found = {s: s in out for s in targets}
    except Exception:
        found = {s: False for s in targets}
    return round(sum(found.values()) / len(targets) * 100, 1), found


def score_scripts(conn) -> tuple:
    rows = conn.execute(
        "SELECT success FROM cowork_execution_log ORDER BY id DESC LIMIT 100").fetchall()
    if not rows:
        return 50.0, {"total": 0, "note": "no data"}
    ok = sum(1 for r in rows if r["success"])
    return round(ok / len(rows) * 100, 1), {"total": len(rows), "success": ok}


def score_tasks() -> tuple:
    try:
        out = subprocess.check_output(["schtasks", "/Query", "/FO", "CSV", "/NH"],
                                      text=True, timeout=10, stderr=subprocess.DEVNULL)
        lines = [l for l in out.strip().splitlines() if l.strip()]
        ready = sum(1 for l in lines if "Ready" in l or "Running" in l)
        return round(ready / len(lines) * 100, 1) if lines else 50.0, \
               {"total": len(lines), "ready": ready}
    except Exception as e:
        return 50.0, {"error": str(e)}


def score_cycles(conn) -> tuple:
    rows = conn.execute(
        "SELECT tasks_total, tasks_ok FROM cluster_pipeline_cycles "
        "ORDER BY rowid DESC LIMIT 50").fetchall()
    if not rows:
        return 50.0, {"total": 0, "note": "no data"}
    t_all = sum(r["tasks_total"] for r in rows if r["tasks_total"])
    t_ok = sum(r["tasks_ok"] for r in rows if r["tasks_ok"])
    pct = (t_ok / t_all * 100) if t_all else 50.0
    return round(pct, 1), {"cycles": len(rows), "tasks_total": t_all, "tasks_ok": t_ok}


def compute_score(conn) -> dict:
    dims = {}
    for name, fn in [("services", lambda: score_services()),
                     ("scripts", lambda: score_scripts(conn)),
                     ("cluster", lambda: score_cluster()),
                     ("tasks", lambda: score_tasks()),
                     ("cycles", lambda: score_cycles(conn))]:
        pct, det = fn()
        dims[name] = {"score": pct, "detail": det}
    gs = round(min(max(sum(dims[d]["score"] * WEIGHTS[d] / 100 for d in WEIGHTS), 0), 100), 1)
    grade = "A+" if gs >= 90 else "A" if gs >= 80 else "B" if gs >= 65 else \
            "C" if gs >= 50 else "D" if gs >= 30 else "F"
    return {"timestamp": datetime.utcnow().isoformat() + "Z",
            "global_score": gs, "grade": grade, "dimensions": dims, "weights": WEIGHTS}


def save_score(conn, report: dict):
    conn.execute(
        "INSERT INTO memories (category,key,value,source,confidence) VALUES (?,?,?,?,?)",
        ("autonomy_score", f"score_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
         json.dumps(report), "autonomy_scorer.py", report["global_score"] / 100))
    conn.commit()


def show_history(conn) -> list:
    rows = conn.execute(
        "SELECT key, value, created_at FROM memories "
        "WHERE category='autonomy_score' ORDER BY id DESC LIMIT 10").fetchall()
    return [{"key": r["key"], "score": json.loads(r["value"]).get("global_score"),
             "grade": json.loads(r["value"]).get("grade"), "at": r["created_at"]}
            for r in rows]


def main():
    ap = argparse.ArgumentParser(description="JARVIS global autonomy scorer")
    ap.add_argument("--once", action="store_true", help="Compute score once")
    ap.add_argument("--history", action="store_true", help="Show last 10 scores")
    args = ap.parse_args()
    if not args.once and not args.history:
        ap.print_help(); sys.exit(1)
    conn = get_conn()
    try:
        if args.history:
            print(json.dumps(show_history(conn), indent=2))
        else:
            report = compute_score(conn)
            save_score(conn, report)
            print(json.dumps(report, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
