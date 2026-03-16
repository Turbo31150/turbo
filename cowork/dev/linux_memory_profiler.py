#!/usr/bin/env python3
"""win_memory_profiler.py — Profileur mémoire Windows.

Detecte fuites, processus gourmands, tendances.

Usage:
    python dev/win_memory_profiler.py --once
    python dev/win_memory_profiler.py --snapshot
    python dev/win_memory_profiler.py --leaks
    python dev/win_memory_profiler.py --top
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "memory_profiler.db"
RAM_ALERT_PCT = 90
LEAK_GROWTH_PCT = 10


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_mb REAL, used_mb REAL, free_mb REAL, pct REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS process_mem (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, name TEXT, pid INTEGER, mem_mb REAL)""")
    db.commit()
    return db


def get_system_mem():
    try:
        out = subprocess.run(
            ["bash", "-Command",
             "$os=Get-CimInstance Win32_OperatingSystem;"
             "Write-Output \"$($os.TotalVisibleMemorySize),$($os.FreePhysicalMemory)\""],
            capture_output=True, text=True, timeout=10
        )
        parts = out.stdout.strip().split(",")
        if len(parts) == 2:
            total_kb, free_kb = float(parts[0]), float(parts[1])
            total_mb = total_kb / 1024
            free_mb = free_kb / 1024
            used_mb = total_mb - free_mb
            return {"total_mb": round(total_mb), "used_mb": round(used_mb),
                    "free_mb": round(free_mb), "pct": round(used_mb / total_mb * 100, 1)}
    except Exception:
        pass
    return {"total_mb": 0, "used_mb": 0, "free_mb": 0, "pct": 0}


def get_top_processes(n=20):
    procs = []
    try:
        out = subprocess.run(
            ["bash", "-Command",
             "Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First "
             f"{n} Name,Id,@{{N='MemMB';E={{[math]::Round($_.WorkingSet64/1MB,1)}}}} | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15
        )
        if out.stdout.strip():
            data = json.loads(out.stdout)
            if isinstance(data, dict):
                data = [data]
            for p in data:
                procs.append({
                    "name": p.get("Name", "?"),
                    "pid": p.get("Id", 0),
                    "mem_mb": p.get("MemMB", 0),
                })
    except Exception:
        pass
    return procs


def do_snapshot():
    db = init_db()
    mem = get_system_mem()
    procs = get_top_processes()

    db.execute("INSERT INTO snapshots (ts, total_mb, used_mb, free_mb, pct) VALUES (?,?,?,?,?)",
               (time.time(), mem["total_mb"], mem["used_mb"], mem["free_mb"], mem["pct"]))
    for p in procs:
        db.execute("INSERT INTO process_mem (ts, name, pid, mem_mb) VALUES (?,?,?,?)",
                   (time.time(), p["name"], p["pid"], p["mem_mb"]))
    db.commit()
    db.close()

    alert = mem["pct"] >= RAM_ALERT_PCT
    return {
        "ts": datetime.now().isoformat(),
        "system": mem,
        "alert": alert,
        "top_processes": procs[:10],
        "total_tracked": len(procs),
    }


def do_leaks():
    db = init_db()
    # Compare last 2 snapshots per process
    rows = db.execute("""
        SELECT name, mem_mb, ts FROM process_mem
        WHERE ts > ? ORDER BY ts DESC
    """, (time.time() - 3600,)).fetchall()
    db.close()

    by_proc = {}
    for name, mem, ts in rows:
        by_proc.setdefault(name, []).append((ts, mem))

    suspects = []
    for name, readings in by_proc.items():
        if len(readings) < 2:
            continue
        readings.sort()
        first, last = readings[0][1], readings[-1][1]
        if first > 0:
            growth = (last - first) / first * 100
            if growth > LEAK_GROWTH_PCT:
                suspects.append({
                    "name": name, "first_mb": first, "last_mb": last,
                    "growth_pct": round(growth, 1), "readings": len(readings),
                })

    suspects.sort(key=lambda x: x["growth_pct"], reverse=True)
    return {
        "ts": datetime.now().isoformat(),
        "suspects": suspects[:10],
        "threshold_pct": LEAK_GROWTH_PCT,
        "analysis_window": "1h",
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Memory Profiler")
    parser.add_argument("--once", "--snapshot", action="store_true", help="Take snapshot")
    parser.add_argument("--leaks", action="store_true", help="Detect leaks")
    parser.add_argument("--top", action="store_true", help="Top processes")
    parser.add_argument("--history", action="store_true", help="History")
    args = parser.parse_args()

    if args.leaks:
        print(json.dumps(do_leaks(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_snapshot(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
