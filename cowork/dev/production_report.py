#!/usr/bin/env python3
"""Generate a text report of system production status from multiple :9742 endpoints."""

import argparse
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:9742"

ENDPOINTS = [
    ("/api/health/full", "Health"),
    ("/api/automation/status", "Automation"),
    ("/api/scheduler/jobs", "Scheduler Jobs"),
    ("/api/queue/status", "Task Queue"),
    ("/api/singletons/list", "Singletons"),
]


def fetch(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def run_once():
    report_lines = []
    report_lines.append(f"=== PRODUCTION REPORT — {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    results = {}
    for path, label in ENDPOINTS:
        t0 = time.perf_counter()
        data = fetch(f"{BASE}{path}")
        elapsed = round(time.perf_counter() - t0, 3)
        ok = "error" not in data
        status = "OK" if ok else "FAIL"
        report_lines.append(f"[{status}] {label:20s} ({elapsed:.3f}s)")
        if not ok:
            report_lines.append(f"       Error: {data['error']}")
        results[label] = {"status": status, "latency_s": elapsed, "data": data}

    up = sum(1 for v in results.values() if v["status"] == "OK")
    total = len(results)
    report_lines.append(f"\nSummary: {up}/{total} endpoints reachable")
    overall = "HEALTHY" if up == total else ("DEGRADED" if up > 0 else "DOWN")
    report_lines.append(f"Overall: {overall}")

    report_text = "\n".join(report_lines)

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "overall": overall,
        "endpoints_up": up,
        "endpoints_total": total,
        "report": report_text,
        "details": results,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Generate production status text report")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        print("Use --once for a single run. Use --help for options.")


if __name__ == "__main__":
    main()
