#!/usr/bin/env python3
"""dispatch_latency_optimizer.py — Optimize dispatch latency for slow patterns.

Identifies slow patterns (web 35s, xl 30s, trading 30s) and generates
optimizations: caching, pre-warming, prompt compression, parallel dispatch.

CLI:
    --once       : analyze and optimize
    --profile    : detailed latency profiling
    --stats      : show optimization history

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

# Latency targets (ms)
LATENCY_TARGETS = {
    "simple": 3000,
    "creative": 10000,
    "system": 10000,
    "code": 15000,
    "math": 15000,
    "devops": 15000,
    "web": 20000,
    "analysis": 20000,
    "architecture": 20000,
    "security": 20000,
    "data": 20000,
    "trading": 20000,
    "reasoning": 25000,
}

OPTIMIZATION_STRATEGIES = {
    "prompt_compression": {
        "description": "Compress prompt by removing redundant context",
        "latency_reduction_pct": 15,
        "applicable_to": ["architecture", "analysis", "security", "data"],
    },
    "response_caching": {
        "description": "Cache frequent identical queries for 5 minutes",
        "latency_reduction_pct": 80,
        "applicable_to": ["simple", "system", "devops"],
    },
    "parallel_dispatch": {
        "description": "Send to 2 nodes simultaneously, use first response",
        "latency_reduction_pct": 30,
        "applicable_to": ["web", "trading", "reasoning"],
    },
    "streaming_response": {
        "description": "Use streaming to reduce perceived latency",
        "latency_reduction_pct": 40,
        "applicable_to": ["code", "creative", "analysis"],
    },
    "model_downgrade": {
        "description": "Use smaller/faster model for non-critical patterns",
        "latency_reduction_pct": 50,
        "applicable_to": ["simple", "system"],
    },
    "timeout_reduction": {
        "description": "Reduce timeout to fail-fast and retry on faster node",
        "latency_reduction_pct": 25,
        "applicable_to": ["web", "trading", "xl"],
    },
}


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS latency_optimizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        pattern TEXT NOT NULL,
        strategy TEXT NOT NULL,
        current_latency_ms REAL,
        expected_latency_ms REAL,
        reduction_pct REAL,
        applied INTEGER DEFAULT 0
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def profile_latency():
    """Detailed latency profiling per pattern."""
    if not ETOILE_DB.exists():
        return {"error": "etoile.db not found"}

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    rows = edb.execute("""
        SELECT classified_type,
               COUNT(*) as total,
               AVG(latency_ms) as avg_lat,
               MIN(latency_ms) as min_lat,
               MAX(latency_ms) as max_lat,
               AVG(CASE WHEN success=1 THEN latency_ms ELSE NULL END) as avg_success_lat,
               AVG(CASE WHEN success=0 THEN latency_ms ELSE NULL END) as avg_fail_lat,
               AVG(tokens_in) as avg_tokens_in,
               AVG(tokens_out) as avg_tokens_out
        FROM agent_dispatch_log
        GROUP BY classified_type
        ORDER BY avg_lat DESC
    """).fetchall()

    # Percentile approximation (P50, P90, P99) via ordered latencies
    profiles = []
    for r in rows:
        pattern = r["classified_type"]
        target = LATENCY_TARGETS.get(pattern, 20000)
        avg = r["avg_lat"] or 0

        latencies = edb.execute("""
            SELECT latency_ms FROM agent_dispatch_log
            WHERE classified_type = ? AND latency_ms IS NOT NULL
            ORDER BY latency_ms
        """, (pattern,)).fetchall()

        lats = [l[0] for l in latencies if l[0]]
        p50 = lats[len(lats) // 2] if lats else 0
        p90 = lats[int(len(lats) * 0.9)] if lats else 0
        p99 = lats[int(len(lats) * 0.99)] if lats else 0

        over_target = avg > target
        profiles.append({
            "pattern": pattern,
            "total": r["total"],
            "avg_ms": round(avg),
            "p50_ms": round(p50),
            "p90_ms": round(p90),
            "p99_ms": round(p99),
            "min_ms": round(r["min_lat"] or 0),
            "max_ms": round(r["max_lat"] or 0),
            "target_ms": target,
            "over_target": over_target,
            "avg_success_ms": round(r["avg_success_lat"] or 0),
            "avg_fail_ms": round(r["avg_fail_lat"] or 0),
            "avg_tokens_in": round(r["avg_tokens_in"] or 0),
            "avg_tokens_out": round(r["avg_tokens_out"] or 0),
        })

    edb.close()
    return profiles


def generate_optimizations(profiles):
    """Generate optimization plan based on profiling."""
    optimizations = []

    for p in profiles:
        if not p["over_target"]:
            continue

        pattern = p["pattern"]
        applicable = []

        for strat_name, strat in OPTIMIZATION_STRATEGIES.items():
            if pattern in strat["applicable_to"]:
                expected = p["avg_ms"] * (1 - strat["latency_reduction_pct"] / 100)
                applicable.append({
                    "strategy": strat_name,
                    "description": strat["description"],
                    "current_ms": p["avg_ms"],
                    "expected_ms": round(expected),
                    "reduction_pct": strat["latency_reduction_pct"],
                    "meets_target": expected <= p["target_ms"],
                })

        # Sort by effectiveness
        applicable.sort(key=lambda x: -x["reduction_pct"])

        if applicable:
            optimizations.append({
                "pattern": pattern,
                "current_avg_ms": p["avg_ms"],
                "target_ms": p["target_ms"],
                "gap_ms": p["avg_ms"] - p["target_ms"],
                "best_strategy": applicable[0],
                "all_strategies": applicable,
            })

    return optimizations


def action_once():
    """Run full analysis cycle."""
    profiles = profile_latency()
    if isinstance(profiles, dict) and "error" in profiles:
        return profiles

    optimizations = generate_optimizations(profiles)

    conn = get_db()
    ts = datetime.now().isoformat()
    for opt in optimizations:
        best = opt["best_strategy"]
        conn.execute("""
            INSERT INTO latency_optimizations
            (timestamp, pattern, strategy, current_latency_ms, expected_latency_ms, reduction_pct)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, opt["pattern"], best["strategy"],
              best["current_ms"], best["expected_ms"], best["reduction_pct"]))
    conn.commit()
    conn.close()

    # Summary
    over_target = [p for p in profiles if p["over_target"]]
    return {
        "timestamp": ts,
        "total_patterns": len(profiles),
        "over_target": len(over_target),
        "profiles": profiles,
        "optimizations": optimizations,
        "summary": {
            "slowest": profiles[0]["pattern"] if profiles else None,
            "slowest_avg_ms": profiles[0]["avg_ms"] if profiles else 0,
            "optimizable": len(optimizations),
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Dispatch Latency Optimizer")
    parser.add_argument("--once", action="store_true", help="Full analysis")
    parser.add_argument("--profile", action="store_true", help="Latency profiling")
    parser.add_argument("--stats", action="store_true", help="Optimization history")
    args = parser.parse_args()

    if not any([args.once, args.profile, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.profile:
        result = profile_latency()
    elif args.stats:
        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM latency_optimizations ORDER BY timestamp DESC LIMIT 20
        """).fetchall()
        conn.close()
        result = {"optimizations": [dict(r) for r in rows]}
    else:
        result = action_once()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
