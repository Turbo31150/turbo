#!/usr/bin/env python3
"""IA Optimize: check dispatch engine stats and suggest optimizations."""
import argparse
import json
import time
import sys
import urllib.request
import urllib.error

STATS_URL = "http://127.0.0.1:9742/api/dispatch_engine/stats"
THRESHOLDS = {
    "min_success_rate": 0.7,
    "max_avg_latency": 10.0,
    "min_dispatches": 5,
    "circuit_open_warning": True,
}


def fetch_stats(timeout: float = 10.0) -> dict:
    try:
        req = urllib.request.Request(STATS_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return {"error": str(e)}


def analyze_stats(data: dict) -> list:
    suggestions = []
    nodes = data.get("nodes", data.get("node_stats", {}))
    if isinstance(nodes, dict):
        for name, stats in nodes.items():
            total = stats.get("total", stats.get("dispatches", 0))
            success = stats.get("success", stats.get("success_count", 0))
            rate = success / total if total > 0 else 0
            latency = stats.get("avg_latency", stats.get("latency_avg", 0))
            circuit = stats.get("circuit", stats.get("circuit_state", "closed"))

            if circuit in ("open", "half-open"):
                suggestions.append(
                    f"{name}: circuit={circuit} - node degraded, check health")
            if total >= THRESHOLDS["min_dispatches"] and rate < THRESHOLDS["min_success_rate"]:
                suggestions.append(
                    f"{name}: success_rate={rate:.0%} < {THRESHOLDS['min_success_rate']:.0%}"
                    f" - reduce weight or disable")
            if latency > THRESHOLDS["max_avg_latency"]:
                suggestions.append(
                    f"{name}: avg_latency={latency:.1f}s > {THRESHOLDS['max_avg_latency']}s"
                    f" - consider faster model or timeout reduction")

    routing = data.get("routing", {})
    if routing.get("fallback_count", 0) > routing.get("direct_count", 0):
        suggestions.append("High fallback rate - primary nodes may be overloaded")

    queue = data.get("queue_depth", data.get("pending", 0))
    if isinstance(queue, int) and queue > 20:
        suggestions.append(f"Queue depth={queue} - increase parallelism or add nodes")

    return suggestions


def optimize_cycle() -> dict:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    raw = fetch_stats()
    if "error" in raw:
        return {"timestamp": ts, "ok": False, "error": raw["error"]}
    suggestions = analyze_stats(raw)
    return {
        "timestamp": ts,
        "ok": True,
        "stats_summary": {
            k: v for k, v in raw.items()
            if k in ("total_dispatches", "uptime", "active_nodes", "queue_depth")
        },
        "suggestions": suggestions or ["Dispatch engine operating optimally"],
        "suggestion_count": len(suggestions),
    }


def main():
    parser = argparse.ArgumentParser(description="IA Optimize dispatch engine")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    parser.add_argument("--interval", type=int, default=300, help="Loop interval (sec)")
    args = parser.parse_args()

    while True:
        result = optimize_cycle()
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.once:
            sys.exit(0 if result["ok"] else 1)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
