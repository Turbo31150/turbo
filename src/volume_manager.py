"""Volume Manager — Windows volume and partition management.

List volumes, partitions, drive space, file system info.
Uses PowerShell Get-Volume / Get-Partition (no external deps).
Designed for JARVIS autonomous storage management.
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
    "VolumeEvent",
    "VolumeInfo",
    "VolumeManager",
]

logger = logging.getLogger("jarvis.volume_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class VolumeInfo:
    """A disk volume."""
    drive_letter: str
    file_system: str = ""
    size_gb: float = 0.0
    free_gb: float = 0.0


@dataclass
class VolumeEvent:
    """Record of a volume action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class VolumeManager:
    """Windows volume and partition management (read-only)."""

    def __init__(self) -> None:
        self._events: list[VolumeEvent] = []
        self._lock = threading.Lock()

    def list_volumes(self) -> list[dict[str, Any]]:
        """List all volumes."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Volume | Where-Object { $_.DriveLetter } | "
                 "Select-Object DriveLetter, FileSystemLabel, FileSystem, "
                 "DriveType, Size, SizeRemaining, HealthStatus | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                volumes = []
                for v in data:
                    size = v.get("Size", 0) or 0
                    free = v.get("SizeRemaining", 0) or 0
                    volumes.append({
                        "drive_letter": v.get("DriveLetter", ""),
                        "label": v.get("FileSystemLabel", "") or "",
                        "file_system": v.get("FileSystem", "") or "",
                        "drive_type": str(v.get("DriveType", "")),
                        "size_gb": round(size / (1024**3), 2) if size > 0 else 0,
                        "free_gb": round(free / (1024**3), 2) if free > 0 else 0,
                        "used_percent": round((1 - free / size) * 100, 1) if size > 0 else 0,
                        "health": v.get("HealthStatus", ""),
                    })
                self._record("list_volumes", True, f"{len(volumes)} volumes")
                return volumes
        except Exception as e:
            self._record("list_volumes", False, str(e))
        return []

    def list_partitions(self) -> list[dict[str, Any]]:
        """List disk partitions."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Partition | Select-Object DiskNumber, PartitionNumber, "
                 "DriveLetter, Size, Type, IsActive | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                parts = []
                for p in data:
                    size = p.get("Size", 0) or 0
                    parts.append({
                        "disk_number": p.get("DiskNumber", 0),
                        "partition_number": p.get("PartitionNumber", 0),
                        "drive_letter": p.get("DriveLetter", "") or "",
                        "size_gb": round(size / (1024**3), 2) if size > 0 else 0,
                        "type": str(p.get("Type", "")),
                        "is_active": p.get("IsActive", False),
                    })
                return parts
        except Exception:
            pass
        return []

    def get_space_summary(self) -> dict[str, Any]:
        """Get total/free space summary."""
        volumes = self.list_volumes()
        total = sum(v.get("size_gb", 0) for v in volumes)
        free = sum(v.get("free_gb", 0) for v in volumes)
        return {
            "volume_count": len(volumes),
            "total_gb": round(total, 2),
            "free_gb": round(free, 2),
            "used_gb": round(total - free, 2),
        }

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search volumes by letter or label."""
        q = query.lower()
        return [
            v for v in self.list_volumes()
            if q in str(v.get("drive_letter", "")).lower() or q in v.get("label", "").lower()
        ]

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(VolumeEvent(action=action, success=success, detail=detail))

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


volume_manager = VolumeManager()
