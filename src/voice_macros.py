"""voice_macros.py — Systeme de macros vocales: enregistrer et rejouer des sequences.

Permet d'enregistrer une sequence de commandes vocales sous un nom,
puis de la rejouer. Stocke dans jarvis.db/voice_macros.

Usage:
    from src.voice_macros import macro_manager
    macro_manager.start_recording("setup_dev")
    macro_manager.add_command("ouvre terminal")
    macro_manager.add_command("ouvre vscode")
    macro_manager.stop_recording()
    macro_manager.play("setup_dev")  # Rejoue la sequence
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.voice_macros")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jarvis.db"


class MacroManager:
    """Gestionnaire de macros vocales."""

    def __init__(self):
        self._recording: bool = False
        self._current_name: str = ""
        self._current_commands: list[str] = []
        self._init_table()

    def _init_table(self):
        """Cree la table voice_macros si elle n'existe pas."""
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=5)
            conn.execute("""CREATE TABLE IF NOT EXISTS voice_macros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                commands TEXT NOT NULL,
                description TEXT DEFAULT '',
                usage_count INTEGER DEFAULT 0,
                created_at REAL DEFAULT 0,
                last_used REAL DEFAULT 0
            )""")
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error("Erreur init voice_macros: %s", e)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self, name: str) -> str:
        """Commence l'enregistrement d'une macro."""
        if self._recording:
            return f"Deja en enregistrement de '{self._current_name}'. Dites 'stop macro' d'abord."
        self._recording = True
        self._current_name = name.strip().lower().replace(" ", "_")
        self._current_commands = []
        logger.info("Enregistrement macro '%s' demarre", self._current_name)
        return f"Enregistrement macro '{self._current_name}' demarre. Dites vos commandes puis 'stop macro'."

    def add_command(self, command: str) -> bool:
        """Ajoute une commande a la macro en cours d'enregistrement."""
        if not self._recording:
            return False
        self._current_commands.append(command)
        logger.info("Macro '%s': ajout commande '%s'", self._current_name, command)
        return True

    def stop_recording(self) -> str:
        """Arrete l'enregistrement et sauvegarde la macro."""
        if not self._recording:
            return "Pas d'enregistrement en cours."
        if not self._current_commands:
            self._recording = False
            return "Macro annulee: aucune commande enregistree."

        name = self._current_name
        commands = self._current_commands.copy()
        self._recording = False
        self._current_name = ""
        self._current_commands = []

        # Sauvegarder
        try:
            conn = self._conn()
            conn.execute(
                "INSERT OR REPLACE INTO voice_macros (name, commands, created_at) VALUES (?, ?, ?)",
                (name, json.dumps(commands, ensure_ascii=False), time.time()),
            )
            conn.commit()
            conn.close()
            logger.info("Macro '%s' sauvegardee (%d commandes)", name, len(commands))
            return f"Macro '{name}' sauvegardee avec {len(commands)} commande(s): {', '.join(commands)}"
        except sqlite3.Error as e:
            return f"Erreur sauvegarde macro: {e}"

    def play(self, name: str) -> str:
        """Rejoue une macro par son nom."""
        name = name.strip().lower().replace(" ", "_")
        try:
            conn = self._conn()
            row = conn.execute(
                "SELECT commands FROM voice_macros WHERE name = ?", (name,)
            ).fetchone()
            if not row:
                conn.close()
                # Recherche fuzzy
                all_names = [r[0] for r in conn.execute("SELECT name FROM voice_macros").fetchall()]
                if all_names:
                    return f"Macro '{name}' introuvable. Macros disponibles: {', '.join(all_names)}"
                return f"Macro '{name}' introuvable. Aucune macro enregistree."

            commands = json.loads(row["commands"])
            # Mettre a jour les stats
            conn.execute(
                "UPDATE voice_macros SET usage_count = usage_count + 1, last_used = ? WHERE name = ?",
                (time.time(), name),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            return f"Erreur lecture macro: {e}"

        # Executer chaque commande
        from src.voice_router import route_voice_command
        results = []
        for cmd in commands:
            r = route_voice_command(cmd)
            status = "OK" if r.get("success") else "FAIL"
            results.append(f"  [{status}] {cmd}")
            # Petit delai entre les commandes
            time.sleep(0.3)

        return f"Macro '{name}' executee ({len(commands)} commandes):\n" + "\n".join(results)

    def list_macros(self) -> str:
        """Liste toutes les macros enregistrees."""
        try:
            conn = self._conn()
            rows = conn.execute(
                "SELECT name, commands, usage_count FROM voice_macros ORDER BY usage_count DESC"
            ).fetchall()
            conn.close()
            if not rows:
                return "Aucune macro enregistree"
            lines = []
            for r in rows:
                cmds = json.loads(r["commands"])
                lines.append(f"  {r['name']}: {len(cmds)} commande(s), utilise {r['usage_count']}x")
            return f"{len(rows)} macro(s):\n" + "\n".join(lines)
        except sqlite3.Error as e:
            return f"Erreur: {e}"

    def delete_macro(self, name: str) -> str:
        """Supprime une macro."""
        name = name.strip().lower().replace(" ", "_")
        try:
            conn = self._conn()
            deleted = conn.execute("DELETE FROM voice_macros WHERE name = ?", (name,)).rowcount
            conn.commit()
            conn.close()
            return f"Macro '{name}' supprimee" if deleted else f"Macro '{name}' introuvable"
        except sqlite3.Error as e:
            return f"Erreur: {e}"

    def get_recording_status(self) -> str:
        """Statut de l'enregistrement en cours."""
        if self._recording:
            return f"Enregistrement macro '{self._current_name}': {len(self._current_commands)} commande(s)"
        return "Pas d'enregistrement en cours"


# Instance globale
macro_manager = MacroManager()
