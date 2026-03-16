"""JARVIS Resource Allocator — Intelligent workload distribution across cluster nodes.

Distributes tasks to the optimal cluster node based on:
  - Real-time health checks (socket probe + model queries)
  - Current load estimates (from allocation history with decay)
  - Task-type affinity (code->M1, reasoning->M2/M3, query->OL1, trading->OL1)
  - Priority levels (high priority gets the fastest available node)

Usage:
    from src.resource_allocator import resource_allocator
    node = resource_allocator.allocate("code", priority=8)
    resource_allocator.record_allocation(node, "code", duration_ms=1200)
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
import urllib.request
import urllib.error
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

__all__ = [
    "ResourceAllocator",
    "NodeConfig",
    "resource_allocator",
]

logger = logging.getLogger("jarvis.resource_allocator")

# ---------------------------------------------------------------------------
# Node configuration
# ---------------------------------------------------------------------------

@dataclass
class NodeConfig:
    """Static configuration for a cluster node."""
    name: str
    host: str
    port: int
    max_concurrent: int
    weight: float                       # Base routing weight (higher = preferred)
    backend: str                        # "lmstudio" or "ollama"
    affinities: list[str] = field(default_factory=list)  # Task types this node excels at
    models_endpoint: str = ""           # URL path to list models


NODES: dict[str, NodeConfig] = {
    "M1": NodeConfig(
        name="M1",
        host="127.0.0.1",
        port=1234,
        max_concurrent=11,
        weight=1.9,
        backend="lmstudio",
        affinities=["code", "math", "architecture", "refactoring", "bugfix"],
        models_endpoint="/api/v1/models",
    ),
    "OL1": NodeConfig(
        name="OL1",
        host="127.0.0.1",
        port=11434,
        max_concurrent=3,
        weight=1.4,
        backend="ollama",
        affinities=["query", "trading", "web"],
        models_endpoint="/api/tags",
    ),
    "M2": NodeConfig(
        name="M2",
        host="192.168.1.26",
        port=1234,
        max_concurrent=3,
        weight=1.5,
        backend="lmstudio",
        affinities=["reasoning", "review"],
        models_endpoint="/api/v1/models",
    ),
    "M3": NodeConfig(
        name="M3",
        host="192.168.1.113",
        port=1234,
        max_concurrent=2,
        weight=1.2,
        backend="lmstudio",
        affinities=["reasoning"],
        models_endpoint="/api/v1/models",
    ),
}

# Task-type -> ordered list of preferred nodes
TASK_AFFINITY: dict[str, list[str]] = {
    "code":          ["M1", "OL1", "M2", "M3"],
    "bugfix":        ["M1", "OL1", "M2", "M3"],
    "architecture":  ["M1", "OL1", "M2", "M3"],
    "refactoring":   ["M1", "OL1", "M2", "M3"],
    "math":          ["M1", "OL1", "M2", "M3"],
    "reasoning":     ["M2", "M3", "M1", "OL1"],
    "review":        ["M2", "M1", "M3", "OL1"],
    "query":         ["OL1", "M1", "M2", "M3"],
    "trading":       ["OL1", "M1", "M2", "M3"],
    "web":           ["OL1", "M1", "M2", "M3"],
}

# Allocations older than this are decayed for load estimation
LOAD_DECAY_WINDOW_S = 120.0     # 2 minutes
LOAD_HALF_LIFE_S = 30.0         # weight halves every 30s
HEALTH_CHECK_TIMEOUT_S = 3.0    # socket + HTTP timeout


# ---------------------------------------------------------------------------
# Allocation record
# ---------------------------------------------------------------------------

@dataclass
class AllocationRecord:
    """A single allocation event used for load estimation."""
    node: str
    task_type: str
    timestamp: float
    duration_ms: float


# ---------------------------------------------------------------------------
# ResourceAllocator
# ---------------------------------------------------------------------------

class ResourceAllocator:
    """Distributes workload across JARVIS cluster nodes."""

    def __init__(self) -> None:
        self._nodes = dict(NODES)
        self._history: list[AllocationRecord] = []
        self._history_lock = threading.Lock()

        # Per-node circuit breaker state
        self._circuit_open: dict[str, float] = {}   # node -> timestamp when opened
        self._circuit_cooldown_s = 60.0

        # Per-node active allocation count (incremented on allocate, decremented on record)
        self._active: dict[str, int] = defaultdict(int)

        # Cumulative stats
        self._stats: dict[str, dict] = defaultdict(lambda: {
            "total_allocations": 0,
            "total_duration_ms": 0.0,
            "avg_duration_ms": 0.0,
        })

    # ------------------------------------------------------------------
    # Health checking
    # ------------------------------------------------------------------

    def _check_node_health(self, cfg: NodeConfig) -> dict:
        """Probe a single node.  Returns dict with online, models, latency_ms."""
        result: dict = {
            "name": cfg.name,
            "host": cfg.host,
            "port": cfg.port,
            "online": False,
            "models": [],
            "loaded_models": 0,
            "latency_ms": 0.0,
            "max_concurrent": cfg.max_concurrent,
        }

        # 1. Socket probe
        t0 = time.monotonic()
        try:
            sock = socket.create_connection(
                (cfg.host, cfg.port),
                timeout=HEALTH_CHECK_TIMEOUT_S,
            )
            sock.close()
        except (OSError, socket.timeout):
            return result
        latency_ms = (time.monotonic() - t0) * 1000
        result["latency_ms"] = round(latency_ms, 1)
        result["online"] = True

        # 2. Model query via HTTP
        if cfg.models_endpoint:
            url = f"http://{cfg.host}:{cfg.port}{cfg.models_endpoint}"
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=HEALTH_CHECK_TIMEOUT_S) as resp:
                    data = json.loads(resp.read().decode())

                if cfg.backend == "lmstudio":
                    models_list = data.get("data", data.get("models", []))
                    result["models"] = [m.get("id", "?") for m in models_list]
                    result["loaded_models"] = sum(
                        1 for m in models_list if m.get("loaded_instances")
                    )
                elif cfg.backend == "ollama":
                    models_list = data.get("models", [])
                    result["models"] = [m.get("name", "?") for m in models_list]
                    result["loaded_models"] = len(models_list)
            except Exception as exc:
                logger.debug("Model query failed for %s: %s", cfg.name, exc)

        return result

    def get_cluster_resources(self) -> dict:
        """Query all nodes and return current cluster state."""
        resources: dict = {}
        for name, cfg in self._nodes.items():
            info = self._check_node_health(cfg)

            # Merge load info
            load_est = self._estimate_node_load(name)
            available = max(0, cfg.max_concurrent - load_est)
            circuit = self._is_circuit_open(name)

            info.update({
                "current_load_estimate": load_est,
                "available_capacity": available,
                "circuit_open": circuit,
                "weight": cfg.weight,
                "affinities": cfg.affinities,
            })
            resources[name] = info

        return resources

    # ------------------------------------------------------------------
    # Load estimation
    # ------------------------------------------------------------------

    def _estimate_node_load(self, node: str) -> int:
        """Estimate how many tasks are currently running on *node*.

        Uses a time-decayed count of recent allocations that haven't been
        completed (recorded) yet, plus an active counter.
        """
        now = time.monotonic()
        active = self._active.get(node, 0)

        # Also count recent un-completed allocations with decay
        with self._history_lock:
            recent = 0
            for rec in reversed(self._history):
                age = now - rec.timestamp
                if age > LOAD_DECAY_WINDOW_S:
                    break
                if rec.node == node:
                    # Decayed contribution
                    weight = 0.5 ** (age / LOAD_HALF_LIFE_S)
                    recent += weight

        # active count is the hard floor (tasks dispatched but not yet recorded)
        return max(active, int(round(recent)))

    # ------------------------------------------------------------------
    # Circuit breaker (lightweight)
    # ------------------------------------------------------------------

    def _is_circuit_open(self, node: str) -> bool:
        ts = self._circuit_open.get(node)
        if ts is None:
            return False
        if time.monotonic() - ts > self._circuit_cooldown_s:
            # Cooldown elapsed, half-open -> allow traffic
            del self._circuit_open[node]
            return False
        return True

    def _open_circuit(self, node: str) -> None:
        self._circuit_open[node] = time.monotonic()
        logger.warning("Circuit OPEN for node %s", node)

    # ------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------

    def allocate(self, task_type: str, priority: int = 5) -> str:
        """Pick the best node for *task_type* at the given *priority* (1-10, 10=highest).

        Returns the node name (e.g. "M1").  Raises RuntimeError if no node is available.
        """
        task_key = task_type.lower()
        preference_order = TASK_AFFINITY.get(task_key, list(self._nodes.keys()))

        candidates: list[tuple[float, str]] = []

        for node_name in preference_order:
            cfg = self._nodes.get(node_name)
            if cfg is None:
                continue

            # Skip circuit-broken nodes
            if self._is_circuit_open(node_name):
                continue

            # Quick socket probe for offline detection
            try:
                sock = socket.create_connection(
                    (cfg.host, cfg.port),
                    timeout=1.0,
                )
                sock.close()
            except (OSError, socket.timeout):
                continue

            load = self._estimate_node_load(node_name)
            available = cfg.max_concurrent - load

            if available <= 0:
                continue

            # Compute score — higher is better
            # Affinity bonus: position in preference list (first = best)
            try:
                affinity_rank = preference_order.index(node_name)
            except ValueError:
                affinity_rank = len(preference_order)
            affinity_bonus = max(0, 10 - affinity_rank * 2)

            # Capacity ratio bonus (prefer nodes with more headroom)
            capacity_ratio = available / cfg.max_concurrent

            # Weight bonus
            weight_bonus = cfg.weight

            # Priority boost: for high priority (>=8), heavily favor fast nodes (M1, OL1)
            priority_boost = 0.0
            if priority >= 8 and node_name in ("M1", "OL1"):
                priority_boost = 3.0
            elif priority >= 6 and node_name == "M1":
                priority_boost = 1.5

            score = (
                affinity_bonus * 2.0
                + capacity_ratio * 5.0
                + weight_bonus * 3.0
                + priority_boost
            )

            candidates.append((score, node_name))

        if not candidates:
            raise RuntimeError(
                f"No available node for task_type={task_type!r} priority={priority}. "
                "All nodes are offline, circuit-broken, or at capacity."
            )

        # Pick highest score
        candidates.sort(key=lambda x: x[0], reverse=True)
        chosen = candidates[0][1]

        # Track active allocation
        self._active[chosen] = self._active.get(chosen, 0) + 1

        logger.info(
            "Allocated %s -> %s (priority=%d, score=%.1f, candidates=%d)",
            task_type, chosen, priority, candidates[0][0], len(candidates),
        )

        return chosen

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_allocation(self, node: str, task_type: str, duration_ms: float) -> None:
        """Record a completed allocation for load tracking and stats."""
        now = time.monotonic()
        record = AllocationRecord(
            node=node,
            task_type=task_type,
            timestamp=now,
            duration_ms=duration_ms,
        )
        with self._history_lock:
            self._history.append(record)
            # Prune old records
            cutoff = now - LOAD_DECAY_WINDOW_S * 2
            self._history = [r for r in self._history if r.timestamp > cutoff]

        # Decrement active counter
        if self._active.get(node, 0) > 0:
            self._active[node] -= 1

        # Update cumulative stats
        stats = self._stats[node]
        stats["total_allocations"] += 1
        stats["total_duration_ms"] += duration_ms
        stats["avg_duration_ms"] = round(
            stats["total_duration_ms"] / stats["total_allocations"], 1
        )

        logger.debug(
            "Recorded allocation: %s on %s, %.0fms", task_type, node, duration_ms,
        )

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_load_report(self) -> dict:
        """Return current load distribution across all nodes."""
        report: dict = {
            "timestamp": time.time(),
            "nodes": {},
            "total_active": 0,
            "history_size": len(self._history),
        }

        for name, cfg in self._nodes.items():
            load = self._estimate_node_load(name)
            active = self._active.get(name, 0)
            stats = dict(self._stats[name])
            circuit = self._is_circuit_open(name)

            node_report = {
                "load_estimate": load,
                "active_tasks": active,
                "max_concurrent": cfg.max_concurrent,
                "utilization_pct": round(load / cfg.max_concurrent * 100, 1) if cfg.max_concurrent > 0 else 0,
                "circuit_open": circuit,
                "weight": cfg.weight,
                **stats,
            }
            report["nodes"][name] = node_report
            report["total_active"] += active

        return report

    # ------------------------------------------------------------------
    # Rebalancing
    # ------------------------------------------------------------------

    def rebalance(self) -> list[str]:
        """Check load distribution and suggest rebalancing actions.

        Returns a list of human-readable action suggestions.
        """
        actions: list[str] = []

        loads: dict[str, float] = {}
        for name, cfg in self._nodes.items():
            load = self._estimate_node_load(name)
            util = load / cfg.max_concurrent if cfg.max_concurrent > 0 else 0
            loads[name] = util

        if not loads:
            return ["No nodes configured."]

        avg_util = sum(loads.values()) / len(loads)

        for name, util in loads.items():
            cfg = self._nodes[name]

            # Node overloaded (>80% utilization)
            if util > 0.80:
                actions.append(
                    f"[HIGH LOAD] {name} at {util*100:.0f}% utilization "
                    f"({self._estimate_node_load(name)}/{cfg.max_concurrent}). "
                    f"Consider routing new tasks to less loaded nodes."
                )

            # Node idle while others are busy
            if util < 0.10 and avg_util > 0.40:
                actions.append(
                    f"[UNDERUSED] {name} at {util*100:.0f}% utilization while "
                    f"cluster average is {avg_util*100:.0f}%. "
                    f"Increase routing weight or add task affinities."
                )

            # Circuit breaker open
            if self._is_circuit_open(name):
                ts = self._circuit_open.get(name, 0)
                elapsed = time.monotonic() - ts
                remaining = max(0, self._circuit_cooldown_s - elapsed)
                actions.append(
                    f"[CIRCUIT OPEN] {name} is circuit-broken. "
                    f"Cooldown remaining: {remaining:.0f}s. "
                    f"Traffic rerouted to other nodes."
                )

        # Check for imbalance between online nodes
        online_utils = {
            n: u for n, u in loads.items()
            if not self._is_circuit_open(n)
        }
        if len(online_utils) >= 2:
            max_u = max(online_utils.values())
            min_u = min(online_utils.values())
            if max_u - min_u > 0.50:
                busiest = max(online_utils, key=online_utils.get)
                lightest = min(online_utils, key=online_utils.get)
                actions.append(
                    f"[IMBALANCE] {busiest} ({max_u*100:.0f}%) vs "
                    f"{lightest} ({min_u*100:.0f}%). "
                    f"Spread of {(max_u - min_u)*100:.0f}% exceeds threshold. "
                    f"Consider adjusting weights or affinities."
                )

        if not actions:
            actions.append("Cluster load is balanced. No action needed.")

        return actions


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

resource_allocator = ResourceAllocator()
