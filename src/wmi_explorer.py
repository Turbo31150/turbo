"""WMI Explorer — Generic Windows WMI/CIM query engine.

Run arbitrary Get-CimInstance queries, list WMI classes, explore namespaces.
Uses PowerShell Get-CimInstance (no external deps).
Designed for JARVIS autonomous system discovery.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.wmi_explorer")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Common useful WMI classes
COMMON_CLASSES = [
    "Win32_OperatingSystem",
    "Win32_ComputerSystem",
    "Win32_Processor",
    "Win32_PhysicalMemory",
    "Win32_DiskDrive",
    "Win32_LogicalDisk",
    "Win32_NetworkAdapter",
    "Win32_VideoController",
    "Win32_BIOS",
    "Win32_BaseBoard",
    "Win32_Battery",
    "Win32_Fan",
    "Win32_TemperatureProbe",
    "Win32_Service",
    "Win32_Process",
    "Win32_UserAccount",
]


@dataclass
class WMIResult:
    """A WMI query result."""
    class_name: str
    instance_count: int = 0
    data: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class WMIEvent:
    """Record of a WMI action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class WMIExplorer:
    """Generic WMI/CIM query engine."""

    def __init__(self) -> None:
        self._events: list[WMIEvent] = []
        self._lock = threading.Lock()

    # ── Query ─────────────────────────────────────────────────────────────

    def query_class(self, class_name: str, properties: str = "",
                    max_results: int = 50) -> list[dict[str, Any]]:
        """Query a WMI class. Returns list of instances."""
        # Sanitize class_name to prevent injection
        safe_class = "".join(c for c in class_name if c.isalnum() or c == "_")
        if not safe_class:
            return []

        select = f"Select-Object {properties}" if properties else ""
        cmd = f"Get-CimInstance {safe_class}"
        if select:
            cmd += f" | {select}"
        cmd += f" | Select-Object -First {max_results} | ConvertTo-Json -Depth 2 -Compress"

        try:
            result = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                # Convert non-serializable values to strings
                clean = []
                for item in data:
                    row = {}
                    for k, v in item.items():
                        if isinstance(v, (str, int, float, bool, type(None))):
                            row[k] = v
                        else:
                            row[k] = str(v)
                    clean.append(row)
                self._record("query_class", True, f"{safe_class}: {len(clean)} results")
                return clean
        except Exception as e:
            self._record("query_class", False, f"{safe_class}: {e}")
        return []

    def list_common_classes(self) -> list[str]:
        """List commonly useful WMI classes."""
        return list(COMMON_CLASSES)

    def get_system_summary(self) -> dict[str, Any]:
        """Quick system summary via key WMI classes."""
        summary: dict[str, Any] = {}
        for cls in ["Win32_OperatingSystem", "Win32_ComputerSystem", "Win32_Processor"]:
            data = self.query_class(cls, max_results=1)
            if data:
                summary[cls] = data[0]
        return summary

    def count_instances(self, class_name: str) -> int:
        """Count instances of a WMI class."""
        safe_class = "".join(c for c in class_name if c.isalnum() or c == "_")
        if not safe_class:
            return 0
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"(Get-CimInstance {safe_class} | Measure-Object).Count"],
                capture_output=True, text=True, timeout=15,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip().isdigit():
                return int(result.stdout.strip())
        except Exception:
            pass
        return 0

    # ── Events ────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(WMIEvent(
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
                "common_classes": len(COMMON_CLASSES),
            }


# ── Singleton ───────────────────────────────────────────────────────
wmi_explorer = WMIExplorer()
