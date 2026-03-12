"""Tests for src/agent_orchestrator_v3.py — Multi-pipeline orchestration.

Covers: StepResult, OrchestratorResult, OrchestratorStep dataclasses,
WORKFLOWS, Orchestrator (_auto_select_workflow, _fill_template,
_build_parallel_groups, list_workflows).
"""

from __future__ import annotations

import sys
from dataclasses import field
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_orchestrator_v3 import (
    StepResult, OrchestratorResult, OrchestratorStep,
    WORKFLOWS, Orchestrator,
)


# ===========================================================================
# StepResult
# ===========================================================================

class TestStepResult:
    def test_defaults(self):
        sr = StepResult(
            step_name="test", pattern="code", node="M1",
            content="hello", latency_ms=100.0, ok=True,
        )
        assert sr.quality == 0.0
        assert sr.metadata == {}

    def test_with_quality(self):
        sr = StepResult(
            step_name="s", pattern="p", node="OL1",
            content="x", latency_ms=50.0, ok=True, quality=0.85,
        )
        assert sr.quality == 0.85


# ===========================================================================
# OrchestratorResult
# ===========================================================================

class TestOrchestratorResult:
    def test_summary(self):
        steps = [
            StepResult("s1", "code", "M1", "hello", 100, True),
            StepResult("s2", "reasoning", "OL1", "world", 200, True),
        ]
        result = OrchestratorResult(
            steps=steps,
            final_content="world",
            total_latency_ms=300,
            strategy_used="deep-analysis",
            patterns_used=["code", "reasoning"],
            nodes_used=["M1", "OL1"],
            ok=True,
        )
        summary = result.summary
        assert "2 steps" in summary
        assert "300ms" in summary
        assert "M1" in summary
        assert "OL1" in summary

    def test_ok_false(self):
        result = OrchestratorResult(
            steps=[], final_content="", total_latency_ms=0,
            strategy_used="auto", patterns_used=[], nodes_used=[], ok=False,
        )
        assert result.ok is False


# ===========================================================================
# OrchestratorStep
# ===========================================================================

class TestOrchestratorStep:
    def test_defaults(self):
        step = OrchestratorStep(
            name="test", pattern="code",
            prompt_template="Analyse: {original_prompt}",
        )
        assert step.condition is None
        assert step.parallel_with == []
        assert step.node_override is None
        assert step.max_tokens == 1024
        assert step.timeout_s == 120

    def test_with_parallel(self):
        step = OrchestratorStep(
            name="agent1", pattern="code",
            prompt_template="{original_prompt}",
            parallel_with=["agent2", "agent3"],
            node_override="M1",
        )
        assert len(step.parallel_with) == 2
        assert step.node_override == "M1"


# ===========================================================================
# WORKFLOWS
# ===========================================================================

class TestWorkflows:
    def test_required_workflows(self):
        for wf in ("auto", "deep-analysis", "code-generate",
                    "consensus-3", "quick-verify"):
            assert wf in WORKFLOWS, f"Missing workflow: {wf}"

    def test_auto_is_empty(self):
        assert WORKFLOWS["auto"] == []

    def test_deep_analysis_steps(self):
        steps = WORKFLOWS["deep-analysis"]
        assert len(steps) == 3
        names = [s.name for s in steps]
        assert "classify" in names
        assert "analyze" in names
        assert "verify" in names

    def test_code_generate_steps(self):
        steps = WORKFLOWS["code-generate"]
        assert len(steps) == 3
        patterns = [s.pattern for s in steps]
        assert "code" in patterns
        assert "reasoning" in patterns

    def test_consensus_has_parallel(self):
        steps = WORKFLOWS["consensus-3"]
        assert any(s.parallel_with for s in steps)

    def test_all_steps_have_pattern(self):
        for wf_name, steps in WORKFLOWS.items():
            for step in steps:
                assert step.pattern, f"{wf_name}/{step.name}: empty pattern"

    def test_templates_have_placeholder(self):
        for wf_name, steps in WORKFLOWS.items():
            for step in steps:
                assert "{original_prompt}" in step.prompt_template or \
                       "{prev_content}" in step.prompt_template, \
                    f"{wf_name}/{step.name}: no placeholder"


# ===========================================================================
# Orchestrator — _auto_select_workflow
# ===========================================================================

class TestAutoSelectWorkflow:
    def setup_method(self):
        with patch("src.agent_orchestrator_v3.PatternAgentRegistry"), \
             patch("src.agent_orchestrator_v3.get_router"), \
             patch("src.agent_orchestrator_v3.get_monitor"):
            self.orch = Orchestrator()

    def test_security(self):
        assert self.orch._auto_select_workflow("audit securite") == "security-audit"

    def test_trading(self):
        assert self.orch._auto_select_workflow("analyse trading btc") == "trading-full"

    def test_code(self):
        assert self.orch._auto_select_workflow("ecris une fonction python") == "code-generate"

    def test_analysis(self):
        assert self.orch._auto_select_workflow("analyse ce rapport") == "deep-analysis"

    def test_consensus(self):
        assert self.orch._auto_select_workflow("donne moi un consensus") == "consensus-3"

    def test_short_prompt(self):
        result = self.orch._auto_select_workflow("bonjour")
        assert result == "quick-verify"

    def test_long_unknown(self):
        result = self.orch._auto_select_workflow("x " * 30)
        assert result == "deep-analysis"


# ===========================================================================
# Orchestrator — _fill_template
# ===========================================================================

class TestFillTemplate:
    def setup_method(self):
        with patch("src.agent_orchestrator_v3.PatternAgentRegistry"), \
             patch("src.agent_orchestrator_v3.get_router"), \
             patch("src.agent_orchestrator_v3.get_monitor"):
            self.orch = Orchestrator()

    def test_fill_original(self):
        result = self.orch._fill_template(
            "Analyse: {original_prompt}", "test prompt", [],
        )
        assert result == "Analyse: test prompt"

    def test_fill_prev_content(self):
        prev = [StepResult("s1", "p", "M1", "prev answer", 100, True)]
        result = self.orch._fill_template(
            "Check: {prev_content}", "original", prev,
        )
        assert "prev answer" in result

    def test_fill_both(self):
        prev = [StepResult("s1", "p", "M1", "analysis", 100, True)]
        result = self.orch._fill_template(
            "Q: {original_prompt}\nA: {prev_content}", "question", prev,
        )
        assert "question" in result
        assert "analysis" in result

    def test_empty_prev(self):
        result = self.orch._fill_template(
            "A: {prev_content}", "q", [],
        )
        assert "{prev_content}" not in result

    def test_truncates_long_prev(self):
        prev = [StepResult("s1", "p", "M1", "x" * 5000, 100, True)]
        result = self.orch._fill_template("{prev_content}", "q", prev)
        # Content is truncated to 2000
        assert len(result) <= 2001


# ===========================================================================
# Orchestrator — _build_parallel_groups
# ===========================================================================

class TestBuildParallelGroups:
    def setup_method(self):
        with patch("src.agent_orchestrator_v3.PatternAgentRegistry"), \
             patch("src.agent_orchestrator_v3.get_router"), \
             patch("src.agent_orchestrator_v3.get_monitor"):
            self.orch = Orchestrator()

    def test_sequential_steps(self):
        steps = [
            OrchestratorStep("s1", "code", "{original_prompt}"),
            OrchestratorStep("s2", "reasoning", "{prev_content}"),
        ]
        groups = self.orch._build_parallel_groups(steps)
        assert len(groups) >= 1  # At least one group

    def test_parallel_steps(self):
        # Use the actual consensus-3 workflow which has known parallel structure
        steps = WORKFLOWS["consensus-3"]
        groups = self.orch._build_parallel_groups(steps)
        # All steps in consensus should be grouped together
        total_steps = sum(len(g) for g in groups)
        assert total_steps == len(steps)

    def test_empty_steps(self):
        groups = self.orch._build_parallel_groups([])
        assert groups == [] or groups == [[]]

    def test_consensus_workflow(self):
        steps = WORKFLOWS["consensus-3"]
        groups = self.orch._build_parallel_groups(steps)
        # Consensus should have a parallel group
        all_steps = sum(len(g) for g in groups)
        assert all_steps == len(steps)


# ===========================================================================
# Orchestrator — list_workflows
# ===========================================================================

class TestListWorkflows:
    def setup_method(self):
        with patch("src.agent_orchestrator_v3.PatternAgentRegistry"), \
             patch("src.agent_orchestrator_v3.get_router"), \
             patch("src.agent_orchestrator_v3.get_monitor"):
            self.orch = Orchestrator()

    def test_returns_dict(self):
        wf = self.orch.list_workflows()
        assert isinstance(wf, dict)

    def test_excludes_auto(self):
        wf = self.orch.list_workflows()
        assert "auto" not in wf  # auto has empty steps

    def test_workflow_info(self):
        wf = self.orch.list_workflows()
        for name, info in wf.items():
            assert "steps" in info
            assert "patterns" in info
            assert "parallel" in info
            assert info["steps"] > 0

    def test_consensus_is_parallel(self):
        wf = self.orch.list_workflows()
        assert wf["consensus-3"]["parallel"] is True
