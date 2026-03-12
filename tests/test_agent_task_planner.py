"""Tests for src/agent_task_planner.py — Task decomposition and planning.

Covers: SubTask, TaskPlan (summary), PlanResult (summary), DECOMPOSITION_RULES,
TaskPlanner (_assess_complexity, _decompose, _assign_groups, _enrich_prompt,
plan, plan_to_dict).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_task_planner import (
    SubTask, TaskPlan, PlanResult, DECOMPOSITION_RULES, TaskPlanner,
)


# ===========================================================================
# SubTask
# ===========================================================================

class TestSubTask:
    def test_defaults(self):
        st = SubTask(id=0, name="test", description="desc",
                     pattern="code", estimated_ms=5000)
        assert st.depends_on == []
        assert st.parallel_group == 0
        assert st.priority == 1
        assert st.result is None
        assert st.ok is False
        assert st.actual_ms == 0

    def test_with_dependencies(self):
        st = SubTask(id=2, name="verify", description="Check",
                     pattern="reasoning", estimated_ms=3000,
                     depends_on=[0, 1], parallel_group=1)
        assert st.depends_on == [0, 1]
        assert st.parallel_group == 1


# ===========================================================================
# TaskPlan
# ===========================================================================

class TestTaskPlan:
    def test_summary(self):
        plan = TaskPlan(
            original_prompt="test", complexity="medium",
            sub_tasks=[SubTask(0, "a", "d", "code", 5000)],
            total_estimated_ms=5000, parallel_groups=1,
            sequential_steps=1,
        )
        s = plan.summary
        assert "1 sub-tasks" in s
        assert "medium" in s
        assert "5000ms" in s

    def test_empty_plan(self):
        plan = TaskPlan("q", "nano", [], 0, 0, 0)
        assert "0 sub-tasks" in plan.summary


# ===========================================================================
# PlanResult
# ===========================================================================

class TestPlanResult:
    def test_summary(self):
        plan = TaskPlan("q", "small", [], 0, 0, 0)
        result = PlanResult(
            plan=plan, results=[], total_ms=1500.0,
            ok=True, final_output="done",
            steps_ok=3, steps_total=4,
        )
        s = result.summary
        assert "3/4" in s
        assert "1500ms" in s
        assert "small" in s


# ===========================================================================
# DECOMPOSITION_RULES
# ===========================================================================

class TestDecompositionRules:
    def test_not_empty(self):
        assert len(DECOMPOSITION_RULES) >= 4

    def test_structure(self):
        for rule in DECOMPOSITION_RULES:
            assert "keywords" in rule
            assert "name" in rule
            assert "steps" in rule
            assert len(rule["keywords"]) >= 1
            assert len(rule["steps"]) >= 2

    def test_steps_format(self):
        for rule in DECOMPOSITION_RULES:
            for step in rule["steps"]:
                assert len(step) == 3  # (name, pattern, description)

    def test_has_api_rule(self):
        api_rules = [r for r in DECOMPOSITION_RULES if "api" in r["keywords"]]
        assert len(api_rules) >= 1

    def test_has_trading_rule(self):
        trading_rules = [r for r in DECOMPOSITION_RULES if "trading" in r["keywords"]]
        assert len(trading_rules) >= 1


# ===========================================================================
# TaskPlanner — _assess_complexity
# ===========================================================================

class TestAssessComplexity:
    def setup_method(self):
        with patch("src.agent_task_planner.PatternAgentRegistry"):
            self.planner = TaskPlanner()

    def test_nano(self):
        assert self.planner._assess_complexity("hello") == "nano"

    def test_micro(self):
        assert self.planner._assess_complexity("x" * 30) == "micro"

    def test_small(self):
        assert self.planner._assess_complexity("x" * 60) == "small"

    def test_medium(self):
        assert self.planner._assess_complexity("x" * 150) == "medium"

    def test_large(self):
        assert self.planner._assess_complexity("x" * 400) == "large"

    def test_xl(self):
        assert self.planner._assess_complexity("x" * 600) == "xl"


# ===========================================================================
# TaskPlanner — _decompose
# ===========================================================================

class TestDecompose:
    def setup_method(self):
        with patch("src.agent_task_planner.PatternAgentRegistry"):
            self.planner = TaskPlanner()

    def test_api_keyword_decomposition(self):
        tasks = self.planner._decompose("Cree une API REST securisee", "medium")
        assert len(tasks) >= 3
        patterns = [t.pattern for t in tasks]
        assert "code" in patterns

    def test_trading_keyword_decomposition(self):
        tasks = self.planner._decompose("position trading crypto signal BTC", "medium")
        assert len(tasks) >= 2
        patterns = [t.pattern for t in tasks]
        assert "trading" in patterns

    def test_nano_no_decomposition(self):
        tasks = self.planner._decompose("bonjour", "nano")
        assert tasks == []

    def test_micro_no_decomposition(self):
        tasks = self.planner._decompose("dis moi l'heure", "micro")
        assert tasks == []

    def test_medium_default_three_steps(self):
        tasks = self.planner._decompose("Explique le fonctionnement de la memoire virtuelle en detail", "medium")
        # Default: classify + execute + verify
        assert len(tasks) == 3
        assert tasks[0].name == "classify"
        assert tasks[1].name == "execute"
        assert tasks[2].name == "verify"

    def test_dependencies_sequential(self):
        tasks = self.planner._decompose("Cree une API REST", "medium")
        for i, t in enumerate(tasks):
            if i > 0:
                assert i - 1 in t.depends_on


# ===========================================================================
# TaskPlanner — _assign_groups
# ===========================================================================

class TestAssignGroups:
    def setup_method(self):
        with patch("src.agent_task_planner.PatternAgentRegistry"):
            self.planner = TaskPlanner()

    def test_no_deps_group_zero(self):
        tasks = [SubTask(0, "a", "d", "code", 1000)]
        self.planner._assign_groups(tasks)
        assert tasks[0].parallel_group == 0

    def test_sequential_deps(self):
        tasks = [
            SubTask(0, "a", "d", "code", 1000),
            SubTask(1, "b", "d", "code", 1000, depends_on=[0]),
            SubTask(2, "c", "d", "code", 1000, depends_on=[1]),
        ]
        self.planner._assign_groups(tasks)
        assert tasks[0].parallel_group == 0
        assert tasks[1].parallel_group == 1
        assert tasks[2].parallel_group == 2

    def test_parallel_no_deps(self):
        tasks = [
            SubTask(0, "a", "d", "code", 1000),
            SubTask(1, "b", "d", "code", 1000),
            SubTask(2, "c", "d", "code", 1000),
        ]
        self.planner._assign_groups(tasks)
        # All in group 0 since no deps
        assert all(t.parallel_group == 0 for t in tasks)


# ===========================================================================
# TaskPlanner — _enrich_prompt
# ===========================================================================

class TestEnrichPrompt:
    def setup_method(self):
        with patch("src.agent_task_planner.PatternAgentRegistry"):
            self.planner = TaskPlanner()

    def test_basic(self):
        st = SubTask(0, "test", "Do the test", "code", 1000)
        result = self.planner._enrich_prompt(st, "original", "original", [])
        assert "Do the test" in result

    def test_with_different_prev_content(self):
        st = SubTask(1, "verify", "Verify output", "reasoning", 1000)
        result = self.planner._enrich_prompt(st, "original prompt", "different content", [])
        assert "Original request:" in result

    def test_with_completed_steps(self):
        st = SubTask(1, "verify", "Check result", "reasoning", 1000)
        prev = SubTask(0, "code", "Write code", "code", 1000)
        prev.ok = True
        prev.result = "def foo(): return 42"
        result = self.planner._enrich_prompt(st, "original", "original", [prev])
        assert "Previous step" in result
        assert "def foo()" in result


# ===========================================================================
# TaskPlanner — plan
# ===========================================================================

class TestPlan:
    def test_simple_prompt(self):
        with patch("src.agent_task_planner.PatternAgentRegistry"):
            planner = TaskPlanner()
        plan = planner.plan("bonjour")
        assert plan.complexity == "nano"
        assert len(plan.sub_tasks) == 0

    def test_complex_prompt(self):
        with patch("src.agent_task_planner.PatternAgentRegistry"):
            planner = TaskPlanner()
        plan = planner.plan("Cree une API REST avec authentification JWT et tests unitaires complets pour le projet JARVIS qui gere les commandes vocales et les pipelines de trading automatise")
        assert plan.complexity in ("medium", "large", "xl")
        assert len(plan.sub_tasks) >= 3
        assert plan.total_estimated_ms > 0
        assert plan.parallel_groups >= 1


# ===========================================================================
# TaskPlanner — plan_to_dict
# ===========================================================================

class TestPlanToDict:
    def test_basic(self):
        with patch("src.agent_task_planner.PatternAgentRegistry"):
            planner = TaskPlanner()
        plan = planner.plan("Analyse le code pour la securite du serveur web")
        d = planner.plan_to_dict(plan)
        assert "prompt" in d
        assert "complexity" in d
        assert "sub_tasks" in d
        assert "summary" in d
        assert isinstance(d["sub_tasks"], list)

    def test_subtask_fields(self):
        with patch("src.agent_task_planner.PatternAgentRegistry"):
            planner = TaskPlanner()
        plan = planner.plan("Cree une API REST securisee")
        d = planner.plan_to_dict(plan)
        if d["sub_tasks"]:
            st = d["sub_tasks"][0]
            assert "id" in st
            assert "name" in st
            assert "pattern" in st
            assert "estimated_ms" in st
            assert "depends_on" in st
            assert "group" in st
