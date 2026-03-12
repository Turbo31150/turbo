#!/usr/bin/env python3
"""zombie_killer.py — Kill orphaned/zombie Python processes eating RAM.

Scans for Python processes that:
  1. Consume more than MAX_RAM_MB of memory
  2. Have been running longer than MAX_AGE_HOURS
  3. Are NOT in the protected PID list (WS server, watchdog, etc.)

Safety: never kills the current process, never kills LM Studio/Ollama/Node.

Usage:
    python scripts/zombie_killer.py             # Dry run (show only)
    python scripts/zombie_killer.py --kill      # Actually kill zombies
    python scripts/zombie_killer.py --json      # JSON output
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

MAX_RAM_MB = 500       # Kill Python processes using > 500 MB
MAX_AGE_HOURS = 4      # Kill Python processes older than 4 hours
MY_PID = os.getpid()

# Protected process names (never kill)
PROTECTED = {"lm studio", "ollama", "node", "electron", "chrome", "msedge"}

# Protected script patterns (never kill — legitimate long-running services)
PROTECTED_SCRIPTS = {
    "jarvis_unified_boot", "server.py", "whisper_worker",
    "linkedin_scheduler", "dashboard", "telegram_bot",
    "claude", "cursortouch",
}

# Protected ports (find PIDs listening on these and never kill them)
PROTECTED_PORTS = {9742, 18800, 11434, 1234, 5678, 8080, 18789, 18791}


def get_python_processes():
    """Get Python processes with RAM and age info via WMIC."""
    try:
        out = subprocess.check_output(
            ["wmic", "process", "where", "name like '%python%'",
             "get", "ProcessId,WorkingSetSize,CreationDate,CommandLine",
             "/FORMAT:CSV"],
            timeout=10, encoding="utf-8", errors="replace"
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return []

    procs = []
    for line in out.strip().split("\n"):
        parts = line.strip().split(",")
        if len(parts) < 5 or parts[1] == "CommandLine":
            continue
        try:
            cmdline = parts[1]
            creation = parts[2]  # YYYYMMDDHHMMSS.FFFFFF+offset
            pid = int(parts[3])
            ram_bytes = int(parts[4])
        except (ValueError, IndexError):
            continue

        ram_mb = ram_bytes / (1024 * 1024)

        # Parse creation date
        try:
            dt_str = creation[:14]  # YYYYMMDDHHMMSS
            created = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            age_hours = (datetime.now() - created).total_seconds() / 3600
        except (ValueError, IndexError):
            age_hours = 0

        procs.append({
            "pid": pid,
            "ram_mb": round(ram_mb, 1),
            "age_hours": round(age_hours, 1),
            "cmdline": cmdline[:200],
        })

    return procs


def get_protected_pids():
    """Find PIDs listening on protected ports."""
    protected = {MY_PID}
    try:
        out = subprocess.check_output(["netstat", "-ano"], timeout=5, encoding="utf-8", errors="replace")
        for line in out.split("\n"):
            for port in PROTECTED_PORTS:
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        try:
                            protected.add(int(parts[-1]))
                        except ValueError:
                            pass
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    return protected


def main():
    parser = argparse.ArgumentParser(description="Kill zombie Python processes")
    parser.add_argument("--kill", action="store_true", help="Actually kill (default: dry run)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    procs = get_python_processes()
    protected_pids = get_protected_pids()

    zombies = []
    for p in procs:
        if p["pid"] in protected_pids:
            continue
        # Check if protected process name or script
        cmdline_lower = p["cmdline"].lower()
        if any(name in cmdline_lower for name in PROTECTED):
            continue
        if any(script in cmdline_lower for script in PROTECTED_SCRIPTS):
            continue
        # Kill criteria: high RAM OR very old
        is_zombie = p["ram_mb"] > MAX_RAM_MB or p["age_hours"] > MAX_AGE_HOURS
        if is_zombie:
            zombies.append(p)

    if args.json:
        print(json.dumps({"zombies": zombies, "total_python": len(procs),
                          "protected": len(protected_pids)}, indent=2))
        return

    print(f"\n  Zombie Killer — {len(procs)} Python processes, {len(protected_pids)} protected PIDs")
    print(f"  Thresholds: RAM > {MAX_RAM_MB} MB OR Age > {MAX_AGE_HOURS}h")
    print(f"  {'=' * 60}")

    if not zombies:
        print("  No zombies found. System clean.")
        return

    killed = 0
    for z in zombies:
        status = "DRY" if not args.kill else "KILL"
        print(f"  [{status}] PID {z['pid']:6d} | {z['ram_mb']:7.1f} MB | {z['age_hours']:5.1f}h | {z['cmdline'][:80]}")
        if args.kill:
            try:
                subprocess.run(["taskkill", "/PID", str(z["pid"]), "/F"],
                              capture_output=True, timeout=5)
                killed += 1
            except Exception:
                pass

    print(f"\n  Summary: {len(zombies)} zombies found, {killed} killed")
    ram_freed = sum(z["ram_mb"] for z in zombies)
    print(f"  RAM freed: ~{ram_freed:.0f} MB")


if __name__ == "__main__":
    main()
