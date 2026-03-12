#!/usr/bin/env python3
"""Auto-test: run pytest on JARVIS tests and parse results."""
import argparse
import json
import re
import subprocess
import time
import sys

TESTS_DIR = "/home/turbo/jarvis-m1-ops/tests"


def run_pytest(tests_dir: str, extra_args: list = None) -> dict:
    cmd = [sys.executable, "-m", "pytest", tests_dir, "--tb=no", "-q"]
    if extra_args:
        cmd.extend(extra_args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
            cwd="/home/turbo/jarvis-m1-ops"
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "pytest timeout (300s)"}
    except FileNotFoundError:
        return {"returncode": -1, "stdout": "", "stderr": "python/pytest not found"}


def parse_summary(stdout: str) -> dict:
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "warnings": 0}
    m = re.search(r"(\d+) passed", stdout)
    if m:
        counts["passed"] = int(m.group(1))
    m = re.search(r"(\d+) failed", stdout)
    if m:
        counts["failed"] = int(m.group(1))
    m = re.search(r"(\d+) skipped", stdout)
    if m:
        counts["skipped"] = int(m.group(1))
    m = re.search(r"(\d+) error", stdout)
    if m:
        counts["errors"] = int(m.group(1))
    m = re.search(r"(\d+) warning", stdout)
    if m:
        counts["warnings"] = int(m.group(1))
    return counts


def test_cycle(extra_args: list = None) -> dict:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    t0 = time.monotonic()
    raw = run_pytest(TESTS_DIR, extra_args)
    elapsed = round(time.monotonic() - t0, 2)
    counts = parse_summary(raw["stdout"])
    ok = raw["returncode"] == 0
    return {
        "timestamp": ts,
        "duration_sec": elapsed,
        "success": ok,
        "counts": counts,
        "total": counts["passed"] + counts["failed"] + counts["skipped"],
        "last_lines": raw["stdout"].strip().split("\n")[-5:],
        "stderr_tail": raw["stderr"].strip().split("\n")[-3:] if raw["stderr"] else [],
    }


def main():
    parser = argparse.ArgumentParser(description="Auto-test JARVIS")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    parser.add_argument("--interval", type=int, default=600, help="Loop interval (sec)")
    parser.add_argument("--marker", type=str, default=None, help="Pytest marker (-m)")
    args = parser.parse_args()
    extra = ["-m", args.marker] if args.marker else None

    while True:
        result = test_cycle(extra)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.once:
            sys.exit(0 if result["success"] else 1)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
