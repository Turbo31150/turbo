#!/usr/bin/env python3
"""Cluster Model Migration — load a model on target node, unload from source."""
import argparse, json, urllib.request

NODES = {
    "m1": "http://127.0.0.1:1234",
    "m2": "http://192.168.1.26:1234",
    "m3": "http://192.168.1.113:1234",
}

def load_model(node_url: str, model_id: str) -> bool:
    payload = json.dumps({"model": model_id, "input": "test", "max_output_tokens": 1, "stream": False, "store": False}).encode()
    req = urllib.request.Request(f"{node_url}/api/v1/chat", data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  Load error: {e}")
        return False

def unload_model(node_url: str, model_id: str) -> bool:
    payload = json.dumps({"model": model_id}).encode()
    req = urllib.request.Request(f"{node_url}/api/v1/models/unload", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  Unload error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Migrate model between cluster nodes")
    parser.add_argument("model", help="Model ID to migrate")
    parser.add_argument("--from-node", required=True, choices=list(NODES.keys()))
    parser.add_argument("--to-node", required=True, choices=list(NODES.keys()))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--keep-source", action="store_true", help="Don't unload from source")
    args = parser.parse_args()

    print(f"Migrating {args.model}: {args.from_node} -> {args.to_node}")

    target_url = NODES[args.to_node]
    print(f"  Loading on {args.to_node}...")
    if not load_model(target_url, args.model):
        print("  FAILED to load on target")
        return

    if not args.keep_source:
        source_url = NODES[args.from_node]
        print(f"  Unloading from {args.from_node}...")
        unload_model(source_url, args.model)

    print("  Migration complete")

if __name__ == "__main__":
    main()
