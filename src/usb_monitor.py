"""USB Monitor — Windows USB device detection and management.

List USB devices, detect connect/disconnect, safe eject, history.
Uses subprocess with wmic/pnputil (no external dependencies).
Designed for JARVIS autonomous peripheral management.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "USBDevice",
    "USBEvent",
    "USBMonitor",
]

logger = logging.getLogger("jarvis.usb_monitor")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class USBDevice:
    """A detected USB device."""
    name: str
    device_id: str = ""
    status: str = ""
    device_type: str = ""
    manufacturer: str = ""


@dataclass
class USBEvent:
    """Record of a USB action."""
    action: str
    device_name: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class USBMonitor:
    """USB device monitoring with history."""

    def __init__(self) -> None:
        self._events: list[USBEvent] = []
        self._known_devices: dict[str, dict[str, str]] = {}
        self._lock = threading.Lock()

    # ── Device Listing ────────────────────────────────────────────────

    def list_devices(self) -> list[dict[str, Any]]:
        """List all connected USB devices."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_USBControllerDevice | "
                 "ForEach-Object { $dep = $_.Dependent; "
                 "Get-CimInstance -Query \"SELECT * FROM Win32_PnPEntity WHERE DeviceID='$($dep.DeviceID -replace '\\\\','\\\\\\\\')' \" } | "
                 "Select-Object Name, DeviceID, Status, Manufacturer | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                devices = []
                for d in data:
                    name = d.get("Name") or "Unknown"
                    devices.append({
                        "name": name,
                        "device_id": d.get("DeviceID", ""),
                        "status": d.get("Status", ""),
                        "manufacturer": d.get("Manufacturer", ""),
                    })
                self._record("list_devices", "", True, f"{len(devices)} devices")
                return devices
        except Exception as e:
            self._record("list_devices", "", False, str(e))
        # Fallback: simpler query
        return self._list_devices_simple()

    def _list_devices_simple(self) -> list[dict[str, Any]]:
        """Simpler USB device listing via pnputil."""
        try:
            result = subprocess.run(
                ["pnputil", "/enum-devices", "/class", "USB"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            devices = []
            current: dict[str, str] = {}
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("Instance ID:"):
                    if current:
                        devices.append(current)
                    current = {"device_id": line.split(":", 1)[1].strip(), "name": "", "status": ""}
                elif line.startswith("Device Description:") and current:
                    current["name"] = line.split(":", 1)[1].strip()
                elif line.startswith("Status:") and current:
                    current["status"] = line.split(":", 1)[1].strip()
            if current and current.get("device_id"):
                devices.append(current)
            return devices
        except Exception:
            return []

    def get_device(self, name_contains: str) -> list[dict[str, Any]]:
        """Find USB devices by partial name match."""
        q = name_contains.lower()
        return [d for d in self.list_devices() if q in d.get("name", "").lower()]

    # ── Change Detection ──────────────────────────────────────────────

    def snapshot_devices(self) -> dict[str, dict[str, str]]:
        """Take a snapshot of current USB devices."""
        devices = self.list_devices()
        snapshot = {}
        for d in devices:
            did = d.get("device_id", d.get("name", ""))
            snapshot[did] = d
        with self._lock:
            self._known_devices = snapshot
        return snapshot

    def detect_changes(self) -> dict[str, Any]:
        """Detect USB device changes since last snapshot."""
        with self._lock:
            old = dict(self._known_devices)

        current_devices = self.list_devices()
        current = {}
        for d in current_devices:
            did = d.get("device_id", d.get("name", ""))
            current[did] = d

        added = [current[k] for k in current if k not in old]
        removed = [old[k] for k in old if k not in current]

        with self._lock:
            self._known_devices = current

        for d in added:
            self._record("device_connected", d.get("name", ""), True)
        for d in removed:
            self._record("device_disconnected", d.get("name", ""), True)

        return {
            "added": added,
            "removed": removed,
            "total_current": len(current),
        }

    # ── Device Count by Type ──────────────────────────────────────────

    def count_by_status(self) -> dict[str, int]:
        """Count devices by status."""
        devices = self.list_devices()
        counts: dict[str, int] = {}
        for d in devices:
            status = d.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts

    # ── Query ─────────────────────────────────────────────────────────

    def _record(self, action: str, device_name: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(USBEvent(
                action=action, device_name=device_name,
                success=success, detail=detail,
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
                "known_devices": len(self._known_devices),
            }


# ── Singleton ───────────────────────────────────────────────────────
usb_monitor = USBMonitor()
