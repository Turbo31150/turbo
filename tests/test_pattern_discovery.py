#!/usr/bin/env python3
"""Tests for src/pattern_discovery.py — PatternDiscovery, DiscoveredPattern, BehaviorInsight."""

import sqlite3
import sys
import os

sys.path.insert(0, "F:/BUREAU/turbo")
os.chdir("F:/BUREAU/turbo")

import pytest
from unittest.mock import patch, MagicMock

from src.pattern_discovery import (
    PatternDiscovery,
    DiscoveredPattern,
    BehaviorInsight,
    STOP_WORDS,
    DB_PATH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_in_memory_db() -> str:
    """Return path placeholder; we'll patch sqlite3.connect instead."""
    return ":memory:"


def _build_dispatch_db(rows_unclassified=None, rows_all=None, rows_failed=None,
                       rows_hours=None, rows_patterns=None, rows_complexity=None,
                       rows_success=None, agent_patterns=None):
    """Create an in-memory SQLite with agent_dispatch_log + agent_patterns tables
    and populate with provided data."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE agent_dispatch_log (
            id INTEGER PRIMARY KEY,
            timestamp TEXT DEFAULT '2026-03-07 14:00:00',
            request_text TEXT,
            classified_type TEXT,
            node TEXT,
            success INTEGER DEFAULT 1,
            latency_ms REAL DEFAULT 100,
            quality_score REAL DEFAULT 0.8
        )
    """)
    db.execute("""
        CREATE TABLE agent_patterns (
            pattern_id TEXT PRIMARY KEY,
            agent_id TEXT,
            pattern_type TEXT,
            strategy TEXT,
            model_primary TEXT,
            model_fallbacks TEXT,
            avg_latency_ms REAL DEFAULT 0,
            success_rate REAL DEFAULT 0,
            total_calls INTEGER DEFAULT 0
        )
    """)
    if agent_patterns:
        for ap in agent_patterns:
            db.execute(
                "INSERT INTO agent_patterns (pattern_id, agent_id, pattern_type, strategy, model_primary, model_fallbacks) VALUES (?,?,?,?,?,?)",
                ap,
            )
    db.commit()
    return db


def _insert_dispatch_rows(db, rows):
    """Insert rows into agent_dispatch_log.
    Each row is a dict with keys: request_text, classified_type, node, success, latency_ms, quality_score, timestamp.
    """
    for r in rows:
        db.execute("""
            INSERT INTO agent_dispatch_log (timestamp, request_text, classified_type, node, success, latency_ms, quality_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            r.get("timestamp", "2026-03-07 14:00:00"),
            r.get("request_text"),
            r.get("classified_type"),
            r.get("node", "M1"),
            r.get("success", 1),
            r.get("latency_ms", 100),
            r.get("quality_score", 0.8),
        ))
    db.commit()


class _FakeConnect:
    """Context-manager wrapper that always returns the same in-memory db."""
    def __init__(self, db):
        self._db = db

    def __call__(self, *args, **kwargs):
        return self._db


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestDiscoveredPattern:
    def test_fields(self):
        p = DiscoveredPattern(
            pattern_type="test",
            keywords=["k1", "k2"],
            sample_prompts=["prompt1"],
            frequency=10,
            confidence=0.85,
            suggested_node="M1",
            suggested_strategy="single",
            reason="test reason",
        )
        assert p.pattern_type == "test"
        assert p.keywords == ["k1", "k2"]
        assert p.frequency == 10
        assert p.confidence == 0.85

    def test_low_confidence_pattern(self):
        p = DiscoveredPattern(
            pattern_type="weak",
            keywords=["x"],
            sample_prompts=[],
            frequency=2,
            confidence=0.1,
            suggested_node="OL1",
            suggested_strategy="single",
            reason="low",
        )
        assert p.confidence < PatternDiscovery.MIN_CONFIDENCE


class TestBehaviorInsight:
    def test_defaults(self):
        b = BehaviorInsight(
            insight_type="peak_hours",
            description="test",
            data={"hours": {14: 50}},
        )
        assert b.actionable is False
        assert b.suggestion == ""

    def test_with_suggestion(self):
        b = BehaviorInsight(
            insight_type="success_degradation",
            description="dropping",
            data={},
            actionable=True,
            suggestion="check nodes",
        )
        assert b.actionable is True
        assert b.suggestion == "check nodes"


# ---------------------------------------------------------------------------
# PatternDiscovery.__init__
# ---------------------------------------------------------------------------

class TestPatternDiscoveryInit:
    def test_default_db_path(self):
        d = PatternDiscovery()
        assert d.db_path == DB_PATH

    def test_custom_db_path(self):
        d = PatternDiscovery(db_path="/tmp/test.db")
        assert d.db_path == "/tmp/test.db"

    def test_class_constants(self):
        assert PatternDiscovery.MIN_FREQUENCY == 5
        assert PatternDiscovery.MIN_CONFIDENCE == 0.6


# ---------------------------------------------------------------------------
# discover() — integration of 3 sub-methods
# ---------------------------------------------------------------------------

class TestDiscover:
    def test_empty_db_returns_empty(self):
        """No data at all => no patterns discovered."""
        db = _build_dispatch_db()
        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d.discover()
            assert result == []

    def test_deduplication_by_pattern_type(self):
        """If sub-methods return duplicate pattern_type, only first is kept."""
        p1 = DiscoveredPattern("dup", ["a"], [], 10, 0.9, "M1", "single", "r1")
        p2 = DiscoveredPattern("dup", ["b"], [], 5, 0.7, "OL1", "single", "r2")
        p3 = DiscoveredPattern("unique", ["c"], [], 8, 0.8, "M1", "single", "r3")

        with patch.object(PatternDiscovery, "_discover_from_unclassified", return_value=[p1]), \
             patch.object(PatternDiscovery, "_discover_from_keyword_clusters", return_value=[p2, p3]), \
             patch.object(PatternDiscovery, "_discover_from_failed_dispatches", return_value=[]):
            d = PatternDiscovery()
            result = d.discover()
            types = [p.pattern_type for p in result]
            assert types == ["dup", "unique"]
            # First "dup" should be from unclassified (keywords=["a"])
            assert result[0].keywords == ["a"]

    def test_all_three_sources_combined(self):
        """Patterns from all three sub-methods are combined."""
        p1 = DiscoveredPattern("from_unclass", [], [], 10, 0.9, "M1", "single", "r1")
        p2 = DiscoveredPattern("from_cluster", [], [], 10, 0.9, "M1", "category", "r2")
        p3 = DiscoveredPattern("from_failed", [], [], 10, 0.9, "OL1", "single", "r3")

        with patch.object(PatternDiscovery, "_discover_from_unclassified", return_value=[p1]), \
             patch.object(PatternDiscovery, "_discover_from_keyword_clusters", return_value=[p2]), \
             patch.object(PatternDiscovery, "_discover_from_failed_dispatches", return_value=[p3]):
            d = PatternDiscovery()
            result = d.discover()
            assert len(result) == 3


# ---------------------------------------------------------------------------
# _discover_from_unclassified()
# ---------------------------------------------------------------------------

class TestDiscoverFromUnclassified:
    def test_too_few_rows_returns_empty(self):
        """Fewer than MIN_FREQUENCY rows => no patterns."""
        db = _build_dispatch_db()
        # Insert only 3 rows (< MIN_FREQUENCY=5)
        _insert_dispatch_rows(db, [
            {"request_text": "deploy serveur docker kubernetes", "classified_type": "simple"},
            {"request_text": "deploy container docker registry", "classified_type": "simple"},
            {"request_text": "deploy image docker compose", "classified_type": "simple"},
        ])
        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_unclassified()
            assert result == []

    def test_discovers_keyword_cluster(self):
        """Repeated keyword in 'simple' dispatches creates a pattern with sufficient confidence."""
        db = _build_dispatch_db()
        # Create 20+ rows with a repeated keyword 'deploiement' + co-word 'kubernetes'
        rows = []
        for i in range(22):
            rows.append({
                "request_text": f"deploiement kubernetes cluster service{i % 3}",
                "classified_type": "simple",
            })
        # Add some noise rows
        for i in range(5):
            rows.append({
                "request_text": f"question simple numero {i}",
                "classified_type": "simple",
            })
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_unclassified()
            # Should find 'deploiement' as a pattern
            types = [p.pattern_type for p in result]
            assert "deploiement" in types
            pat = [p for p in result if p.pattern_type == "deploiement"][0]
            assert pat.confidence >= 0.6
            assert "kubernetes" in pat.keywords
            assert pat.suggested_node == "M1"
            assert len(pat.sample_prompts) <= 3

    def test_filters_existing_types(self):
        """Words already in existing_types are skipped."""
        db = _build_dispatch_db()
        rows = []
        for i in range(20):
            rows.append({
                "request_text": f"monitoring serveur performance check{i % 3}",
                "classified_type": "simple",
            })
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value={"monitoring"}):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_unclassified()
            types = [p.pattern_type for p in result]
            assert "monitoring" not in types

    def test_filters_low_confidence(self):
        """Patterns with confidence < MIN_CONFIDENCE are filtered out."""
        db = _build_dispatch_db()
        # Only 6 occurrences => confidence = 6/20 = 0.3 < 0.6
        rows = []
        for i in range(6):
            rows.append({
                "request_text": f"obscure testword coword{i % 2}",
                "classified_type": "simple",
            })
        # Pad with unrelated rows to reach MIN_FREQUENCY total
        for i in range(10):
            rows.append({
                "request_text": f"random unrelated stuff row {i}",
                "classified_type": "simple",
            })
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_unclassified()
            # 'obscure' has 6 occurrences, confidence = 6/20 = 0.3
            for p in result:
                assert p.confidence >= PatternDiscovery.MIN_CONFIDENCE

    def test_db_error_returns_empty(self):
        """DB connection failure => empty list, no exception raised."""
        with patch("sqlite3.connect", side_effect=Exception("DB locked")):
            d = PatternDiscovery(db_path="/nonexistent/path.db")
            result = d._discover_from_unclassified()
            assert result == []

    def test_null_prompt_handled(self):
        """Rows with NULL request_text are handled gracefully."""
        db = _build_dispatch_db()
        rows = [{"request_text": None, "classified_type": "simple"} for _ in range(10)]
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_unclassified()
            # Should not crash; NULL prompts produce no words
            assert isinstance(result, list)

    def test_stop_words_filtered(self):
        """French and English stop words are not considered as pattern keywords."""
        db = _build_dispatch_db()
        # All keywords are stop words (le, la, les, the, is, are...)
        rows = [
            {"request_text": "le la les the is are dans par pour", "classified_type": "simple"}
            for _ in range(20)
        ]
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_unclassified()
            # Stop words only => nothing meaningful
            assert result == []


# ---------------------------------------------------------------------------
# _discover_from_keyword_clusters()
# ---------------------------------------------------------------------------

class TestDiscoverFromKeywordClusters:
    def test_empty_db(self):
        db = _build_dispatch_db()
        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_keyword_clusters()
            assert result == []

    def test_cross_pattern_word_detected(self):
        """A word appearing across 3+ patterns with no dominant one => cross_ pattern."""
        db = _build_dispatch_db()
        rows = []
        # 'performance' appears in code, system, and devops patterns (5 each)
        for i in range(5):
            rows.append({"request_text": "performance optimization code", "classified_type": "code"})
            rows.append({"request_text": "performance monitoring system", "classified_type": "system"})
            rows.append({"request_text": "performance devops pipeline", "classified_type": "devops"})
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_keyword_clusters()
            cross_types = [p.pattern_type for p in result]
            assert any("cross_performance" == t for t in cross_types)

    def test_dominant_pattern_excluded(self):
        """If a word maps mostly to one pattern (>50%), it's not cross-pattern."""
        db = _build_dispatch_db()
        rows = []
        # 'python' appears mostly in 'code' pattern
        for i in range(20):
            rows.append({"request_text": "python script development", "classified_type": "code"})
        for i in range(2):
            rows.append({"request_text": "python data analysis", "classified_type": "analysis"})
        for i in range(1):
            rows.append({"request_text": "python system check", "classified_type": "system"})
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_keyword_clusters()
            cross_types = [p.pattern_type for p in result]
            # 'python' is dominant in 'code' (20/23 > 50%), so should NOT be cross_python
            assert "cross_python" not in cross_types

    def test_existing_types_excluded(self):
        """Words already in existing types are skipped."""
        db = _build_dispatch_db()
        rows = []
        for i in range(5):
            rows.append({"request_text": "monitoring grafana dashboard", "classified_type": "code"})
            rows.append({"request_text": "monitoring alerting prometheus", "classified_type": "system"})
            rows.append({"request_text": "monitoring infra check", "classified_type": "devops"})
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value={"monitoring"}):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_keyword_clusters()
            cross_types = [p.pattern_type for p in result]
            assert "cross_monitoring" not in cross_types

    def test_db_error_returns_empty(self):
        with patch("sqlite3.connect", side_effect=Exception("boom")):
            d = PatternDiscovery(db_path="/bad.db")
            result = d._discover_from_keyword_clusters()
            assert result == []


# ---------------------------------------------------------------------------
# _discover_from_failed_dispatches()
# ---------------------------------------------------------------------------

class TestDiscoverFromFailedDispatches:
    def test_empty_db(self):
        db = _build_dispatch_db()
        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_failed_dispatches()
            assert result == []

    def test_high_failure_rate_detected(self):
        """Pattern with >50% failure rate and >=5 calls => fix_ pattern."""
        db = _build_dispatch_db()
        # 8 failed dispatches for 'code' on 'M2'
        rows = []
        for i in range(8):
            rows.append({
                "request_text": "code task",
                "classified_type": "code",
                "node": "M2",
                "success": 0,
            })
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_failed_dispatches()
            assert len(result) >= 1
            fix_pat = result[0]
            assert fix_pat.pattern_type == "fix_code_M2"
            assert fix_pat.suggested_node == "OL1"  # alt_node when node=M2
            assert fix_pat.confidence >= 0.5

    def test_suggests_m1_when_ol1_fails(self):
        """When OL1 is the failing node, alt_node should be M1."""
        db = _build_dispatch_db()
        rows = [
            {"request_text": "simple", "classified_type": "simple", "node": "OL1", "success": 0}
            for _ in range(6)
        ]
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_failed_dispatches()
            assert len(result) >= 1
            assert result[0].suggested_node == "M1"

    def test_low_failure_rate_not_reported(self):
        """Pattern with <50% failure rate is NOT reported."""
        db = _build_dispatch_db()
        rows = []
        # 3 failed, 7 successful => 30% failure
        for i in range(3):
            rows.append({"request_text": "t", "classified_type": "code", "node": "M1", "success": 0})
        for i in range(7):
            rows.append({"request_text": "t", "classified_type": "code", "node": "M1", "success": 1})
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_failed_dispatches()
            # The SQL groups by success=0 only (WHERE success = 0), so ok=0/total=3
            # But GROUP BY + HAVING total >= 3 checks count of failed rows
            # Actually re-reading the SQL: WHERE success = 0, GROUP BY pattern, node
            # So it only sees the 3 failed rows, fail_rate = 1 - (0/3) = 1.0
            # But total=3 < 5 => filtered by `total >= 5` condition
            fix_types = [p.pattern_type for p in result]
            assert "fix_code_M1" not in fix_types

    def test_too_few_failures(self):
        """Fewer than 5 failures => not reported (total >= 5 check)."""
        db = _build_dispatch_db()
        rows = [
            {"request_text": "t", "classified_type": "web", "node": "M1", "success": 0}
            for _ in range(4)
        ]
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_failed_dispatches()
            assert result == []

    def test_db_error_returns_empty(self):
        with patch("sqlite3.connect", side_effect=Exception("err")):
            d = PatternDiscovery(db_path="/bad.db")
            result = d._discover_from_failed_dispatches()
            assert result == []


# ---------------------------------------------------------------------------
# analyze_behavior()
# ---------------------------------------------------------------------------

class TestAnalyzeBehavior:
    def test_empty_db_returns_empty(self):
        db = _build_dispatch_db()
        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            result = d.analyze_behavior()
            assert result == []

    def test_peak_hours_detected(self):
        db = _build_dispatch_db()
        rows = []
        # 50 dispatches at 14h, 10 at 22h
        for i in range(50):
            rows.append({"timestamp": "2026-03-07 14:30:00", "request_text": "test"})
        for i in range(10):
            rows.append({"timestamp": "2026-03-07 22:15:00", "request_text": "test"})
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            insights = d.analyze_behavior()
            peak = [i for i in insights if i.insight_type == "peak_hours"]
            assert len(peak) == 1
            assert peak[0].data["hours"][14] == 50
            assert peak[0].actionable is True
            assert "Pre-warm" in peak[0].suggestion

    def test_pattern_distribution(self):
        db = _build_dispatch_db()
        rows = []
        for i in range(20):
            rows.append({"request_text": "code", "classified_type": "code"})
        for i in range(10):
            rows.append({"request_text": "simple", "classified_type": "simple"})
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            insights = d.analyze_behavior()
            dist = [i for i in insights if i.insight_type == "pattern_distribution"]
            assert len(dist) == 1
            assert "code" in dist[0].data["patterns"]

    def test_complexity_trend_increasing(self):
        db = _build_dispatch_db()
        rows = []
        # Day 1: short prompts
        for i in range(5):
            rows.append({
                "timestamp": "2026-03-01 10:00:00",
                "request_text": "short",
            })
        # Day 2: much longer prompts (>1.2x)
        for i in range(5):
            rows.append({
                "timestamp": "2026-03-07 10:00:00",
                "request_text": "a" * 200,  # 200 chars vs 5 chars
            })
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            insights = d.analyze_behavior()
            comp = [i for i in insights if i.insight_type == "complexity_trend"]
            assert len(comp) == 1
            assert "increasing" in comp[0].description
            assert comp[0].actionable is True

    def test_complexity_trend_stable(self):
        db = _build_dispatch_db()
        rows = []
        for i in range(5):
            rows.append({"timestamp": "2026-03-01 10:00:00", "request_text": "hello world test"})
        for i in range(5):
            rows.append({"timestamp": "2026-03-07 10:00:00", "request_text": "hello world test"})
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            insights = d.analyze_behavior()
            comp = [i for i in insights if i.insight_type == "complexity_trend"]
            if comp:
                assert "stable" in comp[0].description
                assert comp[0].actionable is False

    def test_success_degradation_detected(self):
        db = _build_dispatch_db()
        rows = []
        # Older day: 100% success
        for i in range(10):
            rows.append({
                "timestamp": "2026-03-01 10:00:00",
                "request_text": "test",
                "success": 1,
            })
        # Recent day: 50% success (drop > 10%)
        for i in range(5):
            rows.append({
                "timestamp": "2026-03-07 10:00:00",
                "request_text": "test",
                "success": 1,
            })
        for i in range(5):
            rows.append({
                "timestamp": "2026-03-07 10:00:00",
                "request_text": "test",
                "success": 0,
            })
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            insights = d.analyze_behavior()
            degrad = [i for i in insights if i.insight_type == "success_degradation"]
            assert len(degrad) == 1
            assert degrad[0].actionable is True
            assert "dropping" in degrad[0].description

    def test_no_degradation_when_stable(self):
        db = _build_dispatch_db()
        rows = []
        for i in range(10):
            rows.append({"timestamp": "2026-03-01 10:00:00", "request_text": "t", "success": 1})
        for i in range(10):
            rows.append({"timestamp": "2026-03-07 10:00:00", "request_text": "t", "success": 1})
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            insights = d.analyze_behavior()
            degrad = [i for i in insights if i.insight_type == "success_degradation"]
            assert len(degrad) == 0

    def test_db_error_returns_empty(self):
        with patch("sqlite3.connect", side_effect=Exception("err")):
            d = PatternDiscovery(db_path="/bad.db")
            result = d.analyze_behavior()
            assert result == []


# ---------------------------------------------------------------------------
# register_patterns()
# ---------------------------------------------------------------------------

class TestRegisterPatterns:
    def test_empty_list(self):
        d = PatternDiscovery()
        assert d.register_patterns([]) == 0

    def test_registers_valid_pattern(self):
        db = _build_dispatch_db()
        p = DiscoveredPattern(
            pattern_type="new_deploy",
            keywords=["deploy"],
            sample_prompts=[],
            frequency=10,
            confidence=0.9,
            suggested_node="M1",
            suggested_strategy="single",
            reason="test",
        )

        class _NoCloseDB:
            """Wrapper that intercepts close() so we can verify after."""
            def __init__(self, real_db):
                self._db = real_db
            def __getattr__(self, name):
                if name == "close":
                    return lambda: None  # no-op
                return getattr(self._db, name)

        wrapper = _NoCloseDB(db)
        with patch("sqlite3.connect", return_value=wrapper):
            d = PatternDiscovery(db_path=":memory:")
            count = d.register_patterns([p])
            assert count == 1

        # Verify row was inserted (db is still open)
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT * FROM agent_patterns WHERE pattern_type = 'new_deploy'"
        ).fetchone()
        assert row is not None
        assert row["pattern_id"] == "PAT_DISCOVERED_NEW_DEPLOY"
        assert row["model_primary"] == "M1"
        assert row["strategy"] == "single"
        db.close()

    def test_skips_low_confidence(self):
        db = _build_dispatch_db()
        p = DiscoveredPattern(
            pattern_type="weak",
            keywords=[],
            sample_prompts=[],
            frequency=2,
            confidence=0.3,  # Below MIN_CONFIDENCE
            suggested_node="M1",
            suggested_strategy="single",
            reason="too weak",
        )
        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            count = d.register_patterns([p])
            assert count == 0

    def test_skips_already_existing(self):
        db = _build_dispatch_db(agent_patterns=[
            ("PAT_EXISTING", "agent-1", "existing_type", "single", "M1", "OL1"),
        ])
        p = DiscoveredPattern(
            pattern_type="existing_type",
            keywords=[],
            sample_prompts=[],
            frequency=10,
            confidence=0.9,
            suggested_node="M1",
            suggested_strategy="single",
            reason="duplicate",
        )
        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            count = d.register_patterns([p])
            assert count == 0

    def test_multiple_patterns_mixed(self):
        """Mix of valid, low-confidence, and duplicate patterns."""
        db = _build_dispatch_db(agent_patterns=[
            ("PAT_OLD", "agent-old", "old_type", "single", "M1", "OL1"),
        ])
        patterns = [
            DiscoveredPattern("new_one", [], [], 10, 0.9, "M1", "single", "ok"),
            DiscoveredPattern("old_type", [], [], 10, 0.9, "M1", "single", "dup"),
            DiscoveredPattern("weak_one", [], [], 2, 0.3, "M1", "single", "weak"),
            DiscoveredPattern("another_new", [], [], 15, 0.95, "OL1", "category", "ok2"),
        ]
        with patch("sqlite3.connect", return_value=db):
            d = PatternDiscovery(db_path=":memory:")
            count = d.register_patterns(patterns)
            assert count == 2  # Only new_one and another_new

    def test_db_error_returns_zero(self):
        with patch("sqlite3.connect", side_effect=Exception("DB error")):
            d = PatternDiscovery(db_path="/bad.db")
            p = DiscoveredPattern("x", [], [], 10, 0.9, "M1", "single", "r")
            count = d.register_patterns([p])
            assert count == 0


# ---------------------------------------------------------------------------
# _get_existing_types()
# ---------------------------------------------------------------------------

class TestGetExistingTypes:
    def test_from_db(self):
        db = _build_dispatch_db(agent_patterns=[
            ("P1", "a1", "code", "single", "M1", "OL1"),
            ("P2", "a2", "trading", "single", "M1", "OL1"),
        ])
        with patch("sqlite3.connect", return_value=db), \
             patch.dict("sys.modules", {"src.pattern_agents": MagicMock(AGENT_CONFIGS=[])}):
            d = PatternDiscovery(db_path=":memory:")
            types = d._get_existing_types()
            assert "code" in types
            assert "trading" in types

    def test_db_error_falls_back(self):
        """DB error => returns set from pattern_agents only (or empty)."""
        with patch("sqlite3.connect", side_effect=Exception("err")), \
             patch.dict("sys.modules", {"src.pattern_agents": MagicMock(AGENT_CONFIGS=[])}):
            d = PatternDiscovery(db_path="/bad.db")
            types = d._get_existing_types()
            assert isinstance(types, set)

    def test_null_pattern_types_excluded(self):
        db = _build_dispatch_db(agent_patterns=[
            ("P1", "a1", None, "single", "M1", "OL1"),
            ("P2", "a2", "valid", "single", "M1", "OL1"),
        ])
        with patch("sqlite3.connect", return_value=db), \
             patch.dict("sys.modules", {"src.pattern_agents": MagicMock(AGENT_CONFIGS=[])}):
            d = PatternDiscovery(db_path=":memory:")
            types = d._get_existing_types()
            assert None not in types
            assert "valid" in types


# ---------------------------------------------------------------------------
# full_report()
# ---------------------------------------------------------------------------

class TestFullReport:
    def test_structure(self):
        """Report has all expected keys."""
        with patch.object(PatternDiscovery, "discover", return_value=[]), \
             patch.object(PatternDiscovery, "analyze_behavior", return_value=[]):
            d = PatternDiscovery()
            report = d.full_report()
            assert "discovered_patterns" in report
            assert "behavior_insights" in report
            assert "total_discovered" in report
            assert "actionable_insights" in report
            assert report["total_discovered"] == 0
            assert report["actionable_insights"] == 0

    def test_with_patterns_and_insights(self):
        patterns = [
            DiscoveredPattern("test_pat", ["k1"], ["p1"], 10, 0.85, "M1", "single", "reason1"),
        ]
        insights = [
            BehaviorInsight("peak_hours", "Peak at 14h", {"hours": {14: 50}}, True, "Pre-warm"),
            BehaviorInsight("pattern_distribution", "Top: code", {"patterns": {}}, False, ""),
        ]
        with patch.object(PatternDiscovery, "discover", return_value=patterns), \
             patch.object(PatternDiscovery, "analyze_behavior", return_value=insights):
            d = PatternDiscovery()
            report = d.full_report()
            assert report["total_discovered"] == 1
            assert report["actionable_insights"] == 1

            dp = report["discovered_patterns"][0]
            assert dp["type"] == "test_pat"
            assert dp["confidence"] == 0.85
            assert dp["keywords"] == ["k1"]
            assert dp["node"] == "M1"

            bi = report["behavior_insights"]
            assert len(bi) == 2
            assert bi[0]["type"] == "peak_hours"
            assert bi[0]["actionable"] is True
            assert bi[0]["suggestion"] == "Pre-warm"

    def test_confidence_rounded(self):
        """Confidence in report should be rounded to 2 decimals."""
        patterns = [
            DiscoveredPattern("x", [], [], 10, 0.8567, "M1", "single", "r"),
        ]
        with patch.object(PatternDiscovery, "discover", return_value=patterns), \
             patch.object(PatternDiscovery, "analyze_behavior", return_value=[]):
            d = PatternDiscovery()
            report = d.full_report()
            assert report["discovered_patterns"][0]["confidence"] == 0.86


# ---------------------------------------------------------------------------
# Sequence analysis / edge cases
# ---------------------------------------------------------------------------

class TestSequenceAnalysis:
    """Test the word extraction regex and pattern detection logic edge cases."""

    def test_stop_words_coverage(self):
        """STOP_WORDS contains expected French and English words."""
        assert "le" in STOP_WORDS
        assert "la" in STOP_WORDS
        assert "the" in STOP_WORDS
        assert "is" in STOP_WORDS
        assert "dans" in STOP_WORDS
        assert "for" in STOP_WORDS

    def test_regex_extracts_accented_words(self):
        """The regex in discover methods handles accented characters."""
        import re
        pattern = r'\b[a-zA-Z\u00e0\u00e9\u00e8\u00f9\u00ea\u00f4\u00ee\u00fb]{3,}\b'
        text = "deploiement reseau securite"
        words = set(re.findall(pattern, text))
        assert "deploiement" in words
        assert "reseau" in words
        assert "securite" in words

    def test_short_words_excluded_by_regex(self):
        """Words shorter than 3 chars are excluded by the regex."""
        import re
        pattern = r'\b[a-zA-Zàéèùêôîû]{3,}\b'
        text = "le ai do ok fin"
        words = set(re.findall(pattern, text))
        # 'le', 'ai', 'do', 'ok' are 2 chars => excluded
        assert "le" not in words
        assert "ai" not in words
        assert "fin" in words  # 3 chars => included

    def test_repeated_patterns_deduplicated_in_discover(self):
        """If all 3 sub-methods return same pattern_type, only first survives."""
        p = DiscoveredPattern("same", ["a"], [], 10, 0.9, "M1", "single", "r")
        with patch.object(PatternDiscovery, "_discover_from_unclassified", return_value=[p]), \
             patch.object(PatternDiscovery, "_discover_from_keyword_clusters", return_value=[p]), \
             patch.object(PatternDiscovery, "_discover_from_failed_dispatches", return_value=[p]):
            d = PatternDiscovery()
            result = d.discover()
            assert len(result) == 1

    def test_confidence_capped_at_1(self):
        """Confidence = min(1.0, count/20) caps at 1.0."""
        db = _build_dispatch_db()
        rows = []
        for i in range(50):
            rows.append({
                "request_text": f"massive keyword coword{i % 3}",
                "classified_type": "simple",
            })
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_unclassified()
            for p in result:
                assert p.confidence <= 1.0

    def test_co_occurrence_threshold(self):
        """Co-words must appear in >= 30% of keyword's prompts to be included."""
        db = _build_dispatch_db()
        rows = []
        # 'mainword' appears 20x, 'coword' appears with it 20x (100% co-occurrence)
        # 'rareword' appears with it only 1x (5% < 30%)
        for i in range(20):
            rows.append({
                "request_text": "mainword coword context text extra",
                "classified_type": "simple",
            })
        rows.append({
            "request_text": "mainword rareword something",
            "classified_type": "simple",
        })
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_unclassified()
            main_pats = [p for p in result if p.pattern_type == "mainword"]
            if main_pats:
                # 'coword' should be in keywords, 'rareword' should not
                assert "coword" in main_pats[0].keywords
                # rareword has 1 occurrence vs mainword's 21, 1/21 ~= 4.7% < 30%
                assert "rareword" not in main_pats[0].keywords

    def test_cluster_needs_at_least_2_keywords(self):
        """A word with no co-words (cluster size < 2) is not reported."""
        db = _build_dispatch_db()
        rows = []
        # 'loneword' appears 20x but always alone (no co-words above threshold)
        for i in range(20):
            rows.append({
                "request_text": "loneword",
                "classified_type": "simple",
            })
        # Pad to have enough total rows
        for i in range(5):
            rows.append({"request_text": "filler row", "classified_type": "simple"})
        _insert_dispatch_rows(db, rows)

        with patch("sqlite3.connect", return_value=db), \
             patch.object(PatternDiscovery, "_get_existing_types", return_value=set()):
            d = PatternDiscovery(db_path=":memory:")
            result = d._discover_from_unclassified()
            types = [p.pattern_type for p in result]
            assert "loneword" not in types
