"""JARVIS Reflection Engine — Meta-cognitive analysis of system behavior.

Provides deep introspection into:
  - Dispatch patterns and quality trends over time
  - Agent performance evolution
  - Cowork script effectiveness
  - System-wide bottlenecks and opportunities
  - Automatic insight generation with actionable recommendations

Usage:
    from src.reflection_engine import ReflectionEngine, get_reflection
    engine = get_reflection()
    insights = engine.reflect()
    timeline = engine.timeline_analysis(hours=24)
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


__all__ = [
    "Insight",
    "ReflectionEngine",
    "get_reflection",
]

logger = logging.getLogger("jarvis.reflection_engine")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")


@dataclass
class Insight:
    """A system insight from reflection."""
    category: str       # performance, quality, reliability, efficiency, growth
    severity: str       # info, warning, critical
    title: str
    description: str
    metric_value: float = 0
    recommendation: str = ""
    data: dict = field(default_factory=dict)


class ReflectionEngine:
    """Meta-cognitive analysis engine for continuous improvement."""

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                CREATE TABLE IF NOT EXISTS reflection_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT, severity TEXT, title TEXT,
                    metric_value REAL, recommendation TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.commit()
            db.close()
        except Exception:
            pass

    def reflect(self) -> list[Insight]:
        """Run full reflection and generate insights."""
        insights = []
        insights.extend(self._reflect_quality())
        insights.extend(self._reflect_performance())
        insights.extend(self._reflect_reliability())
        insights.extend(self._reflect_efficiency())
        insights.extend(self._reflect_growth())
        insights.extend(self._reflect_benchmark_trend())

        # Sort by severity
        sev_order = {"critical": 0, "warning": 1, "info": 2}
        insights.sort(key=lambda i: sev_order.get(i.severity, 9))

        # Log top insights
        for ins in insights[:10]:
            self._log_insight(ins)

        return insights

    def _reflect_quality(self) -> list[Insight]:
        """Insights about output quality."""
        insights = []
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            # Overall quality trend
            recent_q = db.execute("""
                SELECT AVG(quality) FROM dispatch_pipeline_log
                WHERE id > (SELECT COALESCE(MAX(id), 0) - 50 FROM dispatch_pipeline_log)
            """).fetchone()[0] or 0

            older_q = db.execute("""
                SELECT AVG(quality) FROM dispatch_pipeline_log
                WHERE id <= (SELECT COALESCE(MAX(id), 0) - 50 FROM dispatch_pipeline_log)
                AND id > (SELECT COALESCE(MAX(id), 0) - 100 FROM dispatch_pipeline_log)
            """).fetchone()[0] or 0

            if recent_q and older_q:
                if recent_q > older_q * 1.1:
                    insights.append(Insight(
                        category="quality", severity="info",
                        title="Quality improvement detected",
                        description=f"Quality up from {older_q:.3f} to {recent_q:.3f} (+{((recent_q-older_q)/older_q*100):.1f}%)",
                        metric_value=recent_q,
                        recommendation="Continue current strategy",
                    ))
                elif recent_q < older_q * 0.8:
                    insights.append(Insight(
                        category="quality", severity="warning",
                        title="Quality degradation detected",
                        description=f"Quality dropped from {older_q:.3f} to {recent_q:.3f} ({((recent_q-older_q)/older_q*100):.1f}%)",
                        metric_value=recent_q,
                        recommendation="Investigate recent dispatches and gate failures",
                    ))

            # Worst patterns by quality
            worst = db.execute("""
                SELECT pattern, AVG(quality) as q, COUNT(*) as n
                FROM dispatch_pipeline_log
                WHERE id > (SELECT COALESCE(MAX(id), 0) - 200 FROM dispatch_pipeline_log)
                GROUP BY pattern HAVING n > 3
                ORDER BY q ASC LIMIT 3
            """).fetchall()

            for w in worst:
                if (w["q"] or 0) < 0.4:
                    insights.append(Insight(
                        category="quality", severity="warning",
                        title=f"Low quality pattern: {w['pattern']}",
                        description=f"Pattern '{w['pattern']}' avg quality {w['q']:.3f} over {w['n']} dispatches",
                        metric_value=w["q"] or 0,
                        recommendation=f"Consider temperature adjustment or model upgrade for '{w['pattern']}'",
                        data={"pattern": w["pattern"], "count": w["n"]},
                    ))

            db.close()
        except Exception:
            pass
        return insights

    def _reflect_performance(self) -> list[Insight]:
        """Insights about latency and throughput."""
        insights = []
        try:
            db = sqlite3.connect(DB_PATH)

            # Average pipeline time
            avg_pipe = db.execute("""
                SELECT AVG(pipeline_ms) FROM dispatch_pipeline_log
                WHERE id > (SELECT COALESCE(MAX(id), 0) - 100 FROM dispatch_pipeline_log)
            """).fetchone()[0] or 0

            if avg_pipe > 30000:
                insights.append(Insight(
                    category="performance", severity="warning",
                    title="High average pipeline latency",
                    description=f"Average pipeline time: {avg_pipe:.0f}ms (target: <15000ms)",
                    metric_value=avg_pipe,
                    recommendation="Check node health, consider faster models or reducing pipeline steps",
                ))
            elif avg_pipe > 0 and avg_pipe < 5000:
                insights.append(Insight(
                    category="performance", severity="info",
                    title="Excellent pipeline performance",
                    description=f"Average pipeline time: {avg_pipe:.0f}ms",
                    metric_value=avg_pipe,
                ))

            # Slowest nodes
            slow_nodes = db.execute("""
                SELECT node, AVG(latency_ms) as lat, COUNT(*) as n
                FROM dispatch_pipeline_log
                WHERE id > (SELECT COALESCE(MAX(id), 0) - 200 FROM dispatch_pipeline_log) AND node != ''
                GROUP BY node HAVING n > 3
                ORDER BY lat DESC LIMIT 3
            """).fetchall()

            for sn in slow_nodes:
                if (sn[1] or 0) > 20000:
                    insights.append(Insight(
                        category="performance", severity="warning",
                        title=f"Slow node: {sn[0]}",
                        description=f"Node {sn[0]} avg latency {sn[1]:.0f}ms over {sn[2]} dispatches",
                        metric_value=sn[1] or 0,
                        recommendation=f"Consider redistributing load away from {sn[0]}",
                    ))

            db.close()
        except Exception:
            pass
        return insights

    def _reflect_reliability(self) -> list[Insight]:
        """Insights about success rates and failures."""
        insights = []
        try:
            db = sqlite3.connect(DB_PATH)

            total = db.execute("SELECT COUNT(*) FROM dispatch_pipeline_log").fetchone()[0]
            ok = db.execute("SELECT COUNT(*) FROM dispatch_pipeline_log WHERE success").fetchone()[0]
            rate = ok / max(1, total)

            if rate < 0.8 and total > 20:
                insights.append(Insight(
                    category="reliability", severity="critical",
                    title="Low overall success rate",
                    description=f"Success rate: {rate:.1%} ({ok}/{total})",
                    metric_value=rate,
                    recommendation="Check node connectivity and model availability",
                ))
            elif rate >= 0.95 and total > 20:
                insights.append(Insight(
                    category="reliability", severity="info",
                    title="Excellent reliability",
                    description=f"Success rate: {rate:.1%} ({ok}/{total})",
                    metric_value=rate,
                ))

            # Fallback frequency
            fb = db.execute("SELECT COUNT(*) FROM dispatch_pipeline_log WHERE fallback_used").fetchone()[0]
            fb_rate = fb / max(1, total)
            if fb_rate > 0.2 and total > 20:
                insights.append(Insight(
                    category="reliability", severity="warning",
                    title="High fallback rate",
                    description=f"Fallback used in {fb_rate:.1%} of dispatches ({fb}/{total})",
                    metric_value=fb_rate,
                    recommendation="Primary nodes may be unreliable, check circuit breakers",
                ))

            db.close()
        except Exception:
            pass
        return insights

    def _reflect_efficiency(self) -> list[Insight]:
        """Insights about resource utilization."""
        insights = []
        try:
            db = sqlite3.connect(DB_PATH)

            # Node utilization
            node_usage = db.execute("""
                SELECT node, COUNT(*) as n
                FROM dispatch_pipeline_log
                WHERE id > (SELECT COALESCE(MAX(id), 0) - 200 FROM dispatch_pipeline_log) AND node != ''
                GROUP BY node ORDER BY n DESC
            """).fetchall()

            total_dispatches = sum(n[1] for n in node_usage)
            if node_usage and total_dispatches > 10:
                top_node = node_usage[0]
                top_pct = top_node[1] / total_dispatches
                if top_pct > 0.8:
                    insights.append(Insight(
                        category="efficiency", severity="warning",
                        title=f"Over-reliance on {top_node[0]}",
                        description=f"{top_node[0]} handles {top_pct:.0%} of all dispatches",
                        metric_value=top_pct,
                        recommendation="Distribute load across more nodes for resilience",
                    ))

            # Enrichment usage
            enriched = db.execute("""
                SELECT COUNT(*) FROM dispatch_pipeline_log WHERE enriched
            """).fetchone()[0]
            if total_dispatches > 20:
                enrich_rate = enriched / max(1, total_dispatches)
                if enrich_rate < 0.1:
                    insights.append(Insight(
                        category="efficiency", severity="info",
                        title="Low memory enrichment usage",
                        description=f"Only {enrich_rate:.0%} of dispatches use episodic memory",
                        metric_value=enrich_rate,
                        recommendation="Enable memory enrichment for context-aware responses",
                    ))

            db.close()
        except Exception:
            pass
        return insights

    def _reflect_growth(self) -> list[Insight]:
        """Insights about system growth and patterns."""
        insights = []
        try:
            db = sqlite3.connect(DB_PATH)

            # Pattern count evolution
            total_patterns = db.execute("SELECT COUNT(*) FROM agent_patterns").fetchone()[0]
            total_dispatches = db.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]

            insights.append(Insight(
                category="growth", severity="info",
                title="System scale",
                description=f"{total_patterns} patterns, {total_dispatches} dispatches",
                metric_value=total_patterns,
            ))

            # Unique patterns used recently
            unique_recent = db.execute("""
                SELECT COUNT(DISTINCT pattern) FROM dispatch_pipeline_log
                WHERE id > (SELECT COALESCE(MAX(id), 0) - 100 FROM dispatch_pipeline_log)
            """).fetchone()[0]

            if unique_recent and total_patterns > 10:
                usage_rate = unique_recent / total_patterns
                if usage_rate < 0.2:
                    insights.append(Insight(
                        category="growth", severity="info",
                        title="Many unused patterns",
                        description=f"Only {unique_recent}/{total_patterns} patterns used recently ({usage_rate:.0%})",
                        metric_value=usage_rate,
                        recommendation="Consider deprecating unused patterns or activating dormant ones",
                    ))

            db.close()
        except Exception:
            pass
        return insights

    def _reflect_benchmark_trend(self) -> list[Insight]:
        """Insights from quick benchmark trend data."""
        insights = []
        try:
            db = sqlite3.connect(DB_PATH)
            rows = db.execute("""
                SELECT rate, duration_s, timestamp FROM benchmark_quick
                ORDER BY id DESC LIMIT 10
            """).fetchall()
            db.close()

            if not rows:
                return insights

            latest_rate = rows[0][0]
            rates = [r[0] for r in rows]
            avg_rate = sum(rates) / len(rates)

            if latest_rate >= 0.8:
                insights.append(Insight(
                    category="quality", severity="info",
                    title="Benchmark target reached",
                    description=f"Latest benchmark: {latest_rate*100:.0f}% (target: 80%+)",
                    metric_value=latest_rate,
                ))
            elif latest_rate < 0.6:
                insights.append(Insight(
                    category="quality", severity="critical",
                    title="Benchmark critically low",
                    description=f"Latest benchmark: {latest_rate*100:.0f}% — needs route/prompt optimization",
                    metric_value=latest_rate,
                    recommendation="Run self_improvement.suggest_improvements() and apply fixes",
                ))

            if len(rates) >= 3:
                trend = rates[0] - rates[-1]
                if trend > 0.1:
                    insights.append(Insight(
                        category="growth", severity="info",
                        title="Benchmark improving",
                        description=f"Benchmark up {trend*100:.0f}% over last {len(rates)} runs ({rates[-1]*100:.0f}% -> {rates[0]*100:.0f}%)",
                        metric_value=trend,
                    ))
                elif trend < -0.1:
                    insights.append(Insight(
                        category="quality", severity="warning",
                        title="Benchmark declining",
                        description=f"Benchmark down {abs(trend)*100:.0f}% over last {len(rates)} runs",
                        metric_value=trend,
                        recommendation="Check node health and recent route changes",
                    ))
        except Exception:
            pass
        return insights

    def timeline_analysis(self, hours: int = 24) -> dict:
        """Analyze dispatch timeline over N hours."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            rows = db.execute("""
                SELECT pattern, node, quality, latency_ms, pipeline_ms,
                       success, fallback_used, enriched, timestamp
                FROM dispatch_pipeline_log
                WHERE timestamp > datetime('now', ?)
                ORDER BY id DESC
            """, (f"-{hours} hours",)).fetchall()

            db.close()

            if not rows:
                return {"period_hours": hours, "dispatches": 0, "message": "No data in period"}

            qualities = [r["quality"] for r in rows if r["quality"]]
            latencies = [r["latency_ms"] for r in rows if r["latency_ms"]]
            pipelines = [r["pipeline_ms"] for r in rows if r["pipeline_ms"]]

            return {
                "period_hours": hours,
                "dispatches": len(rows),
                "success_rate": round(sum(1 for r in rows if r["success"]) / len(rows), 3),
                "avg_quality": round(sum(qualities) / max(1, len(qualities)), 3) if qualities else 0,
                "avg_latency_ms": round(sum(latencies) / max(1, len(latencies)), 0) if latencies else 0,
                "avg_pipeline_ms": round(sum(pipelines) / max(1, len(pipelines)), 0) if pipelines else 0,
                "fallback_rate": round(sum(1 for r in rows if r["fallback_used"]) / len(rows), 3),
                "enrichment_rate": round(sum(1 for r in rows if r["enriched"]) / len(rows), 3),
                "patterns_used": list(set(r["pattern"] for r in rows)),
                "nodes_used": list(set(r["node"] for r in rows if r["node"])),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_summary(self) -> dict:
        """Quick system summary with key metrics."""
        try:
            db = sqlite3.connect(DB_PATH)

            # Core metrics
            total = db.execute("SELECT COUNT(*) FROM dispatch_pipeline_log").fetchone()[0]
            ok = db.execute("SELECT COUNT(*) FROM dispatch_pipeline_log WHERE success").fetchone()[0]
            avg_q = db.execute("SELECT AVG(quality) FROM dispatch_pipeline_log WHERE success").fetchone()[0] or 0
            patterns = db.execute("SELECT COUNT(*) FROM agent_patterns").fetchone()[0]
            dispatches = db.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]

            # Gate stats
            gate_total = db.execute("SELECT COUNT(*) FROM quality_gate_log").fetchone()[0]
            gate_pass = db.execute("SELECT COUNT(*) FROM quality_gate_log WHERE passed").fetchone()[0]

            # Improvement stats
            imp_total = 0
            imp_applied = 0
            try:
                imp_total = db.execute("SELECT COUNT(*) FROM self_improvement_log").fetchone()[0]
                imp_applied = db.execute("SELECT COUNT(*) FROM self_improvement_log WHERE applied").fetchone()[0]
            except Exception:
                pass

            db.close()

            return {
                "system_health": round(min(100, (ok / max(1, total)) * 50 + avg_q * 50), 1),
                "total_pipeline_dispatches": total,
                "success_rate": round(ok / max(1, total), 3),
                "avg_quality": round(avg_q, 3),
                "total_patterns": patterns,
                "total_dispatches": dispatches,
                "gate_pass_rate": round(gate_pass / max(1, gate_total), 3),
                "improvements_applied": imp_applied,
                "improvements_total": imp_total,
            }
        except Exception as e:
            return {"error": str(e)}

    def _log_insight(self, insight: Insight):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                INSERT INTO reflection_log
                (category, severity, title, metric_value, recommendation)
                VALUES (?, ?, ?, ?, ?)
            """, (insight.category, insight.severity, insight.title,
                  insight.metric_value, insight.recommendation))
            db.commit()
            db.close()
        except Exception:
            pass

    def get_stats(self) -> dict:
        try:
            db = sqlite3.connect(DB_PATH)
            total = db.execute("SELECT COUNT(*) FROM reflection_log").fetchone()[0]
            by_severity = db.execute("""
                SELECT severity, COUNT(*) FROM reflection_log GROUP BY severity
            """).fetchall()
            by_category = db.execute("""
                SELECT category, COUNT(*) FROM reflection_log GROUP BY category
            """).fetchall()
            db.close()
            return {
                "total_insights": total,
                "by_severity": {r[0]: r[1] for r in by_severity},
                "by_category": {r[0]: r[1] for r in by_category},
            }
        except Exception:
            return {"total_insights": 0}


_reflection: Optional[ReflectionEngine] = None

def get_reflection() -> ReflectionEngine:
    global _reflection
    if _reflection is None:
        _reflection = ReflectionEngine()
    return _reflection
