"""JARVIS Auto Scaler — Dynamic model and resource management.

Monitors load patterns and automatically:
  - Detects overloaded nodes (queue depth, latency spikes)
  - Suggests/executes model swaps (load heavier model when needed)
  - Adjusts parallelism settings
  - Redistributes traffic between nodes
  - Scales down idle resources

Usage:
    from src.agent_auto_scaler import AutoScaler, get_scaler
    scaler = get_scaler()
    actions = await scaler.evaluate()
    await scaler.execute_actions(actions)
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
    "AutoScaler",
    "LoadMetrics",
    "ScaleAction",
    "ScalePolicy",
    "get_scaler",
]

logger = logging.getLogger("jarvis.auto_scaler")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")


@dataclass
class LoadMetrics:
    """Current load metrics for a node."""
    node: str
    active_requests: int = 0
    avg_latency_ms: float = 0
    p95_latency_ms: float = 0
    error_rate: float = 0
    requests_last_5min: int = 0
    requests_last_1h: int = 0
    queue_depth: int = 0
    model_loaded: str = ""


@dataclass
class ScaleAction:
    """A scaling action to take."""
    action_type: str     # scale_up, scale_down, redistribute, swap_model, adjust_parallelism
    target_node: str
    description: str
    priority: int        # 1=critical, 2=high, 3=medium, 4=low
    params: dict = field(default_factory=dict)
    auto_executable: bool = False


@dataclass
class ScalePolicy:
    """Scaling thresholds and policies."""
    latency_warning_ms: float = 5000
    latency_critical_ms: float = 15000
    error_rate_warning: float = 0.2
    error_rate_critical: float = 0.5
    max_active_per_node: int = 5
    idle_timeout_min: float = 30
    min_requests_for_action: int = 10
    cooldown_s: float = 300  # 5min between actions on same node


class AutoScaler:
    """Monitors load and manages scaling decisions."""

    # Node capabilities
    NODE_CAPABILITIES = {
        "M1": {"gpu_gb": 46, "max_parallel": 5, "models": ["qwen3-8b", "qwen3-30b"]},
        "M2": {"gpu_gb": 24, "max_parallel": 2, "models": ["deepseek-r1-0528-qwen3-8b"]},
        "M3": {"gpu_gb": 8, "max_parallel": 1, "models": ["deepseek-r1-0528-qwen3-8b"]},
        "OL1": {"gpu_gb": 0, "max_parallel": 3, "models": ["qwen3:1.7b", "qwen3:14b"]},
    }

    # Model tiers (for swap decisions)
    MODEL_TIERS = {
        "fast": ["qwen3:1.7b", "qwen3-8b"],
        "balanced": ["qwen3:14b", "qwen3-8b"],
        "deep": ["qwen3-30b", "deepseek-r1-0528-qwen3-8b"],
    }

    def __init__(self, policy: Optional[ScalePolicy] = None):
        self.policy = policy or ScalePolicy()
        self._last_actions: dict[str, float] = {}  # node -> timestamp of last action
        self._ensure_table()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                CREATE TABLE IF NOT EXISTS auto_scale_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT, target_node TEXT,
                    description TEXT, priority INTEGER,
                    executed INTEGER DEFAULT 0,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to create auto_scale_log: {e}")

    def get_load_metrics(self) -> dict[str, LoadMetrics]:
        """Collect current load metrics from dispatch history."""
        metrics = {}
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            # Recent stats per node
            rows = db.execute("""
                SELECT node,
                       COUNT(*) as total,
                       AVG(latency_ms) as avg_lat,
                       SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as errors,
                       SUM(CASE WHEN timestamp > datetime('now', '-5 minutes') THEN 1 ELSE 0 END) as last_5min,
                       SUM(CASE WHEN timestamp > datetime('now', '-1 hour') THEN 1 ELSE 0 END) as last_1h
                FROM agent_dispatch_log
                WHERE timestamp > datetime('now', '-2 hours')
                GROUP BY node
            """).fetchall()

            # P95 latency per node
            for r in rows:
                node = r["node"]
                if not node:
                    continue

                # Get p95
                lats = db.execute("""
                    SELECT latency_ms FROM agent_dispatch_log
                    WHERE node = ? AND timestamp > datetime('now', '-1 hour')
                    AND latency_ms IS NOT NULL
                    ORDER BY latency_ms
                """, (node,)).fetchall()

                p95 = 0
                if lats:
                    idx = int(len(lats) * 0.95)
                    p95 = lats[min(idx, len(lats)-1)][0] or 0

                metrics[node] = LoadMetrics(
                    node=node,
                    avg_latency_ms=r["avg_lat"] or 0,
                    p95_latency_ms=p95,
                    error_rate=r["errors"] / max(1, r["total"]),
                    requests_last_5min=r["last_5min"] or 0,
                    requests_last_1h=r["last_1h"] or 0,
                )

            db.close()
        except Exception as e:
            logger.warning(f"Failed to get load metrics: {e}")

        return metrics

    def evaluate(self) -> list[ScaleAction]:
        """Evaluate current state and suggest scaling actions."""
        actions = []
        metrics = self.get_load_metrics()
        now = time.time()

        for node, m in metrics.items():
            # Cooldown check
            last_action = self._last_actions.get(node, 0)
            if now - last_action < self.policy.cooldown_s:
                continue

            # Critical latency
            if m.p95_latency_ms > self.policy.latency_critical_ms:
                actions.append(ScaleAction(
                    action_type="redistribute",
                    target_node=node,
                    description=f"{node}: P95 latency {m.p95_latency_ms:.0f}ms (critical >{self.policy.latency_critical_ms}ms). Redistribute traffic.",
                    priority=1,
                    params={"reason": "latency_critical", "p95": m.p95_latency_ms},
                ))

            # High error rate
            elif m.error_rate > self.policy.error_rate_critical:
                actions.append(ScaleAction(
                    action_type="scale_down",
                    target_node=node,
                    description=f"{node}: Error rate {m.error_rate:.0%} (critical). Reduce or disable traffic.",
                    priority=1,
                    params={"reason": "error_critical", "error_rate": m.error_rate},
                ))

            # Warning latency
            elif m.p95_latency_ms > self.policy.latency_warning_ms:
                # Check if we can swap to a faster model
                cap = self.NODE_CAPABILITIES.get(node, {})
                fast_models = [mod for mod in cap.get("models", []) if mod in self.MODEL_TIERS.get("fast", [])]
                if fast_models:
                    actions.append(ScaleAction(
                        action_type="swap_model",
                        target_node=node,
                        description=f"{node}: High latency ({m.p95_latency_ms:.0f}ms). Consider faster model: {fast_models[0]}",
                        priority=3,
                        params={"suggested_model": fast_models[0]},
                    ))

            # Warning error rate
            elif m.error_rate > self.policy.error_rate_warning:
                actions.append(ScaleAction(
                    action_type="redistribute",
                    target_node=node,
                    description=f"{node}: Error rate {m.error_rate:.0%} (warning). Shift some traffic.",
                    priority=2,
                    params={"reason": "error_warning"},
                ))

            # Overloaded (too many requests in 5min)
            cap = self.NODE_CAPABILITIES.get(node, {})
            max_p = cap.get("max_parallel", 3)
            if m.requests_last_5min > max_p * 10:
                actions.append(ScaleAction(
                    action_type="adjust_parallelism",
                    target_node=node,
                    description=f"{node}: {m.requests_last_5min} reqs/5min (high). Consider parallelism adjustment.",
                    priority=3,
                    params={"current_max": max_p, "requests_5min": m.requests_last_5min},
                ))

            # Idle detection
            if m.requests_last_1h == 0 and node not in ("M1", "OL1"):
                actions.append(ScaleAction(
                    action_type="scale_down",
                    target_node=node,
                    description=f"{node}: Idle (0 requests/1h). Consider unloading model.",
                    priority=4,
                    params={"reason": "idle"},
                ))

        # Cloud scale-up opportunity
        total_5min = sum(m.requests_last_5min for m in metrics.values())
        if total_5min > 20:
            actions.append(ScaleAction(
                action_type="scale_up",
                target_node="cloud",
                description=f"High total load ({total_5min} reqs/5min). Consider enabling cloud models.",
                priority=3,
                params={"total_5min": total_5min,
                        "cloud_models": []},
            ))

        return sorted(actions, key=lambda a: a.priority)

    async def execute_actions(self, actions: list[ScaleAction]) -> list[dict]:
        """Execute auto-scaling actions. Returns results."""
        results = []
        for action in actions:
            if action.priority > 2:
                # Only auto-execute critical/high priority
                results.append({
                    "action": action.action_type,
                    "node": action.target_node,
                    "status": "suggested",
                    "description": action.description,
                })
                continue

            # Execute critical actions
            try:
                if action.action_type == "redistribute":
                    # Update router weights
                    result = self._redistribute(action)
                elif action.action_type == "scale_down":
                    result = self._scale_down(action)
                else:
                    result = {"status": "skipped", "reason": "no_handler"}

                result["action"] = action.action_type
                result["node"] = action.target_node
                results.append(result)

                self._last_actions[action.target_node] = time.time()

            except Exception as e:
                results.append({
                    "action": action.action_type,
                    "node": action.target_node,
                    "status": "error",
                    "error": str(e),
                })

            # Log
            self._log_action(action, results[-1].get("status", "unknown"))

        return results

    def _redistribute(self, action: ScaleAction) -> dict:
        """Redistribute traffic away from a struggling node."""
        try:
            from src.adaptive_router import get_router
            router = get_router()
            # Record a synthetic failure to lower the node's score
            router.record(action.target_node, success=False, latency_ms=99999, pattern="__autoscaler__")
            return {"status": "executed", "description": f"Lowered weight for {action.target_node}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _scale_down(self, action: ScaleAction) -> dict:
        """Scale down a node (disable in router)."""
        try:
            from src.adaptive_router import get_router
            router = get_router()
            # Record multiple failures to trip circuit breaker
            for _ in range(6):
                router.record(action.target_node, success=False, latency_ms=99999, pattern="__autoscaler__")
            return {"status": "executed", "description": f"Tripped circuit breaker for {action.target_node}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _log_action(self, action: ScaleAction, status: str):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                INSERT INTO auto_scale_log
                (action_type, target_node, description, priority, executed)
                VALUES (?, ?, ?, ?, ?)
            """, (action.action_type, action.target_node, action.description,
                  action.priority, int(status == "executed")))
            db.commit()
            db.close()
        except Exception:
            pass

    def get_scaling_history(self, limit: int = 50) -> list[dict]:
        """Get recent scaling actions."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT * FROM auto_scale_log ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            db.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_capacity_report(self) -> dict:
        """Get cluster capacity report."""
        metrics = self.get_load_metrics()
        total_gpu = sum(c.get("gpu_gb", 0) for c in self.NODE_CAPABILITIES.values())
        active_nodes = [n for n, m in metrics.items() if m.requests_last_1h > 0]

        return {
            "cluster": {
                "total_gpu_gb": total_gpu,
                "total_nodes": len(self.NODE_CAPABILITIES),
                "active_nodes": len(active_nodes),
                "active_list": active_nodes,
            },
            "nodes": {
                node: {
                    "capabilities": self.NODE_CAPABILITIES.get(node, {}),
                    "load": {
                        "avg_latency_ms": round(m.avg_latency_ms, 1),
                        "p95_latency_ms": round(m.p95_latency_ms, 1),
                        "error_rate": round(m.error_rate, 3),
                        "requests_5min": m.requests_last_5min,
                        "requests_1h": m.requests_last_1h,
                    },
                    "status": (
                        "critical" if m.error_rate > self.policy.error_rate_critical
                        else "warning" if m.p95_latency_ms > self.policy.latency_warning_ms
                        else "healthy" if m.requests_last_1h > 0
                        else "idle"
                    ),
                }
                for node, m in metrics.items()
            },
            "recommendations": [
                {"action": a.action_type, "node": a.target_node,
                 "description": a.description, "priority": a.priority}
                for a in self.evaluate()[:5]
            ],
        }


# Singleton
_scaler: Optional[AutoScaler] = None

def get_scaler() -> AutoScaler:
    global _scaler
    if _scaler is None:
        _scaler = AutoScaler()
    return _scaler
