#!/usr/bin/env python3
"""JARVIS cowork — Rollback guard: check history and warn on failures."""
from __future__ import annotations
import argparse, json, sys, urllib.request

def _get(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def main():
    p = argparse.ArgumentParser(description="Rollback guard")
    p.add_argument("--once", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    data = _get("http://127.0.0.1:9742/api/rollback/history")
    if not data:
        print("WS offline")
        return
    if args.json:
        json.dump(data, sys.stdout, indent=2)
    else:
        stats = data.get("stats", {})
        print(f"Fixes: {stats.get('total_fixes',0)} | Success: {stats.get('successful',0)} | Rolled back: {stats.get('rolled_back',0)}")
        for h in data.get("history", [])[:5]:
            print(f"  [{h['status']}] {h['fix_id']} -> {h['target']} ({h.get('duration_ms',0):.0f}ms)")

if __name__ == "__main__":
    main()
