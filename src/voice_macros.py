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

    def __init__(self) -> None:
        self._recording: bool = False
        self._current_name: str = ""
        self._current_commands: list[str] = []
        # Cache des macros pre-enregistrees (nom -> liste de commandes)
        self._prebuilt_cache: dict[str, list[str]] = {}
        self._init_table()
        self.load_prebuilt_macros()

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

    # ── Nouvelles methodes ──────────────────────────────────────────────────

    def load_prebuilt_macros(self) -> int:
        """Charge les macros pre-enregistrees depuis la DB dans le cache memoire.

        Retourne le nombre de macros chargees.
        """
        self._prebuilt_cache.clear()
        try:
            conn = self._conn()
            rows = conn.execute(
                "SELECT name, commands FROM voice_macros"
            ).fetchall()
            conn.close()
            for row in rows:
                self._prebuilt_cache[row["name"]] = json.loads(row["commands"])
            logger.info("Macros pre-enregistrees chargees: %d", len(self._prebuilt_cache))
        except sqlite3.Error as e:
            logger.error("Erreur chargement macros pre-enregistrees: %s", e)
        return len(self._prebuilt_cache)

    def execute_macro_by_name(self, name: str) -> dict[str, Any]:
        """Execute une macro par son nom (avec ou sans underscores / espaces).

        Cherche d'abord dans le cache, puis dans la DB.
        Retourne un dict avec success, macro, results et errors.
        """
        # Normaliser le nom (espaces → underscores, minuscules)
        normalized: str = name.strip().lower().replace(" ", "_")

        # Chercher les commandes dans le cache ou la DB
        commands: list[str] | None = self._prebuilt_cache.get(normalized)
        if commands is None:
            # Recherche en DB au cas ou le cache serait desynchronise
            try:
                conn = self._conn()
                row = conn.execute(
                    "SELECT commands FROM voice_macros WHERE name = ?", (normalized,)
                ).fetchone()
                conn.close()
                if row:
                    commands = json.loads(row["commands"])
            except sqlite3.Error as e:
                return {"success": False, "macro": normalized, "error": str(e), "results": []}

        if commands is None:
            return {
                "success": False,
                "macro": normalized,
                "error": f"Macro '{normalized}' introuvable",
                "results": [],
            }

        # Mettre a jour les stats d'utilisation
        try:
            conn = self._conn()
            conn.execute(
                "UPDATE voice_macros SET usage_count = usage_count + 1, last_used = ? WHERE name = ?",
                (time.time(), normalized),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error:
            pass  # Non bloquant

        # Executer chaque commande sequentiellement
        from src.voice_router import route_voice_command

        results: list[dict[str, Any]] = []
        errors: int = 0
        for cmd in commands:
            try:
                r: dict[str, Any] = route_voice_command(cmd)
                success: bool = bool(r.get("success"))
                results.append({"command": cmd, "success": success, "result": r})
                if not success:
                    errors += 1
            except Exception as e:
                results.append({"command": cmd, "success": False, "error": str(e)})
                errors += 1
            time.sleep(0.3)

        return {
            "success": errors == 0,
            "macro": normalized,
            "total": len(commands),
            "errors": errors,
            "results": results,
        }

    def get_stats(self) -> dict[str, Any]:
        """Retourne des statistiques sur les macros enregistrees.

        Inclut le nombre total, le top des plus utilisees,
        la derniere executee et le nombre en cache.
        """
        stats: dict[str, Any] = {
            "total": 0,
            "cached": len(self._prebuilt_cache),
            "total_executions": 0,
            "top_macros": [],
            "last_used_macro": None,
            "recording": self._recording,
        }
        try:
            conn = self._conn()
            # Nombre total et executions
            row = conn.execute(
                "SELECT COUNT(*) as cnt, COALESCE(SUM(usage_count), 0) as total_exec "
                "FROM voice_macros"
            ).fetchone()
            stats["total"] = row["cnt"]
            stats["total_executions"] = row["total_exec"]

            # Top 5 macros les plus utilisees
            top_rows = conn.execute(
                "SELECT name, usage_count, description FROM voice_macros "
                "WHERE usage_count > 0 ORDER BY usage_count DESC LIMIT 5"
            ).fetchall()
            stats["top_macros"] = [
                {"name": r["name"], "usage_count": r["usage_count"], "description": r["description"]}
                for r in top_rows
            ]

            # Derniere macro utilisee
            last = conn.execute(
                "SELECT name, last_used FROM voice_macros "
                "WHERE last_used > 0 ORDER BY last_used DESC LIMIT 1"
            ).fetchone()
            if last:
                stats["last_used_macro"] = {"name": last["name"], "timestamp": last["last_used"]}

            conn.close()
        except sqlite3.Error as e:
            stats["error"] = str(e)
        return stats


# Instance globale
macro_manager = MacroManager()
