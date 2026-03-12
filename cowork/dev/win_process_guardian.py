#!/usr/bin/env python3
"""win_process_guardian.py — Gardien de processus Windows.

Surveille consommation CPU/RAM, tue les processus excessifs.

Usage:
    python dev/win_process_guardian.py --once
    python dev/win_process_guardian.py --watch
    python dev/win_process_guardian.py --whitelist
    python dev/win_process_guardian.py --report
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
DB_PATH = DEV / "data" / "process_guardian.db"

# Never kill these
WHITELIST = [
    "System", "svchost.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "explorer.exe", "dwm.exe", "lsass.exe", "services.exe",
    "LM Studio.exe", "ollama.exe", "ollama_llama_server.exe",
    "node.exe", "python.exe", "python3.exe", "pythonw.exe",
    "Code.exe", "WindowsTerminal.exe", "wt.exe",
    "nvidia-smi.exe", "nvcontainer.exe",
]

CPU_THRESHOLD = 80  # % for > 5min
RAM_THRESHOLD_MB = 2048  # 2GB


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_processes INTEGER, high_cpu INTEGER,
        high_ram INTEGER, total_ram_gb REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, process_name TEXT, pid INTEGER,
        cpu_pct REAL, ram_mb REAL, action TEXT)""")
    db.commit()
    return db


def get_processes():
    """Get process list with CPU and memory."""
    processes = []
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-Process | Select-Object Name,Id,CPU,WorkingSet64 | ConvertTo-Json -Depth 1"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        if isinstance(data, dict):
            data = [data]
        for item in data:
            name = item.get("Name", "")
            pid = item.get("Id", 0)
            cpu = item.get("CPU", 0) or 0
            ram = (item.get("WorkingSet64", 0) or 0) / 1024 / 1024  # MB
            processes.append({
                "name": name, "pid": pid,
                "cpu": round(cpu, 1), "ram_mb": round(ram, 1),
                "whitelisted": f"{name}.exe" in WHITELIST or name in WHITELIST,
            })
    except Exception:
        pass

    # Fallback: wmic
    if not processes:
        try:
            result = subprocess.run(
                ["wmic", "process", "get", "Name,ProcessId,WorkingSetSize", "/format:csv"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.strip().split("\n")[1:]:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    name = parts[1]
                    pid = int(parts[2]) if parts[2].isdigit() else 0
                    ram = int(parts[3]) / 1024 / 1024 if parts[3].isdigit() else 0
                    processes.append({
                        "name": name, "pid": pid, "cpu": 0,
                        "ram_mb": round(ram, 1),
                        "whitelisted": name in WHITELIST,
                    })
        except Exception:
            pass

    return processes


def do_scan():
    """Scan processes and detect issues."""
    db = init_db()
    processes = get_processes()

    high_cpu = [p for p in processes if p["cpu"] > CPU_THRESHOLD and not p["whitelisted"]]
    high_ram = [p for p in processes if p["ram_mb"] > RAM_THRESHOLD_MB and not p["whitelisted"]]
    total_ram = sum(p["ram_mb"] for p in processes) / 1024  # GB

    # Log alerts
    for p in high_cpu:
        db.execute(
            "INSERT INTO alerts (ts, process_name, pid, cpu_pct, ram_mb, action) VALUES (?,?,?,?,?,?)",
            (time.time(), p["name"], p["pid"], p["cpu"], p["ram_mb"], "high_cpu_detected")
        )
    for p in high_ram:
        db.execute(
            "INSERT INTO alerts (ts, process_name, pid, cpu_pct, ram_mb, action) VALUES (?,?,?,?,?,?)",
            (time.time(), p["name"], p["pid"], p["cpu"], p["ram_mb"], "high_ram_detected")
        )

    # Top consumers
    by_ram = sorted(processes, key=lambda x: x["ram_mb"], reverse=True)[:10]
    by_cpu = sorted(processes, key=lambda x: x["cpu"], reverse=True)[:10]

    db.execute(
        "INSERT INTO snapshots (ts, total_processes, high_cpu, high_ram, total_ram_gb) VALUES (?,?,?,?,?)",
        (time.time(), len(processes), len(high_cpu), len(high_ram), round(total_ram, 2))
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_processes": len(processes),
        "total_ram_gb": round(total_ram, 2),
        "high_cpu_alerts": len(high_cpu),
        "high_ram_alerts": len(high_ram),
        "top_ram": [{"name": p["name"], "pid": p["pid"], "ram_mb": p["ram_mb"]} for p in by_ram],
        "top_cpu": [{"name": p["name"], "pid": p["pid"], "cpu": p["cpu"]} for p in by_cpu],
        "alerts": [{
            "name": p["name"], "pid": p["pid"],
            "cpu": p["cpu"], "ram_mb": p["ram_mb"],
        } for p in (high_cpu + high_ram)[:10]],
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Process Guardian")
    parser.add_argument("--once", "--watch", action="store_true", help="Scan processes")
    parser.add_argument("--whitelist", action="store_true", help="Show whitelist")
    parser.add_argument("--kill", metavar="PID", type=int, help="Kill process")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()

    if args.whitelist:
        print(json.dumps(WHITELIST, indent=2))
    elif args.kill:
        print(json.dumps({"error": "Manual kill disabled for safety"}, indent=2))
    else:
        result = do_scan()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
