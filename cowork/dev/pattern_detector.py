#!/usr/bin/env python3
"""Pattern Detector — Analyze etoile.db for failures, slow scripts, unused patterns.

Reads memories, cluster_health, cowork_execution_log to detect:
- Repeated failures (scripts failing > 50% of runs)
- Slow patterns (scripts with avg duration > 10s)
- Unused scripts (in cowork_script_mapping but never executed)
- Cluster instability (nodes with high DOWN ratio)

Usage:
    python pattern_detector.py --once
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "ETOILE_DB", os.path.join(os.path.dirname(__file__), "..", "..", "etoile.db")
)

SLOW_THRESHOLD_MS = 10000
FAILURE_RATE_THRESHOLD = 0.5
MIN_RUNS_FOR_ANALYSIS = 1


def get_db():
    if not os.path.exists(DB_PATH):
        print(json.dumps({"error": f"Database not found: {DB_PATH}"}))
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def detect_failures(conn):
    """Scripts with failure rate above threshold."""
    cur = conn.execute(
        "SELECT script, COUNT(*) as total, "
        "SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fails, "
        "AVG(duration_ms) as avg_ms "
        "FROM cowork_execution_log GROUP BY script HAVING total >= ?",
        (MIN_RUNS_FOR_ANALYSIS,),
    )
    failures = []
    for r in cur:
        rate = r["fails"] / r["total"] if r["total"] else 0
        if rate >= FAILURE_RATE_THRESHOLD:
            failures.append({
                "script": r["script"],
                "total_runs": r["total"],
                "failures": r["fails"],
                "failure_rate": round(rate, 3),
                "avg_duration_ms": round(r["avg_ms"] or 0, 1),
                "severity": "critical" if rate >= 0.8 else "warning",
            })
    return sorted(failures, key=lambda x: -x["failure_rate"])


def detect_slow_patterns(conn):
    """Scripts with average duration above threshold."""
    cur = conn.execute(
        "SELECT script, COUNT(*) as total, AVG(duration_ms) as avg_ms, "
        "MAX(duration_ms) as max_ms, MIN(duration_ms) as min_ms "
        "FROM cowork_execution_log GROUP BY script "
        "HAVING avg_ms > ? AND total >= ?",
        (SLOW_THRESHOLD_MS, MIN_RUNS_FOR_ANALYSIS),
    )
    return [{
        "script": r["script"],
        "avg_duration_ms": round(r["avg_ms"], 1),
        "max_duration_ms": round(r["max_ms"] or 0, 1),
        "min_duration_ms": round(r["min_ms"] or 0, 1),
        "total_runs": r["total"],
        "suggestion": "Consider caching, async, or splitting into sub-tasks",
    } for r in cur]


def detect_unused_scripts(conn):
    """Scripts in mapping but never executed."""
    try:
        mapped = conn.execute(
            "SELECT key FROM memories WHERE category='cowork_script'"
        ).fetchall()
    except sqlite3.Error:
        mapped = []
    if not mapped:
        return []
    executed = {r["script"] for r in conn.execute(
        "SELECT DISTINCT script FROM cowork_execution_log"
    ).fetchall()}
    unused = []
    for r in mapped:
        name = r["key"]
        if name not in executed and not any(name in e for e in executed):
            unused.append({"script": name, "suggestion": "Never executed — remove or schedule"})
    return unused


def detect_cluster_instability(conn):
    """Nodes with high DOWN ratio."""
    cur = conn.execute(
        "SELECT node, COUNT(*) as total, "
        "SUM(CASE WHEN status='DOWN' THEN 1 ELSE 0 END) as downs, "
        "SUM(CASE WHEN status='OK' THEN 1 ELSE 0 END) as ups "
        "FROM cluster_health GROUP BY node"
    )
    unstable = []
    for r in cur:
        total = r["total"]
        down_rate = r["downs"] / total if total else 0
        if down_rate > 0.3:
            unstable.append({
                "node": r["node"],
                "total_checks": total,
                "down_count": r["downs"],
                "up_count": r["ups"],
                "down_rate": round(down_rate, 3),
                "severity": "critical" if down_rate >= 0.7 else "warning",
                "suggestion": "Check service status or remove from routing",
            })
    return sorted(unstable, key=lambda x: -x["down_rate"])


def generate_optimizations(failures, slow, unused, unstable):
    """Aggregate suggestions."""
    opts = []
    for f in failures:
        opts.append(f"Fix {f['script']} — {f['failure_rate']*100:.0f}% failure rate")
    for s in slow:
        opts.append(f"Optimize {s['script']} — avg {s['avg_duration_ms']:.0f}ms")
    for u in unused[:5]:
        opts.append(f"Remove unused {u['script']}")
    for n in unstable:
        opts.append(f"Stabilize {n['node']} — {n['down_rate']*100:.0f}% downtime")
    return opts


def cmd_once(conn):
    failures = detect_failures(conn)
    slow = detect_slow_patterns(conn)
    unused = detect_unused_scripts(conn)
    unstable = detect_cluster_instability(conn)
    optimizations = generate_optimizations(failures, slow, unused, unstable)
    return {
        "mode": "once",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repeated_failures": failures,
        "slow_patterns": slow,
        "unused_scripts": unused,
        "cluster_instability": unstable,
        "optimizations": optimizations,
        "summary": {
            "failure_count": len(failures),
            "slow_count": len(slow),
            "unused_count": len(unused),
            "unstable_nodes": len(unstable),
            "total_suggestions": len(optimizations),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Pattern Detector — etoile.db analysis")
    parser.add_argument("--once", action="store_true", required=True,
                        help="Single analysis pass, JSON output")
    parser.parse_args()

    conn = get_db()
    try:
        result = cmd_once(conn)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
