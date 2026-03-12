"""JARVIS Model Drift Detector — Continuous model quality surveillance.

Tracks model performance over time, detects statistical drift,
and triggers alerts when models degrade significantly.
"""

from __future__ import annotations

import json
import logging
import math
import statistics
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("jarvis.drift_detector")

_DATA_DIR = Path(__file__).parent.parent / "data"
_DRIFT_FILE = _DATA_DIR / "drift_state.json"

# Alert thresholds
Z_SCORE_THRESHOLD = 2.5   # Standard deviations for anomaly
MIN_SAMPLES = 10           # Minimum samples before drift detection
DRIFT_WINDOW = 3600        # 1 hour rolling window for current metrics
BASELINE_WINDOW = 86400    # 24h for baseline computation


@dataclass
class ModelMetricWindow:
    """Rolling window of metric values for a model."""
    values: deque = field(default_factory=lambda: deque(maxlen=500))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=500))

    def add(self, value: float, ts: float | None = None):
        self.values.append(value)
        self.timestamps.append(ts or time.time())

    def recent(self, seconds: float = 3600) -> list[float]:
        cutoff = time.time() - seconds
        return [v for v, t in zip(self.values, self.timestamps) if t >= cutoff]

    @property
    def count(self) -> int:
        return len(self.values)


class DriftDetector:
    """Monitors model performance and detects quality drift."""

    def __init__(self):
        self._lock = threading.Lock()
        # model_name -> metric_name -> MetricWindow
        self._windows: dict[str, dict[str, ModelMetricWindow]] = defaultdict(
            lambda: defaultdict(ModelMetricWindow)
        )
        self._baselines: dict[str, dict[str, tuple[float, float]]] = {}  # (mean, std)
        self._alerts: list[dict] = []
        self._load_state()

    def record(self, model: str, latency_ms: float, success: bool,
               quality: float = 0.0, tokens: int = 0):
        """Record a model inference result."""
        with self._lock:
            windows = self._windows[model]
            windows["latency_ms"].add(latency_ms)
            windows["success"].add(1.0 if success else 0.0)
            if quality > 0:
                windows["quality"].add(quality)
            if tokens > 0:
                windows["tokens"].add(float(tokens))

        # Check for drift after recording
        self._check_drift(model)

    def compute_baselines(self):
        """Compute baselines from long-term data for all models."""
        with self._lock:
            for model, metrics in self._windows.items():
                self._baselines[model] = {}
                for metric_name, window in metrics.items():
                    values = window.recent(BASELINE_WINDOW)
                    if len(values) >= MIN_SAMPLES:
                        mean = statistics.mean(values)
                        std = statistics.stdev(values) if len(values) > 1 else 1.0
                        self._baselines[model][metric_name] = (mean, max(std, 0.001))

    def _check_drift(self, model: str):
        """Check if a model's recent metrics drift from baseline."""
        baseline = self._baselines.get(model, {})
        if not baseline:
            return

        with self._lock:
            metrics = self._windows[model]

        for metric_name in ["latency_ms", "success", "quality"]:
            if metric_name not in baseline or metric_name not in metrics:
                continue

            recent = metrics[metric_name].recent(DRIFT_WINDOW)
            if len(recent) < MIN_SAMPLES:
                continue

            bl_mean, bl_std = baseline[metric_name]
            current_mean = statistics.mean(recent)

            z_score = abs(current_mean - bl_mean) / bl_std

            if z_score > Z_SCORE_THRESHOLD:
                direction = "degraded" if (
                    (metric_name == "latency_ms" and current_mean > bl_mean) or
                    (metric_name in ("success", "quality") and current_mean < bl_mean)
                ) else "improved"

                alert = {
                    "model": model,
                    "metric": metric_name,
                    "z_score": round(z_score, 2),
                    "baseline_mean": round(bl_mean, 3),
                    "current_mean": round(current_mean, 3),
                    "direction": direction,
                    "samples": len(recent),
                    "timestamp": time.time(),
                }

                with self._lock:
                    # Avoid duplicate alerts for same model+metric within 5 min
                    existing = [a for a in self._alerts
                                if a["model"] == model and a["metric"] == metric_name
                                and time.time() - a["timestamp"] < 300]
                    if not existing:
                        self._alerts.append(alert)
                        if len(self._alerts) > 100:
                            self._alerts = self._alerts[-100:]
                        if direction == "degraded":
                            logger.warning("DRIFT ALERT: %s %s — z=%.1f (%.3f → %.3f)",
                                           model, metric_name, z_score, bl_mean, current_mean)

    def get_model_health(self, model: str) -> dict:
        """Get health status for a specific model."""
        with self._lock:
            metrics = self._windows.get(model, {})

        result = {"model": model, "metrics": {}}
        for metric_name in ["latency_ms", "success", "quality", "tokens"]:
            window = metrics.get(metric_name)
            if not window or window.count == 0:
                continue
            recent = window.recent(DRIFT_WINDOW)
            if not recent:
                continue
            result["metrics"][metric_name] = {
                "mean": round(statistics.mean(recent), 2),
                "min": round(min(recent), 2),
                "max": round(max(recent), 2),
                "count": len(recent),
                "std": round(statistics.stdev(recent), 2) if len(recent) > 1 else 0,
            }

        # Compare to baseline
        baseline = self._baselines.get(model, {})
        if baseline:
            result["baseline"] = {k: {"mean": round(v[0], 3), "std": round(v[1], 3)}
                                  for k, v in baseline.items()}

        return result

    def get_all_health(self) -> dict:
        """Get health for all tracked models."""
        with self._lock:
            models = list(self._windows.keys())
        return {m: self.get_model_health(m) for m in models}

    def get_alerts(self, since: float = 0) -> list[dict]:
        """Get recent drift alerts."""
        with self._lock:
            if since:
                return [a for a in self._alerts if a["timestamp"] >= since]
            return list(self._alerts)

    def get_degraded_models(self) -> list[str]:
        """Get list of models currently showing degraded performance."""
        cutoff = time.time() - 600  # Last 10 min alerts
        with self._lock:
            degraded = set()
            for a in self._alerts:
                if a["timestamp"] >= cutoff and a["direction"] == "degraded":
                    degraded.add(a["model"])
            return sorted(degraded)

    def suggest_rerouting(self, task_type: str, candidates: list[str]) -> list[str]:
        """Reorder candidates, moving degraded models to the end."""
        degraded = set(self.get_degraded_models())
        healthy = [c for c in candidates if c not in degraded]
        unhealthy = [c for c in candidates if c in degraded]
        return healthy + unhealthy

    def get_report(self) -> dict:
        """Full drift detection report."""
        return {
            "models": self.get_all_health(),
            "alerts": self.get_alerts(since=time.time() - 3600),
            "degraded": self.get_degraded_models(),
            "baseline_models": list(self._baselines.keys()),
            "timestamp": time.time(),
        }

    def _save_state(self):
        """Persist baselines and alerts to disk."""
        try:
            state = {
                "baselines": {
                    model: {metric: {"mean": m, "std": s} for metric, (m, s) in metrics.items()}
                    for model, metrics in self._baselines.items()
                },
                "alerts": self._alerts[-50:],
                "saved_at": time.time(),
            }
            _DRIFT_FILE.write_text(json.dumps(state, indent=2))
        except (OSError, ValueError) as e:
            logger.debug("Drift state save failed: %s", e)

    def _load_state(self):
        """Restore baselines from disk."""
        try:
            state = json.loads(_DRIFT_FILE.read_text())
            for model, metrics in state.get("baselines", {}).items():
                self._baselines[model] = {
                    m: (v["mean"], v["std"]) for m, v in metrics.items()
                }
            self._alerts = state.get("alerts", [])
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass


# Global singleton
drift_detector = DriftDetector()
