#!/usr/bin/env python3
"""dispatch_error_analyzer.py — Deep analysis of dispatch errors and null error messages.

Identifies why dispatches fail silently (null error_msg), correlates with
timing patterns, and suggests diagnostic improvements.

CLI:
    --once       : run analysis
    --fix-nulls  : attempt to classify null errors from context
    --stats      : show error distribution

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
    conn.execute("""CREATE TABLE IF NOT EXISTS error_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        dispatch_id INTEGER,
        classified_type TEXT,
        node TEXT,
        inferred_cause TEXT,
        confidence REAL,
        latency_ms REAL
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def analyze_errors():
    """Analyze all dispatch errors, especially null ones."""
    if not ETOILE_DB.exists():
        return {"error": "etoile.db not found"}

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    # All failures
    failures = edb.execute("""
        SELECT id, classified_type, node, model_used, strategy,
               latency_ms, error_msg, quality_score, tokens_in, tokens_out
        FROM agent_dispatch_log
        WHERE success = 0
        ORDER BY id DESC
    """).fetchall()

    # Classify null errors by context
    null_errors = []
    timeout_errors = []
    quality_errors = []
    other_errors = []
    inferred = []

    for f in failures:
        entry = dict(f)
        latency = f["latency_ms"] or 0
        error = f["error_msg"]
        quality = f["quality_score"] or 0
        tokens_out = f["tokens_out"] or 0

        if not error or error == "null":
            # Infer cause from context
            if latency >= 58000:  # Near 60s timeout
                cause = "timeout"
                confidence = 0.95
                timeout_errors.append(entry)
            elif tokens_out == 0:
                cause = "empty_response"
                confidence = 0.85
            elif quality == 0:
                cause = "quality_zero"
                confidence = 0.80
            elif latency < 1000:
                cause = "connection_refused"
                confidence = 0.70
            else:
                cause = "unknown_silent_failure"
                confidence = 0.50

            entry["inferred_cause"] = cause
            entry["confidence"] = confidence
            null_errors.append(entry)
            inferred.append({
                "id": f["id"], "pattern": f["classified_type"],
                "node": f["node"], "cause": cause,
                "confidence": confidence, "latency": round(latency)
            })
        elif "timeout" in str(error).lower():
            entry["inferred_cause"] = "explicit_timeout"
            timeout_errors.append(entry)
        elif "quality" in str(error).lower():
            quality_errors.append(entry)
        else:
            other_errors.append(entry)

    # Cause distribution
    cause_counts = {}
    for inf in inferred:
        c = inf["cause"]
        cause_counts[c] = cause_counts.get(c, 0) + 1

    # Node failure rate
    node_failures = {}
    for f in failures:
        node = f["node"] or "unknown"
        if node not in node_failures:
            node_failures[node] = 0
        node_failures[node] += 1

    # Time pattern (hour distribution)
    hour_dist = {}
    for f in failures:
        ts = f["timestamp"] if "timestamp" in f.keys() else ""
        if "T" in str(ts):
            hour = str(ts).split("T")[1][:2] if len(str(ts)) > 11 else "?"
            hour_dist[hour] = hour_dist.get(hour, 0) + 1

    edb.close()

    return {
        "timestamp": datetime.now().isoformat(),
        "total_failures": len(failures),
        "null_error_count": len(null_errors),
        "null_pct": round(len(null_errors) / max(len(failures), 1) * 100, 1),
        "inferred_causes": cause_counts,
        "node_failure_counts": node_failures,
        "hour_distribution": dict(sorted(hour_dist.items())),
        "top_inferred": inferred[:20],
        "recommendations": _generate_recommendations(cause_counts, node_failures),
    }


def _generate_recommendations(causes, nodes):
    """Generate actionable recommendations."""
    recs = []

    timeout_count = causes.get("timeout", 0)
    if timeout_count > 10:
        recs.append({
            "priority": "high",
            "issue": f"{timeout_count} inferred timeouts",
            "fix": "Increase timeout to 90s for complex patterns (architecture/security/analysis) or add streaming"
        })

    empty_count = causes.get("empty_response", 0)
    if empty_count > 5:
        recs.append({
            "priority": "high",
            "issue": f"{empty_count} empty responses",
            "fix": "Add retry logic with exponential backoff when tokens_out=0"
        })

    conn_count = causes.get("connection_refused", 0)
    if conn_count > 3:
        recs.append({
            "priority": "medium",
            "issue": f"{conn_count} connection refused (<1s latency)",
            "fix": "Add health check before dispatch, skip offline nodes"
        })

    for node, count in nodes.items():
        if count > 20:
            recs.append({
                "priority": "medium",
                "issue": f"{node} has {count} total failures",
                "fix": f"Reduce traffic to {node}, distribute across cluster"
            })

    recs.append({
        "priority": "critical",
        "issue": "Error messages are null for most failures",
        "fix": "Patch smart_dispatcher.py to capture exception text in error_msg column"
    })

    return recs


def fix_null_errors():
    """Backfill inferred error causes into dispatch log."""
    if not ETOILE_DB.exists():
        return {"error": "etoile.db not found"}

    edb = sqlite3.connect(str(ETOILE_DB))
    conn = get_db()

    failures = edb.execute("""
        SELECT id, classified_type, node, latency_ms, tokens_out, quality_score
        FROM agent_dispatch_log
        WHERE success = 0 AND (error_msg IS NULL OR error_msg = '')
    """).fetchall()

    fixed = 0
    ts = datetime.now().isoformat()
    for f in failures:
        latency = f[3] or 0
        tokens_out = f[4] or 0
        quality = f[5] or 0

        if latency >= 58000:
            cause, conf = "timeout", 0.95
        elif tokens_out == 0:
            cause, conf = "empty_response", 0.85
        elif quality == 0:
            cause, conf = "quality_zero", 0.80
        elif latency < 1000:
            cause, conf = "connection_refused", 0.70
        else:
            cause, conf = "unknown", 0.50

        # Update etoile.db with inferred error
        edb.execute("""
            UPDATE agent_dispatch_log
            SET error_msg = ?
            WHERE id = ? AND (error_msg IS NULL OR error_msg = '')
        """, (f"[inferred:{cause}]", f[0]))

        # Log in analysis DB
        conn.execute("""
            INSERT INTO error_analysis
            (timestamp, dispatch_id, classified_type, node, inferred_cause, confidence, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ts, f[0], f[1], f[2], cause, conf, latency))
        fixed += 1

    edb.commit()
    edb.close()
    conn.commit()
    conn.close()

    return {"fixed": fixed, "timestamp": ts}


def action_stats():
    """Show error analysis history."""
    conn = get_db()
    rows = conn.execute("""
        SELECT inferred_cause, COUNT(*) as cnt, AVG(confidence) as avg_conf
        FROM error_analysis
        GROUP BY inferred_cause
        ORDER BY cnt DESC
    """).fetchall()
    conn.close()
    return {"causes": [dict(r) for r in rows]}


def main():
    parser = argparse.ArgumentParser(description="Dispatch Error Analyzer")
    parser.add_argument("--once", action="store_true", help="Run analysis")
    parser.add_argument("--fix-nulls", action="store_true", help="Backfill null errors")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    args = parser.parse_args()

    if not any([args.once, args.fix_nulls, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.fix_nulls:
        result = fix_null_errors()
    elif args.stats:
        result = action_stats()
    else:
        result = analyze_errors()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
