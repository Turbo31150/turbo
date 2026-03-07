"""Tests for src/session_manager.py — User session context with persistence.

Covers: SessionManager (create, get_context, touch, set_preference,
get_preference, record_command, set_active_conversation, set_preferred_node,
list_sessions, cleanup, delete, get_stats), session_manager singleton.
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

from src.session_manager import SessionManager, session_manager


# ===========================================================================
# SessionManager — create & get
# ===========================================================================

class TestCreateGet:
    def test_create(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sid = sm.create("electron")
        assert isinstance(sid, str)
        assert len(sid) == 8

    def test_get_context(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sid = sm.create("mcp")
        ctx = sm.get_context(sid)
        assert ctx is not None
        assert ctx["source"] == "mcp"
        assert ctx["preferences"] == {}
        assert ctx["last_commands"] == []

    def test_get_nonexistent(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        assert sm.get_context("nope") is None


# ===========================================================================
# SessionManager — preferences
# ===========================================================================

class TestPreferences:
    def test_set_and_get(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sid = sm.create()
        sm.set_preference(sid, "theme", "dark")
        assert sm.get_preference(sid, "theme") == "dark"

    def test_get_default(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sid = sm.create()
        assert sm.get_preference(sid, "missing", "fallback") == "fallback"

    def test_get_preference_nonexistent_session(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        assert sm.get_preference("nope", "key", "default") == "default"


# ===========================================================================
# SessionManager — commands
# ===========================================================================

class TestCommands:
    def test_record_command(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sid = sm.create()
        sm.record_command(sid, "/cluster-check")
        ctx = sm.get_context(sid)
        assert len(ctx["last_commands"]) == 1
        assert ctx["last_commands"][0]["cmd"] == "/cluster-check"

    def test_command_history_limit(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sid = sm.create()
        for i in range(25):
            sm.record_command(sid, f"/cmd{i}", max_history=10)
        ctx = sm.get_context(sid)
        assert len(ctx["last_commands"]) == 10


# ===========================================================================
# SessionManager — conversation & node
# ===========================================================================

class TestConversationNode:
    def test_set_active_conversation(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sid = sm.create()
        sm.set_active_conversation(sid, "conv123")
        ctx = sm.get_context(sid)
        assert ctx["active_conversation"] == "conv123"

    def test_set_preferred_node(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sid = sm.create()
        sm.set_preferred_node(sid, "M1")
        ctx = sm.get_context(sid)
        assert ctx["preferred_node"] == "M1"


# ===========================================================================
# SessionManager — list & cleanup
# ===========================================================================

class TestListCleanup:
    def test_list_sessions(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sm.create("electron")
        sm.create("mcp")
        sessions = sm.list_sessions()
        assert len(sessions) == 2

    def test_delete(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sid = sm.create()
        assert sm.delete(sid) is True
        assert sm.get_context(sid) is None

    def test_delete_nonexistent(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        assert sm.delete("nope") is False

    def test_cleanup(self, tmp_path):
        import sqlite3
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sid = sm.create()
        old_time = time.time() - (48 * 3600)
        with sqlite3.connect(str(tmp_path / "sessions.db")) as conn:
            conn.execute("UPDATE sessions SET last_active=? WHERE id=?", (old_time, sid))
        removed = sm.cleanup(inactive_hours=24)
        assert removed == 1


# ===========================================================================
# SessionManager — stats
# ===========================================================================

class TestStats:
    def test_stats(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        sm.create("electron")
        sm.create("mcp")
        stats = sm.get_stats()
        assert stats["total_sessions"] == 2
        assert "electron" in stats["by_source"]

    def test_stats_empty(self, tmp_path):
        sm = SessionManager(db_path=tmp_path / "sessions.db")
        stats = sm.get_stats()
        assert stats["total_sessions"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert session_manager is not None
        assert isinstance(session_manager, SessionManager)
