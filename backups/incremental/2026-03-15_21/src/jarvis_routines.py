"""jarvis_routines.py — Routines automatiques JARVIS OS.

Sequences de commandes declenchees par heure ou evenement:
- Matin: briefing, meteo, GPU check
- Soir: backup, rapport vocal, profil veille
- Bureau: profil dev, ouvre les outils
- Custom: routines definies par l'utilisateur

Usage:
    from src.jarvis_routines import routine_manager
    routine_manager.run("matin")
"""
from __future__ import annotations

import json
import logging
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("jarvis.routines")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jarvis.db"

# Routines prédéfinies
BUILT_IN_ROUTINES = {
    "matin": {
        "description": "Routine du matin — briefing complet",
        "commands": [
            "jarvis rapport",
            "temperatures gpu",
            "sante du systeme",
            "quelle heure",
        ],
        "speak": "Bonjour Turbo. Voici le briefing du matin.",
    },
    "soir": {
        "description": "Routine du soir — backup et rapport",
        "commands": [
            "jarvis rapport",
            "rapport vocal",
        ],
        "speak": "Bonsoir. Voici le rapport de fin de journée.",
        "post_action": "backup",
    },
    "bureau": {
        "description": "Arrivée au bureau — profil dev + outils",
        "commands": [
            "mode dev",
            "active les widgets",
            "ouvre le dashboard",
        ],
        "speak": "Mode bureau activé. Bon travail.",
    },
    "depart": {
        "description": "Départ — veille + backup",
        "commands": [
            "mode veille",
            "desactive les widgets",
        ],
        "speak": "Mode veille activé. A demain.",
        "post_action": "backup",
    },
    "gaming": {
        "description": "Session gaming — libérer les GPUs",
        "commands": [
            "mode gaming",
        ],
        "speak": "Mode gaming activé. Bonnes parties.",
    },
    "reset": {
        "description": "Reset — retour à la normale",
        "commands": [
            "mode normal",
            "active les widgets",
        ],
        "speak": "Système remis à la normale.",
    },
}


def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))
        return r.stdout.strip()
    except Exception:
        return ""


def _init_table():
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.execute("""CREATE TABLE IF NOT EXISTS jarvis_routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            commands TEXT NOT NULL,
            speak TEXT DEFAULT '',
            usage_count INTEGER DEFAULT 0,
            created_at REAL DEFAULT 0,
            last_used REAL DEFAULT 0
        )""")
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass


def run_routine(name: str) -> str:
    """Execute une routine par son nom."""
    _init_table()
    name = name.lower().strip()

    # Chercher dans les routines built-in
    routine = BUILT_IN_ROUTINES.get(name)

    # Sinon chercher dans la DB
    if not routine:
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=5)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM jarvis_routines WHERE name = ?", (name,)).fetchone()
            conn.close()
            if row:
                routine = {
                    "description": row["description"],
                    "commands": json.loads(row["commands"]),
                    "speak": row["speak"],
                }
        except sqlite3.Error:
            pass

    if not routine:
        available = list(BUILT_IN_ROUTINES.keys())
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=5)
            rows = conn.execute("SELECT name FROM jarvis_routines").fetchall()
            available.extend([r[0] for r in rows])
            conn.close()
        except sqlite3.Error:
            pass
        return f"Routine '{name}' inconnue. Disponibles: {', '.join(available)}"

    # Exécuter la routine
    from src.voice_router import route_voice_command

    results = [f"Routine '{name}': {routine.get('description', '')}"]

    # Message parlé
    if routine.get("speak"):
        results.append(f"[TTS] {routine['speak']}")

    # Exécuter chaque commande
    for cmd in routine.get("commands", []):
        r = route_voice_command(cmd)
        status = "OK" if r.get("success") else "FAIL"
        results.append(f"  [{status}] {cmd}")
        time.sleep(0.3)

    # Post-action
    if routine.get("post_action") == "backup":
        _run(["/usr/local/bin/jarvis", "backup"])
        results.append("  [OK] Backup SQL")

    # Logger l'usage
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.execute("""INSERT OR IGNORE INTO jarvis_routines (name, description, commands, speak, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (name, routine.get("description", ""), json.dumps(routine.get("commands", [])),
             routine.get("speak", ""), time.time()))
        conn.execute("UPDATE jarvis_routines SET usage_count = usage_count + 1, last_used = ? WHERE name = ?",
                    (time.time(), name))
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass

    return "\n".join(results)


def create_routine(name: str, commands: list[str], description: str = "", speak: str = "") -> str:
    """Creer une routine personnalisée."""
    _init_table()
    name = name.lower().strip().replace(" ", "_")
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.execute(
            "INSERT OR REPLACE INTO jarvis_routines (name, description, commands, speak, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, description, json.dumps(commands), speak, time.time()),
        )
        conn.commit()
        conn.close()
        return f"Routine '{name}' créée avec {len(commands)} commandes"
    except sqlite3.Error as e:
        return f"Erreur: {e}"


def list_routines() -> str:
    """Liste toutes les routines disponibles."""
    _init_table()
    lines = ["Routines JARVIS:"]

    # Built-in
    for name, routine in BUILT_IN_ROUTINES.items():
        lines.append(f"  {name:15s} — {routine['description']} [{len(routine['commands'])} cmds]")

    # Custom
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT name, description, commands, usage_count FROM jarvis_routines").fetchall()
        conn.close()
        custom = [r for r in rows if r["name"] not in BUILT_IN_ROUTINES]
        if custom:
            lines.append("  --- Custom ---")
            for r in custom:
                cmds = json.loads(r["commands"])
                lines.append(f"  {r['name']:15s} — {r['description']} [{len(cmds)} cmds, {r['usage_count']}x]")
    except sqlite3.Error:
        pass

    return "\n".join(lines)


def delete_routine(name: str) -> str:
    """Supprimer une routine custom."""
    if name in BUILT_IN_ROUTINES:
        return f"Impossible de supprimer la routine built-in '{name}'"
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        deleted = conn.execute("DELETE FROM jarvis_routines WHERE name = ?", (name,)).rowcount
        conn.commit()
        conn.close()
        return f"Routine '{name}' supprimée" if deleted else f"Routine '{name}' introuvable"
    except sqlite3.Error as e:
        return f"Erreur: {e}"
