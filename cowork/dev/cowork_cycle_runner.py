#!/usr/bin/env python3
"""Cowork Cycle Runner — Execute the full automation loop.

Runs: deploy patterns → test scripts → map orphans → gaps → health check → report.

Usage:
    python cowork/dev/cowork_cycle_runner.py --once
    python cowork/dev/cowork_cycle_runner.py --interval 300
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent
COWORK = TURBO / "cowork"
PYTHON = sys.executable


def run_step(name, cmd, timeout=60):
    """Run a step and return result."""
    start = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(TURBO))
        elapsed = round(time.time() - start, 1)
        return {"step": name, "status": "OK" if r.returncode == 0 else "FAIL",
                "elapsed_s": elapsed, "exit_code": r.returncode,
                "output_lines": len(r.stdout.splitlines())}
    except subprocess.TimeoutExpired:
        return {"step": name, "status": "TIMEOUT", "elapsed_s": timeout}
    except Exception as e:
        return {"step": name, "status": "ERROR", "error": str(e)}


def run_cycle():
    """Execute one full cycle."""
    results = []
    ts = datetime.now().isoformat()

    # Step 1: Deploy patterns if needed
    results.append(run_step("deploy_patterns",
        [PYTHON, str(COWORK / "deploy_cowork_agents.py"), "--deploy"], 30))

    # Step 2: Health monitor
    results.append(run_step("health_check",
        [PYTHON, str(COWORK / "dev" / "mcp_health_monitor.py"), "--once"], 20))

    # Step 3: Test a batch of scripts (first 50)
    results.append(run_step("test_batch",
        [PYTHON, str(COWORK / "cowork_engine.py"), "--test-all"], 120))

    # Step 4: Gap analysis
    results.append(run_step("gap_analysis",
        [PYTHON, str(COWORK / "cowork_engine.py"), "--gaps"], 60))

    # Step 5: Docker health
    results.append(run_step("docker_health",
        [PYTHON, str(COWORK / "dev" / "docker_health_monitor.py"), "--once"], 20))

    # Step 6: Disk watch
    results.append(run_step("disk_watch",
        [PYTHON, str(COWORK / "dev" / "disk_space_watcher.py"), "--once"], 10))

    ok = sum(1 for r in results if r["status"] == "OK")
    cycle = {
        "timestamp": ts,
        "steps": results,
        "total": len(results),
        "ok": ok,
        "failed": len(results) - ok,
        "success_rate": round(ok / len(results) * 100, 1)
    }
    print(json.dumps(cycle, indent=2))
    return cycle


def main():
    parser = argparse.ArgumentParser(description="Cowork Cycle Runner")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--interval", type=int, default=300, help="Cycle interval (seconds)")
    args = parser.parse_args()

    if args.once:
        run_cycle()
    else:
        print(f"Starting continuous cycles every {args.interval}s")
        while True:
            run_cycle()
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
