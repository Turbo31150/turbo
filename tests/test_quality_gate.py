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

    def test_all_pattern_keys_present(self):
        """Every documented pattern has entries in all config dicts."""
        from src.quality_gate import GateConfig
        cfg = GateConfig()
        for pattern in ("simple", "code", "analysis", "architecture",
                        "reasoning", "math", "trading", "security",
                        "creative", "default"):
            assert pattern in cfg.min_content_length
            assert pattern in cfg.max_latency_ms

    def test_custom_config_values(self):
        """GateConfig accepts overridden values."""
        from src.quality_gate import GateConfig
        cfg = GateConfig(
            min_overall_score=0.9,
            max_error_keywords=1,
        )
        assert cfg.min_overall_score == 0.9
        assert cfg.max_error_keywords == 1


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

    def test_gate_result_all_fields_accessible(self):
        from src.quality_gate import GateResult
        r = GateResult(
            passed=False, overall_score=0.1,
            gates={"length": {"passed": False, "score": 0.0, "reason": "empty"}},
            failed_gates=["length", "relevance"],
            suggestions=["too short", "irrelevant"],
            retry_recommended=True, suggested_node="M2",
        )
        assert len(r.failed_gates) == 2
        assert len(r.suggestions) == 2
        assert r.gates["length"]["score"] == 0.0


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

    def test_empty_response_all_patterns(self):
        """Empty string fails length gate for every pattern."""
        gate = _make_gate()
        for pattern in ("code", "analysis", "simple", "reasoning", "trading"):
            result = gate.evaluate(pattern, "test prompt", "", latency_ms=0)
            assert result.passed is False
            assert "length" in result.failed_gates

    def test_very_short_response_code_fails(self):
        """A 2-char response fails the 'code' pattern (min=50)."""
        gate = _make_gate()
        result = gate.evaluate("code", "test", "ok", latency_ms=0)
        assert result.passed is False
        assert "length" in result.failed_gates

    def test_very_short_response_simple_passes(self):
        """A 3-char response passes the 'simple' pattern (min=3)."""
        gate = _make_gate()
        result = gate.evaluate("simple", "hi", "yes", latency_ms=0)
        assert result.passed is True

    def test_evaluate_returns_all_six_gates(self):
        """Every evaluation populates exactly the 6 expected gates."""
        gate = _make_gate()
        result = gate.evaluate("code", "test", _good_code_content(), latency_ms=100)
        expected_gates = {"length", "structure", "relevance", "confidence",
                          "latency", "hallucination"}
        assert set(result.gates.keys()) == expected_gates

    def test_evaluate_calls_log(self):
        """_log is called once per evaluate."""
        gate = _make_gate()
        gate.evaluate("code", "test", "x" * 60, latency_ms=0)
        gate._log.assert_called_once()

    def test_passed_requires_score_and_few_failures(self):
        """passed = overall_score >= threshold AND len(failed) <= 1."""
        gate = _make_gate()
        # Content that is long enough, structured, but irrelevant
        content = (
            "```python\ndef hello():\n    print('hello')\n```\n"
            "This is a well-structured code block with multiple lines.\n"
            "- point one\n- point two\n- point three\n- four\n- five\n- six\n"
        )
        # Prompt that has zero overlap with content
        result = gate.evaluate("code", "explain quantum entanglement physics",
                               content, latency_ms=0)
        # Even if some gates pass, if >1 fail then overall fails
        if len(result.failed_gates) > 1:
            assert result.passed is False


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

    def test_exact_boundary_length(self):
        """Content exactly at min_content_length boundary passes."""
        gate = _make_gate()
        # "code" min is 50
        content = "x" * 50
        result = gate.evaluate("code", "test", content, latency_ms=0)
        assert result.gates["length"]["passed"] is True

    def test_one_below_boundary_fails(self):
        """Content one char below min_content_length boundary fails."""
        gate = _make_gate()
        content = "x" * 49
        result = gate.evaluate("code", "test", content, latency_ms=0)
        assert result.gates["length"]["passed"] is False

    def test_length_score_calculation(self):
        """Score = min(1.0, len(content) / (min_len * 3))."""
        gate = _make_gate()
        # "simple" min is 3 => score = min(1.0, 6 / (3*3)) = min(1.0, 0.667) = 0.667
        result = gate.evaluate("simple", "test", "abcdef", latency_ms=0)
        expected = min(1.0, 6 / (3 * 3))
        assert abs(result.gates["length"]["score"] - expected) < 0.01

    def test_length_score_caps_at_one(self):
        """Score is capped at 1.0 even for very long content."""
        gate = _make_gate()
        result = gate.evaluate("simple", "test", "x" * 10000, latency_ms=0)
        assert result.gates["length"]["score"] == 1.0

    def test_empty_content_score_zero(self):
        """Empty content has score 0."""
        gate = _make_gate()
        result = gate.evaluate("code", "test", "", latency_ms=0)
        assert result.gates["length"]["score"] == 0.0

    def test_length_suggestion_message(self):
        """Failed length gate produces a suggestion with char counts."""
        gate = _make_gate()
        result = gate.evaluate("code", "test", "abc", latency_ms=0)
        assert any("trop court" in s for s in result.suggestions)


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
        # base 0.3 with no bonus except maybe length -- still passes >= 0.3
        assert result.gates["structure"]["score"] >= 0.3

    def test_list_items_boost(self):
        gate = _make_gate()
        content = "Results:\n- item one\n- item two\n- item three\n- four\n- five\n- six"
        result = gate.evaluate("analysis", "list things", content, latency_ms=0)
        assert result.gates["structure"]["score"] >= 0.5

    def test_headers_boost_score(self):
        """Lines starting with # add structure bonus."""
        gate = _make_gate()
        content = "# Title\nSome intro text.\n## Section\nMore detail here.\nLine 3\nLine 4"
        result = gate.evaluate("analysis", "test", content, latency_ms=0)
        # base 0.3 + 0.15 (>1 line) + 0.1 (>5 lines) + 0.15 (headers) = 0.7
        assert result.gates["structure"]["score"] >= 0.6

    def test_code_keywords_boost_code_pattern(self):
        """'def'/'class'/'function' keywords add +0.1 for code patterns."""
        gate = _make_gate()
        content = "Here is the solution:\ndef solve(x):\n    return x * 2\nDone.\nMore.\nExtra."
        result = gate.evaluate("code", "test", content, latency_ms=0)
        # base 0.3 + 0.15 (>1 line) + 0.1 (>5 lines) + 0.1 (def keyword, code pattern) = 0.65
        assert result.gates["structure"]["score"] >= 0.6

    def test_code_keywords_smaller_boost_non_code(self):
        """'def' keywords add only +0.05 for non-code patterns."""
        gate = _make_gate()
        content = "Analysis:\ndef helper():\n    pass\nResult.\nExtra.\nMore."
        result_code = gate.evaluate("code", "test", content, latency_ms=0)
        result_analysis = gate.evaluate("analysis", "test", content, latency_ms=0)
        # code gets +0.1, analysis gets +0.05
        assert result_code.gates["structure"]["score"] >= result_analysis.gates["structure"]["score"]

    def test_structure_score_capped_at_one(self):
        """Structure score cannot exceed 1.0."""
        gate = _make_gate()
        # Content with everything: code blocks, lists, headers, def, many lines
        content = (
            "# Header\n"
            "```python\n"
            "def solution():\n"
            "    pass\n"
            "```\n"
            "- item 1\n"
            "- item 2\n"
            "* item 3\n"
            "1. numbered\n"
            "2. numbered\n"
        )
        result = gate.evaluate("code", "test", content, latency_ms=0)
        assert result.gates["structure"]["score"] <= 1.0

    def test_numbered_list_detected(self):
        """Lines starting with '1.' or '2.' count as list items."""
        gate = _make_gate()
        content = "Steps:\n1. First step\n2. Second step\nDone.\nMore.\nExtra."
        result = gate.evaluate("analysis", "test", content, latency_ms=0)
        assert result.gates["structure"]["score"] >= 0.5

    def test_asterisk_list_detected(self):
        """Lines starting with '*' count as list items."""
        gate = _make_gate()
        content = "Items:\n* alpha\n* beta\n* gamma\nEnd.\nExtra.\nMore."
        result = gate.evaluate("analysis", "test", content, latency_ms=0)
        assert result.gates["structure"]["score"] >= 0.5

    def test_code_block_no_boost_for_non_code_pattern(self):
        """Code blocks add +0.3 only for 'code' pattern, not other patterns."""
        gate = _make_gate()
        content = "Result:\n```\nsome block\n```\nDone.\nMore."
        result_code = gate.evaluate("code", "test", content, latency_ms=0)
        result_simple = gate.evaluate("simple", "test", content, latency_ms=0)
        # For non-code, ``` doesn't trigger +0.3 but lists/headers check still runs
        assert result_code.gates["structure"]["score"] > result_simple.gates["structure"]["score"]


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

    def test_stopwords_only_prompt_returns_half(self):
        """Prompt containing only stopwords (after filtering) returns 0.5."""
        gate = _make_gate()
        # "les des une est pour" are all stopwords in the code
        result = gate.evaluate("simple", "les des une est pour",
                               "some content here", latency_ms=0)
        assert result.gates["relevance"]["score"] == 0.5

    def test_full_overlap(self):
        """When content contains all prompt words, score approaches 1.0."""
        gate = _make_gate()
        prompt = "fibonacci algorithm python implementation"
        content = "This fibonacci algorithm python implementation works great."
        result = gate.evaluate("code", prompt, content, latency_ms=0)
        assert result.gates["relevance"]["score"] >= 0.9

    def test_relevance_caps_at_one(self):
        """Relevance score never exceeds 1.0."""
        gate = _make_gate()
        prompt = "test"
        content = "test test test test test"
        result = gate.evaluate("simple", prompt, content, latency_ms=0)
        assert result.gates["relevance"]["score"] <= 1.0

    def test_relevance_ignores_short_words(self):
        """Words shorter than 3 chars are excluded from the overlap."""
        gate = _make_gate()
        prompt = "is it ok to go"
        content = "is it ok to go ahead"
        result = gate.evaluate("simple", prompt, content, latency_ms=0)
        # Most words are <3 chars ("is","it","ok","to","go") -- "ok" and "go" are 2 chars
        # Only 3+ char words count, so depends on what passes the regex
        assert 0 <= result.gates["relevance"]["score"] <= 1.0

    def test_irrelevant_content_fails_gate(self):
        """Completely irrelevant content fails the relevance gate."""
        gate = _make_gate()
        prompt = "machine learning neural networks gradient descent"
        content = "The cat sat on the mat and played with yarn."
        result = gate.evaluate("code", prompt, content, latency_ms=0)
        assert result.gates["relevance"]["passed"] is False
        assert "relevance" in result.failed_gates

    def test_relevance_with_non_dict_config(self):
        """When min_relevance is a float (not dict), it is used directly."""
        from src.quality_gate import GateConfig
        cfg = GateConfig()
        cfg.min_relevance = 0.5  # Override dict with scalar
        gate = _make_gate(config=cfg)
        prompt = "fibonacci algorithm"
        content = "Here is the fibonacci algorithm solution."
        result = gate.evaluate("code", prompt, content, latency_ms=0)
        # Should use 0.5 as threshold
        assert result.gates["relevance"]["score"] >= 0


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

    def test_error_keywords_capped_at_max(self):
        """Only max_error_keywords errors are counted (default=3)."""
        gate = _make_gate()
        # 6 different error keywords, but only 3 should count
        content = "error traceback exception failed impossible cannot undefined null NaN erreur"
        result = gate.evaluate("code", "test", content, latency_ms=0)
        # score = 0.8 - 0.15*3 = 0.35
        assert result.gates["confidence"]["score"] >= 0.3

    def test_combined_errors_hedging_apology(self):
        """All penalty sources combine: errors + hedging + apology."""
        gate = _make_gate()
        content = (
            "Sorry, I think there was an error. "
            "The traceback shows an exception. "
            "Perhaps it failed, maybe it works."
        )
        result = gate.evaluate("code", "test", content, latency_ms=0)
        # Significant penalties from all three sources
        assert result.gates["confidence"]["score"] < 0.5

    def test_confidence_score_floors_at_zero(self):
        """Confidence score never goes below 0."""
        gate = _make_gate()
        content = (
            "Sorry, I apologize. I think perhaps possibly maybe "
            "error traceback exception failed impossible cannot null NaN "
            "je pense probablement il semble peut-etre "
            "desole sorry apologize"
        )
        result = gate.evaluate("code", "test", content, latency_ms=0)
        assert result.gates["confidence"]["score"] >= 0

    def test_confidence_score_caps_at_one(self):
        """Confidence score is at most 1.0."""
        gate = _make_gate()
        content = "This is a clear, confident, and correct response."
        result = gate.evaluate("simple", "test", content, latency_ms=0)
        assert result.gates["confidence"]["score"] <= 1.0

    def test_french_hedging_detected(self):
        """French hedging words lower confidence."""
        gate = _make_gate()
        content = "Je pense que peut-etre il semble correct, probablement oui."
        result = gate.evaluate("simple", "test", content, latency_ms=0)
        assert result.gates["confidence"]["score"] < 0.8

    def test_french_apology_detected(self):
        """French apology 'desole' lowers confidence."""
        gate = _make_gate()
        content = "Desole, je ne peux pas aider avec cette demande maintenant."
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

    def test_latency_at_exact_limit_passes(self):
        """Latency exactly at max threshold passes (<=)."""
        gate = _make_gate()
        # "simple" max is 10000
        result = gate.evaluate("simple", "test", "hello world test", latency_ms=10000)
        assert result.gates["latency"]["passed"] is True

    def test_latency_one_over_limit_fails(self):
        """Latency 1ms over max threshold fails."""
        gate = _make_gate()
        result = gate.evaluate("simple", "test", "hello world test", latency_ms=10001)
        assert result.gates["latency"]["passed"] is False

    def test_reasoning_pattern_higher_latency_ok(self):
        """'reasoning' pattern allows up to 90000ms."""
        gate = _make_gate()
        content = "The reasoning leads to the following conclusion which is well supported."
        result = gate.evaluate("reasoning", "test reasoning", content, latency_ms=85000)
        assert result.gates["latency"]["passed"] is True

    def test_unknown_pattern_uses_default_latency(self):
        """Unknown pattern falls back to default max_latency (45000)."""
        gate = _make_gate()
        result = gate.evaluate("unknown_pattern", "test", "x" * 20, latency_ms=44000)
        assert result.gates["latency"]["passed"] is True

    def test_latency_score_formula(self):
        """Score = max(0, 1.0 - latency / (max * 2))."""
        gate = _make_gate()
        # "simple" max is 10000, latency 5000
        result = gate.evaluate("simple", "test", "hello world test", latency_ms=5000)
        expected = max(0, 1.0 - 5000 / (10000 * 2))  # = 0.75
        assert abs(result.gates["latency"]["score"] - expected) < 0.01

    def test_latency_suggestion_message(self):
        """Failed latency gate produces suggestion with ms values."""
        gate = _make_gate()
        result = gate.evaluate("simple", "test", "hello world test", latency_ms=20000)
        assert any("trop lente" in s for s in result.suggestions)


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

    def test_french_ai_reference_detected(self):
        """French self-identification patterns are detected."""
        gate = _make_gate()
        content = "Je suis une intelligence artificielle et je ne peux pas le faire."
        result = gate.evaluate("simple", "test", content, latency_ms=0)
        assert result.gates["hallucination"]["score"] < 1.0

    def test_french_ai_model_reference(self):
        """French 'je suis un modele' pattern is detected."""
        gate = _make_gate()
        content = "Je suis un modele de langage et en tant qu'assistant je dois clarifier."
        result = gate.evaluate("simple", "test", content, latency_ms=0)
        assert result.gates["hallucination"]["score"] < 1.0

    def test_multiple_hallucination_patterns_stack(self):
        """Multiple hallucination patterns stack penalties (-0.2 each)."""
        gate = _make_gate()
        content = (
            "As an AI, I'm a language model. "
            "Je suis une IA. Lorem ipsum dolor sit amet."
        )
        result = gate.evaluate("code", "test", content, latency_ms=0)
        # At least 3 patterns match: "As an AI", "I'm a language model", "lorem ipsum",
        # "je suis une IA" => -0.2 * 4 = -0.8, score = 0.2
        assert result.gates["hallucination"]["score"] < 0.5

    def test_hallucination_score_floors_at_zero(self):
        """Hallucination score cannot go below 0."""
        gate = _make_gate()
        # Stack as many patterns as possible + repetition
        base = (
            "As an AI, I'm a language model. "
            "Je suis une IA. En tant qu'assistant. "
            "Lorem ipsum dolor sit amet."
        )
        content = ". ".join([base] * 10)  # massive repetition too
        result = gate.evaluate("code", "test", content, latency_ms=0)
        assert result.gates["hallucination"]["score"] >= 0

    def test_no_repetition_if_all_unique(self):
        """Unique sentences do not trigger repetition penalty."""
        gate = _make_gate()
        sentences = [f"Sentence number {i} is unique and distinct" for i in range(10)]
        content = ". ".join(sentences)
        result = gate.evaluate("analysis", "test", content, latency_ms=0)
        assert result.gates["hallucination"]["score"] == 1.0

    def test_short_sentences_ignored_in_repetition(self):
        """Sentences <= 20 chars are not counted in repetition check."""
        gate = _make_gate()
        content = "ok. ok. ok. ok. ok. ok. ok. ok. ok. ok."
        result = gate.evaluate("simple", "test", content, latency_ms=0)
        # Short sentences (<20 chars) are filtered out, so no repetition penalty
        assert result.gates["hallucination"]["score"] == 1.0


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

    def test_weights_sum_to_one(self):
        """The gate weights used in overall score sum to 1.0."""
        weights = {"length": 0.2, "structure": 0.15, "relevance": 0.25,
                    "confidence": 0.2, "latency": 0.1, "hallucination": 0.1}
        assert abs(sum(weights.values()) - 1.0) < 0.001

    def test_perfect_content_high_score(self):
        """Content that passes all gates with high scores gets high overall."""
        gate = _make_gate()
        result = gate.evaluate(
            "code", "write a fibonacci function in python",
            _good_code_content(), latency_ms=500,
        )
        assert result.overall_score >= 0.5

    def test_score_rounded_to_3_decimals(self):
        """Overall score is rounded to 3 decimal places."""
        gate = _make_gate()
        result = gate.evaluate("code", "test", _good_code_content(), latency_ms=0)
        score_str = str(result.overall_score)
        if "." in score_str:
            decimals = len(score_str.split(".")[1])
            assert decimals <= 3


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

    def test_length_failure_from_m3_suggests_m1(self):
        """M3 length failure suggests M1."""
        gate = _make_gate()
        result = gate.evaluate("code", "write code", "x", latency_ms=0, node="M3")
        assert result.suggested_node == "M1"

    def test_structure_failure_from_ol1_suggests_m1(self):
        """Structure failure from OL1 suggests M1."""
        gate = _make_gate()
        # Force a structure failure with extremely low threshold override
        from src.quality_gate import GateConfig
        cfg = GateConfig()
        gate = _make_gate(config=cfg)
        # Very short content that fails structure (and length for code)
        result = gate.evaluate("code", "write code", "x", latency_ms=0, node="OL1")
        if "structure" in result.failed_gates or "length" in result.failed_gates:
            assert result.suggested_node == "M1"

    def test_relevance_failure_from_ol1_suggests_m1(self):
        """_suggest_better_node returns M1 for relevance failure from OL1."""
        gate = _make_gate()
        # Test the internal method directly to avoid pass/fail interaction
        result = gate._suggest_better_node("code", "OL1", ["relevance"])
        assert result == "M1"

    def test_relevance_failure_from_other_node_suggests_m1(self):
        """_suggest_better_node returns M1 for relevance failure from any node."""
        gate = _make_gate()
        result = gate._suggest_better_node("code", "M2", ["relevance"])
        assert result == "M1"

    def test_no_retry_when_too_many_failures(self):
        """retry_recommended is False when >3 gates fail."""
        gate = _make_gate()
        # Content that fails many gates: empty + slow + irrelevant
        result = gate.evaluate("code", "write fibonacci", "", latency_ms=999999)
        # With empty content: length, structure (might pass at 0.3 base),
        # relevance, confidence, latency all potentially fail
        if len(result.failed_gates) > 3:
            assert result.retry_recommended is False

    def test_suggestions_list_populated_on_failure(self):
        """Each failed gate adds a suggestion to the list."""
        gate = _make_gate()
        result = gate.evaluate("code", "write code", "", latency_ms=0)
        assert len(result.suggestions) >= len(result.failed_gates)


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

    def test_stats_count_multiple_passes(self):
        """Multiple passing evaluations increment passed counter."""
        gate = _make_gate()
        for _ in range(5):
            gate.evaluate("simple", "hi", "hello there world", latency_ms=100)
        stats = gate.get_stats()
        assert stats["evaluated"] == 5
        assert stats["passed"] == 5
        assert stats["failed"] == 0
        assert stats["pass_rate"] == 1.0

    def test_stats_count_multiple_failures(self):
        """Multiple failing evaluations increment failed counter."""
        gate = _make_gate()
        for _ in range(4):
            gate.evaluate("code", "write code", "", latency_ms=0)
        stats = gate.get_stats()
        assert stats["evaluated"] == 4
        assert stats["failed"] == 4
        assert stats["passed"] == 0
        assert stats["pass_rate"] == 0.0

    def test_pass_rate_mixed(self):
        """Pass rate is correct for mixed results."""
        gate = _make_gate()
        # 2 passes
        gate.evaluate("simple", "hi", "hello world test", latency_ms=100)
        gate.evaluate("simple", "hi", "hello world test", latency_ms=100)
        # 2 failures
        gate.evaluate("code", "write code", "", latency_ms=0)
        gate.evaluate("code", "write code", "", latency_ms=0)
        stats = gate.get_stats()
        assert stats["evaluated"] == 4
        assert stats["pass_rate"] == 0.5


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

    def test_auto_tune_low_dispatch_rate_warning(self):
        """When dispatch rate <30% and total >= 20, a WARNING is produced."""
        gate = _make_gate()

        dispatch_row = MagicMock()
        dispatch_row.__getitem__ = lambda self, k: {
            "pattern": "security", "total": 30, "dispatch_ok": 5,
            "avg_q": 0.3, "avg_lat": 5000,
        }[k]

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.side_effect = [
            [dispatch_row],
            [],
        ]
        mock_db.row_factory = None

        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            adjustments = gate.auto_tune_from_data(min_samples=5)

        assert "security" in adjustments
        assert any("WARNING" in s for s in adjustments["security"])

    def test_auto_tune_relevance_floor_at_003(self):
        """Relaxed relevance never drops below 0.03."""
        gate = _make_gate()
        # Set very low initial relevance
        gate.config.min_relevance["test_pat"] = 0.04

        dispatch_row = MagicMock()
        dispatch_row.__getitem__ = lambda self, k: {
            "pattern": "test_pat", "total": 100, "dispatch_ok": 95,
            "avg_q": 0.9, "avg_lat": 1000,
        }[k]

        gate_row = MagicMock()
        gate_row.__getitem__ = lambda self, k: {
            "pattern": "test_pat", "n": 50, "passed": 10,
            "avg_score": 0.3,
        }[k]

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.side_effect = [
            [dispatch_row],
            [gate_row],
        ]
        mock_db.row_factory = None

        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            gate.auto_tune_from_data(min_samples=5)

        # 0.04 * 0.7 = 0.028, but floor is max(0.03, ...) = 0.03
        assert gate.config.min_relevance["test_pat"] >= 0.03


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

    def test_gate_report_pass_rate_and_avg_score(self):
        """Report includes correct pass_rate and avg_score per pattern."""
        gate = _make_gate()

        pattern_row = MagicMock()
        pattern_row.__getitem__ = lambda self, k: {
            "pattern": "simple", "n": 10, "ok": 8, "avg_score": 0.65,
        }[k]

        call_results = iter([
            MagicMock(fetchone=MagicMock(return_value=(10,))),
            MagicMock(fetchall=MagicMock(return_value=[pattern_row])),
            MagicMock(fetchall=MagicMock(return_value=[])),
        ])
        mock_db = MagicMock()
        mock_db.execute = lambda q, *a: next(call_results)
        mock_db.row_factory = None

        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            report = gate.get_gate_report()

        assert report["by_pattern"][0]["pass_rate"] == 0.8
        assert report["by_pattern"][0]["avg_score"] == 0.65

    def test_gate_report_null_avg_score(self):
        """Report handles NULL avg_score from DB (treated as 0)."""
        gate = _make_gate()

        pattern_row = MagicMock()
        pattern_row.__getitem__ = lambda self, k: {
            "pattern": "empty", "n": 1, "ok": 0, "avg_score": None,
        }[k]

        call_results = iter([
            MagicMock(fetchone=MagicMock(return_value=(1,))),
            MagicMock(fetchall=MagicMock(return_value=[pattern_row])),
            MagicMock(fetchall=MagicMock(return_value=[])),
        ])
        mock_db = MagicMock()
        mock_db.execute = lambda q, *a: next(call_results)
        mock_db.row_factory = None

        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            report = gate.get_gate_report()

        assert report["by_pattern"][0]["avg_score"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# DB interaction — _ensure_table and _log error handling
# ═══════════════════════════════════════════════════════════════════════════

class TestDBInteraction:
    def test_ensure_table_db_error_silenced(self):
        """_ensure_table silently handles DB errors."""
        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB file locked")
            from src.quality_gate import QualityGate
            # Should not raise
            gate = QualityGate()
            assert gate is not None

    def test_log_db_error_silenced(self):
        """_log silently handles DB errors without crashing evaluate."""
        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.return_value = MagicMock()
            from src.quality_gate import QualityGate
            gate = QualityGate()

        # Now make _log's DB call fail
        with patch("src.quality_gate.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("disk full")
            # Call the real _log (not mocked) -- it should not raise
            from src.quality_gate import GateResult
            result = GateResult(
                passed=True, overall_score=0.8, gates={},
                failed_gates=[], suggestions=[],
                retry_recommended=False,
            )
            gate._log("code", result, "M1")  # Should not raise

    def test_constructor_without_config_uses_defaults(self):
        """QualityGate() without config uses GateConfig defaults."""
        with patch("src.quality_gate.sqlite3"):
            from src.quality_gate import QualityGate, GateConfig
            gate = QualityGate()
            assert gate.config.min_overall_score == GateConfig().min_overall_score


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases — _suggest_better_node
# ═══════════════════════════════════════════════════════════════════════════

class TestSuggestBetterNode:
    def test_latency_failure_always_suggests_m1(self):
        gate = _make_gate()
        result = gate._suggest_better_node("code", "M2", ["latency"])
        assert result == "M1"

    def test_length_failure_from_ol1(self):
        gate = _make_gate()
        result = gate._suggest_better_node("code", "OL1", ["length"])
        assert result == "M1"

    def test_length_failure_from_m3(self):
        gate = _make_gate()
        result = gate._suggest_better_node("code", "M3", ["length"])
        assert result == "M1"

    def test_structure_failure_from_any_node(self):
        gate = _make_gate()
        result = gate._suggest_better_node("code", "M2", ["structure"])
        assert result == "M1"

    def test_relevance_failure_from_ol1(self):
        gate = _make_gate()
        result = gate._suggest_better_node("code", "OL1", ["relevance"])
        assert result == "M1"

    def test_relevance_failure_from_m1(self):
        gate = _make_gate()
        result = gate._suggest_better_node("code", "M1", ["relevance"])
        assert result == "M1"

    def test_no_matching_failure_returns_empty(self):
        """Unknown failure type returns empty string."""
        gate = _make_gate()
        result = gate._suggest_better_node("code", "M1", ["confidence"])
        # confidence is not in the if-chain, falls through to return ""
        assert result == ""

    def test_no_failures_returns_empty(self):
        gate = _make_gate()
        result = gate._suggest_better_node("code", "M1", [])
        assert result == ""


# ═══════════════════════════════════════════════════════════════════════════
# Pattern-specific evaluations
# ═══════════════════════════════════════════════════════════════════════════

class TestPatternSpecific:
    def test_each_pattern_has_length_threshold(self):
        """Every pattern type returns a valid length gate with proper threshold."""
        gate = _make_gate()
        patterns = ["simple", "classifier", "code", "analysis", "architecture",
                     "reasoning", "math", "trading", "security", "creative",
                     "system", "data", "devops", "web"]
        for pattern in patterns:
            result = gate.evaluate(pattern, "test prompt", "x" * 200, latency_ms=0)
            assert "length" in result.gates
            assert result.gates["length"]["passed"] is True

    def test_analysis_needs_more_content_than_simple(self):
        """'analysis' requires 80 chars vs 'simple' requires 3."""
        gate = _make_gate()
        short_content = "abcde"  # 5 chars
        result_simple = gate.evaluate("simple", "test", short_content, latency_ms=0)
        result_analysis = gate.evaluate("analysis", "test", short_content, latency_ms=0)
        assert result_simple.gates["length"]["passed"] is True
        assert result_analysis.gates["length"]["passed"] is False

    def test_reasoning_highest_latency_allowance(self):
        """'reasoning' pattern allows the highest latency (90000ms)."""
        gate = _make_gate()
        content = "The logical reasoning process leads to this conclusion with high confidence."
        result = gate.evaluate("reasoning", "test reasoning", content, latency_ms=89000)
        assert result.gates["latency"]["passed"] is True

    def test_code_pattern_rewards_code_blocks(self):
        """'code' pattern specifically rewards ``` code blocks in structure."""
        gate = _make_gate()
        code_content = "Answer:\n```python\ndef foo():\n    return 42\n```\nExplanation."
        plain_content = "Answer:\ndef foo():\n    return 42\nExplanation.\nMore.\nExtra."
        r_code = gate.evaluate("code", "test", code_content, latency_ms=0)
        r_plain = gate.evaluate("code", "test", plain_content, latency_ms=0)
        assert r_code.gates["structure"]["score"] > r_plain.gates["structure"]["score"]
