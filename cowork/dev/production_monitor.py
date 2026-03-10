#!/usr/bin/env python3
"""Production health monitor — combines health + automation status into dashboard JSON."""

import argparse
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:9742"

ENDPOINTS = {
    "health": "/api/health/full",
    "automation": "/api/automation/status",
}


def fetch(url, timeout=10):
    """Fetch JSON from URL, return dict or error dict."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return {"error": str(e), "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}


def run_once():
    ts = time.time()
    results = {}
    for name, path in ENDPOINTS.items():
        t0 = time.perf_counter()
        data = fetch(f"{BASE}{path}")
        elapsed = round(time.perf_counter() - t0, 3)
        results[name] = {
            "data": data,
            "latency_s": elapsed,
            "ok": "error" not in data,
        }

    health_ok = results.get("health", {}).get("ok", False)
    auto_ok = results.get("automation", {}).get("ok", False)

    dashboard = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "overall_status": "OK" if (health_ok and auto_ok) else "DEGRADED",
        "endpoints": results,
        "summary": {
            "health_reachable": health_ok,
            "automation_reachable": auto_ok,
            "total_latency_s": round(sum(r["latency_s"] for r in results.values()), 3),
        },
    }
    print(json.dumps(dashboard, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Production health monitor dashboard")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        print("Use --once for a single run. Use --help for options.")


if __name__ == "__main__":
    main()
