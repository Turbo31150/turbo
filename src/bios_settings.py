"""BIOS Settings — Windows BIOS/UEFI information reader.

Read BIOS info via Win32_BIOS.
Designed for JARVIS autonomous system profiling.
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
    "BIOSEvent",
    "BIOSInfo",
    "BIOSSettingsReader",
]

logger = logging.getLogger("jarvis.bios_settings")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class BIOSInfo:
    """BIOS information entry."""
    manufacturer: str = ""
    version: str = ""
    serial_number: str = ""
    smbios_version: str = ""
    release_date: str = ""


@dataclass
class BIOSEvent:
    """Record of a BIOS query action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class BIOSSettingsReader:
    """Windows BIOS/UEFI information reader (read-only)."""

    def __init__(self) -> None:
        self._events: list[BIOSEvent] = []
        self._lock = threading.Lock()

    def get_info(self) -> dict[str, Any]:
        """Get BIOS information via Win32_BIOS."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_BIOS | "
                 "Select-Object Manufacturer, Name, Version, SerialNumber, "
                 "SMBIOSBIOSVersion, SMBIOSMajorVersion, SMBIOSMinorVersion, "
                 "ReleaseDate, PrimaryBIOS | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    data = data[0]
                release = data.get("ReleaseDate", "") or ""
                if isinstance(release, dict):
                    release = str(release.get("DateTime", release.get("value", "")))
                info = {
                    "manufacturer": data.get("Manufacturer", "") or "",
                    "name": data.get("Name", "") or "",
                    "version": data.get("Version", "") or "",
                    "serial_number": data.get("SerialNumber", "") or "",
                    "smbios_version": f"{data.get('SMBIOSMajorVersion', 0)}.{data.get('SMBIOSMinorVersion', 0)}",
                    "smbios_bios_version": data.get("SMBIOSBIOSVersion", "") or "",
                    "release_date": release,
                    "primary_bios": data.get("PrimaryBIOS", False),
                }
                self._record("get_info", True)
                return info
        except Exception as e:
            self._record("get_info", False, str(e))
        return {"manufacturer": "", "name": "", "version": "", "serial_number": ""}

    def get_secure_boot_status(self) -> dict[str, Any]:
        """Check Secure Boot status."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "try { $sb = Confirm-SecureBootUEFI; ConvertTo-Json @{secure_boot=$sb; uefi=$true} } "
                 "catch { ConvertTo-Json @{secure_boot=$false; uefi=$false; error=$_.Exception.Message} }"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                self._record("get_secure_boot_status", True)
                return data
        except Exception as e:
            self._record("get_secure_boot_status", False, str(e))
        return {"secure_boot": False, "uefi": False}

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(BIOSEvent(action=action, success=success, detail=detail))

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


bios_settings = BIOSSettingsReader()
