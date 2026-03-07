"""Tests for src/pattern_lifecycle.py — Pattern lifecycle management.

Covers: PatternState/LifecycleEvent dataclasses, create/evolve/deprecate,
merge, suggest_actions, health_report, lifecycle_history.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pattern_lifecycle import PatternLifecycle, PatternState, LifecycleEvent, get_lifecycle


def _create_lifecycle_db(db_path: str, patterns: list[dict] | None = None, logs: list[dict] | None = None):
    db = sqlite3.connect(db_path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_patterns (
            pattern_id TEXT, agent_id TEXT, pattern_type TEXT UNIQUE,
            strategy TEXT DEFAULT 'single', model_primary TEXT DEFAULT 'qwen3-8b',
            model_fallbacks TEXT DEFAULT ''
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_dispatch_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classified_type TEXT, node TEXT,
            success INTEGER DEFAULT 1, quality_score REAL DEFAULT 0.5,
            latency_ms REAL DEFAULT 500, strategy TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS pattern_lifecycle_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT, pattern TEXT,
            detail TEXT, old_value TEXT, new_value TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    if patterns:
        for p in patterns:
            db.execute(
                "INSERT INTO agent_patterns (pattern_id, agent_id, pattern_type, strategy, model_primary) VALUES (?, ?, ?, ?, ?)",
                (p.get("id", f"PAT_{p['type'].upper()}"), p.get("agent", f"agent-{p['type']}"),
                 p["type"], p.get("strategy", "single"), p.get("model", "qwen3-8b")),
            )
    if logs:
        for l in logs:
            db.execute(
                "INSERT INTO agent_dispatch_log (classified_type, node, success, quality_score, latency_ms) VALUES (?, ?, ?, ?, ?)",
                (l.get("type"), l.get("node", "M1"), l.get("success", 1),
                 l.get("quality", 0.5), l.get("latency", 500)),
            )
    db.commit()
    db.close()


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_pattern_state(self):
        ps = PatternState("code", "agent-code", "qwen3-8b", "single",
                          "active", 100, 0.95, 0.8, 500, "", "")
        assert ps.status == "active"
        assert ps.total_calls == 100

    def test_lifecycle_event(self):
        e = LifecycleEvent("create", "code", "New pattern")
        assert e.event_type == "create"
        assert e.old_value == ""


# ===========================================================================
# Get all patterns
# ===========================================================================

class TestGetAllPatterns:
    def test_empty_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path)
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            patterns = lc.get_all_patterns()
        assert patterns == []

    def test_with_patterns(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path,
            patterns=[{"type": "code"}, {"type": "math"}],
            logs=[{"type": "code", "success": 1, "quality": 0.8} for _ in range(5)],
        )
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            patterns = lc.get_all_patterns()
        assert len(patterns) == 2
        code_pat = next(p for p in patterns if p.pattern_type == "code")
        assert code_pat.status == "active"
        assert code_pat.total_calls == 5

    def test_new_status(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path, patterns=[{"type": "new_pattern"}])
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            patterns = lc.get_all_patterns()
        assert patterns[0].status == "new"

    def test_degraded_status(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path,
            patterns=[{"type": "bad"}],
            logs=[{"type": "bad", "success": 0, "quality": 0.1} for _ in range(10)],
        )
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            patterns = lc.get_all_patterns()
        assert patterns[0].status == "degraded"


# ===========================================================================
# Create pattern
# ===========================================================================

class TestCreatePattern:
    def test_create_new(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path)
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            result = lc.create_pattern("new_type", model="qwen3-8b")
        assert result is True

        db = sqlite3.connect(db_path)
        count = db.execute("SELECT COUNT(*) FROM agent_patterns WHERE pattern_type='new_type'").fetchone()[0]
        db.close()
        assert count == 1

    def test_create_duplicate(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path, patterns=[{"type": "existing"}])
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            result = lc.create_pattern("existing")
        assert result is False

    def test_create_auto_agent_id(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path)
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            lc.create_pattern("nlp_task")
        db = sqlite3.connect(db_path)
        row = db.execute("SELECT agent_id FROM agent_patterns WHERE pattern_type='nlp_task'").fetchone()
        db.close()
        assert row[0] == "agent-nlp_task"

    def test_create_logs_event(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path)
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            lc.create_pattern("test_type")
        assert len(lc._events) == 1
        assert lc._events[0].event_type == "create"


# ===========================================================================
# Evolve pattern
# ===========================================================================

class TestEvolvePattern:
    def test_evolve_model(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path, patterns=[{"type": "code", "model": "qwen3:1.7b"}])
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            result = lc.evolve_pattern("code", model="qwen3-8b")
        assert result is True
        db = sqlite3.connect(db_path)
        model = db.execute("SELECT model_primary FROM agent_patterns WHERE pattern_type='code'").fetchone()[0]
        db.close()
        assert model == "qwen3-8b"

    def test_evolve_strategy(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path, patterns=[{"type": "code", "strategy": "single"}])
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            result = lc.evolve_pattern("code", strategy="race")
        assert result is True

    def test_evolve_nothing(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path, patterns=[{"type": "code"}])
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            result = lc.evolve_pattern("code")
        assert result is False


# ===========================================================================
# Deprecate pattern
# ===========================================================================

class TestDeprecatePattern:
    def test_deprecate_existing(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path, patterns=[{"type": "old_pattern"}])
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            result = lc.deprecate_pattern("old_pattern")
        assert result is True
        db = sqlite3.connect(db_path)
        count = db.execute("SELECT COUNT(*) FROM agent_patterns WHERE pattern_type='old_pattern'").fetchone()[0]
        db.close()
        assert count == 0

    def test_deprecate_nonexistent(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path)
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            result = lc.deprecate_pattern("nonexistent")
        assert result is False


# ===========================================================================
# Merge patterns
# ===========================================================================

class TestMergePatterns:
    def test_merge(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path, patterns=[{"type": "source"}, {"type": "target"}])
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            result = lc.merge_patterns("source", "target")
        assert result is True
        db = sqlite3.connect(db_path)
        count = db.execute("SELECT COUNT(*) FROM agent_patterns WHERE pattern_type='source'").fetchone()[0]
        target = db.execute("SELECT COUNT(*) FROM agent_patterns WHERE pattern_type='target'").fetchone()[0]
        db.close()
        assert count == 0  # Source removed
        assert target == 1  # Target kept


# ===========================================================================
# Suggest actions
# ===========================================================================

class TestSuggestActions:
    def test_no_actions_healthy(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path,
            patterns=[{"type": "code"}],
            logs=[{"type": "code", "success": 1, "quality": 0.9} for _ in range(10)],
        )
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            actions = lc.suggest_actions()
        deprecate = [a for a in actions if a["action"] == "deprecate" and a["pattern"] == "code"]
        assert len(deprecate) == 0

    def test_suggest_deprecate_unused(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path, patterns=[{"type": "discovered-test"}])
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            actions = lc.suggest_actions()
        deprecate = [a for a in actions if a["action"] == "deprecate"]
        assert len(deprecate) >= 1

    def test_actions_sorted_by_priority(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path,
            patterns=[{"type": "discovered-a"}, {"type": "discovered-b"}],
        )
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            actions = lc.suggest_actions()
        if len(actions) >= 2:
            priorities = [a["priority"] for a in actions]
            assert priorities == sorted(priorities)


# ===========================================================================
# Health report
# ===========================================================================

class TestHealthReport:
    def test_report_structure(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path,
            patterns=[{"type": "code"}, {"type": "math"}],
            logs=[{"type": "code", "success": 1, "quality": 0.8} for _ in range(5)],
        )
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            report = lc.health_report()
        assert "total_patterns" in report
        assert "status_distribution" in report
        assert "total_dispatches" in report
        assert "top_patterns" in report
        assert "degraded_patterns" in report
        assert report["total_patterns"] == 2

    def test_report_empty(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path)
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            report = lc.health_report()
        assert report["total_patterns"] == 0


# ===========================================================================
# Lifecycle history
# ===========================================================================

class TestLifecycleHistory:
    def test_history_empty(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path)
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            history = lc.get_lifecycle_history()
        assert history == []

    def test_history_with_events(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path, patterns=[{"type": "test_pattern"}])
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            lc.create_pattern("new_one")
            history = lc.get_lifecycle_history()
        assert len(history) >= 1

    def test_history_filter_by_pattern(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path)
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            lc.create_pattern("alpha")
            lc.create_pattern("beta")
            history = lc.get_lifecycle_history(pattern="alpha")
        assert all(h["pattern"] == "alpha" for h in history)


# ===========================================================================
# Event log
# ===========================================================================

class TestEventLog:
    def test_events_capped(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path)
        with patch("src.pattern_lifecycle.DB_PATH", db_path):
            lc = PatternLifecycle()
            for i in range(600):
                lc._log_event("test", f"p{i}", "detail")
        assert len(lc._events) == 500


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_get_lifecycle(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_lifecycle_db(db_path)
        import src.pattern_lifecycle as mod
        old = mod._lifecycle
        try:
            mod._lifecycle = None
            with patch("src.pattern_lifecycle.DB_PATH", db_path):
                lc = get_lifecycle()
            assert isinstance(lc, PatternLifecycle)
        finally:
            mod._lifecycle = old
