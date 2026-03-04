"""Resource Monitor — System resource tracking for Windows.

Tracks CPU, RAM, GPU (VRAM + temperature), and disk usage.
Fires alerts via alert_manager when thresholds are exceeded.
"""

from __future__ import annotations

import logging
import subprocess
import time
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("jarvis.resource_monitor")

MAX_HISTORY = 360  # ~1h at 10s intervals


@dataclass
class ResourceSnapshot:
    ts: float
    cpu_percent: float
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    gpus: list[dict]
    disks: list[dict]


class ResourceMonitor:
    """Monitors system resources on Windows."""

    def __init__(self):
        self._history: deque[dict] = deque(maxlen=MAX_HISTORY)
        self._thresholds = {
            "cpu_percent": 90.0,
            "ram_percent": 90.0,
            "gpu_temp_c": 85.0,
            "gpu_vram_percent": 95.0,
            "disk_percent": 95.0,
        }
        self._last_sample: float = 0.0

    def set_threshold(self, key: str, value: float) -> None:
        if key in self._thresholds:
            self._thresholds[key] = value

    def get_thresholds(self) -> dict:
        return dict(self._thresholds)

    def sample(self) -> dict:
        """Take a resource snapshot. Returns dict with cpu, ram, gpus, disks."""
        snap: dict[str, Any] = {"ts": time.time()}

        # CPU + RAM via Python
        try:
            import psutil
            snap["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            snap["ram_used_gb"] = round(mem.used / (1024**3), 2)
            snap["ram_total_gb"] = round(mem.total / (1024**3), 2)
            snap["ram_percent"] = mem.percent
        except ImportError:
            snap["cpu_percent"] = 0.0
            snap["ram_used_gb"] = 0.0
            snap["ram_total_gb"] = 0.0
            snap["ram_percent"] = 0.0

        # GPU via nvidia-smi
        snap["gpus"] = self._query_gpus()

        # Disks
        snap["disks"] = self._query_disks()

        self._history.append(snap)
        self._last_sample = snap["ts"]
        self._check_alerts(snap)
        return snap

    def _query_gpus(self) -> list[dict]:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0:
                return []
            gpus = []
            for line in r.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "temp_c": float(parts[2]),
                        "vram_used_mb": float(parts[3]),
                        "vram_total_mb": float(parts[4]),
                        "utilization_percent": float(parts[5]),
                    })
            return gpus
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return []

    def _query_disks(self) -> list[dict]:
        try:
            import psutil
            disks = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append({
                        "mount": part.mountpoint,
                        "total_gb": round(usage.total / (1024**3), 1),
                        "used_gb": round(usage.used / (1024**3), 1),
                        "percent": usage.percent,
                    })
                except (PermissionError, OSError):
                    pass
            return disks
        except ImportError:
            return []

    def _check_alerts(self, snap: dict) -> None:
        """Fire alerts if thresholds exceeded."""
        try:
            from src.alert_manager import alert_manager
        except ImportError:
            return

        if snap.get("cpu_percent", 0) > self._thresholds["cpu_percent"]:
            alert_manager.fire(
                key="resource_cpu_high",
                message=f"CPU usage {snap['cpu_percent']:.0f}% (threshold {self._thresholds['cpu_percent']}%)",
                level="warning", source="resource_monitor",
            )

        if snap.get("ram_percent", 0) > self._thresholds["ram_percent"]:
            alert_manager.fire(
                key="resource_ram_high",
                message=f"RAM usage {snap['ram_percent']:.0f}% (threshold {self._thresholds['ram_percent']}%)",
                level="warning", source="resource_monitor",
            )

        for gpu in snap.get("gpus", []):
            if gpu.get("temp_c", 0) > self._thresholds["gpu_temp_c"]:
                alert_manager.fire(
                    key=f"resource_gpu{gpu['index']}_hot",
                    message=f"GPU{gpu['index']} {gpu['temp_c']}°C (threshold {self._thresholds['gpu_temp_c']}°C)",
                    level="critical", source="resource_monitor",
                )

    def get_latest(self) -> dict:
        """Return most recent snapshot or empty dict."""
        return self._history[-1] if self._history else {}

    def get_history(self, minutes: int = 60) -> list[dict]:
        cutoff = time.time() - (minutes * 60)
        return [s for s in self._history if s.get("ts", 0) >= cutoff]

    def get_stats(self) -> dict:
        return {
            "samples": len(self._history),
            "max_history": MAX_HISTORY,
            "thresholds": self._thresholds,
            "last_sample": self._last_sample,
        }


# ── Singleton ────────────────────────────────────────────────────────────────
resource_monitor = ResourceMonitor()
