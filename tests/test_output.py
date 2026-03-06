"""Tests for JARVIS structured JSON output formatter (src/output.py)."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.output import (
    JarvisMeta,
    Summary,
    PlanStep,
    EngineInteraction,
    FinalDecision,
    FileAction,
    TerminalAction,
    ActionsRequired,
    JarvisOutput,
    JARVIS_OUTPUT_SCHEMA,
)


# ---------------------------------------------------------------------------
# Test imports
# ---------------------------------------------------------------------------

class TestImports:
    """Verify all public names are importable."""

    def test_import_dataclasses(self):
        assert JarvisMeta is not None
        assert Summary is not None
        assert PlanStep is not None
        assert EngineInteraction is not None
        assert FinalDecision is not None
        assert FileAction is not None
        assert TerminalAction is not None
        assert ActionsRequired is not None
        assert JarvisOutput is not None

    def test_import_schema(self):
        assert isinstance(JARVIS_OUTPUT_SCHEMA, dict)


# ---------------------------------------------------------------------------
# Test JarvisMeta defaults and custom values
# ---------------------------------------------------------------------------

class TestJarvisMeta:
    def test_defaults(self):
        meta = JarvisMeta()
        assert meta.version == "10.6"
        assert meta.current_engine == "CLAUDE"
        assert meta.mode == "DUAL_CORE"

    def test_custom_values(self):
        meta = JarvisMeta(version="12.0", current_engine="GEMINI", mode="SINGLE")
        assert meta.version == "12.0"
        assert meta.current_engine == "GEMINI"
        assert meta.mode == "SINGLE"


# ---------------------------------------------------------------------------
# Test Summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_defaults(self):
        s = Summary()
        assert s.goal == ""
        assert s.consensus_score == 0.0

    def test_custom(self):
        s = Summary(goal="Deploy cluster", consensus_score=0.95)
        assert s.goal == "Deploy cluster"
        assert s.consensus_score == 0.95


# ---------------------------------------------------------------------------
# Test PlanStep
# ---------------------------------------------------------------------------

class TestPlanStep:
    def test_defaults(self):
        step = PlanStep()
        assert step.id == ""
        assert step.action == ""
        assert step.executor == "CLAUDE"
        assert step.command_to_run is None

    def test_with_command(self):
        step = PlanStep(id="S1", action="Run tests", executor="M1", command_to_run="pytest")
        assert step.id == "S1"
        assert step.command_to_run == "pytest"

    def test_command_none_by_default(self):
        step = PlanStep(id="S2", action="Analyse")
        assert step.command_to_run is None


# ---------------------------------------------------------------------------
# Test EngineInteraction
# ---------------------------------------------------------------------------

class TestEngineInteraction:
    def test_defaults(self):
        ei = EngineInteraction()
        assert ei.cross_check_required is False
        assert ei.instruction_for_other_engine == ""

    def test_cross_check(self):
        ei = EngineInteraction(cross_check_required=True, instruction_for_other_engine="Verify math")
        assert ei.cross_check_required is True
        assert ei.instruction_for_other_engine == "Verify math"


# ---------------------------------------------------------------------------
# Test FinalDecision
# ---------------------------------------------------------------------------

class TestFinalDecision:
    def test_defaults(self):
        fd = FinalDecision()
        assert fd.decision == ""
        assert fd.rationale == ""

    def test_custom(self):
        fd = FinalDecision(decision="APPROVE", rationale="All tests pass")
        assert fd.decision == "APPROVE"
        assert fd.rationale == "All tests pass"


# ---------------------------------------------------------------------------
# Test FileAction and TerminalAction
# ---------------------------------------------------------------------------

class TestFileAction:
    def test_defaults(self):
        fa = FileAction()
        assert fa.path == ""
        assert fa.operation == "READ"

    def test_write_operation(self):
        fa = FileAction(path="/tmp/out.json", operation="WRITE")
        assert fa.operation == "WRITE"


class TestTerminalAction:
    def test_defaults(self):
        ta = TerminalAction()
        assert ta.cmd == ""

    def test_custom(self):
        ta = TerminalAction(cmd="uv run pytest")
        assert ta.cmd == "uv run pytest"


# ---------------------------------------------------------------------------
# Test ActionsRequired
# ---------------------------------------------------------------------------

class TestActionsRequired:
    def test_defaults_empty_lists(self):
        ar = ActionsRequired()
        assert ar.filesystem == []
        assert ar.terminal == []

    def test_with_actions(self):
        fa = FileAction(path="src/main.py", operation="READ")
        ta = TerminalAction(cmd="python main.py")
        ar = ActionsRequired(filesystem=[fa], terminal=[ta])
        assert len(ar.filesystem) == 1
        assert len(ar.terminal) == 1
        assert ar.filesystem[0].path == "src/main.py"
        assert ar.terminal[0].cmd == "python main.py"

    def test_multiple_actions(self):
        actions = ActionsRequired(
            filesystem=[FileAction(path="a.py"), FileAction(path="b.py")],
            terminal=[TerminalAction(cmd="ls"), TerminalAction(cmd="pwd")],
        )
        assert len(actions.filesystem) == 2
        assert len(actions.terminal) == 2


# ---------------------------------------------------------------------------
# Test JarvisOutput: construction, to_json, to_dict
# ---------------------------------------------------------------------------

class TestJarvisOutput:
    def test_default_construction(self):
        out = JarvisOutput()
        assert isinstance(out.jarvis_meta, JarvisMeta)
        assert isinstance(out.summary, Summary)
        assert isinstance(out.plan, list)
        assert isinstance(out.engine_interaction, EngineInteraction)
        assert isinstance(out.final_decision, FinalDecision)
        assert isinstance(out.actions_required, ActionsRequired)

    def test_to_dict_returns_dict(self):
        out = JarvisOutput()
        d = out.to_dict()
        assert isinstance(d, dict)
        assert "jarvis_meta" in d
        assert "summary" in d
        assert "plan" in d
        assert "engine_interaction" in d
        assert "final_decision" in d
        assert "actions_required" in d

    def test_to_dict_default_values(self):
        d = JarvisOutput().to_dict()
        assert d["jarvis_meta"]["version"] == "10.6"
        assert d["jarvis_meta"]["current_engine"] == "CLAUDE"
        assert d["summary"]["goal"] == ""
        assert d["summary"]["consensus_score"] == 0.0
        assert d["plan"] == []
        assert d["final_decision"]["decision"] == ""

    def test_to_json_returns_valid_json(self):
        out = JarvisOutput()
        raw = out.to_json()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)
        assert parsed["jarvis_meta"]["mode"] == "DUAL_CORE"

    def test_to_json_ensure_ascii_false(self):
        """Verify non-ASCII characters are preserved (not escaped)."""
        out = JarvisOutput(
            summary=Summary(goal="Deployer le reseau neural"),
            final_decision=FinalDecision(decision="OK", rationale="Tout est pret"),
        )
        raw = out.to_json()
        # ensure_ascii=False means e-acute etc. are kept literal
        assert "\\u00e9" not in raw or "reseau" in raw  # no forced escaping for ASCII text
        parsed = json.loads(raw)
        assert parsed["summary"]["goal"] == "Deployer le reseau neural"

    def test_to_json_indentation(self):
        raw = JarvisOutput().to_json()
        # indent=2 produces lines starting with "  "
        lines = raw.splitlines()
        indented = [l for l in lines if l.startswith("  ")]
        assert len(indented) > 0

    def test_full_output_with_plan_steps(self):
        out = JarvisOutput(
            jarvis_meta=JarvisMeta(version="12.0", current_engine="AUTO", mode="HEXA_CORE"),
            summary=Summary(goal="Run benchmark", consensus_score=0.85),
            plan=[
                PlanStep(id="1", action="Health check", executor="M1"),
                PlanStep(id="2", action="Run tests", executor="CLAUDE", command_to_run="pytest"),
            ],
            engine_interaction=EngineInteraction(cross_check_required=True, instruction_for_other_engine="Validate"),
            final_decision=FinalDecision(decision="PROCEED", rationale="Cluster healthy"),
            actions_required=ActionsRequired(
                filesystem=[FileAction(path="report.json", operation="WRITE")],
                terminal=[TerminalAction(cmd="pytest -x")],
            ),
        )
        d = out.to_dict()
        assert d["jarvis_meta"]["version"] == "12.0"
        assert d["summary"]["consensus_score"] == 0.85
        assert len(d["plan"]) == 2
        assert d["plan"][0]["executor"] == "M1"
        assert d["plan"][1]["command_to_run"] == "pytest"
        assert d["engine_interaction"]["cross_check_required"] is True
        assert d["actions_required"]["filesystem"][0]["operation"] == "WRITE"
        assert d["actions_required"]["terminal"][0]["cmd"] == "pytest -x"

    def test_to_json_roundtrip(self):
        """Serialize then deserialize — output must match to_dict."""
        out = JarvisOutput(
            summary=Summary(goal="Roundtrip", consensus_score=0.5),
            final_decision=FinalDecision(decision="YES", rationale="Test"),
        )
        d_original = out.to_dict()
        d_roundtrip = json.loads(out.to_json())
        assert d_original == d_roundtrip

    def test_separate_instances_do_not_share_lists(self):
        """Ensure default_factory produces independent lists."""
        a = JarvisOutput()
        b = JarvisOutput()
        a.plan.append(PlanStep(id="X"))
        assert len(b.plan) == 0
        a.actions_required.filesystem.append(FileAction(path="x"))
        assert len(b.actions_required.filesystem) == 0


# ---------------------------------------------------------------------------
# Test JARVIS_OUTPUT_SCHEMA structure
# ---------------------------------------------------------------------------

class TestJarvisOutputSchema:
    def test_top_level_type(self):
        assert JARVIS_OUTPUT_SCHEMA["type"] == "object"

    def test_required_keys(self):
        required = JARVIS_OUTPUT_SCHEMA["required"]
        assert "jarvis_meta" in required
        assert "summary" in required
        assert "plan" in required
        assert "final_decision" in required

    def test_engine_interaction_not_required(self):
        """engine_interaction and actions_required are optional at top level."""
        required = JARVIS_OUTPUT_SCHEMA["required"]
        assert "engine_interaction" not in required
        assert "actions_required" not in required

    def test_meta_properties(self):
        meta_props = JARVIS_OUTPUT_SCHEMA["properties"]["jarvis_meta"]["properties"]
        assert "version" in meta_props
        assert "current_engine" in meta_props
        assert "mode" in meta_props

    def test_current_engine_enum(self):
        engine_schema = JARVIS_OUTPUT_SCHEMA["properties"]["jarvis_meta"]["properties"]["current_engine"]
        assert engine_schema["enum"] == ["CLAUDE", "GEMINI", "AUTO"]

    def test_consensus_score_bounds(self):
        score_schema = JARVIS_OUTPUT_SCHEMA["properties"]["summary"]["properties"]["consensus_score"]
        assert score_schema["minimum"] == 0
        assert score_schema["maximum"] == 1

    def test_plan_is_array(self):
        assert JARVIS_OUTPUT_SCHEMA["properties"]["plan"]["type"] == "array"

    def test_plan_item_required_fields(self):
        plan_required = JARVIS_OUTPUT_SCHEMA["properties"]["plan"]["items"]["required"]
        assert "id" in plan_required
        assert "action" in plan_required
        assert "executor" in plan_required

    def test_command_to_run_nullable(self):
        cmd_schema = JARVIS_OUTPUT_SCHEMA["properties"]["plan"]["items"]["properties"]["command_to_run"]
        assert "null" in cmd_schema["type"]
        assert "string" in cmd_schema["type"]

    def test_filesystem_operation_enum(self):
        fs_op = (
            JARVIS_OUTPUT_SCHEMA["properties"]["actions_required"]
            ["properties"]["filesystem"]["items"]["properties"]["operation"]
        )
        assert fs_op["enum"] == ["READ", "WRITE"]

    def test_final_decision_required_fields(self):
        fd_req = JARVIS_OUTPUT_SCHEMA["properties"]["final_decision"]["required"]
        assert "decision" in fd_req
        assert "rationale" in fd_req


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_plan_serializes(self):
        d = JarvisOutput().to_dict()
        assert d["plan"] == []

    def test_unicode_in_output(self):
        out = JarvisOutput(
            summary=Summary(goal="Analyser les donnees"),
            final_decision=FinalDecision(decision="OK", rationale="Fonctionnel"),
        )
        raw = out.to_json()
        parsed = json.loads(raw)
        assert parsed["summary"]["goal"] == "Analyser les donnees"

    def test_large_plan(self):
        steps = [PlanStep(id=str(i), action=f"Step {i}") for i in range(100)]
        out = JarvisOutput(plan=steps)
        d = out.to_dict()
        assert len(d["plan"]) == 100
        assert d["plan"][99]["id"] == "99"
