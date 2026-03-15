"""JARVIS Agent Monitor — Real-time monitoring of all pattern agents.

Tracks:
  - Active dispatches per agent
  - Rolling latency/quality metrics (last 5 min)
  - Node health scores
  - Alert on degradation
  - Provides dashboard data for Electron UI

Usage:
    from src.agent_monitor import AgentMonitor
    monitor = AgentMonitor()
    monitor.record_dispatch(result)
    dashboard = monitor.get_dashboard()
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


__all__ = [
    "AgentMetrics",
    "AgentMonitor",
    "Alert",
    "NodeMetrics",
    "RollingMetric",
    "get_monitor",
]

logger = logging.getLogger("jarvis.agent_monitor")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")


@dataclass
class RollingMetric:
    """Rolling window metric tracker (last N seconds)."""
    window_s: float = 300  # 5 minutes
    _entries: deque = field(default_factory=deque)

    def add(self, value: float, timestamp: float = 0):
        ts = timestamp or time.time()
        self._entries.append((ts, value))
        self._prune()

    def _prune(self):
        cutoff = time.time() - self.window_s
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()

    @property
    def count(self) -> int:
        self._prune()
        return len(self._entries)

    @property
    def avg(self) -> float:
        self._prune()
        if not self._entries:
            return 0
        return sum(v for _, v in self._entries) / len(self._entries)

    @property
    def max(self) -> float:
        self._prune()
        return max((v for _, v in self._entries), default=0)

    @property
    def min(self) -> float:
        self._prune()
        return min((v for _, v in self._entries), default=0)

    @property
    def rate_per_sec(self) -> float:
        self._prune()
        if len(self._entries) < 2:
            return 0
        span = self._entries[-1][0] - self._entries[0][0]
        return len(self._entries) / max(0.1, span)


@dataclass
class AgentMetrics:
    """Metrics for one pattern agent."""
    pattern: str
    latency: RollingMetric = field(default_factory=lambda: RollingMetric(300))
    quality: RollingMetric = field(default_factory=lambda: RollingMetric(300))
    success: RollingMetric = field(default_factory=lambda: RollingMetric(300))
    total_dispatches: int = 0
    total_ok: int = 0
    last_dispatch_ts: float = 0
    last_node: str = ""
    last_strategy: str = ""


@dataclass
class NodeMetrics:
    """Metrics for one cluster node."""
    name: str
    latency: RollingMetric = field(default_factory=lambda: RollingMetric(300))
    success: RollingMetric = field(default_factory=lambda: RollingMetric(300))
    active_count: int = 0
    total_dispatches: int = 0


@dataclass
class Alert:
    """Monitor alert."""
    severity: str  # info, warning, critical
    message: str
    timestamp: float = field(default_factory=time.time)
    pattern: str = ""
    node: str = ""


class AgentMonitor:
    """Real-time agent monitoring."""

    def __init__(self):
        self._agent_metrics: dict[str, AgentMetrics] = {}
        self._node_metrics: dict[str, NodeMetrics] = {}
        self._alerts: deque[Alert] = deque(maxlen=100)
        self._start_time = time.time()

    def record_dispatch(self, pattern: str, node: str, strategy: str,
                        latency_ms: float, ok: bool, quality: float = 0):
        """Record a dispatch result."""
        now = time.time()

        # Agent metrics
        if pattern not in self._agent_metrics:
            self._agent_metrics[pattern] = AgentMetrics(pattern=pattern)
        am = self._agent_metrics[pattern]
        am.latency.add(latency_ms)
        am.quality.add(quality)
        am.success.add(1.0 if ok else 0.0)
        am.total_dispatches += 1
        am.total_ok += 1 if ok else 0
        am.last_dispatch_ts = now
        am.last_node = node
        am.last_strategy = strategy

        # Node metrics
        if node not in self._node_metrics:
            self._node_metrics[node] = NodeMetrics(name=node)
        nm = self._node_metrics[node]
        nm.latency.add(latency_ms)
        nm.success.add(1.0 if ok else 0.0)
        nm.total_dispatches += 1

        # Alert checks
        if am.success.count >= 5 and am.success.avg < 0.5:
            self._alerts.append(Alert(
                severity="critical",
                message=f"Agent {pattern} success rate dropped to {am.success.avg:.0%}",
                pattern=pattern, node=node,
            ))

        if am.latency.count >= 3 and am.latency.avg > 60000:
            self._alerts.append(Alert(
                severity="warning",
                message=f"Agent {pattern} avg latency {am.latency.avg:.0f}ms exceeds 60s",
                pattern=pattern,
            ))

        if nm.success.count >= 5 and nm.success.avg < 0.3:
            self._alerts.append(Alert(
                severity="critical",
                message=f"Node {node} appears down (success rate {nm.success.avg:.0%})",
                node=node,
            ))

    def get_dashboard(self) -> dict:
        """Get complete dashboard data for UI."""
        uptime = time.time() - self._start_time
        total_dispatches = sum(am.total_dispatches for am in self._agent_metrics.values())
        total_ok = sum(am.total_ok for am in self._agent_metrics.values())

        return {
            "uptime_s": round(uptime),
            "total_dispatches": total_dispatches,
            "success_rate": f"{total_ok / max(1, total_dispatches):.0%}",
            "agents": {
                pat: {
                    "dispatches": am.total_dispatches,
                    "ok": am.total_ok,
                    "rate": f"{am.total_ok / max(1, am.total_dispatches):.0%}",
                    "avg_ms": round(am.latency.avg),
                    "avg_quality": round(am.quality.avg, 2),
                    "rps": round(am.latency.rate_per_sec, 2),
                    "last_node": am.last_node,
                    "last_strategy": am.last_strategy,
                    "active": time.time() - am.last_dispatch_ts < 60,
                }
                for pat, am in sorted(self._agent_metrics.items())
            },
            "nodes": {
                name: {
                    "dispatches": nm.total_dispatches,
                    "avg_ms": round(nm.latency.avg),
                    "success_rate": f"{nm.success.avg:.0%}",
                    "rps": round(nm.latency.rate_per_sec, 2),
                }
                for name, nm in sorted(self._node_metrics.items())
            },
            "alerts": [
                {"severity": a.severity, "message": a.message,
                 "ago_s": round(time.time() - a.timestamp)}
                for a in list(self._alerts)[-10:]
            ],
        }

    def get_agent_detail(self, pattern: str) -> dict:
        """Detailed metrics for one agent."""
        am = self._agent_metrics.get(pattern)
        if not am:
            return {"error": f"No data for pattern: {pattern}"}
        return {
            "pattern": pattern,
            "total_dispatches": am.total_dispatches,
            "total_ok": am.total_ok,
            "rate": f"{am.total_ok / max(1, am.total_dispatches):.0%}",
            "latency": {
                "avg": round(am.latency.avg),
                "min": round(am.latency.min),
                "max": round(am.latency.max),
                "count_5min": am.latency.count,
            },
            "quality": {
                "avg": round(am.quality.avg, 3),
                "min": round(am.quality.min, 3),
                "max": round(am.quality.max, 3),
            },
            "last_node": am.last_node,
            "last_strategy": am.last_strategy,
            "last_dispatch_ago_s": round(time.time() - am.last_dispatch_ts),
        }

    def load_from_db(self, db_path: str = DB_PATH, limit: int = 500):
        """Load recent dispatch history into monitor metrics."""
        try:
            db = sqlite3.connect(db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT classified_type, node, strategy, latency_ms, success, quality_score
                FROM agent_dispatch_log
                ORDER BY rowid DESC LIMIT ?
            """, (limit,)).fetchall()
            db.close()

            for r in reversed(rows):  # oldest first
                self.record_dispatch(
                    pattern=r["classified_type"] or "unknown",
                    node=r["node"] or "?",
                    strategy=r["strategy"] or "?",
                    latency_ms=r["latency_ms"] or 0,
                    ok=bool(r["success"]),
                    quality=r["quality_score"] or 0,
                )
            logger.info(f"Loaded {len(rows)} dispatch records into monitor")
        except Exception as e:
            logger.warning(f"Failed to load from DB: {e}")


# Singleton
_monitor: Optional[AgentMonitor] = None

def get_monitor() -> AgentMonitor:
    global _monitor
    if _monitor is None:
        _monitor = AgentMonitor()
        _monitor.load_from_db()
    return _monitor
