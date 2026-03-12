"""JARVIS Metrics Aggregator — Unified real-time metrics from all modules.

Collects metrics from orchestrator, LB, memory, conversations, autonomous loop,
and proactive agent into a single endpoint. Keeps 1h history with 10s sampling.

Usage:
    from src.metrics_aggregator import metrics_aggregator
    snapshot = metrics_aggregator.snapshot()
    history = metrics_aggregator.get_history(minutes=30)
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

logger = logging.getLogger("jarvis.metrics")

# 1 hour of history at 10s intervals = 360 samples
MAX_SAMPLES = 360
SAMPLE_INTERVAL_S = 10.0


class MetricsAggregator:
    """Collects and aggregates metrics from all JARVIS modules."""

    def __init__(self) -> None:
        self._history: deque[dict[str, Any]] = deque(maxlen=MAX_SAMPLES)
        self._last_sample: float = 0.0

    def snapshot(self) -> dict[str, Any]:
        """Take a snapshot of all current metrics."""
        now = time.time()
        snap: dict[str, Any] = {"ts": now}

        # Orchestrator V2
        try:
            from src.orchestrator_v2 import orchestrator_v2
            health = orchestrator_v2.health_check()
            budget = orchestrator_v2.get_budget_report()
            node_stats = orchestrator_v2.get_node_stats()
            snap["orchestrator"] = {
                "health_score": health,
                "total_tokens": budget.get("total_tokens", 0),
                "total_calls": budget.get("total_calls", 0),
                "tokens_per_minute": budget.get("tokens_per_minute", 0),
                "active_nodes": len(node_stats),
            }
        except Exception:
            snap["orchestrator"] = {"health_score": 0, "error": True}

        # Load Balancer
        try:
            from src.load_balancer import load_balancer
            lb_status = load_balancer.get_status()
            nodes = lb_status.get("nodes", {})
            total_active = sum(n.get("active_requests", 0) for n in nodes.values())
            circuit_broken = sum(1 for n in nodes.values() if n.get("circuit_broken"))
            snap["load_balancer"] = {
                "active_requests": total_active,
                "circuit_broken_nodes": circuit_broken,
                "total_nodes": len(nodes),
            }
        except Exception:
            snap["load_balancer"] = {"error": True}

        # Autonomous Loop
        try:
            from src.autonomous_loop import autonomous_loop
            loop_status = autonomous_loop.get_status()
            tasks = loop_status.get("tasks", {})
            total_runs = sum(t.get("run_count", 0) for t in tasks.values())
            total_fails = sum(t.get("fail_count", 0) for t in tasks.values())
            snap["autonomous_loop"] = {
                "running": loop_status.get("running", False),
                "task_count": len(tasks),
                "total_runs": total_runs,
                "total_fails": total_fails,
                "event_count": loop_status.get("event_count", 0),
            }
        except Exception:
            snap["autonomous_loop"] = {"error": True}

        # Agent Memory
        try:
            from src.agent_memory import agent_memory
            mem_stats = agent_memory.get_stats()
            snap["agent_memory"] = {
                "total_memories": mem_stats.get("total", 0),
                "categories": len(mem_stats.get("categories", {})),
            }
        except Exception:
            snap["agent_memory"] = {"error": True}

        # Conversations
        try:
            from src.conversation_store import conversation_store
            conv_stats = conversation_store.get_stats()
            snap["conversations"] = {
                "total_conversations": conv_stats.get("total_conversations", 0),
                "total_turns": conv_stats.get("total_turns", 0),
                "total_tokens": conv_stats.get("total_tokens", 0),
                "avg_latency_ms": conv_stats.get("avg_latency_ms", 0),
            }
        except Exception:
            snap["conversations"] = {"error": True}

        # Proactive Agent
        try:
            from src.proactive_agent import proactive_agent
            pa_stats = proactive_agent.get_stats()
            snap["proactive"] = {
                "last_suggestions": pa_stats.get("last_suggestions_count", 0),
                "dismissed": pa_stats.get("dismissed_count", 0),
            }
        except Exception:
            snap["proactive"] = {"error": True}

        # Auto-Optimizer
        try:
            from src.auto_optimizer import auto_optimizer
            opt_stats = auto_optimizer.get_stats()
            snap["optimizer"] = {
                "total_adjustments": opt_stats.get("total_adjustments", 0),
                "enabled": opt_stats.get("enabled", False),
            }
        except Exception:
            snap["optimizer"] = {"error": True}

        # Event Bus
        try:
            from src.event_bus import event_bus
            eb_stats = event_bus.get_stats()
            snap["event_bus"] = {
                "subscriptions": eb_stats.get("total_subscriptions", 0),
                "total_events": eb_stats.get("total_events_emitted", 0),
            }
        except Exception:
            snap["event_bus"] = {"error": True}

        return snap

    def sample(self) -> dict[str, Any] | None:
        """Take a sample if enough time has elapsed. Returns snapshot or None."""
        now = time.time()
        if (now - self._last_sample) < SAMPLE_INTERVAL_S:
            return None
        self._last_sample = now
        snap = self.snapshot()
        self._history.append(snap)
        return snap

    def get_history(self, minutes: int = 60) -> list[dict[str, Any]]:
        """Return samples from the last N minutes."""
        cutoff = time.time() - (minutes * 60)
        return [s for s in self._history if s.get("ts", 0) >= cutoff]

    def get_latest(self) -> dict[str, Any] | None:
        """Return the most recent sample."""
        return self._history[-1] if self._history else None

    def get_summary(self) -> dict[str, Any]:
        """Summary of aggregator state."""
        return {
            "sample_count": len(self._history),
            "max_samples": MAX_SAMPLES,
            "sample_interval_s": SAMPLE_INTERVAL_S,
            "last_sample_ts": self._last_sample,
        }


# Global singleton
metrics_aggregator = MetricsAggregator()
