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
        """Get virtual memory status via psutil."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            status = {
                "total_visible_mb": mem.total // (1024**2),
                "free_physical_mb": mem.available // (1024**2),
                "total_virtual_mb": (mem.total + swap.total) // (1024**2),
                "free_virtual_mb": (mem.available + swap.free) // (1024**2),
                "pagefile_size_mb": swap.total // (1024**2),
                "pagefile_free_mb": swap.free // (1024**2),
                "used_percent": mem.percent
            }
            self._record("get_status", True)
            return status
        except Exception as e:
            self._record("get_status", False, str(e))
        return {"total_visible_mb": 0, "free_physical_mb": 0, "used_percent": 0}

    def get_top_consumers(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get top memory consuming processes via psutil."""
        try:
            import psutil
            procs = []
            for p in sorted(psutil.process_iter(['name', 'pid', 'memory_info']), key=lambda x: x.info['memory_info'].rss, reverse=True)[:limit]:
                procs.append({
                    "Name": p.info['name'],
                    "Id": p.info['pid'],
                    "WorkingSetMB": round(p.info['memory_info'].rss / (1024**2), 1),
                    "VirtualMB": round(p.info['memory_info'].vms / (1024**2), 1)
                })
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
