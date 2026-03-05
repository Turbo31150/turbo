"""JARVIS Smart Dispatcher — Adaptive routing based on benchmark results.

Uses historical dispatch_log data to learn optimal routing for each pattern type.
Auto-adjusts node selection based on success rate, latency, and quality trends.

Usage:
    from src.smart_dispatcher import SmartDispatcher
    dispatcher = SmartDispatcher()
    result = await dispatcher.dispatch("Ecris un parser JSON Python")
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

import httpx

from src.pattern_agents import (
    PatternAgentRegistry,
    AgentResult,
    NODES,
    PatternAgent,
)

logger = logging.getLogger("jarvis.smart_dispatcher")

DB_PATH = "F:/BUREAU/turbo/etoile.db"


@dataclass
class NodeStats:
    """Runtime stats for a node from dispatch_log."""
    node: str
    total_calls: int = 0
    success_count: int = 0
    avg_latency_ms: float = 0
    avg_quality: float = 0
    p95_latency_ms: float = 0
    last_failure_ago_s: float = float("inf")
    weight: float = 1.0

    @property
    def success_rate(self) -> float:
        return self.success_count / max(1, self.total_calls)

    @property
    def score(self) -> float:
        """Composite score: higher is better."""
        sr = self.success_rate
        speed = max(0, 1 - (self.avg_latency_ms / 30000))  # normalize to 0-1 (30s=0)
        quality = self.avg_quality
        recency_penalty = 0 if self.last_failure_ago_s > 300 else 0.2  # penalty if failed recently
        return (sr * 0.4 + speed * 0.25 + quality * 0.25 + self.weight * 0.1) - recency_penalty


class SmartDispatcher:
    """Adaptive dispatcher that learns from dispatch history."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.registry = PatternAgentRegistry(db_path)
        self._stats_cache: dict[str, dict[str, NodeStats]] = {}  # pattern -> node -> stats
        self._cache_age = 0.0
        self._cache_ttl = 60.0  # refresh stats every 60s

    async def dispatch(self, prompt: str) -> AgentResult:
        """Auto-classify, pick best route, execute."""
        pattern = self.registry.classify(prompt)
        return await self.dispatch_typed(pattern, prompt)

    async def dispatch_typed(self, pattern: str, prompt: str) -> AgentResult:
        """Dispatch with known pattern type, using learned routing."""
        self._maybe_refresh_stats()

        agent = self.registry.agents.get(pattern)
        if not agent:
            return await self.registry.dispatch_auto(prompt)

        # Get best node for this pattern based on historical stats
        best_node = self._get_best_node(pattern, agent)

        if best_node and best_node != agent.primary_node:
            # Override agent's primary node with learned best
            logger.info(f"Smart override: {pattern} {agent.primary_node} -> {best_node}")
            original_primary = agent.primary_node
            agent.primary_node = best_node
            result = await self.registry.dispatch(pattern, prompt)
            agent.primary_node = original_primary  # restore
            return result

        return await self.registry.dispatch(pattern, prompt)

    async def dispatch_batch(self, prompts: list[str], max_parallel: int = 8) -> list[AgentResult]:
        """Dispatch multiple prompts with auto-classification."""
        sem = asyncio.Semaphore(max_parallel)
        async def _run(p):
            async with sem:
                return await self.dispatch(p)
        return await asyncio.gather(*[_run(p) for p in prompts])

    def _get_best_node(self, pattern: str, agent: PatternAgent) -> Optional[str]:
        """Pick the best node for a pattern based on historical data."""
        stats = self._stats_cache.get(pattern, {})
        if not stats:
            return None

        # Score all known nodes for this pattern
        candidates = []
        for node_name, ns in stats.items():
            if ns.total_calls >= 3:  # need minimum data
                candidates.append((node_name, ns.score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: -x[1])
        best = candidates[0]

        # Only override if significantly better (>10% score improvement)
        current = stats.get(agent.primary_node)
        if current and current.total_calls >= 3:
            if best[1] > current.score * 1.1:
                return best[0]
            return None  # current is good enough

        return best[0]

    def _maybe_refresh_stats(self):
        """Refresh stats cache from DB if stale."""
        now = time.time()
        if now - self._cache_age < self._cache_ttl:
            return

        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            cur = db.cursor()

            # Get stats per pattern per node from last 500 dispatches
            rows = cur.execute("""
                SELECT classified_type, node,
                       COUNT(*) as total,
                       SUM(success) as ok,
                       AVG(latency_ms) as avg_ms,
                       AVG(quality_score) as avg_q
                FROM agent_dispatch_log
                WHERE classified_type IS NOT NULL AND node IS NOT NULL
                GROUP BY classified_type, node
                ORDER BY classified_type, total DESC
            """).fetchall()

            self._stats_cache.clear()
            for r in rows:
                pat = r["classified_type"]
                node = r["node"]
                if pat not in self._stats_cache:
                    self._stats_cache[pat] = {}
                self._stats_cache[pat][node] = NodeStats(
                    node=node,
                    total_calls=r["total"],
                    success_count=r["ok"] or 0,
                    avg_latency_ms=r["avg_ms"] or 0,
                    avg_quality=r["avg_q"] or 0,
                    weight=NODES.get(node, {}).get("weight", 1.0),
                )

            db.close()
            self._cache_age = now
            logger.debug(f"Stats refreshed: {len(self._stats_cache)} patterns, {sum(len(v) for v in self._stats_cache.values())} node entries")

        except Exception as e:
            logger.warning(f"Stats refresh failed: {e}")

    def get_routing_report(self) -> dict:
        """Get current routing decisions as a report."""
        self._maybe_refresh_stats()
        report = {}
        for pat, agents_stats in self._stats_cache.items():
            agent = self.registry.agents.get(pat)
            if not agent:
                continue
            best_node = self._get_best_node(pat, agent)
            report[pat] = {
                "default_node": agent.primary_node,
                "smart_node": best_node or agent.primary_node,
                "overridden": best_node is not None and best_node != agent.primary_node,
                "nodes": {
                    n: {"calls": s.total_calls, "rate": f"{s.success_rate:.0%}", "avg_ms": round(s.avg_latency_ms), "score": round(s.score, 3)}
                    for n, s in agents_stats.items()
                }
            }
        return report

    async def health_check(self) -> dict:
        """Quick health check of all nodes."""
        client = await self.registry._get_client()
        results = {}
        for name, cfg in NODES.items():
            t0 = time.perf_counter()
            try:
                if cfg["type"] == "lmstudio":
                    r = await client.get(cfg["url"].replace("/api/v1/chat", "/api/v1/models"), timeout=3)
                    ms = (time.perf_counter() - t0) * 1000
                    results[name] = {"status": "ok", "ms": round(ms)}
                else:
                    r = await client.get("http://127.0.0.1:11434/api/tags", timeout=3)
                    ms = (time.perf_counter() - t0) * 1000
                    results[name] = {"status": "ok", "ms": round(ms)}
            except Exception as e:
                ms = (time.perf_counter() - t0) * 1000
                results[name] = {"status": "offline", "ms": round(ms), "error": str(e)[:50]}
        return results

    async def close(self):
        await self.registry.close()


# ── CLI ─────────────────────────────────────────────────────────────────────

async def _main():
    import sys
    d = SmartDispatcher()

    if "--report" in sys.argv:
        report = d.get_routing_report()
        import json
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif "--health" in sys.argv:
        h = await d.health_check()
        for name, info in h.items():
            print(f"  {name:<12} {info['status']:>8} {info['ms']:>5}ms")
    elif len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        r = await d.dispatch(prompt)
        print(f"Pattern: {r.pattern} | Node: {r.node} | {r.latency_ms:.0f}ms | Q={r.quality_score:.2f}")
        print(f"\n{r.content[:500]}")
    else:
        print("Usage: smart_dispatcher.py [--report|--health|<prompt>]")

    await d.close()

if __name__ == "__main__":
    asyncio.run(_main())
