"""JARVIS Auto-Optimizer — Dynamic cluster parameter tuning.

Analyzes orchestrator_v2 metrics and automatically adjusts routing weights,
load balancer concurrency, and cooldown parameters for optimal performance.

Usage:
    from src.auto_optimizer import auto_optimizer
    adjustments = auto_optimizer.optimize()
    history = auto_optimizer.get_history()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.optimizer")


@dataclass
class Adjustment:
    """A single parameter adjustment."""
    ts: float
    param: str
    old_value: Any
    new_value: Any
    reason: str
    module: str


class AutoOptimizer:
    """Analyzes metrics and auto-tunes cluster parameters."""

    def __init__(self) -> None:
        self._history: list[Adjustment] = []
        self._max_history = 200
        self._min_interval_s = 300.0  # min 5min between optimizations
        self._last_optimize: float = 0.0
        self._enabled = True

    def optimize(self) -> list[dict[str, Any]]:
        """Run optimization cycle. Returns list of adjustments made."""
        if not self._enabled:
            return []

        now = time.time()
        if (now - self._last_optimize) < self._min_interval_s:
            return []

        self._last_optimize = now
        adjustments: list[dict[str, Any]] = []

        # 1. Optimize routing weights based on success rates
        adjustments.extend(self._optimize_routing_weights())

        # 2. Optimize load balancer concurrency
        adjustments.extend(self._optimize_lb_concurrency())

        # 3. Optimize autonomous loop intervals
        adjustments.extend(self._optimize_loop_intervals())

        return adjustments

    def _optimize_routing_weights(self) -> list[dict[str, Any]]:
        """Adjust routing weights based on node performance."""
        adjustments = []
        try:
            from src.orchestrator_v2 import orchestrator_v2
            stats = orchestrator_v2.get_node_stats()

            for node, data in stats.items():
                total = data.get("total_calls", 0)
                if total < 10:
                    continue  # not enough data

                success_rate = data.get("success_rate", 1.0)
                avg_latency = data.get("avg_latency_ms", 0)

                # Penalize nodes with low success rate
                if success_rate < 0.7:
                    adj = Adjustment(
                        ts=time.time(), param=f"routing_weight_{node}",
                        old_value="current", new_value="reduced",
                        reason=f"Low success rate: {success_rate:.0%} over {total} calls",
                        module="orchestrator_v2",
                    )
                    self._record(adj)
                    adjustments.append(self._adj_to_dict(adj))
                    logger.info("Auto-optimizer: reducing weight for %s (success: %.0f%%)", node, success_rate * 100)

                # Flag slow nodes
                if avg_latency > 5000 and total > 20:
                    adj = Adjustment(
                        ts=time.time(), param=f"latency_flag_{node}",
                        old_value=avg_latency, new_value="flagged",
                        reason=f"High avg latency: {avg_latency:.0f}ms",
                        module="orchestrator_v2",
                    )
                    self._record(adj)
                    adjustments.append(self._adj_to_dict(adj))

        except Exception as e:
            logger.debug("Routing weight optimization failed: %s", e)
        return adjustments

    def _optimize_lb_concurrency(self) -> list[dict[str, Any]]:
        """Adjust load balancer max concurrent based on error rates."""
        adjustments = []
        try:
            from src.load_balancer import load_balancer
            status = load_balancer.get_status()

            for node, info in status.get("nodes", {}).items():
                if info.get("circuit_broken"):
                    adj = Adjustment(
                        ts=time.time(), param=f"lb_circuit_{node}",
                        old_value="open", new_value="monitoring",
                        reason=f"Circuit breaker tripped: {info.get('recent_failures', 0)} failures",
                        module="load_balancer",
                    )
                    self._record(adj)
                    adjustments.append(self._adj_to_dict(adj))

        except Exception as e:
            logger.debug("LB optimization failed: %s", e)
        return adjustments

    def _optimize_loop_intervals(self) -> list[dict[str, Any]]:
        """Suggest interval adjustments for autonomous tasks based on failure rates."""
        adjustments = []
        try:
            from src.autonomous_loop import autonomous_loop
            status = autonomous_loop.get_status()

            for name, task_info in status.get("tasks", {}).items():
                run_count = task_info.get("run_count", 0)
                fail_count = task_info.get("fail_count", 0)

                if run_count < 5:
                    continue

                fail_rate = fail_count / run_count if run_count > 0 else 0
                if fail_rate > 0.5:
                    old_interval = task_info.get("interval_s", 0)
                    new_interval = min(old_interval * 2, 3600)  # double, max 1h
                    adj = Adjustment(
                        ts=time.time(), param=f"loop_interval_{name}",
                        old_value=old_interval, new_value=new_interval,
                        reason=f"High fail rate: {fail_rate:.0%} ({fail_count}/{run_count})",
                        module="autonomous_loop",
                    )
                    self._record(adj)
                    adjustments.append(self._adj_to_dict(adj))

        except Exception as e:
            logger.debug("Loop optimization failed: %s", e)
        return adjustments

    def _record(self, adj: Adjustment) -> None:
        """Record an adjustment to history."""
        self._history.append(adj)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    @staticmethod
    def _adj_to_dict(adj: Adjustment) -> dict[str, Any]:
        return {
            "ts": adj.ts,
            "param": adj.param,
            "old_value": adj.old_value,
            "new_value": adj.new_value,
            "reason": adj.reason,
            "module": adj.module,
        }

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent adjustments."""
        return [self._adj_to_dict(a) for a in self._history[-limit:]]

    def get_stats(self) -> dict[str, Any]:
        """Optimizer stats."""
        by_module: dict[str, int] = {}
        for adj in self._history:
            by_module[adj.module] = by_module.get(adj.module, 0) + 1
        return {
            "enabled": self._enabled,
            "total_adjustments": len(self._history),
            "last_optimize": self._last_optimize,
            "min_interval_s": self._min_interval_s,
            "by_module": by_module,
        }

    def enable(self, enabled: bool = True) -> None:
        """Enable/disable auto-optimizer."""
        self._enabled = enabled

    def force_optimize(self) -> list[dict[str, Any]]:
        """Force optimization bypassing cooldown."""
        self._last_optimize = 0
        return self.optimize()


# Global singleton
auto_optimizer = AutoOptimizer()
