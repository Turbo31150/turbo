#!/usr/bin/env python3
"""Audit dispatch engine stats and report anomalies."""

import argparse
import json
import time
import urllib.request
import urllib.error

STATS_URL = "http://127.0.0.1:9742/api/dispatch_engine/stats"

# Thresholds for anomaly detection
THRESHOLDS = {
    "error_rate_pct": 20.0,
    "avg_latency_s": 10.0,
    "queue_depth": 50,
    "circuit_open_nodes": 1,
}


def fetch(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def detect_anomalies(stats):
    """Scan stats dict for anomalies based on thresholds."""
    anomalies = []

    total = stats.get("total_dispatches", 0)
    errors = stats.get("total_errors", 0)
    if total > 0:
        error_rate = (errors / total) * 100
        if error_rate > THRESHOLDS["error_rate_pct"]:
            anomalies.append({
                "type": "high_error_rate",
                "value": round(error_rate, 1),
                "threshold": THRESHOLDS["error_rate_pct"],
                "detail": f"{errors}/{total} dispatches failed",
            })

    avg_lat = stats.get("avg_latency_s") or stats.get("average_latency")
    if avg_lat and avg_lat > THRESHOLDS["avg_latency_s"]:
        anomalies.append({
            "type": "high_latency",
            "value": round(avg_lat, 2),
            "threshold": THRESHOLDS["avg_latency_s"],
        })

    nodes = stats.get("nodes", stats.get("node_stats", {}))
    if isinstance(nodes, dict):
        open_circuits = [n for n, v in nodes.items()
                         if isinstance(v, dict) and v.get("circuit_open")]
        if len(open_circuits) >= THRESHOLDS["circuit_open_nodes"]:
            anomalies.append({
                "type": "circuit_breakers_open",
                "nodes": open_circuits,
                "count": len(open_circuits),
            })

    queue = stats.get("queue_depth", stats.get("pending_tasks", 0))
    if queue and queue > THRESHOLDS["queue_depth"]:
        anomalies.append({
            "type": "queue_backlog",
            "value": queue,
            "threshold": THRESHOLDS["queue_depth"],
        })

    return anomalies


def run_once():
    stats = fetch(STATS_URL)
    if "error" in stats:
        output = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "UNREACHABLE",
            "error": stats["error"],
            "anomalies": [],
        }
    else:
        anomalies = detect_anomalies(stats)
        output = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "CLEAN" if not anomalies else "ANOMALIES_DETECTED",
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "raw_stats": stats,
        }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Audit dispatch engine stats for anomalies")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        print("Use --once for a single run. Use --help for options.")


if __name__ == "__main__":
    main()
