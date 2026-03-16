"""Gestion affichage Linux (xrandr/wlr-randr)."""
from __future__ import annotations

import logging
import subprocess
import os

log = logging.getLogger(__name__)


def _is_wayland() -> bool:
    return os.environ.get("WAYLAND_DISPLAY") is not None


def get_displays() -> list[dict]:
    """Liste les écrans connectés avec résolution."""
    displays = []
    try:
        if _is_wayland():
            result = subprocess.run(
                ["wlr-randr"], capture_output=True, text=True, timeout=5,
            )
        else:
            result = subprocess.run(
                ["xrandr", "--query"], capture_output=True, text=True, timeout=5,
            )
        current_display = None
        for line in result.stdout.splitlines():
            if " connected" in line:
                parts = line.split()
                current_display = {"name": parts[0], "connected": True, "resolutions": []}
                # Parse resolution if present
                for p in parts:
                    if "x" in p and p[0].isdigit():
                        current_display["current_resolution"] = p.split("+")[0]
                        break
                displays.append(current_display)
            elif current_display and line.startswith("   ") and "x" in line:
                res = line.strip().split()[0]
                current_display["resolutions"].append(res)
    except FileNotFoundError:
        log.warning("xrandr/wlr-randr non trouvé")
    except Exception as e:
        log.warning("Erreur display: %s", e)
    return displays


def get_brightness() -> float | None:
    """Récupère la luminosité actuelle (0.0-1.0)."""
    try:
        # Essayer brightnessctl d'abord
        result = subprocess.run(
            ["brightnessctl", "get"], capture_output=True, text=True, timeout=5,
        )
        current = int(result.stdout.strip())
        result_max = subprocess.run(
            ["brightnessctl", "max"], capture_output=True, text=True, timeout=5,
        )
        max_val = int(result_max.stdout.strip())
        return current / max_val if max_val > 0 else None
    except Exception:
        # Fallback xrandr
        try:
            result = subprocess.run(
                ["xrandr", "--verbose"], capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "Brightness:" in line:
                    return float(line.split(":")[1].strip())
        except Exception:
            pass
    return None


def set_brightness(level: float) -> bool:
    """Règle la luminosité (0.0-1.0)."""
    level = max(0.1, min(1.0, level))
    try:
        percent = int(level * 100)
        subprocess.run(
            ["brightnessctl", "set", f"{percent}%"], check=True, timeout=5,
        )
        return True
    except Exception:
        try:
            displays = get_displays()
            if displays:
                subprocess.run(
                    ["xrandr", "--output", displays[0]["name"], "--brightness", str(level)],
                    check=True, timeout=5,
                )
                return True
        except Exception as e:
            log.error("Erreur brightness: %s", e)
    return False


def get_resolution() -> str | None:
    """Résolution de l'écran principal."""
    displays = get_displays()
    if displays:
        return displays[0].get("current_resolution")
    return None
