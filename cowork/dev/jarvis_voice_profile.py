#!/usr/bin/env python3
"""jarvis_voice_profile.py — TTS voice profile manager for JARVIS.
COWORK #232 — Batch 105: JARVIS Voice 2.0

Usage:
    python dev/jarvis_voice_profile.py --create
    python dev/jarvis_voice_profile.py --switch rapide
    python dev/jarvis_voice_profile.py --list
    python dev/jarvis_voice_profile.py --adapt
    python dev/jarvis_voice_profile.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "voice_profile.db"

VOICE_PROFILES = {
    "default": {
        "voice": "fr-FR-DeniseNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "description": "Voix standard JARVIS — Denise, tempo normal",
        "hours": (0, 24)
    },
    "rapide": {
        "voice": "fr-FR-DeniseNeural",
        "rate": "+30%",
        "pitch": "+0Hz",
        "volume": "+5%",
        "description": "Debit rapide pour reponses courtes",
        "hours": (9, 18)
    },
    "anglais": {
        "voice": "en-US-JennyNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "description": "English voice for international context",
        "hours": (0, 24)
    },
    "whisper": {
        "voice": "fr-FR-DeniseNeural",
        "rate": "-15%",
        "pitch": "-2Hz",
        "volume": "-20%",
        "description": "Voix douce et lente pour le soir/nuit",
        "hours": (22, 7)
    },
    "formel": {
        "voice": "fr-FR-HenriNeural",
        "rate": "-5%",
        "pitch": "-1Hz",
        "volume": "+0%",
        "description": "Voix masculine formelle pour presentations",
        "hours": (8, 20)
    },
    "energique": {
        "voice": "fr-FR-DeniseNeural",
        "rate": "+15%",
        "pitch": "+3Hz",
        "volume": "+10%",
        "description": "Voix dynamique et enthusiaste",
        "hours": (7, 22)
    }
}

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS active_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        profile TEXT NOT NULL,
        reason TEXT,
        auto_switched INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS custom_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        voice TEXT NOT NULL,
        rate TEXT DEFAULT '+0%',
        pitch TEXT DEFAULT '+0Hz',
        volume TEXT DEFAULT '+0%',
        description TEXT,
        created_at TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS profile_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile TEXT NOT NULL,
        used_at TEXT NOT NULL,
        duration_seconds INTEGER DEFAULT 0,
        utterances INTEGER DEFAULT 0
    )""")
    db.commit()
    return db

def get_current_profile(db):
    row = db.execute("SELECT profile, ts, reason FROM active_profile ORDER BY id DESC LIMIT 1").fetchone()
    return {"profile": row[0], "since": row[1], "reason": row[2]} if row else {"profile": "default", "since": None, "reason": "initial"}

def do_create():
    """Show how to create a custom profile."""
    db = init_db()
    existing = db.execute("SELECT name, voice, description FROM custom_profiles ORDER BY name").fetchall()
    result = {
        "action": "create_info",
        "builtin_profiles": list(VOICE_PROFILES.keys()),
        "custom_profiles": [{"name": r[0], "voice": r[1], "description": r[2]} for r in existing],
        "available_voices": [
            "fr-FR-DeniseNeural", "fr-FR-HenriNeural",
            "en-US-JennyNeural", "en-US-GuyNeural",
            "es-ES-ElviraNeural", "de-DE-KatjaNeural"
        ],
        "template": {
            "name": "custom_name",
            "voice": "fr-FR-DeniseNeural",
            "rate": "+0%",
            "pitch": "+0Hz",
            "volume": "+0%",
            "description": "Description of the profile"
        },
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_switch(profile_name):
    db = init_db()
    profile_name = profile_name.lower()

    if profile_name not in VOICE_PROFILES:
        # Check custom profiles
        custom = db.execute("SELECT name FROM custom_profiles WHERE name=?", (profile_name,)).fetchone()
        if not custom:
            db.close()
            return {
                "error": f"Profile '{profile_name}' not found",
                "available": list(VOICE_PROFILES.keys()),
                "ts": datetime.now().isoformat()
            }

    db.execute("INSERT INTO active_profile (ts, profile, reason, auto_switched) VALUES (?,?,?,?)",
               (datetime.now().isoformat(), profile_name, "manual_switch", 0))
    db.commit()

    profile_info = VOICE_PROFILES.get(profile_name, {})
    result = {
        "action": "switch",
        "profile": profile_name,
        "voice": profile_info.get("voice", "custom"),
        "rate": profile_info.get("rate", "+0%"),
        "pitch": profile_info.get("pitch", "+0Hz"),
        "volume": profile_info.get("volume", "+0%"),
        "description": profile_info.get("description", "Custom profile"),
        "success": True,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_list():
    db = init_db()
    current = get_current_profile(db)
    profiles = []
    for name, info in VOICE_PROFILES.items():
        profiles.append({
            "name": name,
            "voice": info["voice"],
            "rate": info["rate"],
            "pitch": info["pitch"],
            "volume": info["volume"],
            "description": info["description"],
            "active_hours": f"{info['hours'][0]}h-{info['hours'][1]}h",
            "is_active": name == current["profile"]
        })

    custom = db.execute("SELECT name, voice, rate, pitch, volume, description FROM custom_profiles").fetchall()
    for r in custom:
        profiles.append({
            "name": r[0], "voice": r[1], "rate": r[2], "pitch": r[3],
            "volume": r[4], "description": r[5], "custom": True,
            "is_active": r[0] == current["profile"]
        })

    result = {
        "action": "list",
        "current_profile": current["profile"],
        "profiles": profiles,
        "total": len(profiles),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_adapt():
    """Auto-adapt profile based on current hour."""
    db = init_db()
    hour = datetime.now().hour
    current = get_current_profile(db)

    best_profile = "default"
    if 22 <= hour or hour < 7:
        best_profile = "whisper"
    elif 9 <= hour < 12:
        best_profile = "rapide"
    elif 12 <= hour < 14:
        best_profile = "default"
    elif 14 <= hour < 18:
        best_profile = "rapide"
    elif 18 <= hour < 22:
        best_profile = "default"

    changed = best_profile != current["profile"]
    if changed:
        db.execute("INSERT INTO active_profile (ts, profile, reason, auto_switched) VALUES (?,?,?,?)",
                   (datetime.now().isoformat(), best_profile, f"auto_adapt_hour_{hour}", 1))
        db.commit()

    result = {
        "action": "adapt",
        "current_hour": hour,
        "previous_profile": current["profile"],
        "recommended_profile": best_profile,
        "changed": changed,
        "description": VOICE_PROFILES.get(best_profile, {}).get("description", ""),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    current = get_current_profile(db)
    total_switches = db.execute("SELECT COUNT(*) FROM active_profile").fetchone()[0]
    auto_switches = db.execute("SELECT COUNT(*) FROM active_profile WHERE auto_switched=1").fetchone()[0]
    result = {
        "status": "ok",
        "current_profile": current["profile"],
        "since": current.get("since"),
        "total_switches": total_switches,
        "auto_switches": auto_switches,
        "builtin_profiles": list(VOICE_PROFILES.keys()),
        "current_hour": datetime.now().hour,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="JARVIS Voice Profile — COWORK #232")
    parser.add_argument("--create", action="store_true", help="Show profile creation info")
    parser.add_argument("--switch", type=str, metavar="PROFILE", help="Switch to profile")
    parser.add_argument("--list", action="store_true", help="List all profiles")
    parser.add_argument("--adapt", action="store_true", help="Auto-adapt by hour")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.create:
        print(json.dumps(do_create(), ensure_ascii=False, indent=2))
    elif args.switch:
        print(json.dumps(do_switch(args.switch), ensure_ascii=False, indent=2))
    elif args.list:
        print(json.dumps(do_list(), ensure_ascii=False, indent=2))
    elif args.adapt:
        print(json.dumps(do_adapt(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
