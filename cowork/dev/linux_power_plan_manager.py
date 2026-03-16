#!/usr/bin/env python3
"""win_power_plan_manager.py (#191) — Power plan manager Windows 11.

Gere les plans d'alimentation: current, switch, create custom JARVIS plan,
benchmark mode auto (trading->performance, idle->balanced, night->power saver).

Usage:
    python dev/win_power_plan_manager.py --once
    python dev/win_power_plan_manager.py --current
    python dev/win_power_plan_manager.py --switch performance
    python dev/win_power_plan_manager.py --create
    python dev/win_power_plan_manager.py --benchmark
"""
import argparse
import json
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "power_plan_manager.db"

# Well-known power plan GUIDs
KNOWN_PLANS = {
    "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
    "high_performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
    "power_saver": "a1841308-3541-4fab-bc81-f71556f20b4a",
    "ultimate_performance": "e9a42b02-d5df-448d-aa00-03f14749eb61",
}

JARVIS_PLAN_NAME = "JARVIS Turbo"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS plan_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        plan_name TEXT,
        plan_guid TEXT,
        action TEXT,
        context TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS benchmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        plan_name TEXT,
        cpu_score REAL,
        gpu_score REAL,
        duration_s REAL,
        notes TEXT
    )""")
    db.commit()
    return db


def run_powercfg(*args):
    """Run powercfg and return stdout."""
    try:
        out = subprocess.run(
            ["powercfg"] + list(args),
            capture_output=True, timeout=10
        )
        # Decode with OEM codepage (cp850/cp437), fallback utf-8
        raw = out.stdout
        for enc in ("utf-8", "cp850", "cp437", "cp1252", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, AttributeError):
                continue
        else:
            text = raw.decode("latin-1", errors="replace")
        return text.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def get_current_plan():
    """Get active power scheme."""
    output = run_powercfg("/getactivescheme")
    if not output:
        return {"name": "unknown", "guid": ""}

    # Parse: Power Scheme GUID: xxx-xxx  (Name)
    match = re.search(r'GUID:\s*([a-f0-9-]+)\s*\(([^)]+)\)', output, re.IGNORECASE)
    if match:
        return {"guid": match.group(1), "name": match.group(2).strip()}

    # Fallback
    guid_match = re.search(r'([a-f0-9]{8}-[a-f0-9-]+)', output)
    return {
        "guid": guid_match.group(1) if guid_match else "",
        "name": output.split("(")[-1].rstrip(")").strip() if "(" in output else "unknown"
    }


def list_plans():
    """List all available power plans."""
    output = run_powercfg("/list")
    plans = []
    active_guid = get_current_plan()["guid"]

    for line in output.split("\n"):
        # Match both English "GUID:" and French "GUID du mode..."
        match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\s+\(([^)]+)\)', line, re.IGNORECASE)
        if match:
            guid = match.group(1)
            name = match.group(2).strip()
            is_active = "*" in line[line.rfind(")"):] if ")" in line else False
            plans.append({
                "guid": guid,
                "name": name,
                "active": guid == active_guid or is_active,
                "is_known": guid in KNOWN_PLANS.values()
            })
    return plans


def current(db):
    """Show current power plan."""
    plan = get_current_plan()
    all_plans = list_plans()

    db.execute(
        "INSERT INTO plan_history (ts, plan_name, plan_guid, action, context) VALUES (?,?,?,?,?)",
        (time.time(), plan["name"], plan["guid"], "query", "current")
    )
    db.commit()

    return {
        "status": "ok",
        "active_plan": plan,
        "available_plans": all_plans,
        "total_plans": len(all_plans)
    }


def switch_plan(db, plan_key):
    """Switch to a named power plan."""
    plan_key_lower = plan_key.lower().replace(" ", "_").replace("-", "_")

    # Try known GUIDs first
    target_guid = KNOWN_PLANS.get(plan_key_lower)

    # Try matching by name in available plans
    if not target_guid:
        for p in list_plans():
            if plan_key_lower in p["name"].lower().replace(" ", "_").replace("-", "_"):
                target_guid = p["guid"]
                break

    # Try aliases
    aliases = {
        "performance": "high_performance",
        "perf": "high_performance",
        "ultimate": "ultimate_performance",
        "saver": "power_saver",
        "eco": "power_saver",
        "jarvis": None,  # special
    }
    if not target_guid and plan_key_lower in aliases:
        alias = aliases[plan_key_lower]
        if alias:
            target_guid = KNOWN_PLANS.get(alias)
        else:
            # Search JARVIS plan
            for p in list_plans():
                if "jarvis" in p["name"].lower():
                    target_guid = p["guid"]
                    break

    if not target_guid:
        return {
            "status": "error",
            "error": f"Plan '{plan_key}' not found",
            "available": [p["name"] for p in list_plans()],
            "known_keys": list(KNOWN_PLANS.keys())
        }

    old_plan = get_current_plan()
    run_powercfg("/setactive", target_guid)
    new_plan = get_current_plan()

    success = new_plan["guid"] == target_guid

    db.execute(
        "INSERT INTO plan_history (ts, plan_name, plan_guid, action, context) VALUES (?,?,?,?,?)",
        (time.time(), new_plan["name"], target_guid, "switch",
         f"from {old_plan['name']} to {plan_key}")
    )
    db.commit()

    return {
        "status": "ok" if success else "error",
        "previous": old_plan["name"],
        "current": new_plan["name"],
        "guid": target_guid,
        "switched": success
    }


def create_jarvis_plan(db):
    """Create custom JARVIS Turbo power plan."""
    # Check if already exists
    for p in list_plans():
        if "jarvis" in p["name"].lower():
            return {
                "status": "info",
                "message": f"JARVIS plan already exists: {p['name']}",
                "guid": p["guid"]
            }

    # Duplicate high performance as base
    base_guid = KNOWN_PLANS["high_performance"]
    output = run_powercfg("/duplicatescheme", base_guid)

    # Parse new GUID
    match = re.search(r'GUID:\s*([a-f0-9-]+)', output, re.IGNORECASE)
    if not match:
        match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', output)

    if not match:
        return {"status": "error", "error": "Failed to create plan", "output": output}

    new_guid = match.group(1)

    # Rename
    run_powercfg("/changename", new_guid, JARVIS_PLAN_NAME,
                 "Custom JARVIS power plan - GPU/CPU optimized")

    # Optimize settings for GPU workload
    # Processor performance: 100% min (AC)
    run_powercfg("/setacvalueindex", new_guid,
                 "54533251-82be-4824-96c1-47b60b740d00",
                 "893dee8e-2bef-41e0-89c6-b55d0929964c", "100")
    # Processor max: 100% (AC)
    run_powercfg("/setacvalueindex", new_guid,
                 "54533251-82be-4824-96c1-47b60b740d00",
                 "bc5038f7-23e0-4960-96da-33abaf5935ec", "100")
    # Turn off display after 15 min (AC)
    run_powercfg("/setacvalueindex", new_guid,
                 "7516b95f-f776-4464-8c53-06167f40cc99",
                 "3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e", "900")
    # Never sleep (AC)
    run_powercfg("/setacvalueindex", new_guid,
                 "238c9fa8-0aad-41ed-83f4-97be242c8f20",
                 "29f6c1db-86da-48c5-9fdb-f2b67b1f44da", "0")
    # Hard disk: never turn off (AC)
    run_powercfg("/setacvalueindex", new_guid,
                 "0012ee47-9041-4b5d-9b77-535fba8b1442",
                 "6738e2c4-e8a5-4a42-b16a-e040e769756e", "0")

    db.execute(
        "INSERT INTO plan_history (ts, plan_name, plan_guid, action, context) VALUES (?,?,?,?,?)",
        (time.time(), JARVIS_PLAN_NAME, new_guid, "create", "custom plan from high_performance")
    )
    db.commit()

    return {
        "status": "ok",
        "plan_name": JARVIS_PLAN_NAME,
        "guid": new_guid,
        "base": "High Performance",
        "optimizations": [
            "CPU min performance: 100%",
            "CPU max performance: 100%",
            "Display off: 15 min",
            "Sleep: Never",
            "Hard disk: Never turn off"
        ],
        "activate_cmd": "python dev/win_power_plan_manager.py --switch jarvis"
    }


def benchmark_plans(db):
    """Quick benchmark comparing power plans."""
    plans_to_test = []
    for p in list_plans():
        plans_to_test.append(p)

    original = get_current_plan()
    results = []

    for plan in plans_to_test[:3]:  # Test max 3 plans
        # Switch to plan
        run_powercfg("/setactive", plan["guid"])
        time.sleep(1)

        # Simple CPU benchmark: compute-intensive loop
        start = time.perf_counter()
        total = 0
        for i in range(500000):
            total += i * i
        cpu_duration = time.perf_counter() - start

        # Score: lower is better, normalize to 100
        cpu_score = round(max(0, 100 - cpu_duration * 100), 1)

        results.append({
            "plan": plan["name"],
            "guid": plan["guid"],
            "cpu_score": cpu_score,
            "cpu_time_ms": round(cpu_duration * 1000, 1)
        })

        db.execute(
            "INSERT INTO benchmarks (ts, plan_name, cpu_score, gpu_score, duration_s, notes) VALUES (?,?,?,?,?,?)",
            (time.time(), plan["name"], cpu_score, 0, cpu_duration, "auto-benchmark")
        )

    db.commit()

    # Restore original plan
    run_powercfg("/setactive", original["guid"])

    # Sort by score
    results.sort(key=lambda x: x["cpu_score"], reverse=True)

    return {
        "status": "ok",
        "benchmarks": results,
        "best_plan": results[0]["plan"] if results else "unknown",
        "restored_plan": original["name"]
    }


def auto_switch_context(db):
    """Auto-switch based on context: trading->perf, idle->balanced, night->saver."""
    hour = datetime.now().hour

    # Determine context
    if 0 <= hour < 6:
        context = "night"
        target = "power_saver"
    elif 6 <= hour < 9:
        context = "morning"
        target = "balanced"
    elif 9 <= hour < 22:
        context = "active"
        target = "high_performance"
    else:
        context = "evening"
        target = "balanced"

    # Check if trading is running
    try:
        out = subprocess.run(
            ["bash", "-NoProfile", "-Command",
             "Get-Process -Name python -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object { $_.MainWindowTitle }"],
            capture_output=True, text=True, timeout=5
        )
        if "trading" in out.stdout.lower():
            context = "trading"
            target = "high_performance"
    except Exception:
        pass

    return switch_plan(db, target)


def once(db):
    """Run once: show current plan + recommendation."""
    cur = current(db)
    hour = datetime.now().hour

    if 0 <= hour < 6:
        recommended = "power_saver"
    elif 9 <= hour < 22:
        recommended = "high_performance"
    else:
        recommended = "balanced"

    return {
        "status": "ok",
        "mode": "once",
        "script": "win_power_plan_manager.py (#191)",
        "current": cur,
        "time_of_day": f"{hour}:00",
        "recommended_plan": recommended,
        "total_switches": db.execute(
            "SELECT COUNT(*) FROM plan_history WHERE action='switch'"
        ).fetchone()[0]
    }


def main():
    parser = argparse.ArgumentParser(
        description="win_power_plan_manager.py (#191) — Power plan manager Windows 11"
    )
    parser.add_argument("--current", action="store_true",
                        help="Show current power plan")
    parser.add_argument("--switch", type=str, metavar="PLAN",
                        help="Switch to plan (balanced/performance/saver/jarvis)")
    parser.add_argument("--create", action="store_true",
                        help="Create custom JARVIS Turbo power plan")
    parser.add_argument("--benchmark", action="store_true",
                        help="Benchmark available power plans")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-switch based on time/context")
    parser.add_argument("--once", action="store_true",
                        help="Run once: show current + recommendation")
    args = parser.parse_args()

    db = init_db()

    if args.current:
        result = current(db)
    elif args.switch:
        result = switch_plan(db, args.switch)
    elif args.create:
        result = create_jarvis_plan(db)
    elif args.benchmark:
        result = benchmark_plans(db)
    elif args.auto:
        result = auto_switch_context(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        db.close()
        return

    output = json.dumps(result, ensure_ascii=False, indent=2)
    try:
        print(output)
    except UnicodeEncodeError:
        print(output.encode("utf-8", errors="replace").decode("ascii", errors="replace"))
    db.close()


if __name__ == "__main__":
    main()
