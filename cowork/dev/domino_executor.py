#!/usr/bin/env python3
"""domino_executor.py — Lecteur et executeur de pipelines domino vocaux.

Lit les chaines de commandes vocales (dominos) depuis la config JARVIS,
les interprete et les execute en cascade.
Un domino = une sequence de commandes declenchees par une seule phrase.

Usage:
    python dev/domino_executor.py --list                     # Lister les dominos
    python dev/domino_executor.py --run "routine du matin"   # Executer un domino
    python dev/domino_executor.py --create "nom" "cmd1;cmd2" # Creer un domino
    python dev/domino_executor.py --stats                    # Stats d'utilisation
    python dev/domino_executor.py --test                     # Tester tous les dominos
    python dev/domino_executor.py --suggest                  # Suggerer des dominos
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "dominos.db"
DOMINOS_FILE = DEV / "data" / "dominos.json"

# ---------------------------------------------------------------------------
# Default dominos — chaines de commandes predefinies
# ---------------------------------------------------------------------------
DEFAULT_DOMINOS = {
    "routine du matin": {
        "trigger": ["routine du matin", "bonjour jarvis", "morning", "reveille toi"],
        "description": "Routine complete du matin",
        "steps": [
            {"cmd": "python dev/email_reader.py --unread", "label": "Lire les emails"},
            {"cmd": "python dev/telegram_commander.py --cmd status", "label": "Status systeme"},
            {"cmd": "nvidia-smi --query-gpu=name,temperature.gpu,memory.used --format=csv,noheader", "label": "GPU status"},
            {"cmd": "python dev/interaction_predictor.py --predict", "label": "Predictions du jour"},
        ],
    },
    "scan complet": {
        "trigger": ["scan complet", "diagnostic complet", "check everything"],
        "description": "Scan complet du systeme et cluster",
        "steps": [
            {"cmd": "python dev/telegram_commander.py --cmd health", "label": "Health check"},
            {"cmd": "python dev/api_monitor.py --once", "label": "API monitor"},
            {"cmd": "nvidia-smi --query-gpu=name,temperature.gpu,memory.used --format=csv,noheader", "label": "GPU check"},
            {"cmd": "python -c \"import shutil;u=shutil.disk_usage('C:/');f=shutil.disk_usage('F:/');print(f'C: {u.free//1024**3}GB free | F: {f.free//1024**3}GB free')\"", "label": "Disk check"},
        ],
    },
    "trading pipeline": {
        "trigger": ["scan trading", "pipeline trading", "analyse marche"],
        "description": "Pipeline complet d'analyse trading",
        "steps": [
            {"cmd": "python dev/telegram_commander.py --cmd trading", "label": "Signaux trading"},
            {"cmd": "python dev/interaction_predictor.py --log \"trading scan\"", "label": "Log interaction"},
        ],
    },
    "range tout": {
        "trigger": ["range tout", "nettoie tout", "clean everything", "menage"],
        "description": "Nettoyage complet bureau + telechargements",
        "steps": [
            {"cmd": "python dev/desktop_organizer.py --organize", "label": "Ranger le bureau"},
            {"cmd": "python dev/desktop_organizer.py --downloads", "label": "Ranger telechargements"},
        ],
    },
    "dev status": {
        "trigger": ["status dev", "ou en est le dev", "avancement", "dev progress"],
        "description": "Status du developpement continu",
        "steps": [
            {"cmd": "python dev/continuous_coder.py --status", "label": "Status dev continu"},
            {"cmd": "python dev/self_feeding_engine.py --metrics", "label": "Metriques auto-feed"},
        ],
    },
    "rapport du soir": {
        "trigger": ["rapport du soir", "bilan", "recap", "resume journee"],
        "description": "Rapport complet de fin de journee",
        "steps": [
            {"cmd": "python dev/telegram_commander.py --cmd report", "label": "Rapport general"},
            {"cmd": "python dev/interaction_predictor.py --stats", "label": "Stats interactions"},
            {"cmd": "python dev/continuous_coder.py --history", "label": "Historique dev"},
        ],
    },
    "ouvre navigateur": {
        "trigger": ["ouvre le navigateur", "lance chrome", "internet"],
        "description": "Lancer le navigateur avec CDP",
        "steps": [
            {"cmd": "python dev/browser_pilot.py --start", "label": "Lancer Chrome CDP"},
            {"cmd": "python dev/window_manager.py --maximize Chrome", "label": "Maximiser"},
        ],
    },
    "mode travail": {
        "trigger": ["mode travail", "focus mode", "concentration"],
        "description": "Configuration mode travail",
        "steps": [
            {"cmd": "python dev/smart_launcher.py --launch vscode", "label": "Ouvrir VS Code"},
            {"cmd": "python dev/smart_launcher.py --launch terminal", "label": "Ouvrir terminal"},
            {"cmd": "python dev/browser_pilot.py --start", "label": "Lancer navigateur"},
            {"cmd": "python dev/window_manager.py --tile", "label": "Carreler fenetres"},
        ],
    },
    "shutdown propre": {
        "trigger": ["bonne nuit", "shutdown", "arrete tout", "ferme tout"],
        "description": "Arret propre des services",
        "steps": [
            {"cmd": "python dev/telegram_commander.py --cmd report", "label": "Rapport final"},
            {"cmd": "python dev/interaction_predictor.py --log \"shutdown\"", "label": "Log arret"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, domino_name TEXT, steps_total INTEGER,
        steps_ok INTEGER, steps_failed INTEGER,
        duration_s REAL, details TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS custom_dominos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, name TEXT UNIQUE, trigger_words TEXT,
        description TEXT, steps TEXT)""")
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Domino management
# ---------------------------------------------------------------------------
def load_dominos(db) -> dict:
    """Charge les dominos (defaut + custom)."""
    dominos = dict(DEFAULT_DOMINOS)
    # Load custom from DB
    rows = db.execute("SELECT name, trigger_words, description, steps FROM custom_dominos").fetchall()
    for name, triggers, desc, steps in rows:
        dominos[name] = {
            "trigger": json.loads(triggers),
            "description": desc,
            "steps": json.loads(steps),
            "custom": True,
        }
    return dominos

def find_domino(text: str, dominos: dict):
    """Trouve un domino par son trigger."""
    text_lower = text.lower().strip()
    # Exact name match
    if text_lower in dominos:
        return text_lower, dominos[text_lower]
    # Trigger match
    for name, d in dominos.items():
        for trigger in d.get("trigger", []):
            if trigger.lower() in text_lower or text_lower in trigger.lower():
                return name, d
    return None, None

def execute_domino(name: str, domino: dict, db) -> dict:
    """Execute un domino (toutes les etapes en cascade)."""
    start = time.time()
    steps_ok = 0
    steps_failed = 0
    details = []

    for i, step in enumerate(domino["steps"]):
        step_start = time.time()
        cmd = step["cmd"]
        label = step.get("label", f"Step {i+1}")

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=60,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                cwd=str(DEV.parent)
            )
            ok = result.returncode == 0
            output = result.stdout.strip()[:500] if result.stdout else ""
            error = result.stderr.strip()[:200] if result.stderr else ""

            if ok:
                steps_ok += 1
            else:
                steps_failed += 1

            details.append({
                "step": i + 1,
                "label": label,
                "ok": ok,
                "duration_s": round(time.time() - step_start, 1),
                "output_preview": output[:200],
                "error": error[:100] if error else None,
            })
        except subprocess.TimeoutExpired:
            steps_failed += 1
            details.append({"step": i + 1, "label": label, "ok": False, "error": "timeout"})
        except Exception as e:
            steps_failed += 1
            details.append({"step": i + 1, "label": label, "ok": False, "error": str(e)[:100]})

    duration = time.time() - start

    # Record execution
    db.execute(
        "INSERT INTO executions (ts, domino_name, steps_total, steps_ok, steps_failed, duration_s, details) VALUES (?,?,?,?,?,?,?)",
        (time.time(), name, len(domino["steps"]), steps_ok, steps_failed, round(duration, 1), json.dumps(details))
    )
    db.commit()

    return {
        "domino": name,
        "description": domino.get("description", ""),
        "steps_total": len(domino["steps"]),
        "steps_ok": steps_ok,
        "steps_failed": steps_failed,
        "duration_s": round(duration, 1),
        "success": steps_failed == 0,
        "details": details,
    }

def create_domino(db, name: str, commands_str: str, description: str = "") -> dict:
    """Cree un domino custom."""
    steps = []
    for cmd in commands_str.split(";"):
        cmd = cmd.strip()
        if cmd:
            steps.append({"cmd": cmd, "label": cmd[:50]})

    triggers = [name.lower()]
    db.execute(
        "INSERT OR REPLACE INTO custom_dominos (ts, name, trigger_words, description, steps) VALUES (?,?,?,?,?)",
        (time.time(), name, json.dumps(triggers), description or name, json.dumps(steps))
    )
    db.commit()
    return {"created": name, "steps": len(steps), "triggers": triggers}

def get_stats(db) -> dict:
    """Stats d'utilisation des dominos."""
    total = db.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
    by_name = db.execute("SELECT domino_name, COUNT(*), SUM(steps_ok), SUM(steps_failed) FROM executions GROUP BY domino_name ORDER BY 2 DESC").fetchall()
    recent = db.execute("SELECT domino_name, steps_ok, steps_failed, duration_s, ts FROM executions ORDER BY ts DESC LIMIT 10").fetchall()

    return {
        "total_executions": total,
        "by_domino": {n: {"runs": c, "ok": o, "failed": f} for n, c, o, f in by_name},
        "recent": [{"name": n, "ok": o, "failed": f, "duration": d,
                     "when": datetime.fromtimestamp(t).strftime("%H:%M")} for n, o, f, d, t in recent],
    }

def suggest_dominos(db) -> dict:
    """Suggere de nouveaux dominos basés sur les patterns."""
    # Check interaction_predictor sequences
    pred_db = DEV / "data" / "predictor.db"
    suggestions = []
    if pred_db.exists():
        pdb = sqlite3.connect(str(pred_db))
        seqs = pdb.execute("SELECT command_a, command_b, count FROM sequences WHERE count >= 3 ORDER BY count DESC LIMIT 5").fetchall()
        for a, b, cnt in seqs:
            suggestions.append({
                "type": "sequence_pattern",
                "from": a, "to": b,
                "frequency": cnt,
                "suggestion": f"Creer un domino '{a} puis {b}' — detecte {cnt} fois",
            })
        pdb.close()
    return {"suggestions": suggestions}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Domino Executor — Pipelines vocaux en cascade")
    parser.add_argument("--list", action="store_true", help="Lister les dominos disponibles")
    parser.add_argument("--run", type=str, help="Executer un domino par nom ou trigger")
    parser.add_argument("--create", nargs=2, metavar=("NAME", "COMMANDS"), help="Creer un domino (cmds separees par ;)")
    parser.add_argument("--stats", action="store_true", help="Statistiques")
    parser.add_argument("--test", action="store_true", help="Tester (dry-run)")
    parser.add_argument("--suggest", action="store_true", help="Suggerer des dominos")
    parser.add_argument("--describe", type=str, help="Decrire un domino")
    args = parser.parse_args()

    db = init_db()
    dominos = load_dominos(db)

    if args.list:
        output = []
        for name, d in dominos.items():
            output.append({
                "name": name,
                "description": d.get("description", ""),
                "steps": len(d["steps"]),
                "triggers": d.get("trigger", []),
                "custom": d.get("custom", False),
            })
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif args.run:
        name, domino = find_domino(args.run, dominos)
        if not domino:
            print(json.dumps({"error": f"Domino '{args.run}' non trouve", "available": list(dominos.keys())}, ensure_ascii=False))
            sys.exit(1)
        result = execute_domino(name, domino, db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.create:
        result = create_domino(db, args.create[0], args.create[1])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.stats:
        print(json.dumps(get_stats(db), indent=2, ensure_ascii=False))
    elif args.suggest:
        print(json.dumps(suggest_dominos(db), indent=2, ensure_ascii=False))
    elif args.describe:
        name, domino = find_domino(args.describe, dominos)
        if domino:
            print(json.dumps({"name": name, **domino}, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"error": "Domino non trouve"}, ensure_ascii=False))
    elif args.test:
        results = []
        for name, d in dominos.items():
            results.append({
                "name": name,
                "steps": len(d["steps"]),
                "triggers": len(d.get("trigger", [])),
                "valid": all("cmd" in s for s in d["steps"]),
            })
        valid = sum(1 for r in results if r["valid"])
        print(json.dumps({"total": len(results), "valid": valid, "dominos": results}, indent=2, ensure_ascii=False))
    else:
        # Default: list with summary
        print(json.dumps({
            "total_dominos": len(dominos),
            "dominos": [{"name": n, "steps": len(d["steps"]), "triggers": d.get("trigger", [])[0] if d.get("trigger") else n}
                        for n, d in dominos.items()],
        }, indent=2, ensure_ascii=False))

    db.close()

if __name__ == "__main__":
    main()
