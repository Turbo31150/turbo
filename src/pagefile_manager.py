"""Pagefile Manager — Windows virtual memory / pagefile management.

Pagefile size, location, usage statistics.
Uses PowerShell Get-CimInstance Win32_PageFileUsage (no external deps).
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
    "PagefileEvent",
    "PagefileInfo",
    "PagefileManager",
]

logger = logging.getLogger("jarvis.pagefile_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class PagefileInfo:
    """Pagefile information."""
    name: str
    allocated_mb: int = 0
    current_usage_mb: int = 0
    peak_usage_mb: int = 0


@dataclass
class PagefileEvent:
    """Record of a pagefile action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class PagefileManager:
    """Windows pagefile management."""

    def __init__(self) -> None:
        self._events: list[PagefileEvent] = []
        self._lock = threading.Lock()

    # ── Pagefile Info ─────────────────────────────────────────────────────

    def get_usage(self) -> list[dict[str, Any]]:
        """Get current pagefile usage."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_PageFileUsage | "
                 "Select-Object Name, AllocatedBaseSize, CurrentUsage, "
                 "PeakUsage | ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                pages = []
                for p in data:
                    pages.append({
                        "name": p.get("Name", ""),
                        "allocated_mb": p.get("AllocatedBaseSize", 0) or 0,
                        "current_usage_mb": p.get("CurrentUsage", 0) or 0,
                        "peak_usage_mb": p.get("PeakUsage", 0) or 0,
                    })
                self._record("get_usage", True, f"{len(pages)} pagefiles")
                return pages
        except Exception as e:
            self._record("get_usage", False, str(e))
        return []

    def get_settings(self) -> list[dict[str, Any]]:
        """Get pagefile settings (initial/max size)."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_PageFileSetting | "
                 "Select-Object Name, InitialSize, MaximumSize | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                return [
                    {
                        "name": s.get("Name", ""),
                        "initial_size_mb": s.get("InitialSize", 0) or 0,
                        "max_size_mb": s.get("MaximumSize", 0) or 0,
                    }
                    for s in data
                ]
        except Exception:
            pass
        return []

    def get_virtual_memory(self) -> dict[str, Any]:
        """Get OS virtual memory stats."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_OperatingSystem | "
                 "Select-Object TotalVirtualMemorySize, FreeVirtualMemory, "
                 "TotalVisibleMemorySize, FreePhysicalMemory | "
                 "ConvertTo-Json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                return {
                    "total_virtual_kb": data.get("TotalVirtualMemorySize", 0) or 0,
                    "free_virtual_kb": data.get("FreeVirtualMemory", 0) or 0,
                    "total_physical_kb": data.get("TotalVisibleMemorySize", 0) or 0,
                    "free_physical_kb": data.get("FreePhysicalMemory", 0) or 0,
                }
        except Exception:
            pass
        return {}

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(PagefileEvent(
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
pagefile_manager = PagefileManager()
