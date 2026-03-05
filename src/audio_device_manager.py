"""Audio Device Manager — Windows audio devices inventory.

List audio devices via Win32_SoundDevice.
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

logger = logging.getLogger("jarvis.audio_device_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class AudioDevice:
    """An audio device."""
    name: str
    manufacturer: str = ""
    status: str = ""
    device_id: str = ""


@dataclass
class AudioEvent:
    """Record of an audio device action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class AudioDeviceManager:
    """Windows audio devices inventory (read-only)."""

    def __init__(self) -> None:
        self._events: list[AudioEvent] = []
        self._lock = threading.Lock()

    def list_devices(self) -> list[dict[str, Any]]:
        """List audio devices via Win32_SoundDevice."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_SoundDevice | "
                 "Select-Object Name, Manufacturer, Status, DeviceID | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, timeout=15,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                devices = []
                for d in data:
                    devices.append({
                        "name": d.get("Name", "") or "",
                        "manufacturer": d.get("Manufacturer", "") or "",
                        "status": d.get("Status", "") or "",
                        "device_id": d.get("DeviceID", "") or "",
                    })
                self._record("list_devices", True, f"{len(devices)} devices")
                return devices
        except Exception as e:
            self._record("list_devices", False, str(e))
        return []

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search audio devices by name or manufacturer."""
        q = query.lower()
        return [
            d for d in self.list_devices()
            if q in d.get("name", "").lower() or q in d.get("manufacturer", "").lower()
        ]

    def count_by_status(self) -> dict[str, int]:
        """Count devices by status."""
        counts: dict[str, int] = {}
        for d in self.list_devices():
            s = d.get("status", "Unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(AudioEvent(action=action, success=success, detail=detail))

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


audio_device_manager = AudioDeviceManager()
