"""Tests for src/agent_episodic_memory.py — Episodic + semantic memory.

Covers: episode storage/recall, semantic facts, keyword index, pattern/node memory,
learning from history, session summary, working context.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_episodic_memory import EpisodicMemory, Episode, SemanticFact, WorkingContext


@pytest.fixture
def mem(tmp_path):
    """EpisodicMemory with an isolated temp database."""
    db = str(tmp_path / "test_etoile.db")
    return EpisodicMemory(db_path=db)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_episode_defaults(self):
        ep = Episode("code", "M1", "abc123", "hello", True, 0.8, 500, "single", "2026-01-01")
        assert ep.relevance == 0.0

    def test_semantic_fact(self):
        f = SemanticFact("pattern_affinity", "code", "best_node", "M1", 0.9, "auto", "2026-01-01")
        assert f.confidence == 0.9

    def test_working_context_defaults(self):
        ctx = WorkingContext()
        assert ctx.dispatch_count == 0
        assert ctx.success_count == 0
        assert ctx.current_task == ""


# ===========================================================================
# Table creation
# ===========================================================================

class TestTableCreation:
    def test_tables_created(self, mem, tmp_path):
        import sqlite3
        db = sqlite3.connect(str(tmp_path / "test_etoile.db"))
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "agent_episodic_memory" in tables
        assert "agent_semantic_facts" in tables
        db.close()


# ===========================================================================
# Episode storage
# ===========================================================================

class TestEpisodeStorage:
    def test_store_episode(self, mem):
        mem.store_episode("code", "M1", "Write a parser", success=True, quality=0.9, latency_ms=500)
        assert len(mem._episodes) == 1
        assert mem._episodes[0].pattern == "code"
        assert mem._episodes[0].node == "M1"
        assert mem._episodes[0].success is True

    def test_store_multiple_episodes(self, mem):
        mem.store_episode("code", "M1", "Write a parser", success=True, quality=0.9)
        mem.store_episode("question", "OL1", "What is Python?", success=True, quality=0.7)
        mem.store_episode("math", "M1", "Calculate integral", success=False, quality=0.2)
        assert len(mem._episodes) == 3

    def test_newest_episode_first(self, mem):
        mem.store_episode("code", "M1", "First prompt")
        mem.store_episode("question", "OL1", "Second prompt")
        assert mem._episodes[0].pattern == "question"
        assert mem._episodes[1].pattern == "code"

    def test_max_episodes_limit(self, mem):
        mem.MAX_EPISODES = 10
        for i in range(15):
            mem.store_episode("code", "M1", f"Prompt {i}")
        assert len(mem._episodes) == 10

    def test_working_context_updated(self, mem):
        mem.store_episode("code", "M1", "Test", success=True)
        mem.store_episode("code", "M1", "Test2", success=False)
        assert mem.working.dispatch_count == 2
        assert mem.working.success_count == 1

    def test_prompt_preview_truncated(self, mem):
        long_prompt = "x" * 200
        mem.store_episode("code", "M1", long_prompt)
        assert len(mem._episodes[0].prompt_preview) == 100

    def test_prompt_hash_generated(self, mem):
        mem.store_episode("code", "M1", "Hello world")
        assert len(mem._episodes[0].prompt_hash) == 12

    def test_episode_persisted_to_db(self, mem, tmp_path):
        import sqlite3
        mem.store_episode("code", "M1", "Persistent test", success=True, quality=0.85)
        db = sqlite3.connect(str(tmp_path / "test_etoile.db"))
        count = db.execute("SELECT COUNT(*) FROM agent_episodic_memory").fetchone()[0]
        assert count == 1
        row = db.execute("SELECT * FROM agent_episodic_memory").fetchone()
        assert row[1] == "code"  # pattern
        assert row[2] == "M1"    # node
        db.close()


# ===========================================================================
# Episode recall
# ===========================================================================

class TestEpisodeRecall:
    def test_recall_by_keyword(self, mem):
        mem.store_episode("code", "M1", "Write a JSON parser in Python")
        mem.store_episode("question", "OL1", "What is the weather today")
        results = mem.recall("JSON parser")
        assert len(results) >= 1
        assert results[0].pattern == "code"

    def test_recall_empty_query(self, mem):
        mem.store_episode("code", "M1", "Write something")
        results = mem.recall("")
        assert results == []

    def test_recall_short_words_ignored(self, mem):
        mem.store_episode("code", "M1", "Do it now")
        # "do", "it" are < 3 chars, only "now" counts
        results = mem.recall("do it")
        assert results == []

    def test_recall_with_pattern_filter(self, mem):
        mem.store_episode("code", "M1", "Write function Python")
        mem.store_episode("question", "OL1", "What Python version")
        results = mem.recall("Python", pattern_filter="code")
        assert all(r.pattern == "code" for r in results)

    def test_recall_relevance_score(self, mem):
        mem.store_episode("code", "M1", "Parse JSON data from API endpoint")
        results = mem.recall("Parse JSON data")
        assert len(results) >= 1
        assert results[0].relevance > 0

    def test_recall_top_k_limit(self, mem):
        for i in range(20):
            mem.store_episode("code", "M1", f"Python function number {i}")
        results = mem.recall("Python function", top_k=3)
        assert len(results) <= 3

    def test_recall_no_match(self, mem):
        mem.store_episode("code", "M1", "Write Python code")
        results = mem.recall("xyzzy quantum entanglement")
        assert results == []


# ===========================================================================
# Semantic facts
# ===========================================================================

class TestSemanticFacts:
    def test_store_fact(self, mem):
        mem.store_fact("pattern_affinity", "code", "best_node", "M1", confidence=0.95)
        assert len(mem._facts) == 1
        fact = list(mem._facts.values())[0]
        assert fact.value == "M1"
        assert fact.confidence == 0.95

    def test_store_fact_upsert(self, mem):
        mem.store_fact("pattern_affinity", "code", "best_node", "M1", confidence=0.7)
        mem.store_fact("pattern_affinity", "code", "best_node", "OL1", confidence=0.9)
        assert len(mem._facts) == 1
        fact = list(mem._facts.values())[0]
        assert fact.value == "OL1"

    def test_get_facts_by_type(self, mem):
        mem.store_fact("pattern_affinity", "code", "best_node", "M1")
        mem.store_fact("node_capability", "M1", "status", "healthy")
        results = mem.get_facts(fact_type="pattern_affinity")
        assert len(results) == 1
        assert results[0].fact_type == "pattern_affinity"

    def test_get_facts_by_subject(self, mem):
        mem.store_fact("pattern_affinity", "code", "best_node", "M1")
        mem.store_fact("pattern_affinity", "math", "best_node", "M1")
        results = mem.get_facts(subject="code")
        assert len(results) == 1

    def test_get_facts_sorted_by_confidence(self, mem):
        mem.store_fact("test", "a", "p", "v1", confidence=0.5)
        mem.store_fact("test", "b", "p", "v2", confidence=0.9)
        mem.store_fact("test", "c", "p", "v3", confidence=0.7)
        facts = mem.get_facts(fact_type="test")
        confidences = [f.confidence for f in facts]
        assert confidences == sorted(confidences, reverse=True)

    def test_fact_persisted_to_db(self, mem, tmp_path):
        import sqlite3
        mem.store_fact("test", "sub", "pred", "val", confidence=0.8)
        db = sqlite3.connect(str(tmp_path / "test_etoile.db"))
        count = db.execute("SELECT COUNT(*) FROM agent_semantic_facts").fetchone()[0]
        assert count == 1
        db.close()


# ===========================================================================
# Node & Pattern memory
# ===========================================================================

class TestNodeMemory:
    def test_node_memory_basic(self, mem):
        mem.store_episode("code", "M1", "Test 1", success=True, quality=0.9, latency_ms=500)
        mem.store_episode("code", "M1", "Test 2", success=True, quality=0.8, latency_ms=300)
        mem.store_episode("code", "M1", "Test 3", success=False, quality=0.2, latency_ms=5000)
        info = mem.get_node_memory("M1")
        assert info["total_episodes"] == 3
        assert info["success_rate"] == pytest.approx(2/3)
        assert info["node"] == "M1"

    def test_node_memory_empty(self, mem):
        info = mem.get_node_memory("M1")
        assert info["total_episodes"] == 0
        assert info["success_rate"] == 0

    def test_node_memory_patterns(self, mem):
        mem.store_episode("code", "M1", "Code test")
        mem.store_episode("math", "M1", "Math test")
        info = mem.get_node_memory("M1")
        assert set(info["patterns"]) == {"code", "math"}


class TestPatternMemory:
    def test_pattern_memory_basic(self, mem):
        mem.store_episode("code", "M1", "Test 1", success=True)
        mem.store_episode("code", "OL1", "Test 2", success=True)
        mem.store_episode("code", "M1", "Test 3", success=False)
        info = mem.get_pattern_memory("code")
        assert info["total"] == 3
        assert info["success_rate"] == pytest.approx(2/3)

    def test_pattern_memory_best_node(self, mem):
        for _ in range(5):
            mem.store_episode("code", "M1", "test", success=True)
        for _ in range(2):
            mem.store_episode("code", "OL1", "test", success=True)
        mem.store_episode("code", "OL1", "test", success=False)
        info = mem.get_pattern_memory("code")
        assert info["best_node"] == "M1"

    def test_pattern_memory_empty(self, mem):
        info = mem.get_pattern_memory("nonexistent")
        assert info["total"] == 0


# ===========================================================================
# Learning from history
# ===========================================================================

class TestLearning:
    def test_learn_from_history(self, mem):
        for _ in range(10):
            mem.store_episode("code", "M1", "Python code test", success=True, quality=0.9)
        for _ in range(3):
            mem.store_episode("code", "OL1", "Python code test", success=False, quality=0.2)
        learned = mem.learn_from_history()
        assert len(learned) >= 1
        # Should learn that M1 is best for code
        code_facts = [l for l in learned if "code" in l["fact"]]
        assert len(code_facts) >= 1

    def test_learn_degraded_node(self, mem):
        for _ in range(15):
            mem.store_episode("code", "M3", "Test", success=False, quality=0.1)
        learned = mem.learn_from_history()
        degraded = [l for l in learned if "degraded" in l["fact"]]
        assert len(degraded) >= 1

    def test_learn_needs_minimum_data(self, mem):
        # Only 3 episodes, minimum is 5
        for _ in range(3):
            mem.store_episode("code", "M1", "Test", success=True)
        learned = mem.learn_from_history()
        code_facts = [l for l in learned if "code" in l["fact"]]
        assert len(code_facts) == 0  # Not enough data


# ===========================================================================
# Session summary
# ===========================================================================

class TestSessionSummary:
    def test_session_summary(self, mem):
        mem.store_episode("code", "M1", "Test", success=True)
        mem.store_episode("question", "OL1", "Test", success=True)
        mem.store_fact("test", "s", "p", "v")
        summary = mem.get_session_summary()
        assert summary["dispatches"] == 2
        assert summary["success_rate"] == 1.0
        assert summary["facts_total"] >= 1

    def test_session_summary_empty(self, mem):
        summary = mem.get_session_summary()
        assert summary["dispatches"] == 0
        assert summary["success_rate"] == 0


# ===========================================================================
# Keyword index
# ===========================================================================

class TestKeywordIndex:
    def test_index_built_on_store(self, mem):
        mem.store_episode("code", "M1", "Write Python function")
        assert "python" in mem._keyword_index
        assert "function" in mem._keyword_index

    def test_short_words_not_indexed(self, mem):
        mem.store_episode("code", "M1", "Do it now ok")
        assert "do" not in mem._keyword_index
        assert "it" not in mem._keyword_index
        assert "ok" not in mem._keyword_index
        assert "now" in mem._keyword_index

    def test_rebuild_index(self, mem):
        mem.store_episode("code", "M1", "Python parser")
        mem._build_index()
        assert "python" in mem._keyword_index


# ===========================================================================
# Persistence / reload
# ===========================================================================

class TestPersistence:
    def test_reload_from_db(self, tmp_path):
        db_path = str(tmp_path / "test_persist.db")
        mem1 = EpisodicMemory(db_path=db_path)
        mem1.store_episode("code", "M1", "Persistent test", success=True, quality=0.9)
        mem1.store_fact("test", "sub", "pred", "val")

        # Create new instance from same DB
        mem2 = EpisodicMemory(db_path=db_path)
        assert len(mem2._episodes) == 1
        assert mem2._episodes[0].pattern == "code"
        assert len(mem2._facts) == 1
