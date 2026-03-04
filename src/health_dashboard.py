"""Health Dashboard — Unified cluster health endpoint.

Combines diagnostics, metrics, alerts, scheduler, and rate limiter
into a single comprehensive health report.
"""

from __future__ import annotations

import time
import logging
from typing import Any

logger = logging.getLogger("jarvis.health_dashboard")


class HealthDashboard:
    """Single-pane-of-glass health view for the entire JARVIS cluster."""

    def __init__(self):
        self._last_report: dict = {}
        self._report_history: list[dict] = []

    def collect(self) -> dict:
        """Collect health data from all subsystems into one report."""
        report: dict[str, Any] = {
            "ts": time.time(),
            "subsystems": {},
            "overall_health": 100,
            "status": "healthy",
            "problems": [],
        }

        # 1 — Cluster Diagnostics
        try:
            from src.cluster_diagnostics import cluster_diagnostics
            diag = cluster_diagnostics.run_diagnostic()
            report["subsystems"]["diagnostics"] = {
                "grade": diag.get("grade", "?"),
                "score": diag.get("scores", {}).get("overall", 0),
                "problems": len(diag.get("problems", [])),
            }
            report["problems"].extend(diag.get("problems", []))
        except Exception as e:
            report["subsystems"]["diagnostics"] = {"error": str(e)}

        # 2 — Metrics snapshot
        try:
            from src.metrics_aggregator import metrics_aggregator
            snap = metrics_aggregator.snapshot()
            report["subsystems"]["metrics"] = {
                "modules_reporting": len(snap),
                "sample_count": len(metrics_aggregator._history),
            }
        except Exception as e:
            report["subsystems"]["metrics"] = {"error": str(e)}

        # 3 — Alerts
        try:
            from src.alert_manager import alert_manager
            stats = alert_manager.get_stats()
            active = alert_manager.get_active()
            critical = [a for a in active if a.level == "critical"]
            report["subsystems"]["alerts"] = {
                "active": len(active),
                "critical": len(critical),
                "total_fired": stats["total_fired"],
            }
            if critical:
                report["problems"].extend([f"CRITICAL ALERT: {a.message}" for a in critical])
        except Exception as e:
            report["subsystems"]["alerts"] = {"error": str(e)}

        # 4 — Scheduler
        try:
            from src.task_scheduler import task_scheduler
            sched_stats = task_scheduler.get_stats()
            report["subsystems"]["scheduler"] = {
                "running": sched_stats["running"],
                "total_jobs": sched_stats["total_jobs"],
                "enabled_jobs": sched_stats["enabled_jobs"],
            }
        except Exception as e:
            report["subsystems"]["scheduler"] = {"error": str(e)}

        # 5 — Rate Limiter
        try:
            from src.rate_limiter import rate_limiter
            rl_stats = rate_limiter.get_all_stats()
            report["subsystems"]["rate_limiter"] = {
                "nodes_tracked": len(rl_stats["nodes"]),
                "total_allowed": rl_stats["total_allowed"],
                "total_denied": rl_stats["total_denied"],
            }
        except Exception as e:
            report["subsystems"]["rate_limiter"] = {"error": str(e)}

        # 6 — Config Manager
        try:
            from src.config_manager import config_manager
            cfg_stats = config_manager.get_stats()
            report["subsystems"]["config"] = {
                "sections": len(cfg_stats.get("sections", {})),
                "total_changes": cfg_stats.get("total_changes", 0),
            }
        except Exception as e:
            report["subsystems"]["config"] = {"error": str(e)}

        # 7 — Audit Trail
        try:
            from src.audit_trail import audit_trail
            audit_stats = audit_trail.get_stats(hours=1)
            report["subsystems"]["audit"] = {
                "recent_entries": audit_stats.get("total_recent", 0),
            }
        except Exception as e:
            report["subsystems"]["audit"] = {"error": str(e)}

        # 8 — Event Bus
        try:
            from src.event_bus import event_bus
            eb_stats = event_bus.get_stats()
            report["subsystems"]["event_bus"] = {
                "subscribers": eb_stats.get("subscriber_count", 0),
                "events_emitted": eb_stats.get("events_emitted", 0),
            }
        except Exception as e:
            report["subsystems"]["event_bus"] = {"error": str(e)}

        # Compute overall health
        scores = []
        diag_data = report["subsystems"].get("diagnostics", {})
        if "score" in diag_data:
            scores.append(diag_data["score"])
        alerts_data = report["subsystems"].get("alerts", {})
        if "critical" in alerts_data and alerts_data["critical"] > 0:
            scores.append(max(0, 100 - alerts_data["critical"] * 25))
        if scores:
            report["overall_health"] = round(sum(scores) / len(scores))
        report["status"] = (
            "critical" if report["overall_health"] < 40
            else "degraded" if report["overall_health"] < 75
            else "healthy"
        )

        self._last_report = report
        self._report_history.append({
            "ts": report["ts"],
            "health": report["overall_health"],
            "status": report["status"],
            "problems": len(report["problems"]),
        })
        if len(self._report_history) > 200:
            self._report_history = self._report_history[-200:]

        return report

    def get_summary(self) -> dict:
        """Lightweight summary from last report."""
        if not self._last_report:
            return {"status": "unknown", "overall_health": 0, "message": "No report yet"}
        r = self._last_report
        return {
            "status": r["status"],
            "overall_health": r["overall_health"],
            "problems_count": len(r.get("problems", [])),
            "subsystems_ok": sum(1 for v in r.get("subsystems", {}).values() if "error" not in v),
            "subsystems_total": len(r.get("subsystems", {})),
            "last_check": r.get("ts", 0),
        }

    def get_history(self) -> list[dict]:
        return list(self._report_history)


# ── Singleton ────────────────────────────────────────────────────────────────
health_dashboard = HealthDashboard()
