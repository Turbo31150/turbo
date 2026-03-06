#!/usr/bin/env python3
"""benchmark_trend_analyzer.py — Reads benchmark_results from etoile.db and reports trends.

Analyzes benchmark data over time to detect:
- Improving or degrading node performance
- Score trends per agent/model
- Latency changes
- Anomalies (sudden drops or spikes)

Usage:
    python dev/benchmark_trend_analyzer.py --once
    python dev/benchmark_trend_analyzer.py --once --days 30
    python dev/benchmark_trend_analyzer.py --dry-run
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TURBO_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = TURBO_DIR / "data"
ETOILE_DB = TURBO_DIR / "etoile.db"


def get_benchmark_tables(db_path: Path) -> list:
    """Find benchmark-related tables in etoile.db."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    benchmark_tables = [
        t for t in tables
        if "benchmark" in t.lower() or "dispatch" in t.lower() or "score" in t.lower()
    ]
    return benchmark_tables


def fetch_benchmark_data(db_path: Path, days: int = 30) -> dict:
    """Fetch benchmark records from all relevant tables."""
    if not db_path.exists():
        return {"tables": {}, "error": f"Database not found: {db_path}"}

    conn = sqlite3.connect(str(db_path))
    results = {}

    tables = get_benchmark_tables(db_path)

    for table in tables:
        try:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]

            # Find date/timestamp column
            date_col = None
            for col in columns:
                cl = col.lower()
                if cl in ("timestamp", "created_at", "date", "run_date", "created", "ts"):
                    date_col = col
                    break

            # Fetch data
            if date_col:
                cutoff = (datetime.now() - timedelta(days=days)).isoformat()
                try:
                    cursor = conn.execute(
                        f"SELECT * FROM {table} WHERE {date_col} >= ? ORDER BY {date_col}",
                        (cutoff,),
                    )
                except sqlite3.OperationalError:
                    cursor = conn.execute(f"SELECT * FROM {table} ORDER BY rowid")
            else:
                cursor = conn.execute(f"SELECT * FROM {table} ORDER BY rowid")

            rows = cursor.fetchall()
            results[table] = {
                "columns": columns,
                "rows": [dict(zip(columns, row)) for row in rows],
                "count": len(rows),
                "date_column": date_col,
            }
        except sqlite3.OperationalError as e:
            results[table] = {"error": str(e), "count": 0}

    conn.close()
    return {"tables": results}


def compute_trends(data: dict) -> list:
    """Compute trends from benchmark data."""
    trends = []

    for table_name, table_data in data.get("tables", {}).items():
        if "error" in table_data or table_data["count"] < 2:
            continue

        rows = table_data["rows"]
        columns = table_data["columns"]

        # Find numeric columns that could be scores/latencies
        numeric_cols = []
        for col in columns:
            cl = col.lower()
            if any(kw in cl for kw in ("score", "latency", "time", "quality",
                                        "success", "rate", "tok", "speed",
                                        "accuracy", "result")):
                # Check if values are actually numeric
                values = [r.get(col) for r in rows if r.get(col) is not None]
                numeric_values = []
                for v in values:
                    try:
                        numeric_values.append(float(v))
                    except (ValueError, TypeError):
                        pass
                if len(numeric_values) >= 2:
                    numeric_cols.append((col, numeric_values))

        # Find node/model column for grouping
        group_col = None
        for col in columns:
            cl = col.lower()
            if cl in ("node", "agent", "model", "node_id", "agent_id", "name"):
                group_col = col
                break

        for col_name, values in numeric_cols:
            n = len(values)
            first_half = values[: n // 2]
            second_half = values[n // 2:]

            avg_first = sum(first_half) / len(first_half) if first_half else 0
            avg_second = sum(second_half) / len(second_half) if second_half else 0

            if avg_first == 0:
                pct_change = 0
            else:
                pct_change = ((avg_second - avg_first) / abs(avg_first)) * 100

            # Determine trend direction
            if abs(pct_change) < 5:
                direction = "stable"
            elif pct_change > 0:
                # For latency, higher is worse; for score, higher is better
                if "latency" in col_name.lower() or "time" in col_name.lower():
                    direction = "degrading"
                else:
                    direction = "improving"
            else:
                if "latency" in col_name.lower() or "time" in col_name.lower():
                    direction = "improving"
                else:
                    direction = "degrading"

            # Detect anomalies (values > 2 std deviations)
            mean_val = sum(values) / len(values)
            variance = sum((v - mean_val) ** 2 for v in values) / len(values)
            std_dev = variance ** 0.5
            anomalies = []
            if std_dev > 0:
                for i, v in enumerate(values):
                    z_score = abs(v - mean_val) / std_dev
                    if z_score > 2.0:
                        anomalies.append({
                            "index": i,
                            "value": round(v, 3),
                            "z_score": round(z_score, 2),
                        })

            trends.append({
                "table": table_name,
                "metric": col_name,
                "direction": direction,
                "samples": n,
                "avg_first_half": round(avg_first, 3),
                "avg_second_half": round(avg_second, 3),
                "pct_change": round(pct_change, 1),
                "min": round(min(values), 3),
                "max": round(max(values), 3),
                "current": round(values[-1], 3),
                "anomalies": len(anomalies),
                "anomaly_details": anomalies[:5],  # Top 5
            })

    return trends


def main():
    parser = argparse.ArgumentParser(
        description="Analyze benchmark trends from etoile.db"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without side effects")
    parser.add_argument("--days", type=int, default=30, help="Look back N days (default: 30)")
    parser.add_argument("--db", type=str, default=None, help="Path to etoile.db")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else ETOILE_DB

    if not db_path.exists():
        print(json.dumps({
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": f"Database not found: {db_path}",
        }))
        sys.exit(1)

    # Fetch data
    data = fetch_benchmark_data(db_path, days=args.days)
    tables_found = [t for t, d in data["tables"].items() if d.get("count", 0) > 0]

    # Compute trends
    trends = compute_trends(data)

    if args.json:
        output = {
            "db": str(db_path),
            "days": args.days,
            "tables_found": tables_found,
            "trends": trends,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        sys.exit(0)

    # Human-readable output
    print("=== Benchmark Trend Analyzer ===")
    print(f"Database: {db_path}")
    print(f"Lookback: {args.days} days")
    print(f"Tables with data: {len(tables_found)}")
    if tables_found:
        for t in tables_found:
            count = data["tables"][t].get("count", 0)
            print(f"  - {t} ({count} records)")
    print()

    if not trends:
        print("No numeric trend data found in benchmark tables.")
        print()
    else:
        # Group by direction
        improving = [t for t in trends if t["direction"] == "improving"]
        degrading = [t for t in trends if t["direction"] == "degrading"]
        stable = [t for t in trends if t["direction"] == "stable"]

        if improving:
            print(f"IMPROVING ({len(improving)}):")
            for t in improving:
                print(
                    f"  [+] {t['table']}.{t['metric']}: "
                    f"{t['avg_first_half']} -> {t['avg_second_half']} "
                    f"({t['pct_change']:+.1f}%, {t['samples']} samples)"
                )
            print()

        if degrading:
            print(f"DEGRADING ({len(degrading)}):")
            for t in degrading:
                print(
                    f"  [-] {t['table']}.{t['metric']}: "
                    f"{t['avg_first_half']} -> {t['avg_second_half']} "
                    f"({t['pct_change']:+.1f}%, {t['samples']} samples)"
                )
            print()

        if stable:
            print(f"STABLE ({len(stable)}):")
            for t in stable:
                print(
                    f"  [=] {t['table']}.{t['metric']}: "
                    f"~{t['avg_second_half']} ({t['pct_change']:+.1f}%)"
                )
            print()

        # Anomalies summary
        total_anomalies = sum(t["anomalies"] for t in trends)
        if total_anomalies > 0:
            print(f"ANOMALIES DETECTED: {total_anomalies} total")
            for t in trends:
                if t["anomalies"] > 0:
                    print(f"  {t['table']}.{t['metric']}: {t['anomalies']} anomalies")
            print()

    result = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "tables_analyzed": len(tables_found),
        "trends_found": len(trends),
        "improving": sum(1 for t in trends if t["direction"] == "improving"),
        "degrading": sum(1 for t in trends if t["direction"] == "degrading"),
        "stable": sum(1 for t in trends if t["direction"] == "stable"),
        "anomalies": sum(t["anomalies"] for t in trends),
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
