"""Startup Manager — Windows startup programs management.

List, add, remove, enable/disable startup entries via Registry
Run keys (HKCU and HKLM). History tracking and backup.
Designed for JARVIS autonomous boot optimization.
"""

from __future__ import annotations

import logging
import threading
import time
import winreg
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.startup_manager")

# Registry paths for startup entries
STARTUP_KEYS = {
    "user": (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    "user_once": (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    "machine": (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
}


@dataclass
class StartupEntry:
    """A startup program entry."""
    name: str
    command: str
    scope: str  # user, user_once, machine
    enabled: bool = True


@dataclass
class StartupEvent:
    """Record of a startup action."""
    action: str
    entry_name: str
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class StartupManager:
    """Windows startup programs management with history."""

    def __init__(self) -> None:
        self._events: list[StartupEvent] = []
        self._disabled: dict[str, str] = {}  # name -> original command (for re-enable)
        self._lock = threading.Lock()

    # ── List ──────────────────────────────────────────────────────────

    def list_entries(self, scope: str = "user") -> list[dict[str, Any]]:
        """List startup entries for a scope."""
        key_info = STARTUP_KEYS.get(scope)
        if not key_info:
            return []
        hive, path = key_info
        entries = []
        try:
            with winreg.OpenKey(hive, path) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        with self._lock:
                            disabled = name in self._disabled
                        entries.append({
                            "name": name, "command": str(value),
                            "scope": scope, "enabled": not disabled,
                        })
                        i += 1
                    except OSError:
                        break
        except Exception as e:
            logger.debug("list_entries error for %s: %s", scope, e)
        return entries

    def list_all(self) -> list[dict[str, Any]]:
        """List entries from all scopes."""
        result = []
        for scope in ("user", "user_once", "machine"):
            result.extend(self.list_entries(scope))
        return result

    # ── Add / Remove ──────────────────────────────────────────────────

    def add_entry(self, name: str, command: str, scope: str = "user") -> bool:
        """Add a startup entry."""
        key_info = STARTUP_KEYS.get(scope)
        if not key_info:
            self._record("add", name, False, f"Invalid scope: {scope}")
            return False
        hive, path = key_info
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
            self._record("add", name, True, f"scope={scope}")
            return True
        except PermissionError:
            self._record("add", name, False, "permission denied")
            return False
        except Exception as e:
            self._record("add", name, False, str(e))
            return False

    def remove_entry(self, name: str, scope: str = "user") -> bool:
        """Remove a startup entry."""
        key_info = STARTUP_KEYS.get(scope)
        if not key_info:
            return False
        hive, path = key_info
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_WRITE) as key:
                winreg.DeleteValue(key, name)
            self._record("remove", name, True, f"scope={scope}")
            return True
        except FileNotFoundError:
            self._record("remove", name, False, "not found")
            return False
        except PermissionError:
            self._record("remove", name, False, "permission denied")
            return False
        except Exception as e:
            self._record("remove", name, False, str(e))
            return False

    # ── Enable / Disable ──────────────────────────────────────────────

    def disable_entry(self, name: str, scope: str = "user") -> bool:
        """Disable a startup entry (removes from registry, keeps backup)."""
        entries = self.list_entries(scope)
        entry = next((e for e in entries if e["name"] == name), None)
        if not entry:
            return False
        with self._lock:
            self._disabled[name] = entry["command"]
        if self.remove_entry(name, scope):
            self._record("disable", name, True, f"scope={scope}")
            return True
        return False

    def enable_entry(self, name: str, scope: str = "user") -> bool:
        """Re-enable a disabled startup entry."""
        with self._lock:
            command = self._disabled.pop(name, None)
        if not command:
            return False
        if self.add_entry(name, command, scope):
            self._record("enable", name, True, f"scope={scope}")
            return True
        return False

    # ── Search ────────────────────────────────────────────────────────

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search startup entries by name or command."""
        q = query.lower()
        return [
            e for e in self.list_all()
            if q in e["name"].lower() or q in e["command"].lower()
        ]

    # ── Backup ────────────────────────────────────────────────────────

    def backup(self, scope: str = "user") -> list[dict[str, Any]]:
        """Backup all startup entries for a scope."""
        return self.list_entries(scope)

    def get_disabled(self) -> list[dict[str, str]]:
        """List disabled entries."""
        with self._lock:
            return [
                {"name": n, "command": c}
                for n, c in self._disabled.items()
            ]

    # ── Query ─────────────────────────────────────────────────────────

    def _record(self, action: str, entry_name: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(StartupEvent(
                action=action, entry_name=entry_name,
                success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "entry_name": e.entry_name,
                 "timestamp": e.timestamp, "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        user_count = len(self.list_entries("user"))
        with self._lock:
            return {
                "total_events": len(self._events),
                "user_entries": user_count,
                "disabled_entries": len(self._disabled),
            }


# ── Singleton ───────────────────────────────────────────────────────
startup_manager = StartupManager()
