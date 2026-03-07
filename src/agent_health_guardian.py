"""JARVIS Agent Health Guardian — Proactive health monitoring and auto-healing.

Continuously monitors:
  - Node availability (ping/health checks)
  - Success rate degradation per pattern and node
  - Latency spikes
  - Circuit breaker state changes
  - Memory/resource usage trends
  - Auto-heals by adjusting routing, restarting services, etc.

Usage:
    from src.agent_health_guardian import HealthGuardian
    guardian = HealthGuardian()
    report = await guardian.check_all()
    healed = await guardian.auto_heal()
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from src.pattern_agents import NODES


__all__ = [
    "HealthAlert",
    "HealthGuardian",
    "HealthReport",
    "NodeHealthCheck",
]

logger = logging.getLogger("jarvis.health_guardian")


@dataclass
class NodeHealthCheck:
    """Health check result for one node."""
    node: str
    reachable: bool
    latency_ms: float
    models_loaded: int = 0
    models_available: int = 0
    error: str = ""
    status: str = "unknown"  # healthy, degraded, offline


@dataclass
class HealthAlert:
    """A health alert requiring attention."""
    severity: str       # critical, warning, info
    target: str         # Node or pattern
    alert_type: str     # offline, degraded, slow, circuit_open, success_drop
    message: str
    action: str = ""    # Suggested action
    auto_healable: bool = False


@dataclass
class HealthReport:
    """Complete health report."""
    timestamp: str
    duration_ms: float
    node_checks: list[NodeHealthCheck]
    alerts: list[HealthAlert]
    overall_status: str   # healthy, degraded, critical
    healthy_nodes: int
    total_nodes: int
    auto_heal_actions: list[dict] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.healthy_nodes}/{self.total_nodes} nodes healthy | "
                f"{len(self.alerts)} alerts | Status: {self.overall_status}")


class HealthGuardian:
    """Proactive health monitoring and auto-healing."""

    # Node endpoints for health checks
    HEALTH_CHECKS = {
        "M1": {"url": "http://127.0.0.1:1234/api/v1/models", "type": "lmstudio"},
        "M2": {"url": "http://192.168.1.26:1234/api/v1/models", "type": "lmstudio"},
        "M3": {"url": "http://192.168.1.113:1234/api/v1/models", "type": "lmstudio"},
        "OL1": {"url": "http://127.0.0.1:11434/api/tags", "type": "ollama"},
    }

    def __init__(self):
        self._last_check: Optional[HealthReport] = None
        self._alert_history: list[HealthAlert] = []

    async def check_all(self) -> HealthReport:
        """Run health checks on all nodes."""
        t0 = time.perf_counter()
        node_checks = []

        async with httpx.AsyncClient() as client:
            tasks = [self._check_node(client, name, cfg) for name, cfg in self.HEALTH_CHECKS.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(self.HEALTH_CHECKS.keys(), results):
                if isinstance(result, Exception):
                    node_checks.append(NodeHealthCheck(
                        node=name, reachable=False, latency_ms=0,
                        error=str(result)[:100], status="offline",
                    ))
                else:
                    node_checks.append(result)

        # Generate alerts
        alerts = self._generate_alerts(node_checks)

        # Add routing-based alerts
        alerts.extend(self._check_routing_health())

        # Determine overall status
        healthy = sum(1 for n in node_checks if n.status == "healthy")
        total = len(node_checks)

        if healthy == 0:
            overall = "critical"
        elif healthy < total * 0.5:
            overall = "degraded"
        else:
            overall = "healthy"

        duration = (time.perf_counter() - t0) * 1000

        report = HealthReport(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            duration_ms=duration,
            node_checks=node_checks,
            alerts=alerts,
            overall_status=overall,
            healthy_nodes=healthy,
            total_nodes=total,
        )

        self._last_check = report
        self._alert_history.extend(alerts)

        return report

    async def _check_node(self, client: httpx.AsyncClient,
                          name: str, cfg: dict) -> NodeHealthCheck:
        """Check a single node's health."""
        t0 = time.perf_counter()
        try:
            r = await client.get(cfg["url"], timeout=5)
            ms = (time.perf_counter() - t0) * 1000

            if cfg["type"] == "lmstudio":
                data = r.json()
                models = data.get("data", data.get("models", []))
                loaded = sum(1 for m in models if m.get("loaded_instances"))
                available = len(models)
                status = "healthy" if loaded > 0 else "degraded"
                return NodeHealthCheck(
                    node=name, reachable=True, latency_ms=ms,
                    models_loaded=loaded, models_available=available,
                    status=status,
                )
            else:  # ollama
                data = r.json()
                models = data.get("models", [])
                return NodeHealthCheck(
                    node=name, reachable=True, latency_ms=ms,
                    models_loaded=len(models), models_available=len(models),
                    status="healthy" if models else "degraded",
                )

        except httpx.ConnectError:
            ms = (time.perf_counter() - t0) * 1000
            return NodeHealthCheck(
                node=name, reachable=False, latency_ms=ms,
                error="Connection refused", status="offline",
            )
        except httpx.TimeoutException:
            ms = (time.perf_counter() - t0) * 1000
            return NodeHealthCheck(
                node=name, reachable=False, latency_ms=ms,
                error="Timeout", status="offline",
            )
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            return NodeHealthCheck(
                node=name, reachable=False, latency_ms=ms,
                error=str(e)[:100], status="offline",
            )

    def _generate_alerts(self, checks: list[NodeHealthCheck]) -> list[HealthAlert]:
        """Generate alerts from health check results."""
        alerts = []
        for check in checks:
            if check.status == "offline":
                alerts.append(HealthAlert(
                    severity="critical",
                    target=check.node,
                    alert_type="offline",
                    message=f"{check.node} is offline: {check.error}",
                    action=f"Check if LM Studio/Ollama is running on {check.node}",
                    auto_healable=check.node in ("M1", "OL1"),
                ))
            elif check.status == "degraded":
                alerts.append(HealthAlert(
                    severity="warning",
                    target=check.node,
                    alert_type="degraded",
                    message=f"{check.node} degraded: {check.models_loaded} models loaded, {check.models_available} available",
                    action=f"Load a model on {check.node}",
                    auto_healable=check.node == "M1",
                ))
            elif check.latency_ms > 3000:
                alerts.append(HealthAlert(
                    severity="warning",
                    target=check.node,
                    alert_type="slow",
                    message=f"{check.node} health check slow: {check.latency_ms:.0f}ms",
                    action="Check network or node load",
                ))
        return alerts

    def _check_routing_health(self) -> list[HealthAlert]:
        """Check routing health from adaptive router."""
        alerts = []
        try:
            from src.adaptive_router import get_router
            router = get_router()
            recs = router.get_recommendations()
            for rec in recs:
                alerts.append(HealthAlert(
                    severity=rec.get("severity", "info"),
                    target=rec.get("node", rec.get("pattern", "?")),
                    alert_type=rec.get("type", "routing"),
                    message=rec["message"],
                ))
        except Exception:
            pass
        return alerts

    async def auto_heal(self) -> list[dict]:
        """Attempt to automatically fix detected issues."""
        if not self._last_check:
            self._last_check = await self.check_all()

        healed = []
        for alert in self._last_check.alerts:
            if not alert.auto_healable:
                continue

            if alert.alert_type == "degraded" and alert.target == "M1":
                # Try to load qwen3-8b on M1
                try:
                    async with httpx.AsyncClient() as c:
                        r = await c.post(
                            "http://127.0.0.1:1234/api/v1/models/load",
                            json={"model": "qwen3-8b"}, timeout=30,
                        )
                        if r.status_code == 200:
                            healed.append({
                                "action": "loaded_model",
                                "target": "M1:qwen3-8b",
                                "ok": True,
                            })
                except Exception as e:
                    healed.append({
                        "action": "load_failed",
                        "target": "M1:qwen3-8b",
                        "ok": False,
                        "error": str(e)[:100],
                    })

            elif alert.alert_type == "offline" and alert.target == "OL1":
                # Can't auto-restart Ollama safely, but log it
                healed.append({
                    "action": "alert_logged",
                    "target": "OL1",
                    "ok": False,
                    "message": "Ollama offline — manual restart needed: ollama serve",
                })

        self._last_check.auto_heal_actions = healed
        return healed

    def get_alert_history(self, limit: int = 50) -> list[dict]:
        """Get recent alert history."""
        return [
            {
                "severity": a.severity,
                "target": a.target,
                "type": a.alert_type,
                "message": a.message,
                "action": a.action,
            }
            for a in self._alert_history[-limit:]
        ]

    def get_summary(self) -> dict:
        """Quick health summary."""
        if not self._last_check:
            return {"status": "unknown", "message": "No health check run yet"}

        return {
            "status": self._last_check.overall_status,
            "healthy_nodes": self._last_check.healthy_nodes,
            "total_nodes": self._last_check.total_nodes,
            "alerts": len(self._last_check.alerts),
            "critical_alerts": sum(1 for a in self._last_check.alerts if a.severity == "critical"),
            "last_check": self._last_check.timestamp,
            "summary": self._last_check.summary,
        }
