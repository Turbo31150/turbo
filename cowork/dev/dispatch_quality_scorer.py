#!/usr/bin/env python3
"""dispatch_quality_scorer.py — Analyze and improve response quality scoring.

Examines quality_score distribution, identifies patterns with consistently
low quality, and suggests improvements to scoring/routing.

CLI:
    --once       : full quality analysis
    --trends     : quality trends over time
    --stats      : quality distribution

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
ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS quality_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        pattern TEXT NOT NULL,
        node TEXT NOT NULL,
        avg_quality REAL,
        quality_trend TEXT,
        recommendation TEXT
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def analyze_quality():
    """Full quality analysis."""
    if not ETOILE_DB.exists():
        return {"error": "etoile.db not found"}

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    # Quality by pattern + node
    rows = edb.execute("""
        SELECT classified_type, node, model_used,
               COUNT(*) as total,
               AVG(quality_score) as avg_q,
               MIN(quality_score) as min_q,
               MAX(quality_score) as max_q,
               SUM(CASE WHEN quality_score >= 0.8 THEN 1 ELSE 0 END) as high_q,
               SUM(CASE WHEN quality_score < 0.5 THEN 1 ELSE 0 END) as low_q,
               AVG(tokens_out) as avg_tokens
        FROM agent_dispatch_log
        WHERE success = 1
        GROUP BY classified_type, node
        HAVING total >= 3
        ORDER BY avg_q ASC
    """).fetchall()

    quality_map = []
    conn = get_db()
    ts = datetime.now().isoformat()

    for r in rows:
        avg_q = r["avg_q"] or 0
        total = r["total"]
        high_pct = (r["high_q"] or 0) / max(total, 1) * 100
        low_pct = (r["low_q"] or 0) / max(total, 1) * 100

        # Determine recommendation
        if avg_q >= 0.8:
            rec = "excellent — maintain"
            trend = "stable_high"
        elif avg_q >= 0.6:
            rec = "acceptable — monitor"
            trend = "moderate"
        elif avg_q >= 0.4:
            rec = "poor — consider rerouting or prompt improvement"
            trend = "declining"
        else:
            rec = "critical — reroute immediately"
            trend = "critical"

        entry = {
            "pattern": r["classified_type"],
            "node": r["node"],
            "model": r["model_used"],
            "total_successful": total,
            "avg_quality": round(avg_q, 3),
            "min_quality": round(r["min_q"] or 0, 3),
            "max_quality": round(r["max_q"] or 0, 3),
            "high_quality_pct": round(high_pct, 1),
            "low_quality_pct": round(low_pct, 1),
            "avg_tokens_out": round(r["avg_tokens"] or 0),
            "trend": trend,
            "recommendation": rec,
        }
        quality_map.append(entry)

        conn.execute("""
            INSERT INTO quality_analysis
            (timestamp, pattern, node, avg_quality, quality_trend, recommendation)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, r["classified_type"], r["node"], avg_q, trend, rec))

    conn.commit()
    conn.close()

    # Overall quality score
    overall = edb.execute("""
        SELECT AVG(quality_score) as avg_q,
               COUNT(*) as total,
               SUM(CASE WHEN quality_score >= 0.8 THEN 1 ELSE 0 END) as excellent
        FROM agent_dispatch_log
        WHERE success = 1
    """).fetchone()

    # Best and worst combos
    best = [q for q in quality_map if q["avg_quality"] >= 0.8][:5]
    worst = [q for q in quality_map if q["avg_quality"] < 0.5][:5]

    # Quality by tokens (correlation)
    token_quality = edb.execute("""
        SELECT
            CASE WHEN tokens_out < 50 THEN 'tiny (<50)'
                 WHEN tokens_out < 200 THEN 'short (50-200)'
                 WHEN tokens_out < 500 THEN 'medium (200-500)'
                 ELSE 'long (500+)' END as length_bucket,
            AVG(quality_score) as avg_q,
            COUNT(*) as cnt
        FROM agent_dispatch_log
        WHERE success = 1
        GROUP BY length_bucket
    """).fetchall()

    edb.close()

    return {
        "timestamp": ts,
        "overall_quality": round(overall["avg_q"] or 0, 3),
        "total_successful": overall["total"],
        "excellent_pct": round((overall["excellent"] or 0) / max(overall["total"], 1) * 100, 1),
        "quality_map": quality_map,
        "best_combos": best,
        "worst_combos": worst,
        "quality_by_length": [dict(tq) for tq in token_quality],
        "critical_count": len([q for q in quality_map if q["trend"] == "critical"]),
        "declining_count": len([q for q in quality_map if q["trend"] == "declining"]),
    }


def main():
    parser = argparse.ArgumentParser(description="Dispatch Quality Scorer")
    parser.add_argument("--once", action="store_true", help="Full analysis")
    parser.add_argument("--stats", action="store_true", help="Show history")
    args = parser.parse_args()

    if not any([args.once, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        conn = get_db()
        rows = conn.execute("""
            SELECT pattern, node, avg_quality, quality_trend, recommendation
            FROM quality_analysis ORDER BY avg_quality ASC LIMIT 20
        """).fetchall()
        conn.close()
        result = {"history": [dict(r) for r in rows]}
    else:
        result = analyze_quality()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
