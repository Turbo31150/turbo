#!/usr/bin/env python3
"""cowork_full_cycle.py — Run the complete COWORK improvement cycle.

Orchestrates all analysis/optimization scripts in sequence:
1. Health check (cluster_health_watchdog)
2. Error analysis (dispatch_error_analyzer)
3. Reliability improvement (dispatch_reliability_improver)
4. Load balancing (pattern_load_balancer)
5. Latency optimization (dispatch_latency_optimizer)
6. Quality scoring (dispatch_quality_scorer)
7. Retry simulation (smart_retry_dispatcher)
8. Trend analysis (dispatch_trend_analyzer)
9. Cache analysis (quick_answer_cache)
10. Self-tests (cowork_self_test_runner)

CLI:
    --once       : run full cycle
    --quick      : run essential checks only (health + errors + quality)
    --stats      : summary of all subsystems

Stdlib-only (sqlite3, json, argparse, subprocess).
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable

FULL_CYCLE = [
    ("cluster_health_watchdog", "--once", "Health Check"),
    ("dispatch_error_analyzer", "--once", "Error Analysis"),
    ("dispatch_reliability_improver", "--once", "Reliability"),
    ("pattern_load_balancer", "--once", "Load Balance"),
    ("dispatch_latency_optimizer", "--once", "Latency Opt"),
    ("dispatch_quality_scorer", "--once", "Quality Score"),
    ("smart_retry_dispatcher", "--simulate", "Retry Sim"),
    ("dispatch_trend_analyzer", "--once", "Trends"),
    ("quick_answer_cache", "--once", "Cache Analysis"),
    ("cowork_self_test_runner", "--level", "Self-Tests"),
]

QUICK_CYCLE = [
    ("cluster_health_watchdog", "--once", "Health Check"),
    ("dispatch_error_analyzer", "--once", "Error Analysis"),
    ("dispatch_quality_scorer", "--once", "Quality Score"),
]


def run_script(name, args, label):
    """Run a single analysis script and capture output."""
    script_path = SCRIPT_DIR / f"{name}.py"
    if not script_path.exists():
        return {"script": name, "status": "missing", "error": f"{name}.py not found"}

    cmd = [PYTHON, str(script_path)]
    if isinstance(args, str):
        cmd.append(args)
    else:
        cmd.extend(args)

    # Special case for self-test runner
    if name == "cowork_self_test_runner":
        cmd = [PYTHON, str(script_path), "--level", "1"]

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            cwd=str(SCRIPT_DIR)
        )
        elapsed_ms = int((time.time() - t0) * 1000)

        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                return {
                    "script": name,
                    "label": label,
                    "status": "ok",
                    "duration_ms": elapsed_ms,
                    "summary": _extract_summary(name, data),
                }
            except json.JSONDecodeError:
                return {
                    "script": name, "label": label, "status": "ok",
                    "duration_ms": elapsed_ms,
                    "summary": {"output_lines": len(result.stdout.split("\n"))},
                }
        else:
            return {
                "script": name, "label": label, "status": "error",
                "duration_ms": elapsed_ms,
                "error": result.stderr[:200] if result.stderr else "Empty output",
            }
    except subprocess.TimeoutExpired:
        return {"script": name, "label": label, "status": "timeout", "duration_ms": 120000}
    except Exception as e:
        return {"script": name, "label": label, "status": "error", "error": str(e)[:200]}


def _extract_summary(name, data):
    """Extract key metrics from each script's output."""
    if name == "cluster_health_watchdog":
        return {
            "cluster": data.get("cluster_status"),
            "online": data.get("nodes_online"),
            "alerts": len(data.get("alerts", [])),
        }
    elif name == "dispatch_error_analyzer":
        return {
            "failures": data.get("total_failures"),
            "null_pct": data.get("null_pct"),
            "causes": data.get("inferred_causes"),
        }
    elif name == "dispatch_reliability_improver":
        return {
            "issues": data.get("issues_found"),
            "recommendations": len(data.get("recommendations", [])),
        }
    elif name == "pattern_load_balancer":
        dist = data.get("distribution", {})
        return {
            "dispatches": data.get("total_dispatches"),
            "m1_load": dist.get("M1", {}).get("current_pct"),
            "suggestions": len(data.get("suggestions", [])),
        }
    elif name == "dispatch_quality_scorer":
        return {
            "overall_quality": data.get("overall_quality"),
            "excellent_pct": data.get("excellent_pct"),
            "critical": data.get("critical_count"),
        }
    elif name == "smart_retry_dispatcher":
        return {
            "recovery_rate": data.get("recovery_rate_pct"),
            "would_recover": data.get("would_recover"),
        }
    elif name == "dispatch_trend_analyzer":
        summary = data.get("summary", {})
        return {
            "emerging": summary.get("emerging"),
            "declining": summary.get("declining"),
            "degrading": summary.get("degrading"),
        }
    elif name == "quick_answer_cache":
        return {
            "hit_rate": data.get("potential_hit_rate_pct"),
            "time_saved_s": data.get("estimated_time_saved_s"),
        }
    elif name == "cowork_self_test_runner":
        return {
            "passed": data.get("passed"),
            "failed": data.get("failed"),
            "success_pct": data.get("success_rate_pct"),
        }
    return {"raw_keys": list(data.keys())[:5]}


def run_cycle(cycle_type="full"):
    """Run a full or quick cycle."""
    cycle = FULL_CYCLE if cycle_type == "full" else QUICK_CYCLE
    t0 = time.time()

    results = []
    for name, args, label in cycle:
        result = run_script(name, args, label)
        results.append(result)

    duration_ms = int((time.time() - t0) * 1000)
    ok = sum(1 for r in results if r["status"] == "ok")
    errors = sum(1 for r in results if r["status"] != "ok")

    return {
        "timestamp": datetime.now().isoformat(),
        "cycle_type": cycle_type,
        "total_scripts": len(cycle),
        "ok": ok,
        "errors": errors,
        "duration_ms": duration_ms,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="COWORK Full Improvement Cycle")
    parser.add_argument("--once", action="store_true", help="Full cycle")
    parser.add_argument("--quick", action="store_true", help="Quick check")
    parser.add_argument("--stats", action="store_true", help="Summary")
    args = parser.parse_args()

    if not any([args.once, args.quick, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.quick:
        result = run_cycle("quick")
    elif args.stats:
        result = run_cycle("quick")  # Stats = quick cycle
    else:
        result = run_cycle("full")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
