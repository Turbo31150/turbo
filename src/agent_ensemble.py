"""JARVIS Agent Ensemble — Smart multi-agent execution with output scoring and selection.

More sophisticated than race (first wins) or consensus (majority wins):
  - Runs N agents on the same task
  - Scores each output independently (length, structure, relevance, confidence)
  - Selects the best output (or merges top outputs)
  - Learns which ensembles produce best results per pattern

Usage:
    from src.agent_ensemble import AgentEnsemble, get_ensemble
    ens = get_ensemble()
    result = await ens.execute("code", "Ecris un parser JSON", nodes=["M1", "OL1"])
    # result contains best_output, all_scores, winning_node
"""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional


__all__ = [
    "AgentEnsemble",
    "EnsembleOutput",
    "EnsembleResult",
    "get_ensemble",
]

logger = logging.getLogger("jarvis.ensemble")

DB_PATH = "F:/BUREAU/turbo/etoile.db"


@dataclass
class EnsembleOutput:
    """Output from a single ensemble member."""
    node: str
    content: str
    latency_ms: float
    success: bool
    scores: dict = field(default_factory=dict)  # Detailed scoring
    total_score: float = 0


@dataclass
class EnsembleResult:
    """Full ensemble execution result."""
    pattern: str
    prompt: str
    best_output: EnsembleOutput
    all_outputs: list[EnsembleOutput]
    strategy: str  # best_of_n, merge_top2, weighted_vote
    total_latency_ms: float
    ensemble_size: int
    agreement_score: float  # How much outputs agree (0-1)


class AgentEnsemble:
    """Multi-agent ensemble execution with intelligent output selection."""

    # Scoring weights per pattern
    SCORING_WEIGHTS = {
        "code": {"length": 0.15, "structure": 0.3, "relevance": 0.25, "confidence": 0.15, "speed": 0.15},
        "simple": {"length": 0.1, "structure": 0.1, "relevance": 0.3, "confidence": 0.2, "speed": 0.3},
        "reasoning": {"length": 0.2, "structure": 0.3, "relevance": 0.2, "confidence": 0.2, "speed": 0.1},
        "analysis": {"length": 0.2, "structure": 0.3, "relevance": 0.25, "confidence": 0.15, "speed": 0.1},
        "default": {"length": 0.15, "structure": 0.2, "relevance": 0.25, "confidence": 0.2, "speed": 0.2},
    }

    def __init__(self):
        self._history: list[dict] = []
        self._ensure_table()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                CREATE TABLE IF NOT EXISTS ensemble_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT, ensemble_size INTEGER,
                    strategy TEXT, winning_node TEXT,
                    best_score REAL, agreement REAL,
                    total_latency_ms REAL, nodes_used TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.commit()
            db.close()
        except Exception:
            pass

    async def execute(self, pattern: str, prompt: str,
                      nodes: Optional[list[str]] = None,
                      strategy: str = "best_of_n",
                      timeout_s: float = 30.0) -> EnsembleResult:
        """Execute ensemble and return best result."""
        if not nodes:
            nodes = self._default_nodes(pattern)

        t0 = time.time()

        # Run all nodes in parallel
        outputs = await self._run_parallel(pattern, prompt, nodes, timeout_s)

        # Score each output
        for output in outputs:
            if output.success and output.content:
                output.scores = self._score_output(pattern, prompt, output.content, output.latency_ms)
                output.total_score = sum(
                    output.scores.get(k, 0) * w
                    for k, w in self.SCORING_WEIGHTS.get(pattern, self.SCORING_WEIGHTS["default"]).items()
                )

        # Select best
        successful = [o for o in outputs if o.success and o.content]
        if not successful:
            # All failed
            best = EnsembleOutput(node="none", content="", latency_ms=0, success=False)
        elif strategy == "best_of_n":
            best = max(successful, key=lambda o: o.total_score)
        elif strategy == "merge_top2" and len(successful) >= 2:
            sorted_outputs = sorted(successful, key=lambda o: o.total_score, reverse=True)
            best = self._merge_outputs(sorted_outputs[0], sorted_outputs[1], pattern)
        elif strategy == "weighted_vote":
            best = self._weighted_vote(successful, pattern)
        else:
            best = max(successful, key=lambda o: o.total_score) if successful else outputs[0]

        # Calculate agreement
        agreement = self._calculate_agreement(successful)

        total_latency = (time.time() - t0) * 1000

        result = EnsembleResult(
            pattern=pattern,
            prompt=prompt[:100],
            best_output=best,
            all_outputs=outputs,
            strategy=strategy,
            total_latency_ms=total_latency,
            ensemble_size=len(nodes),
            agreement_score=agreement,
        )

        # Log
        self._log_result(result)
        self._history.append({
            "pattern": pattern, "nodes": nodes,
            "winner": best.node, "score": best.total_score,
            "agreement": agreement,
        })
        if len(self._history) > 200:
            self._history = self._history[-200:]

        return result

    def _default_nodes(self, pattern: str) -> list[str]:
        """Pick default ensemble nodes based on pattern."""
        if pattern in ("simple", "classifier"):
            return ["M1", "OL1"]
        elif pattern in ("code", "architecture", "security"):
            return ["M1", "OL1"]
        elif pattern in ("reasoning", "math"):
            return ["M1", "M2"]
        else:
            return ["M1", "OL1"]

    async def _run_parallel(self, pattern: str, prompt: str,
                            nodes: list[str], timeout_s: float) -> list[EnsembleOutput]:
        """Run dispatch on all nodes in parallel."""
        async def _call_node(node: str) -> EnsembleOutput:
            try:
                from src.pattern_agents import PatternAgentRegistry
                reg = PatternAgentRegistry()
                agent = reg.agents.get(pattern) or reg.agents.get("simple")
                client = await reg._get_client()
                t0 = time.time()
                result = await asyncio.wait_for(
                    agent._call_node(client, node, prompt),
                    timeout=timeout_s,
                )
                latency = (time.time() - t0) * 1000
                content = result.content if hasattr(result, 'content') else ""
                success = result.ok if hasattr(result, 'ok') else bool(content)
                return EnsembleOutput(
                    node=node, content=content,
                    latency_ms=latency, success=success,
                )
            except asyncio.TimeoutError:
                return EnsembleOutput(node=node, content="", latency_ms=timeout_s*1000, success=False)
            except Exception:
                return EnsembleOutput(node=node, content="", latency_ms=0, success=False)

        results = await asyncio.gather(*[_call_node(n) for n in nodes])
        return list(results)

    def _score_output(self, pattern: str, prompt: str,
                      content: str, latency_ms: float) -> dict:
        """Score an output on multiple dimensions."""
        scores = {}

        # Length score
        length = len(content)
        if pattern == "simple":
            scores["length"] = 1.0 if 10 < length < 300 else 0.5 if length < 500 else 0.3
        elif pattern in ("code", "analysis", "architecture"):
            scores["length"] = min(1.0, length / 500)
        else:
            scores["length"] = min(1.0, length / 200)

        # Structure score
        lines = content.split("\n")
        has_code = "```" in content or "def " in content or "class " in content
        has_lists = any(l.strip().startswith(("-", "*", "1.")) for l in lines)
        has_headers = any(l.strip().startswith("#") for l in lines)

        structure = 0.3  # base
        if len(lines) > 1:
            structure += 0.2
        if has_code and pattern == "code":
            structure += 0.3
        elif has_lists or has_headers:
            structure += 0.2
        if len(lines) > 5:
            structure += 0.1
        scores["structure"] = min(1.0, structure)

        # Relevance score (keyword overlap with prompt)
        prompt_words = set(re.findall(r'\b\w{3,}\b', prompt.lower()))
        content_words = set(re.findall(r'\b\w{3,}\b', content.lower()))
        if prompt_words:
            overlap = len(prompt_words & content_words) / len(prompt_words)
            scores["relevance"] = min(1.0, overlap * 2)
        else:
            scores["relevance"] = 0.5

        # Confidence score (no hedging, no errors)
        confidence = 0.7
        hedging = ["peut-etre", "je pense", "il semble", "probably", "might", "possibly"]
        errors = ["erreur", "error", "exception", "failed", "impossible"]
        if any(h in content.lower() for h in hedging):
            confidence -= 0.2
        if any(e in content.lower() for e in errors):
            confidence -= 0.3
        if content.strip().endswith((".", "```", ")")):
            confidence += 0.1  # Properly terminated
        scores["confidence"] = max(0, min(1.0, confidence))

        # Speed score
        if latency_ms < 1000:
            scores["speed"] = 1.0
        elif latency_ms < 3000:
            scores["speed"] = 0.8
        elif latency_ms < 10000:
            scores["speed"] = 0.5
        else:
            scores["speed"] = 0.2

        return scores

    def _merge_outputs(self, top1: EnsembleOutput, top2: EnsembleOutput,
                       pattern: str) -> EnsembleOutput:
        """Merge top 2 outputs into a combined result."""
        # Simple merge: take the longer/better structured one as base
        if len(top1.content) > len(top2.content) * 1.5:
            merged = top1.content
        elif len(top2.content) > len(top1.content) * 1.5:
            merged = top2.content
        else:
            # Both similar length — use the higher scored one
            merged = top1.content

        return EnsembleOutput(
            node=f"{top1.node}+{top2.node}",
            content=merged,
            latency_ms=max(top1.latency_ms, top2.latency_ms),
            success=True,
            scores=top1.scores,
            total_score=(top1.total_score + top2.total_score) / 2,
        )

    def _weighted_vote(self, outputs: list[EnsembleOutput],
                       pattern: str) -> EnsembleOutput:
        """Weighted vote: highest total weighted score wins."""
        from src.pattern_agents import NODES
        weighted = []
        for o in outputs:
            node_weight = NODES.get(o.node, {}).get("weight", 1.0)
            weighted_score = o.total_score * node_weight
            weighted.append((o, weighted_score))

        best = max(weighted, key=lambda x: x[1])
        return best[0]

    def _calculate_agreement(self, outputs: list[EnsembleOutput]) -> float:
        """Calculate how much outputs agree (word overlap between pairs)."""
        if len(outputs) < 2:
            return 1.0

        agreements = []
        for i in range(len(outputs)):
            for j in range(i + 1, len(outputs)):
                words_i = set(re.findall(r'\b\w{3,}\b', outputs[i].content.lower()))
                words_j = set(re.findall(r'\b\w{3,}\b', outputs[j].content.lower()))
                if words_i and words_j:
                    overlap = len(words_i & words_j) / max(len(words_i), len(words_j))
                    agreements.append(overlap)

        return sum(agreements) / max(1, len(agreements))

    def _log_result(self, result: EnsembleResult):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                INSERT INTO ensemble_log
                (pattern, ensemble_size, strategy, winning_node,
                 best_score, agreement, total_latency_ms, nodes_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.pattern, result.ensemble_size, result.strategy,
                result.best_output.node, result.best_output.total_score,
                result.agreement_score, result.total_latency_ms,
                ",".join(o.node for o in result.all_outputs),
            ))
            db.commit()
            db.close()
        except Exception:
            pass

    def get_ensemble_stats(self) -> dict:
        """Stats about ensemble executions."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            total = db.execute("SELECT COUNT(*) FROM ensemble_log").fetchone()[0]
            by_pattern = db.execute("""
                SELECT pattern, COUNT(*) as n,
                       AVG(best_score) as avg_score,
                       AVG(agreement) as avg_agree,
                       AVG(total_latency_ms) as avg_lat
                FROM ensemble_log GROUP BY pattern ORDER BY n DESC
            """).fetchall()

            by_winner = db.execute("""
                SELECT winning_node, COUNT(*) as wins
                FROM ensemble_log GROUP BY winning_node ORDER BY wins DESC
            """).fetchall()

            db.close()

            return {
                "total_ensembles": total,
                "by_pattern": [
                    {
                        "pattern": r["pattern"], "count": r["n"],
                        "avg_score": round(r["avg_score"] or 0, 3),
                        "avg_agreement": round(r["avg_agree"] or 0, 3),
                        "avg_latency_ms": round(r["avg_lat"] or 0, 1),
                    }
                    for r in by_pattern
                ],
                "winner_distribution": {r["winning_node"]: r["wins"] for r in by_winner},
                "recent_history": self._history[-10:],
            }
        except Exception:
            return {"total_ensembles": 0}

    def get_best_ensemble_config(self, pattern: str) -> dict:
        """Get the historically best ensemble configuration for a pattern."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT nodes_used, AVG(best_score) as avg_score, COUNT(*) as n
                FROM ensemble_log WHERE pattern = ?
                GROUP BY nodes_used HAVING n >= 3
                ORDER BY avg_score DESC LIMIT 3
            """, (pattern,)).fetchall()
            db.close()

            if rows:
                return {
                    "pattern": pattern,
                    "best_config": rows[0]["nodes_used"],
                    "avg_score": round(rows[0]["avg_score"], 3),
                    "sample_size": rows[0]["n"],
                    "alternatives": [
                        {"nodes": r["nodes_used"], "score": round(r["avg_score"], 3), "n": r["n"]}
                        for r in rows[1:]
                    ],
                }
            return {"pattern": pattern, "status": "insufficient_data"}
        except Exception:
            return {"pattern": pattern, "status": "error"}


# Singleton
_ensemble: Optional[AgentEnsemble] = None

def get_ensemble() -> AgentEnsemble:
    global _ensemble
    if _ensemble is None:
        _ensemble = AgentEnsemble()
    return _ensemble
