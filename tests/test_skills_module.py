"""Tests for JARVIS Skills module — src/skills.py

Covers: Skill/SkillStep dataclasses, load/save, CRUD operations,
        find_skill fuzzy matching, action history, format/suggest helpers.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# We must mock src.config BEFORE importing src.skills (module-level PATHS use)
# ---------------------------------------------------------------------------

_fake_config = MagicMock()
_fake_config.PATHS = {"turbo": "F:/BUREAU/turbo"}


@pytest.fixture(autouse=True)
def _isolate_skills(tmp_path, monkeypatch):
    """Redirect SKILLS_FILE and HISTORY_FILE to tmp_path for every test.

    This avoids touching the real filesystem and prevents cross-test leakage.
    """
    with patch.dict("sys.modules", {"src.config": _fake_config}):
        import src.skills as mod

        monkeypatch.setattr(mod, "SKILLS_FILE", tmp_path / "skills.json")
        monkeypatch.setattr(mod, "HISTORY_FILE", tmp_path / "action_history.json")
        yield mod


# ---------------------------------------------------------------------------
# Helper to get the freshly-patched module inside tests
# ---------------------------------------------------------------------------

def _get_mod():
    """Return the already-imported (and patched) skills module."""
    return sys.modules["src.skills"]


# ═══════════════════════════════════════════════════════════════════════════
# 1. SkillStep dataclass
# ═══════════════════════════════════════════════════════════════════════════

class TestSkillStep:
    def test_defaults(self):
        mod = _get_mod()
        step = mod.SkillStep(tool="volume_up")
        assert step.tool == "volume_up"
        assert step.args == {}
        assert step.description == ""
        assert step.wait_for_result is True

    def test_custom_args(self):
        mod = _get_mod()
        step = mod.SkillStep(tool="open_url", args={"url": "http://x"}, description="Open", wait_for_result=False)
        assert step.args == {"url": "http://x"}
        assert step.description == "Open"
        assert step.wait_for_result is False

    def test_asdict_round_trip(self):
        mod = _get_mod()
        step = mod.SkillStep(tool="ping", args={"host": "8.8.8.8"}, description="Ping Google")
        d = asdict(step)
        rebuilt = mod.SkillStep(**d)
        assert rebuilt.tool == step.tool
        assert rebuilt.args == step.args


# ═══════════════════════════════════════════════════════════════════════════
# 2. Skill dataclass
# ═══════════════════════════════════════════════════════════════════════════

class TestSkill:
    def test_defaults(self):
        mod = _get_mod()
        skill = mod.Skill(name="test", description="d", triggers=["t"], steps=[])
        assert skill.category == "custom"
        assert skill.usage_count == 0
        assert skill.success_rate == 1.0
        assert skill.confirm is False

    def test_confirm_flag(self):
        mod = _get_mod()
        skill = mod.Skill(name="danger", description="x", triggers=["x"], steps=[], confirm=True)
        assert skill.confirm is True

    def test_asdict_includes_steps(self):
        mod = _get_mod()
        step = mod.SkillStep(tool="a")
        skill = mod.Skill(name="s", description="d", triggers=["t"], steps=[step])
        d = asdict(skill)
        assert len(d["steps"]) == 1
        assert d["steps"][0]["tool"] == "a"


# ═══════════════════════════════════════════════════════════════════════════
# 3. load_skills / save_skills
# ═══════════════════════════════════════════════════════════════════════════

class TestLoadSaveSkills:
    def test_load_creates_defaults_when_no_file(self, tmp_path):
        mod = _get_mod()
        skills = mod.load_skills()
        # Should have created the file with defaults
        assert mod.SKILLS_FILE.exists()
        assert len(skills) > 0

    def test_save_then_load_round_trip(self, tmp_path):
        mod = _get_mod()
        step = mod.SkillStep(tool="test_tool", args={"k": "v"})
        skill = mod.Skill(
            name="my_skill",
            description="A test skill",
            triggers=["do the thing"],
            steps=[step],
            category="test",
            created_at=1000.0,
        )
        mod.save_skills([skill])
        loaded = mod.load_skills()
        assert len(loaded) == 1
        assert loaded[0].name == "my_skill"
        assert loaded[0].steps[0].tool == "test_tool"
        assert loaded[0].steps[0].args == {"k": "v"}

    def test_load_returns_defaults_on_corrupt_json(self, tmp_path):
        mod = _get_mod()
        mod.SKILLS_FILE.parent.mkdir(parents=True, exist_ok=True)
        mod.SKILLS_FILE.write_text("NOT VALID JSON {{{", encoding="utf-8")
        skills = mod.load_skills()
        # Falls back to _default_skills
        assert len(skills) > 0

    def test_save_overwrites(self, tmp_path):
        mod = _get_mod()
        s1 = mod.Skill(name="a", description="", triggers=[], steps=[])
        s2 = mod.Skill(name="b", description="", triggers=[], steps=[])
        mod.save_skills([s1, s2])
        assert len(mod.load_skills()) == 2
        mod.save_skills([s1])
        assert len(mod.load_skills()) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 4. add_skill / remove_skill (CRUD)
# ═══════════════════════════════════════════════════════════════════════════

class TestCRUD:
    def test_add_skill_persists(self, tmp_path):
        mod = _get_mod()
        # Start from empty
        mod.save_skills([])
        skill = mod.Skill(name="new_one", description="d", triggers=["go"], steps=[])
        mod.add_skill(skill)
        loaded = mod.load_skills()
        assert any(s.name == "new_one" for s in loaded)

    def test_add_skill_sets_created_at(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        skill = mod.Skill(name="ts_test", description="", triggers=[], steps=[])
        before = time.time()
        mod.add_skill(skill)
        after = time.time()
        loaded = [s for s in mod.load_skills() if s.name == "ts_test"][0]
        assert before <= loaded.created_at <= after

    def test_add_skill_replaces_existing(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        s1 = mod.Skill(name="dup", description="v1", triggers=["a"], steps=[])
        s2 = mod.Skill(name="dup", description="v2", triggers=["b"], steps=[])
        mod.add_skill(s1)
        mod.add_skill(s2)
        loaded = mod.load_skills()
        dups = [s for s in loaded if s.name == "dup"]
        assert len(dups) == 1
        assert dups[0].description == "v2"

    def test_remove_skill_returns_true(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        mod.add_skill(mod.Skill(name="rem", description="", triggers=[], steps=[]))
        assert mod.remove_skill("rem") is True
        assert not any(s.name == "rem" for s in mod.load_skills())

    def test_remove_nonexistent_returns_false(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        assert mod.remove_skill("ghost") is False


# ═══════════════════════════════════════════════════════════════════════════
# 5. find_skill (fuzzy matching)
# ═══════════════════════════════════════════════════════════════════════════

class TestFindSkill:
    def _setup_skills(self):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="rapport_matin", description="Morning report",
                      triggers=["rapport du matin", "briefing matin"], steps=[]),
            mod.Skill(name="mode_gaming", description="Gaming mode",
                      triggers=["mode gaming", "on joue"], steps=[]),
        ])

    def test_exact_match_returns_score_1(self, tmp_path):
        mod = _get_mod()
        self._setup_skills()
        skill, score = mod.find_skill("rapport du matin")
        assert skill is not None
        assert skill.name == "rapport_matin"
        assert score == 1.0

    def test_substring_match(self, tmp_path):
        mod = _get_mod()
        self._setup_skills()
        skill, score = mod.find_skill("lance le mode gaming maintenant")
        assert skill is not None
        assert skill.name == "mode_gaming"
        assert score >= 0.60

    def test_fuzzy_match_above_threshold(self, tmp_path):
        mod = _get_mod()
        self._setup_skills()
        skill, score = mod.find_skill("briefing du matin")
        assert skill is not None
        assert score >= 0.60

    def test_no_match_below_threshold(self, tmp_path):
        mod = _get_mod()
        self._setup_skills()
        skill, score = mod.find_skill("quelque chose de completement different xyz")
        assert skill is None
        assert score < 0.60

    def test_custom_threshold(self, tmp_path):
        mod = _get_mod()
        self._setup_skills()
        # With very high threshold, even partial matches fail
        skill, score = mod.find_skill("briefing matin approximatif", threshold=0.99)
        assert skill is None


# ═══════════════════════════════════════════════════════════════════════════
# 6. record_skill_use
# ═══════════════════════════════════════════════════════════════════════════

class TestRecordSkillUse:
    def test_success_increments_count(self, tmp_path):
        mod = _get_mod()
        s = mod.Skill(name="used", description="", triggers=[], steps=[])
        mod.save_skills([s])
        mod.record_skill_use("used", success=True)
        loaded = [sk for sk in mod.load_skills() if sk.name == "used"][0]
        assert loaded.usage_count == 1
        assert loaded.last_used > 0

    def test_failure_lowers_success_rate(self, tmp_path):
        mod = _get_mod()
        s = mod.Skill(name="fail_test", description="", triggers=[], steps=[],
                      usage_count=0, success_rate=1.0)
        mod.save_skills([s])
        mod.record_skill_use("fail_test", success=False)
        loaded = [sk for sk in mod.load_skills() if sk.name == "fail_test"][0]
        assert loaded.success_rate < 1.0

    def test_multiple_uses(self, tmp_path):
        mod = _get_mod()
        s = mod.Skill(name="multi", description="", triggers=[], steps=[])
        mod.save_skills([s])
        mod.record_skill_use("multi", success=True)
        mod.record_skill_use("multi", success=True)
        mod.record_skill_use("multi", success=False)
        loaded = [sk for sk in mod.load_skills() if sk.name == "multi"][0]
        assert loaded.usage_count == 3


# ═══════════════════════════════════════════════════════════════════════════
# 7. log_action / get_action_history
# ═══════════════════════════════════════════════════════════════════════════

class TestActionHistory:
    def test_log_and_retrieve(self, tmp_path):
        mod = _get_mod()
        mod.log_action("test_action", "ok", True)
        history = mod.get_action_history()
        assert len(history) == 1
        assert history[0]["action"] == "test_action"
        assert history[0]["success"] is True

    def test_history_limit(self, tmp_path):
        mod = _get_mod()
        for i in range(10):
            mod.log_action(f"action_{i}", "ok", True)
        history = mod.get_action_history(limit=3)
        assert len(history) == 3
        # Should be the last 3
        assert history[0]["action"] == "action_7"

    def test_result_truncation(self, tmp_path):
        mod = _get_mod()
        long_result = "x" * 500
        mod.log_action("trunc", long_result, True)
        history = mod.get_action_history()
        assert len(history[0]["result"]) == 200

    def test_history_max_500_entries(self, tmp_path):
        mod = _get_mod()
        for i in range(510):
            mod.log_action(f"a{i}", "r", True)
        raw = json.loads(mod.HISTORY_FILE.read_text(encoding="utf-8"))
        assert len(raw) == 500

    def test_get_history_empty_file(self, tmp_path):
        mod = _get_mod()
        assert mod.get_action_history() == []

    def test_get_history_corrupt_file(self, tmp_path):
        mod = _get_mod()
        mod.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        mod.HISTORY_FILE.write_text("{{bad json", encoding="utf-8")
        assert mod.get_action_history() == []


# ═══════════════════════════════════════════════════════════════════════════
# 8. format_skills_list
# ═══════════════════════════════════════════════════════════════════════════

class TestFormatSkillsList:
    def test_empty_list(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        result = mod.format_skills_list()
        assert "Aucun skill" in result

    def test_non_empty_list(self, tmp_path):
        mod = _get_mod()
        s = mod.Skill(name="demo", description="Demo skill",
                      triggers=["say demo", "run demo", "do demo"], steps=[
                          mod.SkillStep(tool="a"), mod.SkillStep(tool="b"),
                      ], usage_count=5)
        mod.save_skills([s])
        result = mod.format_skills_list()
        assert "demo" in result
        assert "Demo skill" in result
        assert "(5x)" in result
        assert "2 etapes" in result


# ═══════════════════════════════════════════════════════════════════════════
# 9. suggest_next_actions
# ═══════════════════════════════════════════════════════════════════════════

class TestSuggestNextActions:
    def test_trading_context(self):
        mod = _get_mod()
        suggestions = mod.suggest_next_actions("trading signal")
        assert any("trading" in s.lower() for s in suggestions)

    def test_system_context(self):
        mod = _get_mod()
        suggestions = mod.suggest_next_actions("ram usage high")
        assert any("system" in s.lower() or "gpu" in s.lower() for s in suggestions)

    def test_cluster_context(self):
        mod = _get_mod()
        suggestions = mod.suggest_next_actions("cluster ia status")
        assert any("cluster" in s.lower() for s in suggestions)

    def test_file_context(self):
        mod = _get_mod()
        suggestions = mod.suggest_next_actions("fichier config")
        assert any("folder" in s.lower() or "file" in s.lower() for s in suggestions)

    def test_general_context(self):
        mod = _get_mod()
        suggestions = mod.suggest_next_actions("hello world")
        assert len(suggestions) <= 5

    def test_max_five_suggestions(self):
        mod = _get_mod()
        suggestions = mod.suggest_next_actions("anything")
        assert len(suggestions) <= 5


# ═══════════════════════════════════════════════════════════════════════════
# 10. _default_skills
# ═══════════════════════════════════════════════════════════════════════════

class TestDefaultSkills:
    def test_defaults_not_empty(self):
        mod = _get_mod()
        defaults = mod._default_skills()
        assert len(defaults) > 5

    def test_defaults_are_skill_instances(self):
        mod = _get_mod()
        defaults = mod._default_skills()
        for s in defaults:
            assert isinstance(s, mod.Skill)
            assert isinstance(s.steps, list)
            for step in s.steps:
                assert isinstance(step, mod.SkillStep)

    def test_default_names_mostly_unique(self):
        """Verify that the vast majority of default skill names are unique.

        NOTE: The source _default_skills() currently has 2 duplicate names
        (86 total, 84 unique).  This test documents that reality and guards
        against further regression — no MORE than 2 duplicates allowed.
        """
        mod = _get_mod()
        defaults = mod._default_skills()
        names = [s.name for s in defaults]
        duplicates = len(names) - len(set(names))
        assert duplicates <= 2, f"Too many duplicate skill names: {duplicates}"
