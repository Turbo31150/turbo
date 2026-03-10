#!/usr/bin/env python3
"""JARVIS Test Runner — run test suite and report."""
import argparse, subprocess, sys, os, json, re

TURBO_DIR = os.path.join(os.path.dirname(__file__), "..", "..")

def run_tests(pattern: str = None, quick: bool = False) -> dict:
    cmd = ["python", "-m", "pytest", "-x", "--tb=short", "-q"]
    if pattern:
        cmd.extend(["-k", pattern])
    if quick:
        cmd.append("--timeout=10")

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=TURBO_DIR)
        output = r.stdout + r.stderr

        passed = failed = skipped = 0
        for line in output.split("\n"):
            if "passed" in line:
                m = re.search(r"(\d+) passed", line)
                if m:
                    passed = int(m.group(1))
                m = re.search(r"(\d+) failed", line)
                if m:
                    failed = int(m.group(1))
                m = re.search(r"(\d+) skipped", line)
                if m:
                    skipped = int(m.group(1))

        return {
            "passed": passed, "failed": failed, "skipped": skipped,
            "returncode": r.returncode,
            "output_tail": output[-500:] if len(output) > 500 else output
        }
    except subprocess.TimeoutExpired:
        return {"error": "Test timeout (300s)", "passed": 0, "failed": 0}

def main():
    parser = argparse.ArgumentParser(description="JARVIS test runner")
    parser.add_argument("--pattern", "-k", help="Test pattern filter")
    parser.add_argument("--quick", action="store_true", help="Quick mode (10s timeout)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    results = run_tests(args.pattern, args.quick)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        total = results.get("passed", 0) + results.get("failed", 0) + results.get("skipped", 0)
        print(f"Tests: {results.get('passed', 0)} passed, {results.get('failed', 0)} failed, {results.get('skipped', 0)} skipped ({total} total)")
        if results.get("failed", 0) > 0:
            print(f"\nFailed output:\n{results.get('output_tail', '')}")

if __name__ == "__main__":
    main()
