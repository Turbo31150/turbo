"""Tests for src/env_variable_manager.py — Windows environment variables.

Covers: EnvVariable, EnvEvent, EnvVariableManager (list_system_vars,
list_user_vars, list_all, get_var, search, get_path_entries,
get_events, get_stats), env_variable_manager singleton.
All subprocess calls are mocked.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.env_variable_manager import (
    EnvVariable, EnvEvent, EnvVariableManager, env_variable_manager,
)


SYSTEM_VARS_JSON = json.dumps([
    {"Key": "ComSpec", "Value": "/\Windows/system32/cmd.exe"},
    {"Key": "OS", "Value": "Windows_NT"},
])

USER_VARS_JSON = json.dumps([
    {"Key": "TEMP", "Value": "/\Users/test/AppData/Local/Temp"},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_env_variable(self):
        v = EnvVariable(name="PATH")
        assert v.value == ""
        assert v.scope == ""

    def test_env_event(self):
        e = EnvEvent(action="list")
        assert e.success is True


# ===========================================================================
# EnvVariableManager — list_system_vars (mocked)
# ===========================================================================

class TestListSystemVars:
    def test_success(self):
        evm = EnvVariableManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SYSTEM_VARS_JSON
        with patch("subprocess.run", return_value=mock_result):
            vars_ = evm.list_system_vars()
        assert len(vars_) == 2
        assert vars_[0]["scope"] == "System"

    def test_failure(self):
        evm = EnvVariableManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            vars_ = evm.list_system_vars()
        assert vars_ == []


# ===========================================================================
# EnvVariableManager — list_user_vars (mocked)
# ===========================================================================

class TestListUserVars:
    def test_success(self):
        evm = EnvVariableManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = USER_VARS_JSON
        with patch("subprocess.run", return_value=mock_result):
            vars_ = evm.list_user_vars()
        assert len(vars_) == 1
        assert vars_[0]["scope"] == "User"


# ===========================================================================
# EnvVariableManager — get_var
# ===========================================================================

class TestGetVar:
    def test_existing(self):
        evm = EnvVariableManager()
        # PATH always exists
        result = evm.get_var("PATH")
        assert result is not None
        assert result["scope"] == "Process"

    def test_nonexistent(self):
        evm = EnvVariableManager()
        result = evm.get_var("JARVIS_NONEXISTENT_VAR_12345")
        assert result is None


# ===========================================================================
# EnvVariableManager — search
# ===========================================================================

class TestSearch:
    def test_search(self):
        evm = EnvVariableManager()
        fake_sys = [{"name": "ComSpec", "value": "/\Windows/system32/cmd.exe", "scope": "System"},
                    {"name": "OS", "value": "Windows_NT", "scope": "System"}]
        with patch.object(evm, "list_system_vars", return_value=fake_sys), \
             patch.object(evm, "list_user_vars", return_value=[]):
            results = evm.search("comspec")
        assert len(results) == 1


# ===========================================================================
# EnvVariableManager — get_path_entries
# ===========================================================================

class TestPathEntries:
    def test_returns_list(self):
        evm = EnvVariableManager()
        entries = evm.get_path_entries()
        assert isinstance(entries, list)
        assert len(entries) > 0


# ===========================================================================
# EnvVariableManager — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        evm = EnvVariableManager()
        assert evm.get_events() == []

    def test_stats(self):
        evm = EnvVariableManager()
        stats = evm.get_stats()
        assert stats["total_events"] == 0
        assert stats["process_var_count"] > 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert env_variable_manager is not None
        assert isinstance(env_variable_manager, EnvVariableManager)
