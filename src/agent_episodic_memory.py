"""JARVIS Agent Episodic Memory — Dispatch-specific memory with pattern learning.

Stores and retrieves:
  - Episodic: past dispatches and their outcomes (what worked, what failed)
  - Semantic: learned facts about patterns, nodes, user preferences
  - Working: current session context and pending tasks
  - Procedural: optimal strategies per pattern type learned over time

Usage:
    from src.agent_episodic_memory import EpisodicMemory, get_episodic_memory
    mem = get_episodic_memory()
    mem.store_episode("code", "M1", "Write a parser", success=True, quality=0.9)
    relevant = mem.recall("Write a JSON parser", top_k=5)
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("jarvis.episodic_memory")

DB_PATH = "F:/BUREAU/turbo/etoile.db"


@dataclass
class Episode:
    """A single remembered dispatch episode."""
    pattern: str
    node: str
    prompt_hash: str
    prompt_preview: str
    success: bool
    quality: float
    latency_ms: float
    strategy: str
    timestamp: str
    relevance: float = 0.0


@dataclass
class SemanticFact:
    """A learned fact about the system."""
    fact_type: str
    subject: str
    predicate: str
    value: str
    confidence: float
    source: str
    updated_at: str


@dataclass
class WorkingContext:
    """Current session working memory."""
    current_task: str = ""
    recent_patterns: list[str] = field(default_factory=list)
    recent_nodes: list[str] = field(default_factory=list)
    session_start: float = field(default_factory=time.time)
    dispatch_count: int = 0
    success_count: int = 0


class EpisodicMemory:
    """Episodic + semantic + working memory for pattern agent dispatches."""

    MAX_EPISODES = 5000
    MAX_FACTS = 500

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.working = WorkingContext()
        self._episodes: list[Episode] = []
        self._facts: dict[str, SemanticFact] = {}
        self._keyword_index: dict[str, list[int]] = defaultdict(list)
        self._ensure_tables()
        self._load_episodes()
        self._load_facts()
        self._build_index()

    def _ensure_tables(self):
        try:
            db = sqlite3.connect(self.db_path)
            db.execute("""
                CREATE TABLE IF NOT EXISTS agent_episodic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT, node TEXT, prompt_hash TEXT, prompt_preview TEXT,
                    success INTEGER, quality REAL, latency_ms REAL, strategy TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS agent_semantic_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_type TEXT, subject TEXT, predicate TEXT, value TEXT,
                    confidence REAL, source TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(fact_type, subject, predicate)
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_epimem_pattern ON agent_episodic_memory(pattern)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_epimem_hash ON agent_episodic_memory(prompt_hash)")
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to create memory tables: {e}")

    def _load_episodes(self):
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT * FROM agent_episodic_memory ORDER BY id DESC LIMIT ?
            """, (self.MAX_EPISODES,)).fetchall()
            db.close()
            self._episodes = [
                Episode(pattern=r["pattern"], node=r["node"], prompt_hash=r["prompt_hash"],
                        prompt_preview=r["prompt_preview"], success=bool(r["success"]),
                        quality=r["quality"] or 0, latency_ms=r["latency_ms"] or 0,
                        strategy=r["strategy"] or "", timestamp=r["timestamp"] or "")
                for r in rows
            ]
        except Exception:
            self._episodes = []

        if not self._episodes:
            self._seed_from_dispatch_log()

    def _seed_from_dispatch_log(self):
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT classified_type as pattern, node, request_text,
                       success, quality_score, latency_ms, strategy, timestamp
                FROM agent_dispatch_log WHERE request_text IS NOT NULL
                ORDER BY id DESC LIMIT 1000
            """).fetchall()

            for r in rows:
                prompt = r["request_text"] or ""
                self._episodes.append(Episode(
                    pattern=r["pattern"] or "unknown", node=r["node"] or "M1",
                    prompt_hash=hashlib.md5(prompt.encode()).hexdigest()[:12],
                    prompt_preview=prompt[:100], success=bool(r["success"]),
                    quality=r["quality_score"] or 0, latency_ms=r["latency_ms"] or 0,
                    strategy=r["strategy"] or "single", timestamp=r["timestamp"] or "",
                ))
            db.close()
            logger.info(f"Seeded {len(rows)} episodes from dispatch_log")
        except Exception as e:
            logger.warning(f"Seed failed: {e}")

    def _load_facts(self):
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM agent_semantic_facts ORDER BY confidence DESC").fetchall()
            db.close()
            for r in rows:
                key = f"{r['fact_type']}:{r['subject']}:{r['predicate']}"
                self._facts[key] = SemanticFact(
                    fact_type=r["fact_type"], subject=r["subject"],
                    predicate=r["predicate"], value=r["value"],
                    confidence=r["confidence"] or 0.5, source=r["source"] or "",
                    updated_at=r["updated_at"] or "",
                )
        except Exception:
            pass

    def _build_index(self):
        self._keyword_index.clear()
        for i, ep in enumerate(self._episodes):
            for w in set(ep.prompt_preview.lower().split()):
                if len(w) >= 3:
                    self._keyword_index[w].append(i)

    def store_episode(self, pattern: str, node: str, prompt: str,
                      success: bool = True, quality: float = 0.5,
                      latency_ms: float = 0, strategy: str = "single"):
        h = hashlib.md5(prompt.encode()).hexdigest()[:12]
        preview = prompt[:100]
        ep = Episode(pattern=pattern, node=node, prompt_hash=h, prompt_preview=preview,
                     success=success, quality=quality, latency_ms=latency_ms,
                     strategy=strategy, timestamp=time.strftime("%Y-%m-%d %H:%M:%S"))
        self._episodes.insert(0, ep)

        for w in set(preview.lower().split()):
            if len(w) >= 3:
                self._keyword_index[w].insert(0, 0)

        if len(self._episodes) > self.MAX_EPISODES:
            self._episodes = self._episodes[:self.MAX_EPISODES]

        self.working.dispatch_count += 1
        if success:
            self.working.success_count += 1

        try:
            db = sqlite3.connect(self.db_path)
            db.execute("""
                INSERT INTO agent_episodic_memory
                (pattern, node, prompt_hash, prompt_preview, success, quality, latency_ms, strategy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (pattern, node, h, preview, int(success), quality, latency_ms, strategy))
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to persist episode: {e}")

    def recall(self, query: str, top_k: int = 5, pattern_filter: str = None) -> list[Episode]:
        query_words = set(query.lower().split())
        scores = defaultdict(float)

        for word in query_words:
            if len(word) < 3:
                continue
            for idx in self._keyword_index.get(word, []):
                if idx < len(self._episodes):
                    scores[idx] += 1.0

        candidates = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        results = []
        for idx, score in candidates[:top_k * 2]:
            ep = self._episodes[idx]
            if pattern_filter and ep.pattern != pattern_filter:
                continue
            ep.relevance = score / max(1, len(query_words))
            results.append(ep)
            if len(results) >= top_k:
                break
        return results

    def store_fact(self, fact_type: str, subject: str, predicate: str,
                   value: str, confidence: float = 0.8, source: str = "auto"):
        key = f"{fact_type}:{subject}:{predicate}"
        self._facts[key] = SemanticFact(
            fact_type=fact_type, subject=subject, predicate=predicate,
            value=value, confidence=confidence, source=source,
            updated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        try:
            db = sqlite3.connect(self.db_path)
            db.execute("""
                INSERT INTO agent_semantic_facts
                (fact_type, subject, predicate, value, confidence, source)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(fact_type, subject, predicate)
                DO UPDATE SET value=?, confidence=?, source=?, updated_at=CURRENT_TIMESTAMP
            """, (fact_type, subject, predicate, value, confidence, source,
                  value, confidence, source))
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to persist fact: {e}")

    def get_facts(self, fact_type: str = None, subject: str = None) -> list[SemanticFact]:
        results = []
        for key, fact in self._facts.items():
            if fact_type and fact.fact_type != fact_type:
                continue
            if subject and fact.subject != subject:
                continue
            results.append(fact)
        return sorted(results, key=lambda f: -f.confidence)

    def get_node_memory(self, node: str) -> dict:
        episodes = [ep for ep in self._episodes if ep.node == node]
        facts = self.get_facts(subject=node)
        total = len(episodes)
        ok = sum(1 for ep in episodes if ep.success)
        return {
            "node": node, "total_episodes": total,
            "success_rate": ok / max(1, total),
            "avg_latency": sum(ep.latency_ms for ep in episodes) / max(1, total),
            "patterns": list(set(ep.pattern for ep in episodes)),
            "facts": [{"p": f.predicate, "v": f.value, "c": f.confidence} for f in facts],
        }

    def get_pattern_memory(self, pattern: str) -> dict:
        episodes = [ep for ep in self._episodes if ep.pattern == pattern]
        total = len(episodes)
        ok = sum(1 for ep in episodes if ep.success)
        node_stats = defaultdict(lambda: {"ok": 0, "n": 0})
        for ep in episodes:
            node_stats[ep.node]["n"] += 1
            if ep.success:
                node_stats[ep.node]["ok"] += 1
        best = max(node_stats.items(), key=lambda x: x[1]["ok"] / max(1, x[1]["n"]),
                    default=("M1", {"ok": 0, "n": 0}))
        return {
            "pattern": pattern, "total": total,
            "success_rate": ok / max(1, total),
            "best_node": best[0],
            "nodes": {n: {"rate": s["ok"] / max(1, s["n"]), "n": s["n"]} for n, s in node_stats.items()},
        }

    def learn_from_history(self) -> list[dict]:
        learned = []
        pattern_nodes = defaultdict(lambda: defaultdict(lambda: {"ok": 0, "n": 0}))
        for ep in self._episodes:
            pn = pattern_nodes[ep.pattern][ep.node]
            pn["n"] += 1
            if ep.success:
                pn["ok"] += 1

        for pattern, nodes in pattern_nodes.items():
            best = max(nodes.items(), key=lambda x: x[1]["ok"] / max(1, x[1]["n"]))
            rate = best[1]["ok"] / max(1, best[1]["n"])
            if best[1]["n"] >= 5 and rate > 0.5:
                self.store_fact("pattern_affinity", pattern, "best_node", best[0],
                                confidence=min(1, rate), source="history")
                learned.append({"fact": f"{pattern} -> {best[0]}", "confidence": round(rate, 2)})

        node_stats = defaultdict(lambda: {"ok": 0, "n": 0, "lat": []})
        for ep in self._episodes:
            ns = node_stats[ep.node]
            ns["n"] += 1
            if ep.success:
                ns["ok"] += 1
            ns["lat"].append(ep.latency_ms)

        for node, stats in node_stats.items():
            rate = stats["ok"] / max(1, stats["n"])
            avg_lat = sum(stats["lat"]) / max(1, len(stats["lat"]))
            if rate < 0.3 and stats["n"] >= 10:
                self.store_fact("node_capability", node, "status", "degraded",
                                confidence=1 - rate, source="history")
                learned.append({"fact": f"{node} degraded", "confidence": round(1 - rate, 2)})

        return learned

    def get_session_summary(self) -> dict:
        elapsed = time.time() - self.working.session_start
        return {
            "elapsed_s": round(elapsed),
            "dispatches": self.working.dispatch_count,
            "success_rate": self.working.success_count / max(1, self.working.dispatch_count),
            "episodes_total": len(self._episodes),
            "facts_total": len(self._facts),
        }


_memory: Optional[EpisodicMemory] = None

def get_episodic_memory() -> EpisodicMemory:
    global _memory
    if _memory is None:
        _memory = EpisodicMemory()
    return _memory
