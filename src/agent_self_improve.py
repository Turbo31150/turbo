"""JARVIS Agent Self-Improve — Continuous optimization cycle.

Runs improvement cycles that:
  1. Analyze dispatch_log for failure patterns
  2. Adjust agent strategies/nodes based on data
  3. Discover and register new patterns
  4. Learn semantic facts from history
  5. Optimize routing based on current cluster state
  6. Generate improvement report

Usage:
    from src.agent_self_improve import SelfImprover
    improver = SelfImprover()
    report = await improver.run_cycle()
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


__all__ = [
    "ImprovementAction",
    "ImprovementReport",
    "SelfImprover",
]

logger = logging.getLogger("jarvis.self_improve")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")


@dataclass
class ImprovementAction:
    """A single improvement action taken."""
    action_type: str      # strategy_change, node_swap, pattern_discovered, fact_learned, circuit_update, config_tune
    target: str           # Pattern or node affected
    description: str
    impact: str           # Expected impact
    confidence: float     # 0-1


@dataclass
class ImprovementReport:
    """Result of an improvement cycle."""
    cycle_id: int
    timestamp: str
    duration_ms: float
    actions: list[ImprovementAction]
    metrics_before: dict
    metrics_after: dict
    recommendations: list[str]

    @property
    def summary(self) -> str:
        return (f"Cycle #{self.cycle_id}: {len(self.actions)} actions in {self.duration_ms:.0f}ms | "
                f"{sum(1 for a in self.actions if a.confidence > 0.7)} high-confidence")


class SelfImprover:
    """Continuous improvement engine for the agent system."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._cycle_count = 0

    async def run_cycle(self) -> ImprovementReport:
        """Run a full improvement cycle."""
        t0 = time.perf_counter()
        self._cycle_count += 1
        actions = []

        # 1. Collect current metrics
        metrics_before = self._get_current_metrics()

        # 2. Optimize strategies based on dispatch data
        strategy_actions = self._optimize_strategies()
        actions.extend(strategy_actions)

        # 3. Discover new patterns
        discovery_actions = self._run_discovery()
        actions.extend(discovery_actions)

        # 4. Learn from episodic memory
        memory_actions = self._learn_from_memory()
        actions.extend(memory_actions)

        # 5. Update adaptive router
        router_actions = self._update_router()
        actions.extend(router_actions)

        # 6. Tune configuration
        config_actions = self._tune_config()
        actions.extend(config_actions)

        # 7. Collect after-metrics
        metrics_after = self._get_current_metrics()

        # 8. Generate recommendations
        recommendations = self._generate_recommendations(metrics_before, metrics_after, actions)

        duration = (time.perf_counter() - t0) * 1000

        report = ImprovementReport(
            cycle_id=self._cycle_count,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            duration_ms=duration,
            actions=actions,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            recommendations=recommendations,
        )

        # Persist report
        self._save_report(report)

        return report

    def _get_current_metrics(self) -> dict:
        """Collect current system metrics."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row

            # Overall stats
            overall = db.execute("""
                SELECT COUNT(*) as total,
                       SUM(success) as ok,
                       AVG(latency_ms) as avg_ms,
                       AVG(quality_score) as avg_q
                FROM agent_dispatch_log
            """).fetchone()

            # Per-node stats
            nodes = db.execute("""
                SELECT node, COUNT(*) as n, SUM(success) as ok,
                       AVG(latency_ms) as avg_ms
                FROM agent_dispatch_log WHERE node IS NOT NULL
                GROUP BY node
            """).fetchall()

            # Per-pattern stats
            patterns = db.execute("""
                SELECT classified_type as pattern, COUNT(*) as n,
                       SUM(success) as ok, AVG(latency_ms) as avg_ms
                FROM agent_dispatch_log WHERE classified_type IS NOT NULL
                GROUP BY classified_type
            """).fetchall()

            db.close()

            return {
                "total_dispatches": overall["total"],
                "success_rate": (overall["ok"] or 0) / max(1, overall["total"]),
                "avg_latency_ms": overall["avg_ms"] or 0,
                "avg_quality": overall["avg_q"] or 0,
                "nodes": {r["node"]: {"n": r["n"], "ok": r["ok"] or 0, "avg_ms": r["avg_ms"] or 0} for r in nodes},
                "patterns": {r["pattern"]: {"n": r["n"], "ok": r["ok"] or 0} for r in patterns},
            }
        except Exception:
            return {"total_dispatches": 0, "success_rate": 0, "avg_latency_ms": 0}

    def _optimize_strategies(self) -> list[ImprovementAction]:
        """Analyze which strategies work best per pattern and apply changes."""
        actions = []
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row

            # Find patterns with low success on current strategy
            rows = db.execute("""
                SELECT classified_type as pattern, strategy,
                       COUNT(*) as n, SUM(success) as ok,
                       AVG(latency_ms) as avg_ms
                FROM agent_dispatch_log
                WHERE classified_type IS NOT NULL
                GROUP BY classified_type, strategy
                HAVING n >= 5
                ORDER BY pattern, ok DESC
            """).fetchall()
            db.close()

            # Group by pattern, find best strategy
            from collections import defaultdict
            pattern_strats = defaultdict(list)
            for r in rows:
                rate = (r["ok"] or 0) / max(1, r["n"])
                pattern_strats[r["pattern"]].append({
                    "strategy": r["strategy"], "rate": rate, "n": r["n"], "avg_ms": r["avg_ms"],
                })

            for pattern, strats in pattern_strats.items():
                if len(strats) < 2:
                    continue
                best = max(strats, key=lambda s: s["rate"])
                worst = min(strats, key=lambda s: s["rate"])
                if best["rate"] - worst["rate"] > 0.2:
                    actions.append(ImprovementAction(
                        action_type="strategy_insight",
                        target=pattern,
                        description=f"Best strategy: {best['strategy']} ({best['rate']:.0%}) vs worst: {worst['strategy']} ({worst['rate']:.0%})",
                        impact=f"+{(best['rate'] - worst['rate'])*100:.0f}% success rate",
                        confidence=min(1, best["n"] / 20),
                    ))

        except Exception as e:
            logger.warning(f"Strategy optimization failed: {e}")
        return actions

    def _run_discovery(self) -> list[ImprovementAction]:
        """Run pattern discovery."""
        actions = []
        try:
            from src.pattern_discovery import PatternDiscovery
            d = PatternDiscovery()
            patterns = d.discover()
            if patterns:
                count = d.register_patterns(patterns)
                for p in patterns[:5]:
                    actions.append(ImprovementAction(
                        action_type="pattern_discovered",
                        target=p.pattern_type,
                        description=p.reason[:100],
                        impact=f"New pattern agent for '{p.pattern_type}'",
                        confidence=p.confidence,
                    ))
                if count > 0:
                    actions.append(ImprovementAction(
                        action_type="patterns_registered",
                        target="database",
                        description=f"Registered {count} new patterns in etoile.db",
                        impact=f"{count} new agent routing targets",
                        confidence=0.9,
                    ))
        except Exception as e:
            logger.warning(f"Discovery failed: {e}")
        return actions

    def _learn_from_memory(self) -> list[ImprovementAction]:
        """Learn semantic facts from episodic memory."""
        actions = []
        try:
            from src.agent_episodic_memory import get_episodic_memory
            mem = get_episodic_memory()
            learned = mem.learn_from_history()
            for fact in learned[:5]:
                actions.append(ImprovementAction(
                    action_type="fact_learned",
                    target=fact["fact"],
                    description=f"Confidence: {fact['confidence']}",
                    impact="Routing knowledge updated",
                    confidence=fact["confidence"],
                ))
        except Exception as e:
            logger.warning(f"Memory learning failed: {e}")
        return actions

    def _update_router(self) -> list[ImprovementAction]:
        """Update adaptive router based on current data."""
        actions = []
        try:
            from src.adaptive_router import get_router
            router = get_router()
            recs = router.get_recommendations()
            for rec in recs:
                actions.append(ImprovementAction(
                    action_type="router_alert",
                    target=rec.get("node", rec.get("pattern", "?")),
                    description=rec["message"][:100],
                    impact="Routing adjusted",
                    confidence=0.8 if rec["severity"] == "high" else 0.5,
                ))
        except Exception as e:
            logger.warning(f"Router update failed: {e}")
        return actions

    def _tune_config(self) -> list[ImprovementAction]:
        """Tune configuration parameters based on metrics."""
        actions = []
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row

            # Check if any pattern has very high latency
            slow = db.execute("""
                SELECT classified_type as pattern, AVG(latency_ms) as avg_ms, COUNT(*) as n
                FROM agent_dispatch_log
                WHERE classified_type IS NOT NULL AND latency_ms > 30000
                GROUP BY classified_type
                HAVING n >= 3
            """).fetchall()
            db.close()

            for r in slow:
                actions.append(ImprovementAction(
                    action_type="config_tune",
                    target=r["pattern"],
                    description=f"Pattern '{r['pattern']}' avg {r['avg_ms']:.0f}ms ({r['n']} slow calls)",
                    impact="Consider reducing max_tokens or switching node",
                    confidence=min(1, r["n"] / 10),
                ))

        except Exception as e:
            logger.warning(f"Config tuning failed: {e}")
        return actions

    def _generate_recommendations(self, before: dict, after: dict,
                                    actions: list[ImprovementAction]) -> list[str]:
        """Generate human-readable recommendations."""
        recs = []

        sr = before.get("success_rate", 0)
        if sr < 0.7:
            recs.append(f"Success rate is {sr:.0%} — focus traffic on M1 and OL1")

        avg_ms = before.get("avg_latency_ms", 0)
        if avg_ms > 30000:
            recs.append(f"Avg latency {avg_ms:.0f}ms — reduce M2/M3 usage, increase M1 concurrency")

        high_conf = [a for a in actions if a.confidence > 0.7]
        if high_conf:
            recs.append(f"{len(high_conf)} high-confidence actions found — apply them")

        nodes = before.get("nodes", {})
        for node, stats in nodes.items():
            rate = stats.get("ok", 0) / max(1, stats.get("n", 0))
            if rate < 0.3 and stats.get("n", 0) >= 10:
                recs.append(f"Disable {node} from routing (only {rate:.0%} success on {stats['n']} calls)")

        return recs

    def _save_report(self, report: ImprovementReport):
        """Save improvement report to DB."""
        try:
            db = sqlite3.connect(self.db_path)
            db.execute("""
                CREATE TABLE IF NOT EXISTS agent_improvement_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER,
                    timestamp TEXT,
                    duration_ms REAL,
                    actions_count INTEGER,
                    high_confidence INTEGER,
                    success_rate_before REAL,
                    success_rate_after REAL,
                    recommendations TEXT,
                    summary TEXT
                )
            """)
            db.execute("""
                INSERT INTO agent_improvement_reports
                (cycle_id, timestamp, duration_ms, actions_count, high_confidence,
                 success_rate_before, success_rate_after, recommendations, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report.cycle_id, report.timestamp, report.duration_ms,
                len(report.actions),
                sum(1 for a in report.actions if a.confidence > 0.7),
                report.metrics_before.get("success_rate", 0),
                report.metrics_after.get("success_rate", 0),
                "\n".join(report.recommendations),
                report.summary,
            ))
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to save report: {e}")

    def get_history(self, limit: int = 10) -> list[dict]:
        """Get improvement cycle history."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT * FROM agent_improvement_reports
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            db.close()
            return [dict(r) for r in rows]
        except Exception:
            return []


# CLI
async def _main():
    improver = SelfImprover()
    report = await improver.run_cycle()
    print(f"\n=== SELF-IMPROVE CYCLE #{report.cycle_id} ===")
    print(f"Duration: {report.duration_ms:.0f}ms | Actions: {len(report.actions)}")
    print(f"Before: {report.metrics_before.get('success_rate', 0):.0%} success, "
          f"{report.metrics_before.get('avg_latency_ms', 0):.0f}ms avg")

    for a in report.actions:
        icon = {"strategy_insight": "S", "pattern_discovered": "P", "fact_learned": "F",
                "router_alert": "R", "config_tune": "C", "patterns_registered": "+"}
        print(f"  [{icon.get(a.action_type, '?')}] {a.confidence:.0%} {a.target}: {a.description[:80]}")

    if report.recommendations:
        print("\nRecommendations:")
        for r in report.recommendations:
            print(f"  -> {r}")


if __name__ == "__main__":
    asyncio.run(_main())
