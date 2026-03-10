#!/usr/bin/env python3
"""Deploy/verify cluster status — ping M1, M2, M3, OL1 and report health."""

import argparse
import json
import time
import urllib.request
import urllib.error

NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/models", "type": "lmstudio"},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/models", "type": "lmstudio"},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/models", "type": "lmstudio"},
    "OL1": {"url": "http://127.0.0.1:11434/api/tags", "type": "ollama"},
}


def check_node(name, node, timeout=5):
    """Ping a node and return status."""
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(node["url"], timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            elapsed = round(time.perf_counter() - t0, 3)

            if node["type"] == "lmstudio":
                models_data = data.get("data", data.get("models", []))
                loaded = [m for m in models_data if m.get("loaded_instances")]
                model_names = [m.get("id", m.get("name", "?")) for m in loaded]
                return {
                    "status": "ONLINE",
                    "latency_s": elapsed,
                    "loaded_models": len(loaded),
                    "models": model_names,
                }
            else:  # ollama
                models = data.get("models", [])
                model_names = [m.get("name", "?") for m in models]
                return {
                    "status": "ONLINE",
                    "latency_s": elapsed,
                    "available_models": len(models),
                    "models": model_names,
                }
    except urllib.error.URLError as e:
        elapsed = round(time.perf_counter() - t0, 3)
        return {"status": "OFFLINE", "latency_s": elapsed, "error": str(e.reason)}
    except Exception as e:
        elapsed = round(time.perf_counter() - t0, 3)
        return {"status": "OFFLINE", "latency_s": elapsed, "error": str(e)}


def run_once():
    results = {}
    for name, node in NODES.items():
        results[name] = check_node(name, node)

    online = [n for n, v in results.items() if v["status"] == "ONLINE"]
    offline = [n for n, v in results.items() if v["status"] == "OFFLINE"]

    if len(online) == len(NODES):
        cluster_status = "FULLY_OPERATIONAL"
    elif len(online) > 0:
        cluster_status = "DEGRADED"
    else:
        cluster_status = "DOWN"

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cluster_status": cluster_status,
        "online": online,
        "offline": offline,
        "nodes_up": len(online),
        "nodes_total": len(NODES),
        "nodes": results,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Deploy/verify cluster health status")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        print("Use --once for a single run. Use --help for options.")


if __name__ == "__main__":
    main()
