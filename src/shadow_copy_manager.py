"""Shadow Copy Manager — Volume Shadow Copy management.

Lists shadow copies, count, summary, events tracking.
Uses subprocess for VSS queries.
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ShadowCopy", "ShadowEvent", "ShadowCopyManager", "shadow_copy_manager"]

logger = logging.getLogger("jarvis.shadow_copy_manager")


@dataclass
class ShadowCopy:
    """A volume shadow copy."""
    shadow_id: str = ""
    volume_name: str = ""
    install_date: str = ""
    state: str = ""
    device_object: str = ""


@dataclass
class ShadowEvent:
    """A shadow copy event."""
    action: str = ""
    success: bool = True
    detail: str = ""
    timestamp: float = field(default_factory=time.time)


class ShadowCopyManager:
    """Volume Shadow Copy management."""

    def __init__(self) -> None:
        self._events: list[ShadowEvent] = []

    def list_copies(self) -> list[dict[str, Any]]:
        """List shadow copies via subprocess."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_ShadowCopy | Select-Object ID,VolumeName,InstallDate,State,DeviceObject | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return []
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            copies = []
            for item in data:
                install_date = item.get("InstallDate", "")
                if isinstance(install_date, dict):
                    install_date = install_date.get("DateTime", str(install_date))
                copies.append({
                    "shadow_id": item.get("ID", ""),
                    "volume_name": item.get("VolumeName", ""),
                    "install_date": str(install_date),
                    "state": str(item.get("State", "")),
                    "device_object": item.get("DeviceObject", ""),
                })
            self._events.append(ShadowEvent(action="list_copies", detail=f"{len(copies)} copies"))
            return copies
        except Exception as e:
            logger.warning("list_copies failed: %s", e)
            self._events.append(ShadowEvent(action="list_copies", success=False, detail=str(e)))
            return []

    def count_copies(self) -> int:
        """Count total shadow copies."""
        return len(self.list_copies())

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of shadow copies."""
        copies = self.list_copies()
        volumes = set(c.get("volume_name", "") for c in copies)
        return {
            "total_copies": len(copies),
            "volumes_with_copies": len(volumes),
        }

    def get_events(self) -> list[dict[str, Any]]:
        """Get events."""
        return [{"action": e.action, "success": e.success, "detail": e.detail}
                for e in self._events]

    def get_stats(self) -> dict[str, Any]:
        """Get stats."""
        return {"total_events": len(self._events)}


shadow_copy_manager = ShadowCopyManager()
