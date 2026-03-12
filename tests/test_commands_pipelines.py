"""Tests for src/commands_pipelines.py — Pipeline command definitions.

Covers: PIPELINE_COMMANDS structure, JarvisCommand integrity,
action types, triggers, pipeline step format.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.commands_pipelines import PIPELINE_COMMANDS
from src.commands import JarvisCommand


# ===========================================================================
# Structure integrity
# ===========================================================================

class TestPipelineCommands:
    def test_not_empty(self):
        assert len(PIPELINE_COMMANDS) > 50

    def test_all_are_jarvis_commands(self):
        for cmd in PIPELINE_COMMANDS:
            assert isinstance(cmd, JarvisCommand), f"{cmd} is not a JarvisCommand"

    def test_unique_names(self):
        names = [cmd.name for cmd in PIPELINE_COMMANDS]
        dupes = [n for n in names if names.count(n) > 1]
        assert not dupes, f"Duplicate pipeline names: {set(dupes)}"

    def test_all_have_triggers(self):
        for cmd in PIPELINE_COMMANDS:
            assert len(cmd.triggers) >= 1, f"{cmd.name}: no triggers"
            for t in cmd.triggers:
                assert isinstance(t, str) and t.strip(), f"{cmd.name}: empty trigger"

    def test_all_pipeline_action_type(self):
        for cmd in PIPELINE_COMMANDS:
            assert cmd.action_type == "pipeline", f"{cmd.name}: action_type is '{cmd.action_type}', expected 'pipeline'"

    def test_category_is_pipeline(self):
        for cmd in PIPELINE_COMMANDS:
            assert cmd.category == "pipeline", f"{cmd.name}: category is '{cmd.category}'"

    def test_actions_have_valid_steps(self):
        valid_step_types = {
            "powershell", "app_open", "browser", "hotkey",
            "ms_settings", "jarvis_tool", "sleep",
        }
        bare_string_count = 0
        for cmd in PIPELINE_COMMANDS:
            steps = [s.strip() for s in cmd.action.split(";;") if s.strip()]
            for step in steps:
                if step.startswith("sleep:"):
                    continue
                sep = step.find(":")
                if sep == -1:
                    # Bare strings (inline messages) — executor treats as "invalid step"
                    bare_string_count += 1
                    continue
                step_type = step[:sep].strip()
                assert step_type in valid_step_types, (
                    f"{cmd.name}: unknown step type '{step_type}' in step '{step[:50]}'"
                )
        # Very few bare strings expected (data quality)
        assert bare_string_count <= 5, f"Too many bare string steps: {bare_string_count}"

    def test_descriptions_not_empty(self):
        for cmd in PIPELINE_COMMANDS:
            assert cmd.description and len(cmd.description) > 5, (
                f"{cmd.name}: description too short"
            )


# ===========================================================================
# Specific pipeline categories
# ===========================================================================

class TestPipelineCategories:
    def _names(self):
        return {cmd.name for cmd in PIPELINE_COMMANDS}

    def test_mode_commands_exist(self):
        names = self._names()
        assert "mode_musique" in names
        assert "mode_gaming" in names
        assert "mode_code_turbo" in names

    def test_routine_commands_exist(self):
        names = self._names()
        assert "routine_matin" in names
        assert "routine_soir" in names

    def test_maintenance_commands_exist(self):
        names = self._names()
        assert "nettoyage_express" in names
        assert "diagnostic_complet" in names

    def test_comet_commands_exist(self):
        names = self._names()
        comet_cmds = [n for n in names if "comet" in n]
        assert len(comet_cmds) >= 5

    def test_dev_commands_exist(self):
        names = self._names()
        dev_cmds = [n for n in names if n.startswith("dev_")]
        assert len(dev_cmds) >= 5

    def test_simulation_commands_exist(self):
        names = self._names()
        sim_cmds = [n for n in names if n.startswith("sim_")]
        assert len(sim_cmds) >= 3


# ===========================================================================
# Confirm flag
# ===========================================================================

class TestConfirmFlag:
    def test_dangerous_commands_have_confirm(self):
        danger_keywords = {"nettoyage_express", "veille_securisee", "maintenance_totale",
                          "mode_nuit_totale", "mode_detox_digital", "routine_nuit_urgence",
                          "mode_backup_total"}
        for cmd in PIPELINE_COMMANDS:
            if cmd.name in danger_keywords:
                assert cmd.confirm is True, f"{cmd.name}: should require confirmation"

    def test_safe_commands_no_confirm(self):
        safe_keywords = {"mode_musique", "mode_gaming", "routine_matin"}
        for cmd in PIPELINE_COMMANDS:
            if cmd.name in safe_keywords:
                assert not cmd.confirm, f"{cmd.name}: should NOT require confirmation"


# ===========================================================================
# Pipeline step counts
# ===========================================================================

class TestPipelineSteps:
    def test_all_have_at_least_one_step(self):
        for cmd in PIPELINE_COMMANDS:
            steps = [s.strip() for s in cmd.action.split(";;") if s.strip()]
            assert len(steps) >= 1, f"{cmd.name}: no steps in pipeline"

    def test_complex_pipelines_have_multiple_steps(self):
        multi_step = {
            "mode_code_turbo", "diagnostic_complet", "routine_matin",
            "audit_securite_complet", "rapport_systeme_complet",
        }
        for cmd in PIPELINE_COMMANDS:
            if cmd.name in multi_step:
                steps = [s.strip() for s in cmd.action.split(";;") if s.strip()]
                assert len(steps) >= 3, f"{cmd.name}: expected 3+ steps, got {len(steps)}"
