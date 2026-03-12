"""Tests for src/cluster_intelligence.py — Unified cluster intelligence.

Covers: IntelAction dataclass, health score calculation, full report,
priority actions, predictions, summary, quick status, caching.
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cluster_intelligence import ClusterIntelligence, IntelAction, get_intelligence


def _create_intel_db(db_path: str, dispatch_rows: list[dict] | None = None):
    db = sqlite3.connect(db_path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_dispatch_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classified_type TEXT, node TEXT,
            success INTEGER DEFAULT 1, quality_score REAL DEFAULT 0.5,
            latency_ms REAL DEFAULT 500, strategy TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_patterns (
            pattern_id TEXT, pattern_type TEXT,
            agent_id TEXT, strategy TEXT, priority INTEGER DEFAULT 3,
            model_primary TEXT, model_fallbacks TEXT
        )
    """)
    if dispatch_rows:
        for r in dispatch_rows:
            db.execute(
                "INSERT INTO agent_dispatch_log (classified_type, node, success, quality_score, latency_ms, timestamp) VALUES (?, ?, ?, ?, ?, datetime('now'))",
                (r.get("type", "code"), r.get("node", "M1"),
                 r.get("success", 1), r.get("quality", 0.5),
                 r.get("latency", 500)),
            )
    db.commit()
    db.close()


# ===========================================================================
# Dataclass
# ===========================================================================

class TestIntelAction:
    def test_basic_creation(self):
        a = IntelAction(
            priority=1, category="health", action="restart",
            description="Node down", source="scaler",
            confidence=0.9, impact="Restore availability",
        )
        assert a.priority == 1
        assert a.category == "health"
        assert a.confidence == 0.9


# ===========================================================================
# Health score calculation
# ===========================================================================

class TestHealthScore:
    def test_perfect_score(self):
        intel = ClusterIntelligence()
        subsystems = {
            "router": {"available": True, "open_circuits": 0},
            "feedback": {"available": True, "avg_quality": 0.9, "degrading_patterns": []},
            "scaler": {"available": True, "critical_actions": 0, "overloaded_nodes": []},
            "lifecycle": {"available": True, "degraded": 0},
            "dispatch_stats": {"available": True, "last_hour_success_rate": 0.95},
        }
        score = intel._calculate_health_score(subsystems)
        assert score == 100

    def test_open_circuits_reduce_score(self):
        intel = ClusterIntelligence()
        subsystems = {
            "router": {"available": True, "open_circuits": 2},
            "feedback": {"available": False},
            "scaler": {"available": False},
            "lifecycle": {"available": False},
            "dispatch_stats": {"available": False},
        }
        score = intel._calculate_health_score(subsystems)
        assert score == 80  # -10 per open circuit

    def test_low_quality_reduces_score(self):
        intel = ClusterIntelligence()
        subsystems = {
            "router": {"available": False},
            "feedback": {"available": True, "avg_quality": 0.2, "degrading_patterns": []},
            "scaler": {"available": False},
            "lifecycle": {"available": False},
            "dispatch_stats": {"available": False},
        }
        score = intel._calculate_health_score(subsystems)
        assert score == 75  # -25 for very low quality

    def test_degrading_patterns_reduce_score(self):
        intel = ClusterIntelligence()
        subsystems = {
            "router": {"available": False},
            "feedback": {"available": True, "avg_quality": 0.8, "degrading_patterns": ["code", "math", "question"]},
            "scaler": {"available": False},
            "lifecycle": {"available": False},
            "dispatch_stats": {"available": False},
        }
        score = intel._calculate_health_score(subsystems)
        assert score == 91  # -9 for 3 degrading patterns (3*3)

    def test_critical_scaler_actions_reduce(self):
        intel = ClusterIntelligence()
        subsystems = {
            "router": {"available": False},
            "feedback": {"available": False},
            "scaler": {"available": True, "critical_actions": 3, "overloaded_nodes": ["M1"]},
            "lifecycle": {"available": False},
            "dispatch_stats": {"available": False},
        }
        score = intel._calculate_health_score(subsystems)
        # -21 for 3 critical (3*7) + -5 for 1 overloaded = -26, capped at -20+(-10)=-30
        assert score <= 80

    def test_low_success_rate_reduces(self):
        intel = ClusterIntelligence()
        subsystems = {
            "router": {"available": False},
            "feedback": {"available": False},
            "scaler": {"available": False},
            "lifecycle": {"available": False},
            "dispatch_stats": {"available": True, "last_hour_success_rate": 0.4},
        }
        score = intel._calculate_health_score(subsystems)
        assert score == 80  # -20 for <0.5

    def test_score_clamped_0_100(self):
        intel = ClusterIntelligence()
        # Everything bad
        subsystems = {
            "router": {"available": True, "open_circuits": 5},
            "feedback": {"available": True, "avg_quality": 0.1, "degrading_patterns": ["a", "b", "c", "d", "e"]},
            "scaler": {"available": True, "critical_actions": 5, "overloaded_nodes": ["M1", "M2"]},
            "lifecycle": {"available": True, "degraded": 10},
            "dispatch_stats": {"available": True, "last_hour_success_rate": 0.3},
        }
        score = intel._calculate_health_score(subsystems)
        assert 0 <= score <= 100

    def test_unavailable_subsystems_no_penalty(self):
        intel = ClusterIntelligence()
        subsystems = {
            "router": {"available": False},
            "feedback": {"available": False},
            "scaler": {"available": False},
            "lifecycle": {"available": False},
            "dispatch_stats": {"available": False},
        }
        score = intel._calculate_health_score(subsystems)
        assert score == 100


# ===========================================================================
# Summary generation
# ===========================================================================

class TestSummary:
    def test_grade_a(self):
        intel = ClusterIntelligence()
        report = {"health_score": 95, "subsystems": {}, "actions": []}
        summary = intel._generate_summary(report)
        assert "Grade A" in summary
        assert "95/100" in summary

    def test_grade_f(self):
        intel = ClusterIntelligence()
        report = {"health_score": 20, "subsystems": {}, "actions": []}
        summary = intel._generate_summary(report)
        assert "Grade F" in summary

    def test_summary_includes_dispatches(self):
        intel = ClusterIntelligence()
        report = {
            "health_score": 80,
            "subsystems": {"dispatch_stats": {"available": True, "total_dispatches": 500, "last_hour": 42}},
            "actions": [],
        }
        summary = intel._generate_summary(report)
        assert "500" in summary
        assert "42" in summary

    def test_summary_includes_actions(self):
        intel = ClusterIntelligence()
        report = {"health_score": 70, "subsystems": {}, "actions": [{"a": 1}, {"b": 2}]}
        summary = intel._generate_summary(report)
        assert "2 actions" in summary


# ===========================================================================
# Predictions
# ===========================================================================

class TestPredictions:
    def test_capacity_prediction(self):
        intel = ClusterIntelligence()
        subsystems = {
            "dispatch_stats": {"available": True, "last_hour": 150},
            "feedback": {"available": False},
        }
        preds = intel._generate_predictions(subsystems)
        capacity = [p for p in preds if p["type"] == "capacity"]
        assert len(capacity) >= 1

    def test_degrading_prediction(self):
        intel = ClusterIntelligence()
        subsystems = {
            "dispatch_stats": {"available": False},
            "feedback": {"available": True, "degrading_patterns": ["code"], "improving_patterns": []},
        }
        preds = intel._generate_predictions(subsystems)
        quality = [p for p in preds if p["type"] == "quality"]
        assert len(quality) >= 1

    def test_improving_prediction(self):
        intel = ClusterIntelligence()
        subsystems = {
            "dispatch_stats": {"available": False},
            "feedback": {"available": True, "degrading_patterns": [], "improving_patterns": ["math", "code"]},
        }
        preds = intel._generate_predictions(subsystems)
        quality = [p for p in preds if "improving" in p.get("prediction", "")]
        assert len(quality) >= 1

    def test_no_predictions_low_load(self):
        intel = ClusterIntelligence()
        subsystems = {
            "dispatch_stats": {"available": True, "last_hour": 5},
            "feedback": {"available": True, "degrading_patterns": [], "improving_patterns": []},
        }
        preds = intel._generate_predictions(subsystems)
        assert len(preds) == 0


# ===========================================================================
# Quick status
# ===========================================================================

class TestQuickStatus:
    def test_quick_status_healthy(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_intel_db(db_path, [
            {"type": "code", "success": 1} for _ in range(10)
        ])
        with patch("src.cluster_intelligence.DB_PATH", db_path):
            intel = ClusterIntelligence()
            status = intel.quick_status()
        assert status["status"] == "healthy"
        assert status["total_dispatches"] == 10

    def test_quick_status_degraded(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_intel_db(db_path, [
            {"type": "code", "success": 0} for _ in range(10)
        ])
        with patch("src.cluster_intelligence.DB_PATH", db_path):
            intel = ClusterIntelligence()
            status = intel.quick_status()
        assert status["status"] == "degraded"

    def test_quick_status_db_error(self):
        with patch("src.cluster_intelligence.DB_PATH", "/nonexistent.db"):
            intel = ClusterIntelligence()
            status = intel.quick_status()
        assert status["status"] == "unknown"


# ===========================================================================
# Full report with mocked subsystems
# ===========================================================================

class TestFullReport:
    def test_report_structure(self):
        intel = ClusterIntelligence()
        # Mock all subsystem collectors
        with patch.object(intel, "_collect_router", return_value={"available": False}), \
             patch.object(intel, "_collect_feedback", return_value={"available": False}), \
             patch.object(intel, "_collect_scaler", return_value={"available": False}), \
             patch.object(intel, "_collect_quality_gate", return_value={"available": False}), \
             patch.object(intel, "_collect_lifecycle", return_value={"available": False}), \
             patch.object(intel, "_collect_dispatch_stats", return_value={"available": False}), \
             patch.object(intel, "priority_actions", return_value=[]):
            report = intel.full_report()

        assert "timestamp" in report
        assert "health_score" in report
        assert "subsystems" in report
        assert "actions" in report
        assert "predictions" in report
        assert "summary" in report
        assert report["health_score"] == 100  # No available subsystems = no penalty

    def test_report_cached(self):
        intel = ClusterIntelligence()
        with patch.object(intel, "_collect_router", return_value={"available": False}), \
             patch.object(intel, "_collect_feedback", return_value={"available": False}), \
             patch.object(intel, "_collect_scaler", return_value={"available": False}), \
             patch.object(intel, "_collect_quality_gate", return_value={"available": False}), \
             patch.object(intel, "_collect_lifecycle", return_value={"available": False}), \
             patch.object(intel, "_collect_dispatch_stats", return_value={"available": False}), \
             patch.object(intel, "priority_actions", return_value=[]):
            report1 = intel.full_report()
            report2 = intel.full_report()
        # Should be cached (same object)
        assert report1 is report2

    def test_report_force_refresh(self):
        intel = ClusterIntelligence()
        with patch.object(intel, "_collect_router", return_value={"available": False}), \
             patch.object(intel, "_collect_feedback", return_value={"available": False}), \
             patch.object(intel, "_collect_scaler", return_value={"available": False}), \
             patch.object(intel, "_collect_quality_gate", return_value={"available": False}), \
             patch.object(intel, "_collect_lifecycle", return_value={"available": False}), \
             patch.object(intel, "_collect_dispatch_stats", return_value={"available": False}), \
             patch.object(intel, "priority_actions", return_value=[]):
            report1 = intel.full_report()
            report2 = intel.full_report(force_refresh=True)
        # Should be different objects (force_refresh)
        assert report1 is not report2


# ===========================================================================
# Collect subsystems (error paths)
# ===========================================================================

class TestCollectSubsystems:
    def test_collect_router_error(self):
        intel = ClusterIntelligence()
        with patch.dict("sys.modules", {"src.adaptive_router": None}):
            result = intel._collect_router()
        assert result["available"] is False

    def test_collect_feedback_error(self):
        intel = ClusterIntelligence()
        with patch.dict("sys.modules", {"src.agent_feedback_loop": None}):
            result = intel._collect_feedback()
        assert result["available"] is False

    def test_collect_scaler_error(self):
        intel = ClusterIntelligence()
        with patch.dict("sys.modules", {"src.agent_auto_scaler": None}):
            result = intel._collect_scaler()
        assert result["available"] is False

    def test_collect_quality_gate_error(self):
        intel = ClusterIntelligence()
        with patch.dict("sys.modules", {"src.quality_gate": None}):
            result = intel._collect_quality_gate()
        assert result["available"] is False

    def test_collect_lifecycle_error(self):
        intel = ClusterIntelligence()
        with patch.dict("sys.modules", {"src.pattern_lifecycle": None}):
            result = intel._collect_lifecycle()
        assert result["available"] is False

    def test_collect_dispatch_stats(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_intel_db(db_path, [
            {"type": "code", "node": "M1", "success": 1, "quality": 0.9, "latency": 500},
            {"type": "code", "node": "M1", "success": 1, "quality": 0.8, "latency": 700},
        ])
        with patch("src.cluster_intelligence.DB_PATH", db_path):
            intel = ClusterIntelligence()
            result = intel._collect_dispatch_stats()
        assert result["available"] is True
        assert result["total_dispatches"] == 2


# ===========================================================================
# Priority actions
# ===========================================================================

class TestPriorityActions:
    def test_actions_from_mocked_subsystems(self):
        intel = ClusterIntelligence()
        # Mock all subsystem imports to raise
        with patch.dict("sys.modules", {
            "src.agent_auto_scaler": None,
            "src.agent_feedback_loop": None,
            "src.pattern_lifecycle": None,
        }):
            actions = intel.priority_actions()
        assert isinstance(actions, list)

    def test_actions_sorted_by_priority(self):
        intel = ClusterIntelligence()
        mock_scaler = MagicMock()
        from src.agent_auto_scaler import ScaleAction
        mock_scaler.evaluate.return_value = [
            ScaleAction("redistribute", "M1", "test", 1),
            ScaleAction("swap_model", "OL1", "test", 3),
        ]

        with patch("src.agent_auto_scaler.get_scaler", return_value=mock_scaler), \
             patch.dict("sys.modules", {
                 "src.agent_feedback_loop": None,
                 "src.pattern_lifecycle": None,
             }):
            actions = intel.priority_actions()
        if len(actions) >= 2:
            priorities = [a.priority for a in actions]
            assert priorities == sorted(priorities)


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_get_intelligence(self):
        import src.cluster_intelligence as mod
        old = mod._intelligence
        try:
            mod._intelligence = None
            i = get_intelligence()
            assert isinstance(i, ClusterIntelligence)
        finally:
            mod._intelligence = old
