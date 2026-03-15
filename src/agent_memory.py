"""Agent Memory — Persistent inter-session memory with similarity search.

TF-IDF based recall, category filtering, TTL expiry, access tracking.
Designed for JARVIS episodic memory across sessions.
"""

from __future__ import annotations

import math
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any

DB_MEMORY = Path(__file__).parent.parent / "data" / "agent_memory.db"


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, filter single-char tokens."""
    tokens = re.findall(r"[\w]+", text.lower())
    return [t for t in tokens if len(t) > 1]


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Build a TF-IDF vector from tokens and an IDF dictionary."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    vec: dict[str, float] = {}
    for token, count in counts.items():
        tf = count / total
        vec[token] = tf * idf.get(token, 1.0)
    return vec


def _cosine_sim(v1: dict[str, float], v2: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    if not v1 or not v2:
        return 0.0
    keys = set(v1) & set(v2)
    dot = sum(v1[k] * v2[k] for k in keys)
    mag1 = math.sqrt(sum(x * x for x in v1.values()))
    mag2 = math.sqrt(sum(x * x for x in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


class AgentMemory:
    """Persistent episodic memory with TF-IDF similarity search."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path or DB_MEMORY)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    tokens TEXT DEFAULT '',
                    importance REAL DEFAULT 0.5,
                    created_at REAL,
                    last_accessed REAL,
                    access_count INTEGER DEFAULT 0,
                    expires_at REAL DEFAULT NULL
                )
            """)

    def remember(
        self,
        content: str,
        category: str = "general",
        importance: float = 0.5,
        ttl_seconds: float | None = None,
    ) -> int:
        """Store a memory. Returns the memory ID."""
        tokens = " ".join(_tokenize(content))
        now = time.time()
        expires = now + ttl_seconds if ttl_seconds else None
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "INSERT INTO memories (content, category, tokens, importance, created_at, last_accessed, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (content, category, tokens, importance, now, now, expires),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def recall(
        self,
        query: str,
        limit: int = 5,
        category: str | None = None,
        min_similarity: float = 0.1,
    ) -> list[dict[str, Any]]:
        """Recall memories similar to query using TF-IDF cosine similarity."""
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            sql = "SELECT * FROM memories"
            params: list[Any] = []
            if category:
                sql += " WHERE category = ?"
                params.append(category)
            rows = conn.execute(sql, params).fetchall()

        if not rows:
            return []

        # Build IDF from all documents
        doc_count = len(rows)
        term_doc_count: Counter[str] = Counter()
        all_doc_tokens: list[list[str]] = []
        for row in rows:
            doc_tokens = row["tokens"].split() if row["tokens"] else []
            all_doc_tokens.append(doc_tokens)
            for t in set(doc_tokens):
                term_doc_count[t] += 1
        for t in set(query_tokens):
            if t not in term_doc_count:
                term_doc_count[t] = 0

        idf = {
            t: math.log((doc_count + 1) / (count + 1)) + 1
            for t, count in term_doc_count.items()
        }

        query_vec = _tfidf_vector(query_tokens, idf)

        scored: list[tuple[float, sqlite3.Row]] = []
        for row, doc_tokens in zip(rows, all_doc_tokens):
            doc_vec = _tfidf_vector(doc_tokens, idf)
            sim = _cosine_sim(query_vec, doc_vec)
            if sim >= min_similarity:
                scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Update access counts
        now = time.time()
        results: list[dict[str, Any]] = []
        with sqlite3.connect(self._db_path) as conn:
            for sim, row in scored[:limit]:
                conn.execute(
                    "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                    (now, row["id"]),
                )
                results.append({
                    "id": row["id"],
                    "content": row["content"],
                    "category": row["category"],
                    "importance": row["importance"],
                    "similarity": sim,
                    "access_count": row["access_count"] + 1,
                    "created_at": row["created_at"],
                })

        return results

    def forget(self, memory_id: int) -> bool:
        """Delete a memory by ID. Returns True if deleted."""
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cur.rowcount > 0

    def list_all(
        self,
        category: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List all memories, optionally filtered by category."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            sql = "SELECT * FROM memories"
            params: list[Any] = []
            if category:
                sql += " WHERE category = ?"
                params.append(category)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def cleanup(self) -> int:
        """Remove expired memories. Returns count of removed entries."""
        now = time.time()
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
            return cur.rowcount

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]
            cats = conn.execute(
                "SELECT category, COUNT(*) as c FROM memories GROUP BY category"
            ).fetchall()
            return {
                "total": total,
                "categories": {r["category"]: r["c"] for r in cats},
            }


agent_memory = AgentMemory()
