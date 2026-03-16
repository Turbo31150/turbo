"""System Restore Manager — Windows restore point management.

List restore points, get details, creation dates.
Uses PowerShell Get-ComputerRestorePoint (no external deps).
Designed for JARVIS autonomous system recovery monitoring.
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
    "RestoreEvent",
    "RestorePoint",
    "SysRestoreManager",
]

logger = logging.getLogger("jarvis.sysrestore_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class RestorePoint:
    """A system restore point."""
    sequence: int
    description: str = ""
    event_type: str = ""
    creation_time: str = ""


@dataclass
class RestoreEvent:
    """Record of a restore action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class SysRestoreManager:
    """Windows System Restore point management."""

    def __init__(self) -> None:
        self._events: list[RestoreEvent] = []
        self._lock = threading.Lock()

    # ── Restore Points ─────────────────────────────────────────────────

    def list_points(self) -> list[dict[str, Any]]:
        """List all system restore points."""
        try:
            result = subprocess.run(
                ["bash", "-Command",
                 "Get-ComputerRestorePoint | "
                 "Select-Object SequenceNumber, Description, RestorePointType, CreationTime | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                points = []
                for p in data:
                    rp_type = p.get("RestorePointType", 0)
                    type_name = {0: "APPLICATION_INSTALL", 1: "APPLICATION_UNINSTALL",
                                 10: "DEVICE_DRIVER_INSTALL", 12: "MODIFY_SETTINGS",
                                 13: "CANCELLED_OPERATION"}.get(rp_type, str(rp_type))
                    points.append({
                        "sequence": p.get("SequenceNumber", 0),
                        "description": p.get("Description", ""),
                        "type": type_name,
                        "creation_time": str(p.get("CreationTime", "")),
                    })
                self._record("list_points", True, f"{len(points)} points")
                return points
        except Exception as e:
            self._record("list_points", False, str(e))
        return []

    def get_latest(self) -> dict[str, Any] | None:
        """Get the most recent restore point."""
        points = self.list_points()
        return points[-1] if points else None

    def count_points(self) -> int:
        """Count total restore points."""
        return len(self.list_points())

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search restore points by description."""
        q = query.lower()
        return [p for p in self.list_points() if q in p.get("description", "").lower()]

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(RestoreEvent(
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
sysrestore_manager = SysRestoreManager()
