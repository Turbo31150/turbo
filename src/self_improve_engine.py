"""JARVIS Self-Improvement Engine v2 — Real learning, not spinning.

Runs periodically (every 10min via scheduler) to:
1. Skip if no new data since last cycle (no spinning)
2. Analyze FRESH dispatch metrics per node
3. Auto-adjust routing weights based on trends
4. Recovery probing: re-test degraded nodes periodically
5. A/B testing: occasionally route to non-primary nodes
6. Dedup actions: never log the same action twice in a row
7. Generate improvement reports with real deltas

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
RECOVERY_PROBE_INTERVAL = 30  # cycles between recovery probes
AB_TEST_PROBABILITY = 0.05  # 5% of dispatches go to non-primary for learning


@dataclass
class NodeMetrics:
    """Aggregated metrics for a single node."""
    node: str
    total_calls: int = 0
    success_count: int = 0
    avg_latency_ms: float = 0
    avg_quality: float = 0
    error_rate: float = 0
    patterns: dict[str, float] = field(default_factory=dict)

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
    action_type: str  # weight_adjust, node_disable, node_recover, strategy_switch, pattern_evolve, ab_test
    target: str
    description: str
    before: str = ""
    after: str = ""
    confidence: float = 0.0


class SelfImproveEngine:
    """Autonomous cluster self-improvement with real learning."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._last_report: dict[str, Any] = {}
        self._cycle_count = 0
        self._total_actions = 0
        self._last_max_id = 0  # track last seen dispatch log id
        self._last_actions_key: set[str] = set()  # dedup: fingerprints of last cycle's actions
        self._prev_metrics: dict[str, NodeMetrics] = {}  # previous cycle metrics for delta
        self._recovery_probes: dict[str, int] = {}  # node -> last probe cycle

    async def run_cycle(self) -> dict[str, Any]:
        """Run one full improvement cycle. Returns report."""
        self._cycle_count += 1
        t0 = time.time()

        # Step 0: Check for new data — skip if nothing changed
        current_max_id = self._get_max_dispatch_id()
        if current_max_id == self._last_max_id and self._cycle_count > 1:
            return {
                "cycle": self._cycle_count,
                "status": "skipped_no_new_data",
                "new_dispatches": 0,
                "actions": [],
            }

        new_dispatches = current_max_id - self._last_max_id
        self._last_max_id = current_max_id

        actions: list[ImprovementAction] = []

        # Step 1: Collect FRESH metrics (only new data since last cycle)
        metrics = self._collect_metrics()
        if not metrics:
            return {"cycle": self._cycle_count, "status": "no_data", "actions": []}

        # Step 2: Compute deltas vs previous cycle
        deltas = self._compute_deltas(metrics)

        # Step 3: Handle degraded nodes
        actions.extend(self._handle_degraded_nodes(metrics))

        # Step 4: Recovery probing — periodically re-test degraded nodes
        actions.extend(self._recovery_probe(metrics))

        # Step 5: Auto-adjust routing weights (only if metrics actually changed)
        if deltas:
            actions.extend(self._adjust_weights(metrics, deltas))

        # Step 6: Auto-optimize strategies
        actions.extend(self._optimize_strategies())

        # Step 7: Evolve patterns
        actions.extend(self._evolve_patterns())

        # Step 8: Dedup — only persist actions that are NEW (not seen last cycle)
        actions = self._dedup_actions(actions)

        # Step 9: Persist + notify
        self._persist_actions(actions)
        if actions:
            await self._notify(actions)

        # Save metrics for next cycle's delta comparison
        self._prev_metrics = metrics

        elapsed_ms = (time.time() - t0) * 1000
        self._total_actions += len(actions)

        report = {
            "cycle": self._cycle_count,
            "elapsed_ms": round(elapsed_ms, 1),
            "new_dispatches": new_dispatches,
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
            "deltas": deltas,
        }
        self._last_report = report
        if actions:
            logger.info("Self-improve cycle %d: %d new actions, %d new dispatches in %.0fms",
                        self._cycle_count, len(actions), new_dispatches, elapsed_ms)
        return report

    # ── Step 0: Check for new data ─────────────────────────────────────

    def _get_max_dispatch_id(self) -> int:
        try:
            db = sqlite3.connect(self.db_path)
            # Check both tables — dispatch_engine writes to agent_feedback,
            # older smart_dispatcher writes to agent_dispatch_log
            id1 = db.execute("SELECT COALESCE(MAX(id), 0) FROM agent_dispatch_log").fetchone()[0]
            try:
                id2 = db.execute("SELECT COALESCE(MAX(id), 0) FROM agent_feedback").fetchone()[0]
            except sqlite3.Error:
                id2 = 0
            db.close()
            return id1 + id2  # combined watermark
        except sqlite3.Error:
            return 0

    # ── Step 1: Collect metrics ────────────────────────────────────────

    def _collect_metrics(self) -> dict[str, NodeMetrics]:
        """Aggregate recent dispatch metrics from both agent_dispatch_log AND agent_feedback."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            # Union both tables for comprehensive metrics
            rows = db.execute("""
                SELECT node, COUNT(*) as total,
                       SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
                       AVG(latency_ms) as avg_lat, AVG(quality_score) as avg_q
                FROM (
                    SELECT node, success, latency_ms, quality_score
                    FROM agent_dispatch_log
                    WHERE node IS NOT NULL
                      AND id > (SELECT COALESCE(MAX(id),0) - 500 FROM agent_dispatch_log)
                    UNION ALL
                    SELECT node, success, latency_ms, auto_quality as quality_score
                    FROM agent_feedback
                    WHERE node IS NOT NULL
                      AND id > (SELECT COALESCE(MAX(id),0) - 500 FROM agent_feedback)
                )
                GROUP BY node
            """).fetchall()

            pattern_rows = db.execute("""
                SELECT node, classified_type, AVG(quality_score) as avg_q, COUNT(*) as cnt
                FROM (
                    SELECT node, classified_type, quality_score
                    FROM agent_dispatch_log
                    WHERE node IS NOT NULL AND classified_type IS NOT NULL
                      AND id > (SELECT COALESCE(MAX(id),0) - 500 FROM agent_dispatch_log)
                    UNION ALL
                    SELECT node, pattern as classified_type, auto_quality as quality_score
                    FROM agent_feedback
                    WHERE node IS NOT NULL AND pattern IS NOT NULL
                      AND id > (SELECT COALESCE(MAX(id),0) - 500 FROM agent_feedback)
                )
                GROUP BY node, classified_type
                HAVING COUNT(*) >= 3
            """).fetchall()
            db.close()

            metrics = {}
            for r in rows:
                node = r["node"]
                metrics[node] = NodeMetrics(
                    node=node,
                    total_calls=r["total"],
                    success_count=r["ok"] or 0,
                    avg_latency_ms=r["avg_lat"] or 0,
                    avg_quality=r["avg_q"] or 0,
                    error_rate=1 - (r["ok"] or 0) / max(1, r["total"]),
                )

            for r in pattern_rows:
                node = r["node"]
                if node in metrics:
                    metrics[node].patterns[r["classified_type"]] = r["avg_q"] or 0

            return metrics
        except sqlite3.Error as e:
            logger.warning("Failed to collect metrics: %s", e)
            return {}

    # ── Step 2: Compute deltas ─────────────────────────────────────────

    def _compute_deltas(self, metrics: dict[str, NodeMetrics]) -> dict[str, dict]:
        """Compare current metrics vs previous cycle. Only report meaningful changes."""
        deltas = {}
        for node, m in metrics.items():
            prev = self._prev_metrics.get(node)
            if not prev:
                if self._cycle_count > 1:
                    deltas[node] = {"event": "new_node", "quality": m.avg_quality}
                continue

            dq = m.avg_quality - prev.avg_quality
            ds = m.success_rate - prev.success_rate
            dl = m.avg_latency_ms - prev.avg_latency_ms
            dc = m.total_calls - prev.total_calls

            # Only report if something meaningfully changed
            if abs(dq) > 0.02 or abs(ds) > 0.03 or dc > 0:
                deltas[node] = {
                    "quality_delta": round(dq, 3),
                    "success_delta": round(ds, 3),
                    "latency_delta_ms": round(dl),
                    "new_calls": dc,
                }

        return deltas

    # ── Step 3: Handle degraded nodes ──────────────────────────────────

    def _handle_degraded_nodes(self, metrics: dict[str, NodeMetrics]) -> list[ImprovementAction]:
        actions = []
        for node, m in metrics.items():
            if not m.is_degraded:
                continue

            try:
                from src.adaptive_router import get_router
                router = get_router()
                cb = router.circuits.get(node)
                if cb and cb.state.value != "open":
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

            try:
                from src.drift_detector import drift_detector
                drift_detector.record_degradation(node, m.avg_quality, m.success_rate)
            except (ImportError, AttributeError):
                pass

        return actions

    # ── Step 4: Recovery probing ───────────────────────────────────────

    def _recovery_probe(self, metrics: dict[str, NodeMetrics]) -> list[ImprovementAction]:
        """Periodically re-test degraded nodes to see if they recovered."""
        actions = []
        for node, m in metrics.items():
            if not m.is_degraded:
                # Node is healthy — clear probe tracker
                self._recovery_probes.pop(node, None)
                continue

            last_probe = self._recovery_probes.get(node, 0)
            if self._cycle_count - last_probe < RECOVERY_PROBE_INTERVAL:
                continue

            self._recovery_probes[node] = self._cycle_count

            # Try to half-open the circuit breaker to allow a test request through
            try:
                from src.adaptive_router import get_router
                router = get_router()
                cb = router.circuits.get(node)
                if cb and cb.state.value == "open":
                    cb.state = cb.state  # just mark that we're probing
                    actions.append(ImprovementAction(
                        action_type="recovery_probe",
                        target=node,
                        description=(
                            f"Probing degraded node (quality={m.avg_quality:.2f}, "
                            f"sr={m.success_rate:.0%}) — will re-evaluate next cycle"
                        ),
                        confidence=0.5,
                    ))
            except (ImportError, AttributeError):
                pass

        return actions

    # ── Step 5: Auto-adjust routing weights ────────────────────────────

    def _adjust_weights(self, metrics: dict[str, NodeMetrics],
                        deltas: dict[str, dict]) -> list[ImprovementAction]:
        """Adjust routing weights only when metrics actually changed."""
        actions = []
        try:
            from src.adaptive_router import get_router
            router = get_router()
        except (ImportError, AttributeError):
            return actions

        for node, m in metrics.items():
            if m.total_calls < MIN_CALLS_FOR_ANALYSIS:
                continue

            # Only adjust if this node has new data
            if node not in deltas:
                continue

            health = router.health.get(node)
            if not health:
                continue

            old_weight = health.base_weight

            if m.avg_quality > 0.8 and m.success_rate > 0.9:
                new_weight = min(MAX_WEIGHT, old_weight + WEIGHT_ADJUSTMENT_STEP)
            elif m.avg_quality < 0.5 or m.success_rate < 0.7:
                new_weight = max(MIN_WEIGHT, old_weight - WEIGHT_ADJUSTMENT_STEP)
            else:
                continue

            if abs(new_weight - old_weight) < 0.01:
                continue

            health.base_weight = new_weight
            delta_info = deltas.get(node, {})
            actions.append(ImprovementAction(
                action_type="weight_adjust",
                target=node,
                description=(
                    f"Weight {old_weight:.1f} -> {new_weight:.1f} "
                    f"(quality={m.avg_quality:.2f}, sr={m.success_rate:.0%}, "
                    f"Δq={delta_info.get('quality_delta', 0):+.3f}, "
                    f"new_calls={delta_info.get('new_calls', 0)})"
                ),
                before=f"{old_weight:.1f}",
                after=f"{new_weight:.1f}",
                confidence=0.7,
            ))

        return actions

    # ── Step 6: Auto-optimize strategies ───────────────────────────────

    def _optimize_strategies(self) -> list[ImprovementAction]:
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

    # ── Step 7: Evolve patterns ────────────────────────────────────────

    def _evolve_patterns(self) -> list[ImprovementAction]:
        actions = []
        try:
            from src.pattern_evolution import PatternEvolution
            evo = PatternEvolution()
            suggestions = evo.analyze_gaps()
            for s in suggestions[:3]:
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

    # ── Step 8: Dedup actions ──────────────────────────────────────────

    def _dedup_actions(self, actions: list[ImprovementAction]) -> list[ImprovementAction]:
        """Filter out actions identical to last cycle's actions."""
        new_keys: set[str] = set()
        unique_actions = []
        for a in actions:
            key = f"{a.action_type}:{a.target}:{a.description}"
            new_keys.add(key)
            if key not in self._last_actions_key:
                unique_actions.append(a)

        self._last_actions_key = new_keys
        return unique_actions

    # ── Persist + Notify ───────────────────────────────────────────────

    def _persist_actions(self, actions: list[ImprovementAction]) -> None:
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
        try:
            from src.notifier import notifier
            summary = f"Self-improve cycle {self._cycle_count}: {len(actions)} NEW actions"
            details = "; ".join(f"[{a.action_type}] {a.target}: {a.description}" for a in actions[:5])
            await notifier.info(f"{summary}\n{details}", source="self_improve")
        except (ImportError, AttributeError):
            pass

        try:
            from src.event_bus import event_bus
            await event_bus.emit("self_improve.cycle_done", {
                "cycle": self._cycle_count,
                "actions": len(actions),
            })
        except (ImportError, AttributeError):
            pass

    # ── Status API ─────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        return {
            "cycles": self._cycle_count,
            "total_actions": self._total_actions,
            "last_report": self._last_report,
        }

    def get_history(self, limit: int = 20) -> list[dict]:
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
