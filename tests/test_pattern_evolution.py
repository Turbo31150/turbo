"""Tests for src/pattern_evolution.py — Auto-create/evolve patterns from usage.

Covers: PatternSuggestion dataclass, PatternEvolution (KEYWORD_CLUSTERS,
_find_misclassified, _find_underperforming, _find_redundant, analyze_gaps,
auto_create_patterns, evolve_patterns, _create_pattern, _log_evolution,
get_evolution_history, get_stats), get_evolution singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pattern_evolution import (
    PatternSuggestion, PatternEvolution, get_evolution,
)


# ===========================================================================
# PatternSuggestion
# ===========================================================================

class TestPatternSuggestion:
    def test_defaults(self):
        s = PatternSuggestion(action="create", pattern_type="testing",
                              description="New testing pattern")
        assert s.evidence == {}
        assert s.confidence == 0.0
        assert s.model_suggestion == ""
        assert s.strategy_suggestion == "single"

    def test_with_all_fields(self):
        s = PatternSuggestion(
            action="evolve", pattern_type="code",
            description="Improve code pattern",
            evidence={"count": 42}, confidence=0.8,
            model_suggestion="qwen3-8b",
            strategy_suggestion="consensus",
        )
        assert s.confidence == 0.8
        assert s.evidence["count"] == 42

    def test_action_types(self):
        for action in ("create", "evolve", "merge", "deprecate"):
            s = PatternSuggestion(action=action, pattern_type="x", description="d")
            assert s.action == action


# ===========================================================================
# KEYWORD_CLUSTERS
# ===========================================================================

class TestKeywordClusters:
    def test_has_expected_clusters(self):
        expected = {"deployment", "testing", "documentation", "database",
                    "networking", "frontend", "infrastructure", "nlp",
                    "visualization", "automation"}
        assert expected.issubset(set(PatternEvolution.KEYWORD_CLUSTERS.keys()))

    def test_clusters_are_lists(self):
        for name, keywords in PatternEvolution.KEYWORD_CLUSTERS.items():
            assert isinstance(keywords, list), f"{name} is not a list"
            assert len(keywords) >= 2, f"{name} has too few keywords"

    def test_all_keywords_lowercase(self):
        for name, keywords in PatternEvolution.KEYWORD_CLUSTERS.items():
            for kw in keywords:
                assert kw == kw.lower(), f"{name}: '{kw}' not lowercase"


# ===========================================================================
# PatternEvolution — init
# ===========================================================================

class TestInit:
    def test_init_db_error_no_crash(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB missing")
            evo = PatternEvolution()  # should not raise
        assert evo is not None


# ===========================================================================
# PatternEvolution — _find_misclassified
# ===========================================================================

class TestFindMisclassified:
    def test_no_data(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_db = MagicMock()
            mock_db.execute.return_value.fetchall.return_value = []
            mock_sql.connect.return_value = mock_db
            evo = PatternEvolution()
            results = evo._find_misclassified()
        assert results == []

    def test_finds_cluster_match(self):
        # Simulate prompts that match 'database' cluster
        prompts = [(f"migrate sql database schema #{i}", "simple") for i in range(5)]

        mock_db1 = MagicMock()
        mock_db1.execute.return_value.fetchall.return_value = prompts

        mock_db2 = MagicMock()
        mock_db2.execute.return_value.fetchall.return_value = []  # no existing patterns

        call_count = [0]
        def connect_side_effect(*a, **kw):
            call_count[0] += 1
            if call_count[0] <= 1:
                return mock_db1
            return mock_db2

        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = connect_side_effect
            evo = PatternEvolution()
            # Reset connect side effect for the actual call
            call_count[0] = 0
            mock_sql.connect.side_effect = connect_side_effect
            results = evo._find_misclassified()

        # Should find 'database' cluster
        db_results = [r for r in results if r.pattern_type == "database"]
        assert len(db_results) >= 1
        assert db_results[0].action == "create"

    def test_db_error_no_crash(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB")
            evo = PatternEvolution()
            mock_sql.connect.side_effect = Exception("DB")
            results = evo._find_misclassified()
        assert results == []


# ===========================================================================
# PatternEvolution — _find_underperforming
# ===========================================================================

class TestFindUnderperforming:
    def test_no_data(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_db = MagicMock()
            mock_db.execute.return_value.fetchall.return_value = []
            mock_sql.connect.return_value = mock_db
            evo = PatternEvolution()
            results = evo._find_underperforming()
        assert results == []

    def test_finds_underperformer(self):
        mock_row = {"pattern": "code", "node": "M3", "avg_q": 0.3, "n": 10, "avg_lat": 5000}

        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_db = MagicMock()
            mock_db.row_factory = None
            mock_db.execute.return_value.fetchall.return_value = [mock_row]
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = object
            evo = PatternEvolution()

            # Reset for actual call
            mock_db2 = MagicMock()
            mock_db2.row_factory = None
            mock_db2.execute.return_value.fetchall.return_value = [mock_row]
            mock_sql.connect.return_value = mock_db2
            results = evo._find_underperforming()

        assert len(results) >= 1
        assert results[0].action == "evolve"

    def test_db_error_no_crash(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB")
            evo = PatternEvolution()
            mock_sql.connect.side_effect = Exception("DB")
            results = evo._find_underperforming()
        assert results == []


# ===========================================================================
# PatternEvolution — _find_redundant
# ===========================================================================

class TestFindRedundant:
    def test_no_data(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_db = MagicMock()
            mock_db.execute.return_value.fetchall.return_value = []
            mock_sql.connect.return_value = mock_db
            evo = PatternEvolution()
            results = evo._find_redundant()
        assert results == []

    def test_db_error_no_crash(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB")
            evo = PatternEvolution()
            mock_sql.connect.side_effect = Exception("DB")
            results = evo._find_redundant()
        assert results == []


# ===========================================================================
# PatternEvolution — analyze_gaps
# ===========================================================================

class TestAnalyzeGaps:
    def test_returns_sorted_by_confidence(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.return_value = MagicMock()
            evo = PatternEvolution()

        with patch.object(evo, "_find_misclassified", return_value=[
            PatternSuggestion("create", "a", "d", confidence=0.3),
            PatternSuggestion("create", "b", "d", confidence=0.9),
        ]), patch.object(evo, "_find_underperforming", return_value=[
            PatternSuggestion("evolve", "c", "d", confidence=0.6),
        ]), patch.object(evo, "_find_redundant", return_value=[]):
            suggestions = evo.analyze_gaps()

        assert len(suggestions) == 3
        # Should be sorted by confidence descending
        confs = [s.confidence for s in suggestions]
        assert confs == sorted(confs, reverse=True)


# ===========================================================================
# PatternEvolution — auto_create_patterns
# ===========================================================================

class TestAutoCreatePatterns:
    def test_creates_high_confidence(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.return_value = MagicMock()
            evo = PatternEvolution()

        suggestions = [
            PatternSuggestion("create", "testing", "New", confidence=0.8),
            PatternSuggestion("evolve", "code", "Evolve", confidence=0.9),
            PatternSuggestion("create", "nlp", "NLP", confidence=0.2),  # below threshold
        ]
        with patch.object(evo, "analyze_gaps", return_value=suggestions), \
             patch.object(evo, "_create_pattern", return_value=True), \
             patch.object(evo, "_log_evolution"):
            created = evo.auto_create_patterns(min_confidence=0.5)

        # Only 'testing' is action=create with confidence >= 0.5
        assert len(created) == 1
        assert created[0]["pattern"] == "testing"
        assert created[0]["created"] is True

    def test_no_suggestions(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.return_value = MagicMock()
            evo = PatternEvolution()

        with patch.object(evo, "analyze_gaps", return_value=[]):
            created = evo.auto_create_patterns()
        assert created == []


# ===========================================================================
# PatternEvolution — evolve_patterns
# ===========================================================================

class TestEvolvePatterns:
    def test_evolves_above_threshold(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.return_value = MagicMock()
            evo = PatternEvolution()

        suggestions = [
            PatternSuggestion("evolve", "code", "Improve code", confidence=0.6,
                              model_suggestion="qwen3-8b"),
            PatternSuggestion("create", "testing", "New", confidence=0.8),
        ]
        with patch.object(evo, "analyze_gaps", return_value=suggestions), \
             patch.object(evo, "_log_evolution"):
            evolved = evo.evolve_patterns(min_confidence=0.3)

        assert len(evolved) == 1
        assert evolved[0]["pattern"] == "code"
        assert evolved[0]["action"] == "evolution_logged"


# ===========================================================================
# PatternEvolution — _create_pattern
# ===========================================================================

class TestCreatePattern:
    def test_success(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.return_value = MagicMock()
            evo = PatternEvolution()

        s = PatternSuggestion("create", "testing", "Test pattern",
                              model_suggestion="qwen3-8b")
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.return_value = MagicMock()
            result = evo._create_pattern(s)
        assert result is True

    def test_db_error(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.return_value = MagicMock()
            evo = PatternEvolution()

        s = PatternSuggestion("create", "testing", "Test")
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB error")
            result = evo._create_pattern(s)
        assert result is False

    def test_uses_keyword_clusters(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_db = MagicMock()
            mock_sql.connect.return_value = mock_db
            evo = PatternEvolution()

        s = PatternSuggestion("create", "database", "DB pattern",
                              model_suggestion="qwen3-8b", strategy_suggestion="single")
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            evo._create_pattern(s)

        # Verify the INSERT call includes the pattern_type
        insert_call = mock_db.execute.call_args
        assert "database" in str(insert_call)


# ===========================================================================
# PatternEvolution — get_evolution_history
# ===========================================================================

class TestGetEvolutionHistory:
    def test_empty(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_db = MagicMock()
            mock_db.execute.return_value.fetchall.return_value = []
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = object
            evo = PatternEvolution()

            mock_db2 = MagicMock()
            mock_db2.execute.return_value.fetchall.return_value = []
            mock_sql.connect.return_value = mock_db2
            history = evo.get_evolution_history()
        assert history == []

    def test_db_error(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB")
            evo = PatternEvolution()
            mock_sql.connect.side_effect = Exception("DB")
            history = evo.get_evolution_history()
        assert history == []


# ===========================================================================
# PatternEvolution — get_stats
# ===========================================================================

class TestGetStats:
    def test_empty(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_db = MagicMock()
            mock_db.execute.return_value.fetchone.return_value = (0,)
            mock_db.execute.return_value.fetchall.return_value = []
            mock_sql.connect.return_value = mock_db
            evo = PatternEvolution()

        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_db2 = MagicMock()
            # First call: total count
            # Second call: applied count
            # Third call: by_action
            call_results = [(0,), (0,), []]
            call_idx = [0]
            def execute_side_effect(*a, **kw):
                result = MagicMock()
                idx = call_idx[0]
                call_idx[0] += 1
                if idx < 2:
                    result.fetchone.return_value = call_results[idx]
                else:
                    result.fetchall.return_value = call_results[idx]
                return result
            mock_db2.execute = execute_side_effect
            mock_sql.connect.return_value = mock_db2
            stats = evo.get_stats()
        assert stats["total_suggestions"] == 0

    def test_db_error(self):
        with patch("src.pattern_evolution.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB")
            evo = PatternEvolution()
            mock_sql.connect.side_effect = Exception("DB")
            stats = evo.get_stats()
        assert stats == {"total_suggestions": 0}


# ===========================================================================
# get_evolution singleton
# ===========================================================================

class TestSingleton:
    def test_returns_instance(self):
        with patch("src.pattern_evolution.sqlite3"):
            import src.pattern_evolution as mod
            mod._evolution = None
            evo = get_evolution()
            assert isinstance(evo, PatternEvolution)

    def test_same_instance(self):
        with patch("src.pattern_evolution.sqlite3"):
            import src.pattern_evolution as mod
            mod._evolution = None
            e1 = get_evolution()
            e2 = get_evolution()
            assert e1 is e2
