"""System Info Collector — Windows system information.

OS version, CPU, BIOS, uptime, boot time, computer model.
Uses PowerShell WMI classes (no external deps).
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
    "SysInfoEvent",
    "SystemInfoCollector",
    "SystemProfile",
]

logger = logging.getLogger("jarvis.system_info_collector")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class SystemProfile:
    """System profile information."""
    hostname: str = ""
    os_name: str = ""
    os_version: str = ""
    cpu: str = ""


@dataclass
class SysInfoEvent:
    """Record of a sysinfo action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class SystemInfoCollector:
    """Windows system information collector."""

    def __init__(self) -> None:
        self._events: list[SysInfoEvent] = []
        self._lock = threading.Lock()

    # ── OS Info ───────────────────────────────────────────────────────────

    def get_os_info(self) -> dict[str, Any]:
        """Get operating system information."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_OperatingSystem | "
                 "Select-Object Caption, Version, BuildNumber, "
                 "OSArchitecture, SystemDirectory, "
                 "TotalVisibleMemorySize, FreePhysicalMemory, "
                 "LastBootUpTime | ConvertTo-Json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                boot_time = data.get("LastBootUpTime", "")
                if isinstance(boot_time, dict):
                    boot_time = str(boot_time.get("DateTime", ""))
                self._record("get_os_info", True)
                return {
                    "caption": data.get("Caption", ""),
                    "version": data.get("Version", ""),
                    "build": data.get("BuildNumber", ""),
                    "arch": data.get("OSArchitecture", ""),
                    "system_dir": data.get("SystemDirectory", ""),
                    "total_ram_kb": data.get("TotalVisibleMemorySize", 0) or 0,
                    "free_ram_kb": data.get("FreePhysicalMemory", 0) or 0,
                    "last_boot": str(boot_time),
                }
        except Exception as e:
            self._record("get_os_info", False, str(e))
        return {}

    # ── CPU Info ──────────────────────────────────────────────────────────

    def get_cpu_info(self) -> list[dict[str, Any]]:
        """Get CPU information."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_Processor | "
                 "Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, "
                 "MaxClockSpeed, CurrentClockSpeed, LoadPercentage | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                return [
                    {
                        "name": c.get("Name", "").strip(),
                        "cores": c.get("NumberOfCores", 0) or 0,
                        "logical_processors": c.get("NumberOfLogicalProcessors", 0) or 0,
                        "max_clock_mhz": c.get("MaxClockSpeed", 0) or 0,
                        "current_clock_mhz": c.get("CurrentClockSpeed", 0) or 0,
                        "load_percent": c.get("LoadPercentage", 0) or 0,
                    }
                    for c in data
                ]
        except Exception:
            pass
        return []

    # ── BIOS Info ─────────────────────────────────────────────────────────

    def get_bios_info(self) -> dict[str, Any]:
        """Get BIOS information."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_BIOS | "
                 "Select-Object Manufacturer, Name, Version, "
                 "SerialNumber, SMBIOSBIOSVersion | ConvertTo-Json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                return {
                    "manufacturer": data.get("Manufacturer", ""),
                    "name": data.get("Name", ""),
                    "version": data.get("Version", ""),
                    "serial": data.get("SerialNumber", ""),
                    "smbios_version": data.get("SMBIOSBIOSVersion", ""),
                }
        except Exception:
            pass
        return {}

    # ── Computer System ───────────────────────────────────────────────────

    def get_computer_info(self) -> dict[str, Any]:
        """Get computer system information."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_ComputerSystem | "
                 "Select-Object Name, Manufacturer, Model, "
                 "SystemType, Domain, TotalPhysicalMemory | "
                 "ConvertTo-Json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                ram = data.get("TotalPhysicalMemory", 0) or 0
                return {
                    "name": data.get("Name", ""),
                    "manufacturer": data.get("Manufacturer", ""),
                    "model": data.get("Model", ""),
                    "system_type": data.get("SystemType", ""),
                    "domain": data.get("Domain", ""),
                    "total_ram_gb": round(ram / (1024**3), 2) if ram > 0 else 0,
                }
        except Exception:
            pass
        return {}

    # ── Full Profile ──────────────────────────────────────────────────────

    def get_full_profile(self) -> dict[str, Any]:
        """Get complete system profile."""
        return {
            "os": self.get_os_info(),
            "cpu": self.get_cpu_info(),
            "bios": self.get_bios_info(),
            "computer": self.get_computer_info(),
        }

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(SysInfoEvent(
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
system_info_collector = SystemInfoCollector()
