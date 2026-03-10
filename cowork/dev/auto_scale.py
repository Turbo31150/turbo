#!/usr/bin/env python3
"""Auto-scale: check node load and suggest scaling decisions."""
import argparse
import json
import time
import sys
import urllib.request
import urllib.error

NODES_URL = "http://127.0.0.1:9742/api/orchestrator/nodes"
THRESHOLDS = {"high_load": 0.8, "low_load": 0.2, "queue_warn": 10}


def fetch_nodes(timeout: float = 10.0) -> dict:
    try:
        req = urllib.request.Request(NODES_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return {"error": str(e)}


def analyze_nodes(data: dict) -> dict:
    suggestions = []
    nodes_status = []
    nodes = data.get("nodes", data.get("data", []))
    if isinstance(nodes, dict):
        nodes = list(nodes.values())
    if not isinstance(nodes, list):
        return {"error": "unexpected nodes format", "raw": str(data)[:200]}

    for node in nodes:
        name = node.get("name", node.get("id", "unknown"))
        load = node.get("load", node.get("utilization", 0))
        queue = node.get("queue_size", node.get("pending", 0))
        status = node.get("status", "unknown")
        info = {"name": name, "load": load, "queue": queue, "status": status}
        nodes_status.append(info)

        if isinstance(load, (int, float)):
            if load > THRESHOLDS["high_load"]:
                suggestions.append(f"{name}: HIGH load ({load:.0%}) - consider offloading")
            elif load < THRESHOLDS["low_load"] and status == "online":
                suggestions.append(f"{name}: LOW load ({load:.0%}) - candidate for unload")
        if isinstance(queue, int) and queue > THRESHOLDS["queue_warn"]:
            suggestions.append(f"{name}: queue={queue} - needs more parallel slots")

    return {
        "node_count": len(nodes_status),
        "nodes": nodes_status,
        "suggestions": suggestions or ["All nodes within normal range"],
    }


def scale_cycle() -> dict:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    raw = fetch_nodes()
    if "error" in raw:
        return {"timestamp": ts, "ok": False, "error": raw["error"]}
    analysis = analyze_nodes(raw)
    return {"timestamp": ts, "ok": True, **analysis}


def main():
    parser = argparse.ArgumentParser(description="Auto-scale JARVIS nodes")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    parser.add_argument("--interval", type=int, default=120, help="Loop interval (sec)")
    args = parser.parse_args()

    while True:
        result = scale_cycle()
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.once:
            sys.exit(0 if result["ok"] else 1)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
