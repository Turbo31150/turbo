"""Telemetry Collector — Usage metrics collection.

Tracks API calls, latency, error rates per endpoint/service.
Supports time-windowed aggregation and export. Thread-safe.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.telemetry")


@dataclass
class MetricPoint:
    name: str
    value: float
    tags: dict[str, str] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class TelemetryCollector:
    """Collects and queries usage metrics."""

    def __init__(self, max_points: int = 10000):
        self._points: list[MetricPoint] = []
        self._max_points = max_points
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)

    def record(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        """Record a metric data point."""
        point = MetricPoint(name=name, value=value, tags=tags or {})
        with self._lock:
            self._points.append(point)
            if len(self._points) > self._max_points:
                self._points = self._points[-self._max_points:]

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment a counter."""
        with self._lock:
            self._counters[name] += amount

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge value."""
        self._gauges[name] = value

    def record_histogram(self, name: str, value: float) -> None:
        """Record a value in a histogram (e.g., latency)."""
        with self._lock:
            self._histograms[name].append(value)
            if len(self._histograms[name]) > 1000:
                self._histograms[name] = self._histograms[name][-1000:]

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float | None:
        return self._gauges.get(name)

    def get_histogram_stats(self, name: str) -> dict | None:
        vals = self._histograms.get(name)
        if not vals:
            return None
        sorted_vals = sorted(vals)
        n = len(sorted_vals)
        return {
            "count": n,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(sorted_vals) / n,
            "p50": sorted_vals[n // 2],
            "p95": sorted_vals[int(n * 0.95)] if n >= 20 else sorted_vals[-1],
            "p99": sorted_vals[int(n * 0.99)] if n >= 100 else sorted_vals[-1],
        }

    def query(self, name: str | None = None, since: float | None = None, limit: int = 100) -> list[dict]:
        with self._lock:
            points = self._points
        if name:
            points = [p for p in points if p.name == name]
        if since:
            points = [p for p in points if p.ts >= since]
        return [
            {"name": p.name, "value": p.value, "tags": p.tags, "ts": p.ts}
            for p in points[-limit:]
        ]

    def get_counters(self) -> dict[str, int]:
        return dict(self._counters)

    def get_gauges(self) -> dict[str, float]:
        return dict(self._gauges)

    def get_stats(self) -> dict:
        return {
            "total_points": len(self._points),
            "counters": len(self._counters),
            "gauges": len(self._gauges),
            "histograms": len(self._histograms),
            "max_points": self._max_points,
        }


# ── Singleton ────────────────────────────────────────────────────────────────
telemetry = TelemetryCollector()
