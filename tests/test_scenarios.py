"""Tests for src/scenarios.py — Scenario validation engine.

Covers: SCENARIO_TEMPLATES structure, _simulate_match logic,
validate_scenario, run_validation_cycle.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.scenarios import SCENARIO_TEMPLATES


# ===========================================================================
# SCENARIO_TEMPLATES data integrity
# ===========================================================================

class TestScenarioTemplates:
    def test_not_empty(self):
        assert len(SCENARIO_TEMPLATES) > 100

    def test_required_keys(self):
        required = {"name", "category", "voice_input", "expected", "expected_result"}
        for i, t in enumerate(SCENARIO_TEMPLATES):
            missing = required - set(t.keys())
            assert not missing, f"Template #{i} ({t.get('name', '?')}) missing: {missing}"

    def test_unique_names(self):
        names = [t["name"] for t in SCENARIO_TEMPLATES]
        dupes = [n for n in names if names.count(n) > 1]
        assert not dupes, f"Duplicate scenario names: {set(dupes)}"

    def test_expected_is_list(self):
        for t in SCENARIO_TEMPLATES:
            assert isinstance(t["expected"], list), f"{t['name']}: expected should be a list"
            assert len(t["expected"]) >= 1, f"{t['name']}: expected should have at least 1 item"

    def test_voice_input_not_empty(self):
        for t in SCENARIO_TEMPLATES:
            assert t["voice_input"].strip(), f"{t['name']}: voice_input is empty"

    def test_categories_valid(self):
        valid_cats = {
            "routine", "navigation", "app", "media", "fenetre", "clipboard",
            "systeme", "fichiers", "trading", "dev", "jarvis", "correction",
            "pipeline", "accessibilite", "saisie",
        }
        for t in SCENARIO_TEMPLATES:
            assert t["category"] in valid_cats, f"{t['name']}: unknown category '{t['category']}'"

    def test_difficulty_valid(self):
        for t in SCENARIO_TEMPLATES:
            diff = t.get("difficulty", "normal")
            assert diff in {"easy", "normal", "hard"}, f"{t['name']}: bad difficulty '{diff}'"

    def test_minimum_categories(self):
        cats = {t["category"] for t in SCENARIO_TEMPLATES}
        assert "routine" in cats
        assert "navigation" in cats
        assert "systeme" in cats
        assert "app" in cats
        assert "correction" in cats


# ===========================================================================
# _simulate_match
# ===========================================================================

class TestSimulateMatch:
    def test_command_match(self):
        from src.scenarios import _simulate_match
        mock_cmd = MagicMock()
        mock_cmd.name = "test_cmd"
        with patch("src.scenarios.correct_voice_text", return_value="test"), \
             patch("src.scenarios.find_skill", return_value=(None, 0.0)), \
             patch("src.scenarios.match_command", return_value=(mock_cmd, {}, 0.85)):
            name, score, mtype = _simulate_match("test")
        assert name == "test_cmd"
        assert score == 0.85
        assert mtype == "command"

    def test_skill_match_priority(self):
        from src.scenarios import _simulate_match
        mock_cmd = MagicMock()
        mock_cmd.name = "cmd_match"
        mock_skill = MagicMock()
        mock_skill.name = "skill_match"
        with patch("src.scenarios.correct_voice_text", return_value="test"), \
             patch("src.scenarios.find_skill", return_value=(mock_skill, 0.75)), \
             patch("src.scenarios.match_command", return_value=(mock_cmd, {}, 0.80)):
            name, score, mtype = _simulate_match("test")
        # Skill has priority when score >= 0.65 unless cmd is 1.0
        assert name == "skill_match"
        assert mtype == "skill"

    def test_perfect_command_beats_skill(self):
        from src.scenarios import _simulate_match
        mock_cmd = MagicMock()
        mock_cmd.name = "exact_cmd"
        mock_skill = MagicMock()
        mock_skill.name = "skill_match"
        with patch("src.scenarios.correct_voice_text", return_value="test"), \
             patch("src.scenarios.find_skill", return_value=(mock_skill, 0.75)), \
             patch("src.scenarios.match_command", return_value=(mock_cmd, {}, 1.0)):
            name, score, mtype = _simulate_match("test")
        assert name == "exact_cmd"
        assert mtype == "command"

    def test_no_match(self):
        from src.scenarios import _simulate_match
        with patch("src.scenarios.correct_voice_text", return_value="gibberish"), \
             patch("src.scenarios.find_skill", return_value=(None, 0.0)), \
             patch("src.scenarios.match_command", return_value=(None, {}, 0.1)):
            name, score, mtype = _simulate_match("gibberish")
        assert name is None
        assert mtype == "none"

    def test_skill_fallback_lower_threshold(self):
        from src.scenarios import _simulate_match
        mock_skill = MagicMock()
        mock_skill.name = "low_skill"
        with patch("src.scenarios.correct_voice_text", return_value="test"), \
             patch("src.scenarios.find_skill", return_value=(mock_skill, 0.58)), \
             patch("src.scenarios.match_command", return_value=(None, {}, 0.3)):
            name, score, mtype = _simulate_match("test")
        assert name == "low_skill"
        assert mtype == "skill"


# ===========================================================================
# validate_scenario
# ===========================================================================

class TestValidateScenario:
    def test_pass_result(self):
        from src.scenarios import validate_scenario
        scenario = {
            "name": "test_pass", "voice_input": "test input",
            "expected": ["cmd_a", "cmd_b"], "expected_result": "OK",
        }
        with patch("src.scenarios._simulate_match", return_value=("cmd_a", 0.95, "command")), \
             patch("src.scenarios.record_validation"):
            result = validate_scenario(scenario, cycle_number=1)
        assert result["result"] == "pass"
        assert result["matched"] == "cmd_a"
        assert result["score"] == 0.95

    def test_fail_wrong_match(self):
        from src.scenarios import validate_scenario
        scenario = {
            "name": "test_fail", "voice_input": "test",
            "expected": ["expected_cmd"], "expected_result": "OK",
        }
        with patch("src.scenarios._simulate_match", return_value=("wrong_cmd", 0.6, "command")), \
             patch("src.scenarios.record_validation"):
            result = validate_scenario(scenario, cycle_number=1)
        assert result["result"] == "fail"

    def test_partial_result(self):
        from src.scenarios import validate_scenario
        scenario = {
            "name": "test_partial", "voice_input": "test",
            "expected": ["expected_cmd"], "expected_result": "OK",
        }
        with patch("src.scenarios._simulate_match", return_value=("other_cmd", 0.80, "command")), \
             patch("src.scenarios.record_validation"):
            result = validate_scenario(scenario, cycle_number=1)
        assert result["result"] == "partial"

    def test_fail_no_match(self):
        from src.scenarios import validate_scenario
        scenario = {
            "name": "test_none", "voice_input": "gibberish",
            "expected": ["expected_cmd"], "expected_result": "OK",
        }
        with patch("src.scenarios._simulate_match", return_value=(None, 0.1, "none")), \
             patch("src.scenarios.record_validation"):
            result = validate_scenario(scenario, cycle_number=1)
        assert result["result"] == "fail"
        assert "aucun match" in result["details"].lower()

    def test_result_has_timing(self):
        from src.scenarios import validate_scenario
        scenario = {
            "name": "test_time", "voice_input": "test",
            "expected": ["cmd"], "expected_result": "OK",
        }
        with patch("src.scenarios._simulate_match", return_value=("cmd", 0.9, "command")), \
             patch("src.scenarios.record_validation"):
            result = validate_scenario(scenario, cycle_number=1)
        assert "time_ms" in result
        assert result["time_ms"] >= 0


# ===========================================================================
# run_validation_cycle
# ===========================================================================

class TestRunValidationCycle:
    def test_cycle_with_custom_scenarios(self):
        from src.scenarios import run_validation_cycle
        scenarios = [
            {"name": "s1", "voice_input": "a", "expected": ["cmd_a"], "expected_result": "OK"},
            {"name": "s2", "voice_input": "b", "expected": ["cmd_b"], "expected_result": "OK"},
        ]
        with patch("src.scenarios._simulate_match", return_value=("cmd_a", 0.9, "command")), \
             patch("src.scenarios.record_validation"):
            result = run_validation_cycle(1, scenarios)
        assert result["cycle"] == 1
        assert result["total"] == 2
        assert result["passed"] + result["failed"] + result["partial"] == 2

    def test_cycle_pass_rate(self):
        from src.scenarios import run_validation_cycle
        scenarios = [
            {"name": "s1", "voice_input": "a", "expected": ["ok"], "expected_result": "OK"},
        ]
        with patch("src.scenarios._simulate_match", return_value=("ok", 0.95, "command")), \
             patch("src.scenarios.record_validation"):
            result = run_validation_cycle(1, scenarios)
        assert result["pass_rate"] == 100.0

    def test_cycle_empty_scenarios(self):
        from src.scenarios import run_validation_cycle
        with patch("src.scenarios.get_all_scenarios", return_value=[]):
            result = run_validation_cycle(1, [])
        assert result["total"] == 0
        assert result["pass_rate"] == 0

    def test_cycle_avg_time(self):
        from src.scenarios import run_validation_cycle
        scenarios = [
            {"name": "s1", "voice_input": "a", "expected": ["ok"], "expected_result": "OK"},
        ]
        with patch("src.scenarios._simulate_match", return_value=("ok", 0.9, "command")), \
             patch("src.scenarios.record_validation"):
            result = run_validation_cycle(1, scenarios)
        assert result["avg_time_ms"] >= 0
