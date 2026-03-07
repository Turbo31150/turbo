"""Tests for src/conversation_store.py — Persistent conversation history.

Covers: ConversationStore (create, add_turn, get_conversation,
list_conversations, search_turns, get_node_history, get_stats, cleanup),
conversation_store singleton.
Uses tmp_path for SQLite isolation.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.conversation_store import ConversationStore, conversation_store


# ===========================================================================
# ConversationStore — create & get
# ===========================================================================

class TestCreateGet:
    def test_create_conversation(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        conv_id = cs.create("Test chat")
        assert isinstance(conv_id, str)
        assert len(conv_id) == 8

    def test_get_conversation(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        conv_id = cs.create("Test chat", source="mcp")
        conv = cs.get_conversation(conv_id)
        assert conv is not None
        assert conv["title"] == "Test chat"
        assert conv["source"] == "mcp"
        assert conv["turns"] == []

    def test_get_nonexistent(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        assert cs.get_conversation("nope") is None


# ===========================================================================
# ConversationStore — add_turn
# ===========================================================================

class TestAddTurn:
    def test_add_turn(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        conv_id = cs.create("Chat")
        turn_id = cs.add_turn(conv_id, "M1", "Hello", "Hi there", latency_ms=100, tokens=20)
        assert isinstance(turn_id, int)
        conv = cs.get_conversation(conv_id)
        assert conv["turn_count"] == 1
        assert conv["total_tokens"] == 20
        assert len(conv["turns"]) == 1
        assert conv["turns"][0]["prompt"] == "Hello"
        assert conv["turns"][0]["response"] == "Hi there"

    def test_multiple_turns(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        conv_id = cs.create("Chat")
        cs.add_turn(conv_id, "M1", "Q1", "A1", tokens=10)
        cs.add_turn(conv_id, "OL1", "Q2", "A2", tokens=15)
        conv = cs.get_conversation(conv_id)
        assert conv["turn_count"] == 2
        assert conv["total_tokens"] == 25
        assert len(conv["turns"]) == 2

    def test_add_turn_with_metadata(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        conv_id = cs.create("Chat")
        cs.add_turn(conv_id, "M1", "Q", "A", metadata={"model": "qwen3-8b"})
        conv = cs.get_conversation(conv_id)
        import json
        meta = json.loads(conv["turns"][0]["metadata"])
        assert meta["model"] == "qwen3-8b"


# ===========================================================================
# ConversationStore — list & search
# ===========================================================================

class TestListSearch:
    def test_list_conversations(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        cs.create("Chat 1", source="chat")
        cs.create("Chat 2", source="mcp")
        all_convs = cs.list_conversations()
        assert len(all_convs) == 2

    def test_list_by_source(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        cs.create("Chat 1", source="chat")
        cs.create("Chat 2", source="mcp")
        mcp_convs = cs.list_conversations(source="mcp")
        assert len(mcp_convs) == 1
        assert mcp_convs[0]["source"] == "mcp"

    def test_search_turns(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        cid = cs.create("Chat")
        cs.add_turn(cid, "M1", "How to fix the GPU?", "Check the drivers")
        cs.add_turn(cid, "M1", "What is Python?", "A language")
        results = cs.search_turns("GPU")
        assert len(results) == 1
        assert "GPU" in results[0]["prompt"]

    def test_search_no_results(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        cid = cs.create("Chat")
        cs.add_turn(cid, "M1", "Hello", "Hi")
        results = cs.search_turns("nonexistent_xyz")
        assert results == []


# ===========================================================================
# ConversationStore — node history
# ===========================================================================

class TestNodeHistory:
    def test_get_node_history(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        cid = cs.create("Chat")
        cs.add_turn(cid, "M1", "Q1", "A1")
        cs.add_turn(cid, "OL1", "Q2", "A2")
        cs.add_turn(cid, "M1", "Q3", "A3")
        m1_history = cs.get_node_history("M1")
        assert len(m1_history) == 2
        ol1_history = cs.get_node_history("OL1")
        assert len(ol1_history) == 1


# ===========================================================================
# ConversationStore — stats
# ===========================================================================

class TestStats:
    def test_stats(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        cid = cs.create("Chat")
        cs.add_turn(cid, "M1", "Q", "A", tokens=50, latency_ms=100)
        stats = cs.get_stats()
        assert stats["total_conversations"] == 1
        assert stats["total_turns"] == 1
        assert stats["total_tokens"] == 50
        assert "M1" in stats["by_node"]

    def test_stats_empty(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        stats = cs.get_stats()
        assert stats["total_conversations"] == 0
        assert stats["total_turns"] == 0


# ===========================================================================
# ConversationStore — cleanup
# ===========================================================================

class TestCleanup:
    def test_cleanup_old(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        cid = cs.create("Old chat")
        # Manually set updated_at to 60 days ago
        import sqlite3
        old_time = time.time() - (60 * 86400)
        with sqlite3.connect(str(tmp_path / "conv.db")) as conn:
            conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (old_time, cid))
        removed = cs.cleanup(days=30)
        assert removed == 1

    def test_cleanup_nothing_old(self, tmp_path):
        cs = ConversationStore(db_path=tmp_path / "conv.db")
        cs.create("Fresh chat")
        removed = cs.cleanup(days=30)
        assert removed == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert conversation_store is not None
        assert isinstance(conversation_store, ConversationStore)
