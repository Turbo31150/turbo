#!/usr/bin/env python3
"""Launcher for autonomous cluster pipeline — detached, no window, single instance."""
import subprocess
import sys
from pathlib import Path

TURBO = Path("F:/BUREAU/turbo")
PYTHON = TURBO / ".venv" / "Scripts" / "python.exe"
SCRIPT = TURBO / "cowork" / "dev" / "autonomous_cluster_pipeline.py"
PID_FILE = TURBO / "data" / "cluster_pipeline.pid"

# Kill existing instance
if PID_FILE.exists():
    old_pid = PID_FILE.read_text().strip()
    subprocess.run(["taskkill", "/PID", old_pid, "/F"],
                   capture_output=True, timeout=5)
    print(f"Killed old PID {old_pid}")

# Launch detached
proc = subprocess.Popen(
    [str(PYTHON), "-u", str(SCRIPT),
     "--cycles", "1000", "--batch", "10", "--pause", "5", "--log"],
    cwd=str(TURBO),
    creationflags=subprocess.DETACHED_PROCESS,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print(f"Pipeline launched — PID {proc.pid}")
print(f"Log: {TURBO / 'data' / 'pipeline_output.log'}")
