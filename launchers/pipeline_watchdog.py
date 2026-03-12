#!/usr/bin/env python3
"""Pipeline Watchdog — keeps the autonomous pipeline alive.

Launches the pipeline as a child process and restarts it if it dies.
Run this in a terminal: python launchers/pipeline_watchdog.py
"""
import subprocess
import sys
import time
from pathlib import Path

TURBO = Path("/home/turbo/jarvis-m1-ops")
PYTHON = str(TURBO / ".venv" / "Scripts" / "python.exe")
SCRIPT = str(TURBO / "cowork" / "dev" / "autonomous_cluster_pipeline.py")
ARGS = ["--cycles", "100", "--batch", "5", "--pause", "3", "--log"]
LOG = TURBO / "data" / "pipeline_output.log"

def run():
    print(f"[WATCHDOG] Starting pipeline...")
    proc = subprocess.Popen(
        [PYTHON, "-u", SCRIPT] + ARGS,
        cwd=str(TURBO),
        stdout=sys.stdout, stderr=sys.stderr
    )
    print(f"[WATCHDOG] Pipeline PID: {proc.pid}")
    return proc

restarts = 0
while True:
    proc = run()
    proc.wait()
    restarts += 1
    code = proc.returncode
    print(f"\n[WATCHDOG] Pipeline exited (code={code}), restart #{restarts}")
    if restarts > 20:
        print("[WATCHDOG] Too many restarts, stopping.")
        break
    time.sleep(5)
