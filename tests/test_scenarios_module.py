"""Comprehensive tests for src/scenarios.py — Scenario Engine.

Tests cover:
- SCENARIO_TEMPLATES data integrity
- _simulate_match logic (all branches)
- validate_scenario (pass/partial/fail/no-match)
- run_validation_cycle (with and without provided scenarios)
- run_50_cycles (full pipeline)
- Edge cases and boundary conditions
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Lightweight stand-ins for external dataclasses so we never import real deps
# ---------------------------------------------------------------------------
@dataclass
class _FakeCommand:
    name: str


@dataclass
class _FakeSkill:
    name: str


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_imports():
    """Patch all external dependencies imported at module level by scenarios.py."""
    with patch.dict("sys.modules", {}):  # ensure fresh import each time
        pass

    mock_db = MagicMock()
    mock_db.init_db = MagicMock()
    mock_db.add_scenario = MagicMock(return_value=1)
    mock_db.get_all_scenarios = MagicMock(return_value=[])
    mock_db.record_validation = MagicMock()
    mock_db.get_stats = MagicMock(return_value={
        "commands": 100, "skills": 20, "corrections": 50,
        "scenarios": 10, "scenarios_validated": 10,
        "validation_cycles": 50,
    })
    mock_db.get_validation_report = MagicMock(return_value={})
    mock_db.import_commands_from_code = MagicMock(return_value=100)
    mock_db.import_skills_from_code = MagicMock(return_value=20)
    mock_db.import_corrections_from_code = MagicMock(return_value=50)

    mock_commands = MagicMock()
    mock_commands.match_command = MagicMock(return_value=(None, {}, 0.0))
    mock_commands.correct_voice_text = MagicMock(side_effect=lambda t: t)

    mock_skills = MagicMock()
    mock_skills.find_skill = MagicMock(return_value=(None, 0.0))

    with patch("src.database.init_db", mock_db.init_db), \
         patch("src.database.add_scenario", mock_db.add_scenario), \
         patch("src.database.get_all_scenarios", mock_db.get_all_scenarios), \
         patch("src.database.record_validation", mock_db.record_validation), \
         patch("src.database.get_stats", mock_db.get_stats), \
         patch("src.database.get_validation_report", mock_db.get_validation_report), \
         patch("src.database.import_commands_from_code", mock_db.import_commands_from_code), \
         patch("src.database.import_skills_from_code", mock_db.import_skills_from_code), \
         patch("src.database.import_corrections_from_code", mock_db.import_corrections_from_code), \
         patch("src.commands.match_command", mock_commands.match_command), \
         patch("src.commands.correct_voice_text", mock_commands.correct_voice_text), \
         patch("src.skills.find_skill", mock_skills.find_skill):

        # Force reimport so module-level bindings pick up the mocks
        import importlib
        import src.scenarios as mod
        importlib.reload(mod)

        # Expose mocks for tests via a simple namespace
        class _Mocks:
            db = mock_db
            commands = mock_commands
            skills = mock_skills
            scenarios = mod

        yield _Mocks()


# ---------------------------------------------------------------------------
# Helper to build a minimal scenario dict
# ---------------------------------------------------------------------------
def _scenario(name="test_sc", voice_input="test input",
              expected=None, category="test", difficulty="easy",
              description="desc", expected_result="result"):
    return {
        "name": name,
        "voice_input": voice_input,
        "expected": expected or ["expected_cmd"],
        "category": category,
        "difficulty": difficulty,
        "description": description,
        "expected_result": expected_result,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. SCENARIO_TEMPLATES data integrity
# ═══════════════════════════════════════════════════════════════════════════

class TestScenarioTemplates:
    """Validate the static scenario data structure."""

    def test_templates_is_nonempty_list(self, _patch_imports):
        mod = _patch_imports.scenarios
        assert isinstance(mod.SCENARIO_TEMPLATES, list)
        assert len(mod.SCENARIO_TEMPLATES) > 100, "Should contain 100+ scenarios"

    def test_each_template_has_required_keys(self, _patch_imports):
        mod = _patch_imports.scenarios
        required = {"name", "category", "difficulty", "description",
                     "voice_input", "expected", "expected_result"}
        for i, tpl in enumerate(mod.SCENARIO_TEMPLATES):
            missing = required - set(tpl.keys())
            assert not missing, f"Template #{i} ({tpl.get('name','?')}) missing keys: {missing}"

    def test_unique_names(self, _patch_imports):
        mod = _patch_imports.scenarios
        names = [t["name"] for t in mod.SCENARIO_TEMPLATES]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(dupes) == 0, f"Duplicate scenario names: {set(dupes)}"

    def test_expected_is_list_of_strings(self, _patch_imports):
        mod = _patch_imports.scenarios
        for tpl in mod.SCENARIO_TEMPLATES:
            assert isinstance(tpl["expected"], list), f"{tpl['name']}: expected must be list"
            assert all(isinstance(e, str) for e in tpl["expected"]), f"{tpl['name']}: expected entries must be str"

    def test_difficulty_values(self, _patch_imports):
        mod = _patch_imports.scenarios
        valid = {"easy", "normal", "hard"}
        for tpl in mod.SCENARIO_TEMPLATES:
            assert tpl["difficulty"] in valid, f"{tpl['name']}: bad difficulty '{tpl['difficulty']}'"

    def test_voice_input_nonempty(self, _patch_imports):
        mod = _patch_imports.scenarios
        for tpl in mod.SCENARIO_TEMPLATES:
            assert tpl["voice_input"].strip(), f"{tpl['name']}: voice_input empty"

    def test_categories_are_strings(self, _patch_imports):
        mod = _patch_imports.scenarios
        for tpl in mod.SCENARIO_TEMPLATES:
            assert isinstance(tpl["category"], str) and tpl["category"].strip()


# ═══════════════════════════════════════════════════════════════════════════
# 2. _simulate_match
# ═══════════════════════════════════════════════════════════════════════════

class TestSimulateMatch:
    """Test the internal matching logic with all branch paths."""

    def test_no_match_returns_none(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        name, score, mtype = m.scenarios._simulate_match("unknown input")
        assert name is None
        assert score == 0.0
        assert mtype == "none"

    def test_command_match_above_threshold(self, _patch_imports):
        m = _patch_imports
        cmd = _FakeCommand(name="ouvrir_chrome")
        m.commands.match_command.return_value = (cmd, {}, 0.80)
        m.skills.find_skill.return_value = (None, 0.0)

        name, score, mtype = m.scenarios._simulate_match("ouvre chrome")
        assert name == "ouvrir_chrome"
        assert score == 0.80
        assert mtype == "command"

    def test_skill_match_above_065(self, _patch_imports):
        m = _patch_imports
        skill = _FakeSkill(name="mode_dev")
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (skill, 0.70)

        name, score, mtype = m.scenarios._simulate_match("mode dev")
        assert name == "mode_dev"
        assert score == 0.70
        assert mtype == "skill"

    def test_skill_preferred_over_command_unless_perfect(self, _patch_imports):
        """When skill >= 0.65 and command < 1.0, skill wins."""
        m = _patch_imports
        cmd = _FakeCommand(name="cmd_name")
        skill = _FakeSkill(name="skill_name")
        m.commands.match_command.return_value = (cmd, {}, 0.85)
        m.skills.find_skill.return_value = (skill, 0.70)

        name, score, mtype = m.scenarios._simulate_match("some input")
        assert name == "skill_name"
        assert mtype == "skill"

    def test_perfect_command_beats_skill(self, _patch_imports):
        """When command score is exactly 1.0, it beats skill."""
        m = _patch_imports
        cmd = _FakeCommand(name="exact_cmd")
        skill = _FakeSkill(name="skill_name")
        m.commands.match_command.return_value = (cmd, {}, 1.0)
        m.skills.find_skill.return_value = (skill, 0.70)

        name, score, mtype = m.scenarios._simulate_match("exact match")
        assert name == "exact_cmd"
        assert score == 1.0
        assert mtype == "command"

    def test_skill_fallback_055_threshold(self, _patch_imports):
        """Skill with score between 0.55 and 0.65 used as fallback."""
        m = _patch_imports
        skill = _FakeSkill(name="low_skill")
        m.commands.match_command.return_value = (None, {}, 0.3)
        m.skills.find_skill.return_value = (skill, 0.58)

        name, score, mtype = m.scenarios._simulate_match("fuzzy input")
        assert name == "low_skill"
        assert score == 0.58
        assert mtype == "skill"

    def test_command_below_060_rejected(self, _patch_imports):
        """Command with score < 0.60 is not returned (no skill fallback either)."""
        m = _patch_imports
        cmd = _FakeCommand(name="weak_cmd")
        m.commands.match_command.return_value = (cmd, {}, 0.50)
        m.skills.find_skill.return_value = (None, 0.0)

        name, score, mtype = m.scenarios._simulate_match("vague")
        assert name is None
        assert mtype == "none"

    def test_correction_applied_before_matching(self, _patch_imports):
        m = _patch_imports
        m.commands.correct_voice_text.side_effect = lambda t: t.replace("crome", "chrome")
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        m.scenarios._simulate_match("ouvre crome")
        # Verify that match_command received the corrected text
        m.commands.match_command.assert_called_with("ouvre chrome")

    def test_best_score_returned_on_no_match(self, _patch_imports):
        """When no match qualifies, the best raw score is still reported."""
        m = _patch_imports
        cmd = _FakeCommand(name="weak")
        skill = _FakeSkill(name="weaker")
        m.commands.match_command.return_value = (cmd, {}, 0.40)
        m.skills.find_skill.return_value = (skill, 0.30)

        name, score, mtype = m.scenarios._simulate_match("nothing matches")
        assert name is None
        assert score == 0.40  # max of cmd 0.40 and skill 0.30
        assert mtype == "none"

    def test_skill_at_exactly_065_qualifies(self, _patch_imports):
        m = _patch_imports
        skill = _FakeSkill(name="edge_skill")
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (skill, 0.65)

        name, score, mtype = m.scenarios._simulate_match("edge")
        assert name == "edge_skill"
        assert mtype == "skill"

    def test_command_at_exactly_060_qualifies(self, _patch_imports):
        m = _patch_imports
        cmd = _FakeCommand(name="edge_cmd")
        m.commands.match_command.return_value = (cmd, {}, 0.60)
        m.skills.find_skill.return_value = (None, 0.0)

        name, score, mtype = m.scenarios._simulate_match("edge cmd")
        assert name == "edge_cmd"
        assert mtype == "command"


# ═══════════════════════════════════════════════════════════════════════════
# 3. validate_scenario
# ═══════════════════════════════════════════════════════════════════════════

class TestValidateScenario:
    """Test validate_scenario with various match outcomes."""

    def test_pass_when_match_in_expected(self, _patch_imports):
        m = _patch_imports
        cmd = _FakeCommand(name="ouvrir_chrome")
        m.commands.match_command.return_value = (cmd, {}, 0.95)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario(expected=["ouvrir_chrome"])
        result = m.scenarios.validate_scenario(sc, cycle_number=1)

        assert result["result"] == "pass"
        assert result["matched"] == "ouvrir_chrome"
        assert result["score"] == 0.95
        assert "Match exact" in result["details"]

    def test_partial_when_wrong_match_high_score(self, _patch_imports):
        m = _patch_imports
        cmd = _FakeCommand(name="wrong_cmd")
        m.commands.match_command.return_value = (cmd, {}, 0.80)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario(expected=["correct_cmd"])
        result = m.scenarios.validate_scenario(sc, cycle_number=1)

        assert result["result"] == "partial"
        assert "Match partiel" in result["details"]

    def test_fail_when_wrong_match_low_score(self, _patch_imports):
        m = _patch_imports
        cmd = _FakeCommand(name="wrong_cmd")
        m.commands.match_command.return_value = (cmd, {}, 0.62)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario(expected=["correct_cmd"])
        result = m.scenarios.validate_scenario(sc, cycle_number=1)

        assert result["result"] == "fail"
        assert "Mauvais match" in result["details"]

    def test_fail_when_no_match(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.1)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario(expected=["expected_cmd"])
        result = m.scenarios.validate_scenario(sc, cycle_number=1)

        assert result["result"] == "fail"
        assert "Aucun match" in result["details"]

    def test_records_to_database(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario(name="db_test", voice_input="hello")
        m.scenarios.validate_scenario(sc, cycle_number=5)

        m.db.record_validation.assert_called_once()
        call_kwargs = m.db.record_validation.call_args
        assert call_kwargs[1]["cycle_number"] == 5 or call_kwargs[0][0] == 5

    def test_timing_is_positive(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario()
        result = m.scenarios.validate_scenario(sc, cycle_number=1)

        assert result["time_ms"] >= 0

    def test_scenario_with_id_passed_to_record(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario()
        sc["id"] = 42
        m.scenarios.validate_scenario(sc, cycle_number=1)

        call_kwargs = m.db.record_validation.call_args[1]
        assert call_kwargs.get("scenario_id") == 42

    def test_multiple_expected_first_used_for_db(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario(expected=["first_cmd", "second_cmd"])
        m.scenarios.validate_scenario(sc, cycle_number=1)

        call_kwargs = m.db.record_validation.call_args[1]
        assert call_kwargs.get("expected_command") == "first_cmd"

    def test_pass_with_second_expected(self, _patch_imports):
        """Match is still pass if matched name is in any position of expected list."""
        m = _patch_imports
        cmd = _FakeCommand(name="second_cmd")
        m.commands.match_command.return_value = (cmd, {}, 0.90)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario(expected=["first_cmd", "second_cmd"])
        result = m.scenarios.validate_scenario(sc, cycle_number=1)

        assert result["result"] == "pass"


# ═══════════════════════════════════════════════════════════════════════════
# 4. run_validation_cycle
# ═══════════════════════════════════════════════════════════════════════════

class TestRunValidationCycle:

    def test_with_provided_scenarios(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        scenarios = [_scenario(name=f"sc_{i}") for i in range(3)]
        result = m.scenarios.run_validation_cycle(cycle_number=1, scenarios=scenarios)

        assert result["cycle"] == 1
        assert result["total"] == 3
        assert result["failed"] == 3
        assert result["passed"] == 0
        assert result["partial"] == 0
        assert result["pass_rate"] == 0.0

    def test_all_pass(self, _patch_imports):
        m = _patch_imports
        cmd = _FakeCommand(name="expected_cmd")
        m.commands.match_command.return_value = (cmd, {}, 0.95)
        m.skills.find_skill.return_value = (None, 0.0)

        scenarios = [_scenario() for _ in range(5)]
        result = m.scenarios.run_validation_cycle(cycle_number=1, scenarios=scenarios)

        assert result["passed"] == 5
        assert result["pass_rate"] == 100.0

    def test_mixed_results(self, _patch_imports):
        m = _patch_imports

        # We'll rotate between pass and fail via side_effect
        cmd_pass = _FakeCommand(name="expected_cmd")
        cmd_wrong = _FakeCommand(name="wrong_cmd")
        returns = [
            (cmd_pass, {}, 0.95),   # pass
            (None, {}, 0.0),        # fail (no match)
            (cmd_wrong, {}, 0.80),  # partial
        ]
        m.commands.match_command.side_effect = returns
        m.skills.find_skill.return_value = (None, 0.0)

        scenarios = [_scenario() for _ in range(3)]
        result = m.scenarios.run_validation_cycle(cycle_number=1, scenarios=scenarios)

        assert result["passed"] == 1
        assert result["failed"] == 1
        assert result["partial"] == 1

    def test_empty_scenarios_list(self, _patch_imports):
        m = _patch_imports
        result = m.scenarios.run_validation_cycle(cycle_number=1, scenarios=[])

        assert result["total"] == 0
        assert result["pass_rate"] == 0
        assert result["avg_time_ms"] == 0

    def test_fallback_to_templates_when_db_empty(self, _patch_imports):
        m = _patch_imports
        m.db.get_all_scenarios.return_value = []
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        result = m.scenarios.run_validation_cycle(cycle_number=1, scenarios=None)

        # Should use SCENARIO_TEMPLATES as fallback
        assert result["total"] == len(m.scenarios.SCENARIO_TEMPLATES)

    def test_fallback_to_db_scenarios(self, _patch_imports):
        m = _patch_imports
        db_scenarios = [
            {"name": "db_sc_1", "voice_input": "hello", "expected": ["greet"],
             "category": "test", "difficulty": "easy", "description": "d",
             "expected_result": "r"},
        ]
        m.db.get_all_scenarios.return_value = db_scenarios
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        result = m.scenarios.run_validation_cycle(cycle_number=1, scenarios=None)

        assert result["total"] == 1

    def test_avg_time_ms_positive(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        result = m.scenarios.run_validation_cycle(cycle_number=1,
                                                   scenarios=[_scenario()])
        assert result["avg_time_ms"] >= 0


# ═══════════════════════════════════════════════════════════════════════════
# 5. run_50_cycles
# ═══════════════════════════════════════════════════════════════════════════

class TestRun50Cycles:

    def test_calls_init_db(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        # Temporarily shrink templates to speed up test
        orig = m.scenarios.SCENARIO_TEMPLATES
        m.scenarios.SCENARIO_TEMPLATES = [_scenario()]
        try:
            report = m.scenarios.run_50_cycles()
        finally:
            m.scenarios.SCENARIO_TEMPLATES = orig

        # init_db called at least twice (start + before stats)
        assert m.db.init_db.call_count >= 2

    def test_imports_data(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        orig = m.scenarios.SCENARIO_TEMPLATES
        m.scenarios.SCENARIO_TEMPLATES = [_scenario()]
        try:
            m.scenarios.run_50_cycles()
        finally:
            m.scenarios.SCENARIO_TEMPLATES = orig

        m.db.import_commands_from_code.assert_called_once()
        m.db.import_skills_from_code.assert_called_once()
        m.db.import_corrections_from_code.assert_called_once()

    def test_adds_all_scenarios_to_db(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        templates = [_scenario(name=f"sc_{i}") for i in range(3)]
        orig = m.scenarios.SCENARIO_TEMPLATES
        m.scenarios.SCENARIO_TEMPLATES = templates
        try:
            m.scenarios.run_50_cycles()
        finally:
            m.scenarios.SCENARIO_TEMPLATES = orig

        assert m.db.add_scenario.call_count == 3

    def test_runs_exactly_50_cycles(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        orig = m.scenarios.SCENARIO_TEMPLATES
        m.scenarios.SCENARIO_TEMPLATES = [_scenario()]
        try:
            report = m.scenarios.run_50_cycles()
        finally:
            m.scenarios.SCENARIO_TEMPLATES = orig

        assert report["summary"]["total_cycles"] == 50
        assert len(report["cycles"]) == 50

    def test_summary_aggregation(self, _patch_imports):
        m = _patch_imports
        # 1 scenario, all fail -> 50 failures total
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        orig = m.scenarios.SCENARIO_TEMPLATES
        m.scenarios.SCENARIO_TEMPLATES = [_scenario()]
        try:
            report = m.scenarios.run_50_cycles()
        finally:
            m.scenarios.SCENARIO_TEMPLATES = orig

        s = report["summary"]
        assert s["total_tests"] == 50  # 1 scenario x 50 cycles
        assert s["total_failed"] == 50
        assert s["total_passed"] == 0
        assert s["global_pass_rate"] == 0.0

    def test_all_pass_50_cycles(self, _patch_imports):
        m = _patch_imports
        cmd = _FakeCommand(name="expected_cmd")
        m.commands.match_command.return_value = (cmd, {}, 0.95)
        m.skills.find_skill.return_value = (None, 0.0)

        orig = m.scenarios.SCENARIO_TEMPLATES
        m.scenarios.SCENARIO_TEMPLATES = [_scenario()]
        try:
            report = m.scenarios.run_50_cycles()
        finally:
            m.scenarios.SCENARIO_TEMPLATES = orig

        s = report["summary"]
        assert s["total_passed"] == 50
        assert s["global_pass_rate"] == 100.0

    def test_failures_tracking(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        orig = m.scenarios.SCENARIO_TEMPLATES
        m.scenarios.SCENARIO_TEMPLATES = [
            _scenario(name="always_fails", voice_input="fail input"),
        ]
        try:
            report = m.scenarios.run_50_cycles()
        finally:
            m.scenarios.SCENARIO_TEMPLATES = orig

        assert "always_fails" in report["failures"]
        assert report["failures"]["always_fails"]["count"] == 50

    def test_db_stats_included(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        orig = m.scenarios.SCENARIO_TEMPLATES
        m.scenarios.SCENARIO_TEMPLATES = [_scenario()]
        try:
            report = m.scenarios.run_50_cycles()
        finally:
            m.scenarios.SCENARIO_TEMPLATES = orig

        assert "db_stats" in report
        assert report["db_stats"]["commands"] == 100

    def test_cycles_exclude_results_detail(self, _patch_imports):
        """The 'cycles' list in the report should NOT contain per-result details."""
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        orig = m.scenarios.SCENARIO_TEMPLATES
        m.scenarios.SCENARIO_TEMPLATES = [_scenario()]
        try:
            report = m.scenarios.run_50_cycles()
        finally:
            m.scenarios.SCENARIO_TEMPLATES = orig

        for c in report["cycles"]:
            assert "results" not in c


# ═══════════════════════════════════════════════════════════════════════════
# 6. Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_skill_below_055_not_returned(self, _patch_imports):
        m = _patch_imports
        skill = _FakeSkill(name="too_low")
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (skill, 0.50)

        name, score, mtype = m.scenarios._simulate_match("x")
        assert name is None
        assert mtype == "none"

    def test_both_none_returns_zero_score(self, _patch_imports):
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        name, score, mtype = m.scenarios._simulate_match("x")
        assert score == 0.0

    def test_validate_scenario_empty_expected(self, _patch_imports):
        """Edge case: expected list is empty — should result in fail."""
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario(expected=[])
        result = m.scenarios.validate_scenario(sc, cycle_number=1)
        assert result["result"] == "fail"

    def test_validate_scenario_result_keys(self, _patch_imports):
        """Ensure the returned dict has all expected keys."""
        m = _patch_imports
        m.commands.match_command.return_value = (None, {}, 0.0)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario()
        result = m.scenarios.validate_scenario(sc, cycle_number=1)

        expected_keys = {"scenario", "voice_input", "matched", "expected",
                         "score", "result", "details", "time_ms"}
        assert expected_keys == set(result.keys())

    def test_partial_at_exactly_075(self, _patch_imports):
        """Score exactly 0.75 with wrong match should be partial."""
        m = _patch_imports
        cmd = _FakeCommand(name="wrong")
        m.commands.match_command.return_value = (cmd, {}, 0.75)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario(expected=["correct"])
        result = m.scenarios.validate_scenario(sc, cycle_number=1)
        assert result["result"] == "partial"

    def test_fail_at_074(self, _patch_imports):
        """Score 0.74 with wrong match should be fail."""
        m = _patch_imports
        cmd = _FakeCommand(name="wrong")
        m.commands.match_command.return_value = (cmd, {}, 0.74)
        m.skills.find_skill.return_value = (None, 0.0)

        sc = _scenario(expected=["correct"])
        result = m.scenarios.validate_scenario(sc, cycle_number=1)
        assert result["result"] == "fail"
