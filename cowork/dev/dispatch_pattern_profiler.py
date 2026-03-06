#!/usr/bin/env python3
"""dispatch_pattern_profiler.py — Deep profiling of dispatch patterns.

Creates detailed profiles for each dispatch pattern: timing distributions,
failure modes, optimal nodes, peak hours, and quality trends.

CLI:
    --once       : profile all patterns
    --pattern X  : profile a specific pattern
    --stats      : show profiling history

Stdlib-only (sqlite3, json, argparse).
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS pattern_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        pattern TEXT NOT NULL,
        profile_json TEXT NOT NULL
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def profile_pattern(edb, pattern):
    """Build a comprehensive profile for a pattern."""
    rows = edb.execute("""
        SELECT node, success, latency_ms, quality_score, error_msg, timestamp,
               tokens_in, tokens_out, model_used
        FROM agent_dispatch_log
        WHERE classified_type = ?
        ORDER BY id DESC
    """, (pattern,)).fetchall()

    if not rows:
        return None

    total = len(rows)
    successes = [r for r in rows if r["success"]]
    failures = [r for r in rows if not r["success"]]

    # Timing
    latencies = [r["latency_ms"] for r in rows if r["latency_ms"]]
    latencies.sort()

    def percentile(vals, p):
        if not vals:
            return 0
        k = max(0, int(len(vals) * p / 100) - 1)
        return vals[k]

    # Node performance
    node_stats = {}
    for r in rows:
        n = r["node"] or "?"
        if n not in node_stats:
            node_stats[n] = {"total": 0, "success": 0, "latencies": [], "qualities": []}
        node_stats[n]["total"] += 1
        if r["success"]:
            node_stats[n]["success"] += 1
        if r["latency_ms"]:
            node_stats[n]["latencies"].append(r["latency_ms"])
        if r["quality_score"]:
            node_stats[n]["qualities"].append(r["quality_score"])

    nodes = {}
    best_node = None
    best_score = -1
    for n, s in node_stats.items():
        rate = s["success"] / max(s["total"], 1) * 100
        avg_lat = sum(s["latencies"]) / max(len(s["latencies"]), 1)
        avg_q = sum(s["qualities"]) / max(len(s["qualities"]), 1)
        score = rate * 0.5 + (100 - min(avg_lat / 500, 100)) * 0.2 + avg_q * 100 * 0.3
        nodes[n] = {
            "total": s["total"], "success_rate": round(rate, 1),
            "avg_latency_ms": round(avg_lat), "avg_quality": round(avg_q, 3),
            "score": round(score, 1),
        }
        if score > best_score:
            best_score = score
            best_node = n

    # Error analysis
    error_types = Counter()
    for f in failures:
        err = f["error_msg"] or "unknown"
        if "timeout" in err.lower():
            error_types["timeout"] += 1
        elif "empty" in err.lower():
            error_types["empty_response"] += 1
        elif "null" in err.lower() or err == "unknown":
            error_types["null_error"] += 1
        else:
            error_types[err[:30]] += 1

    # Peak hours (hour distribution)
    hour_dist = Counter()
    for r in rows:
        ts = r["timestamp"] or ""
        if len(ts) >= 13:
            try:
                h = int(ts[11:13])
                hour_dist[h] += 1
            except ValueError:
                pass

    peak_hours = sorted(hour_dist.items(), key=lambda x: -x[1])[:3]

    # Quality trend (first half vs second half)
    mid = total // 2
    recent_q = [r["quality_score"] for r in rows[:mid] if r["quality_score"]]
    older_q = [r["quality_score"] for r in rows[mid:] if r["quality_score"]]
    recent_avg = sum(recent_q) / max(len(recent_q), 1)
    older_avg = sum(older_q) / max(len(older_q), 1)
    q_trend = "improving" if recent_avg > older_avg * 1.05 else "declining" if recent_avg < older_avg * 0.95 else "stable"

    # Token usage
    tokens_in = [r["tokens_in"] for r in rows if r["tokens_in"]]
    tokens_out = [r["tokens_out"] for r in rows if r["tokens_out"]]

    return {
        "pattern": pattern,
        "total_dispatches": total,
        "success_rate": round(len(successes) / max(total, 1) * 100, 1),
        "failure_count": len(failures),
        "timing": {
            "avg_ms": round(sum(latencies) / max(len(latencies), 1)),
            "p50_ms": round(percentile(latencies, 50)),
            "p90_ms": round(percentile(latencies, 90)),
            "p99_ms": round(percentile(latencies, 99)),
            "min_ms": round(min(latencies)) if latencies else 0,
            "max_ms": round(max(latencies)) if latencies else 0,
        },
        "quality": {
            "avg": round(sum(r["quality_score"] for r in successes if r["quality_score"]) / max(len([r for r in successes if r["quality_score"]]), 1), 3),
            "trend": q_trend,
        },
        "nodes": nodes,
        "best_node": best_node,
        "best_node_score": round(best_score, 1),
        "error_types": dict(error_types.most_common(5)),
        "peak_hours": [{"hour": h, "count": c} for h, c in peak_hours],
        "tokens": {
            "avg_in": round(sum(tokens_in) / max(len(tokens_in), 1)),
            "avg_out": round(sum(tokens_out) / max(len(tokens_out), 1)),
        },
        "models_used": list(set(r["model_used"] for r in rows if r["model_used"])),
    }


def profile_all(edb):
    """Profile all patterns."""
    patterns = edb.execute("""
        SELECT DISTINCT classified_type FROM agent_dispatch_log
        WHERE classified_type IS NOT NULL
        ORDER BY classified_type
    """).fetchall()

    profiles = []
    for row in patterns:
        p = profile_pattern(edb, row["classified_type"])
        if p:
            profiles.append(p)

    return profiles


def main():
    parser = argparse.ArgumentParser(description="Dispatch Pattern Profiler")
    parser.add_argument("--once", action="store_true", help="Profile all patterns")
    parser.add_argument("--pattern", type=str, help="Profile specific pattern")
    parser.add_argument("--stats", action="store_true", help="Show history")
    args = parser.parse_args()

    if not any([args.once, args.pattern, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        conn = get_db()
        rows = conn.execute("""
            SELECT timestamp, pattern, json_extract(profile_json, '$.success_rate') as rate
            FROM pattern_profiles ORDER BY id DESC LIMIT 20
        """).fetchall()
        conn.close()
        print(json.dumps({"history": [dict(r) for r in rows]}, indent=2))
        return

    if not ETOILE_DB.exists():
        print(json.dumps({"error": "etoile.db not found"}))
        return

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    if args.pattern:
        profile = profile_pattern(edb, args.pattern)
        edb.close()
        if profile:
            conn = get_db()
            conn.execute(
                "INSERT INTO pattern_profiles (timestamp, pattern, profile_json) VALUES (?, ?, ?)",
                (datetime.now().isoformat(), args.pattern, json.dumps(profile))
            )
            conn.commit()
            conn.close()
        result = profile or {"error": f"Pattern '{args.pattern}' not found"}
    else:
        profiles = profile_all(edb)
        edb.close()

        conn = get_db()
        ts = datetime.now().isoformat()
        for p in profiles:
            conn.execute(
                "INSERT INTO pattern_profiles (timestamp, pattern, profile_json) VALUES (?, ?, ?)",
                (ts, p["pattern"], json.dumps(p))
            )
        conn.commit()
        conn.close()

        # Summary
        best = max(profiles, key=lambda x: x["success_rate"]) if profiles else None
        worst = min(profiles, key=lambda x: x["success_rate"]) if profiles else None

        result = {
            "timestamp": ts,
            "patterns_profiled": len(profiles),
            "best_pattern": {"name": best["pattern"], "rate": best["success_rate"]} if best else None,
            "worst_pattern": {"name": worst["pattern"], "rate": worst["success_rate"]} if worst else None,
            "profiles": profiles,
        }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
