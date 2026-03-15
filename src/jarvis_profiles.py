"""jarvis_profiles.py — Systeme de profils JARVIS OS.

Profils: travail, dev, gaming, veille, presentation.
Chaque profil configure: GPU, services, wallpaper, luminosite, son, mode.

Usage:
    from src.jarvis_profiles import switch_profile, get_current_profile
    switch_profile("dev")
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path

logger = logging.getLogger("jarvis.profiles")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROFILE_STATE = DATA_DIR / "current_profile.json"

PROFILES = {
    "travail": {
        "description": "Mode travail — productivité maximale",
        "dark_mode": True,
        "do_not_disturb": True,
        "widgets": True,
        "voice": True,
        "brightness": 80,
        "volume": 30,
        "gpu_mode": "balanced",
        "services_extra": [],
        "services_stop": [],
    },
    "dev": {
        "description": "Mode développement — terminal + code + IA",
        "dark_mode": True,
        "do_not_disturb": True,
        "widgets": True,
        "voice": True,
        "brightness": 70,
        "volume": 20,
        "gpu_mode": "performance",
        "services_extra": ["jarvis-brain"],
        "services_stop": [],
        "open_apps": ["gnome-terminal", "code"],
    },
    "gaming": {
        "description": "Mode gaming — GPUs libérées, pas de widgets",
        "dark_mode": True,
        "do_not_disturb": True,
        "widgets": False,
        "voice": False,
        "brightness": 100,
        "volume": 70,
        "gpu_mode": "performance",
        "services_extra": [],
        "services_stop": ["jarvis-brain", "jarvis-trading-sentinel", "jarvis-wallpaper"],
    },
    "veille": {
        "description": "Mode veille — économie d'énergie, monitoring minimal",
        "dark_mode": True,
        "do_not_disturb": False,
        "widgets": False,
        "voice": False,
        "brightness": 30,
        "volume": 10,
        "gpu_mode": "powersave",
        "services_extra": [],
        "services_stop": ["jarvis-brain", "jarvis-wallpaper", "jarvis-dashboard-web"],
    },
    "presentation": {
        "description": "Mode présentation — pas de notifications, luminosité max",
        "dark_mode": False,
        "do_not_disturb": True,
        "widgets": False,
        "voice": False,
        "brightness": 100,
        "volume": 50,
        "gpu_mode": "balanced",
        "services_extra": [],
        "services_stop": [],
    },
    "normal": {
        "description": "Mode normal — tout activé, paramètres par défaut",
        "dark_mode": True,
        "do_not_disturb": False,
        "widgets": True,
        "voice": True,
        "brightness": 80,
        "volume": 50,
        "gpu_mode": "balanced",
        "services_extra": [],
        "services_stop": [],
    },
}


def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))
        return r.stdout.strip()
    except Exception:
        return ""


def get_current_profile() -> str:
    """Retourne le profil actuel."""
    try:
        state = json.loads(PROFILE_STATE.read_text())
        return state.get("profile", "normal")
    except (FileNotFoundError, json.JSONDecodeError):
        return "normal"


def switch_profile(name: str) -> str:
    """Basculer vers un profil JARVIS."""
    name = name.lower().strip()
    if name not in PROFILES:
        available = ", ".join(PROFILES.keys())
        return f"Profil inconnu: {name}. Disponibles: {available}"

    profile = PROFILES[name]
    results = [f"Activation profil: {name} — {profile['description']}"]

    # Mode sombre
    scheme = "prefer-dark" if profile["dark_mode"] else "prefer-light"
    _run(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", scheme])
    results.append(f"  Mode: {'sombre' if profile['dark_mode'] else 'clair'}")

    # Ne pas déranger
    show = "false" if profile["do_not_disturb"] else "true"
    _run(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", show])
    results.append(f"  Notifications: {'off' if profile['do_not_disturb'] else 'on'}")

    # Widgets Conky
    widget_script = Path.home() / "jarvis/scripts/jarvis_widgets.sh"
    if widget_script.exists():
        action = "start" if profile["widgets"] else "stop"
        _run(["bash", str(widget_script), action])
        results.append(f"  Widgets: {'on' if profile['widgets'] else 'off'}")

    # Voice pipeline
    if profile["voice"]:
        _run(["systemctl", "--user", "start", "jarvis-voice.service"])
    else:
        _run(["systemctl", "--user", "stop", "jarvis-voice.service"])
    results.append(f"  Voice: {'on' if profile['voice'] else 'off'}")

    # Volume
    _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{profile['volume']}%"])
    results.append(f"  Volume: {profile['volume']}%")

    # Services extra à démarrer
    for svc in profile.get("services_extra", []):
        _run(["systemctl", "--user", "start", f"{svc}.service"])

    # Services à arrêter
    for svc in profile.get("services_stop", []):
        _run(["systemctl", "--user", "stop", f"{svc}.service"])
    if profile.get("services_stop"):
        results.append(f"  Arrêtés: {', '.join(profile['services_stop'])}")

    # GPU mode
    gpu_mode = profile.get("gpu_mode", "balanced")
    if gpu_mode == "performance":
        _run(["sudo", "nvidia-smi", "-pm", "1"])
        results.append("  GPU: performance")
    elif gpu_mode == "powersave":
        # Réduire la puissance GPU
        for i in range(6):
            _run(["sudo", "nvidia-smi", "-i", str(i), "-pl", "100"])
        results.append("  GPU: économie d'énergie")

    # Ouvrir les apps du profil
    for app in profile.get("open_apps", []):
        subprocess.Popen([app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    # Sauvegarder l'état
    PROFILE_STATE.write_text(json.dumps({
        "profile": name,
        "activated_at": time.time(),
    }))

    logger.info("Profil activé: %s", name)
    return "\n".join(results)


def list_profiles() -> str:
    """Liste tous les profils disponibles."""
    current = get_current_profile()
    lines = []
    for name, profile in PROFILES.items():
        marker = " ◄" if name == current else ""
        lines.append(f"  {name:15s} — {profile['description']}{marker}")
    return f"Profils JARVIS ({len(PROFILES)}):\n" + "\n".join(lines)
