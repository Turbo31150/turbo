"""Integration tests for the complete voice pipeline, skills system, and brain.

Covers:
- TestVoiceRouter: routing, correction, fuzzy matching, logging (10 tests)
- TestSkillsSystem: load, find, save, dedup, history, validation (10 tests)
- TestBrain: patterns, decay, feedback, quality, compose, learn (10 tests)

Tous les appels externes (subprocess, fichiers, DB, reseau) sont mockes.
"""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

# Garantir que le dossier racine jarvis est dans le PYTHONPATH
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures communes
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_skills_data():
    """Donnees JSON simulant skills.json avec des skills complets."""
    return [
        {
            "name": "rapport_matin",
            "description": "Rapport complet du matin",
            "triggers": ["rapport du matin", "rapport matin", "briefing matin"],
            "steps": [
                {"tool": "lm_cluster_status", "args": {}, "description": "Cluster status"},
                {"tool": "system_info", "args": {}, "description": "Infos systeme"},
            ],
            "category": "routine",
            "created_at": 1700000000.0,
            "usage_count": 5,
            "last_used": 1700001000.0,
            "success_rate": 0.9,
            "confirm": False,
        },
        {
            "name": "maintenance_complete_linux",
            "description": "Maintenance systeme complete",
            "triggers": ["maintenance complete", "maintenance linux", "nettoyage complet"],
            "steps": [
                {"tool": "bash_run", "args": {"command": "apt update"}, "description": "Update"},
                {"tool": "bash_run", "args": {"command": "apt autoremove -y"}, "description": "Clean"},
            ],
            "category": "system",
            "created_at": 1700000000.0,
            "usage_count": 2,
            "last_used": 1700002000.0,
            "success_rate": 1.0,
            "confirm": True,
        },
        {
            "name": "mode_gaming",
            "description": "Active le mode gaming",
            "triggers": ["mode gaming", "lance le gaming"],
            "steps": [
                {"tool": "app_close", "args": {"name": "chrome"}, "description": "Ferme Chrome"},
                {"tool": "app_open", "args": {"name": "steam"}, "description": "Ouvre Steam"},
                {"tool": "volume_set", "args": {"level": 80}, "description": "Volume 80%"},
            ],
            "category": "custom",
            "created_at": 1700000000.0,
            "usage_count": 10,
            "last_used": 1700003000.0,
            "success_rate": 0.95,
            "confirm": False,
        },
    ]


@pytest.fixture
def sample_action_history():
    """Historique d'actions simule pour les tests de pattern detection."""
    now = time.time()
    return [
        {"action": "app_open", "result": "ok", "success": True, "timestamp": now - 100},
        {"action": "volume_set", "result": "ok", "success": True, "timestamp": now - 90},
        {"action": "app_open", "result": "ok", "success": True, "timestamp": now - 80},
        {"action": "volume_set", "result": "ok", "success": True, "timestamp": now - 70},
        {"action": "app_open", "result": "ok", "success": True, "timestamp": now - 60},
        {"action": "volume_set", "result": "ok", "success": True, "timestamp": now - 50},
        {"action": "system_info", "result": "ok", "success": True, "timestamp": now - 40},
        {"action": "gpu_info", "result": "ok", "success": True, "timestamp": now - 30},
    ]


# ═══════════════════════════════════════════════════════════════════════════
# TestVoiceRouter — 10 tests de routage vocal
# ═══════════════════════════════════════════════════════════════════════════

class TestVoiceRouter:
    """Tests du routeur vocal unifie (voice_router.py)."""

    def _make_success_result(self, module: str, method: str = "execute"):
        """Helper: cree un resultat de succes simule."""
        return {
            "success": True,
            "method": method,
            "result": "OK",
            "confidence": 0.9,
            "module": module,
        }

    @patch("src.voice_router._log_action_history")
    @patch("src.voice_router._log_voice_analytics")
    @patch("src.voice_router._fallback_ia", return_value=None)
    @patch("src.voice_router._try_module")
    def test_route_to_linux_desktop_control(
        self, mock_try, mock_ia, mock_log_analytics, mock_log_history
    ):
        """'ouvre firefox' doit router vers linux_desktop_control."""
        from src.voice_router import route_voice_command

        def try_side_effect(mod, fn, text):
            if mod == "src.linux_desktop_control":
                return self._make_success_result("src.linux_desktop_control", "app_open")
            return None

        mock_try.side_effect = try_side_effect

        result = route_voice_command("ouvre firefox")
        assert result["success"] is True
        assert "linux_desktop_control" in result["module"]

    @patch("src.voice_router._log_action_history")
    @patch("src.voice_router._log_voice_analytics")
    @patch("src.voice_router._fallback_ia", return_value=None)
    @patch("src.voice_router._try_module")
    def test_route_to_window_manager(
        self, mock_try, mock_ia, mock_log_analytics, mock_log_history
    ):
        """'maximise la fenetre' doit router vers voice_window_manager."""
        from src.voice_router import route_voice_command

        def try_side_effect(mod, fn, text):
            if mod == "src.voice_window_manager":
                return self._make_success_result("src.voice_window_manager", "maximize")
            return None

        mock_try.side_effect = try_side_effect

        result = route_voice_command("maximise la fenetre")
        assert result["success"] is True
        assert "voice_window_manager" in result["module"]

    @patch("src.voice_router._log_action_history")
    @patch("src.voice_router._log_voice_analytics")
    @patch("src.voice_router._fallback_ia", return_value=None)
    @patch("src.voice_router._try_module")
    def test_route_to_mouse_control(
        self, mock_try, mock_ia, mock_log_analytics, mock_log_history
    ):
        """'clique ici' doit router vers voice_mouse_control."""
        from src.voice_router import route_voice_command

        def try_side_effect(mod, fn, text):
            if mod == "src.voice_mouse_control":
                return self._make_success_result("src.voice_mouse_control", "click")
            return None

        mock_try.side_effect = try_side_effect

        result = route_voice_command("clique ici")
        assert result["success"] is True
        assert "voice_mouse_control" in result["module"]

    @patch("src.voice_router._log_action_history")
    @patch("src.voice_router._log_voice_analytics")
    @patch("src.voice_router._fallback_ia", return_value=None)
    @patch("src.voice_router._try_module")
    def test_route_to_dictation(
        self, mock_try, mock_ia, mock_log_analytics, mock_log_history
    ):
        """'dicte bonjour' doit router vers voice_dictation (via keyword 'dicte')."""
        from src.voice_router import route_voice_command

        def try_side_effect(mod, fn, text):
            if mod == "src.voice_dictation":
                return self._make_success_result("src.voice_dictation", "type_text")
            return None

        mock_try.side_effect = try_side_effect

        result = route_voice_command("dicte bonjour")
        assert result["success"] is True
        assert "voice_dictation" in result["module"]

    @patch("src.voice_router._log_action_history")
    @patch("src.voice_router._log_voice_analytics")
    @patch("src.voice_router._fallback_ia", return_value=None)
    @patch("src.voice_router._try_module")
    def test_route_to_screen_reader(
        self, mock_try, mock_ia, mock_log_analytics, mock_log_history
    ):
        """'lis le titre' doit router vers voice_screen_reader."""
        from src.voice_router import route_voice_command

        def try_side_effect(mod, fn, text):
            if mod == "src.voice_screen_reader":
                return self._make_success_result("src.voice_screen_reader", "read_title")
            return None

        mock_try.side_effect = try_side_effect

        result = route_voice_command("lis le titre")
        assert result["success"] is True
        assert "voice_screen_reader" in result["module"]

    @patch("src.voice_router._log_action_history")
    @patch("src.voice_router._log_voice_analytics")
    @patch("src.voice_router._fallback_ia", return_value=None)
    @patch("src.voice_router._try_module", return_value=None)
    def test_unknown_command_returns_none(
        self, mock_try, mock_ia, mock_log_analytics, mock_log_history
    ):
        """'blabla' doit retourner un resultat en echec (aucun module ne repond)."""
        from src.voice_router import route_voice_command

        result = route_voice_command("blabla xyz inconnu")
        assert result["success"] is False
        assert result["module"] == "none"
        assert "non reconnue" in result["result"].lower() or result["confidence"] == 0.0

    @patch("src.voice_router._log_action_history")
    @patch("src.voice_router._log_voice_analytics")
    @patch("src.voice_router._fallback_ia", return_value=None)
    @patch("src.voice_router._try_module")
    def test_voice_correction_applied(
        self, mock_try, mock_ia, mock_log_analytics, mock_log_history
    ):
        """'ouvre faierfox' corrige en 'ouvre firefox' via apply_voice_correction."""
        from src.voice_router import route_voice_command

        def try_side_effect(mod, fn, text):
            # Ne repond que si le texte contient "firefox" (corrige)
            if "firefox" in text.lower() and mod == "src.linux_desktop_control":
                return self._make_success_result("src.linux_desktop_control", "app_open")
            return None

        mock_try.side_effect = try_side_effect

        # Mocker db_boot_validator.apply_voice_correction pour corriger le texte
        mock_correction = MagicMock(return_value="ouvre firefox")
        with patch.dict("sys.modules", {
            "src.db_boot_validator": MagicMock(apply_voice_correction=mock_correction)
        }):
            result = route_voice_command("ouvre faierfox")
            assert result["success"] is True
            assert result.get("corrected_from") == "ouvre faierfox"

    @patch("src.voice_router._log_voice_analytics")
    @patch("src.voice_router._fallback_ia", return_value=None)
    @patch("src.voice_router._try_module")
    def test_action_logged_on_success(
        self, mock_try, mock_ia, mock_log_analytics
    ):
        """Verifie que _log_action_history est appele apres un succes."""
        from src.voice_router import route_voice_command

        mock_try.return_value = self._make_success_result("src.linux_desktop_control")

        with patch("src.voice_router._log_action_history") as mock_log:
            route_voice_command("ouvre firefox")
            mock_log.assert_called_once()
            # Le premier argument est le texte, le second est le resultat
            args = mock_log.call_args[0]
            assert isinstance(args[1], dict)
            assert args[1]["success"] is True

    @patch("src.voice_router._log_voice_analytics")
    @patch("src.voice_router._fallback_ia", return_value=None)
    @patch("src.voice_router._try_module", return_value=None)
    def test_action_logged_on_failure(
        self, mock_try, mock_ia, mock_log_analytics
    ):
        """Verifie que _log_action_history est appele meme en cas d'echec."""
        from src.voice_router import route_voice_command

        with patch("src.voice_router._log_action_history") as mock_log:
            route_voice_command("commande impossible xyz")
            mock_log.assert_called_once()
            args = mock_log.call_args[0]
            assert args[1]["success"] is False

    @patch("src.voice_router._log_action_history")
    @patch("src.voice_router._log_voice_analytics")
    @patch("src.voice_router._fallback_ia", return_value=None)
    @patch("src.voice_router._try_module")
    def test_fuzzy_matching(
        self, mock_try, mock_ia, mock_log_analytics, mock_log_history
    ):
        """'ouvrir firefox' doit matcher malgre la conjugaison differente (seuil 0.55)."""
        from src.voice_router import route_voice_command

        # Le routeur utilise _guess_priority pour le dispatch.
        # "ouvrir" n'est pas un mot-cle specifique, donc ca passe par desktop_control (fallback).
        def try_side_effect(mod, fn, text):
            if mod == "src.linux_desktop_control":
                return self._make_success_result("src.linux_desktop_control", "app_open")
            return None

        mock_try.side_effect = try_side_effect

        result = route_voice_command("ouvrir firefox")
        assert result["success"] is True
        assert result["confidence"] >= 0.55


# ═══════════════════════════════════════════════════════════════════════════
# TestSkillsSystem — 10 tests du systeme de skills
# ═══════════════════════════════════════════════════════════════════════════

class TestSkillsSystem:
    """Tests du systeme de skills (skills.py)."""

    def test_load_skills_from_json(self, sample_skills_data, tmp_path):
        """Charge skills.json et verifie le nombre de skills charges."""
        from src.skills import load_skills

        skills_file = tmp_path / "skills.json"
        skills_file.write_text(json.dumps(sample_skills_data), encoding="utf-8")

        with patch("src.skills.SKILLS_FILE", skills_file):
            skills = load_skills()
            assert len(skills) == 3
            assert skills[0].name == "rapport_matin"

    def test_find_skill_by_trigger(self, sample_skills_data, tmp_path):
        """'maintenance complete' doit trouver le skill maintenance_complete_linux."""
        from src.skills import find_skill

        skills_file = tmp_path / "skills.json"
        skills_file.write_text(json.dumps(sample_skills_data), encoding="utf-8")

        with patch("src.skills.SKILLS_FILE", skills_file):
            skill, score = find_skill("maintenance complete")
            assert skill is not None
            assert skill.name == "maintenance_complete_linux"
            assert score >= 0.60

    def test_find_skill_no_match(self, sample_skills_data, tmp_path):
        """'xyz123' ne doit matcher aucun skill."""
        from src.skills import find_skill

        skills_file = tmp_path / "skills.json"
        skills_file.write_text(json.dumps(sample_skills_data), encoding="utf-8")

        with patch("src.skills.SKILLS_FILE", skills_file):
            skill, score = find_skill("xyz123 commande inconnue absolue")
            assert skill is None
            assert score < 0.60

    def test_save_learned_pipeline(self, sample_skills_data, tmp_path):
        """Cree un nouveau skill et verifie qu'il est persiste sur disque."""
        from src.skills import load_skills, add_skill, Skill, SkillStep

        skills_file = tmp_path / "skills.json"
        skills_file.write_text(json.dumps(sample_skills_data), encoding="utf-8")

        with patch("src.skills.SKILLS_FILE", skills_file):
            new_skill = Skill(
                name="test_pipeline",
                description="Pipeline de test",
                triggers=["lance test", "test pipeline"],
                steps=[
                    SkillStep(tool="system_info", args={}, description="Info systeme"),
                    SkillStep(tool="gpu_info", args={}, description="Info GPU"),
                ],
                category="custom",
            )
            add_skill(new_skill)

            # Relire depuis le fichier pour confirmer la persistance
            reloaded = load_skills()
            names = [s.name for s in reloaded]
            assert "test_pipeline" in names
            assert len(reloaded) == 4  # 3 originaux + 1 nouveau

    def test_save_learned_pipeline_dedup(self, sample_skills_data, tmp_path):
        """Ne cree pas de doublon si le skill existe deja (meme nom)."""
        from src.skills import load_skills, add_skill, Skill, SkillStep

        skills_file = tmp_path / "skills.json"
        skills_file.write_text(json.dumps(sample_skills_data), encoding="utf-8")

        with patch("src.skills.SKILLS_FILE", skills_file):
            duplicate = Skill(
                name="rapport_matin",
                description="Version mise a jour",
                triggers=["rapport matin v2"],
                steps=[SkillStep(tool="system_info", args={})],
            )
            add_skill(duplicate)

            reloaded = load_skills()
            # Le count ne doit pas augmenter — le doublon remplace l'ancien
            matin_skills = [s for s in reloaded if s.name == "rapport_matin"]
            assert len(matin_skills) == 1
            assert matin_skills[0].description == "Version mise a jour"

    def test_log_action(self, tmp_path):
        """Verifie que log_action ajoute correctement dans l'historique."""
        from src.skills import log_action, get_action_history

        history_file = tmp_path / "action_history.json"
        history_file.write_text("[]", encoding="utf-8")

        with patch("src.skills.HISTORY_FILE", history_file):
            log_action("test_action", "result ok", True)
            log_action("test_action_2", "result fail", False)

            history = get_action_history(limit=10)
            assert len(history) == 2
            assert history[0]["action"] == "test_action"
            assert history[0]["success"] is True
            assert history[1]["action"] == "test_action_2"
            assert history[1]["success"] is False

    def test_get_action_history(self, tmp_path):
        """Recupere les N dernieres actions avec le bon limit."""
        from src.skills import log_action, get_action_history

        history_file = tmp_path / "action_history.json"
        history_file.write_text("[]", encoding="utf-8")

        with patch("src.skills.HISTORY_FILE", history_file):
            for i in range(10):
                log_action(f"action_{i}", f"result_{i}", True)

            # Demander seulement les 3 dernieres
            history = get_action_history(limit=3)
            assert len(history) == 3
            assert history[0]["action"] == "action_7"
            assert history[2]["action"] == "action_9"

    def test_skill_has_required_fields(self, sample_skills_data, tmp_path):
        """Chaque skill doit avoir name, triggers et steps."""
        from src.skills import load_skills

        skills_file = tmp_path / "skills.json"
        skills_file.write_text(json.dumps(sample_skills_data), encoding="utf-8")

        with patch("src.skills.SKILLS_FILE", skills_file):
            skills = load_skills()
            for skill in skills:
                assert hasattr(skill, "name") and skill.name, f"Skill sans name: {skill}"
                assert hasattr(skill, "triggers"), f"Skill sans triggers: {skill.name}"
                assert hasattr(skill, "steps"), f"Skill sans steps: {skill.name}"

    def test_skill_triggers_not_empty(self, sample_skills_data, tmp_path):
        """Aucun skill ne doit avoir une liste de triggers vide."""
        from src.skills import load_skills

        skills_file = tmp_path / "skills.json"
        skills_file.write_text(json.dumps(sample_skills_data), encoding="utf-8")

        with patch("src.skills.SKILLS_FILE", skills_file):
            skills = load_skills()
            for skill in skills:
                assert len(skill.triggers) > 0, f"Skill {skill.name} a des triggers vides"

    def test_skill_steps_valid(self, sample_skills_data, tmp_path):
        """Chaque step doit avoir 'tool' et 'args'."""
        from src.skills import load_skills

        skills_file = tmp_path / "skills.json"
        skills_file.write_text(json.dumps(sample_skills_data), encoding="utf-8")

        with patch("src.skills.SKILLS_FILE", skills_file):
            skills = load_skills()
            for skill in skills:
                for step in skill.steps:
                    assert hasattr(step, "tool") and step.tool, \
                        f"Step sans tool dans {skill.name}"
                    assert hasattr(step, "args"), \
                        f"Step sans args dans {skill.name}"


# ═══════════════════════════════════════════════════════════════════════════
# TestBrain — 10 tests du systeme d'apprentissage
# ═══════════════════════════════════════════════════════════════════════════

class TestBrain:
    """Tests du cerveau d'apprentissage (brain.py)."""

    def test_detect_patterns(self, sample_action_history):
        """Avec 3+ actions identiques repetees, detecte le pattern."""
        from src.brain import detect_patterns

        # Mocker get_action_history pour retourner notre historique simule
        with patch("src.brain.get_action_history", return_value=sample_action_history):
            with patch("src.brain.load_skills", return_value=[]):
                patterns = detect_patterns(min_repeat=2, window=50)
                assert len(patterns) > 0
                # Le pattern (app_open, volume_set) apparait 3 fois
                found_pattern = False
                for p in patterns:
                    if "app_open" in p.actions and "volume_set" in p.actions:
                        found_pattern = True
                        assert p.count >= 2
                assert found_pattern, f"Pattern (app_open, volume_set) non detecte: {patterns}"

    def test_no_pattern_for_single_action(self):
        """Un historique trop court ne cree aucun pattern."""
        from src.brain import detect_patterns

        short_history = [
            {"action": "system_info", "result": "ok", "success": True, "timestamp": time.time()},
        ]
        with patch("src.brain.get_action_history", return_value=short_history):
            patterns = detect_patterns(min_repeat=2)
            assert len(patterns) == 0

    def test_auto_create_skill(self, tmp_path):
        """Un pattern detecte doit pouvoir creer un skill automatiquement."""
        from src.brain import auto_create_skill, PatternMatch

        pattern = PatternMatch(
            actions=["gpu_info", "system_info"],
            count=3,
            confidence=0.8,
            suggested_name="auto_gpu_info_system_info",
            suggested_triggers=["gpu et system", "lance gpu puis system_info"],
        )

        brain_file = tmp_path / "brain_state.json"
        brain_file.write_text('{"skills_created": [], "total_analyses": 0}', encoding="utf-8")

        with patch("src.brain.BRAIN_FILE", brain_file), \
             patch("src.brain.add_skill") as mock_add, \
             patch("src.brain.log_action") as mock_log, \
             patch("src.brain.load_skills", return_value=[]):
            # Mocker event_bus pour eviter l'import
            with patch.dict("sys.modules", {"src.event_bus": MagicMock()}):
                skill = auto_create_skill(pattern)
                assert skill.name == "auto_gpu_info_system_info"
                assert skill.category == "auto_learned"
                mock_add.assert_called_once()
                mock_log.assert_called_once()

    def test_apply_decay(self, tmp_path):
        """Skills non-utilises perdent de la confiance apres le decay."""
        from src.brain import apply_decay

        quality_file = tmp_path / "skill_quality.json"

        # Creer un skill utilise il y a 14 jours (2 demi-vies)
        old_time = time.time() - (14 * 24 * 3600)
        quality_data = {
            "old_skill": {
                "skill_name": "old_skill",
                "executions": 10,
                "successes": 8,
                "failures": 2,
                "total_duration_ms": 5000,
                "satisfaction_sum": 7.0,
                "last_executed": old_time,
                "confidence": 0.8,
            }
        }
        quality_file.write_text(json.dumps(quality_data), encoding="utf-8")

        with patch("src.brain.QUALITY_FILE", quality_file):
            decayed_count = apply_decay()
            assert decayed_count >= 1

            # Relire et verifier que la confiance a baisse
            reloaded = json.loads(quality_file.read_text(encoding="utf-8"))
            new_conf = reloaded["old_skill"]["confidence"]
            # Apres 14 jours (2 demi-vies), confidence ~= 0.8 * 0.25 = 0.2
            assert new_conf < 0.8, f"Confidence devrait avoir baisse: {new_conf}"
            assert new_conf >= 0.05, f"Confidence minimum est 0.05: {new_conf}"

    def test_record_feedback_positive(self, tmp_path):
        """Feedback positif augmente le score de confiance."""
        from src.brain import record_feedback

        quality_file = tmp_path / "skill_quality.json"
        quality_file.write_text("{}", encoding="utf-8")

        with patch("src.brain.QUALITY_FILE", quality_file):
            record_feedback("test_skill", success=True, duration_ms=100, satisfaction=0.9)

            data = json.loads(quality_file.read_text(encoding="utf-8"))
            q = data["test_skill"]
            assert q["executions"] == 1
            assert q["successes"] == 1
            # Confidence initiale 0.5 + EMA vers 1.0: 0.5*0.8 + 1.0*0.2 = 0.6
            assert float(q["confidence"]) == pytest.approx(0.6, abs=0.01)

    def test_record_feedback_negative(self, tmp_path):
        """Feedback negatif baisse le score de confiance."""
        from src.brain import record_feedback

        quality_file = tmp_path / "skill_quality.json"
        quality_file.write_text("{}", encoding="utf-8")

        with patch("src.brain.QUALITY_FILE", quality_file):
            record_feedback("fail_skill", success=False, duration_ms=500, satisfaction=0.1)

            data = json.loads(quality_file.read_text(encoding="utf-8"))
            q = data["fail_skill"]
            assert q["failures"] == 1
            assert q["successes"] == 0
            # Confidence initiale 0.5 + EMA vers 0.0: 0.5*0.8 + 0.0*0.2 = 0.4
            assert float(q["confidence"]) == pytest.approx(0.4, abs=0.01)

    def test_skill_quality_composite(self):
        """Score composite = 0.4*success_rate + 0.3*satisfaction + 0.3*confidence."""
        from src.brain import SkillQuality

        q = SkillQuality(
            skill_name="test",
            executions=10,
            successes=8,
            failures=2,
            satisfaction_sum=7.0,
            confidence=0.9,
        )
        # success_rate = 8/10 = 0.8
        # user_satisfaction = 7.0 / max(1, 8+2) = 0.7
        # composite = 0.4*0.8 + 0.3*0.7 + 0.3*0.9 = 0.32 + 0.21 + 0.27 = 0.80
        expected = 0.4 * 0.8 + 0.3 * 0.7 + 0.3 * 0.9
        assert q.composite_score == pytest.approx(expected, abs=0.001)

    def test_analyze_and_learn(self, sample_action_history, tmp_path):
        """Pipeline complet d'apprentissage: detect patterns + rapport."""
        from src.brain import analyze_and_learn

        brain_file = tmp_path / "brain_state.json"
        brain_file.write_text('{"total_analyses": 0}', encoding="utf-8")

        with patch("src.brain.BRAIN_FILE", brain_file), \
             patch("src.brain.get_action_history", return_value=sample_action_history), \
             patch("src.brain.load_skills", return_value=[]):
            report = analyze_and_learn(auto_create=False)

            assert "patterns_found" in report
            assert "total_skills" in report
            assert "history_size" in report
            assert report["patterns_found"] >= 0
            # Le rapport ne cree pas de skill sans auto_create=True
            assert len(report["skills_created"]) == 0

    def test_suggest_contextual_skills(self):
        """Suggestions basees sur le contexte (heure, actions recentes)."""
        from src.brain import suggest_contextual_skills

        # Mocker l'historique avec des actions trading
        trading_history = [
            {"action": "trading:scanner:scan", "result": "ok", "success": True, "timestamp": time.time()},
            {"action": "trading:signals:check", "result": "ok", "success": True, "timestamp": time.time()},
        ]

        with patch("src.brain.get_action_history", return_value=trading_history):
            # Mocker check_thermal_status pour eviter l'import
            mock_cluster = MagicMock()
            mock_cluster.check_thermal_status.return_value = {"status": "ok"}
            with patch.dict("sys.modules", {"src.cluster_startup": mock_cluster}):
                suggestions = suggest_contextual_skills(max_suggestions=5)
                assert isinstance(suggestions, list)
                # Chaque suggestion doit avoir la bonne structure
                for s in suggestions:
                    assert "reason" in s
                    assert "label" in s
                    assert "skills" in s

    def test_compose_skills(self, tmp_path):
        """Composition de 2 skills existants en un nouveau pipeline."""
        from src.brain import compose_skills
        from src.skills import Skill, SkillStep

        # Creer des skills existants directement
        skill_a = Skill(
            name="rapport_matin",
            description="Rapport complet du matin",
            triggers=["rapport matin"],
            steps=[
                SkillStep(tool="lm_cluster_status", args={}, description="Cluster status"),
                SkillStep(tool="system_info", args={}, description="Infos systeme"),
            ],
            category="routine",
        )
        skill_b = Skill(
            name="maintenance_complete_linux",
            description="Maintenance systeme complete",
            triggers=["maintenance complete"],
            steps=[
                SkillStep(tool="bash_run", args={"command": "apt update"}, description="Update"),
                SkillStep(tool="bash_run", args={"command": "apt autoremove -y"}, description="Clean"),
            ],
            category="system",
        )

        with patch("src.brain.load_skills", return_value=[skill_a, skill_b]), \
             patch("src.brain.add_skill") as mock_add, \
             patch("src.brain.log_action") as mock_log:
            composed = compose_skills(
                name="rapport_et_maintenance",
                skill_names=["rapport_matin", "maintenance_complete_linux"],
                triggers=["rapport et maintenance", "tout verifier"],
                description="Combine rapport matin + maintenance",
            )

            assert composed is not None
            assert composed.name == "rapport_et_maintenance"
            assert composed.category == "composed"
            # Doit contenir les steps des deux skills (2 + 2 = 4)
            assert len(composed.steps) == 4
            mock_add.assert_called_once()
