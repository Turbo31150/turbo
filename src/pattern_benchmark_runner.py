"""JARVIS Pattern Benchmark Runner — Automated benchmarking of pattern agents.

Runs configurable benchmarks:
  - Per-pattern: test each pattern type on N prompts
  - Per-node: test each node on diverse tasks
  - Per-strategy: compare single/race/consensus/category
  - Cross-pattern: test routing accuracy
  - Stress: parallel load testing

Usage:
    from src.pattern_benchmark_runner import BenchmarkRunner
    runner = BenchmarkRunner()
    report = await runner.run_quick()           # 20 tests, ~2min
    report = await runner.run_full()            # 100 tests, ~10min
    report = await runner.run_stress(parallel=5) # load test
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from src.pattern_agents import PatternAgentRegistry, AgentResult, AGENT_CONFIGS
from pathlib import Path


__all__ = [
    "BenchmarkReport",
    "BenchmarkResult",
    "BenchmarkRunner",
]

logger = logging.getLogger("jarvis.benchmark_runner")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")

# Test prompts per pattern
BENCHMARK_PROMPTS = {
    "simple": [
        "Bonjour, comment ca va?",
        "Quelle est la capitale de la France?",
        "Merci beaucoup!",
    ],
    "code": [
        "Ecris une fonction Python qui trie une liste par frequence",
        "Ecris un decorator qui mesure le temps d'execution",
        "Ecris un parser JSON minimaliste en Python",
    ],
    "math": [
        "Calcule la derivee de f(x) = 3x^3 + 2x^2 - 5x + 1",
        "Resous: 2^10 mod 7",
        "Combien font 17 * 23 + 45 / 9?",
    ],
    "analysis": [
        "Compare Python vs JavaScript pour le backend",
        "Avantages et inconvenients du microservices",
        "Benchmark: SQLite vs PostgreSQL pour 1000 utilisateurs",
    ],
    "system": [
        "Comment verifier l'utilisation GPU sur Windows?",
        "Liste les processus qui consomment le plus de RAM",
        "Comment redemarrer un service Windows en PowerShell?",
    ],
    "creative": [
        "Ecris un haiku sur la programmation",
        "Invente un nom pour une startup IA",
        "Ecris un dialogue entre deux robots",
    ],
    "security": [
        "Quelles sont les 3 principales vulnerabilites OWASP?",
        "Comment securiser une API REST?",
        "Explique le principe de defense en profondeur",
    ],
    "trading": [
        "Analyse technique BTC: RSI et MACD",
        "Strategie de stop loss pour position 10x leverage",
        "Risk management pour portfolio crypto",
    ],
    "reasoning": [
        "Si A > B et B > C, que peut-on dire de A et C?",
        "Un train part a 14h, arrive a 16h30, distance 250km. Vitesse?",
        "Explique le paradoxe de Fermi",
    ],
    "web": [
        "Recherche les dernieres news sur l'IA",
        "Quel est le prix actuel du Bitcoin?",
        "Tendances technologiques 2026",
    ],
}


@dataclass
class BenchmarkResult:
    """Result of a single benchmark test."""
    pattern: str
    prompt: str
    node: str
    strategy: str
    ok: bool
    latency_ms: float
    tokens: int
    quality: float
    content_preview: str


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""
    name: str
    timestamp: str
    duration_ms: float
    total_tests: int
    success_count: int
    results: list[BenchmarkResult]
    per_pattern: dict
    per_node: dict
    recommendations: list[str]

    @property
    def success_rate(self) -> float:
        return self.success_count / max(1, self.total_tests)

    @property
    def summary(self) -> str:
        return (f"{self.name}: {self.success_count}/{self.total_tests} OK "
                f"({self.success_rate:.0%}) in {self.duration_ms:.0f}ms")


class BenchmarkRunner:
    """Automated benchmark runner for pattern agents."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.registry = PatternAgentRegistry()

    async def run_quick(self, patterns: list[str] = None) -> BenchmarkReport:
        """Quick benchmark: 1 prompt per pattern, ~2min."""
        if not patterns:
            patterns = list(BENCHMARK_PROMPTS.keys())

        tests = []
        for pattern in patterns:
            prompts = BENCHMARK_PROMPTS.get(pattern, ["Test prompt"])
            tests.append((pattern, prompts[0]))

        return await self._run_tests("quick", tests, parallel=3)

    async def run_full(self, patterns: list[str] = None) -> BenchmarkReport:
        """Full benchmark: all prompts per pattern, ~10min."""
        if not patterns:
            patterns = list(BENCHMARK_PROMPTS.keys())

        tests = []
        for pattern in patterns:
            for prompt in BENCHMARK_PROMPTS.get(pattern, ["Test"])[:3]:
                tests.append((pattern, prompt))

        return await self._run_tests("full", tests, parallel=5)

    async def run_stress(self, parallel: int = 5, repeat: int = 3) -> BenchmarkReport:
        """Stress test: parallel load on all patterns."""
        tests = []
        for _ in range(repeat):
            for pattern, prompts in BENCHMARK_PROMPTS.items():
                tests.append((pattern, prompts[0]))

        return await self._run_tests("stress", tests, parallel=parallel)

    async def run_node_comparison(self, prompt: str = "Ecris une fonction Python qui calcule fibonacci") -> BenchmarkReport:
        """Compare all nodes on the same prompt."""
        from src.pattern_agents import NODES
        tests = []
        for node in NODES:
            tests.append(("code", prompt))  # Use code pattern for all nodes

        return await self._run_tests("node-comparison", tests, parallel=len(tests))

    async def _run_tests(self, name: str, tests: list[tuple[str, str]],
                         parallel: int = 3) -> BenchmarkReport:
        """Run a set of tests with parallelism control."""
        t0 = time.perf_counter()
        results = []
        sem = asyncio.Semaphore(parallel)

        async def run_one(pattern, prompt):
            async with sem:
                try:
                    r = await self.registry.dispatch(pattern, prompt)
                    return BenchmarkResult(
                        pattern=pattern, prompt=prompt[:80],
                        node=r.node, strategy=r.strategy,
                        ok=r.ok, latency_ms=r.latency_ms,
                        tokens=r.tokens, quality=r.quality_score,
                        content_preview=r.content[:100] if r.content else "",
                    )
                except Exception as e:
                    return BenchmarkResult(
                        pattern=pattern, prompt=prompt[:80],
                        node="?", strategy="?",
                        ok=False, latency_ms=0,
                        tokens=0, quality=0,
                        content_preview=str(e)[:100],
                    )

        tasks = [run_one(p, q) for p, q in tests]
        results = await asyncio.gather(*tasks)

        total_ms = (time.perf_counter() - t0) * 1000

        # Aggregate stats
        per_pattern = defaultdict(lambda: {"ok": 0, "n": 0, "lat": [], "q": []})
        per_node = defaultdict(lambda: {"ok": 0, "n": 0, "lat": [], "q": []})

        for r in results:
            pp = per_pattern[r.pattern]
            pp["n"] += 1
            if r.ok:
                pp["ok"] += 1
            pp["lat"].append(r.latency_ms)
            pp["q"].append(r.quality)

            pn = per_node[r.node]
            pn["n"] += 1
            if r.ok:
                pn["ok"] += 1
            pn["lat"].append(r.latency_ms)
            pn["q"].append(r.quality)

        # Format
        pattern_stats = {
            p: {
                "success_rate": s["ok"] / max(1, s["n"]),
                "count": s["n"],
                "avg_latency_ms": sum(s["lat"]) / max(1, len(s["lat"])),
                "avg_quality": sum(s["q"]) / max(1, len(s["q"])),
            }
            for p, s in per_pattern.items()
        }
        node_stats = {
            n: {
                "success_rate": s["ok"] / max(1, s["n"]),
                "count": s["n"],
                "avg_latency_ms": sum(s["lat"]) / max(1, len(s["lat"])),
                "avg_quality": sum(s["q"]) / max(1, len(s["q"])),
            }
            for n, s in per_node.items()
        }

        # Recommendations
        recs = self._generate_recommendations(pattern_stats, node_stats)

        success_count = sum(1 for r in results if r.ok)

        report = BenchmarkReport(
            name=name,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            duration_ms=total_ms,
            total_tests=len(results),
            success_count=success_count,
            results=list(results),
            per_pattern=pattern_stats,
            per_node=node_stats,
            recommendations=recs,
        )

        # Save to DB
        self._save_report(report)

        return report

    def _generate_recommendations(self, pattern_stats: dict, node_stats: dict) -> list[str]:
        """Generate recommendations from benchmark results."""
        recs = []
        for pattern, stats in pattern_stats.items():
            if stats["success_rate"] < 0.5:
                recs.append(f"Pattern '{pattern}' failing ({stats['success_rate']:.0%}) — check node assignment")
            if stats["avg_latency_ms"] > 30000:
                recs.append(f"Pattern '{pattern}' slow ({stats['avg_latency_ms']:.0f}ms) — consider faster node")

        for node, stats in node_stats.items():
            if stats["success_rate"] < 0.3 and stats["count"] >= 3:
                recs.append(f"Node '{node}' unreliable ({stats['success_rate']:.0%}) — route traffic elsewhere")

        return recs

    def _save_report(self, report: BenchmarkReport):
        """Save benchmark report to DB."""
        try:
            db = sqlite3.connect(self.db_path)
            db.execute("""
                CREATE TABLE IF NOT EXISTS agent_benchmark_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, timestamp TEXT, duration_ms REAL,
                    total_tests INTEGER, success_count INTEGER,
                    success_rate REAL, summary TEXT
                )
            """)
            db.execute("""
                INSERT INTO agent_benchmark_reports
                (name, timestamp, duration_ms, total_tests, success_count, success_rate, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (report.name, report.timestamp, report.duration_ms,
                  report.total_tests, report.success_count,
                  report.success_rate, report.summary))
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to save benchmark: {e}")

    def get_history(self, limit: int = 10) -> list[dict]:
        """Get benchmark history."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT * FROM agent_benchmark_reports
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            db.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    async def close(self):
        await self.registry.close()
