"""GPU Monitor — Windows GPU monitoring and management.

Temperature, VRAM usage, utilization, driver info.
Uses nvidia-smi + PowerShell Win32_VideoController (no external deps).
Designed for JARVIS autonomous GPU thermal management.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.gpu_monitor")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class GPUInfo:
    """GPU device information."""
    name: str
    driver_version: str = ""
    vram_total_mb: int = 0
    vram_used_mb: int = 0
    temperature: int = 0
    utilization: int = 0


@dataclass
class GPUEvent:
    """Record of a GPU action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class GPUMonitor:
    """Windows GPU monitoring."""

    def __init__(self) -> None:
        self._events: list[GPUEvent] = []
        self._history: list[dict[str, Any]] = []
        self._max_history = 100
        self._lock = threading.Lock()

    # ── NVIDIA GPU ─────────────────────────────────────────────────────

    def get_nvidia_info(self) -> list[dict[str, Any]]:
        """Get NVIDIA GPU info via nvidia-smi."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,"
                 "memory.total,memory.used,memory.free,driver_version",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                gpus = []
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 7:
                        gpus.append({
                            "name": parts[0],
                            "temperature": int(parts[1]) if parts[1].isdigit() else 0,
                            "utilization": int(parts[2]) if parts[2].isdigit() else 0,
                            "vram_total_mb": int(parts[3]) if parts[3].isdigit() else 0,
                            "vram_used_mb": int(parts[4]) if parts[4].isdigit() else 0,
                            "vram_free_mb": int(parts[5]) if parts[5].isdigit() else 0,
                            "driver_version": parts[6],
                            "vendor": "NVIDIA",
                        })
                self._record("get_nvidia_info", True, f"{len(gpus)} GPUs")
                return gpus
        except FileNotFoundError:
            pass  # nvidia-smi not found
        except Exception as e:
            self._record("get_nvidia_info", False, str(e))
        return []

    # ── Generic GPU (WMI) ──────────────────────────────────────────────

    def list_gpus(self) -> list[dict[str, Any]]:
        """List all GPUs via WMI."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_VideoController | "
                 "Select-Object Name, DriverVersion, AdapterRAM, "
                 "VideoProcessor, Status | ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, timeout=15,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                gpus = []
                for g in data:
                    ram = g.get("AdapterRAM", 0) or 0
                    gpus.append({
                        "name": g.get("Name", ""),
                        "driver_version": g.get("DriverVersion", ""),
                        "vram_mb": ram // (1024 * 1024) if ram > 0 else 0,
                        "processor": g.get("VideoProcessor", ""),
                        "status": g.get("Status", ""),
                    })
                return gpus
        except Exception as e:
            self._record("list_gpus", False, str(e))
        return []

    # ── Snapshot ───────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Take a GPU snapshot (NVIDIA preferred, WMI fallback)."""
        nvidia = self.get_nvidia_info()
        if nvidia:
            snap = {
                "timestamp": time.time(),
                "gpus": nvidia,
                "gpu_count": len(nvidia),
                "max_temp": max(g.get("temperature", 0) for g in nvidia),
                "total_vram_mb": sum(g.get("vram_total_mb", 0) for g in nvidia),
                "used_vram_mb": sum(g.get("vram_used_mb", 0) for g in nvidia),
            }
        else:
            wmi = self.list_gpus()
            snap = {
                "timestamp": time.time(),
                "gpus": wmi,
                "gpu_count": len(wmi),
                "max_temp": 0,
                "total_vram_mb": sum(g.get("vram_mb", 0) for g in wmi),
                "used_vram_mb": 0,
            }
        with self._lock:
            self._history.append(snap)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        return snap

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get snapshot history."""
        with self._lock:
            return self._history[-limit:]

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(GPUEvent(
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
                "history_size": len(self._history),
            }


# ── Singleton ───────────────────────────────────────────────────────
gpu_monitor = GPUMonitor()
