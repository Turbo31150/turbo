"""Memory Diagnostics — RAM hardware diagnostics.

Lists RAM modules, memory type detection, summary stats.
Uses subprocess for hardware info queries.
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["RAMModule", "MemDiagEvent", "MemoryDiagnostics", "memory_diagnostics"]

logger = logging.getLogger("jarvis.memory_diagnostics")

GB = 1024 ** 3

_MEMORY_TYPES: dict[int, str] = {
    20: "DDR",
    21: "DDR2",
    24: "DDR3",
    26: "DDR4",
    34: "DDR5",
}


@dataclass
class RAMModule:
    """A RAM module."""
    bank: str = ""
    device_locator: str = ""
    capacity_gb: float = 0.0
    speed_mhz: int = 0
    manufacturer: str = ""
    part_number: str = ""
    memory_type: str = ""


@dataclass
class MemDiagEvent:
    """A diagnostic event."""
    action: str = ""
    success: bool = True
    detail: str = ""
    timestamp: float = field(default_factory=time.time)


class MemoryDiagnostics:
    """RAM hardware diagnostics."""

    def __init__(self) -> None:
        self._events: list[MemDiagEvent] = []

    def list_modules(self) -> list[dict[str, Any]]:
        """List RAM modules via subprocess."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_PhysicalMemory | Select-Object BankLabel,DeviceLocator,Capacity,Speed,Manufacturer,PartNumber,SMBIOSMemoryType | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return []
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            modules = []
            for item in data:
                cap = item.get("Capacity") or 0
                speed = item.get("Speed") or 0
                smbios = item.get("SMBIOSMemoryType")
                mem_type = _MEMORY_TYPES.get(smbios, f"Type_{smbios}") if smbios else ""
                modules.append({
                    "bank": item.get("BankLabel") or "",
                    "device_locator": item.get("DeviceLocator") or "",
                    "capacity_gb": cap / GB if cap else 0,
                    "speed_mhz": speed,
                    "manufacturer": item.get("Manufacturer") or "",
                    "part_number": item.get("PartNumber") or "",
                    "memory_type": mem_type,
                })
            self._events.append(MemDiagEvent(action="list_modules", detail=f"{len(modules)} modules"))
            return modules
        except Exception as e:
            logger.warning("list_modules failed: %s", e)
            self._events.append(MemDiagEvent(action="list_modules", success=False, detail=str(e)))
            return []

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all RAM modules."""
        modules = self.list_modules()
        if not modules:
            return {"total_gb": 0, "module_count": 0, "max_speed_mhz": 0, "memory_type": ""}
        total = sum(m["capacity_gb"] for m in modules)
        max_speed = max(m["speed_mhz"] for m in modules)
        mem_type = modules[0].get("memory_type", "")
        return {
            "total_gb": total,
            "module_count": len(modules),
            "max_speed_mhz": max_speed,
            "memory_type": mem_type,
        }

    def get_events(self) -> list[dict[str, Any]]:
        """Get diagnostic events."""
        return [{"action": e.action, "success": e.success, "detail": e.detail, "timestamp": e.timestamp}
                for e in self._events]

    def get_stats(self) -> dict[str, Any]:
        """Get stats."""
        return {
            "total_events": len(self._events),
            "success_count": sum(1 for e in self._events if e.success),
            "failure_count": sum(1 for e in self._events if not e.success),
        }


memory_diagnostics = MemoryDiagnostics()
