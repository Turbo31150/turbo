"""JARVIS Cowork Proactive Engine — Need-driven script execution.

Analyzes system state (quality gate failures, node health, dispatch trends) and
automatically selects and runs the most relevant cowork scripts to fix issues.

Features:
  - Need detection from quality gate + dispatch data
  - Script selection matching needs to cowork categories
  - Proactive execution with priority queue
  - Anticipation engine (predict what scripts will be needed)
  - Multi-test validation after execution

Usage:
    from src.cowork_proactive import CoworkProactive, get_proactive
    pro = get_proactive()
    needs = pro.detect_needs()
    plan = pro.plan_execution(needs)
    results = pro.execute_plan(plan)
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


__all__ = [
    "CoworkProactive",
    "ExecutionPlan",
    "SystemNeed",
    "get_proactive",
]

logger = logging.getLogger("jarvis.cowork_proactive")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")


@dataclass
class SystemNeed:
    """A detected system need that cowork scripts can address."""
    category: str          # monitoring, optimization, security, trading, etc.
    urgency: str           # critical, high, medium, low
    description: str
    source: str            # quality_gate, dispatch, health, self_improvement
    suggested_scripts: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """A plan to execute cowork scripts addressing detected needs."""
    needs: list[SystemNeed]
    scripts_to_run: list[dict]
    estimated_duration_s: float
    created_at: float = 0


class CoworkProactive:
    """Proactively orchestrates cowork script execution based on system needs."""

    NEED_SCRIPT_MAP = {
        "monitoring": ["monitor", "health", "check", "status", "diagnostic"],
        "optimization": ["optimize", "improve", "tune", "performance", "cache"],
        "security": ["security", "audit", "scan", "firewall", "backup"],
        "trading": ["trading", "signal", "portfolio", "risk", "market"],
        "system": ["system", "service", "process", "disk", "network"],
        "intelligence": ["intelligence", "cluster", "node", "gpu", "vram"],
        "automation": ["automation", "scheduler", "cron", "pipeline", "workflow"],
        "data": ["data", "backup", "sync", "clean", "migrate"],
        "voice": ["voice", "tts", "stt", "audio", "whisper"],
        "web": ["browser", "scrape", "fetch", "api", "web"],
    }

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                CREATE TABLE IF NOT EXISTS cowork_proactive_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    need_category TEXT, urgency TEXT, scripts_run TEXT,
                    scripts_ok INTEGER, scripts_total INTEGER,
                    total_duration_ms REAL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.commit()
            db.close()
        except Exception:
            pass

    def detect_needs(self) -> list[SystemNeed]:
        """Analyze system state and detect what needs attention."""
        needs = []
        needs.extend(self._needs_from_quality_gate())
        needs.extend(self._needs_from_health())
        needs.extend(self._needs_from_dispatch())
        needs.extend(self._needs_from_self_improvement())
        needs.extend(self._needs_from_benchmark_trend())
        needs.extend(self._needs_from_timeout_patterns())

        urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        needs.sort(key=lambda n: urgency_order.get(n.urgency, 9))
        return needs

    def _needs_from_quality_gate(self) -> list[SystemNeed]:
        needs = []
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            failures = db.execute("""
                SELECT pattern, failed_gates, COUNT(*) as n
                FROM quality_gate_log WHERE NOT passed
                AND id > (SELECT COALESCE(MAX(id), 0) - 100 FROM quality_gate_log)
                GROUP BY pattern, failed_gates HAVING n >= 3
                ORDER BY n DESC LIMIT 10
            """).fetchall()
            db.close()

            for f in failures:
                urgency = "high" if f["n"] > 5 else "medium"
                gates = f["failed_gates"] or ""
                if "latency" in gates:
                    needs.append(SystemNeed(
                        category="optimization", urgency=urgency,
                        description=f"Pattern '{f['pattern']}' latency gate failure ({f['n']}x)",
                        source="quality_gate",
                        data={"pattern": f["pattern"], "gate": "latency", "count": f["n"]},
                    ))
                elif "length" in gates or "structure" in gates:
                    needs.append(SystemNeed(
                        category="intelligence", urgency="medium",
                        description=f"Pattern '{f['pattern']}' output quality issues",
                        source="quality_gate",
                        data={"pattern": f["pattern"], "gate": gates, "count": f["n"]},
                    ))
        except Exception:
            pass
        return needs

    def _needs_from_health(self) -> list[SystemNeed]:
        needs = []
        try:
            from src.adaptive_router import get_router
            router = get_router()
            status = router.get_status()
            for node_name, info in status.get("nodes", {}).items():
                cb = info.get("circuit_breaker", "closed")
                if cb == "open":
                    needs.append(SystemNeed(
                        category="system", urgency="critical",
                        description=f"Node {node_name} circuit breaker OPEN",
                        source="health", data={"node": node_name},
                    ))
        except Exception:
            pass
        return needs

    def _needs_from_dispatch(self) -> list[SystemNeed]:
        needs = []
        try:
            db = sqlite3.connect(DB_PATH)
            total = db.execute("SELECT COUNT(*) FROM dispatch_pipeline_log").fetchone()[0]
            ok = db.execute("SELECT COUNT(*) FROM dispatch_pipeline_log WHERE success").fetchone()[0]
            rate = ok / max(1, total)
            if rate < 0.7 and total > 10:
                needs.append(SystemNeed(
                    category="intelligence", urgency="critical",
                    description=f"Low dispatch success rate: {rate:.0%}",
                    source="dispatch", data={"success_rate": rate, "total": total},
                ))
            fb = db.execute("SELECT COUNT(*) FROM dispatch_pipeline_log WHERE fallback_used").fetchone()[0]
            fb_rate = fb / max(1, total)
            if fb_rate > 0.3 and total > 10:
                needs.append(SystemNeed(
                    category="optimization", urgency="high",
                    description=f"High fallback rate: {fb_rate:.0%}",
                    source="dispatch", data={"fallback_rate": fb_rate},
                ))
            db.close()
        except Exception:
            pass
        return needs

    def _needs_from_self_improvement(self) -> list[SystemNeed]:
        needs = []
        try:
            from src.self_improvement import get_improver
            actions = get_improver().suggest_improvements()
            for action in actions[:5]:
                if action.priority in ("critical", "high"):
                    needs.append(SystemNeed(
                        category="optimization", urgency=action.priority,
                        description=action.description, source="self_improvement",
                        data=action.params,
                    ))
        except Exception:
            pass
        return needs

    def _needs_from_benchmark_trend(self) -> list[SystemNeed]:
        """Detect declining benchmark performance trends."""
        needs = []
        try:
            db = sqlite3.connect(DB_PATH)
            rows = db.execute("""
                SELECT rate, timestamp FROM benchmark_quick
                ORDER BY id DESC LIMIT 5
            """).fetchall()
            db.close()
            if len(rows) >= 2:
                latest = rows[0][0]
                prev_avg = sum(r[0] for r in rows[1:]) / len(rows[1:])
                if latest < prev_avg - 0.1:
                    needs.append(SystemNeed(
                        category="intelligence", urgency="high",
                        description=f"Benchmark regression: {latest*100:.0f}% vs avg {prev_avg*100:.0f}%",
                        source="benchmark",
                        data={"current": latest, "previous_avg": prev_avg},
                    ))
                if latest < 0.6:
                    needs.append(SystemNeed(
                        category="optimization", urgency="critical",
                        description=f"Benchmark below 60%: {latest*100:.0f}% — needs immediate attention",
                        source="benchmark",
                        data={"rate": latest},
                    ))
        except Exception:
            pass
        return needs

    def _needs_from_timeout_patterns(self) -> list[SystemNeed]:
        """Detect nodes/patterns with high timeout or context overflow rates."""
        needs = []
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            # Find node+pattern combos with >30% failure in last 100 dispatches
            rows = db.execute("""
                SELECT node, classified_type as pattern,
                       COUNT(*) as n,
                       SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fails,
                       AVG(CASE WHEN success=0 THEN latency_ms END) as avg_fail_lat
                FROM agent_dispatch_log
                WHERE id > (SELECT COALESCE(MAX(id),0) - 100 FROM agent_dispatch_log)
                GROUP BY node, classified_type
                HAVING n >= 3 AND fails > 0
                ORDER BY fails * 1.0 / n DESC
            """).fetchall()
            db.close()

            for r in rows:
                fail_rate = r["fails"] / max(1, r["n"])
                avg_lat = r["avg_fail_lat"] or 0
                if fail_rate > 0.3:
                    # High failure: likely timeout or context issue
                    urgency = "critical" if fail_rate > 0.5 else "high"
                    cause = "timeout" if avg_lat > 50000 else "context/quality"
                    needs.append(SystemNeed(
                        category="optimization", urgency=urgency,
                        description=f"{r['node']}/{r['pattern']} {cause} failures: {fail_rate:.0%} ({r['fails']}/{r['n']})",
                        source="timeout_pattern",
                        suggested_scripts=["resilient_dispatcher", "adaptive_timeout_manager"],
                        data={"node": r["node"], "pattern": r["pattern"],
                              "fail_rate": fail_rate, "avg_fail_latency": avg_lat},
                    ))
        except Exception:
            pass
        return needs

    def plan_execution(self, needs: list[SystemNeed]) -> ExecutionPlan:
        """Create an execution plan from detected needs."""
        scripts_to_run = []
        try:
            from src.cowork_bridge import get_bridge
            bridge = get_bridge()
        except Exception:
            return ExecutionPlan(needs=needs, scripts_to_run=[], estimated_duration_s=0)

        seen = set()
        for need in needs:
            terms = self.NEED_SCRIPT_MAP.get(need.category, [need.category])
            for term in terms:
                results = bridge.search(term, limit=3)
                for r in results:
                    if r["name"] not in seen and r.get("has_once", False):
                        seen.add(r["name"])
                        scripts_to_run.append({
                            "name": r["name"], "args": ["--once"],
                            "timeout": 30, "need": need.category,
                            "urgency": need.urgency, "score": r.get("score", 0),
                        })

        urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        scripts_to_run.sort(key=lambda s: (urgency_order.get(s["urgency"], 9), -s["score"]))
        scripts_to_run = scripts_to_run[:10]

        return ExecutionPlan(
            needs=needs, scripts_to_run=scripts_to_run,
            estimated_duration_s=len(scripts_to_run) * 15, created_at=time.time(),
        )

    def execute_plan(self, plan: ExecutionPlan, dry_run: bool = False) -> dict:
        """Execute planned cowork scripts."""
        if dry_run:
            return {
                "dry_run": True, "needs": len(plan.needs),
                "scripts_planned": len(plan.scripts_to_run),
                "scripts": [s["name"] for s in plan.scripts_to_run],
            }

        try:
            from src.cowork_bridge import get_bridge
            bridge = get_bridge()
        except Exception as e:
            return {"error": str(e)}

        results = []
        t0 = time.time()
        for s in plan.scripts_to_run:
            r = bridge.execute(s["name"], args=s["args"], timeout_s=s["timeout"])
            results.append({
                "script": r.script, "success": r.success,
                "duration_ms": r.duration_ms, "need": s["need"],
                "output_preview": (r.stdout[:150] if r.stdout else ""),
            })

        total_ms = (time.time() - t0) * 1000
        ok = sum(1 for r in results if r["success"])
        self._log(plan, ok, len(results), total_ms)
        self._emit(plan, ok, len(results), total_ms)

        return {
            "needs_detected": len(plan.needs), "scripts_executed": len(results),
            "scripts_ok": ok, "total_duration_ms": round(total_ms, 1),
            "success_rate": round(ok / max(1, len(results)), 3), "results": results,
        }

    def anticipate(self) -> dict:
        """Predict future needs from trend analysis."""
        predictions = []
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            declining = db.execute("""
                SELECT pattern,
                    AVG(CASE WHEN id > (SELECT MAX(id) - 50 FROM dispatch_pipeline_log) THEN quality END) as rq,
                    AVG(CASE WHEN id <= (SELECT MAX(id) - 50 FROM dispatch_pipeline_log)
                             AND id > (SELECT MAX(id) - 100 FROM dispatch_pipeline_log) THEN quality END) as oq
                FROM dispatch_pipeline_log
                GROUP BY pattern HAVING rq IS NOT NULL AND oq IS NOT NULL AND rq < oq * 0.8
            """).fetchall()

            for d in declining:
                predictions.append({
                    "type": "quality_decline", "pattern": d["pattern"],
                    "recent_q": round(d["rq"] or 0, 3), "previous_q": round(d["oq"] or 0, 3),
                    "recommendation": f"Pattern '{d['pattern']}' quality declining",
                })

            # Predict timeout risks from latency trends
            latency_trends = db.execute("""
                SELECT node, classified_type as pattern,
                    AVG(CASE WHEN id > (SELECT MAX(id) - 25 FROM agent_dispatch_log) THEN latency_ms END) as recent_lat,
                    AVG(CASE WHEN id <= (SELECT MAX(id) - 25 FROM agent_dispatch_log)
                             AND id > (SELECT MAX(id) - 75 FROM agent_dispatch_log) THEN latency_ms END) as prev_lat
                FROM agent_dispatch_log WHERE success=1
                GROUP BY node, classified_type
                HAVING recent_lat IS NOT NULL AND prev_lat IS NOT NULL AND recent_lat > prev_lat * 1.5
            """).fetchall()
            for t in latency_trends:
                predictions.append({
                    "type": "latency_increase", "node": t["node"], "pattern": t["pattern"],
                    "recent_lat_ms": round(t["recent_lat"] or 0), "prev_lat_ms": round(t["prev_lat"] or 0),
                    "recommendation": f"{t['node']}/{t['pattern']} latency +{((t['recent_lat'] or 0)/(t['prev_lat'] or 1)-1)*100:.0f}% — timeout risk",
                })

            db.close()
        except Exception:
            pass

        return {"predictions": predictions, "count": len(predictions)}

    def run_proactive(self, max_scripts: int = 5, dry_run: bool = False) -> dict:
        """Full cycle: detect -> plan -> execute -> anticipate."""
        needs = self.detect_needs()
        plan = self.plan_execution(needs)
        plan.scripts_to_run = plan.scripts_to_run[:max_scripts]
        result = self.execute_plan(plan, dry_run=dry_run)
        result["anticipation"] = self.anticipate()
        return result

    def _log(self, plan, ok, total, duration_ms):
        try:
            import json
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                INSERT INTO cowork_proactive_log
                (need_category, urgency, scripts_run, scripts_ok, scripts_total, total_duration_ms)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                ",".join(set(n.category for n in plan.needs)),
                ",".join(set(n.urgency for n in plan.needs)),
                json.dumps([s["name"] for s in plan.scripts_to_run]),
                ok, total, duration_ms,
            ))
            db.commit()
            db.close()
        except Exception:
            pass

    def _emit(self, plan, ok, total, duration_ms):
        try:
            from src.event_stream import get_stream
            get_stream().emit("pipeline", {
                "type": "cowork_proactive", "needs": len(plan.needs),
                "scripts_ok": ok, "scripts_total": total,
                "duration_ms": round(duration_ms, 1),
            }, source="cowork_proactive")
        except Exception:
            pass

    def get_stats(self) -> dict:
        try:
            db = sqlite3.connect(DB_PATH)
            total = db.execute("SELECT COUNT(*) FROM cowork_proactive_log").fetchone()[0]
            avg = db.execute("SELECT AVG(CAST(scripts_ok AS REAL)/MAX(1,scripts_total)) FROM cowork_proactive_log").fetchone()[0]
            db.close()
            return {"total_orchestrations": total, "avg_success_rate": round(avg or 0, 3)}
        except Exception:
            return {"total_orchestrations": 0}


_proactive: Optional[CoworkProactive] = None

def get_proactive() -> CoworkProactive:
    global _proactive
    if _proactive is None:
        _proactive = CoworkProactive()
    return _proactive
