#!/usr/bin/env python3
"""win_power_optimizer.py — Optimisation dynamique alimentation Windows.

Switch entre profils selon activite GPU/CPU detectee.

Usage:
    python dev/win_power_optimizer.py --once
    python dev/win_power_optimizer.py --profile DEV
    python dev/win_power_optimizer.py --adaptive
    python dev/win_power_optimizer.py --status
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
DB_PATH = DEV / "data" / "power_optimizer.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS transitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, from_plan TEXT, to_plan TEXT, reason TEXT)""")
    db.commit()
    return db


def get_power_plans():
    """List available power plans."""
    plans = {}
    try:
        result = subprocess.run(
            ["powercfg", "/list"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if "GUID" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    guid_part = parts[1].strip().split()
                    if guid_part:
                        guid = guid_part[0]
                        name = line.split("(")[-1].rstrip(") *\n") if "(" in line else guid
                        active = "*" in line
                        plans[name] = {"guid": guid, "active": active}
    except Exception:
        pass
    return plans


def get_active_plan():
    """Get current active power plan."""
    plans = get_power_plans()
    for name, info in plans.items():
        if info["active"]:
            return name
    return "Unknown"


def get_gpu_usage():
    """Get GPU temperature and load."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            if len(parts) >= 2:
                return {"temp": int(parts[0].strip()), "load": int(parts[1].strip())}
    except Exception:
        pass
    return {"temp": 0, "load": 0}


def get_cpu_load():
    """Get CPU load."""
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


def set_power_plan(guid):
    """Set active power plan."""
    try:
        subprocess.run(["powercfg", "/setactive", guid], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def do_adaptive():
    """Adaptive power management based on current load."""
    db = init_db()
    gpu = get_gpu_usage()
    cpu = get_cpu_load()
    current = get_active_plan()
    plans = get_power_plans()

    # Determine target profile
    if gpu["load"] > 70 or gpu["temp"] > 75:
        target = "Performances elevees"
        reason = f"GPU haute charge (load={gpu['load']}%, temp={gpu['temp']}C)"
    elif cpu > 60:
        target = "Performances elevees"
        reason = f"CPU haute charge ({cpu}%)"
    elif gpu["load"] < 10 and cpu < 20:
        target = "Usage normal"
        reason = f"Systeme idle (GPU={gpu['load']}%, CPU={cpu}%)"
    else:
        target = current
        reason = "No change needed"

    # Find matching plan
    changed = False
    for name, info in plans.items():
        if target.lower() in name.lower() and not info["active"]:
            set_power_plan(info["guid"])
            db.execute(
                "INSERT INTO transitions (ts, from_plan, to_plan, reason) VALUES (?,?,?,?)",
                (time.time(), current, name, reason)
            )
            db.commit()
            changed = True
            break

    db.close()
    return {
        "ts": datetime.now().isoformat(),
        "gpu": gpu, "cpu_load": cpu,
        "current_plan": current,
        "target": target,
        "changed": changed,
        "reason": reason,
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Power Optimizer")
    parser.add_argument("--once", "--adaptive", action="store_true", help="Adaptive power")
    parser.add_argument("--profile", metavar="NAME", help="Set specific profile")
    parser.add_argument("--status", action="store_true", help="Current status")
    args = parser.parse_args()

    if args.status:
        plans = get_power_plans()
        gpu = get_gpu_usage()
        print(json.dumps({"plans": plans, "gpu": gpu, "active": get_active_plan()}, indent=2))
    else:
        result = do_adaptive()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
