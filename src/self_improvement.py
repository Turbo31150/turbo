"""JARVIS Self-Improvement Loop — Continuous quality optimization.

Analyzes quality gate failures and dispatch trends to auto-adjust:
  - Agent parameters (temperature, max_tokens, system_prompt enhancements)
  - Node routing preferences (shift away from failing nodes)
  - Pattern thresholds (adapt quality gate per pattern)
  - Prompt templates (learn from high-quality dispatches)

Usage:
    from src.self_improvement import SelfImprover, get_improver
    improver = get_improver()
    report = improver.analyze()
    actions = improver.suggest_improvements()
    applied = improver.apply_improvements(auto=True)
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


__all__ = [
    "ImprovementAction",
    "SelfImprover",
    "get_improver",
]

logger = logging.getLogger("jarvis.self_improvement")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")


@dataclass
class ImprovementAction:
    """A suggested improvement action."""
    action_type: str       # route_shift, temp_adjust, tokens_adjust, prompt_enhance, gate_tune
    target: str            # pattern or node
    description: str
    priority: str          # critical, high, medium, low
    params: dict = field(default_factory=dict)
    applied: bool = False
    result: str = ""


class SelfImprover:
    """Analyzes system performance and suggests/applies improvements."""

    def __init__(self):
        self._history: list[dict] = []
        self._ensure_table()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                CREATE TABLE IF NOT EXISTS self_improvement_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT, target TEXT, description TEXT,
                    priority TEXT, params TEXT, applied INTEGER,
                    result TEXT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.commit()
            db.close()
        except Exception:
            pass

    def analyze(self) -> dict:
        """Analyze current system performance across all subsystems."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            # 1. Quality gate failure analysis
            gate_failures = db.execute("""
                SELECT pattern, failed_gates, COUNT(*) as n, AVG(overall_score) as avg_score
                FROM quality_gate_log WHERE NOT passed
                GROUP BY pattern, failed_gates ORDER BY n DESC LIMIT 20
            """).fetchall()

            # 2. Node performance trends (last 200 dispatches)
            node_trends = db.execute("""
                SELECT node,
                       COUNT(*) as n,
                       AVG(quality) as avg_q,
                       AVG(latency_ms) as avg_lat,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
                       SUM(CASE WHEN fallback_used THEN 1 ELSE 0 END) as fallbacks
                FROM dispatch_pipeline_log
                WHERE id > (SELECT MAX(id) - 200 FROM dispatch_pipeline_log)
                GROUP BY node ORDER BY avg_q DESC
            """).fetchall()

            # 3. Pattern quality distribution
            pattern_quality = db.execute("""
                SELECT pattern,
                       COUNT(*) as n,
                       AVG(quality) as avg_q,
                       MIN(quality) as min_q,
                       MAX(quality) as max_q,
                       AVG(pipeline_ms) as avg_pipe
                FROM dispatch_pipeline_log
                WHERE id > (SELECT MAX(id) - 500 FROM dispatch_pipeline_log)
                GROUP BY pattern ORDER BY avg_q ASC
            """).fetchall()

            # 4. Fallback frequency
            fallback_stats = db.execute("""
                SELECT pattern, node, COUNT(*) as n
                FROM dispatch_pipeline_log WHERE fallback_used
                GROUP BY pattern, node ORDER BY n DESC LIMIT 15
            """).fetchall()

            # 5. Overall health score
            total = db.execute("SELECT COUNT(*) FROM dispatch_pipeline_log").fetchone()[0]
            ok_total = db.execute("SELECT COUNT(*) FROM dispatch_pipeline_log WHERE success").fetchone()[0]
            avg_q = db.execute("SELECT AVG(quality) FROM dispatch_pipeline_log WHERE success").fetchone()[0] or 0

            db.close()

            return {
                "health_score": round(min(100, (ok_total / max(1, total)) * 50 + avg_q * 50), 1),
                "total_dispatches": total,
                "success_rate": round(ok_total / max(1, total), 3),
                "avg_quality": round(avg_q, 3),
                "gate_failures": [
                    {"pattern": r["pattern"], "failed_gates": r["failed_gates"],
                     "count": r["n"], "avg_score": round(r["avg_score"] or 0, 3)}
                    for r in gate_failures
                ],
                "node_trends": [
                    {"node": r["node"], "dispatches": r["n"],
                     "avg_quality": round(r["avg_q"] or 0, 3),
                     "avg_latency_ms": round(r["avg_lat"] or 0, 0),
                     "success_rate": round(r["success_rate"] or 0, 1),
                     "fallbacks": r["fallbacks"]}
                    for r in node_trends
                ],
                "pattern_quality": [
                    {"pattern": r["pattern"], "dispatches": r["n"],
                     "avg_quality": round(r["avg_q"] or 0, 3),
                     "min_quality": round(r["min_q"] or 0, 3),
                     "max_quality": round(r["max_q"] or 0, 3),
                     "avg_pipeline_ms": round(r["avg_pipe"] or 0, 0)}
                    for r in pattern_quality
                ],
                "fallback_hotspots": [
                    {"pattern": r["pattern"], "node": r["node"], "count": r["n"]}
                    for r in fallback_stats
                ],
            }
        except Exception as e:
            return {"error": str(e)}

    def suggest_improvements(self) -> list[ImprovementAction]:
        """Generate improvement suggestions based on analysis."""
        analysis = self.analyze()
        if "error" in analysis:
            return []

        actions = []

        # 1. Route shifts for underperforming nodes
        for nt in analysis.get("node_trends", []):
            if nt["success_rate"] < 70 and nt["dispatches"] > 5:
                actions.append(ImprovementAction(
                    action_type="route_shift",
                    target=nt["node"],
                    description=f"Node {nt['node']} a un taux de succes de {nt['success_rate']}% "
                                f"- rediriger le trafic vers un noeud plus fiable",
                    priority="high",
                    params={"from_node": nt["node"], "success_rate": nt["success_rate"]},
                ))

            if nt["avg_latency_ms"] > 30000 and nt["dispatches"] > 3:
                actions.append(ImprovementAction(
                    action_type="route_shift",
                    target=nt["node"],
                    description=f"Node {nt['node']} latence moyenne {nt['avg_latency_ms']:.0f}ms "
                                f"- considerer un noeud plus rapide",
                    priority="medium",
                    params={"from_node": nt["node"], "avg_latency_ms": nt["avg_latency_ms"]},
                ))

        # 2. Temperature adjustments for low-quality patterns
        for pq in analysis.get("pattern_quality", []):
            if pq["avg_quality"] < 0.3 and pq["dispatches"] > 3:
                actions.append(ImprovementAction(
                    action_type="temp_adjust",
                    target=pq["pattern"],
                    description=f"Pattern '{pq['pattern']}' qualite moyenne {pq['avg_quality']} "
                                f"- baisser temperature pour plus de coherence",
                    priority="high",
                    params={"pattern": pq["pattern"], "suggested_temp": 0.1,
                            "current_avg_q": pq["avg_quality"]},
                ))
            elif pq["max_quality"] - pq["min_quality"] > 0.5 and pq["dispatches"] > 5:
                actions.append(ImprovementAction(
                    action_type="temp_adjust",
                    target=pq["pattern"],
                    description=f"Pattern '{pq['pattern']}' variance qualite elevee "
                                f"({pq['min_quality']:.2f}-{pq['max_quality']:.2f}) "
                                f"- stabiliser avec temperature plus basse",
                    priority="medium",
                    params={"pattern": pq["pattern"], "suggested_temp": 0.15,
                            "quality_range": pq["max_quality"] - pq["min_quality"]},
                ))

        # 3. Token limit adjustments
        for pq in analysis.get("pattern_quality", []):
            if pq["avg_quality"] < 0.4 and pq["avg_pipeline_ms"] < 5000:
                actions.append(ImprovementAction(
                    action_type="tokens_adjust",
                    target=pq["pattern"],
                    description=f"Pattern '{pq['pattern']}' qualite basse mais rapide "
                                f"- augmenter max_tokens pour des reponses plus completes",
                    priority="medium",
                    params={"pattern": pq["pattern"], "suggested_max_tokens": 2048},
                ))

        # 4. Gate tuning based on failure patterns
        for gf in analysis.get("gate_failures", []):
            if gf["count"] > 3:
                if "length" in (gf["failed_gates"] or ""):
                    actions.append(ImprovementAction(
                        action_type="gate_tune",
                        target=gf["pattern"],
                        description=f"Pattern '{gf['pattern']}' echoue souvent sur length gate "
                                    f"({gf['count']}x) - ajuster min_content_length",
                        priority="medium",
                        params={"pattern": gf["pattern"], "gate": "length",
                                "suggestion": "lower_threshold"},
                    ))
                if "latency" in (gf["failed_gates"] or ""):
                    actions.append(ImprovementAction(
                        action_type="gate_tune",
                        target=gf["pattern"],
                        description=f"Pattern '{gf['pattern']}' echoue souvent sur latency gate "
                                    f"({gf['count']}x) - augmenter max_latency_ms ou changer de noeud",
                        priority="high",
                        params={"pattern": gf["pattern"], "gate": "latency",
                                "suggestion": "raise_threshold_or_faster_node"},
                    ))

        # 5. Prompt enhancements for consistently low quality
        for pq in analysis.get("pattern_quality", []):
            if pq["avg_quality"] < 0.25 and pq["dispatches"] > 5:
                actions.append(ImprovementAction(
                    action_type="prompt_enhance",
                    target=pq["pattern"],
                    description=f"Pattern '{pq['pattern']}' qualite tres basse ({pq['avg_quality']:.2f}) "
                                f"- enrichir le system prompt avec des exemples",
                    priority="critical",
                    params={"pattern": pq["pattern"], "avg_quality": pq["avg_quality"]},
                ))

        # 6. Benchmark-driven pattern-node route shifts from agent_dispatch_log
        benchmark_actions = self._analyze_benchmark_data()
        actions.extend(benchmark_actions)

        # 7. Auto-tune quality gate thresholds
        try:
            from src.quality_gate import get_gate
            gate = get_gate()
            tune_results = gate.auto_tune_from_data()
            for pat, changes in tune_results.items():
                if pat != "error" and changes:
                    desc_parts = ", ".join(changes)
                    has_warning = any("WARNING" in c for c in changes)
                    actions.append(ImprovementAction(
                        action_type="gate_tune",
                        target=pat,
                        description=f"Auto-tune gate pour '{pat}': {desc_parts}",
                        priority="high" if has_warning else "medium",
                        params={"pattern": pat, "changes": changes, "auto_tuned": True},
                    ))
        except Exception:
            pass

        # Sort by priority
        prio_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        actions.sort(key=lambda a: prio_order.get(a.priority, 9))

        return actions

    def _analyze_benchmark_data(self) -> list[ImprovementAction]:
        """Analyze agent_dispatch_log for pattern-node performance issues."""
        actions = []
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            # Find pattern-node combos with <50% success and enough samples
            bad_combos = db.execute("""
                SELECT classified_type as pattern, node,
                       COUNT(*) as n,
                       SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
                       AVG(latency_ms) as avg_lat
                FROM agent_dispatch_log
                WHERE id > (SELECT COALESCE(MAX(id),0) - 1000 FROM agent_dispatch_log)
                GROUP BY classified_type, node
                HAVING n >= 5 AND ok * 1.0 / n < 0.5
                ORDER BY ok * 1.0 / n ASC
            """).fetchall()

            # Find best node for each pattern
            best_nodes = db.execute("""
                SELECT classified_type as pattern, node,
                       SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as rate,
                       COUNT(*) as n
                FROM agent_dispatch_log
                WHERE id > (SELECT COALESCE(MAX(id),0) - 1000 FROM agent_dispatch_log)
                GROUP BY classified_type, node
                HAVING n >= 3
                ORDER BY classified_type, rate DESC
            """).fetchall()

            best_map = {}
            for r in best_nodes:
                if r["pattern"] not in best_map:
                    best_map[r["pattern"]] = {"node": r["node"], "rate": r["rate"]}

            db.close()

            for combo in bad_combos:
                pat = combo["pattern"]
                bad_node = combo["node"]
                rate = combo["ok"] / max(1, combo["n"])
                best = best_map.get(pat, {})
                best_node = best.get("node", "M1")
                best_rate = best.get("rate", 0)

                if best_node != bad_node and best_rate > rate + 0.3:
                    actions.append(ImprovementAction(
                        action_type="route_shift",
                        target=pat,
                        description=f"Pattern '{pat}' sur {bad_node}: {rate*100:.0f}% succes "
                                    f"vs {best_node}: {best_rate*100:.0f}% — rediriger",
                        priority="high" if rate < 0.2 else "medium",
                        params={
                            "pattern": pat, "from_node": bad_node,
                            "to_node": best_node, "bad_rate": round(rate, 3),
                            "good_rate": round(best_rate, 3),
                        },
                    ))

        except Exception as e:
            logger.debug(f"Benchmark data analysis: {e}")

        return actions

    def apply_improvements(self, auto: bool = False, max_actions: int = 5) -> list[dict]:
        """Apply suggested improvements (optionally auto-apply safe ones)."""
        actions = self.suggest_improvements()
        results = []

        for action in actions[:max_actions]:
            if auto and action.priority in ("critical", "high"):
                applied = self._apply_action(action)
                action.applied = applied
                action.result = "auto-applied" if applied else "failed"
            else:
                action.result = "suggested (manual review needed)"

            # Log
            self._log_action(action)
            results.append({
                "type": action.action_type,
                "target": action.target,
                "description": action.description,
                "priority": action.priority,
                "applied": action.applied,
                "result": action.result,
            })

        return results

    def _apply_action(self, action: ImprovementAction) -> bool:
        """Actually apply an improvement action."""
        try:
            if action.action_type == "route_shift":
                return self._apply_route_shift(action)
            elif action.action_type == "temp_adjust":
                return self._apply_temp_adjust(action)
            elif action.action_type == "gate_tune":
                return self._apply_gate_tune(action)
            elif action.action_type == "tokens_adjust":
                return self._apply_tokens_adjust(action)
        except Exception as e:
            logger.warning(f"Failed to apply {action.action_type}: {e}")
        return False

    def _apply_route_shift(self, action: ImprovementAction) -> bool:
        """Shift routing away from a problematic node or reroute a pattern."""
        try:
            from_node = action.params.get("from_node", "")
            to_node = action.params.get("to_node", "")
            pattern = action.params.get("pattern", "")

            # Pattern-level route shift: update agent_patterns in DB
            if pattern and to_node:
                db = sqlite3.connect(DB_PATH)
                # Check if pattern exists in agent_patterns
                existing = db.execute(
                    "SELECT model_primary FROM agent_patterns WHERE pattern_type=?",
                    (pattern,)
                ).fetchone()
                if existing:
                    # Map node to model name
                    NODE_TO_MODEL = {
                        "M1": "qwen3-8b",
                        "M2": "deepseek-r1-0528-qwen3-8b",
                        "M3": "deepseek-r1-0528-qwen3-8b",
                        "OL1": "qwen3:1.7b",
                    }
                    model = NODE_TO_MODEL.get(to_node, "qwen3-8b")
                    db.execute(
                        "UPDATE agent_patterns SET model_primary=? WHERE pattern_type=?",
                        (model, pattern)
                    )
                    db.commit()
                    logger.info(f"Route shift: {pattern} → {to_node} ({model})")
                db.close()
                return True

            # Node-level penalization
            if from_node:
                try:
                    from src.adaptive_router import get_router
                    router = get_router()
                    if hasattr(router, "penalize_node"):
                        router.penalize_node(from_node, penalty=0.5)
                        return True
                    if hasattr(router, "open_circuit"):
                        router.open_circuit(from_node, duration=300)
                        return True
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Route shift failed: {e}")
        return False

    def _apply_temp_adjust(self, action: ImprovementAction) -> bool:
        """Adjust temperature for a pattern agent."""
        try:
            from src.pattern_agents import PatternAgentRegistry
            reg = PatternAgentRegistry()
            pattern = action.params.get("pattern", "")
            new_temp = action.params.get("suggested_temp", 0.2)
            agent = reg.agents.get(pattern)
            if agent:
                agent.temperature = new_temp
                return True
        except Exception:
            pass
        return False

    def _apply_tokens_adjust(self, action: ImprovementAction) -> bool:
        """Adjust max_tokens for a pattern agent."""
        try:
            from src.pattern_agents import PatternAgentRegistry
            reg = PatternAgentRegistry()
            pattern = action.params.get("pattern", "")
            new_tokens = action.params.get("suggested_max_tokens", 2048)
            agent = reg.agents.get(pattern)
            if agent:
                agent.max_tokens = new_tokens
                return True
        except Exception:
            pass
        return False

    def _apply_gate_tune(self, action: ImprovementAction) -> bool:
        """Adjust quality gate thresholds for a pattern."""
        try:
            from src.quality_gate import get_gate
            gate = get_gate()
            pattern = action.params.get("pattern", "")
            gate_name = action.params.get("gate", "")

            if gate_name == "length" and action.params.get("suggestion") == "lower_threshold":
                current = gate.config.min_content_length.get(pattern, 20)
                gate.config.min_content_length[pattern] = max(5, current // 2)
                return True
            elif gate_name == "latency" and "raise_threshold" in (action.params.get("suggestion") or ""):
                current = gate.config.max_latency_ms.get(pattern, 30000)
                gate.config.max_latency_ms[pattern] = int(current * 1.5)
                return True
        except Exception:
            pass
        return False

    def _log_action(self, action: ImprovementAction):
        try:
            import json
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                INSERT INTO self_improvement_log
                (action_type, target, description, priority, params, applied, result)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                action.action_type, action.target, action.description,
                action.priority, json.dumps(action.params),
                int(action.applied), action.result,
            ))
            db.commit()
            db.close()
        except Exception:
            pass

    def get_history(self, limit: int = 50) -> list[dict]:
        """Get improvement history."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT * FROM self_improvement_log ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            db.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_stats(self) -> dict:
        """Get self-improvement statistics."""
        try:
            db = sqlite3.connect(DB_PATH)
            total = db.execute("SELECT COUNT(*) FROM self_improvement_log").fetchone()[0]
            applied = db.execute("SELECT COUNT(*) FROM self_improvement_log WHERE applied").fetchone()[0]
            by_type = db.execute("""
                SELECT action_type, COUNT(*) as n, SUM(applied) as applied
                FROM self_improvement_log GROUP BY action_type
            """).fetchall()
            db.close()
            return {
                "total_suggestions": total,
                "total_applied": applied,
                "apply_rate": round(applied / max(1, total), 3),
                "by_type": [
                    {"type": r[0], "count": r[1], "applied": r[2]}
                    for r in by_type
                ],
            }
        except Exception:
            return {"total_suggestions": 0, "total_applied": 0}


# Singleton
_improver: Optional[SelfImprover] = None

def get_improver() -> SelfImprover:
    global _improver
    if _improver is None:
        _improver = SelfImprover()
    return _improver
