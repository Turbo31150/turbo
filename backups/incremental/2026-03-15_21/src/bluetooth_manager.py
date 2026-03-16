"""Bluetooth Manager — Windows Bluetooth device management.

List paired/nearby devices, status, connection info.
Uses PowerShell Get-PnpDevice (no external deps).
Designed for JARVIS autonomous peripheral management.
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
    "BluetoothDevice",
    "BluetoothEvent",
    "BluetoothManager",
]

logger = logging.getLogger("jarvis.bluetooth_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class BluetoothDevice:
    """A Bluetooth device."""
    name: str
    device_id: str = ""
    status: str = ""
    device_class: str = ""
    manufacturer: str = ""


@dataclass
class BluetoothEvent:
    """Record of a Bluetooth action."""
    action: str
    device_name: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class BluetoothManager:
    """Windows Bluetooth device management."""

    def __init__(self) -> None:
        self._events: list[BluetoothEvent] = []
        self._lock = threading.Lock()

    # ── Device Listing ─────────────────────────────────────────────────

    def list_devices(self) -> list[dict[str, Any]]:
        """List all Bluetooth devices."""
        try:
            result = subprocess.run(
                ["bash", "-Command",
                 "Get-PnpDevice -Class Bluetooth | "
                 "Select-Object FriendlyName, InstanceId, Status, Class, Manufacturer | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                devices = []
                for d in data:
                    devices.append({
                        "name": d.get("FriendlyName", "Unknown"),
                        "device_id": d.get("InstanceId", ""),
                        "status": d.get("Status", ""),
                        "class": d.get("Class", ""),
                        "manufacturer": d.get("Manufacturer", ""),
                    })
                self._record("list_devices", "", True, f"{len(devices)} devices")
                return devices
        except Exception as e:
            self._record("list_devices", "", False, str(e))
        return []

    def get_device(self, name_contains: str) -> list[dict[str, Any]]:
        """Search Bluetooth devices by name."""
        q = name_contains.lower()
        return [d for d in self.list_devices() if q in d.get("name", "").lower()]

    def get_status(self) -> dict[str, Any]:
        """Check if Bluetooth adapter is available."""
        try:
            result = subprocess.run(
                ["bash", "-Command",
                 "Get-PnpDevice -Class Bluetooth | Where-Object {"
                 "$_.FriendlyName -like '*Bluetooth*'} | Select-Object Status | "
                 "ConvertTo-Json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                statuses = [d.get("Status", "") for d in data]
                enabled = any(s == "OK" for s in statuses)
                return {"available": True, "enabled": enabled, "adapters": len(data)}
        except Exception:
            pass
        return {"available": False, "enabled": False, "adapters": 0}

    def count_by_status(self) -> dict[str, int]:
        """Count devices by status."""
        devices = self.list_devices()
        counts: dict[str, int] = {}
        for d in devices:
            s = d.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, device_name: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(BluetoothEvent(
                action=action, device_name=device_name, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "device_name": e.device_name,
                 "timestamp": e.timestamp, "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
bluetooth_manager = BluetoothManager()
