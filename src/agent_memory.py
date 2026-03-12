"""JARVIS Agent Memory — Persistent inter-session memory with similarity search.

Uses TF-IDF + cosine similarity for simple vector search without heavy dependencies.
SQLite backend for persistence.

Usage:
    from src.agent_memory import agent_memory
    agent_memory.remember("User prefers dark mode", category="preference")
    results = agent_memory.recall("theme preference")
    agent_memory.forget(memory_id)
"""

from __future__ import annotations

import logging
import math
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.memory")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "agent_memory.db"


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alpha, filter short tokens."""
    return [w for w in re.findall(r'[a-zàâéèêëïîôùûüç0-9]+', text.lower()) if len(w) > 1]


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Compute TF-IDF vector for a token list."""
    tf = Counter(tokens)
    total = len(tokens) or 1
    return {t: (count / total) * idf.get(t, 1.0) for t, count in tf.items()}


def _cosine_sim(v1: dict[str, float], v2: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    common = set(v1.keys()) & set(v2.keys())
    if not common:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in common)
    mag1 = math.sqrt(sum(v ** 2 for v in v1.values()))
    mag2 = math.sqrt(sum(v ** 2 for v in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


class AgentMemory:
    """Persistent memory with similarity search."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._idf: dict[str, float] = {}
        self._init_db()
        self._rebuild_idf()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    tokens TEXT DEFAULT '',
                    importance REAL DEFAULT 1.0,
                    access_count INTEGER DEFAULT 0,
                    created_at REAL,
                    last_accessed REAL,
                    expires_at REAL DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_category ON memories(category)")

    def _rebuild_idf(self) -> None:
        """Rebuild IDF from all memories."""
        with sqlite3.connect(str(self._db_path)) as conn:
            rows = conn.execute("SELECT tokens FROM memories").fetchall()
        if not rows:
            return
        n_docs = len(rows)
        df: Counter = Counter()
        for (tokens_str,) in rows:
            unique_tokens = set(tokens_str.split())
            for t in unique_tokens:
                df[t] += 1
        self._idf = {t: math.log(n_docs / (1 + count)) for t, count in df.items()}

    def remember(self, content: str, category: str = "general",
                 importance: float = 1.0, ttl_days: int = 0) -> int:
        """Store a memory. Returns memory ID."""
        tokens = _tokenize(content)
        now = time.time()
        expires = now + (ttl_days * 86400) if ttl_days > 0 else 0
        with sqlite3.connect(str(self._db_path)) as conn:
            c = conn.execute(
                "INSERT INTO memories (content, category, tokens, importance, created_at, last_accessed, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (content, category, " ".join(tokens), importance, now, now, expires),
            )
            mem_id = c.lastrowid
        self._rebuild_idf()
        logger.info("Memory %d stored: %s", mem_id, content[:60])
        return mem_id

    def recall(self, query: str, limit: int = 5, category: str | None = None,
               min_similarity: float = 0.1) -> list[dict[str, Any]]:
        """
        Search memories by similarity. Returns top matches.

        Parameters:
            query (str): The query to search for.
            limit (int, optional): Maximum number of results to return. Defaults to 5.
            category (str | None, optional): Filter memories by category. Defaults to None.
            min_similarity (float, optional): Minimum similarity score for a match. Defaults to 0.1.

        Returns:
            list[dict[str, Any]]: List of matching memories with metadata.
        """
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_vec = _tfidf_vector(query_tokens, self._idf)

        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            sql = "SELECT * FROM memories WHERE (expires_at = 0 OR expires_at > ?)"
            params: list[Any] = [time.time()]
            if category:
                sql += " AND category = ?"
                params.append(category)
            rows = conn.execute(sql, params).fetchall()

        scored = []
        for row in rows:
            mem_tokens = row["tokens"].split()
            if not mem_tokens:
                continue
            mem_vec = _tfidf_vector(mem_tokens, self._idf)
            sim = _cosine_sim(query_vec, mem_vec)
            if sim >= min_similarity:
                scored.append((sim, dict(row)))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Update access counts
        results = []
        with sqlite3.connect(str(self._db_path)) as conn:
            for sim, row in scored[:limit]:
                conn.execute(
                    "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                    (time.time(), row["id"]),
                )
                results.append({
                    "id": row["id"],
                    "content": row["content"],
                    "category": row["category"],
                    "similarity": round(sim, 4),
                    "importance": row["importance"],
                    "access_count": row["access_count"] + 1,
                    "created_at": row["created_at"],
                })

        return results

    def forget(self, memory_id: int) -> bool:
        """Delete a specific memory."""
        with sqlite3.connect(str(self._db_path)) as conn:
            c = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            if c.rowcount > 0:
                self._rebuild_idf()
                return True
            return False

    def list_all(self, category: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """List all memories."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            sql = "SELECT id, content, category, importance, access_count, created_at FROM memories"
            params: list[Any] = []
            if category:
                sql += " WHERE category = ?"
                params.append(category)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def cleanup(self, max_age_days: int = 90) -> int:
        """Remove expired + old low-importance memories."""
        now = time.time()
        cutoff = now - (max_age_days * 86400)
        with sqlite3.connect(str(self._db_path)) as conn:
            # Remove expired
            c1 = conn.execute("DELETE FROM memories WHERE expires_at > 0 AND expires_at < ?", (now,))
            # Remove old + low importance + rarely accessed
            c2 = conn.execute(
                "DELETE FROM memories WHERE created_at < ? AND importance < 0.5 AND access_count < 2",
                (cutoff,),
            )
            total = c1.rowcount + c2.rowcount
        if total > 0:
            self._rebuild_idf()
        return total

    def get_stats(self) -> dict[str, Any]:
        """Memory stats."""
        with sqlite3.connect(str(self._db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            cats = conn.execute("SELECT category, COUNT(*) FROM memories GROUP BY category").fetchall()
            return {
                "total": total,
                "categories": {c: n for c, n in cats},
                "idf_vocab_size": len(self._idf),
            }


# Global singleton
agent_memory = AgentMemory()
