"""Tests for src/agent_auto_scaler.py — Agent auto-scaler with policies.

Covers: LoadMetrics, ScaleAction, ScalePolicy dataclasses, evaluate logic,
execute_actions, capacity report, scaling history, cooldown, idle detection.
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

from src.agent_auto_scaler import AutoScaler, LoadMetrics, ScaleAction, ScalePolicy, get_scaler


def _create_test_db(db_path: str, dispatch_rows: list[dict] | None = None):
    db = sqlite3.connect(db_path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_dispatch_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classified_type TEXT, node TEXT, request_text TEXT,
            success INTEGER DEFAULT 1, quality_score REAL,
            latency_ms REAL, strategy TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS auto_scale_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT, target_node TEXT,
            description TEXT, priority INTEGER,
            executed INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    if dispatch_rows:
        for r in dispatch_rows:
            db.execute(
                "INSERT INTO agent_dispatch_log (node, success, latency_ms, timestamp) VALUES (?, ?, ?, datetime('now'))",
                (r.get("node", "M1"), r.get("success", 1), r.get("latency_ms", 500)),
            )
    db.commit()
    db.close()


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_load_metrics_defaults(self):
        m = LoadMetrics(node="M1")
        assert m.active_requests == 0
        assert m.avg_latency_ms == 0
        assert m.queue_depth == 0
        assert m.model_loaded == ""

    def test_scale_action(self):
        sa = ScaleAction(
            action_type="redistribute", target_node="M1",
            description="test", priority=1,
        )
        assert sa.auto_executable is False
        assert sa.params == {}

    def test_scale_policy_defaults(self):
        p = ScalePolicy()
        assert p.latency_warning_ms == 5000
        assert p.latency_critical_ms == 15000
        assert p.error_rate_warning == 0.2
        assert p.cooldown_s == 300

    def test_scale_policy_custom(self):
        p = ScalePolicy(latency_critical_ms=30000, cooldown_s=60)
        assert p.latency_critical_ms == 30000
        assert p.cooldown_s == 60


# ===========================================================================
# Table creation
# ===========================================================================

class TestTableCreation:
    def test_table_created(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
        db = sqlite3.connect(db_path)
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "auto_scale_log" in tables
        db.close()


# ===========================================================================
# Load metrics
# ===========================================================================

class TestLoadMetrics:
    def test_metrics_empty_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            metrics = scaler.get_load_metrics()
        assert metrics == {}

    def test_metrics_with_data(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        rows = [
            {"node": "M1", "success": 1, "latency_ms": 500},
            {"node": "M1", "success": 1, "latency_ms": 700},
            {"node": "M1", "success": 0, "latency_ms": 3000},
            {"node": "OL1", "success": 1, "latency_ms": 200},
        ]
        _create_test_db(db_path, rows)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            metrics = scaler.get_load_metrics()
        assert "M1" in metrics
        m1 = metrics["M1"]
        assert m1.avg_latency_ms > 0
        assert m1.error_rate == pytest.approx(1/3, abs=0.01)


# ===========================================================================
# Evaluate
# ===========================================================================

class TestEvaluate:
    def test_evaluate_empty(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            actions = scaler.evaluate()
        assert isinstance(actions, list)

    def test_critical_latency(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        rows = [{"node": "M3", "success": 1, "latency_ms": 20000} for _ in range(15)]
        _create_test_db(db_path, rows)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            actions = scaler.evaluate()
        redistribute = [a for a in actions if a.action_type == "redistribute" and a.target_node == "M3"]
        assert len(redistribute) >= 1

    def test_high_error_rate(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        rows = [{"node": "M2", "success": 0, "latency_ms": 1000} for _ in range(15)]
        _create_test_db(db_path, rows)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            actions = scaler.evaluate()
        scale_down = [a for a in actions if a.action_type == "scale_down"]
        assert len(scale_down) >= 1

    def test_actions_sorted_by_priority(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        rows = [{"node": "M1", "success": 0, "latency_ms": 20000} for _ in range(20)]
        _create_test_db(db_path, rows)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            actions = scaler.evaluate()
        if len(actions) >= 2:
            priorities = [a.priority for a in actions]
            assert priorities == sorted(priorities)

    def test_cooldown_skips_node(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        rows = [{"node": "M3", "success": 0, "latency_ms": 20000} for _ in range(15)]
        _create_test_db(db_path, rows)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            scaler._last_actions["M3"] = time.time()  # Just now
            actions = scaler.evaluate()
        m3_actions = [a for a in actions if a.target_node == "M3"]
        assert len(m3_actions) == 0

    def test_idle_detection(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""
            CREATE TABLE IF NOT EXISTS agent_dispatch_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                classified_type TEXT, node TEXT,
                success INTEGER DEFAULT 1, quality_score REAL,
                latency_ms REAL, strategy TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS auto_scale_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT, target_node TEXT,
                description TEXT, priority INTEGER,
                executed INTEGER DEFAULT 0,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insert M2 data with timestamp between 1h and 2h ago (in 2h window but not 1h)
        db.execute(
            "INSERT INTO agent_dispatch_log (node, success, latency_ms, timestamp) VALUES (?, ?, ?, datetime('now', '-90 minutes'))",
            ("M2", 1, 500),
        )
        db.commit()
        db.close()
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            actions = scaler.evaluate()
        idle = [a for a in actions if a.action_type == "scale_down" and "idle" in a.params.get("reason", "")]
        assert len(idle) >= 1


# ===========================================================================
# Execute actions
# ===========================================================================

class TestExecuteActions:
    @pytest.mark.asyncio
    async def test_execute_low_priority_suggested(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            action = ScaleAction("swap_model", "M1", "test", priority=3)
            results = await scaler.execute_actions([action])
        assert results[0]["status"] == "suggested"

    @pytest.mark.asyncio
    async def test_execute_critical_redistribute(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        mock_router = MagicMock()
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            action = ScaleAction("redistribute", "M3", "test", priority=1)
            with patch("src.agent_auto_scaler.get_scaler"):
                with patch.dict("sys.modules", {"src.adaptive_router": MagicMock()}):
                    results = await scaler.execute_actions([action])
        assert results[0]["action"] == "redistribute"

    @pytest.mark.asyncio
    async def test_execute_records_timestamp(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            action = ScaleAction("redistribute", "M3", "test", priority=1)
            with patch.dict("sys.modules", {"src.adaptive_router": MagicMock()}):
                await scaler.execute_actions([action])
        assert "M3" in scaler._last_actions


# ===========================================================================
# Scaling history
# ===========================================================================

class TestScalingHistory:
    def test_history_empty(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            history = scaler.get_scaling_history()
        assert history == []

    def test_history_with_data(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        db = sqlite3.connect(db_path)
        db.execute("INSERT INTO auto_scale_log (action_type, target_node, description, priority) VALUES (?, ?, ?, ?)",
                   ("redistribute", "M3", "test", 1))
        db.commit()
        db.close()
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            history = scaler.get_scaling_history()
        assert len(history) == 1
        assert history[0]["action_type"] == "redistribute"

    def test_history_limit(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        db = sqlite3.connect(db_path)
        for i in range(10):
            db.execute("INSERT INTO auto_scale_log (action_type, target_node, description, priority) VALUES (?, ?, ?, ?)",
                       ("test", "M1", f"action {i}", 3))
        db.commit()
        db.close()
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            history = scaler.get_scaling_history(limit=5)
        assert len(history) == 5


# ===========================================================================
# Capacity report
# ===========================================================================

class TestCapacityReport:
    def test_report_structure(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        with patch("src.agent_auto_scaler.DB_PATH", db_path):
            scaler = AutoScaler()
            report = scaler.get_capacity_report()
        assert "cluster" in report
        assert "nodes" in report
        assert "recommendations" in report
        assert report["cluster"]["total_gpu_gb"] > 0
        assert report["cluster"]["total_nodes"] == 4

    def test_node_capabilities(self):
        caps = AutoScaler.NODE_CAPABILITIES
        assert "M1" in caps
        assert caps["M1"]["gpu_gb"] == 46
        assert "qwen3-8b" in caps["M1"]["models"]

    def test_model_tiers(self):
        tiers = AutoScaler.MODEL_TIERS
        assert "fast" in tiers
        assert "deep" in tiers
        assert "qwen3:1.7b" in tiers["fast"]


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_get_scaler(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        import src.agent_auto_scaler as mod
        old = mod._scaler
        try:
            mod._scaler = None
            with patch("src.agent_auto_scaler.DB_PATH", db_path):
                s = get_scaler()
            assert isinstance(s, AutoScaler)
        finally:
            mod._scaler = old
