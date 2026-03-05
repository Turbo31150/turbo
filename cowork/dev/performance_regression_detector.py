#!/usr/bin/env python3
"""performance_regression_detector.py

Compare benchmarks over time and detect performance regressions.

Fonctionnalites :
* Lit les donnees de benchmark depuis etoile.db (table benchmark_runs)
* Detecte les regressions de performance (ralentissement > seuil configurable)
* Suit les metriques : latence, debit (tok/s), taux de succes
* Compare les periodes recentes vs historiques
* Enregistre les regressions detectees dans SQLite (cowork_gaps.db)
* Produit un rapport JSON

CLI :
    --once          : analyse et affiche le resume JSON
    --compare       : comparaison detaillee entre periodes
    --threshold 10  : seuil de regression en % (defaut: 10)

Stdlib-only (sqlite3, json, argparse, statistics).
"""

import argparse
import json
import os
import sqlite3
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path(r"F:/BUREAU/turbo/data/etoile.db")

DEFAULT_THRESHOLD = 10.0  # percent

# Metrics to track and compare
METRICS = [
    "latency_ms",
    "tokens_per_sec",
    "success_rate",
    "throughput",
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS perf_regressions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node TEXT NOT NULL,
            metric TEXT NOT NULL,
            baseline_value REAL NOT NULL,
            current_value REAL NOT NULL,
            change_pct REAL NOT NULL,
            threshold_pct REAL NOT NULL,
            is_regression INTEGER NOT NULL,
            severity TEXT NOT NULL DEFAULT 'warning'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS perf_regression_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            benchmarks_analyzed INTEGER NOT NULL,
            regressions_found INTEGER NOT NULL,
            improvements_found INTEGER NOT NULL,
            threshold_pct REAL NOT NULL,
            duration_ms INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS perf_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            source TEXT DEFAULT 'etoile'
        )
    """)
    conn.commit()


def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn

# ---------------------------------------------------------------------------
# Benchmark Data Loading
# ---------------------------------------------------------------------------
def load_benchmarks_from_etoile() -> list[dict]:
    """Load benchmark data from etoile.db."""
    if not ETOILE_DB.exists():
        return []

    benchmarks = []
    try:
        econn = sqlite3.connect(str(ETOILE_DB))
        econn.row_factory = sqlite3.Row

        # Try multiple possible table schemas
        for query in [
            """SELECT * FROM benchmark_runs ORDER BY timestamp DESC LIMIT 200""",
            """SELECT * FROM benchmarks ORDER BY timestamp DESC LIMIT 200""",
            """SELECT * FROM benchmark_results ORDER BY created_at DESC LIMIT 200""",
        ]:
            try:
                rows = econn.execute(query).fetchall()
                if rows:
                    benchmarks = [dict(r) for r in rows]
                    break
            except sqlite3.OperationalError:
                continue

        econn.close()
    except Exception as e:
        return [{"error": str(e)}]

    return benchmarks


def load_benchmarks_from_cowork() -> list[dict]:
    """Load any previously saved performance snapshots."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM perf_snapshots ORDER BY timestamp DESC LIMIT 500
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def extract_metrics(benchmark: dict) -> dict:
    """Extract standardized metrics from a benchmark record."""
    metrics = {}

    # Try various field names for latency
    for key in ["latency_ms", "latency", "avg_latency", "response_time", "avg_response_ms"]:
        if key in benchmark and benchmark[key] is not None:
            try:
                metrics["latency_ms"] = float(benchmark[key])
            except (ValueError, TypeError):
                pass
            break

    # Tokens per second
    for key in ["tokens_per_sec", "tok_per_sec", "tps", "throughput_tps", "avg_tps"]:
        if key in benchmark and benchmark[key] is not None:
            try:
                metrics["tokens_per_sec"] = float(benchmark[key])
            except (ValueError, TypeError):
                pass
            break

    # Success rate
    for key in ["success_rate", "accuracy", "pass_rate", "ok_rate"]:
        if key in benchmark and benchmark[key] is not None:
            try:
                metrics["success_rate"] = float(benchmark[key])
            except (ValueError, TypeError):
                pass
            break

    # Throughput
    for key in ["throughput", "req_per_sec", "rps"]:
        if key in benchmark and benchmark[key] is not None:
            try:
                metrics["throughput"] = float(benchmark[key])
            except (ValueError, TypeError):
                pass
            break

    # Node name
    for key in ["node", "agent", "model", "node_name"]:
        if key in benchmark and benchmark[key]:
            metrics["_node"] = str(benchmark[key])
            break

    # Timestamp
    for key in ["timestamp", "created_at", "date", "run_date"]:
        if key in benchmark and benchmark[key]:
            metrics["_timestamp"] = str(benchmark[key])
            break

    return metrics


def split_baseline_current(benchmarks: list[dict], split_pct: float = 0.5) -> tuple:
    """Split benchmarks into baseline (older) and current (recent) periods."""
    if len(benchmarks) < 4:
        # Need at least 2 in each group
        mid = max(1, len(benchmarks) // 2)
        return benchmarks[mid:], benchmarks[:mid]

    mid = int(len(benchmarks) * split_pct)
    baseline = benchmarks[mid:]  # older entries (later in desc-sorted list)
    current = benchmarks[:mid]   # recent entries
    return baseline, current


def compute_regression(baseline_values: list[float], current_values: list[float],
                       metric: str, threshold: float) -> dict:
    """Compare baseline vs current for a single metric."""
    if not baseline_values or not current_values:
        return None

    base_mean = statistics.mean(baseline_values)
    curr_mean = statistics.mean(current_values)

    if base_mean == 0:
        return None

    # For latency, higher is worse (regression = increase)
    # For throughput/tps/success_rate, lower is worse (regression = decrease)
    higher_is_worse = metric in ("latency_ms",)

    if higher_is_worse:
        change_pct = ((curr_mean - base_mean) / abs(base_mean)) * 100
        is_regression = change_pct > threshold
        is_improvement = change_pct < -threshold
    else:
        change_pct = ((curr_mean - base_mean) / abs(base_mean)) * 100
        is_regression = change_pct < -threshold
        is_improvement = change_pct > threshold

    # Severity
    abs_change = abs(change_pct)
    if abs_change > threshold * 3:
        severity = "critical"
    elif abs_change > threshold * 2:
        severity = "high"
    elif abs_change > threshold:
        severity = "warning"
    else:
        severity = "info"

    base_stdev = statistics.stdev(baseline_values) if len(baseline_values) > 1 else 0
    curr_stdev = statistics.stdev(current_values) if len(current_values) > 1 else 0

    return {
        "metric": metric,
        "baseline_mean": round(base_mean, 3),
        "baseline_stdev": round(base_stdev, 3),
        "baseline_samples": len(baseline_values),
        "current_mean": round(curr_mean, 3),
        "current_stdev": round(curr_stdev, 3),
        "current_samples": len(current_values),
        "change_pct": round(change_pct, 2),
        "is_regression": is_regression,
        "is_improvement": is_improvement,
        "severity": severity if is_regression else "ok",
    }

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def action_once(threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Analyze benchmarks and detect regressions."""
    start_ms = int(time.time() * 1000)
    conn = get_db()

    benchmarks = load_benchmarks_from_etoile()
    cowork_data = load_benchmarks_from_cowork()

    result = {
        "timestamp": datetime.now().isoformat(),
        "action": "detect",
        "threshold_pct": threshold,
        "benchmarks_loaded": len(benchmarks),
        "cowork_snapshots": len(cowork_data),
        "regressions": [],
        "improvements": [],
        "stable": [],
        "per_node": {},
    }

    if not benchmarks:
        result["warning"] = "No benchmark data found in etoile.db"
        duration_ms = int(time.time() * 1000) - start_ms
        result["duration_ms"] = duration_ms

        conn.execute("""
            INSERT INTO perf_regression_runs
            (timestamp, benchmarks_analyzed, regressions_found, improvements_found,
             threshold_pct, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (result["timestamp"], 0, 0, 0, threshold, duration_ms))
        conn.commit()
        conn.close()
        return result

    # Extract metrics from all benchmarks
    parsed = []
    for b in benchmarks:
        m = extract_metrics(b)
        if m:
            parsed.append(m)

    # Group by node
    by_node = {}
    for m in parsed:
        node = m.get("_node", "unknown")
        by_node.setdefault(node, []).append(m)

    regression_count = 0
    improvement_count = 0

    for node, node_data in by_node.items():
        baseline, current = split_baseline_current(node_data)
        node_results = {}

        for metric in METRICS:
            base_vals = [d[metric] for d in baseline if metric in d]
            curr_vals = [d[metric] for d in current if metric in d]

            comparison = compute_regression(base_vals, curr_vals, metric, threshold)
            if comparison is None:
                continue

            comparison["node"] = node
            node_results[metric] = comparison

            if comparison["is_regression"]:
                result["regressions"].append(comparison)
                regression_count += 1

                # Persist regression
                conn.execute("""
                    INSERT INTO perf_regressions
                    (timestamp, node, metric, baseline_value, current_value,
                     change_pct, threshold_pct, is_regression, severity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result["timestamp"], node, metric,
                    comparison["baseline_mean"], comparison["current_mean"],
                    comparison["change_pct"], threshold, 1, comparison["severity"],
                ))
            elif comparison["is_improvement"]:
                result["improvements"].append(comparison)
                improvement_count += 1
            else:
                result["stable"].append(comparison)

            # Save current snapshot
            if curr_vals:
                conn.execute("""
                    INSERT INTO perf_snapshots
                    (timestamp, node, metric, value, source)
                    VALUES (?, ?, ?, ?, ?)
                """, (result["timestamp"], node, metric,
                      statistics.mean(curr_vals), "etoile"))

        result["per_node"][node] = node_results

    duration_ms = int(time.time() * 1000) - start_ms
    result["duration_ms"] = duration_ms
    result["regression_count"] = regression_count
    result["improvement_count"] = improvement_count
    result["stable_count"] = len(result["stable"])

    # Persist run
    conn.execute("""
        INSERT INTO perf_regression_runs
        (timestamp, benchmarks_analyzed, regressions_found, improvements_found,
         threshold_pct, duration_ms)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (result["timestamp"], len(benchmarks), regression_count,
          improvement_count, threshold, duration_ms))

    conn.commit()
    conn.close()
    return result


def action_compare(threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Detailed comparison between periods."""
    conn = get_db()

    # Get historical regression data
    regressions = conn.execute("""
        SELECT * FROM perf_regressions ORDER BY timestamp DESC LIMIT 100
    """).fetchall()

    runs = conn.execute("""
        SELECT * FROM perf_regression_runs ORDER BY timestamp DESC LIMIT 20
    """).fetchall()

    # Trend analysis: are regressions increasing?
    snapshots = conn.execute("""
        SELECT node, metric,
               AVG(value) as avg_val,
               MIN(value) as min_val,
               MAX(value) as max_val,
               COUNT(*) as samples
        FROM perf_snapshots
        GROUP BY node, metric
        ORDER BY node, metric
    """).fetchall()

    conn.close()

    # Build trend data
    trends = {}
    for s in snapshots:
        s = dict(s)
        node = s["node"]
        trends.setdefault(node, {})[s["metric"]] = {
            "avg": round(s["avg_val"], 3),
            "min": round(s["min_val"], 3),
            "max": round(s["max_val"], 3),
            "samples": s["samples"],
            "range_pct": round(
                (s["max_val"] - s["min_val"]) / max(abs(s["avg_val"]), 0.001) * 100, 1
            ),
        }

    return {
        "timestamp": datetime.now().isoformat(),
        "action": "compare",
        "threshold_pct": threshold,
        "total_regressions_recorded": len(regressions),
        "recent_regressions": [dict(r) for r in regressions[:20]],
        "run_history": [dict(r) for r in runs],
        "metric_trends": trends,
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Compare benchmarks over time and detect performance regressions."
    )
    parser.add_argument("--once", action="store_true",
                        help="Analyze benchmarks and detect regressions, output JSON")
    parser.add_argument("--compare", action="store_true",
                        help="Detailed comparison between baseline and current periods")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"Regression threshold in percent (default: {DEFAULT_THRESHOLD})")
    args = parser.parse_args()

    if not any([args.once, args.compare]):
        parser.print_help()
        sys.exit(1)

    if args.compare:
        result = action_compare(threshold=args.threshold)
    elif args.once:
        result = action_once(threshold=args.threshold)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
