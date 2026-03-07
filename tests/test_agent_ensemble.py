"""Tests for src/agent_ensemble.py — Multi-agent ensemble with scoring.

Covers: EnsembleOutput, EnsembleResult dataclasses, AgentEnsemble
(SCORING_WEIGHTS, _default_nodes, _score_output, _merge_outputs,
_calculate_agreement, get_ensemble_stats, get_best_ensemble_config),
get_ensemble singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_ensemble import (
    EnsembleOutput, EnsembleResult, AgentEnsemble, get_ensemble,
)


# ===========================================================================
# EnsembleOutput
# ===========================================================================

class TestEnsembleOutput:
    def test_defaults(self):
        o = EnsembleOutput(node="M1", content="hello", latency_ms=500, success=True)
        assert o.scores == {}
        assert o.total_score == 0

    def test_with_scores(self):
        o = EnsembleOutput(
            node="OL1", content="world", latency_ms=200, success=True,
            scores={"length": 0.8, "structure": 0.7}, total_score=0.75,
        )
        assert o.scores["length"] == 0.8
        assert o.total_score == 0.75

    def test_failed(self):
        o = EnsembleOutput(node="M2", content="", latency_ms=30000, success=False)
        assert o.success is False


# ===========================================================================
# EnsembleResult
# ===========================================================================

class TestEnsembleResult:
    def test_basic(self):
        best = EnsembleOutput("M1", "code", 300, True, total_score=0.9)
        r = EnsembleResult(
            pattern="code", prompt="write code",
            best_output=best, all_outputs=[best],
            strategy="best_of_n", total_latency_ms=500,
            ensemble_size=2, agreement_score=0.85,
        )
        assert r.pattern == "code"
        assert r.ensemble_size == 2
        assert r.agreement_score == 0.85


# ===========================================================================
# SCORING_WEIGHTS
# ===========================================================================

class TestScoringWeights:
    def test_all_patterns(self):
        for p in ("code", "simple", "reasoning", "analysis", "default"):
            assert p in AgentEnsemble.SCORING_WEIGHTS

    def test_weights_sum_to_one(self):
        for p, weights in AgentEnsemble.SCORING_WEIGHTS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"{p}: weights sum to {total}"

    def test_dimensions(self):
        expected = {"length", "structure", "relevance", "confidence", "speed"}
        for p, weights in AgentEnsemble.SCORING_WEIGHTS.items():
            assert set(weights.keys()) == expected, f"{p}: missing dimensions"


# ===========================================================================
# AgentEnsemble — _default_nodes
# ===========================================================================

class TestDefaultNodes:
    def setup_method(self):
        with patch("src.agent_ensemble.sqlite3"):
            self.ens = AgentEnsemble()

    def test_simple_pattern(self):
        nodes = self.ens._default_nodes("simple")
        assert "M1" in nodes
        assert "OL1" in nodes

    def test_code_pattern(self):
        nodes = self.ens._default_nodes("code")
        assert "M1" in nodes

    def test_reasoning_pattern(self):
        nodes = self.ens._default_nodes("reasoning")
        assert "M1" in nodes
        assert "M2" in nodes

    def test_unknown_pattern(self):
        nodes = self.ens._default_nodes("unknown_xyz")
        assert len(nodes) >= 2


# ===========================================================================
# AgentEnsemble — _score_output
# ===========================================================================

class TestScoreOutput:
    def setup_method(self):
        with patch("src.agent_ensemble.sqlite3"):
            self.ens = AgentEnsemble()

    def test_code_output(self):
        content = "```python\ndef parser():\n    return json.loads(data)\n```"
        scores = self.ens._score_output("code", "ecris un parser", content, 500)
        assert "length" in scores
        assert "structure" in scores
        assert "relevance" in scores
        assert "confidence" in scores
        assert "speed" in scores
        assert scores["structure"] >= 0.5  # Has code blocks

    def test_simple_short_answer(self):
        scores = self.ens._score_output("simple", "bonjour", "Bonjour! Comment allez-vous?", 200)
        assert scores["length"] >= 0.5
        assert scores["speed"] == 1.0  # < 1000ms

    def test_slow_response(self):
        scores = self.ens._score_output("code", "write code", "some code", 15000)
        assert scores["speed"] == 0.2  # > 10000ms

    def test_hedging_lowers_confidence(self):
        scores = self.ens._score_output("simple", "q", "je pense que peut-etre oui", 500)
        assert scores["confidence"] < 0.7

    def test_error_content_lowers_confidence(self):
        scores = self.ens._score_output("code", "q", "error: something failed", 500)
        assert scores["confidence"] < 0.5

    def test_relevance_with_overlap(self):
        scores = self.ens._score_output("code", "parser json python", "parser json en python", 500)
        assert scores["relevance"] >= 0.5

    def test_empty_prompt(self):
        scores = self.ens._score_output("simple", "", "response", 500)
        assert scores["relevance"] == 0.5  # Default when no prompt words

    def test_multiline_structure(self):
        content = "# Header\n- Item 1\n- Item 2\n\nSome text\nMore text\n\nConclusion."
        scores = self.ens._score_output("analysis", "analyse", content, 1000)
        assert scores["structure"] >= 0.5

    def test_all_scores_in_range(self):
        scores = self.ens._score_output("code", "test prompt", "test output " * 50, 2000)
        for k, v in scores.items():
            assert 0 <= v <= 1.0, f"{k}: {v} out of range"


# ===========================================================================
# AgentEnsemble — _merge_outputs
# ===========================================================================

class TestMergeOutputs:
    def setup_method(self):
        with patch("src.agent_ensemble.sqlite3"):
            self.ens = AgentEnsemble()

    def test_longer_wins(self):
        top1 = EnsembleOutput("M1", "x" * 500, 300, True, total_score=0.8)
        top2 = EnsembleOutput("OL1", "y" * 100, 200, True, total_score=0.6)
        merged = self.ens._merge_outputs(top1, top2, "code")
        assert merged.content == "x" * 500
        assert "M1" in merged.node

    def test_similar_length(self):
        top1 = EnsembleOutput("M1", "abc" * 50, 300, True, total_score=0.9)
        top2 = EnsembleOutput("OL1", "def" * 50, 200, True, total_score=0.7)
        merged = self.ens._merge_outputs(top1, top2, "simple")
        # When similar length, takes top1 (higher score)
        assert merged.content == "abc" * 50

    def test_merged_node_name(self):
        top1 = EnsembleOutput("M1", "a" * 500, 300, True, total_score=0.8)
        top2 = EnsembleOutput("OL1", "b" * 100, 200, True, total_score=0.6)
        merged = self.ens._merge_outputs(top1, top2, "code")
        assert "M1" in merged.node
        assert "OL1" in merged.node

    def test_merged_score(self):
        top1 = EnsembleOutput("M1", "a", 300, True, total_score=0.8)
        top2 = EnsembleOutput("OL1", "b", 200, True, total_score=0.6)
        merged = self.ens._merge_outputs(top1, top2, "code")
        assert merged.total_score == 0.7  # Average


# ===========================================================================
# AgentEnsemble — _calculate_agreement
# ===========================================================================

class TestCalculateAgreement:
    def setup_method(self):
        with patch("src.agent_ensemble.sqlite3"):
            self.ens = AgentEnsemble()

    def test_single_output(self):
        outputs = [EnsembleOutput("M1", "hello world", 300, True)]
        assert self.ens._calculate_agreement(outputs) == 1.0

    def test_empty(self):
        assert self.ens._calculate_agreement([]) == 1.0

    def test_identical_outputs(self):
        o1 = EnsembleOutput("M1", "the quick brown fox jumps", 300, True)
        o2 = EnsembleOutput("OL1", "the quick brown fox jumps", 200, True)
        agreement = self.ens._calculate_agreement([o1, o2])
        assert agreement == 1.0

    def test_different_outputs(self):
        o1 = EnsembleOutput("M1", "python code for parsing data", 300, True)
        o2 = EnsembleOutput("OL1", "completely unrelated xyzzy content here", 200, True)
        agreement = self.ens._calculate_agreement([o1, o2])
        assert agreement < 0.5

    def test_partial_agreement(self):
        o1 = EnsembleOutput("M1", "parser json python function", 300, True)
        o2 = EnsembleOutput("OL1", "json parser function implementation", 200, True)
        agreement = self.ens._calculate_agreement([o1, o2])
        assert 0.3 < agreement < 1.0


# ===========================================================================
# AgentEnsemble — get_ensemble_stats
# ===========================================================================

class TestGetEnsembleStats:
    def test_db_error(self):
        with patch("src.agent_ensemble.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB")
            ens = AgentEnsemble()
            stats = ens.get_ensemble_stats()
        assert stats["total_ensembles"] == 0


# ===========================================================================
# AgentEnsemble — get_best_ensemble_config
# ===========================================================================

class TestGetBestConfig:
    def test_no_data(self):
        with patch("src.agent_ensemble.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB")
            ens = AgentEnsemble()
            config = ens.get_best_ensemble_config("code")
        assert config["status"] == "error"


# ===========================================================================
# get_ensemble singleton
# ===========================================================================

class TestSingleton:
    def test_returns_instance(self):
        with patch("src.agent_ensemble.sqlite3"):
            import src.agent_ensemble as mod
            mod._ensemble = None
            ens = get_ensemble()
            assert isinstance(ens, AgentEnsemble)

    def test_singleton(self):
        with patch("src.agent_ensemble.sqlite3"):
            import src.agent_ensemble as mod
            mod._ensemble = None
            e1 = get_ensemble()
            e2 = get_ensemble()
            assert e1 is e2
