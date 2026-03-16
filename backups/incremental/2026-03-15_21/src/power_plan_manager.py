"""Power Plan Manager — Linux power plans and battery status.
Adapted from Windows version for Ubuntu 22.04 LTS.
"""
from __future__ import annotations
import logging
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
    """Linux power plans and battery monitoring."""

    def __init__(self) -> None:
        self._events: list[PowerEvent] = []
        self._lock = threading.Lock()

    def list_plans(self) -> list[dict[str, Any]]:
        """List power profiles via powerprofilesctl (common on Ubuntu)."""
        try:
            result = subprocess.run(["powerprofilesctl", "list"], capture_output=True, text=True, timeout=5)
            plans = []
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith('*'):
                        plans.append({"name": line.replace('*', '').strip(), "is_active": True, "guid": "active"})
                    elif line.strip():
                        plans.append({"name": line.strip(), "is_active": False, "guid": "available"})
            return plans
        except:
            return [{"name": "Balanced", "is_active": True, "guid": "default"}]

    def get_battery_status(self) -> dict[str, Any]:
        """Get battery status via upower."""
        try:
            result = subprocess.run(["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.splitlines()
                data = {}
                for line in lines:
                    if ':' in line:
                        k, v = line.split(':', 1)
                        data[k.strip()] = v.strip()
                
                return {
                    "name": data.get("model", "Battery"),
                    "charge_percent": int(data.get("percentage", "0").replace('%', '')),
                    "status": data.get("state", "unknown"),
                    "estimated_runtime_min": 0 # Logic to parse time remaining if needed
                }
        except: pass
        return {"name": "No Battery", "charge_percent": 100, "status": "AC", "has_battery": False}

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(PowerEvent(action=action, success=success, detail=detail))

power_plan_manager = PowerPlanManager()
