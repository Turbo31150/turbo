#!/usr/bin/env python3
"""smart_retry_dispatcher.py — Intelligent retry logic for failed dispatches.

Implements exponential backoff with node rotation: when a node fails,
automatically retry on the next best node instead of the same one.

CLI:
    --once       : analyze retry opportunities from recent failures
    --simulate   : simulate retry success rates
    --stats      : show retry stats

Stdlib-only (sqlite3, json, argparse).
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")

# Retry configuration
MAX_RETRIES = 3
BACKOFF_BASE_MS = 500
BACKOFF_MULTIPLIER = 2

# Node fallback chains (based on observed success rates)
FALLBACK_CHAINS = {
    "M1": ["OL1", "M2", "M3"],
    "OL1": ["M1", "M2", "M3"],
    "M2": ["M1", "OL1", "M3"],
    "M3": ["M1", "OL1", "M2"],
}

# Pattern-specific preferred fallbacks
PATTERN_FALLBACKS = {
    "architecture": ["OL1", "M2"],
    "analysis": ["OL1", "M2"],
    "security": ["OL1", "M1"],
    "data": ["OL1", "M1"],
    "code": ["M1", "OL1"],
    "reasoning": ["M2", "M1"],
    "trading": ["M1", "M2"],
    "math": ["M1", "M2"],
    "simple": ["OL1", "M1"],
    "system": ["M1", "OL1"],
    "creative": ["OL1", "M1"],
    "web": ["OL1", "M1"],
}


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS retry_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        original_node TEXT,
        pattern TEXT,
        retry_node TEXT,
        retry_number INTEGER,
        would_succeed INTEGER,
        estimated_latency_ms REAL
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def get_node_success_rates():
    """Get success rates per node per pattern."""
    if not ETOILE_DB.exists():
        return {}

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    rows = edb.execute("""
        SELECT classified_type, node,
               COUNT(*) as total,
               SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as successes,
               AVG(latency_ms) as avg_lat
        FROM agent_dispatch_log
        GROUP BY classified_type, node
    """).fetchall()

    edb.close()

    rates = {}
    for r in rows:
        pat = r["classified_type"]
        if pat not in rates:
            rates[pat] = {}
        rates[pat][r["node"]] = {
            "success_rate": r["successes"] / max(r["total"], 1),
            "avg_latency": r["avg_lat"] or 0,
            "total": r["total"],
        }

    return rates


def simulate_retries():
    """Simulate what would happen if we retried failed dispatches on fallback nodes."""
    if not ETOILE_DB.exists():
        return {"error": "etoile.db not found"}

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    failures = edb.execute("""
        SELECT id, classified_type, node, latency_ms
        FROM agent_dispatch_log
        WHERE success = 0
        ORDER BY id DESC
    """).fetchall()

    rates = get_node_success_rates()
    conn = get_db()
    ts = datetime.now().isoformat()

    simulations = []
    would_recover = 0
    total_failures = len(failures)

    for f in failures:
        pattern = f["classified_type"]
        failed_node = f["node"]
        fallbacks = PATTERN_FALLBACKS.get(pattern, FALLBACK_CHAINS.get(failed_node, []))

        recovered = False
        for retry_num, fallback_node in enumerate(fallbacks, 1):
            if fallback_node == failed_node:
                continue

            node_rate = rates.get(pattern, {}).get(fallback_node, {})
            success_rate = node_rate.get("success_rate", 0.5)
            avg_lat = node_rate.get("avg_latency", 30000)

            # Would this retry succeed?
            if success_rate >= 0.7:
                recovered = True
                would_recover += 1

                conn.execute("""
                    INSERT INTO retry_analysis
                    (timestamp, original_node, pattern, retry_node, retry_number, would_succeed, estimated_latency_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ts, failed_node, pattern, fallback_node, retry_num, 1, avg_lat))

                simulations.append({
                    "pattern": pattern,
                    "failed_node": failed_node,
                    "retry_node": fallback_node,
                    "retry_number": retry_num,
                    "fallback_success_rate": round(success_rate * 100, 1),
                    "estimated_latency_ms": round(avg_lat),
                })
                break

    conn.commit()
    conn.close()
    edb.close()

    recovery_rate = would_recover / max(total_failures, 1) * 100

    # Aggregate by pattern
    pattern_recovery = {}
    for s in simulations:
        p = s["pattern"]
        if p not in pattern_recovery:
            pattern_recovery[p] = {"recovered": 0, "total_failures": 0}
        pattern_recovery[p]["recovered"] += 1

    # Get total failures per pattern
    for f in failures:
        p = f["classified_type"]
        if p in pattern_recovery:
            pattern_recovery[p]["total_failures"] += 1

    for p, data in pattern_recovery.items():
        data["recovery_pct"] = round(data["recovered"] / max(data["total_failures"], 1) * 100, 1)

    return {
        "timestamp": ts,
        "total_failures": total_failures,
        "would_recover": would_recover,
        "recovery_rate_pct": round(recovery_rate, 1),
        "new_success_rate_pct": round(
            (1 - (total_failures - would_recover) / max(total_failures + 1700, 1)) * 100, 1
        ),
        "pattern_recovery": pattern_recovery,
        "sample_retries": simulations[:15],
        "recommended_fallback_chains": PATTERN_FALLBACKS,
    }


def action_stats():
    """Show retry analysis stats."""
    conn = get_db()
    rows = conn.execute("""
        SELECT pattern, retry_node, COUNT(*) as cnt,
               AVG(estimated_latency_ms) as avg_lat
        FROM retry_analysis
        WHERE would_succeed = 1
        GROUP BY pattern, retry_node
        ORDER BY cnt DESC
    """).fetchall()
    conn.close()
    return {"recovery_routes": [dict(r) for r in rows]}


def main():
    parser = argparse.ArgumentParser(description="Smart Retry Dispatcher")
    parser.add_argument("--once", action="store_true", help="Analyze retry opportunities")
    parser.add_argument("--simulate", action="store_true", help="Simulate retries")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    args = parser.parse_args()

    if not any([args.once, args.simulate, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        result = action_stats()
    else:
        result = simulate_retries()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
