#!/usr/bin/env python3
"""feedback_loop.py — Collect dispatch results and adjust scenario weights.

Analyzes cowork_execution_log in etoile.db for success/failure rates per
dispatch pattern, then adjusts scenario_weights accordingly.

CLI:
    --once       : run one analysis cycle and print JSON report
    --window N   : hours lookback (default 24)
    --dry-run    : compute adjustments without writing to DB

Stdlib-only (sqlite3, json, argparse).
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from _paths import ETOILE_DB

BOOST_THRESHOLD = 0.80
PENALIZE_THRESHOLD = 0.40
WEIGHT_STEP, WEIGHT_MIN, WEIGHT_MAX, MIN_SAMPLES = 0.1, 0.1, 3.0, 3


def get_conn():
    conn = sqlite3.connect(str(ETOILE_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def extract_pattern(name: str) -> str:
    base = Path(name).stem if name else "unknown"
    return base.split("_")[0] or "unknown"


def fetch_stats(conn, hours: int) -> dict:
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        "SELECT script, success FROM cowork_execution_log WHERE timestamp >= ?",
        (cutoff,)).fetchall()
    stats = {}
    for r in rows:
        p = extract_pattern(r["script"])
        s = stats.setdefault(p, {"total": 0, "success": 0, "failure": 0})
        s["total"] += 1
        s["success" if r["success"] else "failure"] += 1
    for s in stats.values():
        s["rate"] = round(s["success"] / s["total"], 4) if s["total"] else 0.0
    return stats


def fetch_weights(conn) -> dict:
    rows = conn.execute("SELECT scenario, weight FROM scenario_weights").fetchall()
    return {r["scenario"]: r["weight"] for r in rows}


def compute_adjustments(stats: dict, weights: dict) -> list:
    adj = []
    for pat, s in stats.items():
        if s["total"] < MIN_SAMPLES:
            continue
        cur = weights.get(pat, 1.0)
        nw = cur
        if s["rate"] >= BOOST_THRESHOLD:
            nw = min(cur + WEIGHT_STEP, WEIGHT_MAX)
        elif s["rate"] < PENALIZE_THRESHOLD:
            nw = max(cur - WEIGHT_STEP, WEIGHT_MIN)
        if nw != cur:
            adj.append({"pattern": pat, "old_weight": round(cur, 3),
                         "new_weight": round(nw, 3), "success_rate": s["rate"],
                         "samples": s["total"],
                         "direction": "boost" if nw > cur else "penalize"})
    return adj


def apply_adjustments(conn, adjustments: list):
    for a in adjustments:
        if conn.execute("SELECT 1 FROM scenario_weights WHERE scenario=?",
                        (a["pattern"],)).fetchone():
            conn.execute("UPDATE scenario_weights SET weight=? WHERE scenario=?",
                         (a["new_weight"], a["pattern"]))
        else:
            conn.execute("INSERT INTO scenario_weights (scenario,agent,weight,description) "
                         "VALUES (?,?,?,?)", (a["pattern"], "auto", a["new_weight"],
                         f"feedback_loop auto ({a['direction']})"))
    conn.commit()


def log_adjustments(conn, adjustments: list):
    if not adjustments:
        return
    conn.execute(
        "INSERT INTO memories (category,key,value,source,confidence) VALUES (?,?,?,?,?)",
        ("feedback_loop", f"adj_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
         json.dumps(adjustments), "feedback_loop.py", 0.9))
    conn.commit()


def run_once(hours: int, dry_run: bool) -> dict:
    conn = get_conn()
    try:
        stats = fetch_stats(conn, hours)
        weights = fetch_weights(conn)
        adjustments = compute_adjustments(stats, weights)
        if not dry_run and adjustments:
            apply_adjustments(conn, adjustments)
            log_adjustments(conn, adjustments)
        return {"timestamp": datetime.utcnow().isoformat() + "Z",
                "window_hours": hours, "patterns_analyzed": len(stats),
                "adjustments_count": len(adjustments), "adjustments": adjustments,
                "dry_run": dry_run,
                "stats": {p: {"rate": s["rate"], "total": s["total"]}
                          for p, s in stats.items()}}
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="Feedback loop: adjust scenario weights")
    ap.add_argument("--once", action="store_true", help="Run one cycle")
    ap.add_argument("--window", type=int, default=24, help="Hours lookback")
    ap.add_argument("--dry-run", action="store_true", help="No DB writes")
    args = ap.parse_args()
    if not args.once:
        ap.print_help()
        sys.exit(1)
    print(json.dumps(run_once(args.window, args.dry_run), indent=2))


if __name__ == "__main__":
    main()
