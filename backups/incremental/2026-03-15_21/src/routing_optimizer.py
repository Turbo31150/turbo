"""JARVIS Routing Optimizer — Real-time adaptive routing.

Monitors dispatch performance and dynamically adjusts:
  - Node concurrency limits per node
  - Timeout values per node
  - System prompt injection (skip for tiny tasks)
  - Token limits per task size
  - Fallback chains based on node health

Auto-learns from dispatch_log and provides recommendations.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


__all__ = [
    "NodeProfile",
    "RoutingOptimizer",
    "TaskProfile",
]

logger = logging.getLogger("jarvis.routing_optimizer")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")


@dataclass
class NodeProfile:
    """Runtime profile for a node."""
    name: str
    avg_latency_ms: float = 0
    p50_ms: float = 0
    p95_ms: float = 0
    throughput_rps: float = 0
    success_rate: float = 1.0
    concurrent_limit: int = 3
    optimal_timeout_s: float = 30
    total_requests: int = 0
    last_healthy: float = 0
    health_score: float = 1.0  # 0-1

    @property
    def is_healthy(self) -> bool:
        return self.health_score > 0.5 and self.success_rate > 0.7


@dataclass
class TaskProfile:
    """Optimal routing config for a task size/pattern."""
    pattern: str
    size: str  # nano, micro, small, medium, large, xl
    optimal_node: str = "M1"
    optimal_timeout_s: float = 30
    max_tokens: int = 512
    inject_system_prompt: bool = True
    avg_latency_ms: float = 0


class RoutingOptimizer:
    """Auto-optimizes routing parameters from dispatch history."""

    # Default concurrency per node type
    DEFAULT_CONCURRENCY = {
        "M1": 4, "M2": 2, "M3": 1,
        "OL1": 3,
    }

    # Task size -> max_tokens mapping
    SIZE_TOKENS = {
        "nano": 64, "micro": 128, "small": 256,
        "medium": 512, "large": 1024, "xl": 2048,
    }

    # Task size -> should inject system prompt
    SIZE_SYSTEM_PROMPT = {
        "nano": False, "micro": False, "small": True,
        "medium": True, "large": True, "xl": True,
    }

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._node_profiles: dict[str, NodeProfile] = {}
        self._task_profiles: dict[str, TaskProfile] = {}
        self._last_refresh = 0
        self._refresh_interval = 30  # seconds

    def get_node_profile(self, node: str) -> NodeProfile:
        self._maybe_refresh()
        return self._node_profiles.get(node, NodeProfile(name=node))

    def get_task_profile(self, pattern: str, size: str = "medium") -> TaskProfile:
        self._maybe_refresh()
        key = f"{pattern}:{size}"
        if key in self._task_profiles:
            return self._task_profiles[key]
        # Default
        return TaskProfile(
            pattern=pattern, size=size,
            max_tokens=self.SIZE_TOKENS.get(size, 512),
            inject_system_prompt=self.SIZE_SYSTEM_PROMPT.get(size, True),
        )

    def get_optimal_config(self, pattern: str, prompt: str) -> dict:
        """Get optimal routing config for a dispatch."""
        # Estimate size from prompt length
        words = len(prompt.split())
        if words <= 3:
            size = "nano"
        elif words <= 10:
            size = "micro"
        elif words <= 25:
            size = "small"
        elif words <= 60:
            size = "medium"
        elif words <= 120:
            size = "large"
        else:
            size = "xl"

        tp = self.get_task_profile(pattern, size)
        np = self.get_node_profile(tp.optimal_node)

        return {
            "node": tp.optimal_node,
            "timeout_s": tp.optimal_timeout_s,
            "max_tokens": tp.max_tokens,
            "inject_system_prompt": tp.inject_system_prompt,
            "concurrent_limit": np.concurrent_limit,
            "estimated_latency_ms": tp.avg_latency_ms or np.avg_latency_ms,
            "health_score": np.health_score,
        }

    def get_recommendations(self) -> list[dict]:
        """Generate optimization recommendations."""
        self._maybe_refresh()
        recs = []

        for name, np in self._node_profiles.items():
            if np.success_rate < 0.8 and np.total_requests > 10:
                recs.append({
                    "type": "node_health",
                    "node": name,
                    "severity": "high" if np.success_rate < 0.5 else "medium",
                    "message": f"{name} has {np.success_rate:.0%} success rate ({np.total_requests} reqs). Consider reducing load or checking node health.",
                })

            if np.p95_ms > 30000 and np.total_requests > 5:
                recs.append({
                    "type": "latency",
                    "node": name,
                    "severity": "medium",
                    "message": f"{name} P95 latency is {np.p95_ms:.0f}ms. Consider increasing timeout or reducing concurrency.",
                })

        # Check for imbalanced load
        if self._node_profiles:
            loads = [(n, p.total_requests) for n, p in self._node_profiles.items()]
            max_load = max(l for _, l in loads)
            min_load = min(l for _, l in loads) if len(loads) > 1 else max_load
            if max_load > 3 * min_load and max_load > 20:
                heavy = max(loads, key=lambda x: x[1])
                light = min(loads, key=lambda x: x[1])
                recs.append({
                    "type": "load_balance",
                    "severity": "low",
                    "message": f"Load imbalance: {heavy[0]} has {heavy[1]} reqs vs {light[0]} with {light[1]}. Consider rebalancing.",
                })

        return recs

    def _maybe_refresh(self):
        now = time.time()
        if now - self._last_refresh < self._refresh_interval:
            return

        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row

            # Node profiles from dispatch_log
            node_stats = db.execute("""
                SELECT node,
                       COUNT(*) as total,
                       AVG(latency_ms) as avg_ms,
                       AVG(success) as rate,
                       MAX(latency_ms) as max_ms
                FROM agent_dispatch_log
                WHERE node IS NOT NULL
                GROUP BY node
            """).fetchall()

            self._node_profiles.clear()
            for s in node_stats:
                name = s["node"]
                self._node_profiles[name] = NodeProfile(
                    name=name,
                    avg_latency_ms=s["avg_ms"] or 0,
                    p95_ms=(s["max_ms"] or 0) * 0.8,  # approximation
                    success_rate=s["rate"] or 0,
                    total_requests=s["total"],
                    concurrent_limit=self.DEFAULT_CONCURRENCY.get(name, 2),
                    optimal_timeout_s=max(10, min(120, (s["avg_ms"] or 10000) / 1000 * 3)),
                    health_score=min(1.0, (s["rate"] or 0) * (1 - min(1, (s["avg_ms"] or 0) / 60000))),
                )

            # Task profiles
            task_stats = db.execute("""
                SELECT classified_type, node,
                       COUNT(*) as cnt,
                       AVG(latency_ms) as avg_ms,
                       AVG(success) as rate
                FROM agent_dispatch_log
                WHERE classified_type IS NOT NULL AND success = 1
                GROUP BY classified_type, node
                ORDER BY classified_type, avg_ms ASC
            """).fetchall()

            # Pick best node per pattern
            best_per_pattern = {}
            for s in task_stats:
                pat = s["classified_type"]
                if pat not in best_per_pattern or s["avg_ms"] < best_per_pattern[pat]["avg_ms"]:
                    best_per_pattern[pat] = {"node": s["node"], "avg_ms": s["avg_ms"]}

            self._task_profiles.clear()
            for pat, info in best_per_pattern.items():
                for size in self.SIZE_TOKENS:
                    key = f"{pat}:{size}"
                    self._task_profiles[key] = TaskProfile(
                        pattern=pat, size=size,
                        optimal_node=info["node"],
                        optimal_timeout_s=max(10, info["avg_ms"] / 1000 * 3),
                        max_tokens=self.SIZE_TOKENS[size],
                        inject_system_prompt=self.SIZE_SYSTEM_PROMPT[size],
                        avg_latency_ms=info["avg_ms"],
                    )

            db.close()
            self._last_refresh = now

        except sqlite3.Error as e:
            logger.warning(f"Routing optimizer refresh failed: {e}")

    def report(self) -> dict:
        """Full routing optimization report."""
        self._maybe_refresh()
        return {
            "nodes": {n: {
                "avg_ms": round(p.avg_latency_ms),
                "rate": f"{p.success_rate:.0%}",
                "requests": p.total_requests,
                "health": round(p.health_score, 2),
                "concurrency": p.concurrent_limit,
                "timeout_s": round(p.optimal_timeout_s),
            } for n, p in self._node_profiles.items()},
            "recommendations": self.get_recommendations(),
            "task_profiles": {k: {
                "node": v.optimal_node,
                "max_tokens": v.max_tokens,
                "timeout_s": round(v.optimal_timeout_s),
                "system_prompt": v.inject_system_prompt,
            } for k, v in self._task_profiles.items()},
        }


# CLI
if __name__ == "__main__":
    import json
    opt = RoutingOptimizer()
    print(json.dumps(opt.report(), indent=2, ensure_ascii=False))
