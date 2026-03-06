#!/usr/bin/env python3
"""dispatch_trend_analyzer.py — Identify trends in dispatch patterns over time.

Detects emerging patterns, declining patterns, usage shifts, and seasonal
variations in JARVIS dispatch behavior to anticipate future needs.

CLI:
    --once       : full trend analysis
    --emerging   : show emerging patterns
    --stats      : show trend stats

Stdlib-only (sqlite3, json, argparse).
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS dispatch_trends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        pattern TEXT NOT NULL,
        trend_type TEXT NOT NULL,
        old_count INTEGER,
        new_count INTEGER,
        change_pct REAL,
        description TEXT
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def analyze_trends():
    """Compare recent vs older dispatch patterns."""
    if not ETOILE_DB.exists():
        return {"error": "etoile.db not found"}

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    total = edb.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
    midpoint = total // 2

    # Recent half vs older half
    recent = edb.execute("""
        SELECT classified_type, COUNT(*) as cnt,
               AVG(latency_ms) as avg_lat,
               AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) as success_rate
        FROM agent_dispatch_log
        WHERE id > ?
        GROUP BY classified_type
    """, (midpoint,)).fetchall()

    older = edb.execute("""
        SELECT classified_type, COUNT(*) as cnt,
               AVG(latency_ms) as avg_lat,
               AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) as success_rate
        FROM agent_dispatch_log
        WHERE id <= ?
        GROUP BY classified_type
    """, (midpoint,)).fetchall()

    edb.close()

    recent_map = {r["classified_type"]: dict(r) for r in recent}
    older_map = {r["classified_type"]: dict(r) for r in older}

    conn = get_db()
    ts = datetime.now().isoformat()

    trends = {
        "emerging": [],     # New or growing fast
        "declining": [],    # Shrinking
        "stable": [],       # Consistent
        "improving": [],    # Better success rate
        "degrading": [],    # Worse success rate
    }

    all_patterns = set(recent_map.keys()) | set(older_map.keys())

    for pat in all_patterns:
        r = recent_map.get(pat)
        o = older_map.get(pat)

        if r and not o:
            # Completely new pattern
            trends["emerging"].append({
                "pattern": pat, "trend": "new",
                "recent_count": r["cnt"], "old_count": 0,
                "change_pct": 100,
            })
            continue

        if o and not r:
            # Disappeared
            trends["declining"].append({
                "pattern": pat, "trend": "disappeared",
                "recent_count": 0, "old_count": o["cnt"],
                "change_pct": -100,
            })
            continue

        # Both exist — compare
        r_cnt = r["cnt"]
        o_cnt = o["cnt"]
        volume_change = ((r_cnt - o_cnt) / max(o_cnt, 1)) * 100

        r_sr = r["success_rate"]
        o_sr = o["success_rate"]
        sr_change = ((r_sr - o_sr) / max(o_sr, 0.01)) * 100

        entry = {
            "pattern": pat,
            "recent_count": r_cnt, "old_count": o_cnt,
            "volume_change_pct": round(volume_change, 1),
            "recent_success_pct": round(r_sr * 100, 1),
            "old_success_pct": round(o_sr * 100, 1),
            "success_change_pct": round(sr_change, 1),
            "recent_latency_ms": round(r["avg_lat"] or 0),
            "old_latency_ms": round(o["avg_lat"] or 0),
        }

        if volume_change > 30:
            entry["trend"] = "growing"
            trends["emerging"].append(entry)
        elif volume_change < -30:
            entry["trend"] = "shrinking"
            trends["declining"].append(entry)
        else:
            entry["trend"] = "stable"
            trends["stable"].append(entry)

        if sr_change > 15:
            trends["improving"].append(entry)
        elif sr_change < -15:
            trends["degrading"].append(entry)

        # Record trend
        trend_type = "emerging" if volume_change > 30 else "declining" if volume_change < -30 else "stable"
        conn.execute("""
            INSERT INTO dispatch_trends
            (timestamp, pattern, trend_type, old_count, new_count, change_pct, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ts, pat, trend_type, o_cnt, r_cnt, volume_change,
              f"Volume {volume_change:+.0f}%, Success {sr_change:+.0f}%"))

    conn.commit()
    conn.close()

    return {
        "timestamp": ts,
        "total_dispatches": total,
        "analysis_period": f"first {midpoint} vs last {total - midpoint}",
        "trends": trends,
        "summary": {
            "emerging": len(trends["emerging"]),
            "declining": len(trends["declining"]),
            "stable": len(trends["stable"]),
            "improving": len(trends["improving"]),
            "degrading": len(trends["degrading"]),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Dispatch Trend Analyzer")
    parser.add_argument("--once", action="store_true", help="Full analysis")
    parser.add_argument("--stats", action="store_true", help="Show history")
    args = parser.parse_args()

    if not any([args.once, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        conn = get_db()
        rows = conn.execute("""
            SELECT pattern, trend_type, change_pct, description
            FROM dispatch_trends ORDER BY timestamp DESC LIMIT 20
        """).fetchall()
        conn.close()
        result = {"trends": [dict(r) for r in rows]}
    else:
        result = analyze_trends()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
