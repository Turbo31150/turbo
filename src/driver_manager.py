"""Driver Manager — Windows device driver management.

List installed drivers, search by name/vendor, filter by status.
Uses PowerShell Get-CimInstance Win32_PnPSignedDriver (no external deps).
Designed for JARVIS autonomous driver management.
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
    "DriverEvent",
    "DriverInfo",
    "DriverManager",
]

logger = logging.getLogger("jarvis.driver_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class DriverInfo:
    """A device driver."""
    name: str
    vendor: str = ""
    version: str = ""
    status: str = ""
    device_class: str = ""


@dataclass
class DriverEvent:
    """Record of a driver action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class DriverManager:
    """Windows device driver management."""

    def __init__(self) -> None:
        self._events: list[DriverEvent] = []
        self._lock = threading.Lock()

    # ── List Drivers ──────────────────────────────────────────────────────

    def list_drivers(self) -> list[dict[str, Any]]:
        """List installed signed drivers."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_PnPSignedDriver | "
                 "Select-Object DeviceName, Manufacturer, DriverVersion, "
                 "Status, DeviceClass | ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                drivers = []
                for d in data:
                    name = d.get("DeviceName") or ""
                    if not name:
                        continue
                    drivers.append({
                        "name": name,
                        "vendor": d.get("Manufacturer") or "",
                        "version": d.get("DriverVersion") or "",
                        "status": d.get("Status") or "",
                        "device_class": d.get("DeviceClass") or "",
                    })
                self._record("list_drivers", True, f"{len(drivers)} drivers")
                return drivers
        except Exception as e:
            self._record("list_drivers", False, str(e))
        return []

    # ── Search ────────────────────────────────────────────────────────────

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search drivers by name or vendor."""
        q = query.lower()
        return [
            d for d in self.list_drivers()
            if q in d.get("name", "").lower() or q in d.get("vendor", "").lower()
        ]

    def filter_by_class(self, device_class: str) -> list[dict[str, Any]]:
        """Filter drivers by device class."""
        c = device_class.lower()
        return [
            d for d in self.list_drivers()
            if c in d.get("device_class", "").lower()
        ]

    def count_by_status(self) -> dict[str, int]:
        """Count drivers by status."""
        counts: dict[str, int] = {}
        for d in self.list_drivers():
            s = d.get("status", "Unknown") or "Unknown"
            counts[s] = counts.get(s, 0) + 1
        return counts

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(DriverEvent(
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
driver_manager = DriverManager()
