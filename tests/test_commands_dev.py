"""Tests for src/commands_dev.py — Dev command definitions.

Covers: DEV_COMMANDS structure, JarvisCommand integrity,
action types, triggers, categories.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.commands_dev import DEV_COMMANDS
from src.commands import JarvisCommand


# ===========================================================================
# Structure integrity
# ===========================================================================

class TestDevCommands:
    def test_not_empty(self):
        assert len(DEV_COMMANDS) > 20

    def test_all_are_jarvis_commands(self):
        for cmd in DEV_COMMANDS:
            assert isinstance(cmd, JarvisCommand), f"{cmd} is not a JarvisCommand"

    def test_unique_names(self):
        names = [cmd.name for cmd in DEV_COMMANDS]
        dupes = [n for n in names if names.count(n) > 1]
        assert not dupes, f"Duplicate dev command names: {set(dupes)}"

    def test_all_have_triggers(self):
        for cmd in DEV_COMMANDS:
            assert len(cmd.triggers) >= 1, f"{cmd.name}: no triggers"

    def test_category_is_dev(self):
        for cmd in DEV_COMMANDS:
            assert cmd.category == "dev", f"{cmd.name}: category is '{cmd.category}'"

    def test_descriptions_not_empty(self):
        for cmd in DEV_COMMANDS:
            assert cmd.description and len(cmd.description) > 5, f"{cmd.name}: description too short"

    def test_valid_action_types(self):
        valid = {"powershell", "app_open", "browser", "hotkey", "script", "pipeline"}
        for cmd in DEV_COMMANDS:
            assert cmd.action_type in valid, f"{cmd.name}: bad action_type '{cmd.action_type}'"


# ===========================================================================
# Specific command groups
# ===========================================================================

class TestDevGroups:
    def _names(self):
        return {cmd.name for cmd in DEV_COMMANDS}

    def test_git_commands(self):
        names = self._names()
        git_cmds = [n for n in names if n.startswith("git_")]
        assert len(git_cmds) >= 5

    def test_ollama_commands(self):
        names = self._names()
        assert "ollama_list" in names
        assert "ollama_restart" in names

    def test_python_commands(self):
        names = self._names()
        assert "python_test" in names
        assert "python_lint" in names

    def test_docker_commands(self):
        names = self._names()
        docker_cmds = [n for n in names if n.startswith("docker_")]
        assert len(docker_cmds) >= 3

    def test_lms_commands(self):
        names = self._names()
        lms_cmds = [n for n in names if n.startswith("lms_")]
        assert len(lms_cmds) >= 3

    def test_communication_apps(self):
        names = self._names()
        assert "ouvrir_telegram" in names
        assert "ouvrir_whatsapp" in names


# ===========================================================================
# Confirm flag on dangerous commands
# ===========================================================================

class TestConfirmFlags:
    def test_dangerous_have_confirm(self):
        danger_names = {"docker_prune", "ollama_remove"}
        for cmd in DEV_COMMANDS:
            if cmd.name in danger_names:
                assert cmd.confirm is True, f"{cmd.name}: should require confirmation"

    def test_safe_commands_no_confirm(self):
        safe_names = {"git_status_turbo", "ollama_list", "python_test"}
        for cmd in DEV_COMMANDS:
            if cmd.name in safe_names:
                assert not cmd.confirm, f"{cmd.name}: should NOT require confirmation"
