"""JARVIS Cluster Diagnostics — Deep diagnostic with recommendations.

Combines data from orchestrator, LB, autonomous loop, alerts, metrics, and
conversations to generate a comprehensive diagnostic report with actionable
recommendations.

Usage:
    from src.cluster_diagnostics import cluster_diagnostics
    report = cluster_diagnostics.run_diagnostic()
    print(report["grade"])  # A/B/C/D/F
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("jarvis.diagnostics")


class ClusterDiagnostics:
    """Deep cluster diagnostic with scoring and recommendations."""

    def __init__(self) -> None:
        self._last_report: dict[str, Any] = {}
        self._report_history: list[dict[str, Any]] = []
        self._max_history = 50

    def run_diagnostic(self) -> dict[str, Any]:
        """Run a full cluster diagnostic. Returns scored report."""
        report: dict[str, Any] = {
            "ts": time.time(),
            "sections": {},
            "scores": {},
            "problems": [],
            "recommendations": [],
        }

        # 1. Orchestrator Health
        report["sections"]["orchestrator"] = self._check_orchestrator()

        # 2. Load Balancer
        report["sections"]["load_balancer"] = self._check_load_balancer()

        # 3. Autonomous Loop
        report["sections"]["autonomous_loop"] = self._check_autonomous_loop()

        # 4. Alerts
        report["sections"]["alerts"] = self._check_alerts()

        # 5. Memory & Conversations
        report["sections"]["data"] = self._check_data_stores()

        # 6. Event Bus
        report["sections"]["event_bus"] = self._check_event_bus()

        # Calculate scores
        scores = {}
        total_score = 0
        count = 0
        for section, data in report["sections"].items():
            score = data.get("score", 50)
            scores[section] = score
            total_score += score
            count += 1
            # Collect problems and recommendations
            report["problems"].extend(data.get("problems", []))
            report["recommendations"].extend(data.get("recommendations", []))

        overall = total_score // max(count, 1)
        scores["overall"] = overall
        report["scores"] = scores

        # Grade
        if overall >= 90:
            report["grade"] = "A"
        elif overall >= 75:
            report["grade"] = "B"
        elif overall >= 60:
            report["grade"] = "C"
        elif overall >= 40:
            report["grade"] = "D"
        else:
            report["grade"] = "F"

        self._last_report = report
        self._report_history.append({
            "ts": report["ts"], "grade": report["grade"],
            "overall": overall, "problems": len(report["problems"]),
        })
        if len(self._report_history) > self._max_history:
            self._report_history = self._report_history[-self._max_history:]

        return report

    def _check_orchestrator(self) -> dict[str, Any]:
        """Check orchestrator health."""
        result: dict[str, Any] = {"score": 50, "problems": [], "recommendations": []}
        try:
            from src.orchestrator_v2 import orchestrator_v2
            health = orchestrator_v2.health_check()
            stats = orchestrator_v2.get_node_stats()
            budget = orchestrator_v2.get_budget_report()
            alerts = orchestrator_v2.get_alerts()

            result["health_score"] = health
            result["node_count"] = len(stats)
            result["total_tokens"] = budget.get("total_tokens", 0)
            result["alert_count"] = len(alerts)
            result["score"] = health

            if health < 50:
                result["problems"].append(f"Cluster health critical: {health}/100")
                result["recommendations"].append("Run /heal-cluster to diagnose offline nodes")
            elif health < 70:
                result["problems"].append(f"Cluster health degraded: {health}/100")

            # Check for nodes with high failure rates
            for node, data in stats.items():
                sr = data.get("success_rate", 1.0)
                if sr < 0.7 and data.get("total_calls", 0) > 5:
                    result["problems"].append(f"{node}: low success rate {sr:.0%}")
                    result["recommendations"].append(f"Consider reducing load on {node} or checking connectivity")

            if budget.get("total_tokens", 0) > 500_000:
                result["recommendations"].append("High token usage — review query patterns")

        except Exception as e:
            result["score"] = 0
            result["problems"].append(f"Orchestrator check failed: {e}")
        return result

    def _check_load_balancer(self) -> dict[str, Any]:
        """Check load balancer status."""
        result: dict[str, Any] = {"score": 100, "problems": [], "recommendations": []}
        try:
            from src.load_balancer import load_balancer
            status = load_balancer.get_status()
            nodes = status.get("nodes", {})

            circuit_broken = [n for n, info in nodes.items() if info.get("circuit_broken")]
            overloaded = [n for n, info in nodes.items()
                         if info.get("active_requests", 0) >= status.get("max_concurrent", 3)]

            result["total_nodes"] = len(nodes)
            result["circuit_broken"] = circuit_broken
            result["overloaded"] = overloaded

            if circuit_broken:
                result["score"] -= 30 * len(circuit_broken)
                result["problems"].append(f"Circuit broken: {', '.join(circuit_broken)}")
                result["recommendations"].append("Wait for circuit breaker recovery or restart affected nodes")

            if overloaded:
                result["score"] -= 15 * len(overloaded)
                result["problems"].append(f"Overloaded nodes: {', '.join(overloaded)}")
                result["recommendations"].append("Reduce concurrent requests or add capacity")

            result["score"] = max(0, result["score"])
        except Exception as e:
            result["score"] = 50
            result["problems"].append(f"LB check failed: {e}")
        return result

    def _check_autonomous_loop(self) -> dict[str, Any]:
        """Check autonomous loop health."""
        result: dict[str, Any] = {"score": 100, "problems": [], "recommendations": []}
        try:
            from src.autonomous_loop import autonomous_loop
            status = autonomous_loop.get_status()

            if not status.get("running"):
                result["score"] = 0
                result["problems"].append("Autonomous loop is NOT running")
                result["recommendations"].append("Start autonomous loop: await autonomous_loop.start()")
                return result

            tasks = status.get("tasks", {})
            high_fail = []
            for name, info in tasks.items():
                runs = info.get("run_count", 0)
                fails = info.get("fail_count", 0)
                if runs > 5 and fails / runs > 0.3:
                    high_fail.append(f"{name} ({fails}/{runs})")

            if high_fail:
                result["score"] -= 10 * len(high_fail)
                result["problems"].append(f"High failure tasks: {', '.join(high_fail)}")
                result["recommendations"].append("Check logs for failing tasks, consider adjusting intervals")

            result["task_count"] = len(tasks)
            result["event_count"] = status.get("event_count", 0)
            result["score"] = max(0, result["score"])
        except Exception as e:
            result["score"] = 30
            result["problems"].append(f"Loop check failed: {e}")
        return result

    def _check_alerts(self) -> dict[str, Any]:
        """Check active alerts."""
        result: dict[str, Any] = {"score": 100, "problems": [], "recommendations": []}
        try:
            from src.alert_manager import alert_manager
            active = alert_manager.get_active()
            critical = [a for a in active if a["level"] == "critical"]
            warnings = [a for a in active if a["level"] == "warning"]

            result["active_count"] = len(active)
            result["critical_count"] = len(critical)
            result["warning_count"] = len(warnings)

            if critical:
                result["score"] -= 25 * len(critical)
                for a in critical:
                    result["problems"].append(f"CRITICAL: {a['message']}")
                result["recommendations"].append("Address critical alerts immediately")

            if len(warnings) > 3:
                result["score"] -= 10
                result["problems"].append(f"{len(warnings)} active warnings")

            result["score"] = max(0, result["score"])
        except Exception as e:
            result["score"] = 50
        return result

    def _check_data_stores(self) -> dict[str, Any]:
        """Check data stores (memory, conversations)."""
        result: dict[str, Any] = {"score": 100, "problems": [], "recommendations": []}
        try:
            from src.agent_memory import agent_memory
            mem_stats = agent_memory.get_stats()
            result["memory_count"] = mem_stats.get("total", 0)

            if mem_stats.get("total", 0) > 500:
                result["recommendations"].append("Agent memory has many entries — consider cleanup")
        except Exception:
            pass

        try:
            from src.conversation_store import conversation_store
            conv_stats = conversation_store.get_stats()
            result["conversation_count"] = conv_stats.get("total_conversations", 0)
            result["turn_count"] = conv_stats.get("total_turns", 0)
        except Exception:
            pass

        return result

    def _check_event_bus(self) -> dict[str, Any]:
        """Check event bus health."""
        result: dict[str, Any] = {"score": 100, "problems": [], "recommendations": []}
        try:
            from src.event_bus import event_bus
            stats = event_bus.get_stats()
            result["subscriptions"] = stats.get("total_subscriptions", 0)
            result["total_events"] = stats.get("total_events_emitted", 0)

            if stats.get("total_subscriptions", 0) == 0:
                result["recommendations"].append("No event bus subscribers — modules are not interconnected")
                result["score"] = 70
        except Exception:
            result["score"] = 50
        return result

    def get_last_report(self) -> dict[str, Any]:
        """Return the most recent diagnostic report."""
        return self._last_report

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return report history (grade + score only)."""
        return self._report_history[-limit:]

    def get_quick_status(self) -> dict[str, Any]:
        """Quick status without full diagnostic."""
        try:
            from src.orchestrator_v2 import orchestrator_v2
            health = orchestrator_v2.health_check()
        except Exception:
            health = 0

        try:
            from src.alert_manager import alert_manager
            active_alerts = len(alert_manager.get_active())
        except Exception:
            active_alerts = 0

        try:
            from src.autonomous_loop import autonomous_loop
            loop_running = autonomous_loop.is_running
        except Exception:
            loop_running = False

        return {
            "health_score": health,
            "active_alerts": active_alerts,
            "loop_running": loop_running,
            "last_diagnostic": self._last_report.get("grade", "N/A"),
        }


# Global singleton
cluster_diagnostics = ClusterDiagnostics()
