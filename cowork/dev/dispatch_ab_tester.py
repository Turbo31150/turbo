#!/usr/bin/env python3
"""dispatch_ab_tester.py — A/B test dispatch strategies to find optimal routing.

Compares different dispatch strategies (single vs parallel, node preferences,
timeout values) using historical data and generates test plans.

CLI:
    --once       : generate A/B test recommendations
    --compare    : compare two strategies from logs
    --stats      : show test results

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

# Strategies to test
STRATEGIES = {
    "single_m1": {"primary": "M1", "fallback": None, "timeout": 60},
    "single_ol1": {"primary": "OL1", "fallback": None, "timeout": 60},
    "m1_with_retry": {"primary": "M1", "fallback": "OL1", "timeout": 30},
    "ol1_with_retry": {"primary": "OL1", "fallback": "M1", "timeout": 30},
    "parallel_m1_ol1": {"primary": ["M1", "OL1"], "fallback": None, "timeout": 30},
    "fast_timeout": {"primary": "M1", "fallback": "OL1", "timeout": 15},
    "category_optimized": {"primary": "adaptive", "fallback": "OL1", "timeout": 45},
}


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS ab_test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        pattern TEXT NOT NULL,
        strategy_a TEXT NOT NULL,
        strategy_b TEXT NOT NULL,
        a_success_pct REAL,
        b_success_pct REAL,
        a_avg_latency REAL,
        b_avg_latency REAL,
        winner TEXT,
        confidence REAL
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def generate_test_plan():
    """Generate A/B test recommendations based on current data."""
    if not ETOILE_DB.exists():
        return {"error": "etoile.db not found"}

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    # Current performance by strategy
    strat_perf = edb.execute("""
        SELECT strategy, classified_type,
               COUNT(*) as total,
               AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) as success_rate,
               AVG(latency_ms) as avg_lat,
               AVG(quality_score) as avg_q
        FROM agent_dispatch_log
        WHERE strategy IS NOT NULL
        GROUP BY strategy, classified_type
        HAVING total >= 5
        ORDER BY classified_type, success_rate DESC
    """).fetchall()

    # Patterns that need improvement
    weak_patterns = edb.execute("""
        SELECT classified_type,
               AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) as success_rate,
               AVG(latency_ms) as avg_lat
        FROM agent_dispatch_log
        GROUP BY classified_type
        HAVING success_rate < 0.8
        ORDER BY success_rate ASC
    """).fetchall()

    edb.close()

    # Generate test plan
    tests = []
    for wp in weak_patterns:
        pattern = wp["classified_type"]
        current_rate = wp["success_rate"]
        current_lat = wp["avg_lat"] or 0

        # Find best alternative
        if current_lat > 30000:
            test = {
                "pattern": pattern,
                "current_strategy": "single_m1",
                "test_strategy": "m1_with_retry",
                "hypothesis": f"Retry with OL1 fallback will increase {pattern} success from {current_rate*100:.0f}% to 90%+",
                "metric": "success_rate",
                "sample_size_needed": 50,
                "expected_improvement": f"+{(0.9 - current_rate)*100:.0f}% success rate",
            }
        else:
            test = {
                "pattern": pattern,
                "current_strategy": "single_m1",
                "test_strategy": "parallel_m1_ol1",
                "hypothesis": f"Parallel dispatch will reduce {pattern} latency from {current_lat:.0f}ms to <20s",
                "metric": "latency_ms",
                "sample_size_needed": 30,
                "expected_improvement": f"-{(current_lat - 20000):.0f}ms latency",
            }
        tests.append(test)

    # Compare existing strategy results
    comparisons = []
    strategy_data = {}
    for sp in strat_perf:
        key = (sp["classified_type"], sp["strategy"])
        strategy_data[key] = {
            "total": sp["total"],
            "success_rate": round(sp["success_rate"], 3),
            "avg_latency": round(sp["avg_lat"] or 0),
            "avg_quality": round(sp["avg_q"] or 0, 3),
        }

    # Find patterns with multiple strategies
    patterns_strategies = {}
    for (pat, strat), data in strategy_data.items():
        if pat not in patterns_strategies:
            patterns_strategies[pat] = {}
        patterns_strategies[pat][strat] = data

    for pat, strats in patterns_strategies.items():
        if len(strats) >= 2:
            sorted_strats = sorted(strats.items(), key=lambda x: -x[1]["success_rate"])
            if len(sorted_strats) >= 2:
                a_name, a_data = sorted_strats[0]
                b_name, b_data = sorted_strats[1]
                comparisons.append({
                    "pattern": pat,
                    "winner": a_name,
                    "winner_data": a_data,
                    "loser": b_name,
                    "loser_data": b_data,
                    "success_delta": round((a_data["success_rate"] - b_data["success_rate"]) * 100, 1),
                    "latency_delta": a_data["avg_latency"] - b_data["avg_latency"],
                })

    conn = get_db()
    ts = datetime.now().isoformat()
    for comp in comparisons:
        conn.execute("""
            INSERT INTO ab_test_results
            (timestamp, pattern, strategy_a, strategy_b, a_success_pct, b_success_pct,
             a_avg_latency, b_avg_latency, winner, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, comp["pattern"], comp["winner"], comp["loser"],
              comp["winner_data"]["success_rate"] * 100,
              comp["loser_data"]["success_rate"] * 100,
              comp["winner_data"]["avg_latency"],
              comp["loser_data"]["avg_latency"],
              comp["winner"],
              min(comp["winner_data"]["total"], comp["loser_data"]["total"]) / 50))
    conn.commit()
    conn.close()

    return {
        "timestamp": ts,
        "test_plan": tests,
        "existing_comparisons": comparisons,
        "strategies_available": list(STRATEGIES.keys()),
        "weak_patterns": len(weak_patterns),
    }


def main():
    parser = argparse.ArgumentParser(description="Dispatch A/B Tester")
    parser.add_argument("--once", action="store_true", help="Generate test plan")
    parser.add_argument("--stats", action="store_true", help="Show results")
    args = parser.parse_args()

    if not any([args.once, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        conn = get_db()
        rows = conn.execute("SELECT * FROM ab_test_results ORDER BY timestamp DESC LIMIT 20").fetchall()
        conn.close()
        result = {"tests": [dict(r) for r in rows]}
    else:
        result = generate_test_plan()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
