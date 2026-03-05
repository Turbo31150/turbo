#!/usr/bin/env python3
"""performance_regression_detector.py — Compare benchmarks over time.

Reads benchmark data from etoile.db, detects performance regressions
(>10% slowdown), and tracks latency, throughput, success rate metrics.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'cowork_gaps.db')
ETOILE_DB = os.path.join(os.path.dirname(__file__), '..', '..', 'etoile.db')


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS regression_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern TEXT, metric TEXT, old_value REAL, new_value REAL,
        change_pct REAL, is_regression INTEGER, timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    db.commit()
    return db


def get_dispatch_stats(period="recent"):
    """Get dispatch stats from etoile.db."""
    if not os.path.exists(ETOILE_DB):
        return {}
    db = sqlite3.connect(ETOILE_DB)
    db.row_factory = sqlite3.Row

    if period == "recent":
        where = "WHERE id > (SELECT MAX(id) - 500 FROM agent_dispatch_log)"
    else:
        where = "WHERE id <= (SELECT MAX(id) - 500 FROM agent_dispatch_log) AND id > (SELECT MAX(id) - 1000 FROM agent_dispatch_log)"

    rows = db.execute(f"""
        SELECT classified_type,
               COUNT(*) as cnt,
               AVG(latency_ms) as avg_lat,
               AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) as success_rate,
               AVG(quality_score) as avg_quality
        FROM agent_dispatch_log {where}
        GROUP BY classified_type
    """).fetchall()
    db.close()
    return {r["classified_type"]: dict(r) for r in rows if r["classified_type"]}


def detect_regressions(threshold=10):
    """Compare recent vs older stats to find regressions."""
    recent = get_dispatch_stats("recent")
    older = get_dispatch_stats("older")

    if not recent or not older:
        return {"regressions": [], "note": "Not enough data for comparison"}

    db = init_db()
    regressions = []
    improvements = []

    for pattern in set(recent.keys()) & set(older.keys()):
        r, o = recent[pattern], older[pattern]

        # Latency regression
        if o["avg_lat"] and r["avg_lat"]:
            change = ((r["avg_lat"] - o["avg_lat"]) / max(1, o["avg_lat"])) * 100
            is_reg = change > threshold
            entry = {
                "pattern": pattern, "metric": "latency_ms",
                "old": round(o["avg_lat"], 1), "new": round(r["avg_lat"], 1),
                "change_pct": round(change, 1), "regression": is_reg
            }
            if is_reg:
                regressions.append(entry)
            elif change < -threshold:
                improvements.append(entry)

            db.execute(
                "INSERT INTO regression_reports (pattern, metric, old_value, new_value, change_pct, is_regression) VALUES (?,?,?,?,?,?)",
                (pattern, "latency_ms", o["avg_lat"], r["avg_lat"], change, int(is_reg))
            )

        # Success rate regression
        if o["success_rate"] is not None and r["success_rate"] is not None:
            change = ((r["success_rate"] - o["success_rate"]) / max(0.01, o["success_rate"])) * 100
            is_reg = change < -threshold  # lower success = regression
            if is_reg:
                regressions.append({
                    "pattern": pattern, "metric": "success_rate",
                    "old": round(o["success_rate"], 3), "new": round(r["success_rate"], 3),
                    "change_pct": round(change, 1), "regression": True
                })

    db.commit()
    db.close()

    return {
        "regressions": regressions,
        "improvements": improvements,
        "patterns_compared": len(set(recent.keys()) & set(older.keys())),
        "threshold_pct": threshold,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Performance Regression Detector")
    parser.add_argument("--once", action="store_true", help="Run detection once")
    parser.add_argument("--compare", action="store_true", help="Compare periods")
    parser.add_argument("--threshold", type=int, default=10, help="Regression threshold %%")
    args = parser.parse_args()

    result = detect_regressions(args.threshold)
    print(json.dumps(result, indent=2, ensure_ascii=False))
