"""Tests for src/quality_gate.py — QualityGate, GateResult, GateConfig, get_gate."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers — build gate with mocked DB so tests run in isolation
# ---------------------------------------------------------------------------

def _make_gate(config=None):
    """Create a QualityGate with sqlite3 mocked out (no real DB access)."""
    with patch("src.quality_gate.sqlite3") as _mock_sql:
        _mock_sql.connect.return_value = MagicMock()
        from src.quality_gate import QualityGate, GateConfig
        cfg = config or GateConfig()
        gate = QualityGate(config=cfg)
    # Also patch _log so evaluate() never touches the DB
    gate._log = MagicMock()
    return gate


def _good_code_content():
    """Return content that passes all gates for a 'code' pattern."""
    return (
        "```python\n"
        "def fibonacci(n):\n"
        "    \"\"\"Return the n-th Fibonacci number.\"\"\"\n"
        "    if n <= 1:\n"
        "        return n\n"
        "    a, b = 0, 1\n"
        "    for _ in range(2, n + 1):\n"
        "        a, b = b, a + b\n"
        "    return b\n"
        "```\n"
        "\n"
        "This function computes fibonacci using iteration which is efficient.\n"
    )


# ═══════════════════════════════════════════════════════════════════════════
# GateConfig defaults
# ═══════════════════════════════════════════════════════════════════════════

class TestGateConfig:
    def test_default_min_content_length(self):
        from src.quality_gate import GateConfig
        cfg = GateConfig()
        assert cfg.min_content_length["code"] == 50
        assert cfg.min_content_length["simple"] == 3
        assert cfg.min_content_length["default"] == 15

    def test_default_max_latency(self):
        from src.quality_gate import GateConfig
        cfg = GateConfig()
        assert cfg.max_latency_ms["simple"] == 10000
        assert cfg.max_latency_ms["reasoning"] == 90000

    def test_default_min_relevance(self):
        from src.quality_gate import GateConfig
        cfg = GateConfig()
        assert cfg.min_relevance["code"] == 0.12
        assert cfg.min_relevance["simple"] == 0.05

    def test_default_overall_threshold(self):
        from src.quality_gate import GateConfig
        cfg = GateConfig()
        assert cfg.min_overall_score == 0.35
        assert cfg.max_error_keywords == 3


# ═══════════════════════════════════════════════════════════════════════════
# GateResult dataclass
# ═══════════════════════════════════════════════════════════════════════════

class TestGateResult:
    def test_gate_result_fields(self):
        from src.quality_gate import GateResult
        r = GateResult(
            passed=True, overall_score=0.85, gates={},
            failed_gates=[], suggestions=[], retry_recommended=False,
        )
        assert r.passed is True
        assert r.overall_score == 0.85
        assert r.suggested_node == ""

    def test_gate_result_suggested_node(self):
        from src.quality_gate import GateResult
        r = GateResult(
            passed=False, overall_score=0.2, gates={},
            failed_gates=["length"], suggestions=["too short"],
            retry_recommended=True, suggested_node="M1",
        )
        assert r.suggested_node == "M1"
        assert r.retry_recommended is True


# ═══════════════════════════════════════════════════════════════════════════
# Full evaluate() — pass / fail
# ═══════════════════════════════════════════════════════════════════════════

class TestEvaluatePassFail:
    def test_good_code_passes(self):
        gate = _make_gate()
        result = gate.evaluate(
            "code", "write a fibonacci function in python",
            _good_code_content(), latency_ms=2000,
        )
        assert result.passed is True
        assert result.overall_score >= 0.35
        assert len(result.failed_gates) <= 1

    def test_empty_content_fails(self):
        gate = _make_gate()
        result = gate.evaluate("code", "write code", "", latency_ms=100)
        assert result.passed is False
        assert "length" in result.failed_gates

    def test_simple_pattern_short_content_passes(self):
        gate = _make_gate()
        result = gate.evaluate("simple", "hi", "hello there!", latency_ms=100)
        assert result.passed is True

    def test_too_many_failed_gates_fails(self):
        """Even if overall_score is above threshold, >1 failed gate means fail."""
        gate = _make_gate()
        # Very short, irrelevant, hallucinatory content
        content = "sorry I'm an AI"
        result = gate.evaluate("code", "write fibonacci", content, latency_ms=100)
        assert result.passed is False
        assert len(result.failed_gates) >= 2


# ═══════════════════════════════════════════════════════════════════════════
# Individual gate checks
# ═══════════════════════════════════════════════════════════════════════════

class TestLengthGate:
    def test_content_above_min(self):
        gate = _make_gate()
        result = gate.evaluate("simple", "test", "some content here", latency_ms=0)
        assert result.gates["length"]["passed"] is True

    def test_content_below_min(self):
        gate = _make_gate()
        result = gate.evaluate("code", "test", "x", latency_ms=0)
        assert result.gates["length"]["passed"] is False
        assert "length" in result.failed_gates

    def test_unknown_pattern_uses_default(self):
        gate = _make_gate()
        # "unknown_xyz" not in min_content_length, should use "default" = 15
        result = gate.evaluate("unknown_xyz", "q", "a" * 20, latency_ms=0)
        assert result.gates["length"]["passed"] is True


class TestStructureGate:
    def test_code_block_boosts_score(self):
        gate = _make_gate()
        content = "Here is the code:\n```python\nprint('hi')\n```\nDone."
        result = gate.evaluate("code", "show code", content, latency_ms=0)
        assert result.gates["structure"]["score"] >= 0.5

    def test_single_line_low_structure(self):
        gate = _make_gate()
        content = "just a single line without formatting"
        result = gate.evaluate("analysis", "analyze", content, latency_ms=0)
        # base 0.3 with no bonus except maybe length — still passes >= 0.3
        assert result.gates["structure"]["score"] >= 0.3

    def test_list_items_boost(self):
        gate = _make_gate()
        content = "Results:\n- item one\n- item two\n- item three\n- four\n- five\n- six"
        result = gate.evaluate("analysis", "list things", content, latency_ms=0)
        assert result.gates["structure"]["score"] >= 0.5


class TestRelevanceGate:
    def test_high_overlap(self):
        gate = _make_gate()
        prompt = "write a fibonacci function in python"
        content = "Here is a fibonacci function written in python that works recursively."
        result = gate.evaluate("code", prompt, content, latency_ms=0)
        assert result.gates["relevance"]["score"] >= 0.3

    def test_zero_overlap(self):
        gate = _make_gate()
        prompt = "explain quantum computing"
        content = "The weather today is sunny and warm with no clouds."
        result = gate.evaluate("analysis", prompt, content, latency_ms=0)
        assert result.gates["relevance"]["score"] < 0.1

    def test_empty_prompt_returns_half(self):
        gate = _make_gate()
        # Empty prompt (no words >= 3 chars) => relevance defaults to 0.5
        result = gate.evaluate("simple", "hi", "hello world ok", latency_ms=0)
        assert result.gates["relevance"]["score"] == 0.5


class TestConfidenceGate:
    def test_clean_content_high_confidence(self):
        gate = _make_gate()
        content = "The function returns the sum of two integers correctly."
        result = gate.evaluate("simple", "test", content, latency_ms=0)
        assert result.gates["confidence"]["score"] >= 0.7

    def test_error_keywords_lower_confidence(self):
        gate = _make_gate()
        content = "error occurred: traceback exception failed to load"
        result = gate.evaluate("code", "test", content, latency_ms=0)
        assert result.gates["confidence"]["score"] < 0.5

    def test_hedging_lowers_confidence(self):
        gate = _make_gate()
        content = "I think this might be correct, perhaps it works, possibly yes"
        result = gate.evaluate("code", "test", content, latency_ms=0)
        assert result.gates["confidence"]["score"] < 0.7

    def test_apology_lowers_confidence(self):
        gate = _make_gate()
        content = "Sorry, I cannot help with that request at this time."
        result = gate.evaluate("simple", "test", content, latency_ms=0)
        assert result.gates["confidence"]["score"] < 0.7


class TestLatencyGate:
    def test_fast_response_passes(self):
        gate = _make_gate()
        result = gate.evaluate("simple", "test", "hello world test", latency_ms=500)
        assert result.gates["latency"]["passed"] is True

    def test_slow_response_fails(self):
        gate = _make_gate()
        result = gate.evaluate("simple", "test", "hello world test", latency_ms=20000)
        assert result.gates["latency"]["passed"] is False
        assert "latency" in result.failed_gates

    def test_zero_latency_always_passes(self):
        gate = _make_gate()
        result = gate.evaluate("simple", "test", "hello world test", latency_ms=0)
        assert result.gates["latency"]["passed"] is True
        assert result.gates["latency"]["score"] == 1.0


class TestHallucinationGate:
    def test_clean_content_passes(self):
        gate = _make_gate()
        content = "The algorithm runs in O(n) time complexity."
        result = gate.evaluate("code", "test algorithm", content, latency_ms=0)
        assert result.gates["hallucination"]["passed"] is True
        assert result.gates["hallucination"]["score"] >= 0.7

    def test_ai_self_reference_detected(self):
        gate = _make_gate()
        content = "As an AI, I cannot execute code. I'm a language model."
        result = gate.evaluate("code", "test", content, latency_ms=0)
        assert result.gates["hallucination"]["score"] < 1.0

    def test_lorem_ipsum_detected(self):
        gate = _make_gate()
        content = "The result is lorem ipsum dolor sit amet, consectetur."
        result = gate.evaluate("code", "test", content, latency_ms=0)
        assert result.gates["hallucination"]["score"] < 1.0

    def test_repetition_detected(self):
        gate = _make_gate()
        sentence = "This is a repeated sentence that appears many times"
        content = ". ".join([sentence] * 10)
        result = gate.evaluate("analysis", "test", content, latency_ms=0)
        assert result.gates["hallucination"]["score"] < 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Overall score weighting
# ═══════════════════════════════════════════════════════════════════════════

class TestOverallScore:
    def test_score_between_0_and_1(self):
        gate = _make_gate()
        result = gate.evaluate("code", "fibonacci python", _good_code_content(), latency_ms=1000)
        assert 0 <= result.overall_score <= 1.0

    def test_bad_content_low_score(self):
        gate = _make_gate()
        result = gate.evaluate("code", "fibonacci python", "x", latency_ms=0)
        assert result.overall_score < 0.5


# ═══════════════════════════════════════════════════════════════════════════
# Retry & node suggestions
# ═══════════════════════════════════════════════════════════════════════════

class TestRetryAndSuggestions:
    def test_failed_result_recommends_retry(self):
        gate = _make_gate()
        result = gate.evaluate("code", "write code", "", latency_ms=0)
        assert result.passed is False
        assert result.retry_recommended is True

    def test_latency_failure_suggests_m1(self):
        gate = _make_gate()
        result = gate.evaluate("simple", "test", "hello world test", latency_ms=999999)
        if not result.passed:
            assert result.suggested_node == "M1"

    def test_length_failure_from_ol1_suggests_m1(self):
        gate = _make_gate()
        result = gate.evaluate("code", "write code", "x", latency_ms=0, node="OL1")
        assert result.suggested_node == "M1"

    def test_passing_result_no_suggested_node(self):
        gate = _make_gate()
        result = gate.evaluate(
            "code", "write a fibonacci function in python",
            _good_code_content(), latency_ms=1000,
        )
        if result.passed:
            assert result.suggested_node == ""


# ═══════════════════════════════════════════════════════════════════════════
# Stats tracking
# ═══════════════════════════════════════════════════════════════════════════

class TestStats:
    def test_initial_stats(self):
        gate = _make_gate()
        stats = gate.get_stats()
        assert stats["evaluated"] == 0
        assert stats["passed"] == 0
        assert stats["failed"] == 0
        assert stats["pass_rate"] == 0.0

    def test_stats_after_evaluations(self):
        gate = _make_gate()
        gate.evaluate("code", "fibonacci python", _good_code_content(), latency_ms=1000)
        gate.evaluate("code", "write code", "", latency_ms=0)
        stats = gate.get_stats()
        assert stats["evaluated"] == 2
        assert stats["passed"] + stats["failed"] == 2

    def test_pass_rate_calculation(self):
        gate = _make_gate()
        for _ in range(3):
            gate.evaluate("simple", "hi", "hello world test", latency_ms=100)
        stats = gate.get_stats()
        assert stats["pass_rate"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# auto_tune_from_data
# ═══════════════════════════════════════════════════════════════════════════

class TestAutoTune:
    def test_auto_tune_relaxes_strict_gate(self):
        """When dispatch success rate > 80% but gate pass rate < 60%, auto_tune relaxes relevance."""
        gate = _make_gate()

        # Build mock DB with controlled data
        mock_db = MagicMock()

        # dispatch data: pattern "code" with 90% success rate
        dispatch_row = MagicMock()
        dispatch_row.__getitem__ = lambda self, k: {
            "pattern": "code", "total": 100, "dispatch_ok": 90,
            "avg_q": 0.85, "avg_lat": 5000,
        }[k]
        dispatch_row.__contains__ = lambda self, k: True

        # gate data: pattern "code" with 40% pass rate (too strict)
        gate_row = MagicMock()
        gate_row.__getitem__ = lambda self, k: {
            "pattern": "code", "n": 50, "passed": 20,
            "avg_score": 0.4,
        }[k]

        mock_db.execute.return_value.fetchall.side_effect = [
            [dispatch_row],  # first query: dispatch log
            [gate_row],      # second query: gate log
        ]
        mock_db.row_factory = None

        old_relevance = gate.config.min_relevance.get("code", 0.12)

        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            adjustments = gate.auto_tune_from_data(min_samples=5)

        # relevance should have been relaxed
        new_relevance = gate.config.min_relevance.get("code", old_relevance)
        assert new_relevance < old_relevance
        assert "code" in adjustments

    def test_auto_tune_raises_latency_threshold(self):
        """When avg latency > 90% of max, auto_tune raises the latency threshold."""
        gate = _make_gate()
        original_lat = gate.config.max_latency_ms.get("analysis", 60000)

        dispatch_row = MagicMock()
        dispatch_row.__getitem__ = lambda self, k: {
            "pattern": "analysis", "total": 50, "dispatch_ok": 40,
            "avg_q": 0.7, "avg_lat": original_lat * 0.95,  # 95% of max
        }[k]

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.side_effect = [
            [dispatch_row],
            [],  # no gate log data
        ]
        mock_db.row_factory = None

        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            adjustments = gate.auto_tune_from_data(min_samples=5)

        new_lat = gate.config.max_latency_ms.get("analysis", original_lat)
        assert new_lat > original_lat

    def test_auto_tune_db_error_returns_error_key(self):
        gate = _make_gate()
        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB locked")
            adjustments = gate.auto_tune_from_data()
        assert "error" in adjustments

    def test_auto_tune_no_data_returns_empty(self):
        gate = _make_gate()
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.side_effect = [[], []]
        mock_db.row_factory = None

        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            adjustments = gate.auto_tune_from_data(min_samples=10)
        assert adjustments == {}


# ═══════════════════════════════════════════════════════════════════════════
# get_gate singleton
# ═══════════════════════════════════════════════════════════════════════════

class TestGetGate:
    def test_get_gate_returns_quality_gate(self):
        with patch("src.quality_gate.sqlite3"):
            import src.quality_gate as qg_mod
            qg_mod._gate = None  # reset singleton
            gate = qg_mod.get_gate()
            assert isinstance(gate, qg_mod.QualityGate)

    def test_get_gate_singleton(self):
        with patch("src.quality_gate.sqlite3"):
            import src.quality_gate as qg_mod
            qg_mod._gate = None
            g1 = qg_mod.get_gate()
            g2 = qg_mod.get_gate()
            assert g1 is g2


# ═══════════════════════════════════════════════════════════════════════════
# get_gate_report with mocked DB
# ═══════════════════════════════════════════════════════════════════════════

class TestGateReport:
    def test_gate_report_with_data(self):
        gate = _make_gate()

        mock_db = MagicMock()
        mock_db.row_factory = None

        # Total count
        mock_db.execute.return_value.fetchone.return_value = (42,)

        # by_pattern rows
        pattern_row = MagicMock()
        pattern_row.__getitem__ = lambda self, k: {
            "pattern": "code", "n": 30, "ok": 25, "avg_score": 0.72,
        }[k]

        # common_failures rows
        failure_row = MagicMock()
        failure_row.__getitem__ = lambda self, k: {
            "failed_gates": "length,relevance", "n": 5,
        }[k]

        call_results = iter([
            MagicMock(fetchone=MagicMock(return_value=(42,))),      # COUNT(*)
            MagicMock(fetchall=MagicMock(return_value=[pattern_row])),  # by_pattern
            MagicMock(fetchall=MagicMock(return_value=[failure_row])),  # common_failures
        ])
        mock_db.execute = lambda q, *a: next(call_results)

        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            report = gate.get_gate_report()

        assert report["total_evaluated"] == 42
        assert len(report["by_pattern"]) == 1
        assert report["by_pattern"][0]["pattern"] == "code"
        assert len(report["common_failures"]) == 1

    def test_gate_report_db_error(self):
        gate = _make_gate()
        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("no db")
            report = gate.get_gate_report()
        assert report == {"total_evaluated": 0}
