"""Unit tests for src/commander.py — JARVIS Commander v2 orchestration.

Tests classification, decomposition, thermal throttling, cost estimation,
topological sort, and prompt building with ALL external dependencies mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCommanderImport:
    """Verify the module imports cleanly."""

    def test_import_module(self):
        import src.commander
        assert hasattr(src.commander, "classify_task")
        assert hasattr(src.commander, "decompose_task")
        assert hasattr(src.commander, "build_commander_enrichment")

    def test_valid_types_defined(self):
        from src.commander import VALID_TYPES
        assert isinstance(VALID_TYPES, set)
        assert "code" in VALID_TYPES
        assert "trading" in VALID_TYPES
        assert "simple" in VALID_TYPES


class TestDataStructures:
    """Test TaskUnit and CommanderResult dataclasses."""

    def test_task_unit_instantiation(self):
        from src.commander import TaskUnit
        task = TaskUnit(id="t1", prompt="test", task_type="code", target="M1")
        assert task.id == "t1"
        assert task.status == "pending"
        assert task.priority == 1
        assert task.depends_on == []
        assert task.estimated_cost == 0.0

    def test_commander_result_instantiation(self):
        from src.commander import CommanderResult
        result = CommanderResult(
            tasks=[], synthesis="done", quality_score=0.9,
            total_time_ms=500, agents_used=["M1"]
        )
        assert result.quality_score == 0.9
        assert result.total_cost == 0.0

    def test_agent_stats_properties(self):
        from src.commander import AgentStats
        stats = AgentStats(successes=8, failures=2, total_duration_ms=5000, total_quality=7.5)
        assert stats.success_rate == 0.8
        assert stats.avg_quality == 0.75
        assert stats.avg_duration_ms == 500.0

    def test_agent_stats_serialization(self):
        from src.commander import AgentStats
        stats = AgentStats(successes=5, failures=1, total_duration_ms=3000, total_quality=4.2)
        d = stats.to_dict()
        assert d["successes"] == 5
        restored = AgentStats.from_dict(d)
        assert restored.successes == 5
        assert restored.failures == 1


class TestClassifyHeuristic:
    """Test _classify_heuristic() with various inputs — no network needed."""

    def test_classify_code(self):
        from src.commander import _classify_heuristic
        assert _classify_heuristic("debug cette erreur python") == "code"
        assert _classify_heuristic("ecris une fonction de tri") == "code"
        assert _classify_heuristic("refactor le module config") == "code"

    def test_classify_trading(self):
        from src.commander import _classify_heuristic
        assert _classify_heuristic("signal trading BTC") == "trading"
        assert _classify_heuristic("scanner MEXC futures") == "trading"
        assert _classify_heuristic("analyse le prix du btc") == "trading"

    def test_classify_system(self):
        from src.commander import _classify_heuristic
        assert _classify_heuristic("ouvre le dossier bureau") == "systeme"
        assert _classify_heuristic("ferme l'application chrome") == "systeme"
        assert _classify_heuristic("lance powershell") == "systeme"

    def test_classify_analyse(self):
        from src.commander import _classify_heuristic
        assert _classify_heuristic("analyse l'architecture du projet") == "analyse"
        assert _classify_heuristic("benchmark les performances") == "analyse"

    def test_classify_web(self):
        from src.commander import _classify_heuristic
        assert _classify_heuristic("cherche sur le web les nouvelles") == "web"
        assert _classify_heuristic("actualite crypto aujourd'hui") == "web"

    def test_classify_simple(self):
        from src.commander import _classify_heuristic
        assert _classify_heuristic("bonjour comment vas-tu") == "simple"
        assert _classify_heuristic("quelle heure est-il") == "simple"

    def test_code_overrides_trading(self):
        """Code-strong keywords should override trading context."""
        from src.commander import _classify_heuristic
        assert _classify_heuristic("debug le bug dans le module trading") == "code"

    def test_web_overrides_trading(self):
        """Web-strong keywords should override trading context."""
        from src.commander import _classify_heuristic
        assert _classify_heuristic("actualite news crypto bitcoin") == "web"


class TestClassifyTask:
    """Test classify_task() existence and signature."""

    def test_classify_task_is_async(self):
        """classify_task should be an async callable."""
        from src.commander import classify_task
        import asyncio
        assert asyncio.iscoroutinefunction(classify_task)


class TestThermalThrottling:
    """Test get_thermal_throttle_factor() progressive curve."""

    def test_cold_gpu(self):
        from src.commander import get_thermal_throttle_factor
        assert get_thermal_throttle_factor(40) == 1.0
        assert get_thermal_throttle_factor(65) == 1.0

    def test_warm_gpu(self):
        from src.commander import get_thermal_throttle_factor
        factor = get_thermal_throttle_factor(70)
        assert 0.5 < factor < 1.0, f"70C should give moderate throttle, got {factor}"

    def test_hot_gpu(self):
        from src.commander import get_thermal_throttle_factor
        factor = get_thermal_throttle_factor(80)
        assert 0.1 < factor < 0.5, f"80C should give heavy throttle, got {factor}"

    def test_critical_gpu(self):
        from src.commander import get_thermal_throttle_factor
        assert get_thermal_throttle_factor(90) == 0.1
        assert get_thermal_throttle_factor(100) == 0.1

    def test_boundary_values(self):
        from src.commander import get_thermal_throttle_factor
        # Exact boundary at 75C
        factor_75 = get_thermal_throttle_factor(75)
        assert abs(factor_75 - 0.7) < 0.01, f"75C should give ~0.7, got {factor_75}"
        # Exact boundary at 85C
        factor_85 = get_thermal_throttle_factor(85)
        assert abs(factor_85 - 0.1) < 0.01, f"85C should give ~0.1, got {factor_85}"


class TestCostEstimation:
    """Test estimate_task_cost() and MODEL_COSTS."""

    def test_local_models_are_free(self):
        from src.commander import MODEL_COSTS
        assert MODEL_COSTS["M1"] == 0.0
        assert MODEL_COSTS["M2"] == 0.0
        assert MODEL_COSTS["OL1"] == 0.0

    def test_estimate_cost_local(self):
        from src.commander import estimate_task_cost
        cost = estimate_task_cost("simple prompt", "M1")
        assert cost == 0.0, "Local model cost should be 0"

    def test_estimate_cost_cloud(self):
        from src.commander import estimate_task_cost
        cost = estimate_task_cost("analyse this architecture in detail", "CLAUDE")
        assert cost > 0, "Cloud model should have non-zero cost"

    def test_estimate_cost_proportional(self):
        from src.commander import estimate_task_cost
        short = estimate_task_cost("hi", "CLAUDE")
        long = estimate_task_cost("a " * 500, "CLAUDE")
        assert long > short, "Longer prompts should cost more"


class TestTopologicalSort:
    """Test topological_sort_tasks() — pure logic, no deps."""

    def test_independent_tasks_single_wave(self):
        from src.commander import TaskUnit, topological_sort_tasks
        tasks = [
            TaskUnit(id="t1", prompt="a", task_type="code", target="M1"),
            TaskUnit(id="t2", prompt="b", task_type="code", target="M2"),
        ]
        waves = topological_sort_tasks(tasks)
        assert len(waves) == 1
        assert len(waves[0]) == 2

    def test_dependent_tasks_two_waves(self):
        from src.commander import TaskUnit, topological_sort_tasks
        tasks = [
            TaskUnit(id="t1", prompt="code", task_type="code", target="M1"),
            TaskUnit(id="t2", prompt="review", task_type="code", target="M2", depends_on=["t1"]),
        ]
        waves = topological_sort_tasks(tasks)
        assert len(waves) == 2
        assert waves[0][0].id == "t1"
        assert waves[1][0].id == "t2"

    def test_cycle_detection(self):
        """Cyclic dependencies should still produce output (forced into one wave)."""
        from src.commander import TaskUnit, topological_sort_tasks
        tasks = [
            TaskUnit(id="t1", prompt="a", task_type="code", target="M1", depends_on=["t2"]),
            TaskUnit(id="t2", prompt="b", task_type="code", target="M2", depends_on=["t1"]),
        ]
        waves = topological_sort_tasks(tasks)
        # Should handle gracefully — all tasks must appear
        all_ids = {t.id for wave in waves for t in wave}
        assert all_ids == {"t1", "t2"}


class TestDecomposeTask:
    """Test decompose_task() with mocked thermal and config."""

    def test_decompose_simple_task(self):
        from src.commander import decompose_task

        mock_config = MagicMock()
        mock_config.commander_routing = {}

        with patch("src.config.config", mock_config), \
             patch("src.cluster_startup.check_thermal_status", return_value={"ok": True, "max_temp": 50}), \
             patch("src.commander._load_routing_stats", return_value={}):
            tasks = decompose_task("bonjour", "simple")
            assert len(tasks) >= 1
            assert tasks[0].task_type == "simple"
            assert tasks[0].id == "t1"

    def test_decompose_returns_task_units(self):
        from src.commander import decompose_task, TaskUnit

        mock_config = MagicMock()
        mock_config.commander_routing = {}

        with patch("src.config.config", mock_config), \
             patch("src.cluster_startup.check_thermal_status", return_value={"ok": True, "max_temp": 50}), \
             patch("src.commander._load_routing_stats", return_value={}):
            tasks = decompose_task("ecris du code python", "code")
            assert all(isinstance(t, TaskUnit) for t in tasks)


class TestBuildCommanderEnrichment:
    """Test build_commander_enrichment() output format."""

    def test_enrichment_contains_classification(self):
        from src.commander import build_commander_enrichment, TaskUnit
        tasks = [TaskUnit(id="t1", prompt="test code", task_type="code", target="M1")]
        result = build_commander_enrichment("ecris du code", "code", tasks)
        assert "Classification: code" in result
        assert "MODE COMMANDANT" in result

    def test_enrichment_contains_user_prompt(self):
        from src.commander import build_commander_enrichment, TaskUnit
        tasks = [TaskUnit(id="t1", prompt="test", task_type="simple", target="OL1")]
        result = build_commander_enrichment("bonjour jarvis", "simple", tasks)
        assert "bonjour jarvis" in result

    def test_enrichment_contains_dispatch_plan(self):
        from src.commander import build_commander_enrichment, TaskUnit
        tasks = [
            TaskUnit(id="t1", prompt="code", task_type="code", target="M1"),
            TaskUnit(id="t2", prompt="review", task_type="code", target="M2", depends_on=["t1"]),
        ]
        result = build_commander_enrichment("write code", "code", tasks)
        assert "PLAN DE DISPATCH" in result
        assert "2 taches" in result
        assert "DEPENDS:t1" in result

    def test_enrichment_with_pre_analysis(self):
        from src.commander import build_commander_enrichment, TaskUnit
        tasks = [TaskUnit(id="t1", prompt="test", task_type="analyse", target="M1")]
        result = build_commander_enrichment("analyse", "analyse", tasks, pre_analysis="M1 says X")
        assert "Pre-analyse M1: M1 says X" in result

    def test_enrichment_orders_section(self):
        from src.commander import build_commander_enrichment, TaskUnit
        tasks = [TaskUnit(id="t1", prompt="test", task_type="simple", target="OL1")]
        result = build_commander_enrichment("test", "simple", tasks)
        assert "ORDRES:" in result
        assert "Delegue TOUT" in result


class TestBuildTaskPrompt:
    """Test _build_task_prompt() role-based prompt construction."""

    def test_coder_role(self):
        from src.commander import _build_task_prompt
        result = _build_task_prompt("fix the bug", "coder", "code")
        assert "Ecris le code" in result
        assert "fix the bug" in result

    def test_reviewer_role(self):
        from src.commander import _build_task_prompt
        result = _build_task_prompt("check this", "reviewer", "code")
        assert "Review" in result
        assert "score de qualite" in result

    def test_unknown_role_returns_prompt(self):
        from src.commander import _build_task_prompt
        result = _build_task_prompt("hello world", "unknown_role", "simple")
        assert result == "hello world"


class TestGetBestAgent:
    """Test get_best_agent_for() adaptive routing logic."""

    def test_no_history_returns_first_candidate(self):
        from src.commander import get_best_agent_for
        with patch("src.commander._load_routing_stats", return_value={}):
            result = get_best_agent_for("code", ["M1", "M2", "OL1"])
            assert result == "M1"

    def test_with_history_returns_best(self):
        from src.commander import get_best_agent_for, AgentStats
        stats = {
            "code": {
                "M1": AgentStats(successes=9, failures=1, total_duration_ms=5000, total_quality=8.5),
                "M2": AgentStats(successes=3, failures=7, total_duration_ms=8000, total_quality=2.0),
            }
        }
        with patch("src.commander._load_routing_stats", return_value=stats):
            result = get_best_agent_for("code", ["M1", "M2"])
            assert result == "M1"

    def test_empty_candidates_returns_m1(self):
        from src.commander import get_best_agent_for
        with patch("src.commander._load_routing_stats", return_value={}):
            result = get_best_agent_for("code", [])
            assert result == "M1"


class TestVerificationPrompt:
    """Test build_verification_prompt() output."""

    def test_verification_prompt_format(self):
        from src.commander import build_verification_prompt, TaskUnit
        tasks = [
            TaskUnit(id="t1", prompt="x", task_type="code", target="M1",
                     status="done", result="code output here"),
        ]
        result = build_verification_prompt(tasks)
        assert "VERIFICATION QUALITE" in result
        assert "code output here" in result
        assert "JSON" in result


class TestSynthesisPrompt:
    """Test build_synthesis_prompt() output."""

    def test_synthesis_prompt_format(self):
        from src.commander import build_synthesis_prompt, TaskUnit
        tasks = [
            TaskUnit(id="t1", prompt="x", task_type="code", target="M1",
                     status="done", result="result A"),
            TaskUnit(id="t2", prompt="y", task_type="code", target="M2",
                     status="done", result="result B"),
        ]
        result = build_synthesis_prompt(tasks, 0.85)
        assert "SYNTHESE COMMANDANT" in result
        assert "result A" in result
        assert "result B" in result
        assert "0.85" in result
        assert "M1" in result
        assert "M2" in result
