#!/usr/bin/env python3
"""JARVIS Skill Generator — Auto-generate new voice commands and dominos.

Analyzes existing commands, identifies gaps, and generates new
voice commands, corrections, and domino pipelines automatically.
"""
import argparse
import json
import sqlite3
import time
import re
from pathlib import Path

DB_PATH = Path(__file__).parent / "skill_gen.db"
TURBO = Path("F:/BUREAU/turbo")

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS generated (
        id INTEGER PRIMARY KEY, ts REAL, type TEXT, name TEXT,
        content TEXT, approved INTEGER DEFAULT 0, applied INTEGER DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS gaps (
        id INTEGER PRIMARY KEY, ts REAL, category TEXT, description TEXT,
        priority TEXT, addressed INTEGER DEFAULT 0)""")
    db.commit()
    return db

def analyze_commands():
    """Analyze existing commands for patterns and gaps."""
    cmd_file = TURBO / "src" / "commands.py"
    if not cmd_file.exists():
        return [], []

    content = cmd_file.read_text(encoding="utf-8", errors="replace")
    # Extract categories
    categories = set()
    commands_by_cat = {}
    for m in re.finditer(r'JarvisCommand\("(\w+)",\s*"(\w+)"', content):
        name, cat = m.groups()
        categories.add(cat)
        commands_by_cat.setdefault(cat, []).append(name)

    return categories, commands_by_cat

def analyze_corrections():
    """Analyze voice corrections for coverage."""
    corr_file = TURBO / "data" / "voice_corrections.json"
    if not corr_file.exists():
        return 0, set()
    try:
        data = json.loads(corr_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            words = set()
            for item in data:
                if isinstance(item, dict):
                    words.add(item.get("from", "").lower())
            return len(data), words
    except Exception:
        pass
    return 0, set()

def identify_gaps(db, categories, commands_by_cat):
    """Identify missing command categories and gaps."""
    gaps = []

    # Expected categories that should exist
    expected = {
        "system": ["shutdown", "restart", "sleep", "lock", "logout"],
        "network": ["wifi_status", "ip_address", "ping_test", "bandwidth"],
        "audio": ["volume_up", "volume_down", "mute", "unmute"],
        "display": ["brightness_up", "brightness_down", "night_mode"],
        "files": ["open_folder", "search_file", "recent_files"],
        "browser": ["open_chrome", "open_firefox", "search_web"],
        "productivity": ["timer_set", "alarm_set", "note_create"],
        "automation": ["run_script", "schedule_task", "backup_now"],
    }

    for cat, expected_cmds in expected.items():
        existing = set(commands_by_cat.get(cat, []))
        for cmd in expected_cmds:
            if not any(cmd in e for e in existing):
                gaps.append((cat, f"Commande manquante: {cmd}", "medium"))

    # Store new gaps
    for cat, desc, prio in gaps:
        existing = db.execute(
            "SELECT id FROM gaps WHERE category=? AND description=?", (cat, desc)
        ).fetchone()
        if not existing:
            db.execute("INSERT INTO gaps (ts, category, description, priority) VALUES (?,?,?,?)",
                       (time.time(), cat, desc, prio))
    db.commit()
    return gaps

def generate_command(name, category, description, triggers):
    """Generate a JarvisCommand definition."""
    trigger_str = ", ".join(f'"{t}"' for t in triggers)
    return f'    JarvisCommand("{name}", "{category}", "{description}", [\n        {trigger_str},\n    ], "tool", "{name}"),'

def generate_corrections(word_from, word_to):
    """Generate a voice correction entry."""
    return {"from": word_from, "to": word_to, "confidence": 0.9, "generated": True}

def auto_generate(db):
    """Auto-generate new commands based on gaps."""
    generated = 0
    gaps = db.execute(
        "SELECT id, category, description FROM gaps WHERE addressed=0 ORDER BY priority DESC LIMIT 10"
    ).fetchall()

    templates = {
        "timer_set": ("productivity", "Creer un minuteur", ["minuteur", "timer", "chrono", "compte a rebours"]),
        "brightness_up": ("display", "Augmenter la luminosite", ["plus lumineux", "brightness up", "augmenter luminosite"]),
        "brightness_down": ("display", "Baisser la luminosite", ["moins lumineux", "brightness down", "baisser luminosite"]),
        "wifi_status": ("network", "Statut connexion WiFi", ["wifi status", "statut wifi", "connexion internet"]),
        "search_file": ("files", "Rechercher un fichier", ["chercher fichier", "search file", "trouver fichier"]),
        "backup_now": ("automation", "Lancer backup maintenant", ["backup maintenant", "sauvegarder maintenant", "backup now"]),
        "note_create": ("productivity", "Creer une note rapide", ["nouvelle note", "note rapide", "prendre note"]),
    }

    for gap_id, cat, desc in gaps:
        for cmd_name, (cmd_cat, cmd_desc, triggers) in templates.items():
            if cmd_name in desc and cmd_cat == cat:
                code = generate_command(cmd_name, cmd_cat, cmd_desc, triggers)
                db.execute(
                    "INSERT INTO generated (ts, type, name, content) VALUES (?,?,?,?)",
                    (time.time(), "command", cmd_name, code))
                db.execute("UPDATE gaps SET addressed=1 WHERE id=?", (gap_id,))
                generated += 1
                break
    db.commit()
    return generated

def main():
    parser = argparse.ArgumentParser(description="JARVIS Skill Generator")
    parser.add_argument("--analyze", action="store_true", help="Analyze existing skills")
    parser.add_argument("--gaps", action="store_true", help="Show identified gaps")
    parser.add_argument("--generate", action="store_true", help="Auto-generate new skills")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=7200)
    args = parser.parse_args()

    db = init_db()

    if args.analyze or args.once:
        categories, cmds = analyze_commands()
        corr_count, corr_words = analyze_corrections()
        print(f"=== Skill Analysis ===")
        print(f"  Categories: {len(categories)}")
        for cat in sorted(categories):
            print(f"    {cat}: {len(cmds.get(cat, []))} commands")
        print(f"  Corrections: {corr_count}")

        gaps = identify_gaps(db, categories, cmds)
        print(f"  Gaps found: {len(gaps)}")

    if args.gaps:
        all_gaps = db.execute(
            "SELECT category, description, priority, addressed FROM gaps ORDER BY priority DESC, category"
        ).fetchall()
        print(f"=== Gaps ({len(all_gaps)}) ===")
        for cat, desc, prio, done in all_gaps:
            icon = "✅" if done else {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(prio, "⚪")
            print(f"  {icon} [{cat}] {desc}")

    if args.generate or args.once:
        n = auto_generate(db)
        print(f"Generated {n} new skills")
        # Show generated
        recent = db.execute(
            "SELECT name, type, content FROM generated WHERE ts > ? ORDER BY ts DESC",
            (time.time() - 3600,)).fetchall()
        for name, stype, content in recent:
            print(f"  + [{stype}] {name}")

    if args.loop:
        while True:
            try:
                categories, cmds = analyze_commands()
                identify_gaps(db, categories, cmds)
                n = auto_generate(db)
                ts = time.strftime('%H:%M')
                print(f"[{ts}] Analyzed {len(categories)} cats, generated {n} skills")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
