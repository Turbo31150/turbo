#!/usr/bin/env python3
"""win_io_analyzer.py — Analyseur I/O disque.

Detecte goulots, processus I/O intensifs, latence disque.

Usage:
    python dev/win_io_analyzer.py --once
    python dev/win_io_analyzer.py --monitor
    python dev/win_io_analyzer.py --top
    python dev/win_io_analyzer.py --history
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
DB_PATH = DEV / "data" / "io_analyzer.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS io_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, name TEXT, pid INTEGER,
        read_ops INTEGER, write_ops INTEGER,
        read_bytes INTEGER, write_bytes INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS disk_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, drive TEXT, total_gb REAL, free_gb REAL, pct_used REAL)""")
    db.commit()
    return db


def get_io_processes(n=20):
    procs = []
    try:
        out = subprocess.run(
            ["bash", "-Command",
             "Get-Process | Where-Object {$_.Id -ne 0} | "
             "Sort-Object @{E={$_.IO.ReadBytes + $_.IO.WriteBytes}} -Descending | "
             f"Select-Object -First {n} Name,Id,"
             "@{N='ReadOps';E={$_.IO.ReadOperationCount}},"
             "@{N='WriteOps';E={$_.IO.WriteOperationCount}},"
             "@{N='ReadMB';E={[math]::Round($_.IO.ReadBytes/1MB,1)}},"
             "@{N='WriteMB';E={[math]::Round($_.IO.WriteBytes/1MB,1)}} | ConvertTo-Json"],
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
                    "read_ops": p.get("ReadOps", 0) or 0,
                    "write_ops": p.get("WriteOps", 0) or 0,
                    "read_mb": p.get("ReadMB", 0) or 0,
                    "write_mb": p.get("WriteMB", 0) or 0,
                })
    except Exception:
        pass
    return procs


def get_disk_stats():
    stats = []
    try:
        out = subprocess.run(
            ["bash", "-Command",
             "Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Used -gt 0} | "
             "Select-Object Name,@{N='TotalGB';E={[math]::Round(($_.Used+$_.Free)/1GB,1)}},"
             "@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}},"
             "@{N='PctUsed';E={[math]::Round($_.Used/($_.Used+$_.Free)*100,1)}} | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if out.stdout.strip():
            data = json.loads(out.stdout)
            if isinstance(data, dict):
                data = [data]
            for d in data:
                stats.append({
                    "drive": d.get("Name", "?") + ":",
                    "total_gb": d.get("TotalGB", 0),
                    "free_gb": d.get("FreeGB", 0),
                    "pct_used": d.get("PctUsed", 0),
                })
    except Exception:
        pass
    return stats


def do_monitor():
    db = init_db()
    procs = get_io_processes()
    disks = get_disk_stats()

    for p in procs:
        db.execute("INSERT INTO io_snapshots (ts, name, pid, read_ops, write_ops, read_bytes, write_bytes) VALUES (?,?,?,?,?,?,?)",
                   (time.time(), p["name"], p["pid"], p["read_ops"], p["write_ops"],
                    int(p["read_mb"] * 1024 * 1024), int(p["write_mb"] * 1024 * 1024)))
    for d in disks:
        db.execute("INSERT INTO disk_stats (ts, drive, total_gb, free_gb, pct_used) VALUES (?,?,?,?,?)",
                   (time.time(), d["drive"], d["total_gb"], d["free_gb"], d["pct_used"]))

    bottlenecks = [p for p in procs if (p["read_mb"] + p["write_mb"]) > 1000]
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "top_io_processes": procs[:10],
        "disk_stats": disks,
        "bottlenecks": bottlenecks,
        "total_read_mb": round(sum(p["read_mb"] for p in procs), 1),
        "total_write_mb": round(sum(p["write_mb"] for p in procs), 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Windows I/O Analyzer")
    parser.add_argument("--once", "--monitor", action="store_true", help="Monitor I/O")
    parser.add_argument("--top", action="store_true", help="Top I/O processes")
    parser.add_argument("--bottleneck", action="store_true", help="Detect bottlenecks")
    parser.add_argument("--history", action="store_true", help="History")
    args = parser.parse_args()
    print(json.dumps(do_monitor(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
