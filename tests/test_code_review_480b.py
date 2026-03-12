"""Tests for src/code_review_480b.py — Code review pipeline via Ollama.

Covers: ReviewResult (has_issues, critical_count, format_report),
_parse_review (json extraction variants), review_code (fallback chain),
review_diff (no changes, with diff), REVIEW_MODELS, constants.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.code_review_480b import (
    ReviewResult, _parse_review, review_code, review_diff, dual_review,
    REVIEW_MODELS, REVIEW_SYSTEM, DIFF_REVIEW_SYSTEM,
)


# ===========================================================================
# Constants
# ===========================================================================

class TestConstants:
    def test_review_models_not_empty(self):
        assert len(REVIEW_MODELS) >= 1

    def test_review_models_format(self):
        for model, timeout in REVIEW_MODELS:
            assert isinstance(model, str)
            assert isinstance(timeout, (int, float))
            assert timeout > 0

    def test_review_system_prompt(self):
        assert "score" in REVIEW_SYSTEM
        assert "JSON" in REVIEW_SYSTEM

    def test_diff_review_system_prompt(self):
        assert "diff" in DIFF_REVIEW_SYSTEM.lower()
        assert "JSON" in DIFF_REVIEW_SYSTEM


# ===========================================================================
# ReviewResult
# ===========================================================================

class TestReviewResult:
    def test_no_issues(self):
        r = ReviewResult("m1", 95, "APPROVE", [], [], [], [], "ok", 100, "")
        assert r.has_issues is False
        assert r.critical_count == 0

    def test_has_bugs(self):
        r = ReviewResult("m1", 60, "NEEDS_WORK",
                         [{"severity": "major", "line": 10, "desc": "bug"}],
                         [], [], [], "bug", 200, "")
        assert r.has_issues is True
        assert r.critical_count == 0

    def test_has_security(self):
        r = ReviewResult("m1", 40, "REJECT", [],
                         [{"type": "sql_injection", "desc": "bad"}],
                         [], [], "security", 300, "")
        assert r.has_issues is True

    def test_critical_count(self):
        r = ReviewResult("m1", 20, "REJECT",
                         [{"severity": "critical", "desc": "a"},
                          {"severity": "critical", "desc": "b"},
                          {"severity": "major", "desc": "c"}],
                         [], [], [], "bad", 100, "")
        assert r.critical_count == 2

    def test_format_report_basic(self):
        r = ReviewResult("qwen3:14b", 85, "APPROVE", [], [], [], [],
                         "Code is clean.", 150, "")
        report = r.format_report()
        assert "qwen3:14b" in report
        assert "85/100" in report
        assert "APPROVE" in report
        assert "Code is clean." in report

    def test_format_report_with_bugs(self):
        r = ReviewResult("m1", 50, "NEEDS_WORK",
                         [{"severity": "critical", "line": 5, "desc": "null deref"}],
                         [], [], [], "", 100, "")
        report = r.format_report()
        assert "BUGS" in report
        assert "CRITICAL" in report
        assert "L5" in report

    def test_format_report_with_security(self):
        r = ReviewResult("m1", 30, "REJECT", [],
                         [{"type": "XSS", "desc": "unescaped", "fix": "escape it"}],
                         [], [], "", 100, "")
        report = r.format_report()
        assert "SECURITE" in report
        assert "XSS" in report
        assert "Fix:" in report

    def test_format_report_with_perf_and_style(self):
        r = ReviewResult("m1", 70, "APPROVE", [], [],
                         [{"desc": "slow loop"}],
                         [{"desc": "naming convention"}],
                         "", 100, "")
        report = r.format_report()
        assert "PERFORMANCE" in report
        assert "STYLE" in report


# ===========================================================================
# _parse_review
# ===========================================================================

class TestParseReview:
    def test_valid_json(self):
        raw = json.dumps({
            "score": 90, "verdict": "APPROVE", "bugs": [],
            "security": [], "performance": [], "style": [],
            "summary": "Good code",
        })
        r = _parse_review(raw, "test_model", 500)
        assert r.score == 90
        assert r.verdict == "APPROVE"
        assert r.summary == "Good code"
        assert r.model == "test_model"
        assert r.latency_ms == 500

    def test_json_in_code_block(self):
        raw = '```json\n{"score": 80, "verdict": "NEEDS_WORK", "bugs": [], "security": [], "performance": [], "style": [], "summary": "OK"}\n```'
        r = _parse_review(raw, "m1", 100)
        assert r.score == 80
        assert r.verdict == "NEEDS_WORK"

    def test_json_in_generic_code_block(self):
        raw = '```\n{"score": 75, "verdict": "APPROVE"}\n```'
        r = _parse_review(raw, "m1", 100)
        assert r.score == 75

    def test_json_with_surrounding_text(self):
        raw = 'Here is my review:\n{"score": 65, "verdict": "NEEDS_WORK", "summary": "Issues found"}\nEnd of review.'
        r = _parse_review(raw, "m1", 100)
        assert r.score == 65

    def test_invalid_json(self):
        raw = "This is not JSON at all."
        r = _parse_review(raw, "m1", 100)
        assert r.verdict == "PARSE_ERROR"
        assert r.score == 50

    def test_partial_json_defaults(self):
        raw = '{"score": 88}'
        r = _parse_review(raw, "m1", 100)
        assert r.score == 88
        assert r.verdict == "UNKNOWN"
        assert r.bugs == []
        assert r.security == []

    def test_improvements_field_maps_to_performance(self):
        raw = json.dumps({"score": 70, "improvements": [{"desc": "cache it"}]})
        r = _parse_review(raw, "m1", 100)
        assert len(r.performance) == 1
        assert r.performance[0]["desc"] == "cache it"

    def test_changes_analysis_maps_to_summary(self):
        raw = json.dumps({"score": 85, "changes_analysis": "Minor changes"})
        r = _parse_review(raw, "m1", 100)
        assert r.summary == "Minor changes"


# ===========================================================================
# review_code
# ===========================================================================

class TestReviewCode:
    @pytest.mark.asyncio
    async def test_success(self):
        response = json.dumps({"score": 90, "verdict": "APPROVE", "summary": "Good"})
        with patch("src.code_review_480b._query_ollama", new_callable=AsyncMock,
                   return_value=(response, 500)):
            r = await review_code("def foo(): pass")
        assert r.score == 90
        assert r.verdict == "APPROVE"

    @pytest.mark.asyncio
    async def test_with_context(self):
        response = json.dumps({"score": 85, "verdict": "APPROVE"})
        with patch("src.code_review_480b._query_ollama", new_callable=AsyncMock,
                   return_value=(response, 300)) as mock_q:
            await review_code("def bar(): pass", context="File: test.py")
        # Context should be in the prompt
        call_args = mock_q.call_args[0][0]
        assert "File: test.py" in call_args

    @pytest.mark.asyncio
    async def test_all_models_fail(self):
        import httpx
        with patch("src.code_review_480b._query_ollama", new_callable=AsyncMock,
                   side_effect=httpx.ConnectError("connection refused")):
            r = await review_code("broken code")
        assert r.model == "FAILED"
        assert r.verdict == "ERROR"
        assert r.score == 0

    @pytest.mark.asyncio
    async def test_custom_models(self):
        response = json.dumps({"score": 75, "verdict": "APPROVE"})
        with patch("src.code_review_480b._query_ollama", new_callable=AsyncMock,
                   return_value=(response, 200)):
            r = await review_code("x = 1", models=[("custom:model", 30.0)])
        assert r.score == 75


# ===========================================================================
# review_diff
# ===========================================================================

class TestReviewDiff:
    @pytest.mark.asyncio
    async def test_with_explicit_diff(self):
        response = json.dumps({"score": 80, "verdict": "APPROVE", "summary": "OK diff"})
        with patch("src.code_review_480b._query_ollama", new_callable=AsyncMock,
                   return_value=(response, 400)):
            r = await review_diff(diff_text="--- a/f.py\n+++ b/f.py\n+new line")
        assert r.score == 80

    @pytest.mark.asyncio
    async def test_no_changes(self):
        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=mock_result):
            r = await review_diff()
        assert r.verdict == "NO_CHANGES"
        assert r.score == 100

    @pytest.mark.asyncio
    async def test_all_models_fail(self):
        import httpx
        with patch("src.code_review_480b._query_ollama", new_callable=AsyncMock,
                   side_effect=httpx.ConnectError("fail")):
            r = await review_diff(diff_text="some diff text")
        assert r.verdict == "ERROR"


# ===========================================================================
# dual_review
# ===========================================================================

class TestDualReview:
    @pytest.mark.asyncio
    async def test_returns_two_results(self):
        response = json.dumps({"score": 88, "verdict": "APPROVE"})
        with patch("src.code_review_480b._query_ollama", new_callable=AsyncMock,
                   return_value=(response, 300)):
            r1, r2 = await dual_review("def foo(): pass")
        assert r1.score == 88
        assert r2.score == 88

    @pytest.mark.asyncio
    async def test_with_context(self):
        response = json.dumps({"score": 75, "verdict": "NEEDS_WORK"})
        with patch("src.code_review_480b._query_ollama", new_callable=AsyncMock,
                   return_value=(response, 200)) as mock_q:
            await dual_review("x=1", context="Module: utils")
        call_args = mock_q.call_args[0][0]
        assert "Module: utils" in call_args
