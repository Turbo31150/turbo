"""Storage Pool Manager — Windows Storage Spaces inventory.

List storage pools and physical disks via Get-StoragePool, Get-PhysicalDisk.
Designed for JARVIS autonomous storage monitoring.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.storage_pool_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class StoragePool:
    """A storage pool entry."""
    name: str
    health_status: str = ""
    size_gb: float = 0.0
    allocated_gb: float = 0.0


@dataclass
class StorageEvent:
    """Record of a storage pool action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class StoragePoolManager:
    """Windows Storage Spaces inventory (read-only)."""

    def __init__(self) -> None:
        self._events: list[StorageEvent] = []
        self._lock = threading.Lock()

    def list_pools(self) -> list[dict[str, Any]]:
        """List storage pools."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-StoragePool -ErrorAction SilentlyContinue | "
                 "Select-Object FriendlyName, HealthStatus, OperationalStatus, "
                 "Size, AllocatedSize, IsReadOnly | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                pools = []
                for p in data:
                    size = p.get("Size", 0) or 0
                    alloc = p.get("AllocatedSize", 0) or 0
                    pools.append({
                        "name": p.get("FriendlyName", "") or "",
                        "health_status": str(p.get("HealthStatus", "")),
                        "operational_status": str(p.get("OperationalStatus", "")),
                        "size_gb": round(size / (1024**3), 2) if size > 0 else 0,
                        "allocated_gb": round(alloc / (1024**3), 2) if alloc > 0 else 0,
                        "read_only": p.get("IsReadOnly", False),
                    })
                self._record("list_pools", True, f"{len(pools)} pools")
                return pools
        except Exception as e:
            self._record("list_pools", False, str(e))
        return []

    def get_physical_disks(self) -> list[dict[str, Any]]:
        """List physical disks in storage subsystem."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-PhysicalDisk -ErrorAction SilentlyContinue | "
                 "Select-Object FriendlyName, MediaType, HealthStatus, "
                 "Size, BusType, OperationalStatus | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                disks = []
                for d in data:
                    size = d.get("Size", 0) or 0
                    disks.append({
                        "name": d.get("FriendlyName", "") or "",
                        "media_type": str(d.get("MediaType", "")),
                        "health_status": str(d.get("HealthStatus", "")),
                        "size_gb": round(size / (1024**3), 2) if size > 0 else 0,
                        "bus_type": str(d.get("BusType", "")),
                    })
                self._record("get_physical_disks", True, f"{len(disks)} disks")
                return disks
        except Exception as e:
            self._record("get_physical_disks", False, str(e))
        return []

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(StorageEvent(action=action, success=success, detail=detail))

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


storage_pool_manager = StoragePoolManager()
