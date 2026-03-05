#!/usr/bin/env python3
"""performance_regression_detector.py — Detect performance regressions in dispatch metrics.

Compares recent dispatch metrics (last 100 per pattern) against a baseline
(previous 100 per pattern) to surface success-rate drops, latency spikes,
and quality degradation.  Results are stored in cowork_gaps.db and printed
as JSON to stdout.

CLI:
    --once       : detect regressions now
    --history    : show past detection results
    --stats      : summary of all regressions found

Stdlib-only (sqlite3, json, argparse, statistics).
"""

import argparse
import json
import math
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev

PYTHON = sys.executable
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")

# Thresholds for regression detection
THRESH_SUCCESS_DROP = 0.10      # >10% success-rate drop
THRESH_LATENCY_INCREASE = 0.30  # >30% latency increase
THRESH_QUALITY_DROP = 0.15      # >15% quality drop
WINDOW = 100                    # dispatches per window
Z_SIGNIFICANCE = 1.96           # 95% confidence


# -- DB helpers ----------------------------------------------------------------

def init_gaps_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(GAPS_DB))
    db.execute("""CREATE TABLE IF NOT EXISTS performance_regressions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp       TEXT NOT NULL,
        metric          TEXT NOT NULL,
        pattern         TEXT NOT NULL,
        baseline_value  REAL NOT NULL,
        current_value   REAL NOT NULL,
        regression_pct  REAL NOT NULL,
        severity        TEXT NOT NULL
    )""")
    db.commit()
    return db


def open_etoile() -> sqlite3.Connection:
    if not ETOILE_DB.exists():
        print(json.dumps({"error": f"etoile.db not found at {ETOILE_DB}"}))
        sys.exit(1)
    return sqlite3.connect(str(ETOILE_DB))


# -- Statistics ----------------------------------------------------------------

def safe_mean(vals: list) -> float:
    return mean(vals) if vals else 0.0


def safe_stdev(vals: list) -> float:
    if len(vals) < 2:
        return 0.0
    return stdev(vals)


def z_score(baseline_vals: list, current_vals: list) -> float:
    """Two-sample z-score approximation for mean difference."""
    n1, n2 = len(baseline_vals), len(current_vals)
    if n1 < 2 or n2 < 2:
        return 0.0
    m1, m2 = mean(baseline_vals), mean(current_vals)
    s1, s2 = stdev(baseline_vals), stdev(current_vals)
    se = math.sqrt((s1 ** 2 / n1) + (s2 ** 2 / n2))
    if se == 0:
        return 0.0
    return (m2 - m1) / se


def severity_label(pct: float) -> str:
    abs_pct = abs(pct)
    if abs_pct > 0.40:
        return "severe"
    elif abs_pct > 0.20:
        return "moderate"
    return "minor"


# -- Data loading --------------------------------------------------------------

def load_dispatches_by_pattern(edb: sqlite3.Connection) -> dict:
    """Load all dispatches grouped by classified_type, ordered newest first."""
    cur = edb.execute("""
        SELECT id, timestamp, classified_type, node, latency_ms, success, quality_score
        FROM agent_dispatch_log
        ORDER BY id DESC
    """)
    cols = [d[0] for d in cur.description]
    by_pattern = {}
    for row in cur:
        rec = dict(zip(cols, row))
        pat = rec["classified_type"] or "unknown"
        by_pattern.setdefault(pat, []).append(rec)
    return by_pattern


def load_dispatches_by_node(edb: sqlite3.Connection) -> dict:
    """Load all dispatches grouped by node, ordered newest first."""
    cur = edb.execute("""
        SELECT id, timestamp, classified_type, node, latency_ms, success, quality_score
        FROM agent_dispatch_log
        ORDER BY id DESC
    """)
    cols = [d[0] for d in cur.description]
    by_node = {}
    for row in cur:
        rec = dict(zip(cols, row))
        node = rec["node"] or "unknown"
        by_node.setdefault(node, []).append(rec)
    return by_node


# -- Regression detection ------------------------------------------------------

def compare_windows(baseline: list, current: list, label: str) -> list:
    """Compare two windows of dispatches and return detected regressions."""
    regressions = []

    if not baseline or not current:
        return regressions

    # --- Success rate ---
    bl_success = [float(r["success"] or 0) for r in baseline]
    cu_success = [float(r["success"] or 0) for r in current]
    bl_rate = safe_mean(bl_success)
    cu_rate = safe_mean(cu_success)

    if bl_rate > 0:
        drop = (bl_rate - cu_rate) / bl_rate
        if drop > THRESH_SUCCESS_DROP:
            z = z_score(bl_success, cu_success)
            if abs(z) >= Z_SIGNIFICANCE:
                regressions.append({
                    "metric": "success_rate",
                    "pattern": label,
                    "baseline_value": round(bl_rate, 4),
                    "current_value": round(cu_rate, 4),
                    "regression_pct": round(drop, 4),
                    "severity": severity_label(drop),
                    "z_score": round(z, 3),
                    "baseline_n": len(baseline),
                    "current_n": len(current),
                })

    # --- Latency (only successful dispatches) ---
    bl_lat = [r["latency_ms"] for r in baseline
              if r["success"] and r["latency_ms"] is not None]
    cu_lat = [r["latency_ms"] for r in current
              if r["success"] and r["latency_ms"] is not None]

    if bl_lat and cu_lat:
        bl_avg = safe_mean(bl_lat)
        cu_avg = safe_mean(cu_lat)
        if bl_avg > 0:
            increase = (cu_avg - bl_avg) / bl_avg
            if increase > THRESH_LATENCY_INCREASE:
                z = z_score(bl_lat, cu_lat)
                if abs(z) >= Z_SIGNIFICANCE:
                    regressions.append({
                        "metric": "latency_ms",
                        "pattern": label,
                        "baseline_value": round(bl_avg, 2),
                        "current_value": round(cu_avg, 2),
                        "regression_pct": round(increase, 4),
                        "severity": severity_label(increase),
                        "z_score": round(z, 3),
                        "baseline_n": len(bl_lat),
                        "current_n": len(cu_lat),
                    })

    # --- Quality score ---
    bl_qual = [r["quality_score"] for r in baseline
               if r["quality_score"] is not None]
    cu_qual = [r["quality_score"] for r in current
               if r["quality_score"] is not None]

    if bl_qual and cu_qual:
        bl_avg_q = safe_mean(bl_qual)
        cu_avg_q = safe_mean(cu_qual)
        if bl_avg_q > 0:
            q_drop = (bl_avg_q - cu_avg_q) / bl_avg_q
            if q_drop > THRESH_QUALITY_DROP:
                z = z_score(bl_qual, cu_qual)
                if abs(z) >= Z_SIGNIFICANCE:
                    regressions.append({
                        "metric": "quality_score",
                        "pattern": label,
                        "baseline_value": round(bl_avg_q, 4),
                        "current_value": round(cu_avg_q, 4),
                        "regression_pct": round(q_drop, 4),
                        "severity": severity_label(q_drop),
                        "z_score": round(z, 3),
                        "baseline_n": len(bl_qual),
                        "current_n": len(cu_qual),
                    })

    return regressions


def detect_improvements(baseline: list, current: list, label: str) -> list:
    """Detect patterns that improved (inverse of regression)."""
    improvements = []

    if not baseline or not current:
        return improvements

    # --- Success rate improvement ---
    bl_success = [float(r["success"] or 0) for r in baseline]
    cu_success = [float(r["success"] or 0) for r in current]
    bl_rate = safe_mean(bl_success)
    cu_rate = safe_mean(cu_success)

    if bl_rate > 0 and cu_rate > bl_rate:
        gain = (cu_rate - bl_rate) / bl_rate
        if gain > 0.05:  # >5% improvement
            improvements.append({
                "metric": "success_rate",
                "pattern": label,
                "baseline_value": round(bl_rate, 4),
                "current_value": round(cu_rate, 4),
                "improvement_pct": round(gain, 4),
            })

    # --- Latency improvement (decrease) ---
    bl_lat = [r["latency_ms"] for r in baseline
              if r["success"] and r["latency_ms"] is not None]
    cu_lat = [r["latency_ms"] for r in current
              if r["success"] and r["latency_ms"] is not None]
    if bl_lat and cu_lat:
        bl_avg = safe_mean(bl_lat)
        cu_avg = safe_mean(cu_lat)
        if bl_avg > 0:
            decrease = (bl_avg - cu_avg) / bl_avg
            if decrease > 0.10:  # >10% faster
                improvements.append({
                    "metric": "latency_ms",
                    "pattern": label,
                    "baseline_value": round(bl_avg, 2),
                    "current_value": round(cu_avg, 2),
                    "improvement_pct": round(decrease, 4),
                })

    # --- Quality improvement ---
    bl_qual = [r["quality_score"] for r in baseline
               if r["quality_score"] is not None]
    cu_qual = [r["quality_score"] for r in current
               if r["quality_score"] is not None]
    if bl_qual and cu_qual:
        bl_avg_q = safe_mean(bl_qual)
        cu_avg_q = safe_mean(cu_qual)
        if bl_avg_q > 0 and cu_avg_q > bl_avg_q:
            q_gain = (cu_avg_q - bl_avg_q) / bl_avg_q
            if q_gain > 0.05:
                improvements.append({
                    "metric": "quality_score",
                    "pattern": label,
                    "baseline_value": round(bl_avg_q, 4),
                    "current_value": round(cu_avg_q, 4),
                    "improvement_pct": round(q_gain, 4),
                })

    return improvements


# -- CLI commands --------------------------------------------------------------

def cmd_once() -> None:
    """Run a single regression detection pass."""
    edb = open_etoile()
    gdb = init_gaps_db()
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    all_regressions = []
    all_improvements = []

    # Per-pattern analysis
    by_pattern = load_dispatches_by_pattern(edb)
    for pattern, records in by_pattern.items():
        if len(records) < WINDOW:
            continue
        current = records[:WINDOW]              # newest WINDOW
        baseline = records[WINDOW:2 * WINDOW]   # previous WINDOW
        if len(baseline) < WINDOW // 2:
            continue
        all_regressions.extend(
            compare_windows(baseline, current, "pattern:" + pattern))
        all_improvements.extend(
            detect_improvements(baseline, current, "pattern:" + pattern))

    # Per-node analysis
    by_node = load_dispatches_by_node(edb)
    for node, records in by_node.items():
        if len(records) < WINDOW:
            continue
        current = records[:WINDOW]
        baseline = records[WINDOW:2 * WINDOW]
        if len(baseline) < WINDOW // 2:
            continue
        all_regressions.extend(
            compare_windows(baseline, current, "node:" + node))
        all_improvements.extend(
            detect_improvements(baseline, current, "node:" + node))

    edb.close()

    # Store regressions
    for reg in all_regressions:
        gdb.execute(
            """INSERT INTO performance_regressions
               (timestamp, metric, pattern, baseline_value, current_value,
                regression_pct, severity)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (now, reg["metric"], reg["pattern"],
             reg["baseline_value"], reg["current_value"],
             reg["regression_pct"], reg["severity"]))
    gdb.commit()
    gdb.close()

    # Build severity / metric breakdowns
    by_severity = {}
    by_metric = {}
    for r in all_regressions:
        by_severity[r["severity"]] = by_severity.get(r["severity"], 0) + 1
        by_metric[r["metric"]] = by_metric.get(r["metric"], 0) + 1

    # Top 5 worst regressions (highest regression_pct)
    worst = sorted(all_regressions,
                   key=lambda r: r["regression_pct"], reverse=True)[:5]

    result = {
        "timestamp": now,
        "regressions_found": len(all_regressions),
        "by_severity": by_severity,
        "by_metric": by_metric,
        "worst_regressions": worst,
        "improving_patterns": all_improvements,
        "patterns_analyzed": len(
            [p for p, recs in by_pattern.items() if len(recs) >= WINDOW]),
        "nodes_analyzed": len(
            [n for n, recs in by_node.items() if len(recs) >= WINDOW]),
        "window_size": WINDOW,
    }

    print(json.dumps(result, indent=2))


def cmd_history() -> None:
    """Show past detection results."""
    gdb = init_gaps_db()
    cur = gdb.execute("""
        SELECT id, timestamp, metric, pattern, baseline_value, current_value,
               regression_pct, severity
        FROM performance_regressions
        ORDER BY id DESC
        LIMIT 50
    """)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    gdb.close()

    result = {
        "total_shown": len(rows),
        "regressions": rows,
    }
    print(json.dumps(result, indent=2))


def cmd_stats() -> None:
    """Summary statistics of all detected regressions."""
    gdb = init_gaps_db()

    total = gdb.execute(
        "SELECT COUNT(*) FROM performance_regressions").fetchone()[0]

    by_severity = {}
    for row in gdb.execute(
        "SELECT severity, COUNT(*) FROM performance_regressions "
        "GROUP BY severity"
    ):
        by_severity[row[0]] = row[1]

    by_metric = {}
    for row in gdb.execute(
        "SELECT metric, COUNT(*) FROM performance_regressions "
        "GROUP BY metric"
    ):
        by_metric[row[0]] = row[1]

    by_pattern = {}
    for row in gdb.execute(
        "SELECT pattern, COUNT(*) FROM performance_regressions "
        "GROUP BY pattern ORDER BY COUNT(*) DESC LIMIT 10"
    ):
        by_pattern[row[0]] = row[1]

    avg_regression = gdb.execute(
        "SELECT AVG(regression_pct) FROM performance_regressions"
    ).fetchone()[0]

    worst_ever = None
    row = gdb.execute(
        "SELECT metric, pattern, baseline_value, current_value, "
        "regression_pct, severity, timestamp "
        "FROM performance_regressions ORDER BY regression_pct DESC LIMIT 1"
    ).fetchone()
    if row:
        worst_ever = {
            "metric": row[0], "pattern": row[1],
            "baseline_value": row[2], "current_value": row[3],
            "regression_pct": row[4], "severity": row[5],
            "timestamp": row[6],
        }

    recent_count = gdb.execute(
        "SELECT COUNT(*) FROM performance_regressions "
        "WHERE timestamp >= datetime('now', '-24 hours')"
    ).fetchone()[0]

    gdb.close()

    result = {
        "total_regressions_detected": total,
        "by_severity": by_severity,
        "by_metric": by_metric,
        "top_affected_patterns": by_pattern,
        "avg_regression_pct": round(avg_regression, 4) if avg_regression else 0.0,
        "worst_ever": worst_ever,
        "last_24h_count": recent_count,
    }
    print(json.dumps(result, indent=2))


# -- Main ----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect performance regressions in dispatch metrics.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true",
                       help="Run regression detection")
    group.add_argument("--history", action="store_true",
                       help="Show past detections")
    group.add_argument("--stats", action="store_true",
                       help="Summary statistics")
    args = parser.parse_args()

    if args.once:
        cmd_once()
    elif args.history:
        cmd_history()
    elif args.stats:
        cmd_stats()


if __name__ == "__main__":
    main()
