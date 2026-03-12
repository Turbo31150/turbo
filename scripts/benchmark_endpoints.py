#!/usr/bin/env python3
"""
JARVIS Endpoint Performance Benchmark
--------------------------------------
Tests all critical JARVIS API endpoints for response time, HTTP status,
and JSON validity. Produces a summary table with per-endpoint grades
and an overall system grade.

Usage:
    python benchmark_endpoints.py            # Human-readable table
    python benchmark_endpoints.py --json     # Machine-readable JSON to stdout

Results are always saved to: /home/turbo/jarvis-m1-ops/data/endpoint_benchmarks.json
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "http://127.0.0.1:9742"
RESULTS_PATH = os.path.join("F:", os.sep, "BUREAU", "turbo", "data", "endpoint_benchmarks.json")
RUNS_PER_ENDPOINT = 3
TIMEOUT_SECONDS = 30
WARN_THRESHOLD_S = 5.0
CRIT_THRESHOLD_S = 15.0

ENDPOINTS: list[dict[str, Any]] = [
    {"method": "GET",  "path": "/api/metrics/health-score",   "label": "Health Score"},
    {"method": "GET",  "path": "/api/metrics/dashboard",      "label": "Dashboard Metrics"},
    {"method": "GET",  "path": "/api/decisions/stats",        "label": "Decision Stats"},
    {"method": "GET",  "path": "/api/decisions/recent",       "label": "Recent Decisions"},
    {"method": "GET",  "path": "/api/resources/cluster",      "label": "Cluster Resources"},
    {"method": "GET",  "path": "/api/resources/load",         "label": "Resource Load"},
    {"method": "GET",  "path": "/api/diagnostic/run",         "label": "Diagnostic Run"},
    {"method": "GET",  "path": "/api/logs/analysis",          "label": "Log Analysis"},
    {"method": "GET",  "path": "/api/logs/patterns",          "label": "Log Patterns"},
    {
        "method": "POST",
        "path": "/api/autonomous/cycle",
        "label": "Autonomous Cycle",
        "body": {"notify": False, "fix": False},
    },
    {"method": "GET",  "path": "/api/autonomous/status",      "label": "Autonomous Status"},
    {"method": "GET",  "path": "/api/dispatch_engine/cache",  "label": "Dispatch Cache"},
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grade_for_median(median_s: float) -> str:
    """Return a letter grade based on median response time."""
    if median_s < 0.3:
        return "A+"
    if median_s < 0.8:
        return "A"
    if median_s < 2.0:
        return "B"
    if median_s < WARN_THRESHOLD_S:
        return "C"
    if median_s < CRIT_THRESHOLD_S:
        return "D"
    return "F"


def _severity(median_s: float) -> str:
    if median_s >= CRIT_THRESHOLD_S:
        return "CRITICAL"
    if median_s >= WARN_THRESHOLD_S:
        return "WARNING"
    return "OK"


def _overall_grade(results: list[dict]) -> str:
    """Weighted overall grade from individual results."""
    grade_points = {"A+": 4.3, "A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}
    points: list[float] = []
    for r in results:
        g = r.get("grade", "F")
        if r.get("error"):
            points.append(0.0)
        else:
            points.append(grade_points.get(g, 0.0))
    if not points:
        return "F"
    avg = sum(points) / len(points)
    if avg >= 4.15:
        return "A+"
    if avg >= 3.5:
        return "A"
    if avg >= 2.5:
        return "B"
    if avg >= 1.5:
        return "C"
    if avg >= 0.5:
        return "D"
    return "F"


def _http_request(
    url: str,
    method: str = "GET",
    body: dict | None = None,
    timeout: int = TIMEOUT_SECONDS,
) -> tuple[int, str, float]:
    """
    Execute a single HTTP request.
    Returns (status_code, response_body, elapsed_seconds).
    On network/timeout error returns (0, error_message, elapsed).
    """
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.perf_counter() - start
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, raw, elapsed
    except urllib.error.HTTPError as exc:
        elapsed = time.perf_counter() - start
        raw = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return exc.code, raw, elapsed
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return 0, str(exc), elapsed


def _is_valid_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Benchmark logic
# ---------------------------------------------------------------------------

def benchmark_endpoint(endpoint: dict) -> dict:
    """Run RUNS_PER_ENDPOINT requests and compute stats for one endpoint."""
    url = f"{BASE_URL}{endpoint['path']}"
    method = endpoint.get("method", "GET")
    body = endpoint.get("body")
    label = endpoint.get("label", endpoint["path"])

    timings: list[float] = []
    statuses: list[int] = []
    json_valid_flags: list[bool] = []
    last_error: str | None = None

    for _ in range(RUNS_PER_ENDPOINT):
        status, raw, elapsed = _http_request(url, method=method, body=body)
        statuses.append(status)
        timings.append(elapsed)
        json_valid_flags.append(_is_valid_json(raw))
        if status == 0:
            last_error = raw

    # Compute stats
    median_time = statistics.median(timings)
    min_time = min(timings)
    max_time = max(timings)
    all_200 = all(s == 200 for s in statuses)
    all_json = all(json_valid_flags)
    any_error = any(s == 0 for s in statuses)

    result: dict[str, Any] = {
        "label": label,
        "endpoint": f"{method} {endpoint['path']}",
        "runs": RUNS_PER_ENDPOINT,
        "median_ms": round(median_time * 1000, 1),
        "min_ms": round(min_time * 1000, 1),
        "max_ms": round(max_time * 1000, 1),
        "http_ok": all_200,
        "json_valid": all_json,
        "severity": _severity(median_time),
        "grade": _grade_for_median(median_time) if not any_error else "F",
        "error": last_error if any_error else None,
        "statuses": statuses,
    }

    if any_error:
        result["severity"] = "ERROR"

    return result


def run_all_benchmarks() -> dict:
    """Benchmark every endpoint and return the full report."""
    results: list[dict] = []
    total_start = time.perf_counter()

    for i, ep in enumerate(ENDPOINTS):
        label = ep.get("label", ep["path"])
        sys.stderr.write(f"\r  [{i + 1}/{len(ENDPOINTS)}] {label}...")
        sys.stderr.flush()
        result = benchmark_endpoint(ep)
        results.append(result)

    total_elapsed = time.perf_counter() - total_start
    sys.stderr.write("\r" + " " * 60 + "\r")
    sys.stderr.flush()

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "runs_per_endpoint": RUNS_PER_ENDPOINT,
        "thresholds": {
            "warn_s": WARN_THRESHOLD_S,
            "critical_s": CRIT_THRESHOLD_S,
        },
        "total_time_s": round(total_elapsed, 2),
        "overall_grade": _overall_grade(results),
        "summary": {
            "total": len(results),
            "ok": sum(1 for r in results if r["severity"] == "OK"),
            "warnings": sum(1 for r in results if r["severity"] == "WARNING"),
            "critical": sum(1 for r in results if r["severity"] == "CRITICAL"),
            "errors": sum(1 for r in results if r["severity"] == "ERROR"),
        },
        "endpoints": results,
    }
    return report


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_table(report: dict) -> None:
    """Print a human-readable summary table to stdout."""
    results = report["endpoints"]

    # Header
    print()
    print("=" * 90)
    print("  JARVIS Endpoint Performance Benchmark")
    print(f"  {report['timestamp']}  |  {report['runs_per_endpoint']} runs/endpoint")
    print("=" * 90)
    print()

    # Column widths
    lw = max(len(r["label"]) for r in results)
    lw = max(lw, 8)

    header = (
        f"  {'Endpoint':<{lw}}  {'Median':>9}  {'Min':>9}  {'Max':>9}"
        f"  {'HTTP':>5}  {'JSON':>5}  {'Status':>8}  {'Grade':>5}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))

    for r in results:
        if r["error"]:
            status_str = "ERROR"
            med = "---"
            mn = "---"
            mx = "---"
        else:
            status_str = r["severity"]
            med = f"{r['median_ms']:>7.1f}ms"
            mn = f"{r['min_ms']:>7.1f}ms"
            mx = f"{r['max_ms']:>7.1f}ms"

        http_str = "OK" if r["http_ok"] else "FAIL"
        json_str = "OK" if r["json_valid"] else "FAIL"
        grade = r["grade"]

        # Prefix indicator
        if r["severity"] == "ERROR":
            prefix = "[!!]"
        elif r["severity"] == "CRITICAL":
            prefix = "[!!]"
        elif r["severity"] == "WARNING":
            prefix = "[! ]"
        else:
            prefix = "[ o]"

        line = (
            f"  {prefix} {r['label']:<{lw}}  {med:>9}  {mn:>9}  {mx:>9}"
            f"  {http_str:>5}  {json_str:>5}  {status_str:>8}  {grade:>5}"
        )
        print(line)

    # Footer
    s = report["summary"]
    print()
    print("  " + "-" * 70)
    print(f"  Total endpoints: {s['total']}  |  OK: {s['ok']}  |  "
          f"Warn: {s['warnings']}  |  Crit: {s['critical']}  |  Err: {s['errors']}")
    print(f"  Total benchmark time: {report['total_time_s']}s")
    print()
    print(f"  Overall Grade: {report['overall_grade']}")
    print()

    # Warnings detail
    flagged = [r for r in results if r["severity"] in ("WARNING", "CRITICAL", "ERROR")]
    if flagged:
        print("  Flagged endpoints:")
        for r in flagged:
            if r["error"]:
                detail = f"Connection error: {r['error'][:80]}"
            else:
                detail = f"Median {r['median_ms']:.1f}ms ({r['severity']})"
            print(f"    - {r['label']}: {detail}")
        print()

    print("=" * 90)
    print()


def save_results(report: dict) -> None:
    """Save the full report to the JSON results file."""
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

    # Load existing history if present
    history: list[dict] = []
    if os.path.isfile(RESULTS_PATH):
        try:
            with open(RESULTS_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, list):
                history = existing
            elif isinstance(existing, dict):
                # Wrap single report into history
                history = [existing]
        except (json.JSONDecodeError, OSError):
            pass

    history.append(report)

    # Keep last 50 runs to prevent unbounded growth
    if len(history) > 50:
        history = history[-50:]

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    json_mode = "--json" in sys.argv

    if not json_mode:
        print("\n  Starting JARVIS endpoint benchmark...\n")

    report = run_all_benchmarks()

    # Always save
    try:
        save_results(report)
        if not json_mode:
            print(f"  Results saved to: {RESULTS_PATH}")
    except OSError as exc:
        sys.stderr.write(f"  Warning: could not save results: {exc}\n")

    # Output
    if json_mode:
        # Clean output: remove per-run statuses list for brevity
        for ep in report["endpoints"]:
            ep.pop("statuses", None)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_table(report)


if __name__ == "__main__":
    main()
