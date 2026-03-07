"""Screen Resolution Manager — Windows display/monitor inventory.

List monitors and resolutions via Win32_VideoController.
Designed for JARVIS autonomous display management.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.screen_resolution_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class DisplayInfo:
    """A display/monitor entry."""
    name: str
    resolution: str = ""
    refresh_rate: int = 0
    adapter_ram_mb: int = 0


@dataclass
class ScreenEvent:
    """Record of a display action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class ScreenResolutionManager:
    """Windows display/monitor inventory (read-only)."""

    def __init__(self) -> None:
        self._events: list[ScreenEvent] = []
        self._lock = threading.Lock()

    def list_displays(self) -> list[dict[str, Any]]:
        """List display adapters via Win32_VideoController."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_VideoController | "
                 "Select-Object Name, "
                 "CurrentHorizontalResolution, CurrentVerticalResolution, "
                 "CurrentRefreshRate, AdapterRAM, VideoModeDescription, Status | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                displays = []
                for d in data:
                    h = d.get("CurrentHorizontalResolution") or 0
                    v = d.get("CurrentVerticalResolution") or 0
                    ram = d.get("AdapterRAM") or 0
                    displays.append({
                        "name": d.get("Name", "") or "",
                        "resolution": f"{h}x{v}" if h and v else "",
                        "refresh_rate": d.get("CurrentRefreshRate") or 0,
                        "adapter_ram_mb": round(ram / (1024 * 1024)) if ram > 0 else 0,
                        "video_mode": d.get("VideoModeDescription", "") or "",
                        "status": d.get("Status", "") or "",
                    })
                self._record("list_displays", True, f"{len(displays)} displays")
                return displays
        except Exception as e:
            self._record("list_displays", False, str(e))
        return []

    def get_primary_resolution(self) -> str:
        """Get primary display resolution string."""
        displays = self.list_displays()
        if displays:
            return displays[0].get("resolution", "Unknown")
        return "Unknown"

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search displays by name."""
        q = query.lower()
        return [d for d in self.list_displays() if q in d.get("name", "").lower()]

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(ScreenEvent(action=action, success=success, detail=detail))

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


screen_resolution_manager = ScreenResolutionManager()
