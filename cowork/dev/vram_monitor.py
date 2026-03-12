#!/usr/bin/env python3
"""JARVIS cowork — VRAM monitor with auto-alert."""
from __future__ import annotations
import argparse, json, sys, urllib.request

def _get(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def main():
    p = argparse.ArgumentParser(description="VRAM monitor")
    p.add_argument("--once", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    data = _get("http://127.0.0.1:9742/api/vram/status")
    if not data:
        print("WS offline" if not args.json else json.dumps({"error": "WS offline"}))
        return
    if args.json:
        json.dump(data, sys.stdout, indent=2)
    else:
        gpu = data.get("gpu", {})
        print(f"GPU: {gpu.get('name','?')} | {gpu.get('temp_c','?')}C | VRAM: {gpu.get('vram_pct','?')}%")
        for a in data.get("alerts", []):
            print(f"  ALERT: {a}")
        for a in data.get("actions", []):
            print(f"  ACTION: {a}")

if __name__ == "__main__":
    main()
