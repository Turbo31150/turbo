"""Tests for src/audit_trail.py — Structured audit log.

Covers: AuditTrail (log, search, get_entry, get_stats, cleanup),
audit_trail singleton.
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

from src.audit_trail import AuditTrail, audit_trail


# ===========================================================================
# AuditTrail — log & get_entry
# ===========================================================================

class TestLogGet:
    def test_log(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        eid = at.log("mcp_call", "handle_lm_query", {"node": "M1"})
        assert isinstance(eid, str)
        assert len(eid) == 12

    def test_get_entry(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        eid = at.log("api", "test_action", {"key": "val"}, source="test")
        entry = at.get_entry(eid)
        assert entry is not None
        assert entry["action_type"] == "api"
        assert entry["action"] == "test_action"
        assert entry["details"]["key"] == "val"
        assert entry["success"] is True

    def test_get_entry_nonexistent(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        assert at.get_entry("nonexistent") is None

    def test_log_failure(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        eid = at.log("error", "crash", success=False, result="boom")
        entry = at.get_entry(eid)
        assert entry["success"] is False
        assert entry["result"] == "boom"


# ===========================================================================
# AuditTrail — search
# ===========================================================================

class TestSearch:
    def test_search_by_type(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        at.log("mcp_call", "a")
        at.log("api", "b")
        at.log("mcp_call", "c")
        results = at.search(action_type="mcp_call")
        assert len(results) == 2

    def test_search_by_source(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        at.log("api", "a", source="voice")
        at.log("api", "b", source="mcp")
        results = at.search(source="voice")
        assert len(results) == 1

    def test_search_by_query(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        at.log("api", "cluster_health", {"node": "M1"})
        at.log("api", "gpu_status")
        results = at.search(query="cluster")
        assert len(results) == 1

    def test_search_since(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        at.log("api", "old")
        # Force old timestamp via direct SQL
        import sqlite3
        with sqlite3.connect(str(tmp_path / "audit.db")) as conn:
            conn.execute("UPDATE audit_log SET ts = ? WHERE action = 'old'",
                         (time.time() - 7200,))
        at.log("api", "new")
        results = at.search(since=time.time() - 60)
        assert len(results) == 1

    def test_search_success_only(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        at.log("api", "ok", success=True)
        at.log("api", "fail", success=False)
        results = at.search(success_only=True)
        assert len(results) == 1

    def test_search_limit(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        for i in range(10):
            at.log("api", f"action_{i}")
        results = at.search(limit=3)
        assert len(results) == 3


# ===========================================================================
# AuditTrail — stats
# ===========================================================================

class TestStats:
    def test_stats_empty(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        stats = at.get_stats()
        assert stats["total_recent"] == 0
        assert stats["total_all"] == 0

    def test_stats_with_data(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        at.log("mcp_call", "a", source="voice", duration_ms=100)
        at.log("api", "b", source="mcp", duration_ms=200, success=False)
        stats = at.get_stats()
        assert stats["total_recent"] == 2
        assert stats["failures_recent"] == 1
        assert stats["avg_duration_ms"] == 150.0
        assert stats["by_type"]["mcp_call"] == 1
        assert stats["by_source"]["voice"] == 1


# ===========================================================================
# AuditTrail — cleanup
# ===========================================================================

class TestCleanup:
    def test_cleanup(self, tmp_path):
        at = AuditTrail(db_path=tmp_path / "audit.db")
        at.log("api", "old")
        import sqlite3
        with sqlite3.connect(str(tmp_path / "audit.db")) as conn:
            conn.execute("UPDATE audit_log SET ts = ?",
                         (time.time() - 40 * 86400,))
        at.log("api", "recent")
        removed = at.cleanup(days=30)
        assert removed == 1
        assert len(at.search()) == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert audit_trail is not None
        assert isinstance(audit_trail, AuditTrail)
