#!/usr/bin/env python3
"""JARVIS cowork — Log predictor: analyze patterns and predict failures."""
from __future__ import annotations
import argparse, json, sys, urllib.request

def _get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def main():
    p = argparse.ArgumentParser(description="Log predictor")
    p.add_argument("--once", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--predictions", action="store_true", help="Show predictions only")
    args = p.parse_args()
    if args.predictions:
        data = _get("http://127.0.0.1:9742/api/logs/predictions")
    else:
        data = _get("http://127.0.0.1:9742/api/logs/analysis")
    if not data:
        print("WS offline")
        return
    if args.json:
        json.dump(data, sys.stdout, indent=2)
    else:
        if args.predictions:
            preds = data.get("predictions", [])
            trend = data.get("trend", {})
            print(f"Trend: {trend.get('trend','?')} | Change: {trend.get('change_pct','?')}%")
            for p in preds:
                print(f"  [{p.get('confidence',0):.0%}] {p.get('predicted_issue','?')}")
        else:
            print(f"Entries: {data.get('total_entries',0)} | Errors: {data.get('errors',0)} | Criticals: {data.get('criticals',0)}")
            print(f"Trend: {data.get('trend','?')}")
            for pat in data.get("top_patterns", [])[:5]:
                print(f"  [{pat.get('count',0)}x] {pat.get('pattern','?')[:80]}")

if __name__ == "__main__":
    main()
