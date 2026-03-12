"""Health Probe — Deep health checks with dependency verification and degraded states."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Callable



__all__ = [
    "CheckResult",
    "HealthProbe",
    "HealthStatus",
    "ProbeConfig",
]

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class CheckResult:
    name: str
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class ProbeConfig:
    name: str
    check_fn: Callable[[], bool | str]
    critical: bool = True  # if critical, failure → UNHEALTHY; else → DEGRADED
    timeout_s: float = 5.0
    interval_s: float = 30.0
    last_result: CheckResult | None = None


class HealthProbe:
    """Deep health check system with dependency verification."""

    def __init__(self):
        self._probes: dict[str, ProbeConfig] = {}
        self._history: list[CheckResult] = []
        self._max_history = 500
        self._lock = Lock()

    # ── Probe Registration ──────────────────────────────────────────
    def register(self, name: str, check_fn: Callable, critical: bool = True,
                 timeout_s: float = 5.0, interval_s: float = 30.0) -> None:
        with self._lock:
            self._probes[name] = ProbeConfig(
                name=name, check_fn=check_fn, critical=critical,
                timeout_s=timeout_s, interval_s=interval_s,
            )

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._probes.pop(name, None) is not None

    def list_probes(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "name": p.name, "critical": p.critical,
                    "timeout_s": p.timeout_s, "interval_s": p.interval_s,
                    "last_status": p.last_result.status.value if p.last_result else "unknown",
                }
                for p in self._probes.values()
            ]

    # ── Check Execution ─────────────────────────────────────────────
    def run_check(self, name: str) -> CheckResult | None:
        probe = self._probes.get(name)
        if not probe:
            return None
        t0 = time.time()
        try:
            result = probe.check_fn()
            latency = (time.time() - t0) * 1000
            if result is True or result == "ok":
                status = HealthStatus.HEALTHY
                msg = "OK"
            elif isinstance(result, str):
                status = HealthStatus.DEGRADED
                msg = result
            else:
                status = HealthStatus.UNHEALTHY if probe.critical else HealthStatus.DEGRADED
                msg = "check returned falsy"
        except Exception as exc:
            latency = (time.time() - t0) * 1000
            status = HealthStatus.UNHEALTHY if probe.critical else HealthStatus.DEGRADED
            msg = str(exc)

        cr = CheckResult(name=name, status=status, latency_ms=round(latency, 2), message=msg)
        with self._lock:
            probe.last_result = cr
            self._history.append(cr)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        return cr

    def run_all(self) -> list[CheckResult]:
        results = []
        for name in list(self._probes.keys()):
            r = self.run_check(name)
            if r:
                results.append(r)
        return results

    # ── Overall Status ──────────────────────────────────────────────
    def _compute_overall(self) -> HealthStatus:
        """Compute overall status — caller must hold lock or ensure safety."""
        if not self._probes:
            return HealthStatus.UNKNOWN
        statuses = []
        for p in self._probes.values():
            if p.last_result:
                statuses.append(p.last_result.status)
            else:
                statuses.append(HealthStatus.UNKNOWN)
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        if HealthStatus.UNKNOWN in statuses:
            return HealthStatus.UNKNOWN
        return HealthStatus.HEALTHY

    def overall_status(self) -> HealthStatus:
        with self._lock:
            return self._compute_overall()

    # ── History ─────────────────────────────────────────────────────
    def get_history(self, name: str | None = None, limit: int = 50) -> list[dict]:
        with self._lock:
            items = self._history
            if name:
                items = [r for r in items if r.name == name]
            return [
                {
                    "name": r.name, "status": r.status.value,
                    "latency_ms": r.latency_ms, "message": r.message,
                    "timestamp": r.timestamp,
                }
                for r in items[-limit:]
            ]

    # ── Stats ───────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with self._lock:
            total_checks = len(self._history)
            healthy = sum(1 for r in self._history if r.status == HealthStatus.HEALTHY)
            degraded = sum(1 for r in self._history if r.status == HealthStatus.DEGRADED)
            unhealthy = sum(1 for r in self._history if r.status == HealthStatus.UNHEALTHY)
            avg_latency = 0.0
            if self._history:
                avg_latency = round(sum(r.latency_ms for r in self._history) / len(self._history), 2)
            return {
                "total_probes": len(self._probes),
                "critical_probes": sum(1 for p in self._probes.values() if p.critical),
                "total_checks": total_checks,
                "healthy": healthy,
                "degraded": degraded,
                "unhealthy": unhealthy,
                "avg_latency_ms": avg_latency,
                "overall": self._compute_overall().value,
            }


health_probe = HealthProbe()
