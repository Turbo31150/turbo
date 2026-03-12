"""Virtual Desktop — Windows virtual desktop management.

Count desktops, get current desktop info, window-to-desktop mapping.
Uses ctypes user32 and Registry (no external deps).
Designed for JARVIS autonomous workspace management.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "DesktopEvent",
    "DesktopInfo",
    "VirtualDesktopManager",
]

logger = logging.getLogger("jarvis.virtual_desktop")

user32 = ctypes.windll.user32
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class DesktopInfo:
    """A virtual desktop."""
    index: int
    name: str = ""
    is_current: bool = False


@dataclass
class DesktopEvent:
    """Record of a desktop action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class VirtualDesktopManager:
    """Windows virtual desktop management."""

    def __init__(self) -> None:
        self._events: list[DesktopEvent] = []
        self._lock = threading.Lock()

    # ── Desktop Info ───────────────────────────────────────────────────

    def get_desktop_count(self) -> int:
        """Get number of virtual desktops via PowerShell."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance -Namespace ROOT/Microsoft/Windows/DesktopManager "
                 "-ClassName MSFT_VirtualDesktop | Measure-Object).Count"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                count = int(result.stdout.strip())
                self._record("get_desktop_count", True, str(count))
                return count
        except Exception as e:
            self._record("get_desktop_count", False, str(e))
        # Fallback: at least 1
        return 1

    def list_desktops(self) -> list[dict[str, Any]]:
        """List virtual desktops."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance -Namespace ROOT/Microsoft/Windows/DesktopManager "
                 "-ClassName MSFT_VirtualDesktop | "
                 "Select-Object Id, Name, IsCurrentDesktop | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                desktops = []
                for i, d in enumerate(data):
                    desktops.append({
                        "index": i,
                        "id": d.get("Id", ""),
                        "name": d.get("Name", f"Desktop {i + 1}"),
                        "is_current": bool(d.get("IsCurrentDesktop", False)),
                    })
                self._record("list_desktops", True, f"{len(desktops)} desktops")
                return desktops
        except Exception as e:
            self._record("list_desktops", False, str(e))
        return [{"index": 0, "name": "Desktop 1", "is_current": True}]

    def get_current_desktop(self) -> dict[str, Any]:
        """Get current active desktop."""
        for d in self.list_desktops():
            if d.get("is_current"):
                return d
        return {"index": 0, "name": "Desktop 1", "is_current": True}

    def get_screen_info(self) -> dict[str, Any]:
        """Get screen metrics for current desktop."""
        return {
            "width": user32.GetSystemMetrics(0),
            "height": user32.GetSystemMetrics(1),
            "virtual_width": user32.GetSystemMetrics(78),
            "virtual_height": user32.GetSystemMetrics(79),
            "monitors": user32.GetSystemMetrics(80),
        }

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(DesktopEvent(
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
virtual_desktop = VirtualDesktopManager()
