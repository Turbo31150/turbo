#!/usr/bin/env python3
"""continuous_improver.py — Continuous improvement loop for JARVIS cluster.

Runs a cycle: benchmark -> learn -> optimize -> predict -> report
Each cycle improves dispatch quality, routing, and overall health grade.

CLI:
    --once         : Single improvement cycle
    --watch        : Continuous improvement (default 30 min)
    --interval N   : Cycle interval in minutes
    --fast         : Quick cycle (benchmark on M1+OL1 only)

Stdlib-only (json, argparse, sqlite3, subprocess, time).
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"

IMPROVEMENT_STEPS = [
    {"name": "benchmark", "script": "dispatch_quality_tracker.py", "args": ["--benchmark"], "timeout": 300},
    {"name": "learn", "script": "dispatch_learner.py", "args": ["--learn"], "timeout": 60},
    {"name": "optimize", "script": "grade_optimizer.py", "args": ["--once"], "timeout": 30},
    {"name": "predict", "script": "failure_predictor.py", "args": ["--once"], "timeout": 30},
    {"name": "heal", "script": "cluster_auto_healer.py", "args": ["--once"], "timeout": 60},
    {"name": "status", "script": "telegram_quick_status.py", "args": ["--once"], "timeout": 30},
]


def run_step(step):
    """Run a single improvement step."""
    script = SCRIPT_DIR / step["script"]
    if not script.exists():
        return {"success": False, "error": f"Missing: {step['script']}"}

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(script)] + step["args"],
            capture_output=True, text=True,
            timeout=step.get("timeout", 120),
            cwd=str(SCRIPT_DIR)
        )
        elapsed = int((time.time() - start) * 1000)
        return {
            "success": result.returncode == 0,
            "duration_ms": elapsed,
            "output": result.stdout[-300:] if result.stdout else "",
            "error": result.stderr[-200:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout", "duration_ms": int(step.get("timeout", 120) * 1000)}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def get_grade():
    """Get current grade."""
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "grade_optimizer.py"), "--analyze"],
            capture_output=True, text=True, timeout=15, cwd=str(SCRIPT_DIR)
        )
        for line in result.stdout.split("\n"):
            if '"overall"' in line:
                return float(line.split(":")[1].strip().rstrip(","))
    except Exception:
        pass
    return 0


def send_telegram(text):
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def run_cycle(fast=False):
    """Run one improvement cycle."""
    ts = datetime.now().strftime("%H:%M:%S")
    grade_before = get_grade()

    steps = IMPROVEMENT_STEPS
    if fast:
        steps = [s for s in steps if s["name"] in ("optimize", "status")]

    results = {}
    for step in steps:
        print(f"  [{ts}] {step['name']}...", end=" ", flush=True)
        r = run_step(step)
        results[step["name"]] = r
        status = "OK" if r["success"] else "FAIL"
        dur = r.get("duration_ms", 0)
        print(f"{status} ({dur}ms)")

    grade_after = get_grade()
    delta = grade_after - grade_before

    summary = {
        "timestamp": datetime.now().isoformat(),
        "grade_before": grade_before,
        "grade_after": grade_after,
        "delta": round(delta, 1),
        "steps": {k: {"ok": v["success"], "ms": v.get("duration_ms", 0)} for k, v in results.items()},
    }

    ok = sum(1 for r in results.values() if r["success"])
    print(f"\n  Cycle done: {ok}/{len(results)} steps OK")
    print(f"  Grade: {grade_before} -> {grade_after} (delta={delta:+.1f})")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Continuous Improver")
    parser.add_argument("--once", action="store_true", help="Single cycle")
    parser.add_argument("--watch", action="store_true", help="Continuous")
    parser.add_argument("--interval", type=int, default=30, help="Interval (min)")
    parser.add_argument("--fast", action="store_true", help="Quick cycle")
    args = parser.parse_args()

    if not any([args.once, args.watch]):
        parser.print_help()
        sys.exit(1)

    if args.once:
        summary = run_cycle(fast=args.fast)
        print(json.dumps(summary, indent=2))
        return

    if args.watch:
        print(f"Continuous improvement every {args.interval}m")
        cycle = 0
        while True:
            try:
                cycle += 1
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{ts}] === Cycle {cycle} ===")
                summary = run_cycle(fast=args.fast)

                if summary["delta"] > 0:
                    send_telegram(
                        f"<b>Improvement</b> Cycle {cycle}\n"
                        f"Grade: {summary['grade_before']} -> {summary['grade_after']} (+{summary['delta']})"
                    )

                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                print("\nStopped")
                break


if __name__ == "__main__":
    main()
