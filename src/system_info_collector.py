"""System Info Collector — Linux system information.
Adapted from Windows version for Ubuntu 22.04 LTS.
"""
from __future__ import annotations
import json
import logging
import subprocess
import threading
import time
import platform
import os
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "SysInfoEvent",
    "SystemInfoCollector",
    "SystemProfile",
]

logger = logging.getLogger("jarvis.system_info_collector")

@dataclass
class SystemProfile:
    hostname: str = ""
    os_name: str = ""
    os_version: str = ""
    cpu: str = ""

@dataclass
class SysInfoEvent:
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True

class SystemInfoCollector:
    """Linux system information collector."""

    def __init__(self) -> None:
        self._events: list[SysInfoEvent] = []
        self._lock = threading.Lock()

    def get_os_info(self) -> dict[str, Any]:
        """Get operating system information."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "caption": f"Ubuntu {platform.release()}",
                "version": platform.version(),
                "build": platform.machine(),
                "arch": platform.architecture()[0],
                "system_dir": "/usr/bin",
                "total_ram_kb": mem.total // 1024,
                "free_ram_kb": mem.available // 1024,
                "last_boot": str(datetime.fromtimestamp(psutil.boot_time())) if 'psutil' in globals() else "N/A",
            }
        except: return {"os": "Linux"}

    def get_cpu_info(self) -> list[dict[str, Any]]:
        """Get CPU information."""
        try:
            import psutil
            return [{
                "Name": platform.processor(),
                "NumberOfCores": psutil.cpu_count(logical=False),
                "NumberOfLogicalProcessors": psutil.cpu_count(logical=True),
                "LoadPercentage": psutil.cpu_percent()
            }]
        except: return []

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(SysInfoEvent(action=action, success=success, detail=detail))

    def get_stats(self) -> dict[str, Any]:
        return {"os": platform.system(), "node": platform.node()}

system_info_collector = SystemInfoCollector()
