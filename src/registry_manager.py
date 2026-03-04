"""Registry Manager — Windows Registry read/write operations.

Read, write, delete, search registry keys and values.
Favorites, history, export. Uses winreg stdlib.
Designed for JARVIS autonomous Windows configuration.
"""

from __future__ import annotations

import logging
import threading
import time
import winreg
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.registry_manager")

# Hive name mapping
HIVES = {
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKCR": winreg.HKEY_CLASSES_ROOT,
    "HKU": winreg.HKEY_USERS,
    "HKCC": winreg.HKEY_CURRENT_CONFIG,
}

TYPE_MAP = {
    winreg.REG_SZ: "REG_SZ",
    winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
    winreg.REG_DWORD: "REG_DWORD",
    winreg.REG_QWORD: "REG_QWORD",
    winreg.REG_BINARY: "REG_BINARY",
    winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
}


@dataclass
class RegistryEvent:
    """Record of a registry action."""
    action: str
    hive: str
    path: str
    value_name: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


@dataclass
class RegistryFavorite:
    """A bookmarked registry path."""
    name: str
    hive: str
    path: str
    description: str = ""
    created_at: float = field(default_factory=time.time)


class RegistryManager:
    """Windows Registry management with favorites and history."""

    def __init__(self) -> None:
        self._events: list[RegistryEvent] = []
        self._favorites: dict[str, RegistryFavorite] = {}
        self._lock = threading.Lock()

    # ── Read ──────────────────────────────────────────────────────────

    def read_value(self, hive: str, path: str, name: str) -> dict[str, Any]:
        """Read a single registry value."""
        hkey = HIVES.get(hive.upper())
        if not hkey:
            return {"error": f"Unknown hive: {hive}"}
        try:
            with winreg.OpenKey(hkey, path) as key:
                value, reg_type = winreg.QueryValueEx(key, name)
                self._record("read", hive, path, name, True)
                return {
                    "value": value if not isinstance(value, bytes) else value.hex(),
                    "type": TYPE_MAP.get(reg_type, str(reg_type)),
                    "name": name,
                }
        except FileNotFoundError:
            self._record("read", hive, path, name, False, "not found")
            return {"error": "Key or value not found"}
        except PermissionError:
            self._record("read", hive, path, name, False, "permission denied")
            return {"error": "Permission denied"}
        except Exception as e:
            self._record("read", hive, path, name, False, str(e))
            return {"error": str(e)}

    def list_values(self, hive: str, path: str) -> list[dict[str, Any]]:
        """List all values under a registry key."""
        hkey = HIVES.get(hive.upper())
        if not hkey:
            return []
        try:
            values = []
            with winreg.OpenKey(hkey, path) as key:
                i = 0
                while True:
                    try:
                        name, data, reg_type = winreg.EnumValue(key, i)
                        values.append({
                            "name": name,
                            "value": data if not isinstance(data, bytes) else data.hex(),
                            "type": TYPE_MAP.get(reg_type, str(reg_type)),
                        })
                        i += 1
                    except OSError:
                        break
            self._record("list_values", hive, path, "", True, f"{len(values)} values")
            return values
        except Exception as e:
            self._record("list_values", hive, path, "", False, str(e))
            return []

    def list_subkeys(self, hive: str, path: str) -> list[str]:
        """List subkey names under a registry key."""
        hkey = HIVES.get(hive.upper())
        if not hkey:
            return []
        try:
            subkeys = []
            with winreg.OpenKey(hkey, path) as key:
                i = 0
                while True:
                    try:
                        subkeys.append(winreg.EnumKey(key, i))
                        i += 1
                    except OSError:
                        break
            self._record("list_subkeys", hive, path, "", True, f"{len(subkeys)} subkeys")
            return subkeys
        except Exception as e:
            self._record("list_subkeys", hive, path, "", False, str(e))
            return []

    # ── Write ─────────────────────────────────────────────────────────

    def write_value(self, hive: str, path: str, name: str, value: Any,
                    reg_type: int = winreg.REG_SZ) -> bool:
        """Write a registry value."""
        hkey = HIVES.get(hive.upper())
        if not hkey:
            return False
        try:
            with winreg.CreateKeyEx(hkey, path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, name, 0, reg_type, value)
            self._record("write", hive, path, name, True)
            return True
        except Exception as e:
            self._record("write", hive, path, name, False, str(e))
            return False

    def delete_value(self, hive: str, path: str, name: str) -> bool:
        """Delete a registry value."""
        hkey = HIVES.get(hive.upper())
        if not hkey:
            return False
        try:
            with winreg.OpenKey(hkey, path, 0, winreg.KEY_WRITE) as key:
                winreg.DeleteValue(key, name)
            self._record("delete_value", hive, path, name, True)
            return True
        except Exception as e:
            self._record("delete_value", hive, path, name, False, str(e))
            return False

    # ── Favorites ─────────────────────────────────────────────────────

    def add_favorite(self, name: str, hive: str, path: str, description: str = "") -> RegistryFavorite:
        """Bookmark a registry path."""
        fav = RegistryFavorite(name=name, hive=hive, path=path, description=description)
        with self._lock:
            self._favorites[name] = fav
        return fav

    def remove_favorite(self, name: str) -> bool:
        with self._lock:
            if name in self._favorites:
                del self._favorites[name]
                return True
            return False

    def list_favorites(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": f.name, "hive": f.hive, "path": f.path,
                 "description": f.description, "created_at": f.created_at}
                for f in self._favorites.values()
            ]

    # ── Search ────────────────────────────────────────────────────────

    def search_values(self, hive: str, path: str, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        """Search value names under a key (non-recursive, name match)."""
        q = query.lower()
        results = []
        for v in self.list_values(hive, path):
            if q in v["name"].lower() or q in str(v["value"]).lower():
                results.append(v)
                if len(results) >= max_results:
                    break
        return results

    # ── Export ─────────────────────────────────────────────────────────

    def export_key(self, hive: str, path: str) -> dict[str, Any]:
        """Export a key and its values as a dict."""
        values = self.list_values(hive, path)
        subkeys = self.list_subkeys(hive, path)
        return {
            "hive": hive, "path": path,
            "values": values, "subkeys": subkeys,
            "exported_at": time.time(),
        }

    # ── Query ─────────────────────────────────────────────────────────

    def _record(self, action: str, hive: str, path: str, name: str,
                success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(RegistryEvent(
                action=action, hive=hive, path=path,
                value_name=name, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "hive": e.hive, "path": e.path,
                 "value_name": e.value_name, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
                "total_favorites": len(self._favorites),
                "supported_hives": list(HIVES.keys()),
            }


# ── Singleton ───────────────────────────────────────────────────────
registry_manager = RegistryManager()
