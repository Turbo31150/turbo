#!/usr/bin/env python3
"""Kill all zombie/duplicate JARVIS processes. One-shot cleanup."""
import subprocess
import os
import signal
import sys

def get_processes(pattern):
    """Get PIDs matching commandline pattern."""
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where', f"commandline like '%{pattern}%'",
             'get', 'ProcessId,CreationDate,CommandLine'],
            capture_output=True, text=True, timeout=10
        )
        pids = []
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            if parts and parts[-1].isdigit():
                pids.append(int(parts[-1]))
        return pids
    except Exception as e:
        print(f"  Error querying {pattern}: {e}")
        return []

def kill_pids(pids, keep_newest=False):
    """Kill list of PIDs. Optionally keep the last one (newest)."""
    to_kill = pids[:-1] if keep_newest and len(pids) > 1 else pids
    killed = 0
    for pid in to_kill:
        if pid == os.getpid():
            continue
        try:
            subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                         capture_output=True, timeout=5)
            killed += 1
        except Exception:
            pass
    return killed, len(to_kill)

def main():
    my_pid = os.getpid()
    print(f"=== JARVIS Zombie Cleanup (my PID: {my_pid}) ===\n")

    # 1. LinkedIn Scheduler — kill ALL (will be restarted cleanly)
    pids = get_processes("linkedin_scheduler")
    print(f"linkedin_scheduler.py: {len(pids)} instances")
    if pids:
        killed, total = kill_pids(pids, keep_newest=False)
        print(f"  Killed {killed}/{total}")

    # 2. Unified boot — kill duplicates (keep 1)
    pids = get_processes("jarvis_unified_boot")
    print(f"\njarvis_unified_boot.py: {len(pids)} instances")
    if len(pids) > 1:
        killed, total = kill_pids(pids, keep_newest=True)
        print(f"  Killed {killed} duplicates, kept 1")
    else:
        print("  OK (1 instance)")

    # 3. Dashboard — kill duplicates
    pids = get_processes("dashboard//server.py")
    if not pids:
        pids = get_processes("dashboard/server.py")
    print(f"\ndashboard/server.py: {len(pids)} instances")
    if len(pids) > 1:
        killed, total = kill_pids(pids, keep_newest=True)
        print(f"  Killed {killed} duplicates, kept 1")
    else:
        print("  OK")

    # 4. Python WS — kill duplicates
    pids = get_processes("python_ws//server.py")
    if not pids:
        pids = get_processes("python_ws/server.py")
    print(f"\npython_ws/server.py: {len(pids)} instances")
    if len(pids) > 1:
        killed, total = kill_pids(pids, keep_newest=True)
        print(f"  Killed {killed} duplicates, kept 1")
    else:
        print("  OK")

    # 5. OpenClaw watchdog — kill duplicates
    pids = get_processes("openclaw_watchdog")
    print(f"\nopenclaw_watchdog: {len(pids)} instances")
    if len(pids) > 1:
        killed, total = kill_pids(pids, keep_newest=True)
        print(f"  Killed {killed} duplicates, kept 1")
    else:
        print("  OK")

    # Clean lock file
    lock = "/home/turbo/jarvis-m1-ops/data/.linkedin-scheduler.lock"
    try:
        os.unlink(lock)
        print(f"\nLock file removed: {lock}")
    except FileNotFoundError:
        print(f"\nNo lock file to clean")
    except Exception as e:
        print(f"\nLock file error: {e}")

    print("\n=== Cleanup done ===")

if __name__ == "__main__":
    main()
