"""Linux Swap Manager — Swap space and virtual memory management.

swapon/swapoff, /proc/swaps, zramctl, fallocate for swapfile.
Designed for JARVIS autonomous memory management.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "SwapEvent",
    "SwapInfo",
    "LinuxSwapManager",
]

logger = logging.getLogger("jarvis.linux_swap_manager")


@dataclass
class SwapInfo:
    """Swap space information."""
    name: str
    allocated_mb: int = 0
    current_usage_mb: int = 0
    peak_usage_mb: int = 0


@dataclass
class SwapEvent:
    """Record of a swap action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class LinuxSwapManager:
    """Linux swap space management."""

    def __init__(self) -> None:
        self._events: list[SwapEvent] = []
        self._lock = threading.Lock()

    # ── Swap Info ─────────────────────────────────────────────────────────

    def get_usage(self) -> list[dict[str, Any]]:
        """Get current swap usage from /proc/swaps."""
        try:
            if os.path.exists("/proc/swaps"):
                with open("/proc/swaps") as f:
                    lines = f.readlines()
                swaps = []
                for line in lines[1:]:  # Skip header
                    parts = line.split()
                    if len(parts) >= 5:
                        size_kb = int(parts[2])
                        used_kb = int(parts[3])
                        swaps.append({
                            "name": parts[0],
                            "type": parts[1],
                            "allocated_mb": round(size_kb / 1024),
                            "current_usage_mb": round(used_kb / 1024),
                            "peak_usage_mb": 0,  # Linux ne track pas le peak dans /proc/swaps
                        })
                self._record("get_usage", True, f"{len(swaps)} swap devices")
                return swaps
        except Exception as e:
            self._record("get_usage", False, str(e))
        return []

    def get_settings(self) -> list[dict[str, Any]]:
        """Get swap configuration (fstab entries + current)."""
        settings: list[dict[str, Any]] = []
        # Depuis /etc/fstab
        try:
            if os.path.exists("/etc/fstab"):
                with open("/etc/fstab") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("#") or not line:
                            continue
                        parts = line.split()
                        if len(parts) >= 3 and parts[2] == "swap":
                            settings.append({
                                "name": parts[0],
                                "initial_size_mb": 0,  # Taille dynamique
                                "max_size_mb": 0,
                                "source": "fstab",
                            })
        except Exception:
            pass
        # ZRAM
        settings.extend(self._get_zram_info())
        return settings

    def _get_zram_info(self) -> list[dict[str, Any]]:
        """Get ZRAM device info."""
        zram_devices: list[dict[str, Any]] = []
        try:
            result = subprocess.run(
                ["zramctl", "--output-all", "--noheadings"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    parts = line.split()
                    if parts:
                        zram_devices.append({
                            "name": parts[0],
                            "initial_size_mb": 0,
                            "max_size_mb": 0,
                            "source": "zram",
                            "detail": line.strip(),
                        })
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return zram_devices

    def get_virtual_memory(self) -> dict[str, Any]:
        """Get OS virtual memory stats from /proc/meminfo."""
        try:
            if os.path.exists("/proc/meminfo"):
                meminfo: dict[str, int] = {}
                with open("/proc/meminfo") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val_parts = parts[1].strip().split()
                            if val_parts:
                                try:
                                    meminfo[key] = int(val_parts[0])  # kB
                                except ValueError:
                                    pass
                return {
                    "total_virtual_kb": meminfo.get("SwapTotal", 0) + meminfo.get("MemTotal", 0),
                    "free_virtual_kb": meminfo.get("SwapFree", 0) + meminfo.get("MemFree", 0),
                    "total_physical_kb": meminfo.get("MemTotal", 0),
                    "free_physical_kb": meminfo.get("MemFree", 0),
                    "swap_total_kb": meminfo.get("SwapTotal", 0),
                    "swap_free_kb": meminfo.get("SwapFree", 0),
                    "cached_kb": meminfo.get("Cached", 0),
                    "buffers_kb": meminfo.get("Buffers", 0),
                }
        except Exception:
            pass
        return {}

    def get_swappiness(self) -> int:
        """Get current vm.swappiness value."""
        try:
            with open("/proc/sys/vm/swappiness") as f:
                return int(f.read().strip())
        except Exception:
            return -1

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(SwapEvent(
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
linux_swap_manager = LinuxSwapManager()
