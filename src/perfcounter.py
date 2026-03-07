"""Performance Counter — Windows real-time performance metrics.

CPU, memory, disk I/O, network throughput via counters.
Uses PowerShell Get-Counter (no external deps).
Designed for JARVIS autonomous performance monitoring.
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
    "PerfCounter",
    "PerfEvent",
    "PerfSample",
]

logger = logging.getLogger("jarvis.perfcounter")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Common performance counter paths
COUNTER_PATHS = {
    "cpu": "\\Processor(_Total)\\% Processor Time",
    "memory": "\\Memory\\Available MBytes",
    "disk_read": "\\PhysicalDisk(_Total)\\Disk Read Bytes/sec",
    "disk_write": "\\PhysicalDisk(_Total)\\Disk Write Bytes/sec",
    "disk_queue": "\\PhysicalDisk(_Total)\\Current Disk Queue Length",
    "net_recv": "\\Network Interface(*)\\Bytes Received/sec",
    "net_sent": "\\Network Interface(*)\\Bytes Sent/sec",
    "processes": "\\System\\Processes",
    "threads": "\\System\\Threads",
    "handles": "\\Process(_Total)\\Handle Count",
}


@dataclass
class PerfSample:
    """A performance counter sample."""
    counter: str
    value: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class PerfEvent:
    """Record of a perf counter action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class PerfCounter:
    """Windows performance counter reader."""

    def __init__(self) -> None:
        self._events: list[PerfEvent] = []
        self._history: list[dict[str, Any]] = []
        self._max_history = 100
        self._lock = threading.Lock()

    # ── Counter Reading ────────────────────────────────────────────────

    def read_counter(self, counter_path: str) -> float | None:
        """Read a single performance counter value."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"(Get-Counter '{counter_path}').CounterSamples[0].CookedValue"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                self._record("read_counter", True, f"{counter_path}: {val:.2f}")
                return val
        except Exception as e:
            self._record("read_counter", False, str(e))
        return None

    def read_named(self, name: str) -> float | None:
        """Read a named counter (cpu, memory, disk_read, etc.)."""
        path = COUNTER_PATHS.get(name)
        if not path:
            return None
        return self.read_counter(path)

    def snapshot(self) -> dict[str, Any]:
        """Take a snapshot of key performance metrics."""
        try:
            paths = [COUNTER_PATHS["cpu"], COUNTER_PATHS["memory"],
                     COUNTER_PATHS["processes"], COUNTER_PATHS["threads"]]
            paths_str = "', '".join(paths)
            result = subprocess.run(
                ["powershell", "-Command",
                 f"(Get-Counter @('{paths_str}')).CounterSamples | "
                 "Select-Object Path, CookedValue | ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, timeout=15,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                snap = {"timestamp": time.time()}
                for s in data:
                    path = s.get("Path", "").lower()
                    val = s.get("CookedValue", 0)
                    if "processor" in path and "%" in path:
                        snap["cpu_percent"] = round(val, 1)
                    elif "available mbytes" in path:
                        snap["available_mb"] = round(val, 0)
                    elif "processes" in path:
                        snap["processes"] = int(val)
                    elif "threads" in path:
                        snap["threads"] = int(val)
                with self._lock:
                    self._history.append(snap)
                    if len(self._history) > self._max_history:
                        self._history = self._history[-self._max_history:]
                self._record("snapshot", True)
                return snap
        except Exception as e:
            self._record("snapshot", False, str(e))
        return {"timestamp": time.time(), "error": "failed"}

    def list_counters(self) -> dict[str, str]:
        """List available named counters."""
        return dict(COUNTER_PATHS)

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get snapshot history."""
        with self._lock:
            return self._history[-limit:]

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(PerfEvent(
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
                "available_counters": len(COUNTER_PATHS),
            }


# ── Singleton ───────────────────────────────────────────────────────
perfcounter = PerfCounter()
