#!/usr/bin/env python3
"""process_gc.py — Garbage collector for zombie Python processes.

Scans for orphan Python processes spawned by cowork/dev scripts,
kills those exceeding age or memory thresholds, and logs actions.

The #1 cause of JARVIS system degradation: cowork scripts spawn
Python subprocesses via `uv run` that accumulate without cleanup.
With 438 scripts, some running every 5-10 minutes, zombie processes
pile up until RAM/VRAM overflow causes VIDEO_TDR_FAILURE (green screen).

Usage:
    python scripts/process_gc.py --once          # Single GC pass
    python scripts/process_gc.py --loop           # Continuous (every 5min)
    python scripts/process_gc.py --dry-run        # Show what would be killed
    python scripts/process_gc.py --status         # Show current process count

Stdlib-only (subprocess, json, time, argparse, sqlite3).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

TURBO_DIR = Path("/home/turbo/jarvis-m1-ops")
LOG_DIR = TURBO_DIR / "logs"
DB_PATH = TURBO_DIR / "data" / "process_gc.db"

# Processes matching these command-line patterns are GC candidates.
# They are cowork scripts that should finish quickly (<120s).
COWORK_PATTERNS = [
    "cowork//dev//",
    "cowork/dev/",
]

# NEVER kill these — they are long-running services.
PROTECTED_PATTERNS = [
    "server.py",
    "unified_boot.py",
    "telegram-bot",
    "linkedin_scheduler",
    "openclaw",
    "watchdog",
    "dashboard",
    "process_gc.py",  # self
    "whisperflow",
    "vram_guard.py",
]

# Thresholds
MAX_AGE_S = 180          # Kill cowork processes older than 3 minutes
MAX_MEMORY_MB = 512      # Kill any Python process using >512MB RSS
MAX_COWORK_PROCS = 20    # Alert if more than 20 cowork processes running
GC_INTERVAL_S = 300      # 5 minutes between GC cycles


def init_db() -> sqlite3.Connection:
    """Create/open the GC log database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS gc_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        pid INTEGER NOT NULL,
        name TEXT,
        cmdline TEXT,
        age_s REAL,
        memory_mb REAL,
        reason TEXT,
        action TEXT
    )""")
    conn.commit()
    return conn


def get_python_processes() -> list[dict]:
    """Get all Python processes with PID, name, command line, and memory."""
    try:
        # Use wmic for reliable process enumeration on Windows
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'",
             "get", "ProcessId,CommandLine,WorkingSetSize,CreationDate",
             "/FORMAT:CSV"],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
        processes = []
        for line in r.stdout.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("Node"):
                continue
            parts = line.split(",")
            if len(parts) < 5:
                continue
            # CSV format: Node,CommandLine,CreationDate,ProcessId,WorkingSetSize
            try:
                cmdline = parts[1] if len(parts) > 1 else ""
                creation = parts[2] if len(parts) > 2 else ""
                pid = int(parts[3]) if len(parts) > 3 and parts[3].strip().isdigit() else 0
                wss = int(parts[4]) if len(parts) > 4 and parts[4].strip().isdigit() else 0
            except (ValueError, IndexError):
                continue

            if pid == 0 or pid == os.getpid():
                continue

            # Parse creation date (WMI format: 20260307143022.123456+060)
            age_s = 0.0
            if creation and len(creation) >= 14:
                try:
                    dt_str = creation[:14]
                    dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
                    age_s = (datetime.now() - dt).total_seconds()
                except ValueError:
                    pass

            processes.append({
                "pid": pid,
                "cmdline": cmdline,
                "age_s": age_s,
                "memory_mb": round(wss / (1024 * 1024), 1),
            })
        return processes
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"[GC] Error enumerating processes: {e}")
        return []


def is_cowork_process(cmdline: str) -> bool:
    """Check if a process command line matches cowork patterns."""
    for pat in COWORK_PATTERNS:
        if pat in cmdline:
            return True
    return False


def is_protected(cmdline: str) -> bool:
    """Check if a process is a protected long-running service."""
    cmdline_lower = cmdline.lower()
    for pat in PROTECTED_PATTERNS:
        if pat.lower() in cmdline_lower:
            return True
    return False


def gc_pass(dry_run: bool = False, conn: sqlite3.Connection | None = None) -> dict:
    """Run one GC pass. Returns summary dict."""
    processes = get_python_processes()
    now = datetime.now().isoformat()

    killed = 0
    skipped = 0
    protected = 0
    errors = 0
    details = []

    cowork_count = sum(1 for p in processes if is_cowork_process(p["cmdline"]))

    for proc in processes:
        cmdline = proc["cmdline"]
        pid = proc["pid"]
        age_s = proc["age_s"]
        mem_mb = proc["memory_mb"]

        # Skip protected processes
        if is_protected(cmdline):
            protected += 1
            continue

        reason = None

        # Rule 1: Cowork process older than MAX_AGE_S
        if is_cowork_process(cmdline) and age_s > MAX_AGE_S:
            reason = f"cowork_timeout({age_s:.0f}s>{MAX_AGE_S}s)"

        # Rule 2: Any Python process using excessive memory
        elif mem_mb > MAX_MEMORY_MB:
            reason = f"memory_hog({mem_mb:.0f}MB>{MAX_MEMORY_MB}MB)"

        if not reason:
            skipped += 1
            continue

        # Kill or log
        action = "dry_run" if dry_run else "killed"
        if not dry_run:
            try:
                os.kill(pid, 9)  # SIGKILL
                action = "killed"
                killed += 1
            except OSError as e:
                action = f"error:{e}"
                errors += 1
        else:
            killed += 1  # Count as "would kill" for dry-run

        detail = {
            "pid": pid,
            "cmdline": cmdline[:200],
            "age_s": round(age_s, 1),
            "memory_mb": mem_mb,
            "reason": reason,
            "action": action,
        }
        details.append(detail)

        if conn:
            try:
                conn.execute(
                    "INSERT INTO gc_log (timestamp, pid, name, cmdline, age_s, memory_mb, reason, action) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (now, pid, "python.exe", cmdline[:500], age_s, mem_mb, reason, action))
                conn.commit()
            except sqlite3.Error:
                pass

    summary = {
        "timestamp": now,
        "total_python": len(processes),
        "cowork_active": cowork_count,
        "killed": killed,
        "skipped": skipped,
        "protected": protected,
        "errors": errors,
        "alert": cowork_count > MAX_COWORK_PROCS,
        "details": details,
    }
    return summary


def print_status():
    """Show current Python process state."""
    processes = get_python_processes()
    cowork = [p for p in processes if is_cowork_process(p["cmdline"])]
    heavy = [p for p in processes if p["memory_mb"] > 200]

    print(f"\n  Python processes: {len(processes)}")
    print(f"  Cowork scripts:  {len(cowork)}")
    print(f"  Heavy (>200MB):  {len(heavy)}")

    if cowork:
        print(f"\n  Active cowork processes:")
        for p in sorted(cowork, key=lambda x: -x["age_s"])[:15]:
            script = p["cmdline"].split("/")[-1].split("/")[-1][:40] if p["cmdline"] else "?"
            print(f"    PID {p['pid']:6d}  {p['age_s']:6.0f}s  {p['memory_mb']:6.1f}MB  {script}")

    if heavy:
        print(f"\n  Heavy Python processes:")
        for p in sorted(heavy, key=lambda x: -x["memory_mb"])[:10]:
            script = p["cmdline"][:60] if p["cmdline"] else "?"
            print(f"    PID {p['pid']:6d}  {p['memory_mb']:6.1f}MB  {script}")

    alert = len(cowork) > MAX_COWORK_PROCS
    if alert:
        print(f"\n  ALERT: {len(cowork)} cowork processes > threshold ({MAX_COWORK_PROCS})")

    return {"total": len(processes), "cowork": len(cowork), "heavy": len(heavy), "alert": alert}


def main():
    parser = argparse.ArgumentParser(description="Process GC — kill zombie Python processes")
    parser.add_argument("--once", action="store_true", help="Single GC pass")
    parser.add_argument("--loop", action="store_true", help=f"Continuous GC every {GC_INTERVAL_S}s")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be killed")
    parser.add_argument("--status", action="store_true", help="Show current process status")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not any([args.once, args.loop, args.dry_run, args.status]):
        parser.print_help()
        sys.exit(1)

    if args.status:
        result = print_status()
        if args.json:
            print(json.dumps(result))
        return

    conn = init_db()

    if args.once or args.dry_run:
        summary = gc_pass(dry_run=args.dry_run, conn=conn)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            prefix = "[DRY-RUN] " if args.dry_run else ""
            print(f"\n  {prefix}Process GC: {summary['killed']} killed, "
                  f"{summary['skipped']} skipped, {summary['protected']} protected")
            for d in summary["details"]:
                script = d["cmdline"].split("/")[-1].split("/")[-1][:40]
                print(f"    {d['action']:8s} PID {d['pid']:6d}  {d['reason']}  {script}")
        conn.close()
        return

    if args.loop:
        print(f"[Process GC] Loop mode — cycle every {GC_INTERVAL_S}s")
        print(f"[Process GC] Thresholds: age>{MAX_AGE_S}s, memory>{MAX_MEMORY_MB}MB")
        while True:
            try:
                summary = gc_pass(dry_run=False, conn=conn)
                ts = datetime.now().strftime("%H:%M:%S")
                killed = summary["killed"]
                total = summary["total_python"]
                cowork = summary["cowork_active"]
                if killed > 0 or cowork > 5:
                    print(f"  [{ts}] GC: {killed} killed | {cowork} cowork / {total} python")
                time.sleep(GC_INTERVAL_S)
            except KeyboardInterrupt:
                break
        conn.close()


if __name__ == "__main__":
    main()
