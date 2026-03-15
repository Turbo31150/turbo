"""Capture d'écran Linux (scrot, grim, gnome-screenshot)."""
from __future__ import annotations

import logging
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


def _find_tool() -> str | None:
    for tool in ["grim", "scrot", "gnome-screenshot", "spectacle"]:
        if shutil.which(tool):
            return tool
    return None


def capture_screen(output_path: Path | None = None) -> Path | None:
    """Capture l'écran complet."""
    tool = _find_tool()
    if not tool:
        log.error("Aucun outil de capture trouvé (grim, scrot, gnome-screenshot)")
        return None

    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path.home() / "jarvis" / "data" / "screenshots" / f"screen_{ts}.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if tool == "grim":
            subprocess.run(["grim", str(output_path)], check=True, timeout=10)
        elif tool == "scrot":
            subprocess.run(["scrot", str(output_path)], check=True, timeout=10)
        elif tool == "gnome-screenshot":
            subprocess.run(["gnome-screenshot", "-f", str(output_path)], check=True, timeout=10)
        elif tool == "spectacle":
            subprocess.run(["spectacle", "-b", "-n", "-o", str(output_path)], check=True, timeout=10)
        log.info("Screenshot: %s", output_path)
        return output_path
    except Exception as e:
        log.error("Erreur capture: %s", e)
        return None


def capture_window(output_path: Path | None = None) -> Path | None:
    """Capture la fenêtre active."""
    tool = _find_tool()
    if not tool:
        return None

    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path.home() / "jarvis" / "data" / "screenshots" / f"window_{ts}.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if tool == "grim":
            # Wayland: besoin de slurp pour sélectionner
            subprocess.run(["grim", "-g", "$(slurp)", str(output_path)], check=True, timeout=15, shell=True)
        elif tool == "scrot":
            subprocess.run(["scrot", "-u", str(output_path)], check=True, timeout=10)
        elif tool == "gnome-screenshot":
            subprocess.run(["gnome-screenshot", "-w", "-f", str(output_path)], check=True, timeout=10)
        return output_path
    except Exception as e:
        log.error("Erreur capture fenêtre: %s", e)
        return None
