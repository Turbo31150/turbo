"""Tests for src/agent_prompt_optimizer.py — Prompt optimization and analysis.

Covers: optimization, system prompts, constraints, insights, templates,
prompt analysis, length checks, keyword analysis.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_prompt_optimizer import PromptOptimizer, PromptInsight, PromptTemplate


@pytest.fixture
def opt(tmp_path):
    """PromptOptimizer with isolated temp database."""
    return PromptOptimizer(db_path=str(tmp_path / "test_opt.db"))


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_prompt_insight(self):
        pi = PromptInsight("code", (20, 200), ["python"], ["bug"], "system", 0.8, 0.6, 100, "single")
        assert pi.optimal_length_range == (20, 200)

    def test_prompt_template(self):
        pt = PromptTemplate("code", "system prompt", "prefix", ["c1"], 2, 500, 0.85)
        assert pt.effectiveness == 0.85


# ===========================================================================
# System prompts & constraints
# ===========================================================================

class TestSystemPrompts:
    def test_all_key_patterns_have_system_prompt(self, opt):
        for pattern in ["code", "simple", "reasoning", "math", "analysis",
                        "architecture", "trading", "security", "system"]:
            assert pattern in opt.SYSTEM_PROMPTS, f"Missing system prompt for {pattern}"

    def test_system_prompts_are_nonempty(self, opt):
        for pattern, prompt in opt.SYSTEM_PROMPTS.items():
            assert len(prompt) > 10, f"System prompt too short for {pattern}"

    def test_constraints_exist_for_key_patterns(self, opt):
        assert "code" in opt.CONSTRAINTS
        assert "simple" in opt.CONSTRAINTS
        assert "reasoning" in opt.CONSTRAINTS


# ===========================================================================
# Optimize
# ===========================================================================

class TestOptimize:
    def test_basic_optimize(self, opt):
        result = opt.optimize("code", "Ecris un parser JSON en Python")
        assert "system_prompt" in result
        assert "user_prompt" in result
        assert "optimizations_applied" in result
        assert "system_prompt" in result["optimizations_applied"]

    def test_optimize_adds_constraints(self, opt):
        result = opt.optimize("code", "Ecris une fonction")
        assert "constraints" in result["optimizations_applied"]
        assert "Contraintes" in result["user_prompt"]

    def test_optimize_no_system(self, opt):
        result = opt.optimize("code", "Test", add_system=False)
        assert result["system_prompt"] == ""
        assert "system_prompt" not in result["optimizations_applied"]

    def test_optimize_no_constraints(self, opt):
        result = opt.optimize("code", "Test", add_constraints=False)
        assert "constraints" not in result["optimizations_applied"]

    def test_optimize_unknown_pattern(self, opt):
        result = opt.optimize("unknown_xyz", "Test prompt")
        assert result["system_prompt"] == ""
        assert result["user_prompt"] == "Test prompt"

    def test_optimize_preserves_original(self, opt):
        original = "Mon prompt original"
        result = opt.optimize("simple", original)
        assert result["original_prompt"] == original
        assert result["original_length"] == len(original)

    def test_optimize_simple_short(self, opt):
        result = opt.optimize("simple", "Bonjour")
        assert result["pattern"] == "simple"


# ===========================================================================
# Insights
# ===========================================================================

class TestInsights:
    def test_insights_no_data(self, opt):
        result = opt.get_insights("code")
        assert result["status"] == "no_data"

    def test_insights_all_patterns(self, opt):
        result = opt.get_insights()
        assert isinstance(result, dict)

    def test_insights_with_mock_data(self, opt):
        # Manually inject an insight
        opt._insights_cache["code"] = PromptInsight(
            "code", (20, 200), ["python", "function"], ["bug"],
            "system", 0.85, 0.65, 50, "single"
        )
        result = opt.get_insights("code")
        assert result["pattern"] == "code"
        assert result["optimal_length"]["min"] == 20
        assert result["optimal_length"]["max"] == 200
        assert "python" in result["high_quality_keywords"]
        assert result["sample_size"] == 50


# ===========================================================================
# Templates
# ===========================================================================

class TestTemplates:
    def test_get_templates(self, opt):
        templates = opt.get_templates()
        assert "code" in templates
        assert "system_prompt" in templates["code"]
        assert "constraints" in templates["code"]

    def test_templates_include_insights_data(self, opt):
        opt._insights_cache["code"] = PromptInsight(
            "code", (30, 150), ["python"], [], "", 0.8, 0.6, 20, "single"
        )
        templates = opt.get_templates()
        assert templates["code"]["optimal_length"] is not None
        assert templates["code"]["optimal_length"]["min"] == 30


# ===========================================================================
# Analyze prompt
# ===========================================================================

class TestAnalyzePrompt:
    def test_analyze_basic(self, opt):
        result = opt.analyze_prompt("code", "Ecris un parser JSON en Python")
        assert "prompt_length" in result
        assert "word_count" in result
        assert "estimated_quality" in result
        assert "suggestions" in result
        assert "optimized" in result

    def test_analyze_very_short_prompt(self, opt):
        result = opt.analyze_prompt("code", "hi")
        suggestions = " ".join(result["suggestions"])
        assert "vague" in suggestions.lower() or "court" in suggestions.lower() or "specifie" in suggestions.lower()
        assert result["estimated_quality"] < 0.5

    def test_analyze_well_formed_prompt(self, opt):
        result = opt.analyze_prompt("code", "Ecris une fonction Python qui parse un fichier JSON et retourne un dictionnaire avec gestion d'erreurs")
        assert result["estimated_quality"] >= 0.3

    def test_analyze_code_without_language(self, opt):
        result = opt.analyze_prompt("code", "Ecris un programme qui trie une liste de nombres en ordre croissant")
        suggestions = " ".join(result["suggestions"])
        assert "langage" in suggestions.lower() or "technologie" in suggestions.lower()

    def test_analyze_code_with_language(self, opt):
        result = opt.analyze_prompt("code", "Ecris une fonction Python qui calcule")
        suggestions = " ".join(result["suggestions"])
        # Should NOT suggest specifying language
        assert "langage" not in suggestions.lower() or "Aucune" in suggestions

    def test_quality_clamped_0_1(self, opt):
        # Very bad prompt
        result = opt.analyze_prompt("code", "x")
        assert 0 <= result["estimated_quality"] <= 1

    def test_analyze_architecture_single_line(self, opt):
        result = opt.analyze_prompt("architecture", "Design un systeme")
        suggestions = " ".join(result["suggestions"])
        assert "structure" in suggestions.lower() or "section" in suggestions.lower() or "specifie" in suggestions.lower()


# ===========================================================================
# Refresh
# ===========================================================================

class TestRefresh:
    def test_refresh_clears_cache(self, opt):
        opt._insights_cache["test"] = PromptInsight("test", (10, 100), [], [], "", 0, 0, 0, "single")
        opt.refresh()
        assert "test" not in opt._insights_cache


# ===========================================================================
# Table creation
# ===========================================================================

class TestTableCreation:
    def test_table_created(self, opt, tmp_path):
        import sqlite3
        db = sqlite3.connect(str(tmp_path / "test_opt.db"))
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "prompt_optimization_log" in tables
        db.close()
