"""Linux Update Manager — System update history and status.

Check for updates via apt, snap, flatpak. Monitor unattended-upgrades.
Designed for JARVIS autonomous update monitoring.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "LinuxUpdate",
    "UpdateEvent",
    "LinuxUpdateManager",
]

logger = logging.getLogger("jarvis.linux_update_manager")


@dataclass
class LinuxUpdate:
    """A Linux update entry."""
    title: str
    package: str = ""
    date: str = ""
    source: str = ""  # apt, snap, flatpak


@dataclass
class UpdateEvent:
    """Record of an update action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class LinuxUpdateManager:
    """Linux update history and pending updates reader."""

    def __init__(self) -> None:
        self._events: list[UpdateEvent] = []
        self._lock = threading.Lock()

    def get_update_history(self, limit: int = 30) -> list[dict[str, Any]]:
        """Get recent update history from dpkg log."""
        updates: list[dict[str, Any]] = []
        log_path = "/var/log/dpkg.log"
        try:
            if os.path.exists(log_path):
                with open(log_path, "r", errors="replace") as f:
                    lines = f.readlines()
                # Filtrer les lignes d'installation/upgrade
                for line in reversed(lines):
                    if len(updates) >= min(limit, 100):
                        break
                    line = line.strip()
                    if " install " in line or " upgrade " in line:
                        # Format: 2025-01-15 10:30:45 upgrade package:arch old-ver new-ver
                        parts = line.split()
                        if len(parts) >= 4:
                            date_str = f"{parts[0]} {parts[1]}"
                            action = parts[2]
                            package = parts[3].split(":")[0] if len(parts) > 3 else ""
                            title = f"{action}: {package}"
                            if len(parts) >= 6:
                                title += f" ({parts[4]} → {parts[5]})"
                            updates.append({
                                "title": title,
                                "date": date_str,
                                "result_code": 0,
                                "update_id": package,
                                "source": "apt",
                            })
            self._record("get_update_history", True, f"{len(updates)} updates")
        except Exception as e:
            self._record("get_update_history", False, str(e))
        return updates

    def get_pending_updates(self) -> list[dict[str, Any]]:
        """Get pending (not yet installed) updates."""
        pending: list[dict[str, Any]] = []
        # apt upgradable
        pending.extend(self._get_apt_pending())
        # snap refreshable
        pending.extend(self._get_snap_pending())
        self._record("get_pending_updates", True, f"{len(pending)} pending")
        return pending

    def _get_apt_pending(self) -> list[dict[str, Any]]:
        """Get apt upgradable packages."""
        try:
            # Rafraichir la liste (rapide si cache récent)
            subprocess.run(
                ["apt", "list", "--upgradable"],
                capture_output=True, text=True, timeout=30,
            )
            result = subprocess.run(
                ["apt", "list", "--upgradable"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                pending = []
                for line in result.stdout.strip().splitlines():
                    if "/" in line and "upgradable" in line.lower():
                        # Format: package/source version arch [upgradable from: old-version]
                        name = line.split("/")[0]
                        pending.append({
                            "title": name,
                            "is_downloaded": False,
                            "is_mandatory": False,
                            "source": "apt",
                        })
                return pending
        except Exception:
            pass
        return []

    def _get_snap_pending(self) -> list[dict[str, Any]]:
        """Get snap refreshable packages."""
        try:
            result = subprocess.run(
                ["snap", "refresh", "--list"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                pending = []
                lines = result.stdout.strip().splitlines()
                for line in lines[1:]:  # Skip header
                    parts = line.split()
                    if parts:
                        pending.append({
                            "title": parts[0],
                            "is_downloaded": False,
                            "is_mandatory": False,
                            "source": "snap",
                        })
                return pending
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return []

    def get_unattended_status(self) -> dict[str, Any]:
        """Check unattended-upgrades configuration status."""
        status: dict[str, Any] = {"installed": False, "enabled": False}
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f", "${Status}", "unattended-upgrades"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and "install ok installed" in result.stdout:
                status["installed"] = True
                # Vérifier si activé via apt config
                cfg_result = subprocess.run(
                    ["apt-config", "dump", "APT::Periodic::Unattended-Upgrade"],
                    capture_output=True, text=True, timeout=5,
                )
                if cfg_result.returncode == 0:
                    match = re.search(r'"(\d+)"', cfg_result.stdout)
                    if match and int(match.group(1)) > 0:
                        status["enabled"] = True
        except Exception:
            pass
        return status

    def search_history(self, query: str) -> list[dict[str, Any]]:
        """Search update history by title."""
        q = query.lower()
        return [u for u in self.get_update_history(100) if q in u.get("title", "").lower()]

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(UpdateEvent(action=action, success=success, detail=detail))

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


linux_update_manager = LinuxUpdateManager()
