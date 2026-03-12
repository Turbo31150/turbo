#!/usr/bin/env python3
"""JARVIS cowork — Metric stream: fetch snapshot of real-time metrics."""
from __future__ import annotations
import argparse, json, sys, urllib.request

def _get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def main():
    p = argparse.ArgumentParser(description="Metrics snapshot")
    p.add_argument("--once", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    data = _get("http://127.0.0.1:9742/api/metrics/snapshot")
    if not data:
        print("WS offline or endpoint not available")
        return
    if args.json:
        json.dump(data, sys.stdout, indent=2, default=str)
    else:
        gpu = data.get("gpu", {})
        ram = data.get("ram", {})
        nodes = data.get("nodes", {})
        dispatch = data.get("dispatch_1h", {})
        print(f"CPU: {data.get('cpu_pct','?')}% | RAM: {ram.get('usage_pct','?')}% ({ram.get('used_mb','?')}/{ram.get('total_mb','?')}MB)")
        print(f"GPU: {gpu.get('temp_c','?')}C | VRAM: {gpu.get('vram_used_mb','?')}/{gpu.get('vram_total_mb','?')}MB ({gpu.get('utilization_pct','?')}%)")
        online = [n for n,s in nodes.items() if s == "online"]
        offline = [n for n,s in nodes.items() if s == "offline"]
        print(f"Nodes: {len(online)} online ({', '.join(online)}) | {len(offline)} offline ({', '.join(offline)})")
        print(f"Dispatch (1h): {dispatch.get('count',0)} queries | Avg quality: {dispatch.get('avg_quality','?')}")

if __name__ == "__main__":
    main()
