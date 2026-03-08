"""JARVIS Self-Improvement Engine — Autonomous cluster optimization.

Runs periodically via autonomous_loop to:
1. Analyze cluster metrics (latency, quality, error rate per node)
2. Detect degradation patterns
3. Auto-adjust routing weights
4. Auto-disable failing nodes
5. Auto-optimize pattern agent strategies
6. Generate daily improvement reports

Usage:
    from src.self_improve_engine import self_improve_engine
    report = await self_improve_engine.run_cycle()
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


__all__ = [
    "ImprovementAction",
    "NodeMetrics",
    "SelfImproveEngine",
]

logger = logging.getLogger("jarvis.self_improve")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")

# Thresholds
MIN_CALLS_FOR_ANALYSIS = 5
DEGRADATION_QUALITY_THRESHOLD = 0.4
DEGRADATION_SUCCESS_THRESHOLD = 0.5
WEIGHT_ADJUSTMENT_STEP = 0.1
MAX_WEIGHT = 2.0
MIN_WEIGHT = 0.3


@dataclass
class NodeMetrics:
    """Aggregated metrics for a single node."""
    node: str
    total_calls: int = 0
    success_count: int = 0
    avg_latency_ms: float = 0
    avg_quality: float = 0
    error_rate: float = 0
    patterns: dict[str, float] = field(default_factory=dict)  # pattern -> quality

    @property
    def success_rate(self) -> float:
        return self.success_count / max(1, self.total_calls)

    @property
    def is_degraded(self) -> bool:
        return (self.total_calls >= MIN_CALLS_FOR_ANALYSIS
                and (self.avg_quality < DEGRADATION_QUALITY_THRESHOLD
                     or self.success_rate < DEGRADATION_SUCCESS_THRESHOLD))


@dataclass
class ImprovementAction:
    """A single improvement action taken."""
    action_type: str  # weight_adjust, node_disable, strategy_switch, pattern_evolve
    target: str
    description: str
    before: str = ""
    after: str = ""
    confidence: float = 0.0


class SelfImproveEngine:
    """Autonomous cluster self-improvement."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._last_report: dict[str, Any] = {}
        self._cycle_count = 0
        self._total_actions = 0

    async def run_cycle(self) -> dict[str, Any]:
        """Run one full improvement cycle. Returns report."""
        self._cycle_count += 1
        t0 = time.time()
        actions: list[ImprovementAction] = []

        # Step 1: Collect metrics
        metrics = self._collect_metrics()
        if not metrics:
            return {"cycle": self._cycle_count, "status": "no_data", "actions": []}

        # Step 2: Detect degradation + auto-disable
        actions.extend(self._handle_degraded_nodes(metrics))

        # Step 3: Auto-adjust routing weights
        actions.extend(self._adjust_weights(metrics))

        # Step 4: Auto-optimize strategies
        actions.extend(self._optimize_strategies())

        # Step 5: Evolve patterns (detect gaps)
        actions.extend(self._evolve_patterns())

        # Step 6: Persist actions
        self._persist_actions(actions)

        # Step 7: Notify if significant
        if actions:
            await self._notify(actions)

        elapsed_ms = (time.time() - t0) * 1000
        self._total_actions += len(actions)

        report = {
            "cycle": self._cycle_count,
            "elapsed_ms": round(elapsed_ms, 1),
            "nodes_analyzed": len(metrics),
            "actions_taken": len(actions),
            "actions": [
                {"type": a.action_type, "target": a.target, "desc": a.description}
                for a in actions
            ],
            "node_health": {
                n: {"calls": m.total_calls, "success": f"{m.success_rate:.0%}",
                    "quality": round(m.avg_quality, 2), "latency_ms": round(m.avg_latency_ms),
                    "degraded": m.is_degraded}
                for n, m in metrics.items()
            },
        }
        self._last_report = report
        logger.info("Self-improve cycle %d: %d actions in %.0fms",
                     self._cycle_count, len(actions), elapsed_ms)
        return report

    # ── Step 1: Collect metrics ──────────────────────────────────────────

    def _collect_metrics(self) -> dict[str, NodeMetrics]:
        """Aggregate recent dispatch metrics per node."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT node,
                       COUNT(*) as total,
                       SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
                       AVG(latency_ms) as avg_lat,
                       AVG(quality_score) as avg_q
                FROM agent_dispatch_log
                WHERE node IS NOT NULL
                  AND id > (SELECT COALESCE(MAX(id),0) - 500 FROM agent_dispatch_log)
                GROUP BY node
            """).fetchall()

            # Also get per-pattern quality
            pattern_rows = db.execute("""
                SELECT node, classified_type, AVG(quality_score) as avg_q
                FROM agent_dispatch_log
                WHERE node IS NOT NULL AND classified_type IS NOT NULL
                  AND id > (SELECT COALESCE(MAX(id),0) - 500 FROM agent_dispatch_log)
                GROUP BY node, classified_type
                HAVING COUNT(*) >= 3
            """).fetchall()
            db.close()

            metrics = {}
            for r in rows:
                node = r["node"]
                m = NodeMetrics(
                    node=node,
                    total_calls=r["total"],
                    success_count=r["ok"] or 0,
                    avg_latency_ms=r["avg_lat"] or 0,
                    avg_quality=r["avg_q"] or 0,
                    error_rate=1 - (r["ok"] or 0) / max(1, r["total"]),
                )
                metrics[node] = m

            for r in pattern_rows:
                node = r["node"]
                if node in metrics:
                    metrics[node].patterns[r["classified_type"]] = r["avg_q"] or 0

            return metrics
        except sqlite3.Error as e:
            logger.warning("Failed to collect metrics: %s", e)
            return {}

    # ── Step 2: Handle degraded nodes ────────────────────────────────────

    def _handle_degraded_nodes(self, metrics: dict[str, NodeMetrics]) -> list[ImprovementAction]:
        """Detect degraded nodes and disable them in adaptive_router."""
        actions = []
        for node, m in metrics.items():
            if not m.is_degraded:
                continue

            # Disable in circuit breaker
            try:
                from src.adaptive_router import get_router
                router = get_router()
                cb = router.circuits.get(node)
                if cb and cb.state.value != "open":
                    # Force circuit open
                    for _ in range(5):
                        cb.record_failure()
                    actions.append(ImprovementAction(
                        action_type="node_disable",
                        target=node,
                        description=(
                            f"Circuit opened: quality={m.avg_quality:.2f}, "
                            f"success={m.success_rate:.0%} over {m.total_calls} calls"
                        ),
                        confidence=0.8,
                    ))
            except (ImportError, AttributeError):
                pass

            # Record in drift detector
            try:
                from src.drift_detector import drift_detector
                drift_detector.record_degradation(node, m.avg_quality, m.success_rate)
            except (ImportError, AttributeError):
                pass

        return actions

    # ── Step 3: Auto-adjust routing weights ──────────────────────────────

    def _adjust_weights(self, metrics: dict[str, NodeMetrics]) -> list[ImprovementAction]:
        """Adjust routing weights based on quality trends."""
        actions = []
        try:
            from src.adaptive_router import get_router
            router = get_router()
        except (ImportError, AttributeError):
            return actions

        for node, m in metrics.items():
            if m.total_calls < MIN_CALLS_FOR_ANALYSIS:
                continue

            health = router.health.get(node)
            if not health:
                continue

            old_weight = health.base_weight

            if m.avg_quality > 0.8 and m.success_rate > 0.9:
                # High performer — increase weight
                new_weight = min(MAX_WEIGHT, old_weight + WEIGHT_ADJUSTMENT_STEP)
            elif m.avg_quality < 0.5 or m.success_rate < 0.7:
                # Low performer — decrease weight
                new_weight = max(MIN_WEIGHT, old_weight - WEIGHT_ADJUSTMENT_STEP)
            else:
                continue

            if abs(new_weight - old_weight) < 0.01:
                continue

            health.base_weight = new_weight
            actions.append(ImprovementAction(
                action_type="weight_adjust",
                target=node,
                description=f"Weight {old_weight:.1f} -> {new_weight:.1f} "
                            f"(quality={m.avg_quality:.2f}, sr={m.success_rate:.0%})",
                before=f"{old_weight:.1f}",
                after=f"{new_weight:.1f}",
                confidence=0.7,
            ))

        return actions

    # ── Step 4: Auto-optimize strategies ─────────────────────────────────

    def _optimize_strategies(self) -> list[ImprovementAction]:
        """Use PatternAgentRegistry.auto_optimize_strategies() to switch strategies."""
        actions = []
        try:
            from src.pattern_agents import PatternAgentRegistry
            registry = PatternAgentRegistry(self.db_path)
            changes = registry.auto_optimize_strategies()
            for pattern, info in changes.items():
                actions.append(ImprovementAction(
                    action_type="strategy_switch",
                    target=pattern,
                    description=f"Strategy {info['from']} -> {info['to']} ({info['rate_improvement']} sr)",
                    before=info["from"],
                    after=info["to"],
                    confidence=0.6,
                ))
        except (ImportError, AttributeError, sqlite3.Error) as e:
            logger.debug("Strategy optimization skipped: %s", e)
        return actions

    # ── Step 5: Evolve patterns ──────────────────────────────────────────

    def _evolve_patterns(self) -> list[ImprovementAction]:
        """Use PatternEvolution to detect gaps and suggest new patterns."""
        actions = []
        try:
            from src.pattern_evolution import PatternEvolution
            evo = PatternEvolution()
            suggestions = evo.analyze_gaps()
            for s in suggestions[:3]:  # max 3 suggestions per cycle
                if s.confidence >= 0.6:
                    actions.append(ImprovementAction(
                        action_type="pattern_evolve",
                        target=s.pattern_type,
                        description=f"{s.action}: {s.description} (conf={s.confidence:.0%})",
                        confidence=s.confidence,
                    ))
        except (ImportError, AttributeError, sqlite3.Error) as e:
            logger.debug("Pattern evolution skipped: %s", e)
        return actions

    # ── Persist + Notify ─────────────────────────────────────────────────

    def _persist_actions(self, actions: list[ImprovementAction]) -> None:
        """Log actions to DB for audit trail."""
        if not actions:
            return
        try:
            db = sqlite3.connect(self.db_path)
            db.execute("""CREATE TABLE IF NOT EXISTS self_improve_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle INTEGER, action_type TEXT, target TEXT,
                description TEXT, confidence REAL,
                before_val TEXT, after_val TEXT,
                timestamp REAL
            )""")
            now = time.time()
            for a in actions:
                db.execute(
                    "INSERT INTO self_improve_log (cycle, action_type, target, description, "
                    "confidence, before_val, after_val, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                    (self._cycle_count, a.action_type, a.target, a.description,
                     a.confidence, a.before, a.after, now),
                )
            db.commit()
            db.close()
        except sqlite3.Error as e:
            logger.warning("Failed to persist actions: %s", e)

    async def _notify(self, actions: list[ImprovementAction]) -> None:
        """Send notification about improvement actions."""
        try:
            from src.notifier import notifier
            summary = f"Self-improve cycle {self._cycle_count}: {len(actions)} actions"
            details = "; ".join(f"[{a.action_type}] {a.target}: {a.description}" for a in actions[:5])
            await notifier.info(f"{summary}\n{details}", source="self_improve")
        except (ImportError, AttributeError):
            pass

        # Emit event for dashboard
        try:
            from src.event_bus import event_bus
            await event_bus.emit("self_improve.cycle_done", {
                "cycle": self._cycle_count,
                "actions": len(actions),
            })
        except (ImportError, AttributeError):
            pass

    # ── Status API ───────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        return {
            "cycles": self._cycle_count,
            "total_actions": self._total_actions,
            "last_report": self._last_report,
        }

    def get_history(self, limit: int = 20) -> list[dict]:
        """Get recent improvement actions from DB."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM self_improve_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            db.close()
            return [dict(r) for r in rows]
        except sqlite3.Error:
            return []


# ── Singleton ────────────────────────────────────────────────────────────────
self_improve_engine = SelfImproveEngine()
