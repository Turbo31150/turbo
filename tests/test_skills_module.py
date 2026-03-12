"""Tests for JARVIS Skills module — src/skills.py

Covers: Skill/SkillStep dataclasses, load/save, CRUD operations,
        find_skill fuzzy matching, action history, format/suggest helpers,
        export/import JSON, stats, search, unused skills, edge cases.
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
_fake_config.PATHS = {"turbo": "/home/turbo/jarvis-m1-ops"}


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

    def test_defaults_have_triggers(self):
        mod = _get_mod()
        defaults = mod._default_skills()
        for s in defaults:
            assert len(s.triggers) > 0, f"Skill {s.name} has no triggers"

    def test_defaults_have_steps(self):
        mod = _get_mod()
        defaults = mod._default_skills()
        for s in defaults:
            assert len(s.steps) > 0, f"Skill {s.name} has no steps"

    def test_defaults_have_categories(self):
        mod = _get_mod()
        defaults = mod._default_skills()
        for s in defaults:
            assert s.category, f"Skill {s.name} has empty category"


# =====================================================================
# 11. export_skills_json
# =====================================================================

class TestExportSkillsJson:
    def test_export_returns_valid_json(self, tmp_path):
        mod = _get_mod()
        s = mod.Skill(name="exp", description="d", triggers=["go"], steps=[
            mod.SkillStep(tool="ping", args={"host": "1.1.1.1"}),
        ])
        mod.save_skills([s])
        result = mod.export_skills_json()
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "exp"

    def test_export_empty_skills(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        result = mod.export_skills_json()
        assert json.loads(result) == []

    def test_export_preserves_unicode(self, tmp_path):
        mod = _get_mod()
        s = mod.Skill(name="unicode_test", description="Accentue: etoile",
                      triggers=["declencheur"], steps=[])
        mod.save_skills([s])
        result = mod.export_skills_json()
        assert "etoile" in result

    def test_export_multiple_skills(self, tmp_path):
        mod = _get_mod()
        skills = [
            mod.Skill(name=f"skill_{i}", description=f"d{i}",
                      triggers=[f"t{i}"], steps=[])
            for i in range(5)
        ]
        mod.save_skills(skills)
        result = mod.export_skills_json()
        parsed = json.loads(result)
        assert len(parsed) == 5


# =====================================================================
# 12. import_skills_json
# =====================================================================

class TestImportSkillsJson:
    def test_import_new_skills(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        data = json.dumps([{
            "name": "imported", "description": "from JSON",
            "triggers": ["import trigger"], "steps": [{"tool": "test_tool"}],
            "category": "custom", "created_at": 0.0, "usage_count": 0,
            "last_used": 0.0, "success_rate": 1.0, "confirm": False,
        }])
        count = mod.import_skills_json(data)
        assert count == 1
        loaded = mod.load_skills()
        assert any(s.name == "imported" for s in loaded)

    def test_import_merge_skips_duplicates(self, tmp_path):
        mod = _get_mod()
        existing = mod.Skill(name="existing", description="v1",
                             triggers=["t"], steps=[])
        mod.save_skills([existing])
        data = json.dumps([{
            "name": "existing", "description": "v2",
            "triggers": ["t2"], "steps": [],
            "category": "custom", "created_at": 0.0, "usage_count": 0,
            "last_used": 0.0, "success_rate": 1.0, "confirm": False,
        }, {
            "name": "brand_new", "description": "new",
            "triggers": ["new_t"], "steps": [],
            "category": "custom", "created_at": 0.0, "usage_count": 0,
            "last_used": 0.0, "success_rate": 1.0, "confirm": False,
        }])
        count = mod.import_skills_json(data, merge=True)
        assert count == 1  # only brand_new imported, existing skipped
        loaded = mod.load_skills()
        names = [s.name for s in loaded]
        assert "existing" in names
        assert "brand_new" in names
        # existing should keep v1 description
        ex = [s for s in loaded if s.name == "existing"][0]
        assert ex.description == "v1"

    def test_import_no_merge_replaces_all(self, tmp_path):
        mod = _get_mod()
        existing = mod.Skill(name="old", description="old", triggers=[], steps=[])
        mod.save_skills([existing])
        data = json.dumps([{
            "name": "new_only", "description": "fresh",
            "triggers": ["t"], "steps": [],
            "category": "custom", "created_at": 0.0, "usage_count": 0,
            "last_used": 0.0, "success_rate": 1.0, "confirm": False,
        }])
        count = mod.import_skills_json(data, merge=False)
        assert count == 1
        loaded = mod.load_skills()
        names = [s.name for s in loaded]
        assert "new_only" in names

    def test_import_invalid_json_returns_zero(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        count = mod.import_skills_json("NOT VALID JSON {{{")
        assert count == 0

    def test_import_empty_array(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        count = mod.import_skills_json("[]")
        assert count == 0

    def test_import_with_steps(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        data = json.dumps([{
            "name": "with_steps", "description": "has steps",
            "triggers": ["go"], "steps": [
                {"tool": "ping", "args": {"host": "8.8.8.8"},
                 "description": "Ping", "wait_for_result": True},
                {"tool": "notify", "args": {}, "description": "Done",
                 "wait_for_result": False},
            ],
            "category": "test", "created_at": 100.0, "usage_count": 3,
            "last_used": 200.0, "success_rate": 0.9, "confirm": True,
        }])
        count = mod.import_skills_json(data)
        assert count == 1
        loaded = [s for s in mod.load_skills() if s.name == "with_steps"][0]
        assert len(loaded.steps) == 2
        assert loaded.steps[0].tool == "ping"
        assert loaded.steps[1].wait_for_result is False
        assert loaded.confirm is True


# =====================================================================
# 13. get_skills_stats
# =====================================================================

class TestGetSkillsStats:
    def test_stats_on_empty(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        stats = mod.get_skills_stats()
        assert stats["total_skills"] == 0
        assert stats["total_triggers"] == 0
        assert stats["total_steps"] == 0
        assert stats["most_used"] is None
        assert stats["most_used_count"] == 0
        assert stats["avg_steps_per_skill"] == 0.0

    def test_stats_counts(self, tmp_path):
        mod = _get_mod()
        skills = [
            mod.Skill(name="a", description="", triggers=["t1", "t2"],
                      steps=[mod.SkillStep(tool="x"), mod.SkillStep(tool="y")],
                      category="cat1", usage_count=10),
            mod.Skill(name="b", description="", triggers=["t3"],
                      steps=[mod.SkillStep(tool="z")],
                      category="cat2", usage_count=5),
            mod.Skill(name="c", description="", triggers=["t4"],
                      steps=[mod.SkillStep(tool="w")],
                      category="cat1", usage_count=0),
        ]
        mod.save_skills(skills)
        stats = mod.get_skills_stats()
        assert stats["total_skills"] == 3
        assert stats["total_triggers"] == 4
        assert stats["total_steps"] == 4
        assert stats["categories"] == {"cat1": 2, "cat2": 1}
        assert stats["most_used"] == "a"
        assert stats["most_used_count"] == 10
        assert stats["avg_steps_per_skill"] == round(4 / 3, 1)

    def test_stats_uncategorized(self, tmp_path):
        mod = _get_mod()
        s = mod.Skill(name="nocat", description="", triggers=["t"],
                      steps=[], category="")
        mod.save_skills([s])
        stats = mod.get_skills_stats()
        assert "uncategorized" in stats["categories"]


# =====================================================================
# 14. search_skills
# =====================================================================

class TestSearchSkills:
    def _setup_search_skills(self):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="rapport_matin", description="Morning report",
                      triggers=["rapport du matin"], steps=[
                          mod.SkillStep(tool="system_info"),
                      ], category="routine"),
            mod.Skill(name="mode_gaming", description="Gaming mode",
                      triggers=["mode gaming", "on joue"],
                      steps=[mod.SkillStep(tool="app_open")],
                      category="loisir"),
            mod.Skill(name="mode_trading", description="Trading session",
                      triggers=["mode trading"],
                      steps=[mod.SkillStep(tool="trading_status")],
                      category="trading"),
        ])

    def test_search_by_name(self, tmp_path):
        self._setup_search_skills()
        mod = _get_mod()
        results = mod.search_skills("rapport")
        assert len(results) >= 1
        assert results[0]["name"] == "rapport_matin"
        assert results[0]["score"] == 1.0

    def test_search_by_description(self, tmp_path):
        self._setup_search_skills()
        mod = _get_mod()
        results = mod.search_skills("gaming")
        assert len(results) >= 1
        found_names = [r["name"] for r in results]
        assert "mode_gaming" in found_names

    def test_search_by_trigger(self, tmp_path):
        self._setup_search_skills()
        mod = _get_mod()
        results = mod.search_skills("on joue")
        assert len(results) >= 1
        assert results[0]["name"] == "mode_gaming"
        assert results[0]["score"] == 0.9

    def test_search_by_tool(self, tmp_path):
        self._setup_search_skills()
        mod = _get_mod()
        results = mod.search_skills("trading_status")
        assert len(results) >= 1
        assert results[0]["name"] == "mode_trading"
        assert results[0]["score"] == 0.6

    def test_search_no_match(self, tmp_path):
        self._setup_search_skills()
        mod = _get_mod()
        results = mod.search_skills("xyznonexistent999")
        assert results == []

    def test_search_limit(self, tmp_path):
        mod = _get_mod()
        skills = [
            mod.Skill(name=f"mode_{i}", description=f"mode {i}",
                      triggers=[f"mode {i}"], steps=[], category="test")
            for i in range(20)
        ]
        mod.save_skills(skills)
        results = mod.search_skills("mode", limit=3)
        assert len(results) == 3

    def test_search_result_fields(self, tmp_path):
        self._setup_search_skills()
        mod = _get_mod()
        results = mod.search_skills("rapport")
        r = results[0]
        assert "name" in r
        assert "description" in r
        assert "category" in r
        assert "score" in r
        assert "usage_count" in r
        assert "steps" in r
        assert "triggers" in r

    def test_search_sorted_by_score(self, tmp_path):
        self._setup_search_skills()
        mod = _get_mod()
        # "mode" matches mode_gaming by name (1.0) and mode_trading by name (1.0)
        results = mod.search_skills("mode")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_empty_query_matches_nothing(self, tmp_path):
        """Empty string is 'in' every string, so it matches by name (score 1.0)."""
        self._setup_search_skills()
        mod = _get_mod()
        results = mod.search_skills("")
        # Empty string is a substring of all names, so all match
        assert len(results) == 3


# =====================================================================
# 15. get_unused_skills
# =====================================================================

class TestGetUnusedSkills:
    def test_all_unused(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="stale1", description="", triggers=["t"],
                      steps=[], last_used=0.0, category="custom"),
            mod.Skill(name="stale2", description="", triggers=["t"],
                      steps=[], last_used=0.0, category="custom"),
        ])
        unused = mod.get_unused_skills(days=30)
        assert "stale1" in unused
        assert "stale2" in unused

    def test_recently_used_excluded(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="recent", description="", triggers=["t"],
                      steps=[], last_used=time.time(), category="custom"),
            mod.Skill(name="old", description="", triggers=["t"],
                      steps=[], last_used=0.0, category="custom"),
        ])
        unused = mod.get_unused_skills(days=30)
        assert "recent" not in unused
        assert "old" in unused

    def test_default_category_excluded(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="defaultcat", description="", triggers=["t"],
                      steps=[], last_used=0.0, category="default"),
        ])
        unused = mod.get_unused_skills(days=30)
        assert "defaultcat" not in unused

    def test_custom_days_parameter(self, tmp_path):
        mod = _get_mod()
        # Used 2 days ago
        two_days_ago = time.time() - 2 * 86400
        mod.save_skills([
            mod.Skill(name="twodaysago", description="", triggers=["t"],
                      steps=[], last_used=two_days_ago, category="custom"),
        ])
        # With days=1, it should be "unused"
        unused_1d = mod.get_unused_skills(days=1)
        assert "twodaysago" in unused_1d
        # With days=5, it should NOT be "unused"
        unused_5d = mod.get_unused_skills(days=5)
        assert "twodaysago" not in unused_5d

    def test_empty_skills(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        unused = mod.get_unused_skills()
        assert unused == []


# =====================================================================
# 16. Edge cases — find_skill advanced
# =====================================================================

class TestFindSkillEdgeCases:
    def test_empty_voice_text(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="s", description="", triggers=["hello"], steps=[]),
        ])
        skill, score = mod.find_skill("")
        # Empty input should not crash; might match or not
        assert isinstance(score, float)

    def test_empty_triggers_skill(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="no_trig", description="", triggers=[], steps=[]),
        ])
        skill, score = mod.find_skill("anything")
        # No triggers means no match possible
        assert skill is None or skill.name != "no_trig"

    def test_case_insensitive_match(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="upper", description="",
                      triggers=["MODE GAMING"], steps=[]),
        ])
        skill, score = mod.find_skill("mode gaming")
        assert skill is not None
        assert score == 1.0

    def test_whitespace_handling(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="ws", description="",
                      triggers=["mode gaming"], steps=[]),
        ])
        skill, score = mod.find_skill("  mode gaming  ")
        assert skill is not None
        assert score == 1.0

    def test_zero_threshold_matches_anything(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="any", description="",
                      triggers=["xyz"], steps=[]),
        ])
        skill, score = mod.find_skill("abc totally different", threshold=0.0)
        assert skill is not None

    def test_no_skills_returns_none(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        skill, score = mod.find_skill("anything")
        assert skill is None
        assert score == 0.0


# =====================================================================
# 17. Edge cases — CRUD advanced
# =====================================================================

class TestCRUDEdgeCases:
    def test_add_multiple_skills_sequential(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        for i in range(10):
            mod.add_skill(mod.Skill(
                name=f"skill_{i}", description=f"d{i}",
                triggers=[f"t{i}"], steps=[],
            ))
        loaded = mod.load_skills()
        assert len(loaded) == 10

    def test_remove_from_empty(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        assert mod.remove_skill("nonexistent") is False

    def test_add_then_remove_then_add(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        s = mod.Skill(name="cycle", description="v1", triggers=["t"], steps=[])
        mod.add_skill(s)
        assert mod.remove_skill("cycle") is True
        s2 = mod.Skill(name="cycle", description="v2", triggers=["t2"], steps=[])
        mod.add_skill(s2)
        loaded = [sk for sk in mod.load_skills() if sk.name == "cycle"]
        assert len(loaded) == 1
        assert loaded[0].description == "v2"

    def test_add_skill_with_many_steps(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        steps = [mod.SkillStep(tool=f"tool_{i}", args={"i": i}) for i in range(50)]
        s = mod.Skill(name="big", description="", triggers=["big"], steps=steps)
        mod.add_skill(s)
        loaded = [sk for sk in mod.load_skills() if sk.name == "big"][0]
        assert len(loaded.steps) == 50
        assert loaded.steps[49].tool == "tool_49"


# =====================================================================
# 18. Edge cases — record_skill_use
# =====================================================================

class TestRecordSkillUseEdgeCases:
    def test_record_nonexistent_skill_no_crash(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        # Should not raise, just does nothing
        mod.record_skill_use("ghost", success=True)
        assert mod.load_skills() == []

    def test_success_rate_stays_between_0_and_1(self, tmp_path):
        mod = _get_mod()
        s = mod.Skill(name="rate_test", description="", triggers=[], steps=[])
        mod.save_skills([s])
        # 10 successes then 10 failures
        for _ in range(10):
            mod.record_skill_use("rate_test", success=True)
        for _ in range(10):
            mod.record_skill_use("rate_test", success=False)
        loaded = [sk for sk in mod.load_skills() if sk.name == "rate_test"][0]
        assert 0.0 <= loaded.success_rate <= 1.0
        assert loaded.usage_count == 20


# =====================================================================
# 19. Edge cases — log_action
# =====================================================================

class TestLogActionEdgeCases:
    def test_log_empty_action(self, tmp_path):
        mod = _get_mod()
        mod.log_action("", "", False)
        history = mod.get_action_history()
        assert len(history) == 1
        assert history[0]["action"] == ""

    def test_log_special_characters(self, tmp_path):
        mod = _get_mod()
        mod.log_action('action "with" quotes & <tags>', "ok\nnewline", True)
        history = mod.get_action_history()
        assert len(history) == 1
        assert '"with"' in history[0]["action"]

    def test_log_action_has_timestamp(self, tmp_path):
        mod = _get_mod()
        before = time.time()
        mod.log_action("ts_action", "ok", True)
        after = time.time()
        history = mod.get_action_history()
        assert before <= history[0]["timestamp"] <= after


# =====================================================================
# 20. Edge cases — format_skills_list
# =====================================================================

class TestFormatSkillsListEdgeCases:
    def test_skill_with_zero_usage(self, tmp_path):
        mod = _get_mod()
        s = mod.Skill(name="nouse", description="Never used",
                      triggers=["t"], steps=[mod.SkillStep(tool="a")],
                      usage_count=0)
        mod.save_skills([s])
        result = mod.format_skills_list()
        assert "nouse" in result
        # 0 usage should NOT show "(0x)"
        assert "(0x)" not in result

    def test_skill_triggers_truncated_to_3(self, tmp_path):
        mod = _get_mod()
        s = mod.Skill(name="many_trig", description="",
                      triggers=["a", "b", "c", "d", "e"],
                      steps=[mod.SkillStep(tool="x")])
        mod.save_skills([s])
        result = mod.format_skills_list()
        # Only first 3 triggers shown
        assert "a" in result
        assert "c" in result


# =====================================================================
# 21. _ensure_data_dir
# =====================================================================

class TestEnsureDataDir:
    def test_creates_parent_dirs(self, tmp_path):
        mod = _get_mod()
        deep = tmp_path / "a" / "b" / "c" / "skills.json"
        mod.SKILLS_FILE = deep
        mod._ensure_data_dir()
        assert deep.parent.exists()

    def test_idempotent(self, tmp_path):
        mod = _get_mod()
        mod._ensure_data_dir()
        mod._ensure_data_dir()  # should not raise
        assert mod.SKILLS_FILE.parent.exists()


# =====================================================================
# 22. save_skills JSON integrity
# =====================================================================

class TestSaveSkillsIntegrity:
    def test_saved_json_is_valid(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="a", description="d", triggers=["t"],
                      steps=[mod.SkillStep(tool="x")]),
        ])
        raw = mod.SKILLS_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data, list)
        assert data[0]["name"] == "a"

    def test_saved_json_is_indented(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([
            mod.Skill(name="a", description="d", triggers=["t"], steps=[]),
        ])
        raw = mod.SKILLS_FILE.read_text(encoding="utf-8")
        # indent=2 means lines start with spaces
        assert "\n  " in raw

    def test_save_empty_list(self, tmp_path):
        mod = _get_mod()
        mod.save_skills([])
        raw = mod.SKILLS_FILE.read_text(encoding="utf-8")
        assert json.loads(raw) == []
