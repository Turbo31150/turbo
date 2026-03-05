"""Disk Health — Windows disk health and SMART monitoring.

Physical disk health, reliability counters, media type.
Uses PowerShell Get-PhysicalDisk + StorageReliabilityCounter (no external deps).
Designed for JARVIS autonomous storage health monitoring.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.disk_health")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class DiskInfo:
    """Physical disk information."""
    friendly_name: str
    media_type: str = ""
    health_status: str = ""
    size_gb: float = 0.0


@dataclass
class DiskHealthEvent:
    """Record of a disk health action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class DiskHealthMonitor:
    """Windows disk health monitoring."""

    def __init__(self) -> None:
        self._events: list[DiskHealthEvent] = []
        self._lock = threading.Lock()

    # ── Physical Disks ────────────────────────────────────────────────────

    def list_disks(self) -> list[dict[str, Any]]:
        """List physical disks with health status."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-PhysicalDisk | Select-Object FriendlyName, MediaType, "
                 "HealthStatus, OperationalStatus, Size, BusType | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, timeout=15,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                disks = []
                for d in data:
                    size = d.get("Size", 0) or 0
                    disks.append({
                        "friendly_name": d.get("FriendlyName", ""),
                        "media_type": str(d.get("MediaType", "")),
                        "health_status": d.get("HealthStatus", ""),
                        "operational_status": d.get("OperationalStatus", ""),
                        "size_gb": round(size / (1024**3), 2) if size > 0 else 0,
                        "bus_type": str(d.get("BusType", "")),
                    })
                self._record("list_disks", True, f"{len(disks)} disks")
                return disks
        except Exception as e:
            self._record("list_disks", False, str(e))
        return []

    def get_reliability(self) -> list[dict[str, Any]]:
        """Get storage reliability counters (SMART-like data)."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-PhysicalDisk | Get-StorageReliabilityCounter | "
                 "Select-Object DeviceId, Temperature, Wear, "
                 "ReadErrorsTotal, WriteErrorsTotal, PowerOnHours | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, timeout=15,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                counters = []
                for c in data:
                    counters.append({
                        "device_id": c.get("DeviceId", ""),
                        "temperature": c.get("Temperature", 0) or 0,
                        "wear": c.get("Wear", 0) or 0,
                        "read_errors": c.get("ReadErrorsTotal", 0) or 0,
                        "write_errors": c.get("WriteErrorsTotal", 0) or 0,
                        "power_on_hours": c.get("PowerOnHours", 0) or 0,
                    })
                self._record("get_reliability", True, f"{len(counters)} counters")
                return counters
        except Exception as e:
            self._record("get_reliability", False, str(e))
        return []

    def get_health_summary(self) -> dict[str, Any]:
        """Quick health summary of all disks."""
        disks = self.list_disks()
        healthy = sum(1 for d in disks if d.get("health_status") == "Healthy")
        return {
            "total_disks": len(disks),
            "healthy": healthy,
            "unhealthy": len(disks) - healthy,
            "all_healthy": healthy == len(disks) if disks else False,
        }

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(DiskHealthEvent(
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
disk_health = DiskHealthMonitor()
