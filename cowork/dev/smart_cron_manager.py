#!/usr/bin/env python3
"""smart_cron_manager.py — Optimise les intervalles des taches autonomes.

Mesure GPU temp + CPU load et ajuste les interval_s des taches
dynamiquement (charge haute → ralentir, charge basse → accelerer).

Usage:
    python dev/smart_cron_manager.py --once
    python dev/smart_cron_manager.py --list
    python dev/smart_cron_manager.py --optimize
    python dev/smart_cron_manager.py --loop --interval 1800
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "smart_cron.db"
WS_URL = "http://127.0.0.1:9742"

# Default task intervals (seconds)
DEFAULT_INTERVALS = {
    "health_check": 60,
    "gpu_monitor": 120,
    "drift_reroute": 300,
    "budget_alert": 600,
    "auto_tune_sample": 300,
    "self_heal": 180,
    "proactive_suggest": 300,
    "db_backup": 3600,
    "weekly_cleanup": 86400,
    "brain_auto_learn": 1800,
    "improve_cycle": 86400,
    "predict_next_actions": 300,
    "auto_develop": 86400,
}

# Scaling factors based on load
LOAD_PROFILES = {
    "idle": 0.5,      # Half the interval (more frequent)
    "normal": 1.0,    # Default
    "busy": 1.5,      # 1.5x slower
    "heavy": 2.0,     # 2x slower
    "critical": 3.0,  # 3x slower (thermal protection)
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, gpu_temp REAL, cpu_load REAL,
        load_profile TEXT, adjustments TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS optimizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, task_name TEXT,
        old_interval INTEGER, new_interval INTEGER,
        reason TEXT)""")
    db.commit()
    return db


def get_gpu_temp():
    """Get GPU temperature via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            temps = [int(t.strip()) for t in result.stdout.strip().split("\n") if t.strip()]
            return max(temps) if temps else 0
    except Exception:
        pass
    return 0


def get_cpu_load():
    """Get CPU load percentage."""
    try:
        result = subprocess.run(
            ["bash", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    return 0


def determine_load_profile(gpu_temp, cpu_load):
    """Determine current load profile."""
    if gpu_temp >= 85 or cpu_load >= 95:
        return "critical"
    elif gpu_temp >= 75 or cpu_load >= 80:
        return "heavy"
    elif gpu_temp >= 60 or cpu_load >= 50:
        return "busy"
    elif gpu_temp >= 40 or cpu_load >= 20:
        return "normal"
    else:
        return "idle"


def get_current_tasks():
    """Get current autonomous task status."""
    try:
        req = urllib.request.Request(f"{WS_URL}/api/autonomous/status")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            return data.get("tasks", {})
    except Exception:
        return {}


def calculate_adjustments(profile, tasks):
    """Calculate interval adjustments based on load profile."""
    factor = LOAD_PROFILES.get(profile, 1.0)
    adjustments = {}

    for name, default_interval in DEFAULT_INTERVALS.items():
        task = tasks.get(name, {})
        current = task.get("interval_s", default_interval) if isinstance(task, dict) else default_interval
        new_interval = max(30, int(default_interval * factor))

        # Don't adjust critical tasks below their minimum
        if name in ("health_check", "self_heal") and new_interval < 30:
            new_interval = 30
        if name in ("db_backup", "weekly_cleanup") and new_interval < 1800:
            new_interval = 1800

        if abs(new_interval - current) > current * 0.1:  # Only adjust if >10% change
            adjustments[name] = {
                "current": current,
                "new": new_interval,
                "factor": factor,
                "reason": f"load_profile={profile}",
            }

    return adjustments


def do_optimize():
    """Run optimization cycle."""
    db = init_db()

    gpu_temp = get_gpu_temp()
    cpu_load = get_cpu_load()
    profile = determine_load_profile(gpu_temp, cpu_load)
    tasks = get_current_tasks()

    adjustments = calculate_adjustments(profile, tasks)

    # Store snapshot
    db.execute(
        "INSERT INTO snapshots (ts, gpu_temp, cpu_load, load_profile, adjustments) VALUES (?,?,?,?,?)",
        (time.time(), gpu_temp, cpu_load, profile, json.dumps(adjustments))
    )

    # Store individual optimizations
    for name, adj in adjustments.items():
        db.execute(
            "INSERT INTO optimizations (ts, task_name, old_interval, new_interval, reason) VALUES (?,?,?,?,?)",
            (time.time(), name, adj["current"], adj["new"], adj["reason"])
        )

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "gpu_temp": gpu_temp,
        "cpu_load": cpu_load,
        "load_profile": profile,
        "scale_factor": LOAD_PROFILES.get(profile, 1.0),
        "adjustments": adjustments,
        "tasks_monitored": len(DEFAULT_INTERVALS),
    }


def list_tasks():
    """List current task intervals and status."""
    tasks = get_current_tasks()
    result = []
    for name, default in DEFAULT_INTERVALS.items():
        task = tasks.get(name, {})
        result.append({
            "name": name,
            "default_interval": default,
            "current_interval": task.get("interval_s", default) if isinstance(task, dict) else default,
            "run_count": task.get("run_count", 0) if isinstance(task, dict) else 0,
            "fail_count": task.get("fail_count", 0) if isinstance(task, dict) else 0,
        })
    return result


def main():
    parser = argparse.ArgumentParser(description="Smart Cron Manager — Dynamic task interval optimization")
    parser.add_argument("--once", "--optimize", action="store_true", help="Run optimization cycle")
    parser.add_argument("--list", action="store_true", help="List tasks and intervals")
    parser.add_argument("--loop", action="store_true", help="Continuous optimization")
    parser.add_argument("--interval", type=int, default=1800, help="Loop interval (seconds)")
    args = parser.parse_args()

    if args.list:
        result = list_tasks()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.loop:
        print(f"[SMART_CRON] Starting continuous optimization (interval={args.interval}s)")
        while True:
            try:
                result = do_optimize()
                adj = len(result["adjustments"])
                print(f"[{result['ts']}] GPU:{result['gpu_temp']}C CPU:{result['cpu_load']}% Profile:{result['load_profile']} Adjustments:{adj}")
            except Exception as e:
                print(f"[ERROR] Optimize failed: {e}")
            time.sleep(args.interval)
    else:
        result = do_optimize()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
