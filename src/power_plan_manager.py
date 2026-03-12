"""Power Plan Manager — Windows power plans and settings.

List and read power plans via powercfg.
Designed for JARVIS autonomous power management.
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "PowerEvent",
    "PowerPlan",
    "PowerPlanManager",
]

logger = logging.getLogger("jarvis.power_plan_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class PowerPlan:
    """A power plan entry."""
    name: str
    guid: str = ""
    is_active: bool = False


@dataclass
class PowerEvent:
    """Record of a power plan action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class PowerPlanManager:
    """Windows power plans reader (read-only)."""

    def __init__(self) -> None:
        self._events: list[PowerEvent] = []
        self._lock = threading.Lock()

    def list_plans(self) -> list[dict[str, Any]]:
        """List all power plans via powercfg /list."""
        try:
            result = subprocess.run(
                ["powercfg", "/list"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                plans = []
                # Pattern: Power Scheme GUID: <guid>  (Name) [*]
                pattern = re.compile(
                    r":\s*([0-9a-fA-F\-]+)\s+\(([^)]+)\)\s*(\*)?",
                )
                for line in result.stdout.splitlines():
                    m = pattern.search(line)
                    if m:
                        plans.append({
                            "guid": m.group(1),
                            "name": m.group(2).strip(),
                            "is_active": m.group(3) == "*",
                        })
                self._record("list_plans", True, f"{len(plans)} plans")
                return plans
        except Exception as e:
            self._record("list_plans", False, str(e))
        return []

    def get_active_plan(self) -> dict[str, Any]:
        """Get the currently active power plan."""
        plans = self.list_plans()
        for p in plans:
            if p.get("is_active"):
                return p
        return {"name": "Unknown", "guid": "", "is_active": False}

    def get_battery_status(self) -> dict[str, Any]:
        """Get battery status (for laptops)."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | "
                 "Select-Object Name, EstimatedChargeRemaining, BatteryStatus, "
                 "EstimatedRunTime | ConvertTo-Json -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    data = data[0] if data else {}
                self._record("get_battery_status", True)
                return {
                    "name": data.get("Name", "") or "",
                    "charge_percent": data.get("EstimatedChargeRemaining", 0) or 0,
                    "status": data.get("BatteryStatus", 0),
                    "estimated_runtime_min": data.get("EstimatedRunTime", 0) or 0,
                }
        except Exception as e:
            self._record("get_battery_status", False, str(e))
        return {"name": "", "charge_percent": 0, "status": 0, "has_battery": False}

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(PowerEvent(action=action, success=success, detail=detail))

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


power_plan_manager = PowerPlanManager()
