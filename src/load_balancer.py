"""JARVIS Load Balancer — Intelligent request distribution across cluster nodes.

Uses weighted round-robin with dynamic scoring to prevent overloading a single node.
Integrates with orchestrator_v2 for metrics and drift detection.

Usage:
    from src.load_balancer import load_balancer
    node = load_balancer.pick("code")           # best node for code task
    load_balancer.report(node, 120.0, True, 50)  # report call result
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any

logger = logging.getLogger("jarvis.lb")


class LoadBalancer:
    """Weighted round-robin load balancer with dynamic scoring."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: dict[str, int] = defaultdict(int)  # round-robin counters
        self._active: dict[str, int] = defaultdict(int)     # active requests per node
        self._recent_failures: dict[str, list[float]] = defaultdict(list)  # failure timestamps
        self._max_concurrent = 3  # max parallel requests per node
        self._failure_window_s = 300.0  # 5 min failure window
        self._failure_threshold = 5  # trips circuit breaker

    def pick(self, task_type: str = "code", exclude: set[str] | None = None) -> str:
        """Pick the best node for a task type.

        Pipeline:
        1. Get candidates from orchestrator_v2 routing matrix
        2. Filter out circuit-broken nodes
        3. Filter out overloaded nodes (active >= max_concurrent)
        4. Weighted round-robin from remaining
        """
        exclude = exclude or set()

        # Get candidates with weights
        try:
            from src.orchestrator_v2 import orchestrator_v2, ROUTING_MATRIX
            matrix_entry = ROUTING_MATRIX.get(task_type, ROUTING_MATRIX.get("simple", []))
            candidates = [(n, w) for n, w in matrix_entry if n not in exclude]
        except Exception:
            candidates = [("M1", 1.8), ("OL1", 1.3)]

        if not candidates:
            return "M1"

        with self._lock:
            # Filter circuit-broken
            now = time.time()
            viable = []
            for node, weight in candidates:
                failures = [t for t in self._recent_failures.get(node, [])
                            if (now - t) < self._failure_window_s]
                self._recent_failures[node] = failures  # cleanup
                if len(failures) >= self._failure_threshold:
                    logger.debug("LB: %s circuit-broken (%d failures)", node, len(failures))
                    continue
                viable.append((node, weight))

            if not viable:
                viable = list(candidates)  # fallback: ignore circuit breaker

            # Filter overloaded
            available = [(n, w) for n, w in viable if self._active[n] < self._max_concurrent]
            if not available:
                available = viable  # all overloaded, pick least loaded

            # Get orchestrator scores for fine-tuning
            try:
                scored = []
                for node, weight in available:
                    orch_score = orchestrator_v2.weighted_score(node, task_type)
                    active_penalty = 1.0 / (1 + self._active[node])
                    final_score = orch_score * active_penalty
                    scored.append((node, final_score))
                scored.sort(key=lambda x: x[1], reverse=True)

                # Weighted round-robin among top candidates
                if scored:
                    selected = scored[0][0]
                    self._counters[selected] += 1
                    self._active[selected] += 1
                    return selected
            except Exception:
                pass

            # Simple fallback
            node = available[0][0]
            self._active[node] += 1
            return node

    def release(self, node: str) -> None:
        """Release a node after request completes."""
        with self._lock:
            self._active[node] = max(0, self._active[node] - 1)

    def report(self, node: str, latency_ms: float, success: bool, tokens: int = 0) -> None:
        """Report a call result. Records in both LB and orchestrator_v2."""
        with self._lock:
            self._active[node] = max(0, self._active[node] - 1)
            if not success:
                self._recent_failures[node].append(time.time())

        # Forward to orchestrator_v2
        try:
            from src.orchestrator_v2 import orchestrator_v2
            orchestrator_v2.record_call(node, latency_ms, success, tokens)
        except Exception:
            pass

    def get_status(self) -> dict[str, Any]:
        """Current LB status."""
        with self._lock:
            now = time.time()
            nodes = {}
            all_nodes = set(self._counters.keys()) | set(self._active.keys()) | set(self._recent_failures.keys())
            for node in all_nodes:
                failures = [t for t in self._recent_failures.get(node, [])
                            if (now - t) < self._failure_window_s]
                nodes[node] = {
                    "active_requests": self._active.get(node, 0),
                    "total_picks": self._counters.get(node, 0),
                    "recent_failures": len(failures),
                    "circuit_broken": len(failures) >= self._failure_threshold,
                }
            return {
                "nodes": nodes,
                "max_concurrent": self._max_concurrent,
                "failure_threshold": self._failure_threshold,
                "failure_window_s": self._failure_window_s,
            }

    def reset(self) -> None:
        """Reset all counters."""
        with self._lock:
            self._counters.clear()
            self._active.clear()
            self._recent_failures.clear()


# Global singleton
load_balancer = LoadBalancer()
