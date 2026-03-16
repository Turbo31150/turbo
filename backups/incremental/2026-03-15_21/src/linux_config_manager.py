"""Linux Config Manager — Configuration management via gsettings, dconf, /etc/.

Replaces Windows Registry operations with Linux equivalents:
gsettings/dconf for GNOME, /etc/ config files, systemd unit configs.
Designed for JARVIS autonomous Linux configuration.
"""

from __future__ import annotations

import configparser
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "ConfigEvent",
    "ConfigFavorite",
    "LinuxConfigManager",
]

logger = logging.getLogger("jarvis.linux_config_manager")

# Mapping des "hives" Windows → backends Linux
CONFIG_BACKENDS = {
    "GSETTINGS": "gsettings",
    "DCONF": "dconf",
    "ETC": "/etc",
    "SYSTEMD": "systemd",
    "SYSFS": "/sys",
}


@dataclass
class ConfigEvent:
    """Record of a config action."""
    action: str
    backend: str
    path: str
    value_name: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


@dataclass
class ConfigFavorite:
    """A bookmarked config path."""
    name: str
    backend: str
    path: str
    description: str = ""
    created_at: float = field(default_factory=time.time)


class LinuxConfigManager:
    """Linux configuration management with favorites and history."""

    def __init__(self) -> None:
        self._events: list[ConfigEvent] = []
        self._favorites: dict[str, ConfigFavorite] = {}
        self._lock = threading.Lock()

    # ── Read ──────────────────────────────────────────────────────────

    def read_value(self, hive: str, path: str, name: str) -> dict[str, Any]:
        """Read a configuration value.

        Args:
            hive: Backend name (GSETTINGS, DCONF, ETC, SYSTEMD, SYSFS)
            path: Schema/path (e.g. 'org.gnome.desktop.interface' or '/etc/hostname')
            name: Key name (e.g. 'gtk-theme' or empty for file content)
        """
        backend = hive.upper()
        if backend == "GSETTINGS":
            return self._read_gsetting(path, name)
        elif backend == "DCONF":
            return self._read_dconf(path, name)
        elif backend in ("ETC", "SYSFS"):
            return self._read_file(path, name)
        elif backend == "SYSTEMD":
            return self._read_systemd(path, name)
        else:
            return {"error": f"Unknown backend: {hive}"}

    def _read_gsetting(self, schema: str, key: str) -> dict[str, Any]:
        """Read a gsettings value."""
        try:
            result = subprocess.run(
                ["gsettings", "get", schema, key],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                value = result.stdout.strip().strip("'")
                self._record("read", "GSETTINGS", schema, key, True)
                return {"value": value, "type": "gsettings", "name": key}
            self._record("read", "GSETTINGS", schema, key, False, result.stderr.strip())
            return {"error": result.stderr.strip()}
        except FileNotFoundError:
            return {"error": "gsettings not found"}
        except Exception as e:
            self._record("read", "GSETTINGS", schema, key, False, str(e))
            return {"error": str(e)}

    def _read_dconf(self, path: str, key: str) -> dict[str, Any]:
        """Read a dconf value."""
        full_path = f"{path}/{key}" if key else path
        try:
            result = subprocess.run(
                ["dconf", "read", full_path],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                self._record("read", "DCONF", path, key, True)
                return {"value": result.stdout.strip(), "type": "dconf", "name": key}
            return {"error": "Key not found or empty"}
        except FileNotFoundError:
            return {"error": "dconf not found"}
        except Exception as e:
            return {"error": str(e)}

    def _read_file(self, path: str, key: str) -> dict[str, Any]:
        """Read from a config file (INI-style or plain text)."""
        if not os.path.exists(path):
            self._record("read", "ETC", path, key, False, "not found")
            return {"error": f"File not found: {path}"}
        try:
            with open(path, "r", errors="replace") as f:
                content = f.read()
            if not key:
                self._record("read", "ETC", path, "", True)
                return {"value": content[:2000], "type": "file", "name": path}
            # Chercher la clé dans le contenu (format KEY=VALUE ou KEY: VALUE)
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == key:
                        self._record("read", "ETC", path, key, True)
                        return {"value": v.strip(), "type": "file", "name": key}
                elif ":" in line:
                    k, v = line.split(":", 1)
                    if k.strip() == key:
                        self._record("read", "ETC", path, key, True)
                        return {"value": v.strip(), "type": "file", "name": key}
            return {"error": f"Key '{key}' not found in {path}"}
        except Exception as e:
            self._record("read", "ETC", path, key, False, str(e))
            return {"error": str(e)}

    def _read_systemd(self, unit: str, key: str) -> dict[str, Any]:
        """Read a systemd unit property."""
        try:
            result = subprocess.run(
                ["systemctl", "show", unit, f"--property={key}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and "=" in result.stdout:
                value = result.stdout.strip().split("=", 1)[1]
                self._record("read", "SYSTEMD", unit, key, True)
                return {"value": value, "type": "systemd", "name": key}
            return {"error": "Property not found"}
        except Exception as e:
            return {"error": str(e)}

    def list_values(self, hive: str, path: str) -> list[dict[str, Any]]:
        """List all values under a config path."""
        backend = hive.upper()
        if backend == "GSETTINGS":
            return self._list_gsettings(path)
        elif backend == "DCONF":
            return self._list_dconf(path)
        elif backend in ("ETC", "SYSFS"):
            return self._list_file_keys(path)
        elif backend == "SYSTEMD":
            return self._list_systemd_props(path)
        return []

    def _list_gsettings(self, schema: str) -> list[dict[str, Any]]:
        """List all keys in a gsettings schema."""
        try:
            result = subprocess.run(
                ["gsettings", "list-recursively", schema],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                values = []
                for line in result.stdout.strip().splitlines():
                    parts = line.split(None, 2)
                    if len(parts) >= 3:
                        values.append({
                            "name": parts[1],
                            "value": parts[2].strip("'"),
                            "type": "gsettings",
                        })
                self._record("list_values", "GSETTINGS", schema, "", True, f"{len(values)} values")
                return values
        except Exception:
            pass
        return []

    def _list_dconf(self, path: str) -> list[dict[str, Any]]:
        """List dconf keys under a path."""
        try:
            result = subprocess.run(
                ["dconf", "list", path],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                values = []
                for key in result.stdout.strip().splitlines():
                    key = key.strip()
                    if key and not key.endswith("/"):
                        values.append({"name": key, "value": "", "type": "dconf"})
                return values
        except Exception:
            pass
        return []

    def _list_file_keys(self, path: str) -> list[dict[str, Any]]:
        """List key=value pairs from a config file."""
        values: list[dict[str, Any]] = []
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        values.append({"name": k.strip(), "value": v.strip(), "type": "file"})
        except Exception:
            pass
        return values

    def _list_systemd_props(self, unit: str) -> list[dict[str, Any]]:
        """List all systemd unit properties."""
        try:
            result = subprocess.run(
                ["systemctl", "show", unit],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                values = []
                for line in result.stdout.strip().splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        values.append({"name": k, "value": v, "type": "systemd"})
                return values
        except Exception:
            pass
        return []

    def list_subkeys(self, hive: str, path: str) -> list[str]:
        """List subkeys/subdirectories under a config path."""
        backend = hive.upper()
        if backend == "GSETTINGS":
            try:
                result = subprocess.run(
                    ["gsettings", "list-schemas"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    prefix = path + "."
                    children = set()
                    for schema in result.stdout.strip().splitlines():
                        if schema.startswith(prefix):
                            rest = schema[len(prefix):]
                            child = rest.split(".")[0]
                            children.add(child)
                    return sorted(children)
            except Exception:
                pass
        elif backend == "DCONF":
            try:
                result = subprocess.run(
                    ["dconf", "list", path],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return [k.strip("/") for k in result.stdout.strip().splitlines()
                            if k.strip().endswith("/")]
            except Exception:
                pass
        elif backend in ("ETC", "SYSFS"):
            if os.path.isdir(path):
                try:
                    return sorted(os.listdir(path))
                except Exception:
                    pass
        return []

    # ── Write ─────────────────────────────────────────────────────────

    def write_value(self, hive: str, path: str, name: str, value: Any,
                    reg_type: int = 0) -> bool:
        """Write a configuration value."""
        backend = hive.upper()
        if backend == "GSETTINGS":
            return self._write_gsetting(path, name, str(value))
        elif backend == "DCONF":
            return self._write_dconf(path, name, str(value))
        self._record("write", backend, path, name, False, "write not supported")
        return False

    def _write_gsetting(self, schema: str, key: str, value: str) -> bool:
        """Write a gsettings value."""
        try:
            result = subprocess.run(
                ["gsettings", "set", schema, key, value],
                capture_output=True, text=True, timeout=5,
            )
            success = result.returncode == 0
            self._record("write", "GSETTINGS", schema, key, success,
                         result.stderr.strip() if not success else "")
            return success
        except Exception as e:
            self._record("write", "GSETTINGS", schema, key, False, str(e))
            return False

    def _write_dconf(self, path: str, key: str, value: str) -> bool:
        """Write a dconf value."""
        full_path = f"{path}/{key}" if key else path
        try:
            result = subprocess.run(
                ["dconf", "write", full_path, value],
                capture_output=True, text=True, timeout=5,
            )
            success = result.returncode == 0
            self._record("write", "DCONF", path, key, success)
            return success
        except Exception as e:
            self._record("write", "DCONF", path, key, False, str(e))
            return False

    def delete_value(self, hive: str, path: str, name: str) -> bool:
        """Delete a configuration value."""
        backend = hive.upper()
        if backend == "GSETTINGS":
            try:
                result = subprocess.run(
                    ["gsettings", "reset", path, name],
                    capture_output=True, text=True, timeout=5,
                )
                success = result.returncode == 0
                self._record("delete_value", "GSETTINGS", path, name, success)
                return success
            except Exception as e:
                self._record("delete_value", "GSETTINGS", path, name, False, str(e))
                return False
        elif backend == "DCONF":
            full_path = f"{path}/{name}" if name else path
            try:
                result = subprocess.run(
                    ["dconf", "reset", full_path],
                    capture_output=True, text=True, timeout=5,
                )
                success = result.returncode == 0
                self._record("delete_value", "DCONF", path, name, success)
                return success
            except Exception as e:
                self._record("delete_value", "DCONF", path, name, False, str(e))
                return False
        return False

    # ── Favorites ─────────────────────────────────────────────────────

    def add_favorite(self, name: str, hive: str, path: str, description: str = "") -> ConfigFavorite:
        """Bookmark a config path."""
        fav = ConfigFavorite(name=name, backend=hive, path=path, description=description)
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
                {"name": f.name, "hive": f.backend, "path": f.path,
                 "description": f.description, "created_at": f.created_at}
                for f in self._favorites.values()
            ]

    # ── Search ────────────────────────────────────────────────────────

    def search_values(self, hive: str, path: str, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        """Search value names under a config path."""
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
        """Export a config path and its values as a dict."""
        values = self.list_values(hive, path)
        subkeys = self.list_subkeys(hive, path)
        return {
            "hive": hive, "path": path,
            "values": values, "subkeys": subkeys,
            "exported_at": time.time(),
        }

    # ── Query ─────────────────────────────────────────────────────────

    def _record(self, action: str, backend: str, path: str, name: str,
                success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(ConfigEvent(
                action=action, backend=backend, path=path,
                value_name=name, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "hive": e.backend, "path": e.path,
                 "value_name": e.value_name, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
                "total_favorites": len(self._favorites),
                "supported_hives": list(CONFIG_BACKENDS.keys()),
            }


# ── Singleton ───────────────────────────────────────────────────────
linux_config_manager = LinuxConfigManager()
