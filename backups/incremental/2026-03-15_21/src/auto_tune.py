"""JARVIS Auto-Tune Scheduler — Dynamic resource profiling & workload balancing.

Monitors CPU/GPU/memory load and adjusts cluster parameters:
- Threadpool sizing for async workers
- Cooldown periods for overloaded nodes
- GC tuning recommendations
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "AutoTuneScheduler",
    "NodeLoad",
    "ResourceSnapshot",
]

logger = logging.getLogger("jarvis.auto_tune")


@dataclass
class ResourceSnapshot:
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    gpu_temp_c: float = 0.0
    gpu_util_percent: float = 0.0
    gpu_memory_used_mb: float = 0.0
    gpu_memory_total_mb: float = 0.0


@dataclass
class NodeLoad:
    """Track load state per cluster node."""
    name: str
    active_requests: int = 0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    cooldown_until: float = 0.0
    max_concurrent: int = 3

    @property
    def is_cooling(self) -> bool:
        return time.time() < self.cooldown_until

    @property
    def load_factor(self) -> float:
        """0.0 = idle, 1.0 = at capacity."""
        if self.is_cooling:
            return 1.0
        return min(self.active_requests / self.max_concurrent, 1.0)


class AutoTuneScheduler:
    """Profiles resources and recommends workload adjustments."""

    def __init__(self, history_size: int = 120):
        self._lock = threading.Lock()
        self._history: deque[ResourceSnapshot] = deque(maxlen=history_size)
        self._node_loads: dict[str, NodeLoad] = {}
        self._threadpool_size = 4  # default
        self._min_threads = 2
        self._max_threads = 12
        self._gpu_cache: str = ""
        self._gpu_cache_ts: float = 0.0

    def sample(self) -> ResourceSnapshot:
        """Take a resource snapshot (CPU, memory, GPU)."""
        snap = ResourceSnapshot()

        # CPU & memory via psutil (if available)
        try:
            import psutil
            snap.cpu_percent = psutil.cpu_percent(interval=0)
            snap.memory_percent = psutil.virtual_memory().percent
        except ImportError:
            pass

        # GPU via nvidia-smi (cached 60s to avoid hammering)
        now = time.time()
        if now - self._gpu_cache_ts > 60:
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
                     "--format=csv,noheader,nounits"],
                    timeout=5, text=True,
                ).strip()
                self._gpu_cache = out
                self._gpu_cache_ts = now
            except (subprocess.SubprocessError, FileNotFoundError, ValueError):
                pass
        if self._gpu_cache:
            for line in self._gpu_cache.split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    snap.gpu_temp_c = max(snap.gpu_temp_c, float(parts[0]))
                    snap.gpu_util_percent = max(snap.gpu_util_percent, float(parts[1]))
                    snap.gpu_memory_used_mb += float(parts[2])
                    snap.gpu_memory_total_mb += float(parts[3])

        with self._lock:
            self._history.append(snap)
        return snap

    def get_node_load(self, node: str) -> NodeLoad:
        with self._lock:
            if node not in self._node_loads:
                self._node_loads[node] = NodeLoad(name=node)
            return self._node_loads[node]

    def begin_request(self, node: str):
        """Mark a request starting on a node."""
        load = self.get_node_load(node)
        with self._lock:
            load.active_requests += 1

    def end_request(self, node: str, latency_ms: float, success: bool):
        """Mark a request completing on a node."""
        load = self.get_node_load(node)
        with self._lock:
            load.active_requests = max(0, load.active_requests - 1)
            # EMA for latency
            alpha = 0.3
            load.avg_latency_ms = load.avg_latency_ms * (1 - alpha) + latency_ms * alpha
            # EMA for error rate
            load.error_rate = load.error_rate * (1 - alpha) + (0.0 if success else 1.0) * alpha

    def apply_cooldown(self, node: str, seconds: float = 30.0):
        """Put a node in cooldown (won't receive new requests)."""
        load = self.get_node_load(node)
        with self._lock:
            load.cooldown_until = time.time() + seconds
        logger.info("Node %s in cooldown for %.0fs", node, seconds)

    def recommend_threadpool_size(self) -> int:
        """Recommend threadpool size based on recent CPU/GPU load."""
        with self._lock:
            if len(self._history) < 3:
                return self._threadpool_size

            recent = list(self._history)[-10:]

        avg_cpu = sum(s.cpu_percent for s in recent) / len(recent)
        avg_gpu = sum(s.gpu_util_percent for s in recent) / len(recent)
        avg_mem = sum(s.memory_percent for s in recent) / len(recent)

        # High load → fewer threads to avoid contention
        if avg_cpu > 85 or avg_mem > 90 or avg_gpu > 90:
            recommended = max(self._min_threads, self._threadpool_size - 1)
        elif avg_cpu < 40 and avg_gpu < 50:
            recommended = min(self._max_threads, self._threadpool_size + 1)
        else:
            recommended = self._threadpool_size

        self._threadpool_size = recommended
        return recommended

    def get_best_available_node(self, candidates: list[str]) -> str | None:
        """Get the best available node (lowest load, not cooling)."""
        available = []
        for name in candidates:
            load = self.get_node_load(name)
            if not load.is_cooling and load.load_factor < 1.0:
                available.append((name, load.load_factor, load.avg_latency_ms))

        if not available:
            return None

        # Sort by load factor, then by latency
        available.sort(key=lambda x: (x[1], x[2]))
        return available[0][0]

    def get_status(self) -> dict:
        """Full scheduler status."""
        with self._lock:
            latest = self._history[-1] if self._history else ResourceSnapshot()
            nodes = {
                name: {
                    "active_requests": load.active_requests,
                    "avg_latency_ms": round(load.avg_latency_ms, 1),
                    "error_rate": round(load.error_rate, 3),
                    "load_factor": round(load.load_factor, 2),
                    "is_cooling": load.is_cooling,
                    "cooldown_remaining": max(0, round(load.cooldown_until - time.time(), 0)),
                }
                for name, load in self._node_loads.items()
            }

        return {
            "resource_snapshot": {
                "cpu_percent": latest.cpu_percent,
                "memory_percent": latest.memory_percent,
                "gpu_temp_c": latest.gpu_temp_c,
                "gpu_util_percent": latest.gpu_util_percent,
                "gpu_vram_used_mb": latest.gpu_memory_used_mb,
                "gpu_vram_total_mb": latest.gpu_memory_total_mb,
            },
            "threadpool_size": self._threadpool_size,
            "recommended_threads": self.recommend_threadpool_size(),
            "nodes": nodes,
            "history_size": len(self._history),
        }


# Global singleton
auto_tune = AutoTuneScheduler()
