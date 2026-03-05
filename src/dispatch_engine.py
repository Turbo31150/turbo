"""JARVIS Dispatch Engine — Unified dispatch pipeline.

Ties together all subsystems into one coherent dispatch flow:
  1. Health check (guardian) — skip degraded nodes
  2. Route selection (adaptive_router) — pick best node
  3. Episodic recall (memory) — enrich prompt with past context
  4. Actual dispatch (pattern_agents) — call the LLM
  5. Quality gate evaluation (6 gates: length, structure, relevance, confidence, latency, hallucination)
  6. Feedback recording
  7. Episodic storage — store this dispatch for future recall
  8. Event stream emission — real-time SSE events

Usage:
    from src.dispatch_engine import DispatchEngine, get_engine
    engine = get_engine()
    result = await engine.dispatch("code", "Ecris un parser JSON en Python")
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("jarvis.dispatch_engine")

DB_PATH = "F:/BUREAU/turbo/etoile.db"


@dataclass
class DispatchResult:
    """Full dispatch result with metadata."""
    pattern: str
    node: str
    strategy: str
    content: str
    quality: float
    latency_ms: float
    success: bool
    enriched: bool = False       # True if episodic memory was used
    health_bypassed: list = field(default_factory=list)  # Nodes skipped due to health
    fallback_used: bool = False  # True if original node was replaced
    feedback_recorded: bool = False
    episode_stored: bool = False
    pipeline_ms: float = 0       # Total pipeline time (including overhead)
    prompt_tokens_est: int = 0   # Estimated prompt tokens
    error: str = ""
    # Quality gate details
    gate_passed: bool = True
    gate_score: float = 0.0
    gate_failed: list = field(default_factory=list)
    gate_suggestions: list = field(default_factory=list)
    event_emitted: bool = False
    prompt_optimized: bool = False


@dataclass
class PipelineConfig:
    """Configuration for the dispatch pipeline."""
    enable_health_check: bool = True
    enable_memory_enrichment: bool = True
    enable_prompt_optimization: bool = True
    enable_feedback: bool = True
    enable_episodic_store: bool = True
    max_retries: int = 1
    timeout_s: float = 60.0
    quality_threshold: float = 0.3  # Retry if below
    auto_fallback: bool = True


class DispatchEngine:
    """Unified dispatch pipeline — the brain of JARVIS agent system."""

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self._stats = {
            "total_dispatches": 0,
            "successful": 0,
            "failed": 0,
            "retries": 0,
            "fallbacks": 0,
            "avg_pipeline_ms": 0,
            "avg_quality": 0,
        }
        self._ensure_table()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                CREATE TABLE IF NOT EXISTS dispatch_pipeline_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT, node TEXT, strategy TEXT,
                    quality REAL, latency_ms REAL, pipeline_ms REAL,
                    success INTEGER, enriched INTEGER, fallback_used INTEGER,
                    health_bypassed TEXT, error TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_dpl_pattern ON dispatch_pipeline_log(pattern)")
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to create dispatch_pipeline_log: {e}")

    async def dispatch(self, pattern: str, prompt: str,
                       node_override: Optional[str] = None,
                       strategy_override: Optional[str] = None) -> DispatchResult:
        """Full pipeline dispatch."""
        t0 = time.time()
        result = DispatchResult(
            pattern=pattern, node="", strategy="single",
            content="", quality=0, latency_ms=0, success=False,
        )

        try:
            # Step 1: Health check — find available nodes
            bypassed = []
            if self.config.enable_health_check:
                bypassed = await self._check_health()
                result.health_bypassed = bypassed

            # Step 2: Route selection
            node = node_override
            strategy = strategy_override or "single"
            if not node:
                node, strategy = await self._pick_route(pattern, prompt, bypassed)
            result.node = node
            result.strategy = strategy

            # Step 3: Episodic memory enrichment
            enriched_prompt = prompt
            if self.config.enable_memory_enrichment:
                enriched_prompt, was_enriched = await self._enrich_with_memory(pattern, prompt)
                result.enriched = was_enriched

            # Step 3b: Prompt optimization
            if self.config.enable_prompt_optimization:
                enriched_prompt, was_optimized = self._optimize_prompt(pattern, enriched_prompt)
                result.prompt_optimized = was_optimized

            # Step 4: Dispatch
            content, latency_ms, success = await self._do_dispatch(
                pattern, enriched_prompt, node, strategy
            )
            result.content = content
            result.latency_ms = latency_ms
            result.success = success

            # Step 4b: Retry/fallback on failure
            if not success and self.config.auto_fallback and self.config.max_retries > 0:
                fallback_node = await self._pick_fallback(pattern, node, bypassed)
                if fallback_node and fallback_node != node:
                    self._stats["retries"] += 1
                    self._stats["fallbacks"] += 1
                    content, latency_ms, success = await self._do_dispatch(
                        pattern, enriched_prompt, fallback_node, "single"
                    )
                    result.content = content
                    result.latency_ms = latency_ms
                    result.success = success
                    result.node = fallback_node
                    result.fallback_used = True

            # Step 5: Quality Gate evaluation (6 gates)
            gate_result = self._evaluate_quality_gate(
                pattern, prompt, content, latency_ms, result.node
            )
            result.quality = gate_result.get("overall_score", 0.0)
            result.gate_passed = gate_result.get("passed", True)
            result.gate_score = gate_result.get("overall_score", 0.0)
            result.gate_failed = gate_result.get("failed_gates", [])
            result.gate_suggestions = gate_result.get("suggestions", [])

            # Step 5b: Quality-based retry (if gate failed + retry recommended)
            if (not result.gate_passed
                    and gate_result.get("retry_recommended", False)
                    and result.success and self.config.max_retries > 0
                    and not result.fallback_used):
                # Use suggested node from gate, or pick fallback
                better_node = gate_result.get("suggested_node") or await self._pick_fallback(
                    pattern, node, bypassed + [node]
                )
                if better_node and better_node != node:
                    self._stats["retries"] += 1
                    content2, lat2, ok2 = await self._do_dispatch(
                        pattern, enriched_prompt, better_node, "single"
                    )
                    gate2 = self._evaluate_quality_gate(
                        pattern, prompt, content2, lat2, better_node
                    )
                    if gate2.get("overall_score", 0) > result.quality:
                        result.content = content2
                        result.latency_ms = lat2
                        result.success = ok2
                        result.quality = gate2["overall_score"]
                        result.gate_passed = gate2["passed"]
                        result.gate_score = gate2["overall_score"]
                        result.gate_failed = gate2.get("failed_gates", [])
                        result.gate_suggestions = gate2.get("suggestions", [])
                        result.node = better_node
                        result.fallback_used = True

            # Step 6: Feedback recording
            if self.config.enable_feedback:
                result.feedback_recorded = await self._record_feedback(result, prompt)

            # Step 7: Episodic storage
            if self.config.enable_episodic_store and result.success:
                result.episode_stored = await self._store_episode(result, prompt)

        except Exception as e:
            result.error = str(e)
            logger.error(f"Dispatch pipeline error: {e}")

        result.pipeline_ms = (time.time() - t0) * 1000
        result.prompt_tokens_est = len(prompt.split()) * 2  # rough estimate

        # Update stats
        self._stats["total_dispatches"] += 1
        if result.success:
            self._stats["successful"] += 1
        else:
            self._stats["failed"] += 1
        n = self._stats["total_dispatches"]
        self._stats["avg_pipeline_ms"] = (
            self._stats["avg_pipeline_ms"] * (n - 1) + result.pipeline_ms
        ) / n
        self._stats["avg_quality"] = (
            self._stats["avg_quality"] * (n - 1) + result.quality
        ) / n

        # Persist
        self._log_pipeline(result)

        # Step 8: Event stream emission
        result.event_emitted = self._emit_event(result, prompt)

        return result

    async def _check_health(self) -> list[str]:
        """Return list of unhealthy nodes to bypass."""
        try:
            from src.adaptive_router import get_router
            router = get_router()
            status = router.get_status()
            bypassed = []
            for node_name, info in status.get("nodes", {}).items():
                cb = info.get("circuit_breaker", "closed")
                if cb == "open":
                    bypassed.append(node_name)
            return bypassed
        except Exception:
            return []

    # Blacklisted pattern-node combos (from benchmark data: 0% success rate)
    ROUTE_BLACKLIST = {
        ("reasoning", "M3"), ("math", "M3"),         # M3 always times out
        ("architecture", "M3"), ("security", "M3"),   # M3 too slow for complex
        ("analysis", "M3"), ("data", "M3"),
        ("code", "M3"),                               # M3 not suited for code gen
    }

    # Preferred nodes per pattern (from benchmark-v2: race strategy for weak patterns)
    ROUTE_PREFERENCE = {
        "reasoning": ["M1", "gpt-oss", "M2", "OL1"],
        "math": ["M1", "M2", "gpt-oss"],
        "architecture": ["M1", "gpt-oss", "devstral", "OL1"],
        "security": ["M1", "gpt-oss", "devstral", "OL1"],
        "analysis": ["M1", "gpt-oss", "devstral", "OL1"],
        "data": ["M1", "gpt-oss", "devstral", "OL1"],
        "code": ["M1", "gpt-oss", "devstral", "OL1"],
        "trading": ["M1", "gpt-oss", "OL1"],
        "classifier": ["M1", "OL1"],
        "simple": ["OL1", "M1"],
        "creative": ["M1", "OL1", "M2"],
        "system": ["M1", "OL1"],
        "web": ["OL1", "M1", "minimax"],
        "devops": ["OL1", "M1"],
    }

    async def _pick_route(self, pattern: str, prompt: str,
                          exclude: list[str]) -> tuple[str, str]:
        """Pick best node and strategy. Uses benchmark-driven preferences."""
        # Apply blacklist to exclude list
        blacklisted = [n for p, n in self.ROUTE_BLACKLIST if p == pattern]
        all_exclude = list(set(exclude + blacklisted))

        # Try benchmark-preferred nodes first
        preferred = self.ROUTE_PREFERENCE.get(pattern, [])
        for node in preferred:
            if node not in all_exclude:
                return node, "single"

        try:
            from src.adaptive_router import get_router
            router = get_router()
            node = router.pick_node(pattern, exclude_nodes=all_exclude)
            if node:
                return node, "single"
        except Exception:
            pass

        # Fallback: use pattern_agents registry
        try:
            from src.pattern_agents import PatternAgentRegistry
            reg = PatternAgentRegistry()
            agent = reg.agents.get(pattern)
            if agent:
                for n in [agent.primary_node] + list(agent.fallback_chain):
                    if n not in all_exclude:
                        return n, agent.strategy
        except Exception:
            pass

        return "M1", "single"

    async def _pick_fallback(self, pattern: str, current: str,
                             exclude: list[str]) -> Optional[str]:
        """Pick a fallback node different from current."""
        try:
            from src.adaptive_router import get_router
            router = get_router()
            node = router.pick_node(pattern, exclude_nodes=exclude + [current])
            return node
        except Exception:
            pass

        # Manual fallback chain (M3 last — consistently worst in benchmarks)
        chain = ["M1", "OL1", "M1B", "M2", "gpt-oss", "devstral", "M3"]
        # Also apply pattern blacklist
        blacklisted = [n for p, n in self.ROUTE_BLACKLIST if p == pattern]
        for n in chain:
            if n != current and n not in exclude and n not in blacklisted:
                return n
        return None

    async def _enrich_with_memory(self, pattern: str, prompt: str) -> tuple[str, bool]:
        """Enrich prompt with episodic memory context."""
        try:
            from src.agent_episodic_memory import get_episodic_memory
            mem = get_episodic_memory()
            episodes = mem.recall(pattern, limit=3)
            if episodes:
                context_lines = []
                for ep in episodes[:2]:
                    if ep.get("content"):
                        snippet = ep["content"][:200]
                        context_lines.append(f"[Previous {pattern}]: {snippet}")
                if context_lines:
                    context = "\n".join(context_lines)
                    enriched = f"Context from previous interactions:\n{context}\n\n{prompt}"
                    return enriched, True
        except Exception:
            pass
        return prompt, False

    def _optimize_prompt(self, pattern: str, prompt: str) -> tuple[str, bool]:
        """Optimize prompt using pattern-specific system prompts and learned insights."""
        try:
            from src.agent_prompt_optimizer import get_optimizer
            opt = get_optimizer()
            result = opt.optimize(pattern, prompt)
            optimized = result.get("user_prompt", prompt)
            if optimized != prompt:
                return optimized, True
        except Exception:
            pass
        return prompt, False

    async def _do_dispatch(self, pattern: str, prompt: str,
                           node: str, strategy: str) -> tuple[str, float, bool]:
        """Actually dispatch to a node. Searches hardcoded + dynamic agents."""
        try:
            from src.pattern_agents import PatternAgentRegistry, NODES

            reg = PatternAgentRegistry()
            agent = reg.agents.get(pattern)

            # If not in hardcoded, check dynamic agents
            if not agent:
                try:
                    from src.dynamic_agents import get_spawner
                    spawner = get_spawner()
                    dyn = spawner.agents.get(pattern)
                    if dyn:
                        agent = dyn.to_pattern_agent()
                    else:
                        # Fallback to loading all dynamic agents
                        if not spawner._loaded:
                            spawner.load_all()
                        dyn = spawner.agents.get(pattern)
                        if dyn:
                            agent = dyn.to_pattern_agent()
                except Exception:
                    pass

            # Final fallback: use simple agent
            if not agent:
                agent = reg.agents.get("simple")

            client = await reg._get_client()

            t0 = time.time()
            result = await agent._call_node(client, node, prompt)
            latency = (time.time() - t0) * 1000

            if result:
                content = result.content if hasattr(result, 'content') else str(result)
                success = result.ok if hasattr(result, 'ok') else bool(content)
                return content, latency, success
        except Exception as e:
            logger.warning(f"Dispatch to {node} failed: {e}")
        return "", 0, False

    def _evaluate_quality_gate(self, pattern: str, prompt: str, content: str,
                               latency_ms: float, node: str) -> dict:
        """Evaluate output through the full quality gate system."""
        try:
            from src.quality_gate import get_gate
            gate = get_gate()
            verdict = gate.evaluate(pattern, prompt, content, latency_ms, node)
            return {
                "passed": verdict.passed,
                "overall_score": verdict.overall_score,
                "gates": verdict.gates,
                "failed_gates": verdict.failed_gates,
                "suggestions": verdict.suggestions,
                "retry_recommended": verdict.retry_recommended,
                "suggested_node": verdict.suggested_node,
            }
        except Exception as e:
            logger.warning(f"Quality gate failed, using fallback scoring: {e}")
            # Fallback: simple heuristic if quality_gate module unavailable
            if not content:
                return {"passed": False, "overall_score": 0.0, "failed_gates": ["empty"],
                        "suggestions": [], "retry_recommended": True, "suggested_node": ""}
            score = min(1.0, 0.3 + (0.2 if len(content) > 50 else 0) +
                        (0.2 if latency_ms < 5000 else 0) + (0.2 if len(content) > 200 else 0))
            return {"passed": score >= 0.4, "overall_score": score, "failed_gates": [],
                    "suggestions": [], "retry_recommended": False, "suggested_node": ""}

    def _emit_event(self, result: DispatchResult, prompt: str) -> bool:
        """Emit dispatch event to the event stream for real-time SSE consumers."""
        try:
            from src.event_stream import get_stream
            stream = get_stream()

            # Emit dispatch event
            stream.emit_dispatch(
                pattern=result.pattern,
                node=result.node,
                quality=result.quality,
                latency_ms=result.latency_ms,
                success=result.success,
                strategy=result.strategy,
                pipeline_ms=result.pipeline_ms,
                enriched=result.enriched,
                fallback_used=result.fallback_used,
                gate_passed=result.gate_passed,
                gate_failed=result.gate_failed,
            )

            # Emit pipeline event with more detail
            stream.emit("pipeline", {
                "pattern": result.pattern,
                "node": result.node,
                "quality": result.quality,
                "gate_passed": result.gate_passed,
                "latency_ms": result.latency_ms,
                "pipeline_ms": result.pipeline_ms,
                "enriched": result.enriched,
                "fallback_used": result.fallback_used,
                "prompt_preview": prompt[:80],
                "content_preview": result.content[:120] if result.content else "",
            }, source="dispatch_engine")

            # Emit alert if quality gate failed
            if not result.gate_passed and result.gate_failed:
                stream.emit_alert(
                    level="warning",
                    message=f"Quality gate failed for {result.pattern}@{result.node}: {', '.join(result.gate_failed)}",
                    pattern=result.pattern,
                    node=result.node,
                )

            return True
        except Exception as e:
            logger.debug(f"Event emission failed: {e}")
            return False

    async def _record_feedback(self, result: DispatchResult, prompt: str) -> bool:
        """Record feedback from this dispatch."""
        try:
            from src.agent_feedback_loop import get_feedback
            fb = get_feedback()
            fb.record_feedback(
                pattern=result.pattern,
                node=result.node,
                strategy=result.strategy,
                quality=result.quality,
                latency_ms=result.latency_ms,
                success=result.success,
                prompt_preview=prompt[:100],
            )
            return True
        except Exception:
            return False

    async def _store_episode(self, result: DispatchResult, prompt: str) -> bool:
        """Store dispatch as episodic memory."""
        try:
            from src.agent_episodic_memory import get_episodic_memory
            mem = get_episodic_memory()
            mem.store_episode(
                pattern=result.pattern,
                prompt=prompt[:200],
                content=result.content[:500],
                node=result.node,
                quality=result.quality,
            )
            return True
        except Exception:
            return False

    def _log_pipeline(self, result: DispatchResult):
        """Persist pipeline log."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                INSERT INTO dispatch_pipeline_log
                (pattern, node, strategy, quality, latency_ms, pipeline_ms,
                 success, enriched, fallback_used, health_bypassed, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.pattern, result.node, result.strategy,
                result.quality, result.latency_ms, result.pipeline_ms,
                int(result.success), int(result.enriched),
                int(result.fallback_used),
                ",".join(result.health_bypassed),
                result.error,
            ))
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to log pipeline: {e}")

    def get_stats(self) -> dict:
        """Return pipeline stats."""
        return {
            **self._stats,
            "config": {
                "health_check": self.config.enable_health_check,
                "memory_enrichment": self.config.enable_memory_enrichment,
                "prompt_optimization": self.config.enable_prompt_optimization,
                "feedback": self.config.enable_feedback,
                "episodic_store": self.config.enable_episodic_store,
                "max_retries": self.config.max_retries,
                "timeout_s": self.config.timeout_s,
                "quality_threshold": self.config.quality_threshold,
            },
        }

    def get_pipeline_report(self) -> dict:
        """Detailed pipeline report from DB."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            total = db.execute("SELECT COUNT(*) FROM dispatch_pipeline_log").fetchone()[0]
            by_pattern = db.execute("""
                SELECT pattern, COUNT(*) as n,
                       AVG(quality) as avg_q, AVG(latency_ms) as avg_lat,
                       AVG(pipeline_ms) as avg_pipe,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) as ok,
                       SUM(CASE WHEN fallback_used THEN 1 ELSE 0 END) as fb,
                       SUM(CASE WHEN enriched THEN 1 ELSE 0 END) as enriched
                FROM dispatch_pipeline_log
                GROUP BY pattern ORDER BY n DESC
            """).fetchall()

            by_node = db.execute("""
                SELECT node, COUNT(*) as n,
                       AVG(quality) as avg_q, AVG(latency_ms) as avg_lat,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) as ok
                FROM dispatch_pipeline_log
                GROUP BY node ORDER BY n DESC
            """).fetchall()

            recent_errors = db.execute("""
                SELECT pattern, node, error, timestamp
                FROM dispatch_pipeline_log
                WHERE success = 0 AND error != ''
                ORDER BY id DESC LIMIT 10
            """).fetchall()

            db.close()

            return {
                "total_dispatches": total,
                "by_pattern": [
                    {
                        "pattern": r["pattern"], "count": r["n"],
                        "avg_quality": round(r["avg_q"] or 0, 3),
                        "avg_latency_ms": round(r["avg_lat"] or 0, 1),
                        "avg_pipeline_ms": round(r["avg_pipe"] or 0, 1),
                        "success_rate": round(r["ok"] / max(1, r["n"]), 3),
                        "fallback_rate": round(r["fb"] / max(1, r["n"]), 3),
                        "enrichment_rate": round(r["enriched"] / max(1, r["n"]), 3),
                    }
                    for r in by_pattern
                ],
                "by_node": [
                    {
                        "node": r["node"], "count": r["n"],
                        "avg_quality": round(r["avg_q"] or 0, 3),
                        "avg_latency_ms": round(r["avg_lat"] or 0, 1),
                        "success_rate": round(r["ok"] / max(1, r["n"]), 3),
                    }
                    for r in by_node
                ],
                "recent_errors": [
                    {"pattern": r["pattern"], "node": r["node"],
                     "error": r["error"], "timestamp": r["timestamp"]}
                    for r in recent_errors
                ],
            }
        except Exception as e:
            return {"error": str(e)}

    async def batch_dispatch(self, tasks: list[dict],
                             concurrency: int = 3) -> list[DispatchResult]:
        """Dispatch multiple tasks with concurrency limit."""
        sem = asyncio.Semaphore(concurrency)
        results = []

        async def _run(task):
            async with sem:
                return await self.dispatch(
                    pattern=task.get("pattern", "simple"),
                    prompt=task.get("prompt", ""),
                    node_override=task.get("node"),
                    strategy_override=task.get("strategy"),
                )

        results = await asyncio.gather(*[_run(t) for t in tasks])
        return list(results)


# Singleton
_engine: Optional[DispatchEngine] = None

def get_engine() -> DispatchEngine:
    global _engine
    if _engine is None:
        _engine = DispatchEngine()
    return _engine
