"""app_context.py — Detection de l'application active pour commandes contextuelles.

Detecte quelle application est au premier plan et adapte le comportement
des commandes vocales en consequence.

Usage:
    from src.app_context import get_active_app, get_contextual_commands
    app = get_active_app()  # {"name": "firefox", "class": "Firefox", "title": "..."}
"""
from __future__ import annotations

import logging
import re
import subprocess
from typing import Any

logger = logging.getLogger("jarvis.app_context")


def _run(cmd, timeout=3):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def get_active_app() -> dict[str, str]:
    """Detecte l'application active (nom, classe WM, titre)."""
    result = {"name": "", "class": "", "title": "", "pid": ""}

    wid = _run(["xdotool", "getactivewindow"])
    if not wid:
        return result

    result["title"] = _run(["xdotool", "getactivewindow", "getwindowname"])
    result["pid"] = _run(["xdotool", "getactivewindow", "getwindowpid"])

    # Classe WM
    raw = _run(["xprop", "-id", wid, "WM_CLASS"])
    match = re.search(r'"([^"]+)",\s*"([^"]+)"', raw)
    if match:
        result["name"] = match.group(1).lower()
        result["class"] = match.group(2)

    return result


def get_app_category(app: dict[str, str]) -> str:
    """Categorise l'application active."""
    name = app.get("name", "").lower()
    cls = app.get("class", "").lower()
    title = app.get("title", "").lower()

    # Navigateurs
    if any(b in name or b in cls for b in ["firefox", "chrome", "chromium", "brave", "edge"]):
        return "browser"

    # Editeurs de code
    if any(e in name or e in cls for e in ["code", "vscode", "sublime", "atom", "gedit", "vim", "nano"]):
        return "editor"

    # Terminaux
    if any(t in name or t in cls for t in ["terminal", "gnome-terminal", "konsole", "alacritty", "kitty", "tmux"]):
        return "terminal"

    # Gestionnaire de fichiers
    if any(f in name or f in cls for f in ["nautilus", "nemo", "thunar", "dolphin", "files"]):
        return "filemanager"

    # Multimédia
    if any(m in name or m in cls for m in ["spotify", "vlc", "rhythmbox", "totem", "mpv"]):
        return "media"

    # Communication
    if any(c in name or c in cls for c in ["discord", "telegram", "slack", "teams", "signal"]):
        return "chat"

    # Bureautique
    if any(o in name or o in cls for o in ["libreoffice", "writer", "calc", "impress"]):
        return "office"

    # Systeme
    if any(s in name or s in cls for s in ["monitor", "settings", "control-center"]):
        return "system"

    return "other"


# Commandes contextuelles par categorie d'app
CONTEXTUAL_HINTS: dict[str, dict[str, str]] = {
    "browser": {
        "sauvegarde": "Ctrl+D (bookmark) — dans le navigateur",
        "ferme": "Ctrl+W (ferme l'onglet)",
        "nouveau": "Ctrl+T (nouvel onglet)",
        "cherche": "Ctrl+F (recherche dans la page)",
        "rafraichis": "F5 (recharge)",
        "zoom": "Ctrl++ (zoom avant)",
    },
    "editor": {
        "sauvegarde": "Ctrl+S (sauvegarder le fichier)",
        "ferme": "Ctrl+W (ferme l'éditeur/tab)",
        "nouveau": "Ctrl+N (nouveau fichier)",
        "cherche": "Ctrl+F (recherche)",
        "execute": "F5 ou Ctrl+Shift+B (run/build)",
        "terminal": "Ctrl+` (terminal intégré)",
    },
    "terminal": {
        "copie": "Ctrl+Shift+C",
        "colle": "Ctrl+Shift+V",
        "nouveau": "Ctrl+Shift+T (nouvel onglet)",
        "ferme": "Ctrl+Shift+W (ferme l'onglet)",
        "cherche": "Ctrl+Shift+F",
    },
    "media": {
        "pause": "Espace",
        "suivant": "N ou Ctrl+Right",
        "precedent": "P ou Ctrl+Left",
        "volume": "playerctl volume",
    },
}


def get_context_info() -> str:
    """Retourne un résumé du contexte actuel pour le voice_router."""
    app = get_active_app()
    category = get_app_category(app)
    hints = CONTEXTUAL_HINTS.get(category, {})

    parts = [f"App: {app.get('class', '?')} ({category})"]
    if app.get("title"):
        parts.append(f"Titre: {app['title'][:50]}")
    if hints:
        parts.append("Contexte: " + ", ".join(f"{k}={v}" for k, v in list(hints.items())[:3]))
    return " | ".join(parts)
