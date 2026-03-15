"""Linux Package Manager — Package management via apt, snap, flatpak.

List, search, filter installed packages across multiple package managers.
Designed for JARVIS autonomous package discovery.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "LinuxPackage",
    "PackageEvent",
    "LinuxPackageManager",
]

logger = logging.getLogger("jarvis.linux_package_manager")


@dataclass
class LinuxPackage:
    """A Linux package entry."""
    name: str
    state: str = ""
    source: str = ""  # apt, snap, flatpak


@dataclass
class PackageEvent:
    """Record of a package action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class LinuxPackageManager:
    """Linux package management (read-only, multi-backend)."""

    def __init__(self) -> None:
        self._events: list[PackageEvent] = []
        self._lock = threading.Lock()

    # ── Packages ──────────────────────────────────────────────────────────

    def list_features(self) -> list[dict[str, Any]]:
        """List all installed packages across apt, snap, flatpak."""
        packages: list[dict[str, Any]] = []
        packages.extend(self._list_apt())
        packages.extend(self._list_snap())
        packages.extend(self._list_flatpak())
        self._record("list_features", True, f"{len(packages)} packages")
        return packages

    def _list_apt(self) -> list[dict[str, Any]]:
        """List apt installed packages."""
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f", "${Package}\t${Status}\n"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                packages = []
                for line in result.stdout.strip().splitlines():
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        status = parts[1].strip()
                        state = "Enabled" if "install ok installed" in status else "Disabled"
                        packages.append({
                            "name": name,
                            "state": state,
                            "source": "apt",
                        })
                return packages
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug("apt list error: %s", e)
        return []

    def _list_snap(self) -> list[dict[str, Any]]:
        """List snap installed packages."""
        try:
            result = subprocess.run(
                ["snap", "list"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                packages = []
                lines = result.stdout.strip().splitlines()
                for line in lines[1:]:  # Skip header
                    parts = line.split()
                    if parts:
                        packages.append({
                            "name": parts[0],
                            "state": "Enabled",
                            "source": "snap",
                        })
                return packages
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug("snap list error: %s", e)
        return []

    def _list_flatpak(self) -> list[dict[str, Any]]:
        """List flatpak installed packages."""
        try:
            result = subprocess.run(
                ["flatpak", "list", "--columns=application"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                packages = []
                for line in result.stdout.strip().splitlines():
                    name = line.strip()
                    if name:
                        packages.append({
                            "name": name,
                            "state": "Enabled",
                            "source": "flatpak",
                        })
                return packages
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug("flatpak list error: %s", e)
        return []

    def list_enabled(self) -> list[dict[str, Any]]:
        """List enabled (installed) packages only."""
        return [f for f in self.list_features() if f.get("state") == "Enabled"]

    def list_disabled(self) -> list[dict[str, Any]]:
        """List disabled (partially installed/removed) packages only."""
        return [f for f in self.list_features() if f.get("state") != "Enabled"]

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search packages by name."""
        q = query.lower()
        return [f for f in self.list_features() if q in f.get("name", "").lower()]

    def is_enabled(self, feature_name: str) -> bool:
        """Check if a specific package is installed."""
        fn = feature_name.lower()
        for f in self.list_features():
            if f.get("name", "").lower() == fn:
                return f.get("state") == "Enabled"
        return False

    def count_by_state(self) -> dict[str, int]:
        """Count packages by state."""
        counts: dict[str, int] = {}
        for f in self.list_features():
            s = f.get("state", "Unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    def count_by_source(self) -> dict[str, int]:
        """Count packages by source (apt, snap, flatpak)."""
        counts: dict[str, int] = {}
        for f in self.list_features():
            s = f.get("source", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(PackageEvent(
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
        with self._lock:
            return {
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
linux_package_manager = LinuxPackageManager()
