"""Tests for src/log_aggregator.py — Centralized log management.

Covers: LogEntry, LogAggregator (log, query, get_sources, get_level_counts,
clear, get_stats), log_aggregator singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.log_aggregator import LogEntry, LogAggregator, log_aggregator


class TestLogEntry:
    def test_defaults(self):
        e = LogEntry(message="test")
        assert e.level == "info"
        assert e.source == "system"
        assert e.metadata == {}


class TestLog:
    def test_log(self):
        la = LogAggregator()
        la.log("hello", level="info", source="test")
        entries = la.query()
        assert len(entries) == 1
        assert entries[0]["message"] == "hello"

    def test_log_max_entries(self):
        la = LogAggregator(max_entries=5)
        for i in range(10):
            la.log(f"msg {i}")
        assert len(la.query(limit=100)) == 5


class TestQuery:
    def test_filter_by_level(self):
        la = LogAggregator()
        la.log("info msg", level="info")
        la.log("error msg", level="error")
        results = la.query(level="error")
        assert len(results) == 1
        assert results[0]["level"] == "error"

    def test_filter_by_source(self):
        la = LogAggregator()
        la.log("a", source="api")
        la.log("b", source="db")
        results = la.query(source="api")
        assert len(results) == 1

    def test_search_regex(self):
        la = LogAggregator()
        la.log("Connection failed to DB")
        la.log("User logged in")
        results = la.query(search="connection.*DB")
        assert len(results) == 1

    def test_search_case_insensitive(self):
        la = LogAggregator()
        la.log("ERROR occurred")
        results = la.query(search="error")
        assert len(results) == 1

    def test_limit(self):
        la = LogAggregator()
        for i in range(10):
            la.log(f"msg {i}")
        assert len(la.query(limit=3)) == 3


class TestGetSources:
    def test_sources(self):
        la = LogAggregator()
        la.log("a", source="api")
        la.log("b", source="db")
        sources = la.get_sources()
        assert "api" in sources
        assert "db" in sources


class TestGetLevelCounts:
    def test_counts(self):
        la = LogAggregator()
        la.log("a", level="info")
        la.log("b", level="info")
        la.log("c", level="error")
        counts = la.get_level_counts()
        assert counts["info"] == 2
        assert counts["error"] == 1


class TestClear:
    def test_clear_all(self):
        la = LogAggregator()
        la.log("a")
        la.log("b")
        cleared = la.clear()
        assert cleared == 2
        assert len(la.query()) == 0

    def test_clear_by_source(self):
        la = LogAggregator()
        la.log("a", source="api")
        la.log("b", source="db")
        cleared = la.clear(source="api")
        assert cleared == 1
        remaining = la.query()
        assert len(remaining) == 1
        assert remaining[0]["source"] == "db"


class TestStats:
    def test_stats(self):
        la = LogAggregator()
        la.log("a", level="info", source="api")
        la.log("b", level="error", source="db")
        stats = la.get_stats()
        assert stats["total_entries"] == 2
        assert stats["sources"] == 2
        assert stats["level_counts"]["info"] == 1
        assert stats["source_counts"]["api"] == 1


class TestSingleton:
    def test_exists(self):
        assert isinstance(log_aggregator, LogAggregator)
