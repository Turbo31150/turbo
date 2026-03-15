"""Driver Manager — Linux kernel modules and hardware drivers.
Adapted from Windows version for Ubuntu 22.04 LTS.
"""
from __future__ import annotations
import json
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DriverEvent",
    "DriverInfo",
    "DriverManager",
]

logger = logging.getLogger("jarvis.driver_manager")

@dataclass
class DriverInfo:
    """A device driver."""
    name: str
    vendor: str = ""
    version: str = ""
    status: str = ""
    device_class: str = ""

@dataclass
class DriverEvent:
    """Record of a driver action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True

class DriverManager:
    """Linux kernel modules management."""

    def __init__(self) -> None:
        self._events: list[DriverEvent] = []
        self._lock = threading.Lock()

    def list_drivers(self) -> list[dict[str, Any]]:
        """List kernel modules via lsmod."""
        try:
            result = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=5)
            drivers = []
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:] # Skip header
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 1:
                        drivers.append({
                            "name": parts[0],
                            "vendor": "Linux Kernel",
                            "version": "native",
                            "status": "Live",
                            "device_class": "Kernel Module"
                        })
            return drivers
        except: return []

    def search(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        return [d for d in self.list_drivers() if q in d.get("name", "").lower()]

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(DriverEvent(action=action, success=success, detail=detail))

    def get_stats(self) -> dict[str, Any]:
        return {"total_modules": len(self.list_drivers())}

driver_manager = DriverManager()
