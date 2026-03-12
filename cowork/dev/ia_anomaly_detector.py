#!/usr/bin/env python3
"""ia_anomaly_detector.py — Detecteur d'anomalies IA.

Identifie comportements inhabituels dans le cluster.

Usage:
    python dev/ia_anomaly_detector.py --once
    python dev/ia_anomaly_detector.py --scan
    python dev/ia_anomaly_detector.py --baseline
    python dev/ia_anomaly_detector.py --alerts
"""
import argparse
import json
import math
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "anomaly_detector.db"
from _paths import ETOILE_DB


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS baselines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, agent TEXT, metric TEXT,
        mean REAL, stddev REAL, samples INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS anomalies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, agent TEXT, metric TEXT,
        value REAL, expected_mean REAL, deviation REAL,
        severity TEXT)""")
    db.commit()
    return db


def load_metrics():
    """Load recent metrics from etoile.db."""
    metrics = defaultdict(lambda: defaultdict(list))

    if not ETOILE_DB.exists():
        return metrics

    try:
        db = sqlite3.connect(str(ETOILE_DB))
        tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

        if "tool_metrics" in tables:
            rows = db.execute(
                "SELECT node, latency_ms, status FROM tool_metrics WHERE ts > ? ORDER BY ts DESC LIMIT 1000",
                (time.time() - 86400 * 7,)
            ).fetchall()
            for r in rows:
                node = r[0] or "unknown"
                metrics[node]["latency"].append(r[1] or 0)
                metrics[node]["success"].append(1 if r[2] == "ok" else 0)

        db.close()
    except Exception:
        pass

    return metrics


def calculate_baseline(values):
    """Calculate mean and standard deviation."""
    if not values:
        return 0, 0
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / max(n - 1, 1)
    stddev = math.sqrt(variance)
    return round(mean, 2), round(stddev, 2)


def detect_anomalies(metrics):
    """Detect anomalies using mean + 2*stddev."""
    anomalies = []

    for agent, agent_metrics in metrics.items():
        for metric_name, values in agent_metrics.items():
            if len(values) < 5:
                continue

            mean, stddev = calculate_baseline(values)
            threshold_high = mean + 2 * stddev
            threshold_low = mean - 2 * stddev

            # Check recent values (last 10)
            recent = values[:10]
            for val in recent:
                if stddev > 0:
                    deviation = abs(val - mean) / stddev
                    if deviation > 2:
                        severity = "high" if deviation > 3 else "medium"
                        anomalies.append({
                            "agent": agent,
                            "metric": metric_name,
                            "value": val,
                            "mean": mean,
                            "stddev": stddev,
                            "deviation": round(deviation, 2),
                            "severity": severity,
                        })

    return anomalies


def do_scan():
    """Full anomaly scan."""
    db = init_db()
    metrics = load_metrics()
    anomalies = detect_anomalies(metrics)

    # Store baselines
    for agent, agent_metrics in metrics.items():
        for metric_name, values in agent_metrics.items():
            if len(values) >= 5:
                mean, stddev = calculate_baseline(values)
                db.execute(
                    "INSERT INTO baselines (ts, agent, metric, mean, stddev, samples) VALUES (?,?,?,?,?,?)",
                    (time.time(), agent, metric_name, mean, stddev, len(values))
                )

    # Store anomalies
    for a in anomalies:
        db.execute(
            "INSERT INTO anomalies (ts, agent, metric, value, expected_mean, deviation, severity) VALUES (?,?,?,?,?,?,?)",
            (time.time(), a["agent"], a["metric"], a["value"],
             a["mean"], a["deviation"], a["severity"])
        )

    # Unique anomalies by agent+metric
    unique = {}
    for a in anomalies:
        key = f"{a['agent']}_{a['metric']}"
        if key not in unique or a["deviation"] > unique[key]["deviation"]:
            unique[key] = a

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "agents_analyzed": len(metrics),
        "anomalies_detected": len(unique),
        "high_severity": sum(1 for a in unique.values() if a["severity"] == "high"),
        "anomalies": list(unique.values())[:15],
    }


def main():
    parser = argparse.ArgumentParser(description="IA Anomaly Detector")
    parser.add_argument("--once", "--scan", action="store_true", help="Scan for anomalies")
    parser.add_argument("--baseline", action="store_true", help="Show baselines")
    parser.add_argument("--alerts", action="store_true", help="Show alerts")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()

    if args.baseline:
        db = init_db()
        rows = db.execute("SELECT agent, metric, mean, stddev, samples FROM baselines ORDER BY ts DESC LIMIT 20").fetchall()
        db.close()
        print(json.dumps([{"agent": r[0], "metric": r[1], "mean": r[2], "stddev": r[3], "n": r[4]} for r in rows], indent=2))
    elif args.alerts:
        db = init_db()
        rows = db.execute("SELECT ts, agent, metric, deviation, severity FROM anomalies ORDER BY ts DESC LIMIT 20").fetchall()
        db.close()
        print(json.dumps([{
            "ts": datetime.fromtimestamp(r[0]).isoformat(),
            "agent": r[1], "metric": r[2], "deviation": r[3], "severity": r[4],
        } for r in rows], indent=2))
    else:
        result = do_scan()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
