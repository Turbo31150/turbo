"""Theme Controller — Windows personalization and theme management.

Dark/light mode, accent color, wallpaper, system colors.
Uses Windows Registry Personalize key (no external deps).
Designed for JARVIS autonomous desktop personalization.
"""

from __future__ import annotations

import logging
import threading
import time
import winreg
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.theme_controller")

PERSONALIZE_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
DESKTOP_KEY = r"Control Panel\Desktop"
ACCENT_KEY = r"SOFTWARE\Microsoft\Windows\DWM"


@dataclass
class ThemeEvent:
    """Record of a theme action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class ThemeController:
    """Windows theme and personalization management."""

    def __init__(self) -> None:
        self._events: list[ThemeEvent] = []
        self._lock = threading.Lock()

    # ── Theme Reading ──────────────────────────────────────────────────

    def get_theme(self) -> dict[str, Any]:
        """Get current theme settings."""
        theme = {
            "dark_mode_apps": self._read_personalize("AppsUseLightTheme") == 0,
            "dark_mode_system": self._read_personalize("SystemUsesLightTheme") == 0,
            "transparency": self._read_personalize("EnableTransparency") == 1,
            "accent_color": self._get_accent_color(),
            "wallpaper": self._get_wallpaper(),
        }
        self._record("get_theme", True)
        return theme

    def is_dark_mode(self) -> bool:
        """Check if dark mode is enabled for apps."""
        return self._read_personalize("AppsUseLightTheme") == 0

    def _read_personalize(self, value_name: str) -> int:
        """Read a value from Personalize registry key."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY)
            try:
                val, _ = winreg.QueryValueEx(key, value_name)
                return val
            finally:
                winreg.CloseKey(key)
        except Exception:
            pass
            return -1

    def _get_accent_color(self) -> str:
        """Get Windows accent color as hex."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, ACCENT_KEY)
            try:
                val, _ = winreg.QueryValueEx(key, "AccentColor")
                # AccentColor is ABGR format DWORD
                b = (val >> 16) & 0xFF
                g = (val >> 8) & 0xFF
                r = val & 0xFF
                return f"#{r:02x}{g:02x}{b:02x}"
            finally:
                winreg.CloseKey(key)
        except Exception:
            return "#0078d4"

    def _get_wallpaper(self) -> str:
        """Get current wallpaper path."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, DESKTOP_KEY)
            try:
                val, _ = winreg.QueryValueEx(key, "Wallpaper")
                return val
            finally:
                winreg.CloseKey(key)
        except Exception:
            return ""

    def get_color_prevalence(self) -> dict[str, bool]:
        """Get color prevalence settings (accent on taskbar/title bars)."""
        return {
            "color_on_taskbar": self._read_personalize("ColorPrevalence") == 1,
            "color_on_titlebars": self._read_dwm("ColorPrevalence") == 1,
        }

    def _read_dwm(self, value_name: str) -> int:
        """Read DWM registry value."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, ACCENT_KEY)
            try:
                val, _ = winreg.QueryValueEx(key, value_name)
                return val
            finally:
                winreg.CloseKey(key)
        except Exception:
            return -1

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(ThemeEvent(
                action=action, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        theme = self.get_theme()
        with self._lock:
            return {
                "dark_mode": theme.get("dark_mode_apps", False),
                "accent_color": theme.get("accent_color", ""),
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
theme_controller = ThemeController()
