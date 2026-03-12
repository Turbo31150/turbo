#!/usr/bin/env python3
"""win_game_mode_manager.py — Windows Game Mode manager with process control.
COWORK #237 — Batch 107: Windows Gaming & Media

Usage:
    python dev/win_game_mode_manager.py --activate
    python dev/win_game_mode_manager.py --deactivate
    python dev/win_game_mode_manager.py --profile "Cyberpunk"
    python dev/win_game_mode_manager.py --stats
    python dev/win_game_mode_manager.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "game_mode.db"

# Non-essential processes to kill in game mode
KILLABLE_PROCESSES = [
    "SearchUI.exe", "SearchHost.exe", "OneDrive.exe", "Teams.exe",
    "Spotify.exe", "Discord.exe", "Slack.exe", "Skype.exe",
    "PhoneExperienceHost.exe", "YourPhone.exe", "cortana.exe",
    "WidgetService.exe", "GameBar.exe"
]

# Essential processes to never kill
PROTECTED_PROCESSES = [
    "explorer.exe", "svchost.exe", "csrss.exe", "winlogon.exe",
    "lsass.exe", "services.exe", "System", "smss.exe",
    "dwm.exe", "taskhostw.exe", "RuntimeBroker.exe",
    "LMStudio.exe", "ollama.exe", "node.exe", "python.exe"
]

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS game_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        action TEXT NOT NULL,
        game_profile TEXT,
        processes_killed TEXT,
        power_plan TEXT,
        game_mode_enabled INTEGER,
        duration_seconds INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS game_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        kill_processes TEXT DEFAULT '[]',
        priority TEXT DEFAULT 'high',
        power_plan TEXT DEFAULT 'performance',
        notes TEXT,
        created_at TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS game_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        profile TEXT,
        duration_minutes INTEGER,
        processes_killed INTEGER DEFAULT 0,
        ram_freed_mb REAL DEFAULT 0
    )""")
    # Default profiles
    if db.execute("SELECT COUNT(*) FROM game_profiles").fetchone()[0] == 0:
        now = datetime.now().isoformat()
        defaults = [
            ("Default", json.dumps(KILLABLE_PROCESSES[:5]), "high", "performance", "Standard game mode"),
            ("Maximum", json.dumps(KILLABLE_PROCESSES), "realtime", "performance", "Maximum performance — kills all non-essential"),
            ("Streaming", json.dumps(KILLABLE_PROCESSES[:3]), "high", "balanced", "Gaming + OBS/streaming friendly"),
        ]
        for name, kill, prio, power, notes in defaults:
            db.execute("INSERT INTO game_profiles (name, kill_processes, priority, power_plan, notes, created_at) VALUES (?,?,?,?,?,?)",
                       (name, kill, prio, power, notes, now))
    db.commit()
    return db

def check_game_mode_registry():
    """Check if Windows Game Mode is enabled in registry."""
    try:
        cmd = 'powershell -NoProfile -Command "(Get-ItemProperty -Path \'HKCU:/SOFTWARE/Microsoft/GameBar\' -Name \'AutoGameModeEnabled\' -ErrorAction SilentlyContinue).AutoGameModeEnabled"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        val = r.stdout.strip()
        return val == "1"
    except Exception:
        return None

def set_game_mode_registry(enabled):
    """Enable/disable Game Mode via registry."""
    val = 1 if enabled else 0
    try:
        cmd = f'powershell -NoProfile -Command "Set-ItemProperty -Path \'HKCU:/SOFTWARE/Microsoft/GameBar\' -Name \'AutoGameModeEnabled\' -Value {val} -Type DWord -Force; Write-Output OK"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        return "OK" in r.stdout
    except Exception:
        return False

def get_power_plan():
    """Get current power plan."""
    try:
        cmd = 'powershell -NoProfile -Command "(powercfg /getactivescheme) -replace \'.*: \',\'\'"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        return r.stdout.strip()[:100]
    except Exception:
        return "unknown"

def set_power_plan(plan_type="performance"):
    """Set power plan."""
    plans = {
        "performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
        "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
        "power_saver": "a1841308-3541-4fab-bc81-f71556f20b4a"
    }
    guid = plans.get(plan_type, plans["performance"])
    try:
        cmd = f'powercfg /setactive {guid}'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        return r.returncode == 0
    except Exception:
        return False

def kill_nonessential(process_list):
    """Kill non-essential processes."""
    killed = []
    for proc in process_list:
        if proc.lower() not in [p.lower() for p in PROTECTED_PROCESSES]:
            try:
                cmd = f'taskkill /IM "{proc}" /F 2>nul'
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=True)
                if r.returncode == 0:
                    killed.append(proc)
            except Exception:
                pass
    return killed

def do_activate(profile_name="Default"):
    db = init_db()
    profile = db.execute("SELECT name, kill_processes, priority, power_plan FROM game_profiles WHERE name=?", (profile_name,)).fetchone()
    if not profile:
        profile = db.execute("SELECT name, kill_processes, priority, power_plan FROM game_profiles ORDER BY id LIMIT 1").fetchone()

    kill_list = json.loads(profile[1]) if profile else KILLABLE_PROCESSES[:5]
    power = profile[3] if profile else "performance"

    # Enable Game Mode
    gm_ok = set_game_mode_registry(True)
    # Set power plan
    pp_ok = set_power_plan(power)
    # Kill processes
    killed = kill_nonessential(kill_list)

    prev_plan = get_power_plan()

    db.execute("INSERT INTO game_sessions (ts, action, game_profile, processes_killed, power_plan, game_mode_enabled) VALUES (?,?,?,?,?,?)",
               (datetime.now().isoformat(), "activate", profile[0] if profile else "Default",
                json.dumps(killed), power, int(gm_ok)))
    db.execute("INSERT INTO game_stats (ts, profile, processes_killed) VALUES (?,?,?)",
               (datetime.now().isoformat(), profile[0] if profile else "Default", len(killed)))
    db.commit()

    result = {
        "action": "activate",
        "profile": profile[0] if profile else "Default",
        "game_mode_enabled": gm_ok,
        "power_plan_set": pp_ok,
        "power_plan": power,
        "processes_killed": killed,
        "total_killed": len(killed),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_deactivate():
    db = init_db()
    # Restore balanced power plan
    pp_ok = set_power_plan("balanced")
    # Keep game mode enabled (Windows default)

    db.execute("INSERT INTO game_sessions (ts, action, power_plan, game_mode_enabled) VALUES (?,?,?,?)",
               (datetime.now().isoformat(), "deactivate", "balanced", 1))
    db.commit()

    result = {
        "action": "deactivate",
        "power_plan_restored": pp_ok,
        "power_plan": "balanced",
        "note": "Killed processes must be restarted manually if needed",
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_profile(name):
    db = init_db()
    row = db.execute("SELECT name, kill_processes, priority, power_plan, notes, created_at FROM game_profiles WHERE name=?", (name,)).fetchone()
    if row:
        result = {
            "action": "profile_detail",
            "name": row[0],
            "kill_processes": json.loads(row[1]),
            "priority": row[2],
            "power_plan": row[3],
            "notes": row[4],
            "created_at": row[5]
        }
    else:
        profiles = db.execute("SELECT name, priority, power_plan, notes FROM game_profiles ORDER BY name").fetchall()
        result = {
            "action": "profile_not_found",
            "requested": name,
            "available_profiles": [{"name": r[0], "priority": r[1], "power": r[2], "notes": r[3]} for r in profiles]
        }
    result["ts"] = datetime.now().isoformat()
    db.close()
    return result

def do_stats():
    db = init_db()
    total_sessions = db.execute("SELECT COUNT(*) FROM game_sessions").fetchone()[0]
    activations = db.execute("SELECT COUNT(*) FROM game_sessions WHERE action='activate'").fetchone()[0]
    total_killed = db.execute("SELECT SUM(processes_killed) FROM game_stats").fetchone()[0] or 0
    game_mode = check_game_mode_registry()
    power = get_power_plan()
    recent = db.execute("SELECT ts, action, game_profile, processes_killed FROM game_sessions ORDER BY id DESC LIMIT 10").fetchall()

    result = {
        "action": "stats",
        "total_sessions": total_sessions,
        "total_activations": activations,
        "total_processes_killed": total_killed,
        "current_game_mode": game_mode,
        "current_power_plan": power,
        "recent_sessions": [{"ts": r[0], "action": r[1], "profile": r[2], "killed": r[3]} for r in recent],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    game_mode = check_game_mode_registry()
    power = get_power_plan()
    profiles = db.execute("SELECT COUNT(*) FROM game_profiles").fetchone()[0]
    sessions = db.execute("SELECT COUNT(*) FROM game_sessions").fetchone()[0]
    result = {
        "status": "ok",
        "game_mode_enabled": game_mode,
        "current_power_plan": power,
        "profiles_available": profiles,
        "total_sessions": sessions,
        "killable_processes": len(KILLABLE_PROCESSES),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="Windows Game Mode Manager — COWORK #237")
    parser.add_argument("--activate", action="store_true", help="Activate game mode")
    parser.add_argument("--deactivate", action="store_true", help="Deactivate game mode")
    parser.add_argument("--profile", type=str, metavar="GAME", help="Show/set game profile")
    parser.add_argument("--stats", action="store_true", help="Show game mode statistics")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.activate:
        profile = args.profile or "Default"
        print(json.dumps(do_activate(profile), ensure_ascii=False, indent=2))
    elif args.deactivate:
        print(json.dumps(do_deactivate(), ensure_ascii=False, indent=2))
    elif args.profile:
        print(json.dumps(do_profile(args.profile), ensure_ascii=False, indent=2))
    elif args.stats:
        print(json.dumps(do_stats(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
