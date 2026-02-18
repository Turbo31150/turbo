"""JARVIS Systray — System tray icon with quick actions.

Provides a persistent icon in Windows system tray with:
  - Quick status check (cluster, system)
  - Launch skills (Rapport Matin, Mode Trading, etc.)
  - Open Dashboard TUI
  - Start voice/hybrid mode
  - Quit JARVIS
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import pystray

# JARVIS project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")


def _create_icon_image() -> Image.Image:
    """Create a simple JARVIS icon (orange J on dark bg)."""
    size = 64
    img = Image.new("RGBA", (size, size), (20, 20, 30, 255))
    draw = ImageDraw.Draw(img)

    # Orange circle
    draw.ellipse([4, 4, size - 4, size - 4], outline=(255, 165, 0, 255), width=3)

    # Letter "J" in center
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except OSError:
        font = ImageFont.load_default()
    draw.text((size // 2, size // 2), "J", fill=(255, 165, 0, 255), font=font, anchor="mm")

    return img


def _launch_bat(bat_name: str) -> None:
    """Launch a JARVIS .bat launcher in a new console."""
    bat_path = PROJECT_ROOT / bat_name
    if bat_path.exists():
        subprocess.Popen(
            ["cmd", "/c", "start", "", str(bat_path)],
            cwd=str(PROJECT_ROOT),
        )


def _launch_dashboard() -> None:
    """Launch the Textual TUI dashboard."""
    subprocess.Popen(
        ["cmd", "/c", "start", "", str(PROJECT_ROOT / "jarvis_dashboard.bat")],
        cwd=str(PROJECT_ROOT),
    )


def _quick_cluster_status() -> None:
    """Show cluster status in a notification."""
    import asyncio
    import httpx
    from src.config import config

    async def _check():
        results = []
        async with httpx.AsyncClient(timeout=5) as c:
            for node in config.lm_nodes:
                try:
                    r = await c.get(f"{node.url}/api/v1/models")
                    r.raise_for_status()
                    cnt = len([m for m in r.json().get("models", []) if m.get("loaded_instances")])
                    results.append(f"{node.name}: OK ({cnt} modeles)")
                except Exception:
                    results.append(f"{node.name}: OFFLINE")
        return "\n".join(results)

    try:
        loop = asyncio.new_event_loop()
        text = loop.run_until_complete(_check())
        loop.close()
        # Show via Windows notification
        from src.windows import notify_windows
        notify_windows("JARVIS Cluster", text)
    except Exception as e:
        print(f"[SYSTRAY] Erreur cluster: {e}")


def _notify_action(title: str, message: str) -> None:
    """Send a Windows notification."""
    try:
        from src.windows import notify_windows
        notify_windows(title, message)
    except Exception:
        pass


def create_systray() -> pystray.Icon:
    """Create the JARVIS system tray icon with menu."""

    def on_dashboard(icon, item):
        threading.Thread(target=_launch_dashboard, daemon=True).start()

    def on_interactive(icon, item):
        threading.Thread(target=lambda: _launch_bat("jarvis_interactive.bat"), daemon=True).start()

    def on_hybrid(icon, item):
        threading.Thread(target=lambda: _launch_bat("jarvis_hybrid.bat"), daemon=True).start()

    def on_voice(icon, item):
        threading.Thread(target=lambda: _launch_bat("jarvis_voice.bat"), daemon=True).start()

    def on_cluster(icon, item):
        threading.Thread(target=_quick_cluster_status, daemon=True).start()

    def on_rapport_matin(icon, item):
        _notify_action("JARVIS", "Lancement du rapport matin...")
        threading.Thread(target=lambda: _launch_bat("jarvis_hybrid.bat"), daemon=True).start()

    def on_quit(icon, item):
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Dashboard TUI", on_dashboard, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Mode Interactif", on_interactive),
        pystray.MenuItem("Mode Hybride", on_hybrid),
        pystray.MenuItem("Mode Vocal", on_voice),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Cluster Status", on_cluster),
        pystray.MenuItem("Rapport Matin", on_rapport_matin),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quitter JARVIS", on_quit),
    )

    icon = pystray.Icon(
        "JARVIS",
        _create_icon_image(),
        "JARVIS v10.1 — Orchestrateur IA",
        menu,
    )
    return icon


def run_systray():
    """Run the system tray icon (blocking)."""
    icon = create_systray()
    icon.run()


if __name__ == "__main__":
    run_systray()
