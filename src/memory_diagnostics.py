"""Memory Diagnostics — Windows RAM hardware diagnostics.

RAM slots, speed, manufacturer, type, capacity per module.
Uses PowerShell Get-CimInstance Win32_PhysicalMemory (no external deps).
Designed for JARVIS autonomous hardware diagnostics.
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
    "MemDiagEvent",
    "MemoryDiagnostics",
    "RAMModule",
]

logger = logging.getLogger("jarvis.memory_diagnostics")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Memory type mapping (SMBIOS MemoryType)
_MEMORY_TYPES = {
    0: "Unknown", 20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM",
    24: "DDR3", 26: "DDR4", 34: "DDR5",
}


@dataclass
class RAMModule:
    """A physical RAM module."""
    bank: str
    capacity_gb: float = 0.0
    speed_mhz: int = 0
    manufacturer: str = ""
    memory_type: str = ""


@dataclass
class MemDiagEvent:
    """Record of a memory diagnostic action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class MemoryDiagnostics:
    """Windows RAM hardware diagnostics."""

    def __init__(self) -> None:
        self._events: list[MemDiagEvent] = []
        self._lock = threading.Lock()

    # ── RAM Modules ───────────────────────────────────────────────────────

    def list_modules(self) -> list[dict[str, Any]]:
        """List physical RAM modules."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_PhysicalMemory | "
                 "Select-Object BankLabel, Capacity, Speed, Manufacturer, "
                 "SMBIOSMemoryType, PartNumber, DeviceLocator | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                modules = []
                for m in data:
                    cap = m.get("Capacity", 0) or 0
                    mem_type_id = m.get("SMBIOSMemoryType", 0) or 0
                    modules.append({
                        "bank": m.get("BankLabel", "") or "",
                        "device_locator": m.get("DeviceLocator", "") or "",
                        "capacity_gb": round(cap / (1024**3), 2) if cap > 0 else 0,
                        "speed_mhz": m.get("Speed", 0) or 0,
                        "manufacturer": (m.get("Manufacturer", "") or "").strip(),
                        "part_number": (m.get("PartNumber", "") or "").strip(),
                        "memory_type": _MEMORY_TYPES.get(mem_type_id, f"Type_{mem_type_id}"),
                    })
                self._record("list_modules", True, f"{len(modules)} modules")
                return modules
        except Exception as e:
            self._record("list_modules", False, str(e))
        return []

    def get_summary(self) -> dict[str, Any]:
        """Get RAM summary: total, slots, speed."""
        modules = self.list_modules()
        if not modules:
            return {"total_gb": 0, "module_count": 0, "max_speed_mhz": 0}
        return {
            "total_gb": round(sum(m.get("capacity_gb", 0) for m in modules), 2),
            "module_count": len(modules),
            "max_speed_mhz": max(m.get("speed_mhz", 0) for m in modules),
            "memory_type": modules[0].get("memory_type", "Unknown"),
        }

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(MemDiagEvent(
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
memory_diagnostics = MemoryDiagnostics()
