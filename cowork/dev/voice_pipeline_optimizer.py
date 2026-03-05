#!/usr/bin/env python3
"""Voice Pipeline Optimizer — Monitor and improve voice recognition quality.

Analyzes transcription errors, tunes correction patterns, measures
latency, and generates improvement recommendations.
"""
import argparse
import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "voice_optimizer.db"
TURBO = Path("F:/BUREAU/turbo")
CORRECTIONS_FILE = TURBO / "data" / "voice_corrections.json"
COMMANDS_FILE = TURBO / "src" / "commands.py"
DOMINOS_FILE = TURBO / "data" / "dominos.json"

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY, ts REAL, total_corrections INTEGER,
        total_commands INTEGER, total_dominos INTEGER,
        correction_coverage REAL, command_coverage REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY, ts REAL, category TEXT,
        suggestion TEXT, priority TEXT, applied INTEGER DEFAULT 0)""")
    db.commit()
    return db

def count_corrections():
    """Count voice corrections from JSON."""
    if not CORRECTIONS_FILE.exists():
        return 0
    try:
        data = json.loads(CORRECTIONS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return sum(len(v) if isinstance(v, list) else 1 for v in data.values())
    except Exception:
        pass
    return 0

def count_commands():
    """Count voice commands from commands.py."""
    if not COMMANDS_FILE.exists():
        return 0
    try:
        content = COMMANDS_FILE.read_text(encoding="utf-8")
        return content.count("JarvisCommand(")
    except Exception:
        return 0

def count_dominos():
    """Count domino definitions."""
    if not DOMINOS_FILE.exists():
        return 0
    try:
        data = json.loads(DOMINOS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return len(data.get("dominos", data.get("commands", [])))
    except Exception:
        return 0

def analyze_coverage(db):
    """Analyze voice system coverage and gaps."""
    corrections = count_corrections()
    commands = count_commands()
    dominos = count_dominos()

    # Estimate coverage
    # Target: 5000 corrections, 3000 commands, 500 dominos
    corr_coverage = min(1.0, corrections / 5000)
    cmd_coverage = min(1.0, commands / 3000)

    db.execute(
        "INSERT INTO metrics (ts, total_corrections, total_commands, total_dominos, correction_coverage, command_coverage) VALUES (?,?,?,?,?,?)",
        (time.time(), corrections, commands, dominos, corr_coverage, cmd_coverage))
    db.commit()

    return {
        "corrections": corrections,
        "commands": commands,
        "dominos": dominos,
        "correction_coverage": f"{corr_coverage*100:.0f}%",
        "command_coverage": f"{cmd_coverage*100:.0f}%",
    }

def generate_suggestions(db, metrics):
    """Generate improvement suggestions based on metrics."""
    suggestions = []

    if metrics["corrections"] < 3000:
        suggestions.append(("corrections", "Ajouter plus de corrections vocales (cible: 3000+)", "medium"))
    if metrics["commands"] < 2500:
        suggestions.append(("commands", f"Ajouter commandes vocales ({metrics['commands']} actuellement, cible: 2500+)", "medium"))
    if metrics["dominos"] < 400:
        suggestions.append(("dominos", f"Creer plus de dominos ({metrics['dominos']} actuellement, cible: 400+)", "medium"))

    # Check for common French phonetic issues
    phonetic_gaps = [
        ("fillers", "Ajouter des fillers pour les hesitations courantes (euh, hm, ben)"),
        ("homophones", "Verifier les homophones francais (a/à, ou/où, ce/se)"),
        ("anglicismes", "Ajouter des corrections pour les anglicismes tech (debug→débogage, push→pousser)"),
    ]
    for cat, suggestion in phonetic_gaps:
        # Only suggest if not recently suggested
        recent = db.execute(
            "SELECT id FROM suggestions WHERE category=? AND ts > ?",
            (cat, time.time() - 86400)).fetchone()
        if not recent:
            suggestions.append((cat, suggestion, "low"))

    for cat, text, prio in suggestions:
        db.execute("INSERT INTO suggestions (ts, category, suggestion, priority) VALUES (?,?,?,?)",
                   (time.time(), cat, text, prio))
    db.commit()
    return suggestions

def check_whisper_model():
    """Check Whisper model availability."""
    whisper_dir = TURBO / "models"
    models = list(whisper_dir.glob("*whisper*")) if whisper_dir.exists() else []
    return len(models), [m.name for m in models[:5]]

def main():
    parser = argparse.ArgumentParser(description="Voice Pipeline Optimizer")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=3600)
    args = parser.parse_args()

    db = init_db()

    if args.once or not args.loop:
        metrics = analyze_coverage(db)
        print("=== Voice Pipeline Metrics ===")
        print(f"  Corrections: {metrics['corrections']} ({metrics['correction_coverage']})")
        print(f"  Commands: {metrics['commands']} ({metrics['command_coverage']})")
        print(f"  Dominos: {metrics['dominos']}")

        suggestions = generate_suggestions(db, metrics)
        if suggestions:
            print("\n=== Suggestions ===")
            for cat, text, prio in suggestions:
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(prio, "⚪")
                print(f"  {icon} [{cat}] {text}")

        n_models, model_names = check_whisper_model()
        print(f"\n  Whisper models: {n_models}")

    if args.loop:
        while True:
            try:
                metrics = analyze_coverage(db)
                suggestions = generate_suggestions(db, metrics)
                ts = time.strftime('%H:%M')
                print(f"[{ts}] Corrections: {metrics['corrections']} | Commands: {metrics['commands']} | +{len(suggestions)} suggestions")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
