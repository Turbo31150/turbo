"""USB Device Manager — Windows USB devices inventory.

List USB devices via Win32_PnPEntity (USB class).
Designed for JARVIS autonomous hardware monitoring.
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
    "USBDevice",
    "USBDeviceManager",
    "USBEvent",
]

logger = logging.getLogger("jarvis.usb_device_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class USBDevice:
    """A USB device."""
    name: str
    device_id: str = ""
    manufacturer: str = ""
    status: str = ""
    pnp_class: str = ""


@dataclass
class USBEvent:
    """Record of a USB device action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class USBDeviceManager:
    """Windows USB devices inventory (read-only)."""

    def __init__(self) -> None:
        self._events: list[USBEvent] = []
        self._lock = threading.Lock()

    def list_devices(self) -> list[dict[str, Any]]:
        """List USB devices via Win32_PnPEntity filtered by USB DeviceID."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_PnPEntity | "
                 "Where-Object { $_.DeviceID -like 'USB*' } | "
                 "Select-Object Name, DeviceID, Manufacturer, Status, PNPClass | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                devices = []
                for d in data:
                    devices.append({
                        "name": d.get("Name", "") or "",
                        "device_id": d.get("DeviceID", "") or "",
                        "manufacturer": d.get("Manufacturer", "") or "",
                        "status": d.get("Status", "") or "",
                        "pnp_class": d.get("PNPClass", "") or "",
                    })
                self._record("list_devices", True, f"{len(devices)} devices")
                return devices
        except Exception as e:
            self._record("list_devices", False, str(e))
        return []

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search USB devices by name or manufacturer."""
        q = query.lower()
        return [
            d for d in self.list_devices()
            if q in d.get("name", "").lower() or q in d.get("manufacturer", "").lower()
        ]

    def count_by_class(self) -> dict[str, int]:
        """Count USB devices by PNP class."""
        counts: dict[str, int] = {}
        for d in self.list_devices():
            c = d.get("pnp_class", "Unknown") or "Unknown"
            counts[c] = counts.get(c, 0) + 1
        return counts

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(USBEvent(action=action, success=success, detail=detail))

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


usb_device_manager = USBDeviceManager()
