#!/usr/bin/env python3
"""voice_app_controller.py — Controle vocal des applications Linux courantes.

50 commandes vocales reparties en 5 categories:
1. Navigateur (Firefox/Chrome) — 10 commandes
2. VSCode — 10 commandes
3. Terminal — 10 commandes
4. Spotify — 10 commandes
5. Systeme GNOME — 10 commandes

Usage:
    python src/voice_app_controller.py --cmd "nouvel onglet"
    python src/voice_app_controller.py --list
    python src/voice_app_controller.py --init-db
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Garantir que le dossier racine jarvis est dans le PYTHONPATH
_jarvis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _jarvis_root not in sys.path:
    sys.path.insert(0, _jarvis_root)

logger = logging.getLogger(__name__)

DB_PATH = Path(_jarvis_root) / "data" / "jarvis.db"


# ---------------------------------------------------------------------------
# Modele de commande applicative
# ---------------------------------------------------------------------------
@dataclass
class AppCommand:
    """Represente une commande vocale pour une application."""

    name: str
    triggers: list[str]
    action_type: str  # "xdotool_key", "xdotool_type", "dbus", "pactl", "shell"
    action: str
    category: str
    description: str = ""
    confirm: bool = False


# ===========================================================================
# Definitions des 50 commandes — 5 categories x 10 commandes
# ===========================================================================

# --- 1. Navigateur (Firefox / Chrome) — 10 commandes ---
BROWSER_COMMANDS: list[AppCommand] = [
    AppCommand(
        name="browser_new_tab",
        triggers=["nouvel onglet", "nouveau tab", "ouvre un onglet"],
        action_type="xdotool_key",
        action="ctrl+t",
        category="browser",
        description="Ouvrir un nouvel onglet dans le navigateur",
    ),
    AppCommand(
        name="browser_close_tab",
        triggers=["ferme l'onglet", "ferme l onglet", "close tab", "ferme onglet"],
        action_type="xdotool_key",
        action="ctrl+w",
        category="browser",
        description="Fermer l'onglet actif",
    ),
    AppCommand(
        name="browser_next_tab",
        triggers=["onglet suivant", "tab suivant", "prochain onglet"],
        action_type="xdotool_key",
        action="ctrl+Tab",
        category="browser",
        description="Passer a l'onglet suivant",
    ),
    AppCommand(
        name="browser_prev_tab",
        triggers=["onglet precedent", "onglet précédent", "tab precedent"],
        action_type="xdotool_key",
        action="ctrl+shift+Tab",
        category="browser",
        description="Passer a l'onglet precedent",
    ),
    AppCommand(
        name="browser_refresh",
        triggers=["actualise", "rafraichis", "refresh", "recharge la page"],
        action_type="xdotool_key",
        action="F5",
        category="browser",
        description="Actualiser la page courante",
    ),
    AppCommand(
        name="browser_back",
        triggers=["retour", "page precedente", "page précédente", "go back"],
        action_type="xdotool_key",
        action="alt+Left",
        category="browser",
        description="Revenir a la page precedente",
    ),
    AppCommand(
        name="browser_forward",
        triggers=["avance", "page suivante", "go forward"],
        action_type="xdotool_key",
        action="alt+Right",
        category="browser",
        description="Aller a la page suivante",
    ),
    AppCommand(
        name="browser_address_bar",
        triggers=["barre d'adresse", "barre d adresse", "url", "adresse"],
        action_type="xdotool_key",
        action="ctrl+l",
        category="browser",
        description="Focus sur la barre d'adresse",
    ),
    AppCommand(
        name="browser_search",
        triggers=["recherche", "barre de recherche", "search"],
        action_type="xdotool_key",
        action="ctrl+k",
        category="browser",
        description="Ouvrir la barre de recherche",
    ),
    AppCommand(
        name="browser_fullscreen",
        triggers=["plein ecran navigateur", "plein écran navigateur", "fullscreen browser"],
        action_type="xdotool_key",
        action="F11",
        category="browser",
        description="Basculer le mode plein ecran du navigateur",
    ),
]

# --- 2. VSCode — 10 commandes ---
VSCODE_COMMANDS: list[AppCommand] = [
    AppCommand(
        name="vscode_new_file",
        triggers=["nouveau fichier", "new file", "crée un fichier"],
        action_type="xdotool_key",
        action="ctrl+n",
        category="vscode",
        description="Creer un nouveau fichier dans VSCode",
    ),
    AppCommand(
        name="vscode_terminal",
        triggers=["ouvre le terminal", "terminal vscode", "toggle terminal"],
        action_type="xdotool_key",
        action="ctrl+grave",
        category="vscode",
        description="Ouvrir/fermer le terminal integre VSCode",
    ),
    AppCommand(
        name="vscode_save",
        triggers=["sauvegarde", "enregistre", "save", "ctrl s"],
        action_type="xdotool_key",
        action="ctrl+s",
        category="vscode",
        description="Sauvegarder le fichier actif",
    ),
    AppCommand(
        name="vscode_search",
        triggers=["cherche", "recherche globale", "find in files", "cherche dans les fichiers"],
        action_type="xdotool_key",
        action="ctrl+shift+f",
        category="vscode",
        description="Recherche globale dans les fichiers",
    ),
    AppCommand(
        name="vscode_palette",
        triggers=["palette", "command palette", "palette de commandes"],
        action_type="xdotool_key",
        action="ctrl+shift+p",
        category="vscode",
        description="Ouvrir la palette de commandes VSCode",
    ),
    AppCommand(
        name="vscode_comment",
        triggers=["commentaire", "commente", "toggle comment", "comment"],
        action_type="xdotool_key",
        action="ctrl+slash",
        category="vscode",
        description="Commenter/decommenter la ligne ou selection",
    ),
    AppCommand(
        name="vscode_close_file",
        triggers=["ferme le fichier", "close file", "ferme le tab"],
        action_type="xdotool_key",
        action="ctrl+w",
        category="vscode",
        description="Fermer le fichier actif dans VSCode",
    ),
    AppCommand(
        name="vscode_goto_line",
        triggers=["va a la ligne", "va à la ligne", "goto line", "aller a la ligne"],
        action_type="xdotool_key",
        action="ctrl+g",
        category="vscode",
        description="Aller a un numero de ligne",
    ),
    AppCommand(
        name="vscode_split",
        triggers=["split", "divise l'editeur", "split editor"],
        action_type="xdotool_key",
        action="ctrl+backslash",
        category="vscode",
        description="Diviser l'editeur en deux panneaux",
    ),
    AppCommand(
        name="vscode_zen_mode",
        triggers=["zen mode", "mode zen", "mode concentration"],
        action_type="xdotool_key",
        action="ctrl+k z",
        category="vscode",
        description="Activer/desactiver le mode zen VSCode",
    ),
]

# --- 3. Terminal — 10 commandes ---
TERMINAL_COMMANDS: list[AppCommand] = [
    AppCommand(
        name="terminal_new_tab",
        triggers=["nouvel onglet terminal", "nouveau tab terminal", "new terminal tab"],
        action_type="xdotool_key",
        action="ctrl+shift+t",
        category="terminal",
        description="Ouvrir un nouvel onglet dans le terminal",
    ),
    AppCommand(
        name="terminal_copy",
        triggers=["copie terminal", "copie", "copy terminal"],
        action_type="xdotool_key",
        action="ctrl+shift+c",
        category="terminal",
        description="Copier la selection dans le terminal",
    ),
    AppCommand(
        name="terminal_paste",
        triggers=["colle terminal", "colle", "paste terminal"],
        action_type="xdotool_key",
        action="ctrl+shift+v",
        category="terminal",
        description="Coller dans le terminal",
    ),
    AppCommand(
        name="terminal_clear",
        triggers=["clear", "efface", "nettoie le terminal"],
        action_type="xdotool_key",
        action="ctrl+l",
        category="terminal",
        description="Effacer le contenu du terminal",
    ),
    AppCommand(
        name="terminal_cancel",
        triggers=["annule", "cancel", "interromps", "stop commande"],
        action_type="xdotool_key",
        action="ctrl+c",
        category="terminal",
        description="Annuler la commande en cours (SIGINT)",
    ),
    AppCommand(
        name="terminal_close",
        triggers=["ferme le terminal", "close terminal", "ferme la fenetre terminal"],
        action_type="xdotool_key",
        action="ctrl+shift+w",
        category="terminal",
        description="Fermer l'onglet ou la fenetre du terminal",
    ),
    AppCommand(
        name="terminal_zoom_in",
        triggers=["zoom plus", "zoom in", "agrandis le texte"],
        action_type="xdotool_key",
        action="ctrl+plus",
        category="terminal",
        description="Augmenter la taille du texte dans le terminal",
    ),
    AppCommand(
        name="terminal_zoom_out",
        triggers=["zoom moins", "zoom out", "reduis le texte"],
        action_type="xdotool_key",
        action="ctrl+minus",
        category="terminal",
        description="Reduire la taille du texte dans le terminal",
    ),
    AppCommand(
        name="terminal_history",
        triggers=["historique", "history", "recherche historique"],
        action_type="xdotool_key",
        action="ctrl+r",
        category="terminal",
        description="Recherche dans l'historique des commandes",
    ),
    AppCommand(
        name="terminal_exit",
        triggers=["fin", "exit terminal", "quitte le terminal"],
        action_type="xdotool_type_enter",
        action="exit",
        category="terminal",
        description="Taper 'exit' et valider pour quitter le terminal",
    ),
]

# --- 4. Spotify — 10 commandes ---
SPOTIFY_COMMANDS: list[AppCommand] = [
    AppCommand(
        name="spotify_play_pause",
        triggers=["play pause", "lecture pause", "play", "pause musique"],
        action_type="dbus",
        action="org.mpris.MediaPlayer2.Player.PlayPause",
        category="spotify",
        description="Basculer lecture/pause sur Spotify",
    ),
    AppCommand(
        name="spotify_next",
        triggers=["suivant spotify", "chanson suivante", "next", "piste suivante"],
        action_type="dbus",
        action="org.mpris.MediaPlayer2.Player.Next",
        category="spotify",
        description="Passer a la piste suivante",
    ),
    AppCommand(
        name="spotify_previous",
        triggers=["precedent spotify", "précédent spotify", "chanson precedente", "previous"],
        action_type="dbus",
        action="org.mpris.MediaPlayer2.Player.Previous",
        category="spotify",
        description="Revenir a la piste precedente",
    ),
    AppCommand(
        name="spotify_volume_up",
        triggers=["volume plus spotify", "monte le son spotify", "plus fort spotify"],
        action_type="pactl",
        action="volume_up",
        category="spotify",
        description="Augmenter le volume de Spotify (+5%)",
    ),
    AppCommand(
        name="spotify_volume_down",
        triggers=["volume moins spotify", "baisse le son spotify", "moins fort spotify"],
        action_type="pactl",
        action="volume_down",
        category="spotify",
        description="Baisser le volume de Spotify (-5%)",
    ),
    AppCommand(
        name="spotify_mute",
        triggers=["mute spotify", "coupe le son spotify", "silence spotify"],
        action_type="pactl",
        action="mute_toggle",
        category="spotify",
        description="Couper/reactiver le son de Spotify",
    ),
    AppCommand(
        name="spotify_like",
        triggers=["like", "j'aime", "ajoute aux favoris", "like spotify"],
        action_type="dbus",
        action="like_current",
        category="spotify",
        description="Ajouter la piste actuelle aux favoris",
    ),
    AppCommand(
        name="spotify_shuffle",
        triggers=["shuffle", "mode aleatoire", "mode aléatoire", "melange"],
        action_type="dbus",
        action="shuffle_toggle",
        category="spotify",
        description="Activer/desactiver la lecture aleatoire",
    ),
    AppCommand(
        name="spotify_repeat",
        triggers=["repetition", "répétition", "repeat", "boucle"],
        action_type="dbus",
        action="repeat_toggle",
        category="spotify",
        description="Basculer le mode repetition (off/track/playlist)",
    ),
    AppCommand(
        name="spotify_now_playing",
        triggers=["quelle chanson", "c'est quoi cette chanson", "now playing", "en cours"],
        action_type="dbus",
        action="now_playing",
        category="spotify",
        description="Afficher la piste en cours de lecture",
    ),
]

# --- 5. Systeme GNOME — 10 commandes ---
GNOME_COMMANDS: list[AppCommand] = [
    AppCommand(
        name="gnome_activities",
        triggers=["activites", "activités", "activities", "vue d'ensemble"],
        action_type="xdotool_key",
        action="super",
        category="gnome",
        description="Ouvrir la vue d'ensemble GNOME (Activities)",
    ),
    AppCommand(
        name="gnome_notifications",
        triggers=["notifications", "centre de notifications", "notifs"],
        action_type="xdotool_key",
        action="super+v",
        category="gnome",
        description="Ouvrir le panneau de notifications",
    ),
    AppCommand(
        name="gnome_settings",
        triggers=["parametres", "paramètres", "settings", "reglages", "réglages"],
        action_type="shell",
        action="gnome-control-center",
        category="gnome",
        description="Ouvrir les parametres systeme GNOME",
    ),
    AppCommand(
        name="gnome_files",
        triggers=["fichiers", "explorateur", "nautilus", "gestionnaire de fichiers"],
        action_type="shell",
        action="nautilus --new-window",
        category="gnome",
        description="Ouvrir le gestionnaire de fichiers (Nautilus)",
    ),
    AppCommand(
        name="gnome_calculator",
        triggers=["calculatrice", "calculette", "calculator", "calc"],
        action_type="shell",
        action="gnome-calculator",
        category="gnome",
        description="Ouvrir la calculatrice GNOME",
    ),
    AppCommand(
        name="gnome_screenshot",
        triggers=["capture d'ecran", "capture d'écran", "screenshot gnome", "capture ecran"],
        action_type="xdotool_key",
        action="Print",
        category="gnome",
        description="Prendre une capture d'ecran (outil GNOME)",
    ),
    AppCommand(
        name="gnome_lock_screen",
        triggers=["verrouille l'ecran", "verrouille l ecran", "lock screen", "verrouille"],
        action_type="shell",
        action="gnome-screensaver-command -l",
        category="gnome",
        description="Verrouiller la session GNOME",
    ),
    AppCommand(
        name="gnome_night_light",
        triggers=["mode nuit", "night light", "lumiere nocturne", "eclairage nocturne"],
        action_type="shell",
        action="gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled true",
        category="gnome",
        description="Activer le mode lumiere nocturne GNOME",
    ),
    AppCommand(
        name="gnome_text_editor",
        triggers=["editeur de texte", "éditeur de texte", "text editor", "gedit"],
        action_type="shell",
        action="gnome-text-editor",
        category="gnome",
        description="Ouvrir l'editeur de texte GNOME",
    ),
    AppCommand(
        name="gnome_system_monitor",
        triggers=["moniteur systeme", "moniteur système", "system monitor", "task manager"],
        action_type="shell",
        action="gnome-system-monitor",
        category="gnome",
        description="Ouvrir le moniteur systeme GNOME",
    ),
]

# Toutes les commandes regroupees
ALL_APP_COMMANDS: list[AppCommand] = (
    BROWSER_COMMANDS + VSCODE_COMMANDS + TERMINAL_COMMANDS
    + SPOTIFY_COMMANDS + GNOME_COMMANDS
)

# Index rapide par trigger pour le dispatch O(1)
_TRIGGER_INDEX: dict[str, AppCommand] = {}
for _cmd in ALL_APP_COMMANDS:
    for _trigger in _cmd.triggers:
        _TRIGGER_INDEX[_trigger.lower()] = _cmd


# ===========================================================================
# VoiceAppController — Classe principale
# ===========================================================================
class VoiceAppController:
    """Controleur vocal pour les applications Linux courantes.

    Gere 50 commandes reparties en 5 categories:
    - browser: Firefox/Chrome (xdotool)
    - vscode: Visual Studio Code (xdotool)
    - terminal: GNOME Terminal (xdotool)
    - spotify: Spotify (dbus-send / pactl)
    - gnome: Systeme GNOME (xdotool / shell)
    """

    def __init__(self) -> None:
        """Initialise le controleur et l'index des triggers."""
        self._trigger_index: dict[str, AppCommand] = dict(_TRIGGER_INDEX)
        self._stats: dict[str, int] = {"total": 0, "success": 0, "fail": 0}

    # -----------------------------------------------------------------------
    # Execution systeme
    # -----------------------------------------------------------------------
    @staticmethod
    def _run(cmd: str | list[str], timeout: int = 10, shell: bool = False) -> tuple[bool, str]:
        """Execute une commande systeme. Retourne (success, output)."""
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, shell=shell,
            )
            output = r.stdout.strip() or r.stderr.strip()
            return r.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except FileNotFoundError:
            name = cmd[0] if isinstance(cmd, list) else cmd.split()[0]
            return False, f"{name} non installe"
        except Exception as e:
            return False, str(e)

    # -----------------------------------------------------------------------
    # Execution xdotool
    # -----------------------------------------------------------------------
    def _exec_xdotool_key(self, key_combo: str) -> tuple[bool, str]:
        """Envoie une combinaison de touches via xdotool key."""
        # Gestion des sequences (ex: "ctrl+k z" → deux appels)
        parts = key_combo.split(" ")
        for part in parts:
            ok, out = self._run(["xdotool", "key", "--clearmodifiers", part])
            if not ok:
                return False, f"xdotool key {part} echoue: {out}"
            if len(parts) > 1:
                # Petit delai entre les touches d'une sequence
                time.sleep(0.15)
        return True, f"Touche(s) envoyee(s): {key_combo}"

    def _exec_xdotool_type_enter(self, text: str) -> tuple[bool, str]:
        """Tape du texte puis appuie sur Entree via xdotool."""
        ok, out = self._run(["xdotool", "type", "--clearmodifiers", text])
        if not ok:
            return False, f"xdotool type echoue: {out}"
        time.sleep(0.05)
        ok2, out2 = self._run(["xdotool", "key", "Return"])
        if not ok2:
            return False, f"xdotool key Return echoue: {out2}"
        return True, f"Tape '{text}' + Entree"

    # -----------------------------------------------------------------------
    # Execution dbus (Spotify MPRIS)
    # -----------------------------------------------------------------------
    def _exec_dbus_spotify(self, method: str) -> tuple[bool, str]:
        """Execute une commande Spotify via dbus-send (MPRIS)."""
        dest = "org.mpris.MediaPlayer2.spotify"
        path = "/org/mpris/MediaPlayer2"

        # Commandes speciales
        if method == "now_playing":
            return self._spotify_now_playing()
        if method == "like_current":
            return True, "Like via dbus non supporte nativement — utilisez le raccourci Spotify"
        if method == "shuffle_toggle":
            return self._spotify_property_toggle("Shuffle")
        if method == "repeat_toggle":
            return self._spotify_property_cycle("LoopStatus", ["None", "Track", "Playlist"])

        # Commandes MPRIS standard (PlayPause, Next, Previous)
        cmd = [
            "dbus-send", "--print-reply",
            f"--dest={dest}", path,
            f"{method}",
        ]
        ok, out = self._run(cmd)
        if not ok:
            return False, f"dbus-send echoue (Spotify lance?): {out}"
        return True, f"Spotify: {method.split('.')[-1]}"

    def _spotify_now_playing(self) -> tuple[bool, str]:
        """Recupere la piste en cours via dbus-send."""
        cmd = [
            "dbus-send", "--print-reply",
            "--dest=org.mpris.MediaPlayer2.spotify",
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties.Get",
            "string:org.mpris.MediaPlayer2.Player",
            "string:Metadata",
        ]
        ok, out = self._run(cmd, timeout=5)
        if not ok:
            return False, "Impossible de lire la piste (Spotify lance?)"

        # Extraction artiste et titre depuis le dump dbus
        title = _extract_dbus_string(out, "xesam:title")
        artist = _extract_dbus_string(out, "xesam:artist")
        if title:
            info = f"{artist} - {title}" if artist else title
            return True, f"En cours: {info}"
        return True, "Piste inconnue"

    def _spotify_property_toggle(self, prop: str) -> tuple[bool, str]:
        """Toggle une propriete booleenne Spotify (Shuffle)."""
        # Lire l'etat actuel
        cmd_get = [
            "dbus-send", "--print-reply",
            "--dest=org.mpris.MediaPlayer2.spotify",
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties.Get",
            "string:org.mpris.MediaPlayer2.Player",
            f"string:{prop}",
        ]
        ok, out = self._run(cmd_get)
        current = "true" in out.lower()
        new_val = "false" if current else "true"

        cmd_set = [
            "dbus-send", "--print-reply",
            "--dest=org.mpris.MediaPlayer2.spotify",
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties.Set",
            "string:org.mpris.MediaPlayer2.Player",
            f"string:{prop}",
            f"variant:boolean:{new_val}",
        ]
        ok2, out2 = self._run(cmd_set)
        if not ok2:
            return False, f"Toggle {prop} echoue: {out2}"
        state = "active" if new_val == "true" else "desactive"
        return True, f"{prop} {state}"

    def _spotify_property_cycle(self, prop: str, values: list[str]) -> tuple[bool, str]:
        """Cycle une propriete string Spotify (LoopStatus)."""
        cmd_get = [
            "dbus-send", "--print-reply",
            "--dest=org.mpris.MediaPlayer2.spotify",
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties.Get",
            "string:org.mpris.MediaPlayer2.Player",
            f"string:{prop}",
        ]
        ok, out = self._run(cmd_get)
        # Trouver la valeur actuelle et passer a la suivante
        current_idx = 0
        for i, v in enumerate(values):
            if v.lower() in out.lower():
                current_idx = i
                break
        next_val = values[(current_idx + 1) % len(values)]

        cmd_set = [
            "dbus-send", "--print-reply",
            "--dest=org.mpris.MediaPlayer2.spotify",
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties.Set",
            "string:org.mpris.MediaPlayer2.Player",
            f"string:{prop}",
            f"variant:string:{next_val}",
        ]
        ok2, out2 = self._run(cmd_set)
        if not ok2:
            return False, f"Cycle {prop} echoue: {out2}"
        return True, f"{prop}: {next_val}"

    # -----------------------------------------------------------------------
    # Execution pactl (volume Spotify)
    # -----------------------------------------------------------------------
    def _exec_pactl(self, action: str) -> tuple[bool, str]:
        """Controle le volume via pactl (PipeWire/PulseAudio)."""
        if action == "volume_up":
            ok, out = self._run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"])
            return ok, "Volume +5%" if ok else f"pactl echoue: {out}"
        elif action == "volume_down":
            ok, out = self._run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"])
            return ok, "Volume -5%" if ok else f"pactl echoue: {out}"
        elif action == "mute_toggle":
            ok, out = self._run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
            return ok, "Mute bascule" if ok else f"pactl echoue: {out}"
        return False, f"Action pactl inconnue: {action}"

    # -----------------------------------------------------------------------
    # Execution shell (commandes systeme GNOME)
    # -----------------------------------------------------------------------
    def _exec_shell(self, command: str) -> tuple[bool, str]:
        """Execute une commande shell en arriere-plan (non bloquante pour les apps GUI)."""
        try:
            # Lancer en arriere-plan pour les applications GUI
            subprocess.Popen(
                command, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True, f"Lance: {command}"
        except Exception as e:
            return False, f"Echec lancement: {e}"

    # -----------------------------------------------------------------------
    # Dispatch principal
    # -----------------------------------------------------------------------
    def execute(self, text: str) -> dict[str, Any]:
        """Execute une commande vocale applicative.

        Args:
            text: Commande vocale brute (ex: "nouvel onglet", "play pause")

        Returns:
            Dict avec success, method, result, confidence, module, category
        """
        normalized = text.lower().strip()
        self._stats["total"] += 1

        # Recherche exacte dans l'index des triggers
        cmd = self._trigger_index.get(normalized)

        # Recherche par inclusion si pas de match exact
        if cmd is None:
            cmd = self._find_by_inclusion(normalized)

        if cmd is None:
            return {
                "success": False,
                "method": "app_controller",
                "result": f"Commande applicative non reconnue: {text}",
                "confidence": 0.0,
                "module": "src.voice_app_controller",
                "category": "unknown",
            }

        # Executer selon le type d'action
        ok, result_text = self._dispatch_action(cmd)

        if ok:
            self._stats["success"] += 1
            # Mettre a jour le compteur d'utilisation en DB
            self._update_usage_count(cmd.name, success=True)
        else:
            self._stats["fail"] += 1
            self._update_usage_count(cmd.name, success=False)

        return {
            "success": ok,
            "method": f"app_{cmd.category}",
            "result": result_text,
            "confidence": 0.95 if ok else 0.3,
            "module": "src.voice_app_controller",
            "category": cmd.category,
        }

    def _find_by_inclusion(self, text: str) -> AppCommand | None:
        """Recherche une commande par inclusion de trigger dans le texte."""
        best_cmd: AppCommand | None = None
        best_len = 0
        for trigger, cmd in self._trigger_index.items():
            if trigger in text and len(trigger) > best_len:
                best_cmd = cmd
                best_len = len(trigger)
        return best_cmd

    def _dispatch_action(self, cmd: AppCommand) -> tuple[bool, str]:
        """Dispatch l'execution selon le type d'action."""
        if cmd.action_type == "xdotool_key":
            return self._exec_xdotool_key(cmd.action)
        elif cmd.action_type == "xdotool_type_enter":
            return self._exec_xdotool_type_enter(cmd.action)
        elif cmd.action_type == "dbus":
            return self._exec_dbus_spotify(cmd.action)
        elif cmd.action_type == "pactl":
            return self._exec_pactl(cmd.action)
        elif cmd.action_type == "shell":
            return self._exec_shell(cmd.action)
        return False, f"Type d'action inconnu: {cmd.action_type}"

    def _update_usage_count(self, name: str, success: bool) -> None:
        """Met a jour les compteurs d'utilisation dans la DB."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            if success:
                conn.execute(
                    "UPDATE voice_commands SET usage_count = usage_count + 1, "
                    "success_count = success_count + 1, last_used = ? WHERE name = ?",
                    (time.time(), name),
                )
            else:
                conn.execute(
                    "UPDATE voice_commands SET usage_count = usage_count + 1, "
                    "fail_count = fail_count + 1, last_used = ? WHERE name = ?",
                    (time.time(), name),
                )
            conn.commit()
            conn.close()
        except Exception:
            pass  # Ne jamais bloquer le pipeline vocal

    # -----------------------------------------------------------------------
    # Listing et stats
    # -----------------------------------------------------------------------
    def list_commands(self, category: str | None = None) -> dict[str, list[str]]:
        """Liste toutes les commandes par categorie."""
        result: dict[str, list[str]] = {}
        for cmd in ALL_APP_COMMANDS:
            if category and cmd.category != category:
                continue
            if cmd.category not in result:
                result[cmd.category] = []
            result[cmd.category].extend(cmd.triggers)
        return result

    @property
    def command_count(self) -> int:
        """Nombre total de commandes."""
        return len(ALL_APP_COMMANDS)

    @property
    def trigger_count(self) -> int:
        """Nombre total de triggers (phrases reconnues)."""
        return len(self._trigger_index)

    def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques d'utilisation."""
        return {
            **self._stats,
            "commands": self.command_count,
            "triggers": self.trigger_count,
            "categories": ["browser", "vscode", "terminal", "spotify", "gnome"],
        }


# ===========================================================================
# Helpers
# ===========================================================================
def _extract_dbus_string(output: str, key: str) -> str:
    """Extrait une valeur string depuis un dump dbus-send."""
    lines = output.split("\n")
    found_key = False
    for line in lines:
        if key in line:
            found_key = True
            continue
        if found_key and "string" in line:
            # Extraire la valeur entre guillemets
            start = line.find('"')
            end = line.rfind('"')
            if start != -1 and end > start:
                return line[start + 1:end]
            found_key = False
    return ""


# ===========================================================================
# VOICE_COMMANDS — Export pour le voice_router (format compatible)
# ===========================================================================
VOICE_COMMANDS: dict[str, str] = {}
for _cmd in ALL_APP_COMMANDS:
    for _trigger in _cmd.triggers:
        VOICE_COMMANDS[_trigger] = _cmd.description


# ===========================================================================
# Singleton et fonction d'entree pour le voice_router
# ===========================================================================
_controller: VoiceAppController | None = None


def _get_controller() -> VoiceAppController:
    """Retourne le singleton du controleur."""
    global _controller
    if _controller is None:
        _controller = VoiceAppController()
    return _controller


def execute_app_command(text: str) -> dict[str, Any]:
    """Point d'entree pour le voice_router — execute une commande applicative."""
    return _get_controller().execute(text)


# ===========================================================================
# Insertion des 50 commandes dans la DB voice_commands
# ===========================================================================
def init_db() -> int:
    """Insere les 50 commandes applicatives dans voice_commands de jarvis.db.

    Returns:
        Nombre de commandes inserees.
    """
    conn = sqlite3.connect(str(DB_PATH))
    inserted = 0
    now = time.time()

    for cmd in ALL_APP_COMMANDS:
        triggers_json = json.dumps(cmd.triggers, ensure_ascii=False)
        # Determiner l'action_type pour la DB
        if cmd.action_type in ("xdotool_key", "xdotool_type_enter"):
            db_action_type = "xdotool"
        elif cmd.action_type == "dbus":
            db_action_type = "dbus"
        elif cmd.action_type == "pactl":
            db_action_type = "pactl"
        else:
            db_action_type = "bash"

        # Construire la commande bash complete pour la DB
        if cmd.action_type == "xdotool_key":
            parts = cmd.action.split(" ")
            if len(parts) > 1:
                db_action = " && ".join(
                    f"xdotool key --clearmodifiers {p}" for p in parts
                )
            else:
                db_action = f"xdotool key --clearmodifiers {cmd.action}"
        elif cmd.action_type == "xdotool_type_enter":
            db_action = f'xdotool type --clearmodifiers "{cmd.action}" && xdotool key Return'
        elif cmd.action_type == "dbus":
            db_action = (
                f"dbus-send --print-reply "
                f"--dest=org.mpris.MediaPlayer2.spotify "
                f"/org/mpris/MediaPlayer2 "
                f"{cmd.action}"
            )
        elif cmd.action_type == "pactl":
            if cmd.action == "volume_up":
                db_action = "pactl set-sink-volume @DEFAULT_SINK@ +5%"
            elif cmd.action == "volume_down":
                db_action = "pactl set-sink-volume @DEFAULT_SINK@ -5%"
            elif cmd.action == "mute_toggle":
                db_action = "pactl set-sink-mute @DEFAULT_SINK@ toggle"
            else:
                db_action = cmd.action
        else:
            db_action = cmd.action

        try:
            conn.execute(
                """INSERT OR REPLACE INTO voice_commands
                (name, category, description, triggers, action_type, action,
                 params, confirm, enabled, created_at, usage_count, success_count, fail_count)
                VALUES (?, ?, ?, ?, ?, ?, '[]', ?, 1, ?, 0, 0, 0)""",
                (
                    cmd.name,
                    f"app_{cmd.category}",
                    cmd.description,
                    triggers_json,
                    db_action_type,
                    db_action,
                    1 if cmd.confirm else 0,
                    now,
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            logger.debug("Commande %s deja presente, mise a jour", cmd.name)

    conn.commit()
    conn.close()
    logger.info("Insere %d commandes applicatives dans voice_commands", inserted)
    return inserted


# ===========================================================================
# CLI
# ===========================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS Voice App Controller")
    parser.add_argument("--cmd", help="Commande vocale a executer")
    parser.add_argument("--list", action="store_true", help="Lister toutes les commandes")
    parser.add_argument("--init-db", action="store_true", help="Inserer les 50 commandes dans jarvis.db")
    parser.add_argument("--stats", action="store_true", help="Afficher les statistiques")
    parser.add_argument("--category", help="Filtrer par categorie (browser, vscode, terminal, spotify, gnome)")
    args = parser.parse_args()

    if args.init_db:
        count = init_db()
        print(f"OK: {count} commandes inserees dans voice_commands (jarvis.db)")

    elif args.list:
        ctrl = VoiceAppController()
        cmds = ctrl.list_commands(category=args.category)
        total = 0
        for cat, triggers in sorted(cmds.items()):
            print(f"\n{'=' * 50}")
            print(f"  {cat.upper()} ({len(triggers)} triggers)")
            print(f"{'=' * 50}")
            for t in sorted(triggers):
                print(f"  - {t}")
            total += len(triggers)
        print(f"\nTotal: {total} triggers pour {ctrl.command_count} commandes")

    elif args.cmd:
        result = execute_app_command(args.cmd)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.stats:
        ctrl = VoiceAppController()
        stats = ctrl.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
