"""Performance Counter — Windows performance counter snapshots.

Read CPU, Memory, Disk, Network counters via Get-Counter.
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
    "CounterSnapshot",
    "PerfEvent",
    "PerformanceCounterManager",
]

logger = logging.getLogger("jarvis.performance_counter")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Common counter paths
COUNTER_PATHS = [
    "/Processor(_Total)/% Processor Time",
    "/Memory/Available MBytes",
    "/Memory/% Committed Bytes In Use",
    "/PhysicalDisk(_Total)/% Disk Time",
    "/PhysicalDisk(_Total)/Disk Read Bytes/sec",
    "/PhysicalDisk(_Total)/Disk Write Bytes/sec",
]


@dataclass
class CounterSnapshot:
    """A performance counter snapshot."""
    timestamp: float = 0.0
    counters: dict[str, float] = field(default_factory=dict)


@dataclass
class PerfEvent:
    """Record of a perf counter action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class PerformanceCounterManager:
    """Windows performance counter snapshots."""

    def __init__(self, max_history: int = 60) -> None:
        self._events: list[PerfEvent] = []
        self._history: list[dict[str, Any]] = []
        self._max_history = max_history
        self._lock = threading.Lock()

    def snapshot(self) -> dict[str, Any]:
        """Take a snapshot of common performance counters."""
        try:
            paths_arg = ",".join(f"'{p}'" for p in COUNTER_PATHS)
            result = subprocess.run(
                ["bash", "-Command",
                 f"$c = Get-Counter -Counter {paths_arg} -ErrorAction SilentlyContinue; "
                 "$out = @{}; foreach($s in $c.CounterSamples) { "
                 "$out[$s.Path] = [math]::Round($s.CookedValue, 2) }; "
                 "ConvertTo-Json $out -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                raw = json.loads(result.stdout)
                # Simplify counter names
                counters: dict[str, float] = {}
                for path, val in raw.items():
                    # Extract short name from full path
                    short = path.rsplit("/", 1)[-1] if "/" in path else path
                    counters[short] = val
                snap = {
                    "timestamp": time.time(),
                    "counters": counters,
                }
                with self._lock:
                    self._history.append(snap)
                    if len(self._history) > self._max_history:
                        self._history = self._history[-self._max_history:]
                self._record("snapshot", True, f"{len(counters)} counters")
                return snap
        except Exception as e:
            self._record("snapshot", False, str(e))
        return {"timestamp": time.time(), "counters": {}}

    def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent counter snapshots."""
        with self._lock:
            return list(self._history[-limit:])

    def get_counter(self, counter_path: str) -> dict[str, Any]:
        """Get a single custom counter value."""
        try:
            result = subprocess.run(
                ["bash", "-Command",
                 f"$c = Get-Counter -Counter '{counter_path}' -ErrorAction Stop; "
                 "ConvertTo-Json @{path=$c.CounterSamples[0].Path; "
                 "value=[math]::Round($c.CounterSamples[0].CookedValue, 2)} -Compress"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                self._record("get_counter", True, counter_path)
                return data
        except Exception as e:
            self._record("get_counter", False, str(e))
        return {"path": counter_path, "value": 0}

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(PerfEvent(action=action, success=success, detail=detail))

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


performance_counter = PerformanceCounterManager()
