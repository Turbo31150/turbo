"""JARVIS Observability Matrix v1 — Real-time metrics correlation & anomaly detection.

Collects metrics from all cluster nodes, detects correlations and anomalies,
provides heatmap-ready data for the dashboard.
"""

from __future__ import annotations

import logging
import math
import sqlite3
import statistics
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.observability")

_METRICS_DB = Path(__file__).parent.parent / "data" / "metrics.db"

# Nodes tracked
NODES = ["M1", "M2", "M3", "OL1"]

# Metric types
METRIC_TYPES = ["latency_ms", "success_rate", "throughput", "error_rate", "tokens_per_sec"]

# Time windows (seconds)
WINDOWS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}


@dataclass
class MetricPoint:
    node: str
    metric: str
    value: float
    timestamp: float = field(default_factory=time.time)


class ObservabilityMatrix:
    """Real-time metrics matrix with windowed aggregation and anomaly detection."""

    def __init__(self, max_points: int = 5000):
        self._lock = threading.Lock()
        self._points: deque[MetricPoint] = deque(maxlen=max_points)
        self._baselines: dict[str, dict[str, float]] = {}  # node -> metric -> baseline_mean
        self._baseline_std: dict[str, dict[str, float]] = {}

    def record(self, node: str, metric: str, value: float):
        """Record a metric data point."""
        with self._lock:
            self._points.append(MetricPoint(node=node, metric=metric, value=value))

    def record_node_call(self, node: str, latency_ms: float, success: bool,
                         tokens: int = 0, duration_s: float = 0):
        """Convenience: record a full node call with derived metrics."""
        self.record(node, "latency_ms", latency_ms)
        self.record(node, "success_rate", 1.0 if success else 0.0)
        if duration_s > 0 and tokens > 0:
            self.record(node, "tokens_per_sec", tokens / duration_s)
        if not success:
            self.record(node, "error_rate", 1.0)

    def get_windowed(self, window: str = "5m") -> dict[str, dict[str, dict]]:
        """Get aggregated metrics per node per metric for a time window.

        Returns: {node: {metric: {mean, min, max, count, std}}}
        """
        seconds = WINDOWS.get(window, 300)
        cutoff = time.time() - seconds

        with self._lock:
            filtered = [p for p in self._points if p.timestamp >= cutoff]

        # Group by node -> metric
        groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for p in filtered:
            groups[p.node][p.metric].append(p.value)

        result = {}
        for node in groups:
            result[node] = {}
            for metric, values in groups[node].items():
                result[node][metric] = {
                    "mean": round(statistics.mean(values), 2),
                    "min": round(min(values), 2),
                    "max": round(max(values), 2),
                    "count": len(values),
                    "std": round(statistics.stdev(values), 2) if len(values) > 1 else 0,
                }
        return result

    def get_heatmap(self, window: str = "5m") -> list[dict]:
        """Get heatmap-ready data: [{node, metric, value, anomaly_score}]."""
        data = self.get_windowed(window)
        heatmap = []
        for node, metrics in data.items():
            for metric, stats in metrics.items():
                anomaly = self._anomaly_score(node, metric, stats["mean"])
                heatmap.append({
                    "node": node,
                    "metric": metric,
                    "value": stats["mean"],
                    "count": stats["count"],
                    "anomaly_score": anomaly,
                })
        return heatmap

    def compute_baselines(self, window: str = "1h"):
        """Compute baseline statistics from a longer window for anomaly detection."""
        data = self.get_windowed(window)
        with self._lock:
            self._baselines = {}
            self._baseline_std = {}
            for node, metrics in data.items():
                self._baselines[node] = {}
                self._baseline_std[node] = {}
                for metric, stats in metrics.items():
                    self._baselines[node][metric] = stats["mean"]
                    self._baseline_std[node][metric] = stats["std"] if stats["std"] > 0 else 1.0

    def _anomaly_score(self, node: str, metric: str, current_value: float) -> float:
        """Z-score based anomaly detection. Returns 0-1 normalized score."""
        baseline = self._baselines.get(node, {}).get(metric)
        std = self._baseline_std.get(node, {}).get(metric, 1.0)
        if baseline is None:
            return 0.0
        z = abs(current_value - baseline) / std if std > 0 else 0.0
        # Sigmoid normalization: z=2 -> 0.5, z=3 -> 0.73, z=4 -> 0.88
        return round(1.0 / (1.0 + math.exp(-z + 3)), 3)

    def get_correlations(self, window: str = "5m") -> list[dict]:
        """Detect correlations between metrics across nodes.

        Returns list of {node_a, metric_a, node_b, metric_b, correlation}.
        """
        seconds = WINDOWS.get(window, 300)
        cutoff = time.time() - seconds

        with self._lock:
            filtered = [p for p in self._points if p.timestamp >= cutoff]

        # Bucket points into time slots (10s buckets)
        bucket_size = 10
        series: dict[tuple[str, str], dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
        for p in filtered:
            bucket = int(p.timestamp / bucket_size)
            series[(p.node, p.metric)][bucket].append(p.value)

        # Average per bucket
        averaged: dict[tuple[str, str], dict[int, float]] = {}
        for key, buckets in series.items():
            averaged[key] = {b: statistics.mean(vals) for b, vals in buckets.items()}

        # Compute correlations between all pairs
        keys = list(averaged.keys())
        correlations = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                k1, k2 = keys[i], keys[j]
                if k1[0] == k2[0] and k1[1] == k2[1]:
                    continue  # Skip self
                common_buckets = set(averaged[k1].keys()) & set(averaged[k2].keys())
                if len(common_buckets) < 3:
                    continue
                v1 = [averaged[k1][b] for b in sorted(common_buckets)]
                v2 = [averaged[k2][b] for b in sorted(common_buckets)]
                corr = _pearson(v1, v2)
                if abs(corr) > 0.6:
                    correlations.append({
                        "node_a": k1[0], "metric_a": k1[1],
                        "node_b": k2[0], "metric_b": k2[1],
                        "correlation": round(corr, 3),
                        "samples": len(common_buckets),
                    })

        return sorted(correlations, key=lambda x: abs(x["correlation"]), reverse=True)[:20]

    def get_alerts(self, threshold: float = 0.7) -> list[dict]:
        """Get active anomaly alerts above threshold."""
        heatmap = self.get_heatmap("5m")
        return [
            {"node": h["node"], "metric": h["metric"],
             "value": h["value"], "anomaly_score": h["anomaly_score"]}
            for h in heatmap if h["anomaly_score"] >= threshold
        ]

    def get_report(self) -> dict:
        """Full observability report."""
        return {
            "matrix_5m": self.get_windowed("5m"),
            "heatmap": self.get_heatmap("5m"),
            "correlations": self.get_correlations("5m"),
            "alerts": self.get_alerts(),
            "total_points": len(self._points),
            "timestamp": time.time(),
        }


def _pearson(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient."""
    n = len(x)
    if n < 2:
        return 0.0
    mx, my = statistics.mean(x), statistics.mean(y)
    sx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    sy = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if sx == 0 or sy == 0:
        return 0.0
    return sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / (sx * sy)


# Global singleton
observability_matrix = ObservabilityMatrix()
