"""Virtual Memory Manager — Windows commit charge and working sets.

Monitor virtual memory via Win32_OperatingSystem and Win32_Process top consumers.
Designed for JARVIS autonomous memory management.
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
    "VMEvent",
    "VirtualMemoryInfo",
    "VirtualMemoryManager",
]

logger = logging.getLogger("jarvis.virtual_memory_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class VirtualMemoryInfo:
    """Virtual memory status."""
    total_visible_mb: int = 0
    free_physical_mb: int = 0
    total_virtual_mb: int = 0
    free_virtual_mb: int = 0
    commit_limit_mb: int = 0
    commit_total_mb: int = 0


@dataclass
class VMEvent:
    """Record of a virtual memory action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class VirtualMemoryManager:
    """Windows virtual memory monitoring (read-only)."""

    def __init__(self) -> None:
        self._events: list[VMEvent] = []
        self._lock = threading.Lock()

    def get_status(self) -> dict[str, Any]:
        """Get virtual memory status via Win32_OperatingSystem."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_OperatingSystem | "
                 "Select-Object TotalVisibleMemorySize, FreePhysicalMemory, "
                 "TotalVirtualMemorySize, FreeVirtualMemory, "
                 "SizeStoredInPagingFiles, FreeSpaceInPagingFiles | "
                 "ConvertTo-Json -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                d = json.loads(result.stdout)
                to_mb = lambda k: round((d.get(k, 0) or 0) / 1024)
                status = {
                    "total_visible_mb": to_mb("TotalVisibleMemorySize"),
                    "free_physical_mb": to_mb("FreePhysicalMemory"),
                    "total_virtual_mb": to_mb("TotalVirtualMemorySize"),
                    "free_virtual_mb": to_mb("FreeVirtualMemory"),
                    "pagefile_size_mb": to_mb("SizeStoredInPagingFiles"),
                    "pagefile_free_mb": to_mb("FreeSpaceInPagingFiles"),
                }
                total = status["total_visible_mb"]
                free = status["free_physical_mb"]
                status["used_percent"] = round((total - free) / total * 100, 1) if total > 0 else 0
                self._record("get_status", True)
                return status
        except Exception as e:
            self._record("get_status", False, str(e))
        return {"total_visible_mb": 0, "free_physical_mb": 0, "used_percent": 0}

    def get_top_consumers(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get top memory consuming processes."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"Get-Process | Sort-Object WorkingSet64 -Descending | "
                 f"Select-Object -First {limit} Name, Id, "
                 "@{N='WorkingSetMB';E={[math]::Round($_.WorkingSet64/1MB,1)}}, "
                 "@{N='VirtualMB';E={[math]::Round($_.VirtualMemorySize64/1MB,1)}} | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                procs = []
                for p in data:
                    procs.append({
                        "name": p.get("Name", ""),
                        "pid": p.get("Id", 0),
                        "working_set_mb": p.get("WorkingSetMB", 0),
                        "virtual_mb": p.get("VirtualMB", 0),
                    })
                self._record("get_top_consumers", True, f"{len(procs)} processes")
                return procs
        except Exception as e:
            self._record("get_top_consumers", False, str(e))
        return []

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(VMEvent(action=action, success=success, detail=detail))

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


virtual_memory_manager = VirtualMemoryManager()
