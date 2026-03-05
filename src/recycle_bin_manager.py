"""Recycle Bin Manager — Windows Recycle Bin management.

Count items, total size, list recent deletions.
Uses PowerShell Shell.Application COM (no external deps).
Designed for JARVIS autonomous cleanup management.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.recycle_bin_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class RecycleBinInfo:
    """Recycle bin information."""
    item_count: int = 0
    total_size_mb: float = 0.0


@dataclass
class RecycleBinEvent:
    """Record of a recycle bin action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class RecycleBinManager:
    """Windows Recycle Bin management (read-only)."""

    def __init__(self) -> None:
        self._events: list[RecycleBinEvent] = []
        self._lock = threading.Lock()

    def get_info(self) -> dict[str, Any]:
        """Get recycle bin item count and size."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "$shell = New-Object -ComObject Shell.Application; "
                 "$rb = $shell.NameSpace(0x0a); "
                 "$items = $rb.Items(); "
                 "$count = $items.Count; "
                 "$size = 0; foreach($i in $items) { $size += $rb.GetDetailsOf($i, 3) -replace '[^0-9]',''}; "
                 "ConvertTo-Json @{count=$count; size_bytes=[long]$size}"],
                capture_output=True, text=True, timeout=15,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                size_bytes = data.get("size_bytes", 0) or 0
                self._record("get_info", True)
                return {
                    "item_count": data.get("count", 0) or 0,
                    "size_mb": round(size_bytes / (1024 * 1024), 2) if size_bytes > 0 else 0,
                }
        except Exception as e:
            self._record("get_info", False, str(e))
        # Fallback: simpler count
        return self._get_info_fallback()

    def _get_info_fallback(self) -> dict[str, Any]:
        """Fallback using simpler PowerShell."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(New-Object -ComObject Shell.Application).NameSpace(0x0a).Items().Count"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip().isdigit():
                return {"item_count": int(result.stdout.strip()), "size_mb": 0}
        except Exception:
            pass
        return {"item_count": 0, "size_mb": 0}

    def is_empty(self) -> bool:
        """Check if recycle bin is empty."""
        info = self.get_info()
        return info.get("item_count", 0) == 0

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(RecycleBinEvent(action=action, success=success, detail=detail))

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


recycle_bin_manager = RecycleBinManager()
