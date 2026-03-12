"""Shadow Copy Manager — Windows Volume Shadow Copy (VSS) inventory.

List shadow copies via Win32_ShadowCopy.
Designed for JARVIS autonomous backup monitoring.
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
    "ShadowCopy",
    "ShadowCopyManager",
    "ShadowEvent",
]

logger = logging.getLogger("jarvis.shadow_copy_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class ShadowCopy:
    """A volume shadow copy entry."""
    shadow_id: str = ""
    volume_name: str = ""
    install_date: str = ""
    state: str = ""


@dataclass
class ShadowEvent:
    """Record of a shadow copy action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class ShadowCopyManager:
    """Windows Volume Shadow Copy inventory (read-only)."""

    def __init__(self) -> None:
        self._events: list[ShadowEvent] = []
        self._lock = threading.Lock()

    def list_copies(self) -> list[dict[str, Any]]:
        """List all shadow copies via Win32_ShadowCopy."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_ShadowCopy -ErrorAction SilentlyContinue | "
                 "Select-Object ID, VolumeName, InstallDate, State, DeviceObject | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                copies = []
                for c in data:
                    idate = c.get("InstallDate", "") or ""
                    if isinstance(idate, dict):
                        idate = str(idate.get("DateTime", idate.get("value", "")))
                    copies.append({
                        "shadow_id": c.get("ID", "") or "",
                        "volume_name": c.get("VolumeName", "") or "",
                        "install_date": idate,
                        "state": str(c.get("State", "")),
                        "device_object": c.get("DeviceObject", "") or "",
                    })
                self._record("list_copies", True, f"{len(copies)} copies")
                return copies
        except Exception as e:
            self._record("list_copies", False, str(e))
        return []

    def count_copies(self) -> int:
        """Count total shadow copies."""
        return len(self.list_copies())

    def get_summary(self) -> dict[str, Any]:
        """Get shadow copy summary."""
        copies = self.list_copies()
        volumes: set[str] = set()
        for c in copies:
            v = c.get("volume_name", "")
            if v:
                volumes.add(v)
        return {
            "total_copies": len(copies),
            "volumes_with_copies": len(volumes),
        }

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(ShadowEvent(action=action, success=success, detail=detail))

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


shadow_copy_manager = ShadowCopyManager()
