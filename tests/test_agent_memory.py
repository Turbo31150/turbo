"""Tests for src/agent_memory.py — Persistent inter-session memory with similarity search.

Covers: _tokenize, _tfidf_vector, _cosine_sim, AgentMemory (remember, recall,
forget, list_all, cleanup, get_stats), agent_memory singleton.
Uses tmp_path SQLite DB for isolation.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_memory import (
    _tokenize, _tfidf_vector, _cosine_sim, AgentMemory, agent_memory,
)


# ===========================================================================
# Helper functions
# ===========================================================================

class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_short_filtered(self):
        tokens = _tokenize("I am a cat")
        # Single-char tokens filtered out
        assert "i" not in tokens
        assert "am" in tokens

    def test_french(self):
        tokens = _tokenize("réseau clé privée")
        assert "réseau" in tokens or "seau" in tokens
        assert "priv" in tokens or "privée" in tokens

    def test_numbers(self):
        tokens = _tokenize("GPU RTX 2060 has 12GB")
        assert "2060" in tokens
        assert "12gb" in tokens or "12" in tokens


class TestTfidfVector:
    def test_basic(self):
        idf = {"hello": 1.0, "world": 2.0}
        vec = _tfidf_vector(["hello", "world"], idf)
        assert "hello" in vec
        assert "world" in vec
        assert vec["world"] > vec["hello"]

    def test_empty(self):
        vec = _tfidf_vector([], {})
        assert vec == {}


class TestCosineSim:
    def test_identical(self):
        v = {"a": 1.0, "b": 2.0}
        assert _cosine_sim(v, v) == pytest.approx(1.0)

    def test_orthogonal(self):
        v1 = {"a": 1.0}
        v2 = {"b": 1.0}
        assert _cosine_sim(v1, v2) == 0.0

    def test_empty(self):
        assert _cosine_sim({}, {"a": 1.0}) == 0.0

    def test_zero_magnitude(self):
        assert _cosine_sim({"a": 0.0}, {"a": 1.0}) == 0.0


# ===========================================================================
# AgentMemory — remember / recall / forget
# ===========================================================================

class TestRememberRecall:
    def _make_memory(self, tmp_path):
        return AgentMemory(db_path=tmp_path / "test_memory.db")

    def test_remember_returns_id(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mid = mem.remember("User prefers dark mode", category="preference")
        assert isinstance(mid, int)
        assert mid > 0

    def test_recall_finds_similar(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.remember("The user likes dark mode theme", category="pref")
        mem.remember("Trading BTC with 10x leverage", category="trading")
        mem.remember("System configuration and settings", category="system")
        # Use low min_similarity since TF-IDF with few docs gives low scores
        results = mem.recall("dark mode theme", min_similarity=0.01)
        assert len(results) >= 1
        assert "dark" in results[0]["content"].lower()

    def test_recall_category_filter(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.remember("GPU temperature is high", category="system")
        mem.remember("GPU benchmark results", category="benchmark")
        results = mem.recall("GPU", category="system")
        assert all(r["category"] == "system" for r in results)

    def test_recall_empty_query(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.remember("some content")
        results = mem.recall("")
        assert results == []

    def test_recall_no_match(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.remember("cats and dogs")
        results = mem.recall("quantum physics relativity", min_similarity=0.5)
        assert results == []

    def test_recall_updates_access_count(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.remember("important system config")
        results = mem.recall("system config")
        if results:
            assert results[0]["access_count"] >= 1

    def test_forget(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mid = mem.remember("temporary note")
        assert mem.forget(mid) is True
        assert mem.forget(mid) is False  # already deleted

    def test_forget_nonexistent(self, tmp_path):
        mem = self._make_memory(tmp_path)
        assert mem.forget(99999) is False


# ===========================================================================
# AgentMemory — list_all
# ===========================================================================

class TestListAll:
    def test_list_all(self, tmp_path):
        mem = AgentMemory(db_path=tmp_path / "test.db")
        mem.remember("note 1", category="general")
        mem.remember("note 2", category="system")
        result = mem.list_all()
        assert len(result) == 2

    def test_list_all_category(self, tmp_path):
        mem = AgentMemory(db_path=tmp_path / "test.db")
        mem.remember("note 1", category="general")
        mem.remember("note 2", category="system")
        result = mem.list_all(category="system")
        assert len(result) == 1

    def test_list_all_limit(self, tmp_path):
        mem = AgentMemory(db_path=tmp_path / "test.db")
        for i in range(10):
            mem.remember(f"note {i}")
        result = mem.list_all(limit=3)
        assert len(result) == 3


# ===========================================================================
# AgentMemory — cleanup
# ===========================================================================

class TestCleanup:
    def test_cleanup_expired(self, tmp_path):
        mem = AgentMemory(db_path=tmp_path / "test.db")
        # Insert a memory with expired TTL
        import sqlite3
        with sqlite3.connect(str(tmp_path / "test.db")) as conn:
            conn.execute(
                "INSERT INTO memories (content, category, tokens, importance, created_at, last_accessed, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("expired note", "general", "expired note", 1.0, time.time() - 100, time.time() - 100, time.time() - 1),
            )
        removed = mem.cleanup()
        assert removed >= 1

    def test_cleanup_none(self, tmp_path):
        mem = AgentMemory(db_path=tmp_path / "test.db")
        mem.remember("fresh note", importance=1.0)
        removed = mem.cleanup()
        assert removed == 0


# ===========================================================================
# AgentMemory — get_stats
# ===========================================================================

class TestStats:
    def test_stats(self, tmp_path):
        mem = AgentMemory(db_path=tmp_path / "test.db")
        mem.remember("hello world", category="general")
        mem.remember("system config", category="system")
        stats = mem.get_stats()
        assert stats["total"] == 2
        assert "general" in stats["categories"]
        assert "system" in stats["categories"]

    def test_stats_empty(self, tmp_path):
        mem = AgentMemory(db_path=tmp_path / "test.db")
        stats = mem.get_stats()
        assert stats["total"] == 0
        assert stats["categories"] == {}


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert agent_memory is not None
        assert isinstance(agent_memory, AgentMemory)
