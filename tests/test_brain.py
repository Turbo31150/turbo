"""Comprehensive tests for src/brain.py — JARVIS Brain v2.

Tests cover:
- SkillQuality dataclass (properties, serialization, deserialization)
- Quality DB persistence (_load_quality_db, _save_quality_db)
- Feedback loop (record_feedback)
- Temporal decay (apply_decay)
- Skill rankings and quality lookups
- Context-aware suggestions
- Skill composition (compose_skills)
- Pattern detection helpers (_extract_tool, _generate_skill_name, _generate_triggers)
- PatternMatch dataclass
- detect_patterns
- auto_create_skill
- analyze_and_learn
- reject_pattern
- Brain state persistence (_load_brain_state, _save_brain_state)
- get_brain_status
- cluster_suggest_skill (async, mocked HTTP)
- format_brain_report

All external dependencies (filesystem, network, time, imports) are mocked.
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Mock heavy external dependencies BEFORE importing brain
# ---------------------------------------------------------------------------

# Mock src.config (prepare_lmstudio_input, build_lmstudio_payload)
_mock_config_module = MagicMock()
_mock_config_module.prepare_lmstudio_input = MagicMock(side_effect=lambda text, node, model: text)
_mock_config_module.build_lmstudio_payload = MagicMock(
    side_effect=lambda model, inp, **kw: {"model": model, "input": inp}
)
_mock_config_module.config = MagicMock()
_mock_config_module.config.get_node.return_value = MagicMock(url="http://10.5.0.2:1234")
_mock_config_module.JarvisConfig = MagicMock

# Mock src.skills
_mock_skills_module = MagicMock()
_mock_skills_module.load_skills = MagicMock(return_value=[])
_mock_skills_module.add_skill = MagicMock()
_mock_skills_module.get_action_history = MagicMock(return_value=[])
_mock_skills_module.log_action = MagicMock()


@dataclass
class _FakeSkillStep:
    tool: str
    args: dict = field(default_factory=dict)
    description: str = ""
    wait_for_result: bool = True


@dataclass
class _FakeSkill:
    name: str
    description: str
    triggers: list
    steps: list
    category: str = "custom"
    created_at: float = 0.0
    usage_count: int = 0
    last_used: float = 0.0
    success_rate: float = 1.0
    confirm: bool = False


_mock_skills_module.Skill = _FakeSkill
_mock_skills_module.SkillStep = _FakeSkillStep

# Inject mocks into sys.modules before importing brain
sys.modules.setdefault("src.config", _mock_config_module)
sys.modules.setdefault("src.skills", _mock_skills_module)

# Mock optional deps that brain imports lazily
sys.modules.setdefault("httpx", MagicMock())
sys.modules.setdefault("src.event_bus", MagicMock())
sys.modules.setdefault("src.tools", MagicMock())
sys.modules.setdefault("src.cluster_startup", MagicMock())

# Now import brain
from src.brain import (
    SkillQuality,
    PatternMatch,
    BRAIN_FILE,
    QUALITY_FILE,
    DECAY_HALF_LIFE_SECONDS,
    _load_quality_db,
    _save_quality_db,
    _load_brain_state,
    _save_brain_state,
    record_feedback,
    apply_decay,
    get_skill_rankings,
    get_skill_quality,
    suggest_contextual_skills,
    compose_skills,
    _extract_tool,
    _generate_skill_name,
    _generate_triggers,
    detect_patterns,
    auto_create_skill,
    analyze_and_learn,
    reject_pattern,
    get_brain_status,
    cluster_suggest_skill,
    format_brain_report,
)


# ===== SkillQuality Dataclass ==============================================

class TestSkillQuality:

    def test_default_values(self):
        sq = SkillQuality(skill_name="test_skill")
        assert sq.skill_name == "test_skill"
        assert sq.executions == 0
        assert sq.successes == 0
        assert sq.failures == 0
        assert sq.total_duration_ms == 0
        assert sq.satisfaction_sum == 0
        assert sq.last_executed == 0
        assert sq.last_feedback == 0
        assert sq.confidence == 0.5

    def test_success_rate_no_executions(self):
        sq = SkillQuality(skill_name="s")
        assert sq.success_rate == 0.0

    def test_success_rate_with_executions(self):
        sq = SkillQuality(skill_name="s", executions=10, successes=7)
        assert sq.success_rate == pytest.approx(0.7)

    def test_avg_duration_no_executions(self):
        sq = SkillQuality(skill_name="s")
        assert sq.avg_duration_ms == 0.0

    def test_avg_duration_with_executions(self):
        sq = SkillQuality(skill_name="s", executions=4, total_duration_ms=1200)
        assert sq.avg_duration_ms == pytest.approx(300.0)

    def test_user_satisfaction_no_ratings(self):
        sq = SkillQuality(skill_name="s")
        assert sq.user_satisfaction == 0.0

    def test_user_satisfaction_with_ratings(self):
        sq = SkillQuality(skill_name="s", successes=3, failures=2, satisfaction_sum=3.5)
        # rated = 3+2 = 5
        assert sq.user_satisfaction == pytest.approx(0.7)

    def test_composite_score(self):
        sq = SkillQuality(
            skill_name="s",
            executions=10,
            successes=8,
            failures=2,
            satisfaction_sum=7.0,
            confidence=0.9,
        )
        # success_rate=0.8, satisfaction=7.0/10=0.7, confidence=0.9
        expected = 0.4 * 0.8 + 0.3 * 0.7 + 0.3 * 0.9
        assert sq.composite_score == pytest.approx(expected)

    def test_to_dict(self):
        sq = SkillQuality(
            skill_name="demo",
            executions=5,
            successes=4,
            failures=1,
            total_duration_ms=500.0,
            satisfaction_sum=3.5,
            last_executed=1000.0,
            confidence=0.8,
        )
        d = sq.to_dict()
        assert d["skill_name"] == "demo"
        assert d["executions"] == 5
        assert d["successes"] == 4
        assert d["failures"] == 1
        assert d["total_duration_ms"] == 500.0
        assert d["confidence"] == 0.8
        assert "success_rate" in d
        assert "composite_score" in d

    def test_from_dict_full(self):
        d = {
            "skill_name": "from_dict_test",
            "executions": 3,
            "successes": 2,
            "failures": 1,
            "total_duration_ms": 600,
            "satisfaction_sum": 1.5,
            "last_executed": 999,
            "last_feedback": 998,
            "confidence": 0.75,
        }
        sq = SkillQuality.from_dict(d)
        assert sq.skill_name == "from_dict_test"
        assert sq.executions == 3
        assert sq.successes == 2
        assert sq.confidence == 0.75
        assert sq.last_feedback == 998

    def test_from_dict_minimal(self):
        d = {"skill_name": "minimal"}
        sq = SkillQuality.from_dict(d)
        assert sq.skill_name == "minimal"
        assert sq.executions == 0
        assert sq.confidence == 0.5

    def test_roundtrip_dict(self):
        sq = SkillQuality(
            skill_name="roundtrip",
            executions=10,
            successes=7,
            failures=3,
            total_duration_ms=2000,
            satisfaction_sum=6.0,
            last_executed=12345,
            last_feedback=12344,
            confidence=0.85,
        )
        d = sq.to_dict()
        sq2 = SkillQuality.from_dict(d)
        assert sq2.skill_name == sq.skill_name
        assert sq2.executions == sq.executions
        assert sq2.successes == sq.successes
        assert sq2.failures == sq.failures


# ===== Quality DB Persistence ==============================================

class TestQualityDB:

    @patch("src.brain.QUALITY_FILE")
    def test_load_quality_db_file_not_exists(self, mock_path):
        mock_path.exists.return_value = False
        result = _load_quality_db()
        assert result == {}

    @patch("src.brain.QUALITY_FILE")
    def test_load_quality_db_valid_json(self, mock_path):
        mock_path.exists.return_value = True
        data = {
            "skill_a": {
                "skill_name": "skill_a",
                "executions": 5,
                "successes": 4,
                "confidence": 0.9,
            }
        }
        mock_path.read_text.return_value = json.dumps(data)
        result = _load_quality_db()
        assert "skill_a" in result
        assert isinstance(result["skill_a"], SkillQuality)
        assert result["skill_a"].confidence == 0.9

    @patch("src.brain.QUALITY_FILE")
    def test_load_quality_db_corrupt_json(self, mock_path):
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "{invalid json"
        result = _load_quality_db()
        assert result == {}

    @patch("src.brain.QUALITY_FILE")
    def test_save_quality_db(self, mock_path):
        mock_path.parent.mkdir = MagicMock()
        mock_path.write_text = MagicMock()
        db = {"x": SkillQuality(skill_name="x", executions=1, successes=1, confidence=0.8)}
        _save_quality_db(db)
        mock_path.write_text.assert_called_once()
        written = mock_path.write_text.call_args[0][0]
        parsed = json.loads(written)
        assert "x" in parsed
        assert parsed["x"]["skill_name"] == "x"


# ===== Record Feedback =====================================================

class TestRecordFeedback:

    @patch("src.brain._save_quality_db")
    @patch("src.brain._load_quality_db")
    @patch("src.brain.time")
    def test_record_success(self, mock_time, mock_load, mock_save):
        mock_time.time.return_value = 1000.0
        mock_load.return_value = {}

        record_feedback("my_skill", success=True, duration_ms=150, satisfaction=0.9)

        mock_save.assert_called_once()
        db = mock_save.call_args[0][0]
        q = db["my_skill"]
        assert q.executions == 1
        assert q.successes == 1
        assert q.failures == 0
        assert q.total_duration_ms == 150
        assert q.satisfaction_sum == 0.9
        # confidence: 0.5 * 0.8 + 1.0 * 0.2 = 0.6
        assert q.confidence == pytest.approx(0.6)

    @patch("src.brain._save_quality_db")
    @patch("src.brain._load_quality_db")
    @patch("src.brain.time")
    def test_record_failure(self, mock_time, mock_load, mock_save):
        mock_time.time.return_value = 2000.0
        mock_load.return_value = {}

        record_feedback("fail_skill", success=False, duration_ms=50, satisfaction=0.2)

        db = mock_save.call_args[0][0]
        q = db["fail_skill"]
        assert q.executions == 1
        assert q.successes == 0
        assert q.failures == 1
        # confidence: 0.5 * 0.8 + 0.0 * 0.2 = 0.4
        assert q.confidence == pytest.approx(0.4)

    @patch("src.brain._save_quality_db")
    @patch("src.brain._load_quality_db")
    @patch("src.brain.time")
    def test_record_updates_existing(self, mock_time, mock_load, mock_save):
        mock_time.time.return_value = 3000.0
        existing = SkillQuality(skill_name="ex", executions=5, successes=3, confidence=0.7)
        mock_load.return_value = {"ex": existing}

        record_feedback("ex", success=True, duration_ms=100, satisfaction=0.8)

        db = mock_save.call_args[0][0]
        q = db["ex"]
        assert q.executions == 6
        assert q.successes == 4
        # confidence: 0.7 * 0.8 + 1.0 * 0.2 = 0.76
        assert q.confidence == pytest.approx(0.76)


# ===== Temporal Decay ======================================================

class TestApplyDecay:

    @patch("src.brain._save_quality_db")
    @patch("src.brain._load_quality_db")
    @patch("src.brain.time")
    def test_decay_applied_to_old_skills(self, mock_time, mock_load, mock_save):
        now = 1_000_000.0
        mock_time.time.return_value = now
        # Skill last executed 3 days ago
        age = 3 * 24 * 3600
        sq = SkillQuality(
            skill_name="old_skill",
            confidence=0.8,
            last_executed=now - age,
        )
        mock_load.return_value = {"old_skill": sq}

        result = apply_decay()

        assert result == 1
        mock_save.assert_called_once()
        db = mock_save.call_args[0][0]
        # Confidence should have decayed
        assert db["old_skill"].confidence < 0.8

    @patch("src.brain._save_quality_db")
    @patch("src.brain._load_quality_db")
    @patch("src.brain.time")
    def test_no_decay_for_recent_skills(self, mock_time, mock_load, mock_save):
        now = 1_000_000.0
        mock_time.time.return_value = now
        # Skill used 10 minutes ago (< 1 hour threshold)
        sq = SkillQuality(
            skill_name="recent_skill",
            confidence=0.8,
            last_executed=now - 600,
        )
        mock_load.return_value = {"recent_skill": sq}

        result = apply_decay()

        assert result == 0
        mock_save.assert_not_called()

    @patch("src.brain._save_quality_db")
    @patch("src.brain._load_quality_db")
    @patch("src.brain.time")
    def test_decay_minimum_confidence(self, mock_time, mock_load, mock_save):
        # Use a large enough 'now' so that last_executed stays positive
        # (apply_decay skips skills with last_executed <= 0)
        now = 100_000_000.0
        mock_time.time.return_value = now
        # Skill last executed 1 year ago
        age = 365 * 24 * 3600  # 1 year
        sq = SkillQuality(
            skill_name="ancient",
            confidence=0.1,
            last_executed=now - age,  # still positive
        )
        mock_load.return_value = {"ancient": sq}

        apply_decay()

        db = mock_save.call_args[0][0]
        # Confidence should never go below 0.05
        assert db["ancient"].confidence >= 0.05
        assert db["ancient"].confidence < 0.1  # but it did decay

    @patch("src.brain._save_quality_db")
    @patch("src.brain._load_quality_db")
    @patch("src.brain.time")
    def test_no_decay_if_never_executed(self, mock_time, mock_load, mock_save):
        mock_time.time.return_value = 999999.0
        sq = SkillQuality(skill_name="never_run", confidence=0.5, last_executed=0)
        mock_load.return_value = {"never_run": sq}

        result = apply_decay()

        assert result == 0
        mock_save.assert_not_called()


# ===== Skill Rankings & Quality Lookup =====================================

class TestSkillRankings:

    @patch("src.brain._load_quality_db")
    def test_get_skill_rankings_empty(self, mock_load):
        mock_load.return_value = {}
        result = get_skill_rankings(top_n=5)
        assert result == []

    @patch("src.brain._load_quality_db")
    def test_get_skill_rankings_sorted(self, mock_load):
        mock_load.return_value = {
            "low": SkillQuality(skill_name="low", confidence=0.1),
            "high": SkillQuality(skill_name="high", confidence=0.9, executions=10, successes=9, satisfaction_sum=9),
            "mid": SkillQuality(skill_name="mid", confidence=0.5, executions=5, successes=3, satisfaction_sum=3),
        }
        result = get_skill_rankings(top_n=2)
        assert len(result) == 2
        assert result[0]["skill_name"] == "high"

    @patch("src.brain._load_quality_db")
    def test_get_skill_quality_found(self, mock_load):
        mock_load.return_value = {
            "target": SkillQuality(skill_name="target", executions=3, confidence=0.7),
        }
        result = get_skill_quality("target")
        assert result is not None
        assert result["skill_name"] == "target"

    @patch("src.brain._load_quality_db")
    def test_get_skill_quality_not_found(self, mock_load):
        mock_load.return_value = {}
        result = get_skill_quality("nonexistent")
        assert result is None


# ===== Context-Aware Suggestions ===========================================

class TestSuggestContextualSkills:

    def test_returns_list(self):
        # The function has an early return [] due to TODO, so it always returns []
        result = suggest_contextual_skills()
        assert isinstance(result, list)

    def test_max_suggestions_param(self):
        result = suggest_contextual_skills(max_suggestions=1)
        assert isinstance(result, list)
        assert len(result) <= 1


# ===== Pattern Detection Helpers ===========================================

class TestExtractTool:

    def test_with_parentheses(self):
        assert _extract_tool("gpu_info({})") == "gpu_info"

    def test_with_colon(self):
        assert _extract_tool("brain:compose:name") == "brain"

    def test_plain_name(self):
        assert _extract_tool("system_info") == "system_info"

    def test_with_args(self):
        assert _extract_tool('lm_query({"prompt":"hello"})') == "lm_query"


class TestGenerateSkillName:

    def test_two_actions(self):
        name = _generate_skill_name(("gpu_info({})", "system_info({})"))
        assert name == "auto_gpu_info_system_info"

    def test_three_actions(self):
        name = _generate_skill_name(("a()", "b()", "c()"))
        assert name == "auto_a_b_x3"

    def test_five_actions(self):
        name = _generate_skill_name(("a()", "b()", "c()", "d()", "e()"))
        assert name == "auto_a_b_x5"


class TestGenerateTriggers:

    def test_returns_three_triggers(self):
        triggers = _generate_triggers(("gpu_info({})", "system_info({})"))
        assert len(triggers) == 3

    def test_trigger_content(self):
        triggers = _generate_triggers(("gpu()", "sys()"))
        assert "gpu et sys" in triggers
        assert any("lance" in t for t in triggers)
        assert any("pipeline" in t for t in triggers)


# ===== PatternMatch Dataclass ==============================================

class TestPatternMatch:

    def test_create(self):
        pm = PatternMatch(
            actions=["a", "b"],
            count=3,
            confidence=0.6,
            suggested_name="auto_a_b",
            suggested_triggers=["a et b"],
        )
        assert pm.actions == ["a", "b"]
        assert pm.count == 3
        assert pm.confidence == 0.6


# ===== Brain State Persistence =============================================

class TestBrainState:

    @patch("src.brain.BRAIN_FILE")
    def test_load_brain_state_no_file(self, mock_path):
        mock_path.parent.mkdir = MagicMock()
        mock_path.exists.return_value = False
        state = _load_brain_state()
        assert state["patterns_detected"] == []
        assert state["skills_created"] == []
        assert state["last_analysis"] == 0
        assert state["total_analyses"] == 0
        assert state["rejected_patterns"] == []

    @patch("src.brain.BRAIN_FILE")
    def test_load_brain_state_valid(self, mock_path):
        mock_path.parent.mkdir = MagicMock()
        mock_path.exists.return_value = True
        data = {"patterns_detected": [{"name": "p1"}], "skills_created": [], "last_analysis": 100, "total_analyses": 5, "rejected_patterns": ["r1"]}
        mock_path.read_text.return_value = json.dumps(data)
        state = _load_brain_state()
        assert state["total_analyses"] == 5
        assert "r1" in state["rejected_patterns"]

    @patch("src.brain.BRAIN_FILE")
    def test_load_brain_state_corrupt(self, mock_path):
        mock_path.parent.mkdir = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "NOT JSON"
        state = _load_brain_state()
        assert state["total_analyses"] == 0

    @patch("src.brain.BRAIN_FILE")
    def test_save_brain_state(self, mock_path):
        mock_path.parent.mkdir = MagicMock()
        mock_path.write_text = MagicMock()
        _save_brain_state({"total_analyses": 42})
        mock_path.write_text.assert_called_once()
        written = json.loads(mock_path.write_text.call_args[0][0])
        assert written["total_analyses"] == 42


# ===== Detect Patterns =====================================================

class TestDetectPatterns:

    @patch("src.brain.load_skills", return_value=[])
    @patch("src.brain.get_action_history")
    def test_no_patterns_short_history(self, mock_history, mock_skills):
        mock_history.return_value = [{"action": "a"}, {"action": "b"}]
        result = detect_patterns()
        assert result == []

    @patch("src.brain.load_skills", return_value=[])
    @patch("src.brain.get_action_history")
    def test_detects_repeated_pair(self, mock_history, mock_skills):
        # Same pair of actions repeated 3 times
        actions = [{"action": "gpu_info"}, {"action": "system_info"}] * 3
        mock_history.return_value = actions
        result = detect_patterns(min_repeat=2)
        assert len(result) > 0
        assert any(p.count >= 2 for p in result)

    @patch("src.brain.load_skills", return_value=[])
    @patch("src.brain.get_action_history")
    def test_empty_history(self, mock_history, mock_skills):
        mock_history.return_value = []
        result = detect_patterns()
        assert result == []


# ===== Compose Skills ======================================================

class TestComposeSkills:

    @patch("src.brain.log_action")
    @patch("src.brain.add_skill")
    @patch("src.brain.load_skills")
    def test_compose_two_skills(self, mock_load, mock_add, mock_log):
        s1 = _FakeSkill(
            name="s1", description="", triggers=[], category="custom",
            steps=[_FakeSkillStep(tool="gpu_info")],
        )
        s2 = _FakeSkill(
            name="s2", description="", triggers=[], category="custom",
            steps=[_FakeSkillStep(tool="system_info")],
        )
        mock_load.return_value = [s1, s2]

        result = compose_skills("combo", ["s1", "s2"])
        assert result is not None
        assert result.name == "combo"
        assert result.category == "composed"
        assert len(result.steps) == 2
        mock_add.assert_called_once()

    @patch("src.brain.load_skills")
    def test_compose_missing_skill(self, mock_load):
        mock_load.return_value = []
        result = compose_skills("bad", ["nonexistent"])
        assert result is None

    @patch("src.brain.log_action")
    @patch("src.brain.add_skill")
    @patch("src.brain.load_skills")
    def test_compose_default_triggers(self, mock_load, mock_add, mock_log):
        s1 = _FakeSkill(name="s1", description="", triggers=[], category="custom",
                        steps=[_FakeSkillStep(tool="t1")])
        mock_load.return_value = [s1]
        result = compose_skills("solo", ["s1"])
        assert "pipeline solo" in result.triggers
        assert "lance solo" in result.triggers


# ===== Auto Create Skill ===================================================

class TestAutoCreateSkill:

    @patch("src.brain._save_brain_state")
    @patch("src.brain._load_brain_state", return_value={"skills_created": [], "total_analyses": 0})
    @patch("src.brain.log_action")
    @patch("src.brain.add_skill")
    def test_auto_create_basic(self, mock_add, mock_log, mock_load_state, mock_save_state):
        pattern = PatternMatch(
            actions=["gpu_info({})", "system_info({})"],
            count=3,
            confidence=0.6,
            suggested_name="auto_gpu_system",
            suggested_triggers=["gpu et system"],
        )
        skill = auto_create_skill(pattern)
        assert skill is not None
        assert skill.name == "auto_gpu_system"
        assert skill.category == "auto_learned"
        mock_add.assert_called_once()
        mock_log.assert_called_once()


# ===== Analyze and Learn ===================================================

class TestAnalyzeAndLearn:

    @patch("src.brain._save_brain_state")
    @patch("src.brain._load_brain_state", return_value={"rejected_patterns": [], "total_analyses": 0, "skills_created": []})
    @patch("src.brain.get_action_history", return_value=[])
    @patch("src.brain.load_skills", return_value=[])
    @patch("src.brain.detect_patterns", return_value=[])
    def test_no_patterns(self, mock_detect, mock_skills, mock_history, mock_state, mock_save):
        report = analyze_and_learn()
        assert report["patterns_found"] == 0
        assert report["skills_created"] == []

    @patch("src.brain._save_brain_state")
    @patch("src.brain._load_brain_state", return_value={"rejected_patterns": [], "total_analyses": 0, "skills_created": []})
    @patch("src.brain.get_action_history", return_value=[{"action": "a"}] * 10)
    @patch("src.brain.load_skills", return_value=[])
    @patch("src.brain.auto_create_skill")
    @patch("src.brain.detect_patterns")
    def test_auto_create_above_threshold(self, mock_detect, mock_auto, mock_skills, mock_history, mock_state, mock_save):
        pm = PatternMatch(actions=["a", "b"], count=5, confidence=0.8, suggested_name="auto_a_b", suggested_triggers=["a et b"])
        mock_detect.return_value = [pm]
        mock_auto.return_value = _FakeSkill(name="auto_a_b", description="", triggers=[], steps=[], category="auto_learned")

        report = analyze_and_learn(auto_create=True, min_confidence=0.6)
        assert report["patterns_found"] == 1
        assert "auto_a_b" in report["skills_created"]
        mock_auto.assert_called_once()

    @patch("src.brain._save_brain_state")
    @patch("src.brain._load_brain_state", return_value={"rejected_patterns": ["auto_a_b"], "total_analyses": 0, "skills_created": []})
    @patch("src.brain.get_action_history", return_value=[{"action": "a"}] * 10)
    @patch("src.brain.load_skills", return_value=[])
    @patch("src.brain.auto_create_skill")
    @patch("src.brain.detect_patterns")
    def test_skips_rejected_pattern(self, mock_detect, mock_auto, mock_skills, mock_history, mock_state, mock_save):
        pm = PatternMatch(actions=["a", "b"], count=5, confidence=0.9, suggested_name="auto_a_b", suggested_triggers=[])
        mock_detect.return_value = [pm]

        report = analyze_and_learn(auto_create=True, min_confidence=0.5)
        mock_auto.assert_not_called()
        assert report["skills_created"] == []

    @patch("src.brain._save_brain_state")
    @patch("src.brain._load_brain_state", return_value={"rejected_patterns": [], "total_analyses": 0, "skills_created": []})
    @patch("src.brain.get_action_history", return_value=[])
    @patch("src.brain.load_skills", return_value=[])
    @patch("src.brain.auto_create_skill")
    @patch("src.brain.detect_patterns")
    def test_no_auto_create_below_threshold(self, mock_detect, mock_auto, mock_skills, mock_history, mock_state, mock_save):
        pm = PatternMatch(actions=["a", "b"], count=2, confidence=0.3, suggested_name="auto_a_b", suggested_triggers=[])
        mock_detect.return_value = [pm]

        report = analyze_and_learn(auto_create=True, min_confidence=0.6)
        mock_auto.assert_not_called()


# ===== Reject Pattern ======================================================

class TestRejectPattern:

    @patch("src.brain._save_brain_state")
    @patch("src.brain._load_brain_state")
    def test_reject_new_pattern(self, mock_load, mock_save):
        mock_load.return_value = {"rejected_patterns": []}
        reject_pattern("bad_pattern")
        mock_save.assert_called()

    @patch("src.brain._save_brain_state")
    @patch("src.brain._load_brain_state")
    def test_reject_already_rejected(self, mock_load, mock_save):
        mock_load.return_value = {"rejected_patterns": ["already"]}
        reject_pattern("already")
        # Should still save (the function saves unconditionally at the end)
        mock_save.assert_called()


# ===== Get Brain Status ====================================================

class TestGetBrainStatus:

    @patch("src.brain.suggest_contextual_skills", return_value=[])
    @patch("src.brain.get_skill_rankings", return_value=[])
    @patch("src.brain._load_quality_db", return_value={})
    @patch("src.brain.get_action_history", return_value=[])
    @patch("src.brain.load_skills", return_value=[])
    @patch("src.brain._load_brain_state", return_value={"total_analyses": 3, "last_analysis": 100, "patterns_detected": [], "rejected_patterns": []})
    def test_brain_status_structure(self, mock_state, mock_skills, mock_hist, mock_qdb, mock_rank, mock_suggest):
        status = get_brain_status()
        assert "total_skills" in status
        assert "auto_learned" in status
        assert "custom" in status
        assert "composed" in status
        assert "default" in status
        assert "total_actions" in status
        assert "total_analyses" in status
        assert "quality" in status
        assert status["total_analyses"] == 3

    @patch("src.brain.suggest_contextual_skills", return_value=[])
    @patch("src.brain.get_skill_rankings", return_value=[])
    @patch("src.brain._load_quality_db")
    @patch("src.brain.get_action_history", return_value=[])
    @patch("src.brain.load_skills")
    @patch("src.brain._load_brain_state", return_value={"total_analyses": 0, "last_analysis": 0, "patterns_detected": [], "rejected_patterns": []})
    def test_brain_status_skill_categories(self, mock_state, mock_skills, mock_hist, mock_qdb, mock_rank, mock_suggest):
        mock_skills.return_value = [
            _FakeSkill(name="a1", description="", triggers=[], steps=[], category="auto_learned"),
            _FakeSkill(name="c1", description="", triggers=[], steps=[], category="custom"),
            _FakeSkill(name="co1", description="", triggers=[], steps=[], category="composed"),
            _FakeSkill(name="d1", description="", triggers=[], steps=[], category="default"),
        ]
        mock_qdb.return_value = {}
        status = get_brain_status()
        assert status["auto_learned"] == 1
        assert status["custom"] == 1
        assert status["composed"] == 1
        assert status["default"] == 1


# ===== Cluster Suggest Skill (async) =======================================

class TestClusterSuggestSkill:

    @pytest.mark.asyncio
    async def test_cluster_suggest_success(self):
        """Test successful cluster skill suggestion with mocked httpx."""
        expected = {"name": "test_skill", "description": "desc", "triggers": ["t1"], "steps": []}

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"output": [{"type": "message", "content": json.dumps(expected)}]}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        # Build a mock httpx module with proper async context manager
        mock_httpx = MagicMock()
        mock_httpx.ConnectError = ConnectionError
        mock_httpx.HTTPError = Exception

        mock_async_client_ctx = AsyncMock()
        mock_async_client_ctx.__aenter__.return_value = mock_client
        mock_async_client_ctx.__aexit__.return_value = False
        mock_httpx.AsyncClient.return_value = mock_async_client_ctx

        # Mock extract_lms_output to return clean JSON
        mock_tools = MagicMock()
        mock_tools.extract_lms_output.return_value = json.dumps(expected)

        with patch.dict("sys.modules", {"httpx": mock_httpx, "src.tools": mock_tools}), \
             patch("src.brain.build_lmstudio_payload", return_value={"model": "m", "input": "p"}):
            result = await cluster_suggest_skill("test context", node_url="http://fake:1234")
            assert result is not None
            assert result["name"] == "test_skill"

    @pytest.mark.asyncio
    async def test_cluster_suggest_connect_error(self):
        """Test cluster_suggest_skill returns None on connection error."""
        real_connect_error = type("ConnectError", (ConnectionError,), {})

        mock_client = AsyncMock()
        mock_client.post.side_effect = real_connect_error("connection refused")

        mock_httpx = MagicMock()
        mock_httpx.ConnectError = real_connect_error
        mock_httpx.HTTPError = Exception

        mock_async_client_ctx = AsyncMock()
        mock_async_client_ctx.__aenter__.return_value = mock_client
        mock_async_client_ctx.__aexit__.return_value = False
        mock_httpx.AsyncClient.return_value = mock_async_client_ctx

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = await cluster_suggest_skill("ctx", node_url="http://fake:9999")
            assert result is None


# ===== Format Brain Report =================================================

class TestFormatBrainReport:

    @patch("src.brain.get_brain_status")
    def test_format_basic(self, mock_status):
        mock_status.return_value = {
            "total_skills": 10,
            "auto_learned": 2,
            "composed": 1,
            "custom": 3,
            "default": 4,
            "total_actions": 50,
            "total_analyses": 5,
            "patterns_detected": [],
            "quality": {},
            "suggestions": [],
        }
        report = format_brain_report()
        assert "10 skills total" in report
        assert "Auto-appris: 2" in report
        assert "Composes: 1" in report
        assert "Custom: 3" in report
        assert "Par defaut: 4" in report
        assert "Actions loguees: 50" in report

    @patch("src.brain.get_brain_status")
    def test_format_with_patterns(self, mock_status):
        mock_status.return_value = {
            "total_skills": 5,
            "auto_learned": 0,
            "composed": 0,
            "custom": 0,
            "default": 5,
            "total_actions": 20,
            "total_analyses": 1,
            "patterns_detected": [{"name": "auto_gpu_sys", "count": 3, "confidence": 0.6}],
            "quality": {},
            "suggestions": [],
        }
        report = format_brain_report()
        assert "Patterns detectes" in report
        assert "auto_gpu_sys" in report

    @patch("src.brain.get_brain_status")
    def test_format_with_quality_metrics(self, mock_status):
        mock_status.return_value = {
            "total_skills": 5,
            "auto_learned": 0,
            "composed": 0,
            "custom": 0,
            "default": 5,
            "total_actions": 20,
            "total_analyses": 1,
            "patterns_detected": [],
            "quality": {
                "tracked_skills": 3,
                "total_executions": 15,
                "avg_confidence": 0.75,
                "top_skills": [
                    {"skill_name": "best", "composite_score": 0.9, "success_rate": "90.0%"},
                ],
            },
            "suggestions": [],
        }
        report = format_brain_report()
        assert "Qualite:" in report
        assert "3 skills suivis" in report
        assert "Top skills" in report
        assert "best" in report


# ===== Constants ============================================================

class TestConstants:

    def test_decay_half_life(self):
        assert DECAY_HALF_LIFE_SECONDS == 7 * 24 * 3600

    def test_brain_file_path(self):
        assert BRAIN_FILE.name == "brain_state.json"
        assert "data" in str(BRAIN_FILE)

    def test_quality_file_path(self):
        assert QUALITY_FILE.name == "skill_quality.json"
        assert "data" in str(QUALITY_FILE)
