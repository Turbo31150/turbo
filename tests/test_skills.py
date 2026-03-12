"""Tests for src/skills.py — Skill management, matching, persistence, history.

Covers: SkillStep, Skill, load_skills, save_skills, add_skill, remove_skill,
        find_skill, record_skill_use, log_action, get_action_history,
        format_skills_list, suggest_next_actions, _default_skills.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Safe import setup
# ---------------------------------------------------------------------------
_originals: dict[str, object] = {}


@pytest.fixture(autouse=True, scope="module")
def _mock_externals():
    """Mock heavy externals if needed for import."""
    for mod_name in ("claude_agent_sdk",):
        if mod_name not in sys.modules or isinstance(sys.modules[mod_name], MagicMock):
            mock = MagicMock()
            mock.tool = lambda *a, **kw: (lambda fn: fn)
            _originals[mod_name] = sys.modules.get(mod_name)
            sys.modules[mod_name] = mock
    yield
    for mod_name, orig in _originals.items():
        if orig is None:
            sys.modules.pop(mod_name, None)
        else:
            sys.modules[mod_name] = orig


@pytest.fixture(scope="module")
def skills_mod():
    """Import and return the skills module."""
    import src.skills as mod
    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory and patch SKILLS_FILE/HISTORY_FILE."""
    skills_file = tmp_path / "skills.json"
    history_file = tmp_path / "action_history.json"
    return skills_file, history_file


@pytest.fixture
def patched_files(skills_mod, tmp_data_dir):
    """Patch SKILLS_FILE and HISTORY_FILE to temporary paths."""
    skills_file, history_file = tmp_data_dir
    with patch.object(skills_mod, "SKILLS_FILE", skills_file), \
         patch.object(skills_mod, "HISTORY_FILE", history_file):
        yield skills_file, history_file


# ===== SkillStep =====


class TestSkillStep:
    """Tests for SkillStep dataclass."""

    def test_creation_minimal(self, skills_mod):
        step = skills_mod.SkillStep("lm_query")
        assert step.tool == "lm_query"
        assert step.args == {}
        assert step.description == ""
        assert step.wait_for_result is True

    def test_creation_full(self, skills_mod):
        step = skills_mod.SkillStep("app_open", {"name": "chrome"}, "Open Chrome", False)
        assert step.tool == "app_open"
        assert step.args == {"name": "chrome"}
        assert step.description == "Open Chrome"
        assert step.wait_for_result is False

    def test_serialization(self, skills_mod):
        step = skills_mod.SkillStep("test", {"x": 1}, "desc")
        d = asdict(step)
        assert d["tool"] == "test"
        assert d["args"] == {"x": 1}

    def test_deserialization(self, skills_mod):
        data = {"tool": "ping", "args": {"host": "8.8.8.8"}, "description": "Ping Google", "wait_for_result": True}
        step = skills_mod.SkillStep(**data)
        assert step.tool == "ping"
        assert step.args["host"] == "8.8.8.8"


# ===== Skill =====


class TestSkill:
    """Tests for Skill dataclass."""

    def test_creation_minimal(self, skills_mod):
        skill = skills_mod.Skill(
            name="test", description="A test skill",
            triggers=["test me"], steps=[]
        )
        assert skill.name == "test"
        assert skill.usage_count == 0
        assert skill.success_rate == 1.0
        assert skill.confirm is False

    def test_creation_full(self, skills_mod):
        steps = [skills_mod.SkillStep("app_open", {"name": "chrome"})]
        skill = skills_mod.Skill(
            name="full", description="Full skill",
            triggers=["go"], steps=steps,
            category="dev", confirm=True
        )
        assert skill.category == "dev"
        assert skill.confirm is True
        assert len(skill.steps) == 1

    def test_serialization_roundtrip(self, skills_mod):
        steps = [skills_mod.SkillStep("ping", {"host": "1.1.1.1"}, "Ping")]
        skill = skills_mod.Skill(
            name="rt", description="Roundtrip",
            triggers=["trigger1"], steps=steps
        )
        d = asdict(skill)
        assert d["name"] == "rt"
        assert len(d["steps"]) == 1
        assert d["steps"][0]["tool"] == "ping"


# ===== load_skills / save_skills =====


class TestLoadSaveSkills:
    """Tests for load_skills and save_skills persistence."""

    def test_load_returns_defaults_when_no_file(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        # File does not exist yet
        assert not skills_file.exists()
        skills = skills_mod.load_skills()
        assert isinstance(skills, list)
        assert len(skills) > 0  # should return defaults
        assert skills_file.exists()  # defaults written

    def test_save_and_load_roundtrip(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        steps = [skills_mod.SkillStep("test_tool", {"a": 1}, "Test")]
        original = [skills_mod.Skill(
            name="save_test", description="Save test",
            triggers=["save"], steps=steps, category="test"
        )]
        skills_mod.save_skills(original)
        loaded = skills_mod.load_skills()
        assert len(loaded) == 1
        assert loaded[0].name == "save_test"
        assert loaded[0].steps[0].tool == "test_tool"

    def test_load_corrupted_json_returns_defaults(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        skills_file.write_text("NOT VALID JSON!!!", encoding="utf-8")
        skills = skills_mod.load_skills()
        assert isinstance(skills, list)
        assert len(skills) > 0  # defaults

    def test_save_overwrites(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s1 = [skills_mod.Skill("a", "A", ["a"], [])]
        s2 = [skills_mod.Skill("b", "B", ["b"], [])]
        skills_mod.save_skills(s1)
        skills_mod.save_skills(s2)
        loaded = skills_mod.load_skills()
        assert len(loaded) == 1
        assert loaded[0].name == "b"

    def test_load_empty_list(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        skills_file.write_text("[]", encoding="utf-8")
        skills = skills_mod.load_skills()
        assert skills == []


# ===== add_skill =====


class TestAddSkill:
    """Tests for add_skill — add/replace behavior."""

    def test_add_new_skill(self, skills_mod, patched_files):
        # Start with empty list
        skills_file, _ = patched_files
        skills_file.write_text("[]", encoding="utf-8")

        skill = skills_mod.Skill("new_one", "New", ["trigger"], [])
        skills_mod.add_skill(skill)
        loaded = skills_mod.load_skills()
        assert any(s.name == "new_one" for s in loaded)

    def test_add_replaces_existing(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s1 = skills_mod.Skill("dup", "Original", ["orig"], [])
        s2 = skills_mod.Skill("dup", "Replaced", ["new"], [])
        skills_file.write_text("[]", encoding="utf-8")
        skills_mod.add_skill(s1)
        skills_mod.add_skill(s2)
        loaded = skills_mod.load_skills()
        dups = [s for s in loaded if s.name == "dup"]
        assert len(dups) == 1
        assert dups[0].description == "Replaced"

    def test_add_sets_created_at(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        skills_file.write_text("[]", encoding="utf-8")
        skill = skills_mod.Skill("timed", "Timed", ["t"], [])
        skills_mod.add_skill(skill)
        loaded = skills_mod.load_skills()
        found = [s for s in loaded if s.name == "timed"][0]
        assert found.created_at > 0


# ===== remove_skill =====


class TestRemoveSkill:
    """Tests for remove_skill."""

    def test_remove_existing(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("to_remove", "R", ["r"], [])
        skills_mod.save_skills([s])
        result = skills_mod.remove_skill("to_remove")
        assert result is True
        loaded = skills_mod.load_skills()
        assert not any(sk.name == "to_remove" for sk in loaded)

    def test_remove_nonexistent(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        skills_file.write_text("[]", encoding="utf-8")
        result = skills_mod.remove_skill("ghost")
        assert result is False

    def test_remove_preserves_others(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s1 = skills_mod.Skill("keep", "Keep", ["k"], [])
        s2 = skills_mod.Skill("drop", "Drop", ["d"], [])
        skills_mod.save_skills([s1, s2])
        skills_mod.remove_skill("drop")
        loaded = skills_mod.load_skills()
        assert len(loaded) == 1
        assert loaded[0].name == "keep"


# ===== find_skill =====


class TestFindSkill:
    """Tests for find_skill — fuzzy matching."""

    def test_exact_match(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("exact", "Exact", ["mode gaming"], [])
        skills_mod.save_skills([s])
        found, score = skills_mod.find_skill("mode gaming")
        assert found is not None
        assert found.name == "exact"
        assert score == 1.0

    def test_substring_match(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("sub", "Sub", ["lance le trading"], [])
        skills_mod.save_skills([s])
        found, score = skills_mod.find_skill("ok lance le trading maintenant")
        assert found is not None
        assert score >= 0.85

    def test_fuzzy_match(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("fuzzy", "Fuzzy", ["rapport du matin"], [])
        skills_mod.save_skills([s])
        found, score = skills_mod.find_skill("rapport matin")
        assert found is not None
        assert score >= 0.60

    def test_below_threshold(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("far", "Far", ["mode gaming extreme"], [])
        skills_mod.save_skills([s])
        found, score = skills_mod.find_skill("achete du pain")
        assert found is None
        assert score < 0.60

    def test_empty_skills_list(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        skills_file.write_text("[]", encoding="utf-8")
        found, score = skills_mod.find_skill("anything")
        assert found is None

    def test_case_insensitive(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("ci", "CI", ["Mode Gaming"], [])
        skills_mod.save_skills([s])
        found, score = skills_mod.find_skill("mode gaming")
        assert found is not None
        assert score == 1.0

    def test_custom_threshold(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("thresh", "T", ["quelque chose de particulier"], [])
        skills_mod.save_skills([s])
        # With very high threshold, even close matches should fail
        found, score = skills_mod.find_skill("quelque chose", threshold=0.99)
        # Score should be > 0 but below 0.99
        assert found is None or score >= 0.99


# ===== record_skill_use =====


class TestRecordSkillUse:
    """Tests for record_skill_use — usage tracking."""

    def test_record_success(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("used", "Used", ["u"], [], usage_count=0, success_rate=1.0)
        skills_mod.save_skills([s])
        skills_mod.record_skill_use("used", True)
        loaded = skills_mod.load_skills()
        found = [sk for sk in loaded if sk.name == "used"][0]
        assert found.usage_count == 1
        assert found.success_rate == 1.0

    def test_record_failure(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("fail", "Fail", ["f"], [], usage_count=0, success_rate=1.0)
        skills_mod.save_skills([s])
        skills_mod.record_skill_use("fail", False)
        loaded = skills_mod.load_skills()
        found = [sk for sk in loaded if sk.name == "fail"][0]
        assert found.usage_count == 1
        assert found.success_rate == 0.0

    def test_record_nonexistent_skill(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        skills_file.write_text("[]", encoding="utf-8")
        # Should not raise
        skills_mod.record_skill_use("ghost", True)

    def test_last_used_updated(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("timed", "T", ["t"], [], last_used=0.0)
        skills_mod.save_skills([s])
        before = time.time()
        skills_mod.record_skill_use("timed", True)
        loaded = skills_mod.load_skills()
        found = [sk for sk in loaded if sk.name == "timed"][0]
        assert found.last_used >= before


# ===== log_action / get_action_history =====


class TestActionHistory:
    """Tests for log_action and get_action_history."""

    def test_log_and_retrieve(self, skills_mod, patched_files):
        _, history_file = patched_files
        skills_mod.log_action("test_action", "ok", True)
        history = skills_mod.get_action_history()
        assert len(history) >= 1
        assert history[-1]["action"] == "test_action"

    def test_log_truncates_result(self, skills_mod, patched_files):
        _, history_file = patched_files
        long_result = "x" * 500
        skills_mod.log_action("long", long_result, True)
        history = skills_mod.get_action_history()
        assert len(history[-1]["result"]) <= 200

    def test_history_limit(self, skills_mod, patched_files):
        _, history_file = patched_files
        skills_mod.log_action("a", "ok", True)
        skills_mod.log_action("b", "ok", True)
        skills_mod.log_action("c", "ok", True)
        history = skills_mod.get_action_history(limit=2)
        assert len(history) == 2

    def test_history_max_500(self, skills_mod, patched_files):
        _, history_file = patched_files
        # Write 510 entries
        big = [{"action": f"a{i}", "result": "ok", "success": True, "timestamp": i} for i in range(510)]
        history_file.write_text(json.dumps(big), encoding="utf-8")
        skills_mod.log_action("new", "ok", True)
        data = json.loads(history_file.read_text(encoding="utf-8"))
        assert len(data) <= 500

    def test_empty_history(self, skills_mod, patched_files):
        _, history_file = patched_files
        # No file exists
        if history_file.exists():
            history_file.unlink()
        history = skills_mod.get_action_history()
        assert history == []

    def test_corrupted_history_returns_empty(self, skills_mod, patched_files):
        _, history_file = patched_files
        history_file.write_text("BROKEN JSON", encoding="utf-8")
        history = skills_mod.get_action_history()
        assert history == []


# ===== format_skills_list =====


class TestFormatSkillsList:
    """Tests for format_skills_list."""

    def test_empty_skills(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        skills_file.write_text("[]", encoding="utf-8")
        result = skills_mod.format_skills_list()
        assert "aucun" in result.lower() or "Aucun" in result

    def test_non_empty_skills(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("demo", "Demo skill", ["trigger1", "trigger2"], [
            skills_mod.SkillStep("app_open", {}, "Open")
        ])
        skills_mod.save_skills([s])
        result = skills_mod.format_skills_list()
        assert "demo" in result
        assert "Demo skill" in result
        assert "trigger1" in result
        assert "1 etapes" in result

    def test_usage_count_shown(self, skills_mod, patched_files):
        skills_file, _ = patched_files
        s = skills_mod.Skill("used_demo", "Used", ["t"], [], usage_count=5)
        skills_mod.save_skills([s])
        result = skills_mod.format_skills_list()
        assert "5x" in result


# ===== suggest_next_actions =====


class TestSuggestNextActions:
    """Tests for suggest_next_actions context-based suggestions."""

    def test_trading_context(self, skills_mod):
        suggestions = skills_mod.suggest_next_actions("check trading signal")
        assert len(suggestions) > 0
        assert any("trading" in s.lower() for s in suggestions)

    def test_system_context(self, skills_mod):
        suggestions = skills_mod.suggest_next_actions("ram usage trop haute")
        assert any("system" in s.lower() or "process" in s.lower() for s in suggestions)

    def test_cluster_context(self, skills_mod):
        suggestions = skills_mod.suggest_next_actions("statut du cluster ia")
        assert any("cluster" in s.lower() or "model" in s.lower() for s in suggestions)

    def test_files_context(self, skills_mod):
        suggestions = skills_mod.suggest_next_actions("copier le fichier")
        assert any("fichier" in s.lower() or "folder" in s.lower() or "dossier" in s.lower() or "list" in s.lower() for s in suggestions)

    def test_general_context(self, skills_mod):
        suggestions = skills_mod.suggest_next_actions("hello")
        assert len(suggestions) > 0
        assert len(suggestions) <= 5

    def test_returns_max_5(self, skills_mod):
        suggestions = skills_mod.suggest_next_actions("trading signal crypto bitcoin ethereum")
        assert len(suggestions) <= 5


# ===== _default_skills =====


class TestDefaultSkills:
    """Tests for _default_skills — built-in pipeline generation."""

    def test_returns_non_empty_list(self, skills_mod):
        defaults = skills_mod._default_skills()
        assert isinstance(defaults, list)
        assert len(defaults) > 5

    def test_all_have_required_fields(self, skills_mod):
        defaults = skills_mod._default_skills()
        for skill in defaults:
            assert skill.name
            assert skill.description
            assert len(skill.triggers) > 0
            assert len(skill.steps) > 0

    def test_no_duplicate_names(self, skills_mod):
        defaults = skills_mod._default_skills()
        names = [s.name for s in defaults]
        assert len(names) == len(set(names)), f"Duplicate names: {[n for n in names if names.count(n) > 1]}"

    def test_known_skills_present(self, skills_mod):
        defaults = skills_mod._default_skills()
        names = {s.name for s in defaults}
        assert "rapport_matin" in names
        assert "mode_trading" in names
        assert "mode_dev" in names
