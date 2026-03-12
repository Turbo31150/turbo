"""Tests for src/command_router.py — Natural language command routing.

Covers: Route, MatchResult, CommandRouter (register, unregister, match,
route, _keyword_score, get_routes, get_history, get_stats),
command_router singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.command_router import CommandRouter, Route, MatchResult, command_router


# ===========================================================================
# Route & MatchResult dataclasses
# ===========================================================================

class TestDataclasses:
    def test_route_defaults(self):
        import re
        r = Route(name="test", keywords=["a"], patterns=[re.compile("x")],
                  handler=lambda: None)
        assert r.category == "general"
        assert r.priority == 0
        assert r.call_count == 0

    def test_match_result(self):
        import re
        r = Route(name="t", keywords=[], patterns=[], handler=lambda: None)
        mr = MatchResult(route=r, score=0.8, matched_by="keyword")
        assert mr.score == 0.8
        assert mr.captures == {}


# ===========================================================================
# CommandRouter — register / unregister
# ===========================================================================

class TestRegister:
    def test_register(self):
        cr = CommandRouter()
        cr.register("greet", handler=lambda: "hi", keywords=["hello", "hi"])
        routes = cr.get_routes()
        assert len(routes) == 1
        assert routes[0]["name"] == "greet"
        assert routes[0]["keywords"] == ["hello", "hi"]

    def test_register_with_pattern(self):
        cr = CommandRouter()
        cr.register("timer", handler=lambda: None,
                     patterns=[r"set timer (?P<mins>\d+)"])
        routes = cr.get_routes()
        assert len(routes) == 1
        assert "set timer" in routes[0]["patterns"][0]

    def test_unregister(self):
        cr = CommandRouter()
        cr.register("tmp", handler=lambda: None)
        assert cr.unregister("tmp") is True
        assert cr.unregister("tmp") is False

    def test_unregister_nonexistent(self):
        cr = CommandRouter()
        assert cr.unregister("nope") is False


# ===========================================================================
# CommandRouter — match
# ===========================================================================

class TestMatch:
    def test_exact_match(self):
        cr = CommandRouter()
        cr.register("status", handler=lambda: None, keywords=["status"])
        results = cr.match("status")
        assert len(results) >= 1
        assert results[0].matched_by == "exact"
        assert results[0].score == 1.0

    def test_keyword_match(self):
        cr = CommandRouter()
        cr.register("cluster", handler=lambda: None,
                     keywords=["cluster", "health"])
        results = cr.match("check cluster health")
        assert len(results) >= 1
        assert results[0].matched_by == "keyword"
        assert results[0].score > 0.1

    def test_pattern_match_with_captures(self):
        cr = CommandRouter()
        cr.register("timer", handler=lambda: None,
                     patterns=[r"timer (?P<mins>\d+) minutes"])
        results = cr.match("set timer 5 minutes please")
        assert len(results) >= 1
        assert results[0].matched_by == "pattern"
        assert results[0].captures.get("mins") == "5"

    def test_no_match(self):
        cr = CommandRouter()
        cr.register("foo", handler=lambda: None, keywords=["xyz"])
        results = cr.match("completely unrelated text")
        assert len(results) == 0

    def test_top_n_limit(self):
        cr = CommandRouter()
        for i in range(5):
            cr.register(f"cmd{i}", handler=lambda: None,
                         keywords=[f"keyword{i}", "common"])
        results = cr.match("common keyword0 keyword1 keyword2", top_n=2)
        assert len(results) <= 2

    def test_priority_ordering(self):
        cr = CommandRouter()
        cr.register("low", handler=lambda: None,
                     patterns=[r"test"], priority=0)
        cr.register("high", handler=lambda: None,
                     patterns=[r"test"], priority=5)
        results = cr.match("test pattern")
        assert results[0].route.name == "high"


# ===========================================================================
# CommandRouter — route
# ===========================================================================

class TestRoute:
    def test_route_returns_best(self):
        cr = CommandRouter()
        cr.register("boot", handler=lambda: None, keywords=["boot", "status"])
        result = cr.route("boot status")
        assert result is not None
        assert result.route.name == "boot"
        assert result.route.call_count == 1

    def test_route_no_match(self):
        cr = CommandRouter()
        result = cr.route("gibberish text")
        assert result is None

    def test_route_below_threshold(self):
        cr = CommandRouter()
        cr.register("x", handler=lambda: None, keywords=["a", "b", "c", "d", "e"])
        # Only 1/5 keywords match = 0.16 score < 0.3 threshold
        result = cr.route("a")
        assert result is None

    def test_route_records_history(self):
        cr = CommandRouter()
        cr.register("demo", handler=lambda: None, keywords=["demo"])
        cr.route("demo")
        history = cr.get_history()
        assert len(history) == 1
        assert history[0]["route"] == "demo"


# ===========================================================================
# CommandRouter — keyword_score
# ===========================================================================

class TestKeywordScore:
    def test_empty_keywords(self):
        assert CommandRouter._keyword_score("hello", []) == 0.0

    def test_full_match(self):
        score = CommandRouter._keyword_score("hello world", ["hello", "world"])
        assert score == pytest.approx(0.8)

    def test_partial_match(self):
        score = CommandRouter._keyword_score("hello there", ["hello", "world"])
        assert 0.0 < score < 0.8


# ===========================================================================
# CommandRouter — stats
# ===========================================================================

class TestStats:
    def test_stats_empty(self):
        cr = CommandRouter()
        stats = cr.get_stats()
        assert stats["total_routes"] == 0
        assert stats["total_calls"] == 0
        assert stats["history_size"] == 0

    def test_stats_after_register(self):
        cr = CommandRouter()
        cr.register("a", handler=lambda: None, category="system")
        cr.register("b", handler=lambda: None, category="voice")
        stats = cr.get_stats()
        assert stats["total_routes"] == 2
        assert "system" in stats["categories"]
        assert "voice" in stats["categories"]


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert command_router is not None
        assert isinstance(command_router, CommandRouter)
