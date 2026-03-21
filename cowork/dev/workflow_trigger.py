#!/usr/bin/env python3
"""Workflow Trigger — Chain multiple cowork scripts in sequence.

Define workflow: list of scripts to run in order. Stop on failure.

Usage:
  python cowork/dev/workflow_trigger.py --once --workflow health
  python cowork/dev/workflow_trigger.py --once --workflow full_cycle
  python cowork/dev/workflow_trigger.py --list
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent
DEV = TURBO / "cowork" / "dev"
PYTHON = sys.executable

# Ensure Windows console can print non-ASCII safely
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

WORKFLOWS = {
    "health": [
        "mcp_health_monitor", "disk_space_watcher", "docker_health_monitor"
    ],
    "trading": [
        "auto_trader", "signal_backtester", "portfolio_tracker", "risk_manager"
    ],
    "maintenance": [
        "query_optimizer", "auto_cleaner", "log_rotator", "auto_backup"
    ],
    "full_cycle": [
        "mcp_health_monitor", "disk_space_watcher", "docker_health_monitor",
        "query_optimizer", "metrics_aggregator", "daily_health_report"
    ],
    "security": [
        "security_auditor", "integrity_auditor", "port_scanner"
    ],
    "cluster": [
        "cluster_heartbeat", "cluster_auto_tuner", "cluster_load_predictor"
    ],
}


def run_workflow(name: str):
    """Execute a named workflow."""
    if name not in WORKFLOWS:
        print(json.dumps({"error": f"Unknown workflow: {name}", "available": list(WORKFLOWS.keys())}))
        return

    scripts = WORKFLOWS[name]
    results = []
    start = time.time()

    for script in scripts:
        path = DEV / f"{script}.py"
        if not path.exists():
            results.append({"script": script, "status": "MISSING"})
            continue
        try:
            r = subprocess.run([PYTHON, str(path), "--once"],
                               capture_output=True, text=True, timeout=60, cwd=str(TURBO))
            results.append({
                "script": script,
                "status": "OK" if r.returncode == 0 else "FAIL",
                "exit_code": r.returncode
            })
        except subprocess.TimeoutExpired:
            results.append({"script": script, "status": "TIMEOUT"})
        except Exception as e:
            results.append({"script": script, "status": "ERROR", "error": str(e)})

    ok = sum(1 for r in results if r["status"] == "OK")
    output = {
        "workflow": name,
        "timestamp": datetime.now().isoformat(),
        "steps": results,
        "total": len(results),
        "ok": ok,
        "elapsed_s": round(time.time() - start, 1)
    }
    print(json.dumps(output, indent=2))
    return output


def main():
    parser = argparse.ArgumentParser(description="Workflow Trigger")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--workflow", "-w", type=str, help="Workflow name")
    parser.add_argument("--list", action="store_true", help="List workflows")
    args = parser.parse_args()

    if args.list:
        for name, scripts in WORKFLOWS.items():
            print(f"  {name}: {' -> '.join(scripts)}")
        return
    if args.workflow:
        run_workflow(args.workflow)
        return
    print("Use --workflow NAME or --list")


if __name__ == "__main__":
    main()

