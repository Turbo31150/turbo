"""Tests for src/session_manager_v2.py — Advanced multi-session tracking.

Covers: Session, SessionManagerV2 (create, get, touch, close,
cleanup_expired, list_sessions, get_stats, persistence),
session_manager_v2 singleton. Uses tmp_path for JSON isolation.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.session_manager_v2 import Session, SessionManagerV2, session_manager_v2


# ===========================================================================
# Session dataclass
# ===========================================================================

class TestSession:
    def test_defaults(self):
        s = Session(session_id="abc", owner="user")
        assert s.status == "active"
        assert s.activity_count == 0
        assert s.timeout_s == 3600.0


# ===========================================================================
# SessionManagerV2 — create & get
# ===========================================================================

class TestCreateGet:
    def test_create(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        s = sm.create("turbo")
        assert s.owner == "turbo"
        assert s.status == "active"

    def test_get(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        s = sm.create("turbo")
        got = sm.get(s.session_id)
        assert got is not None
        assert got.owner == "turbo"

    def test_get_nonexistent(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        assert sm.get("nope") is None

    def test_create_with_metadata(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        s = sm.create("turbo", metadata={"mode": "voice"}, tags=["voice"])
        assert s.metadata["mode"] == "voice"
        assert "voice" in s.tags


# ===========================================================================
# SessionManagerV2 — touch
# ===========================================================================

class TestTouch:
    def test_touch(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        s = sm.create("turbo")
        assert sm.touch(s.session_id) is True
        got = sm.get(s.session_id)
        assert got.activity_count == 1

    def test_touch_nonexistent(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        assert sm.touch("nope") is False


# ===========================================================================
# SessionManagerV2 — close
# ===========================================================================

class TestClose:
    def test_close(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        s = sm.create("turbo")
        assert sm.close(s.session_id) is True
        assert sm.get(s.session_id).status == "closed"

    def test_close_nonexistent(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        assert sm.close("nope") is False

    def test_touch_closed(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        s = sm.create("turbo")
        sm.close(s.session_id)
        assert sm.touch(s.session_id) is False


# ===========================================================================
# SessionManagerV2 — cleanup_expired
# ===========================================================================

class TestCleanup:
    def test_cleanup(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        s = sm.create("turbo", timeout_s=0.01)
        time.sleep(0.02)
        count = sm.cleanup_expired()
        assert count == 1
        assert sm.get(s.session_id).status == "expired"


# ===========================================================================
# SessionManagerV2 — list_sessions
# ===========================================================================

class TestListSessions:
    def test_list_all(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        sm.create("alice")
        sm.create("bob")
        assert len(sm.list_sessions()) == 2

    def test_list_by_owner(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        sm.create("alice")
        sm.create("bob")
        assert len(sm.list_sessions(owner="alice")) == 1

    def test_list_by_status(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        s = sm.create("alice")
        sm.create("bob")
        sm.close(s.session_id)
        assert len(sm.list_sessions(status="closed")) == 1


# ===========================================================================
# SessionManagerV2 — persistence
# ===========================================================================

class TestPersistence:
    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "sessions.json"
        sm1 = SessionManagerV2(store_path=path)
        s = sm1.create("turbo", metadata={"test": True})
        sm2 = SessionManagerV2(store_path=path)
        got = sm2.get(s.session_id)
        assert got is not None
        assert got.owner == "turbo"


# ===========================================================================
# SessionManagerV2 — stats
# ===========================================================================

class TestStats:
    def test_stats(self, tmp_path):
        sm = SessionManagerV2(store_path=tmp_path / "s.json")
        sm.create("alice")
        s = sm.create("bob")
        sm.close(s.session_id)
        stats = sm.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["active"] == 1
        assert stats["closed"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert session_manager_v2 is not None
        assert isinstance(session_manager_v2, SessionManagerV2)
