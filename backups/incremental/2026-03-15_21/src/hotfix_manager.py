"""Hotfix Manager — Windows Update / Hotfix management.

List installed hotfixes, search by KB, filter by type.
Uses PowerShell Get-HotFix (no external deps).
Designed for JARVIS autonomous update tracking.
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
    "HotfixEvent",
    "HotfixInfo",
    "HotfixManager",
]

logger = logging.getLogger("jarvis.hotfix_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class HotfixInfo:
    """A Windows hotfix/update."""
    hotfix_id: str
    description: str = ""
    installed_on: str = ""


@dataclass
class HotfixEvent:
    """Record of a hotfix action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class HotfixManager:
    """Windows hotfix/update management (read-only)."""

    def __init__(self) -> None:
        self._events: list[HotfixEvent] = []
        self._lock = threading.Lock()

    def list_hotfixes(self) -> list[dict[str, Any]]:
        """List installed hotfixes."""
        try:
            result = subprocess.run(
                ["bash", "-Command",
                 "Get-HotFix | Select-Object HotFixID, Description, "
                 "InstalledOn, InstalledBy | ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                fixes = []
                for h in data:
                    installed = h.get("InstalledOn", "")
                    if isinstance(installed, dict):
                        installed = str(installed.get("DateTime", ""))
                    fixes.append({
                        "hotfix_id": h.get("HotFixID", ""),
                        "description": h.get("Description", "") or "",
                        "installed_on": str(installed),
                        "installed_by": h.get("InstalledBy", "") or "",
                    })
                self._record("list_hotfixes", True, f"{len(fixes)} hotfixes")
                return fixes
        except Exception as e:
            self._record("list_hotfixes", False, str(e))
        return []

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search hotfixes by KB ID or description."""
        q = query.lower()
        return [
            h for h in self.list_hotfixes()
            if q in h.get("hotfix_id", "").lower() or q in h.get("description", "").lower()
        ]

    def count_by_type(self) -> dict[str, int]:
        """Count hotfixes by description type."""
        counts: dict[str, int] = {}
        for h in self.list_hotfixes():
            t = h.get("description", "Unknown") or "Unknown"
            counts[t] = counts.get(t, 0) + 1
        return counts

    def get_latest(self, n: int = 5) -> list[dict[str, Any]]:
        """Get the N most recent hotfixes."""
        fixes = self.list_hotfixes()
        return sorted(fixes, key=lambda h: h.get("installed_on", ""), reverse=True)[:n]

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(HotfixEvent(action=action, success=success, detail=detail))

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


hotfix_manager = HotfixManager()
