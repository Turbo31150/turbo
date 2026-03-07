"""Installed Apps Manager — Windows installed applications.

List Win32 apps (Registry Uninstall) and UWP apps (Get-AppxPackage).
Uses PowerShell Registry + Get-AppxPackage (no external deps).
Designed for JARVIS autonomous software inventory.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "AppEvent",
    "InstalledApp",
    "InstalledAppsManager",
]

logger = logging.getLogger("jarvis.installed_apps_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class InstalledApp:
    """An installed application."""
    name: str
    version: str = ""
    publisher: str = ""
    app_type: str = ""  # "Win32" or "UWP"


@dataclass
class AppEvent:
    """Record of an app manager action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class InstalledAppsManager:
    """Windows installed applications inventory (read-only)."""

    def __init__(self) -> None:
        self._events: list[AppEvent] = []
        self._lock = threading.Lock()

    def list_win32_apps(self) -> list[dict[str, Any]]:
        """List Win32 installed apps from Registry."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-ItemProperty "
                 "'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*', "
                 "'HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' "
                 "-ErrorAction SilentlyContinue | "
                 "Where-Object { $_.DisplayName } | "
                 "Select-Object DisplayName, DisplayVersion, Publisher, InstallDate | "
                 "Sort-Object DisplayName | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                apps = []
                for a in data:
                    apps.append({
                        "name": a.get("DisplayName", ""),
                        "version": a.get("DisplayVersion", "") or "",
                        "publisher": a.get("Publisher", "") or "",
                        "install_date": a.get("InstallDate", "") or "",
                        "type": "Win32",
                    })
                self._record("list_win32_apps", True, f"{len(apps)} apps")
                return apps
        except Exception as e:
            self._record("list_win32_apps", False, str(e))
        return []

    def list_uwp_apps(self) -> list[dict[str, Any]]:
        """List UWP/Store apps."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-AppxPackage | Select-Object Name, Version, Publisher | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                apps = []
                for a in data:
                    apps.append({
                        "name": a.get("Name", ""),
                        "version": a.get("Version", "") or "",
                        "publisher": a.get("Publisher", "") or "",
                        "type": "UWP",
                    })
                self._record("list_uwp_apps", True, f"{len(apps)} apps")
                return apps
        except Exception as e:
            self._record("list_uwp_apps", False, str(e))
        return []

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search apps by name across Win32 and UWP."""
        q = query.lower()
        results = []
        for app in self.list_win32_apps():
            if q in app.get("name", "").lower():
                results.append(app)
        for app in self.list_uwp_apps():
            if q in app.get("name", "").lower():
                results.append(app)
        return results

    def count_by_type(self) -> dict[str, int]:
        """Count apps by type."""
        return {
            "Win32": len(self.list_win32_apps()),
            "UWP": len(self.list_uwp_apps()),
        }

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(AppEvent(action=action, success=success, detail=detail))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {"total_events": len(self._events)}


installed_apps_manager = InstalledAppsManager()
