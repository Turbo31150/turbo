#!/usr/bin/env python3
"""win_thermal_monitor.py — Moniteur thermique avancé.

GPU + CPU + disques, alerte surchauffe, historique.

Usage:
    python dev/win_thermal_monitor.py --once
    python dev/win_thermal_monitor.py --status
    python dev/win_thermal_monitor.py --history
    python dev/win_thermal_monitor.py --alert 85
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "thermal_monitor.db"
GPU_ALERT = 85
CPU_ALERT = 90


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS thermal_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, component TEXT, name TEXT,
        temp_c REAL, alert INTEGER)""")
    db.commit()
    return db


def get_gpu_temps():
    temps = []
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        for line in out.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                temps.append({
                    "component": "GPU",
                    "name": parts[1],
                    "temp_c": float(parts[2]),
                    "util_pct": float(parts[3]) if len(parts) > 3 else 0,
                })
    except Exception:
        pass
    return temps


def get_cpu_temp():
    try:
        out = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace root/wmi 2>$null | "
             "Select-Object -First 1 -ExpandProperty CurrentTemperature"],
            capture_output=True, text=True, timeout=10
        )
        val = out.stdout.strip()
        if val:
            kelvin_tenths = float(val)
            celsius = (kelvin_tenths / 10.0) - 273.15
            if 0 < celsius < 120:
                return [{"component": "CPU", "name": "CPU Zone", "temp_c": round(celsius, 1)}]
    except Exception:
        pass
    return []


def get_disk_temps():
    temps = []
    try:
        out = subprocess.run(
            ["powershell", "-Command",
             "Get-PhysicalDisk | Select-Object FriendlyName,MediaType,Size | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if out.stdout.strip():
            disks = json.loads(out.stdout)
            if isinstance(disks, dict):
                disks = [disks]
            for d in disks:
                temps.append({
                    "component": "Disk",
                    "name": d.get("FriendlyName", "Unknown"),
                    "temp_c": -1,  # No direct temp API without admin
                    "media": d.get("MediaType", "Unknown"),
                })
    except Exception:
        pass
    return temps


def do_status(alert_temp=None):
    db = init_db()
    gpu_alert = alert_temp or GPU_ALERT
    readings = []

    for r in get_gpu_temps():
        is_alert = r["temp_c"] >= gpu_alert
        readings.append({**r, "alert": is_alert})
        db.execute("INSERT INTO thermal_readings (ts, component, name, temp_c, alert) VALUES (?,?,?,?,?)",
                   (time.time(), r["component"], r["name"], r["temp_c"], int(is_alert)))

    for r in get_cpu_temp():
        is_alert = r["temp_c"] >= CPU_ALERT
        readings.append({**r, "alert": is_alert})
        db.execute("INSERT INTO thermal_readings (ts, component, name, temp_c, alert) VALUES (?,?,?,?,?)",
                   (time.time(), r["component"], r["name"], r["temp_c"], int(is_alert)))

    for r in get_disk_temps():
        readings.append({**r, "alert": False})

    alerts = [r for r in readings if r.get("alert")]
    db.commit()
    db.close()
    return {
        "ts": datetime.now().isoformat(),
        "readings": readings,
        "alerts": len(alerts),
        "alert_details": alerts,
        "thresholds": {"gpu": gpu_alert, "cpu": CPU_ALERT},
    }


def do_history():
    db = init_db()
    rows = db.execute(
        "SELECT ts, component, name, temp_c, alert FROM thermal_readings ORDER BY ts DESC LIMIT 100"
    ).fetchall()
    db.close()
    return {
        "ts": datetime.now().isoformat(),
        "entries": len(rows),
        "history": [
            {"ts": datetime.fromtimestamp(r[0]).isoformat(), "component": r[1],
             "name": r[2], "temp_c": r[3], "alert": bool(r[4])}
            for r in rows
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Thermal Monitor")
    parser.add_argument("--once", "--status", action="store_true", help="Current status")
    parser.add_argument("--history", action="store_true", help="History")
    parser.add_argument("--alert", type=int, metavar="TEMP", help="Alert threshold")
    parser.add_argument("--throttle", action="store_true", help="Check throttling")
    args = parser.parse_args()

    if args.history:
        print(json.dumps(do_history(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_status(args.alert), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
