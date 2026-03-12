"""Tests for src/pattern_benchmark_runner.py — Pattern agent benchmarking.

Covers: BENCHMARK_PROMPTS, BenchmarkResult, BenchmarkReport (success_rate,
summary), BenchmarkRunner (run_quick, run_full, run_stress,
run_node_comparison, _run_tests, _generate_recommendations, _save_report,
get_history).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

with patch("src.pattern_agents.PatternAgentRegistry"), \
     patch("src.pattern_agents.AGENT_CONFIGS", {}):
    from src.pattern_benchmark_runner import (
        BENCHMARK_PROMPTS, BenchmarkResult, BenchmarkReport, BenchmarkRunner,
    )


# ===========================================================================
# BENCHMARK_PROMPTS
# ===========================================================================

class TestBenchmarkPrompts:
    def test_has_10_patterns(self):
        assert len(BENCHMARK_PROMPTS) == 10

    def test_expected_patterns(self):
        expected = {"simple", "code", "math", "analysis", "system",
                    "creative", "security", "trading", "reasoning", "web"}
        assert expected == set(BENCHMARK_PROMPTS.keys())

    def test_three_prompts_per_pattern(self):
        for pattern, prompts in BENCHMARK_PROMPTS.items():
            assert len(prompts) == 3, f"{pattern} has {len(prompts)} prompts"

    def test_all_prompts_non_empty(self):
        for pattern, prompts in BENCHMARK_PROMPTS.items():
            for p in prompts:
                assert len(p) > 5, f"Empty prompt in {pattern}"


# ===========================================================================
# BenchmarkResult
# ===========================================================================

class TestBenchmarkResult:
    def test_creation(self):
        r = BenchmarkResult(
            pattern="code", prompt="test", node="M1", strategy="single",
            ok=True, latency_ms=500, tokens=100, quality=0.9,
            content_preview="def foo():",
        )
        assert r.pattern == "code"
        assert r.ok is True
        assert r.latency_ms == 500

    def test_failed_result(self):
        r = BenchmarkResult(
            pattern="math", prompt="calc", node="?", strategy="?",
            ok=False, latency_ms=0, tokens=0, quality=0,
            content_preview="timeout",
        )
        assert r.ok is False
        assert r.node == "?"


# ===========================================================================
# BenchmarkReport
# ===========================================================================

class TestBenchmarkReport:
    def _make_report(self, total=10, success=8):
        return BenchmarkReport(
            name="test",
            timestamp="2026-03-07 12:00:00",
            duration_ms=5000,
            total_tests=total,
            success_count=success,
            results=[],
            per_pattern={},
            per_node={},
            recommendations=[],
        )

    def test_success_rate(self):
        r = self._make_report(total=10, success=8)
        assert r.success_rate == 0.8

    def test_success_rate_zero_tests(self):
        r = self._make_report(total=0, success=0)
        assert r.success_rate == 0.0

    def test_summary_format(self):
        r = self._make_report(total=10, success=8)
        s = r.summary
        assert "test:" in s
        assert "8/10" in s
        assert "80%" in s
        assert "5000ms" in s

    def test_summary_with_recommendations(self):
        r = self._make_report()
        r.recommendations = ["Fix pattern X"]
        assert r.summary  # should not crash


# ===========================================================================
# BenchmarkRunner — _generate_recommendations
# ===========================================================================

class TestGenerateRecommendations:
    def setup_method(self):
        with patch("src.pattern_benchmark_runner.PatternAgentRegistry"):
            self.runner = BenchmarkRunner(db_path=":memory:")

    def test_no_issues(self):
        pattern_stats = {"code": {"success_rate": 0.9, "avg_latency_ms": 500}}
        node_stats = {"M1": {"success_rate": 0.95, "count": 10}}
        recs = self.runner._generate_recommendations(pattern_stats, node_stats)
        assert recs == []

    def test_low_success_rate_pattern(self):
        pattern_stats = {"code": {"success_rate": 0.3, "avg_latency_ms": 500}}
        node_stats = {}
        recs = self.runner._generate_recommendations(pattern_stats, node_stats)
        assert len(recs) == 1
        assert "code" in recs[0]
        assert "failing" in recs[0]

    def test_slow_pattern(self):
        pattern_stats = {"math": {"success_rate": 0.9, "avg_latency_ms": 35000}}
        node_stats = {}
        recs = self.runner._generate_recommendations(pattern_stats, node_stats)
        assert len(recs) == 1
        assert "slow" in recs[0]

    def test_unreliable_node(self):
        pattern_stats = {}
        node_stats = {"M3": {"success_rate": 0.2, "count": 5}}
        recs = self.runner._generate_recommendations(pattern_stats, node_stats)
        assert len(recs) == 1
        assert "M3" in recs[0]
        assert "unreliable" in recs[0]

    def test_unreliable_node_low_count_ignored(self):
        pattern_stats = {}
        node_stats = {"M3": {"success_rate": 0.0, "count": 2}}  # < 3 calls
        recs = self.runner._generate_recommendations(pattern_stats, node_stats)
        assert recs == []

    def test_multiple_recommendations(self):
        pattern_stats = {
            "code": {"success_rate": 0.1, "avg_latency_ms": 40000},
        }
        node_stats = {"OL1": {"success_rate": 0.1, "count": 10}}
        recs = self.runner._generate_recommendations(pattern_stats, node_stats)
        assert len(recs) == 3  # failing + slow + unreliable


# ===========================================================================
# BenchmarkRunner — _save_report
# ===========================================================================

class TestSaveReport:
    def test_save_success(self):
        with patch("src.pattern_benchmark_runner.PatternAgentRegistry"):
            runner = BenchmarkRunner(db_path=":memory:")

        report = BenchmarkReport(
            name="test", timestamp="2026-01-01", duration_ms=1000,
            total_tests=5, success_count=4, results=[], per_pattern={},
            per_node={}, recommendations=[],
        )
        with patch("src.pattern_benchmark_runner.sqlite3") as mock_sql:
            mock_db = MagicMock()
            mock_sql.connect.return_value = mock_db
            runner._save_report(report)
        mock_db.execute.assert_called()
        mock_db.commit.assert_called_once()

    def test_save_db_error_no_crash(self):
        with patch("src.pattern_benchmark_runner.PatternAgentRegistry"):
            runner = BenchmarkRunner(db_path=":memory:")

        report = BenchmarkReport(
            name="test", timestamp="now", duration_ms=0,
            total_tests=0, success_count=0, results=[], per_pattern={},
            per_node={}, recommendations=[],
        )
        with patch("src.pattern_benchmark_runner.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB gone")
            runner._save_report(report)  # should not raise


# ===========================================================================
# BenchmarkRunner — get_history
# ===========================================================================

class TestGetHistory:
    def test_empty(self):
        with patch("src.pattern_benchmark_runner.PatternAgentRegistry"):
            runner = BenchmarkRunner(db_path=":memory:")

        with patch("src.pattern_benchmark_runner.sqlite3") as mock_sql:
            mock_db = MagicMock()
            mock_db.execute.return_value.fetchall.return_value = []
            mock_sql.connect.return_value = mock_db
            history = runner.get_history()
        assert history == []

    def test_db_error_returns_empty(self):
        with patch("src.pattern_benchmark_runner.PatternAgentRegistry"):
            runner = BenchmarkRunner(db_path=":memory:")

        with patch("src.pattern_benchmark_runner.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB")
            history = runner.get_history()
        assert history == []


# ===========================================================================
# BenchmarkRunner — run_quick
# ===========================================================================

class TestRunQuick:
    @pytest.mark.asyncio
    async def test_runs_one_per_pattern(self):
        with patch("src.pattern_benchmark_runner.PatternAgentRegistry") as MockReg:
            runner = BenchmarkRunner(db_path=":memory:")

        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.node = "M1"
        mock_result.strategy = "single"
        mock_result.latency_ms = 500
        mock_result.tokens = 50
        mock_result.quality_score = 0.9
        mock_result.content = "test output"
        runner.registry.dispatch = AsyncMock(return_value=mock_result)

        with patch.object(runner, "_save_report"):
            report = await runner.run_quick()

        assert report.name == "quick"
        assert report.total_tests == 10  # 10 patterns × 1 prompt
        assert report.success_count == 10

    @pytest.mark.asyncio
    async def test_specific_patterns(self):
        with patch("src.pattern_benchmark_runner.PatternAgentRegistry"):
            runner = BenchmarkRunner(db_path=":memory:")

        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.node = "M1"
        mock_result.strategy = "single"
        mock_result.latency_ms = 100
        mock_result.tokens = 10
        mock_result.quality_score = 0.8
        mock_result.content = "ok"
        runner.registry.dispatch = AsyncMock(return_value=mock_result)

        with patch.object(runner, "_save_report"):
            report = await runner.run_quick(patterns=["code", "math"])

        assert report.total_tests == 2


# ===========================================================================
# BenchmarkRunner — run_full
# ===========================================================================

class TestRunFull:
    @pytest.mark.asyncio
    async def test_runs_all_prompts(self):
        with patch("src.pattern_benchmark_runner.PatternAgentRegistry"):
            runner = BenchmarkRunner(db_path=":memory:")

        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.node = "OL1"
        mock_result.strategy = "single"
        mock_result.latency_ms = 300
        mock_result.tokens = 20
        mock_result.quality_score = 0.7
        mock_result.content = "response"
        runner.registry.dispatch = AsyncMock(return_value=mock_result)

        with patch.object(runner, "_save_report"):
            report = await runner.run_full()

        assert report.name == "full"
        assert report.total_tests == 30  # 10 patterns × 3 prompts


# ===========================================================================
# BenchmarkRunner — run_stress
# ===========================================================================

class TestRunStress:
    @pytest.mark.asyncio
    async def test_repeated_tests(self):
        with patch("src.pattern_benchmark_runner.PatternAgentRegistry"):
            runner = BenchmarkRunner(db_path=":memory:")

        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.node = "M1"
        mock_result.strategy = "single"
        mock_result.latency_ms = 200
        mock_result.tokens = 15
        mock_result.quality_score = 0.85
        mock_result.content = "ok"
        runner.registry.dispatch = AsyncMock(return_value=mock_result)

        with patch.object(runner, "_save_report"):
            report = await runner.run_stress(parallel=2, repeat=2)

        assert report.name == "stress"
        assert report.total_tests == 20  # 10 patterns × 2 repeats


# ===========================================================================
# BenchmarkRunner — dispatch failure
# ===========================================================================

class TestDispatchFailure:
    @pytest.mark.asyncio
    async def test_exception_captured(self):
        with patch("src.pattern_benchmark_runner.PatternAgentRegistry"):
            runner = BenchmarkRunner(db_path=":memory:")

        runner.registry.dispatch = AsyncMock(side_effect=Exception("timeout"))

        with patch.object(runner, "_save_report"):
            report = await runner.run_quick(patterns=["code"])

        assert report.total_tests == 1
        assert report.success_count == 0
        assert report.results[0].ok is False
        assert "timeout" in report.results[0].content_preview


# ===========================================================================
# BenchmarkRunner — aggregation
# ===========================================================================

class TestAggregation:
    @pytest.mark.asyncio
    async def test_per_pattern_stats(self):
        with patch("src.pattern_benchmark_runner.PatternAgentRegistry"):
            runner = BenchmarkRunner(db_path=":memory:")

        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.node = "M1"
        mock_result.strategy = "single"
        mock_result.latency_ms = 400
        mock_result.tokens = 30
        mock_result.quality_score = 0.8
        mock_result.content = "code output"
        runner.registry.dispatch = AsyncMock(return_value=mock_result)

        with patch.object(runner, "_save_report"):
            report = await runner.run_quick(patterns=["code", "math"])

        assert "code" in report.per_pattern
        assert report.per_pattern["code"]["count"] == 1
        assert report.per_pattern["code"]["success_rate"] == 1.0
        assert "M1" in report.per_node
