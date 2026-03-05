"""JARVIS Cluster Intelligence — Aggregates all subsystem insights into actionable intelligence.

Combines data from:
  - Adaptive Router (circuit breakers, load balancing)
  - Feedback Loop (quality trends, A/B results)
  - Pattern Discovery (new patterns, behavior insights)
  - Auto Scaler (load metrics, scaling actions)
  - Quality Gate (pass rates, failure patterns)
  - Pattern Lifecycle (health, deprecation candidates)
  - Event Stream (event flow rates)

Produces:
  - Unified cluster health score (0-100)
  - Prioritized action queue
  - Performance predictions
  - Capacity planning insights

Usage:
    from src.cluster_intelligence import ClusterIntelligence, get_intelligence
    intel = get_intelligence()
    report = intel.full_report()
    actions = intel.priority_actions()
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("jarvis.cluster_intelligence")

DB_PATH = "F:/BUREAU/turbo/etoile.db"


@dataclass
class IntelAction:
    """A prioritized action from cluster intelligence."""
    priority: int        # 1=critical, 2=high, 3=medium, 4=low
    category: str        # health, quality, performance, capacity, lifecycle
    action: str
    description: str
    source: str          # Which subsystem suggested this
    confidence: float    # 0-1
    impact: str          # Description of expected impact


class ClusterIntelligence:
    """Aggregates all subsystem insights into unified intelligence."""

    def __init__(self):
        self._last_report_ts: float = 0
        self._cached_report: Optional[dict] = None

    def full_report(self, force_refresh: bool = False) -> dict:
        """Generate comprehensive intelligence report."""
        # Cache for 60s
        if not force_refresh and self._cached_report and time.time() - self._last_report_ts < 60:
            return self._cached_report

        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "health_score": 0,
            "subsystems": {},
            "actions": [],
            "predictions": [],
            "summary": "",
        }

        # Collect from each subsystem
        report["subsystems"]["router"] = self._collect_router()
        report["subsystems"]["feedback"] = self._collect_feedback()
        report["subsystems"]["scaler"] = self._collect_scaler()
        report["subsystems"]["quality_gate"] = self._collect_quality_gate()
        report["subsystems"]["lifecycle"] = self._collect_lifecycle()
        report["subsystems"]["dispatch_stats"] = self._collect_dispatch_stats()

        # Calculate health score
        report["health_score"] = self._calculate_health_score(report["subsystems"])

        # Collect and prioritize actions
        report["actions"] = [a.__dict__ for a in self.priority_actions()]

        # Generate predictions
        report["predictions"] = self._generate_predictions(report["subsystems"])

        # Summary
        report["summary"] = self._generate_summary(report)

        self._cached_report = report
        self._last_report_ts = time.time()
        return report

    def _collect_router(self) -> dict:
        """Collect adaptive router status."""
        try:
            from src.adaptive_router import get_router
            router = get_router()
            status = router.get_status()
            return {
                "available": True,
                "nodes": len(status.get("nodes", {})),
                "open_circuits": sum(
                    1 for n in status.get("nodes", {}).values()
                    if n.get("circuit_breaker") == "open"
                ),
                "status": status,
            }
        except Exception:
            return {"available": False}

    def _collect_feedback(self) -> dict:
        """Collect feedback loop data."""
        try:
            from src.agent_feedback_loop import get_feedback
            fb = get_feedback()
            report = fb.get_quality_report()
            trends = fb.get_trends()
            return {
                "available": True,
                "total_feedback": report.get("total_feedback", 0),
                "avg_quality": report.get("avg_quality", 0),
                "success_rate": report.get("success_rate", 0),
                "degrading_patterns": [t.pattern for t in trends if t.direction == "degrading"],
                "improving_patterns": [t.pattern for t in trends if t.direction == "improving"],
            }
        except Exception:
            return {"available": False}

    def _collect_scaler(self) -> dict:
        """Collect auto scaler data."""
        try:
            from src.agent_auto_scaler import get_scaler
            scaler = get_scaler()
            metrics = scaler.get_load_metrics()
            actions = scaler.evaluate()
            return {
                "available": True,
                "active_nodes": len(metrics),
                "critical_actions": sum(1 for a in actions if a.priority <= 2),
                "total_actions": len(actions),
                "overloaded_nodes": [
                    n for n, m in metrics.items()
                    if m.error_rate > 0.3 or m.p95_latency_ms > 15000
                ],
            }
        except Exception:
            return {"available": False}

    def _collect_quality_gate(self) -> dict:
        """Collect quality gate data."""
        try:
            from src.quality_gate import get_gate
            gate = get_gate()
            stats = gate.get_stats()
            return {
                "available": True,
                "evaluated": stats.get("evaluated", 0),
                "pass_rate": stats.get("pass_rate", 0),
            }
        except Exception:
            return {"available": False}

    def _collect_lifecycle(self) -> dict:
        """Collect pattern lifecycle data."""
        try:
            from src.pattern_lifecycle import get_lifecycle
            lc = get_lifecycle()
            patterns = lc.get_all_patterns()
            actions = lc.suggest_actions()
            return {
                "available": True,
                "total_patterns": len(patterns),
                "active": sum(1 for p in patterns if p.status == "active"),
                "degraded": sum(1 for p in patterns if p.status == "degraded"),
                "new": sum(1 for p in patterns if p.status == "new"),
                "suggested_actions": len(actions),
            }
        except Exception:
            return {"available": False}

    def _collect_dispatch_stats(self) -> dict:
        """Collect overall dispatch statistics from DB."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            total = db.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
            recent = db.execute("""
                SELECT COUNT(*) FROM agent_dispatch_log
                WHERE timestamp > datetime('now', '-1 hour')
            """).fetchone()[0]
            success = db.execute("""
                SELECT AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as sr,
                       AVG(quality_score) as q, AVG(latency_ms) as lat
                FROM agent_dispatch_log
                WHERE timestamp > datetime('now', '-1 hour')
            """).fetchone()

            top_nodes = db.execute("""
                SELECT node, COUNT(*) as n,
                       AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as sr
                FROM agent_dispatch_log
                WHERE timestamp > datetime('now', '-1 hour')
                GROUP BY node ORDER BY n DESC LIMIT 5
            """).fetchall()

            db.close()

            return {
                "available": True,
                "total_dispatches": total,
                "last_hour": recent,
                "last_hour_success_rate": round(success["sr"] or 0, 3) if success else 0,
                "last_hour_avg_quality": round(success["q"] or 0, 3) if success else 0,
                "last_hour_avg_latency": round(success["lat"] or 0, 1) if success else 0,
                "top_nodes": [
                    {"node": r["node"], "calls": r["n"], "success_rate": round(r["sr"], 3)}
                    for r in top_nodes
                ],
            }
        except Exception:
            return {"available": False}

    def _calculate_health_score(self, subsystems: dict) -> int:
        """Calculate unified health score 0-100."""
        score = 100

        # Router health (-20 max)
        router = subsystems.get("router", {})
        if router.get("available"):
            open_circuits = router.get("open_circuits", 0)
            score -= open_circuits * 10

        # Feedback quality (-25 max)
        feedback = subsystems.get("feedback", {})
        if feedback.get("available"):
            avg_q = feedback.get("avg_quality", 0.5)
            if avg_q < 0.3:
                score -= 25
            elif avg_q < 0.5:
                score -= 15
            elif avg_q < 0.7:
                score -= 5

            degrading = len(feedback.get("degrading_patterns", []))
            score -= min(15, degrading * 3)

        # Scaler health (-20 max)
        scaler = subsystems.get("scaler", {})
        if scaler.get("available"):
            critical = scaler.get("critical_actions", 0)
            score -= min(20, critical * 7)
            overloaded = len(scaler.get("overloaded_nodes", []))
            score -= min(10, overloaded * 5)

        # Lifecycle health (-15 max)
        lifecycle = subsystems.get("lifecycle", {})
        if lifecycle.get("available"):
            degraded = lifecycle.get("degraded", 0)
            score -= min(15, degraded * 2)

        # Dispatch stats (-20 max)
        dispatch = subsystems.get("dispatch_stats", {})
        if dispatch.get("available"):
            sr = dispatch.get("last_hour_success_rate", 1)
            if sr < 0.5:
                score -= 20
            elif sr < 0.7:
                score -= 10
            elif sr < 0.9:
                score -= 5

        return max(0, min(100, score))

    def priority_actions(self) -> list[IntelAction]:
        """Collect and prioritize actions from all subsystems."""
        actions = []

        # From scaler
        try:
            from src.agent_auto_scaler import get_scaler
            for a in get_scaler().evaluate()[:5]:
                actions.append(IntelAction(
                    priority=a.priority,
                    category="performance",
                    action=a.action_type,
                    description=a.description,
                    source="auto_scaler",
                    confidence=0.7,
                    impact="Improved latency and reliability",
                ))
        except Exception:
            pass

        # From feedback
        try:
            from src.agent_feedback_loop import get_feedback
            for a in get_feedback().suggest_adjustments()[:5]:
                actions.append(IntelAction(
                    priority=2 if a.confidence > 0.7 else 3,
                    category="quality",
                    action=a.action,
                    description=f"{a.pattern}: {a.reason}",
                    source="feedback_loop",
                    confidence=a.confidence,
                    impact=a.expected_improvement,
                ))
        except Exception:
            pass

        # From lifecycle
        try:
            from src.pattern_lifecycle import get_lifecycle
            for a in get_lifecycle().suggest_actions()[:5]:
                actions.append(IntelAction(
                    priority=a.get("priority", 3),
                    category="lifecycle",
                    action=a.get("action", "unknown"),
                    description=f"{a.get('pattern', '')}: {a.get('reason', '')}",
                    source="pattern_lifecycle",
                    confidence=0.6,
                    impact=a.get("suggestion", "Pattern health improvement"),
                ))
        except Exception:
            pass

        return sorted(actions, key=lambda a: (a.priority, -a.confidence))

    def _generate_predictions(self, subsystems: dict) -> list[dict]:
        """Generate performance predictions."""
        predictions = []

        dispatch = subsystems.get("dispatch_stats", {})
        if dispatch.get("available"):
            hourly_rate = dispatch.get("last_hour", 0)
            if hourly_rate > 100:
                predictions.append({
                    "type": "capacity",
                    "prediction": f"At current rate ({hourly_rate}/h), cluster may need scaling within 2h",
                    "confidence": 0.6,
                })

        feedback = subsystems.get("feedback", {})
        if feedback.get("available"):
            degrading = feedback.get("degrading_patterns", [])
            if degrading:
                predictions.append({
                    "type": "quality",
                    "prediction": f"{len(degrading)} patterns degrading: {', '.join(degrading[:3])}",
                    "confidence": 0.7,
                })

            improving = feedback.get("improving_patterns", [])
            if improving:
                predictions.append({
                    "type": "quality",
                    "prediction": f"{len(improving)} patterns improving: {', '.join(improving[:3])}",
                    "confidence": 0.7,
                })

        return predictions

    def _generate_summary(self, report: dict) -> str:
        """Generate human-readable summary."""
        score = report["health_score"]
        grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"

        parts = [f"Cluster health: {score}/100 (Grade {grade})"]

        dispatch = report["subsystems"].get("dispatch_stats", {})
        if dispatch.get("available"):
            parts.append(f"{dispatch.get('total_dispatches', 0)} total dispatches, "
                        f"{dispatch.get('last_hour', 0)} last hour")

        lifecycle = report["subsystems"].get("lifecycle", {})
        if lifecycle.get("available"):
            parts.append(f"{lifecycle.get('total_patterns', 0)} patterns "
                        f"({lifecycle.get('active', 0)} active, "
                        f"{lifecycle.get('degraded', 0)} degraded)")

        n_actions = len(report.get("actions", []))
        if n_actions:
            parts.append(f"{n_actions} actions recommended")

        return " | ".join(parts)

    def quick_status(self) -> dict:
        """Quick status check (lightweight, no heavy DB queries)."""
        try:
            db = sqlite3.connect(DB_PATH)
            total = db.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
            patterns = db.execute("SELECT COUNT(*) FROM agent_patterns").fetchone()[0]
            recent_ok = db.execute("""
                SELECT AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END)
                FROM agent_dispatch_log
                WHERE timestamp > datetime('now', '-30 minutes')
            """).fetchone()[0]
            db.close()

            return {
                "status": "healthy" if (recent_ok or 0) > 0.7 else "degraded",
                "total_dispatches": total,
                "patterns": patterns,
                "recent_success_rate": round(recent_ok or 0, 3),
            }
        except Exception:
            return {"status": "unknown"}


# Singleton
_intelligence: Optional[ClusterIntelligence] = None

def get_intelligence() -> ClusterIntelligence:
    global _intelligence
    if _intelligence is None:
        _intelligence = ClusterIntelligence()
    return _intelligence
