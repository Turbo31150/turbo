"""Locale Manager — Windows locale, language and regional settings.

System locale, display language, keyboard layouts, date/time format.
Uses PowerShell Get-WinSystemLocale + Registry (no external deps).
Designed for JARVIS autonomous localization management.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.locale_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class LocaleInfo:
    """Locale information."""
    name: str
    display_name: str = ""
    language_tag: str = ""


@dataclass
class LocaleEvent:
    """Record of a locale action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class LocaleManager:
    """Windows locale and regional settings management."""

    def __init__(self) -> None:
        self._events: list[LocaleEvent] = []
        self._lock = threading.Lock()

    # ── Locale Info ────────────────────────────────────────────────────

    def get_system_locale(self) -> dict[str, Any]:
        """Get system locale info."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WinSystemLocale | Select-Object Name, DisplayName, "
                 "LCID | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                self._record("get_system_locale", True)
                return {
                    "name": data.get("Name", ""),
                    "display_name": data.get("DisplayName", ""),
                    "lcid": data.get("LCID", 0),
                }
        except Exception as e:
            self._record("get_system_locale", False, str(e))
        return {"name": "unknown", "display_name": "Unknown", "lcid": 0}

    def get_user_language(self) -> list[dict[str, Any]]:
        """Get user preferred languages."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WinUserLanguageList | Select-Object LanguageTag, "
                 "Autonym, EnglishName | ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                return [
                    {
                        "language_tag": d.get("LanguageTag", ""),
                        "autonym": d.get("Autonym", ""),
                        "english_name": d.get("EnglishName", ""),
                    }
                    for d in data
                ]
        except Exception:
            pass
        return []

    def get_keyboard_layouts(self) -> list[dict[str, Any]]:
        """Get installed keyboard layouts."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WinUserLanguageList | ForEach-Object { $_.InputMethodTips } | "
                 "ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, str):
                    data = [data]
                return [{"layout_id": d} for d in data]
        except Exception:
            pass
        return []

    def get_timezone(self) -> dict[str, Any]:
        """Get current timezone."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-TimeZone | Select-Object Id, DisplayName, "
                 "BaseUtcOffset | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                offset = data.get("BaseUtcOffset", {})
                hours = offset.get("Hours", 0) if isinstance(offset, dict) else 0
                return {
                    "id": data.get("Id", ""),
                    "display_name": data.get("DisplayName", ""),
                    "utc_offset_hours": hours,
                }
        except Exception:
            pass
        return {"id": "unknown", "display_name": "Unknown", "utc_offset_hours": 0}

    def get_date_format(self) -> dict[str, Any]:
        """Get date/time format settings."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-Culture).DateTimeFormat | Select-Object "
                 "ShortDatePattern, LongDatePattern, ShortTimePattern, "
                 "LongTimePattern | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except Exception:
            pass
        return {}

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(LocaleEvent(
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
        locale = self.get_system_locale()
        with self._lock:
            return {
                "system_locale": locale.get("name", "unknown"),
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
locale_manager = LocaleManager()
