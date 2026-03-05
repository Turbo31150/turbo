#!/usr/bin/env python3
"""win_sound_mixer.py — Windows Sound Mixer with app volume control and profiles.
COWORK #220 — Batch 101: Windows Advanced Control

Usage:
    python dev/win_sound_mixer.py --apps
    python dev/win_sound_mixer.py --set "chrome" 50
    python dev/win_sound_mixer.py --profiles
    python dev/win_sound_mixer.py --schedule
    python dev/win_sound_mixer.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "sound_mixer.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS volume_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        master_volume INTEGER DEFAULT 50,
        app_volumes TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS volume_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        action TEXT NOT NULL,
        app TEXT,
        volume INTEGER,
        profile TEXT,
        details TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS volume_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile TEXT NOT NULL,
        hour_start INTEGER NOT NULL,
        hour_end INTEGER NOT NULL,
        days TEXT DEFAULT 'all',
        active INTEGER DEFAULT 1
    )""")
    # Insert default profiles if empty
    count = db.execute("SELECT COUNT(*) FROM volume_profiles").fetchone()[0]
    if count == 0:
        now = datetime.now().isoformat()
        defaults = [
            ("meeting", 30, '{"chrome": 80, "teams": 100, "spotify": 0}'),
            ("coding", 50, '{"spotify": 40, "chrome": 20, "teams": 50}'),
            ("gaming", 80, '{"steam": 100, "discord": 70, "chrome": 10}'),
            ("silent", 5, '{}'),
            ("normal", 50, '{"chrome": 50, "spotify": 50}'),
        ]
        for name, vol, apps in defaults:
            db.execute("INSERT INTO volume_profiles (name, master_volume, app_volumes, created_at, updated_at) VALUES (?,?,?,?,?)",
                       (name, vol, apps, now, now))
    db.commit()
    return db

def log_event(db, action, app=None, volume=None, profile=None, details=None):
    db.execute("INSERT INTO volume_events (ts, action, app, volume, profile, details) VALUES (?,?,?,?,?,?)",
               (datetime.now().isoformat(), action, app, volume, profile, details))
    db.commit()

def get_audio_apps():
    """Get running apps that may produce audio."""
    try:
        cmd = 'powershell -NoProfile -Command "Get-Process | Where-Object { $_.MainWindowTitle -ne \'\'} | Select-Object ProcessName, Id, MainWindowTitle | ConvertTo-Json"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=True)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            apps = []
            audio_hints = ["chrome", "firefox", "spotify", "vlc", "discord", "teams", "zoom",
                           "steam", "brave", "edge", "opera", "foobar", "musicbee", "winamp",
                           "obs", "audacity", "media", "video", "music", "player"]
            for proc in data:
                name = proc.get("ProcessName", "").lower()
                title = proc.get("MainWindowTitle", "")
                is_audio = any(h in name for h in audio_hints) or any(h in title.lower() for h in audio_hints)
                apps.append({
                    "name": proc.get("ProcessName", ""),
                    "pid": proc.get("Id", 0),
                    "title": title,
                    "likely_audio": is_audio
                })
            return apps
        return []
    except Exception as e:
        return [{"error": str(e)}]

def get_master_volume():
    """Get master volume via powershell."""
    try:
        cmd = 'powershell -NoProfile -Command "try { $audio = New-Object -ComObject WScript.Shell; Write-Output \'volume_check_ok\' } catch { Write-Output \'no_com\' }"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        # Alternative: nircmd approach or registry
        cmd2 = 'powershell -NoProfile -Command "(Get-ItemProperty -Path \'HKCU:\\SOFTWARE\\Microsoft\\Multimedia\\Audio\' -ErrorAction SilentlyContinue) | ConvertTo-Json"'
        r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10, shell=True)
        return {"status": "checked", "note": "Use Windows Volume Mixer for per-app control"}
    except Exception:
        return {"status": "unknown"}

def set_app_volume(app_name, volume):
    """Set volume concept - logs the intent. Actual per-app volume needs COM/pycaw."""
    volume = max(0, min(100, volume))
    return {
        "action": "set_volume",
        "app": app_name,
        "volume": volume,
        "method": "logged_intent",
        "note": "Per-app volume via nircmd: nircmd setappvolume <app>.exe {:.2f}".format(volume / 100.0),
        "nircmd_command": f"nircmd setappvolume {app_name}.exe {volume / 100.0:.2f}",
        "ts": datetime.now().isoformat()
    }

def do_apps():
    db = init_db()
    apps = get_audio_apps()
    audio_apps = [a for a in apps if a.get("likely_audio")]
    result = {
        "action": "list_apps",
        "total_windowed": len(apps),
        "audio_likely": len(audio_apps),
        "apps": apps,
        "master_volume": get_master_volume(),
        "ts": datetime.now().isoformat()
    }
    log_event(db, "list_apps", details=f"{len(apps)} apps, {len(audio_apps)} audio")
    db.close()
    return result

def do_profiles():
    db = init_db()
    rows = db.execute("SELECT name, master_volume, app_volumes, updated_at FROM volume_profiles ORDER BY name").fetchall()
    profiles = []
    for r in rows:
        profiles.append({
            "name": r[0],
            "master_volume": r[1],
            "app_volumes": json.loads(r[2]) if r[2] else {},
            "updated_at": r[3]
        })
    result = {
        "action": "list_profiles",
        "profiles": profiles,
        "total": len(profiles),
        "ts": datetime.now().isoformat()
    }
    log_event(db, "list_profiles")
    db.close()
    return result

def do_schedule():
    db = init_db()
    rows = db.execute("SELECT id, profile, hour_start, hour_end, days, active FROM volume_schedule ORDER BY hour_start").fetchall()
    schedules = []
    for r in rows:
        schedules.append({
            "id": r[0], "profile": r[1], "hour_start": r[2],
            "hour_end": r[3], "days": r[4], "active": bool(r[5])
        })
    # Check current hour for active profile
    current_hour = datetime.now().hour
    active_profile = None
    for s in schedules:
        if s["active"] and s["hour_start"] <= current_hour < s["hour_end"]:
            active_profile = s["profile"]
            break
    result = {
        "action": "schedule",
        "schedules": schedules,
        "current_hour": current_hour,
        "active_profile": active_profile,
        "ts": datetime.now().isoformat()
    }
    log_event(db, "check_schedule", profile=active_profile)
    db.close()
    return result

def do_once():
    db = init_db()
    apps = get_audio_apps()
    audio_apps = [a for a in apps if a.get("likely_audio")]
    profiles = db.execute("SELECT COUNT(*) FROM volume_profiles").fetchone()[0]
    events = db.execute("SELECT COUNT(*) FROM volume_events").fetchone()[0]
    recent = db.execute("SELECT ts, action, app, volume FROM volume_events ORDER BY id DESC LIMIT 5").fetchall()
    result = {
        "status": "ok",
        "audio_apps": len(audio_apps),
        "total_windowed_apps": len(apps),
        "profiles_count": profiles,
        "total_events": events,
        "recent_events": [{"ts": r[0], "action": r[1], "app": r[2], "volume": r[3]} for r in recent],
        "ts": datetime.now().isoformat()
    }
    log_event(db, "once_check")
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="Windows Sound Mixer — COWORK #220")
    parser.add_argument("--apps", action="store_true", help="List audio apps")
    parser.add_argument("--set", nargs=2, metavar=("APP", "VOLUME"), help="Set app volume")
    parser.add_argument("--profiles", action="store_true", help="List volume profiles")
    parser.add_argument("--schedule", action="store_true", help="Show volume schedule")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.apps:
        print(json.dumps(do_apps(), ensure_ascii=False, indent=2))
    elif args.set:
        db = init_db()
        result = set_app_volume(args.set[0], int(args.set[1]))
        log_event(db, "set_volume", app=args.set[0], volume=int(args.set[1]))
        db.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.profiles:
        print(json.dumps(do_profiles(), ensure_ascii=False, indent=2))
    elif args.schedule:
        print(json.dumps(do_schedule(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
