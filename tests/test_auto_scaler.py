"""Tests for src/auto_scaler.py — Dynamic cluster scaling.

Covers: ScaleAction dataclass, node stats from DB, scale decisions,
auto-heal, model check logic.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.auto_scaler import AutoScaler, ScaleAction


def _create_dispatch_db(db_path: str, rows: list[dict] | None = None):
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
    if rows:
        for r in rows:
            db.execute(
                "INSERT INTO agent_dispatch_log (node, success, latency_ms) VALUES (?, ?, ?)",
                (r.get("node", "M1"), r.get("success", 1), r.get("latency_ms", 500)),
            )
    db.commit()
    db.close()


# ===========================================================================
# Dataclass
# ===========================================================================

class TestScaleAction:
    def test_basic_creation(self):
        sa = ScaleAction(action="load_model", target="M1", reason="no model", params={"model": "qwen3-8b"})
        assert sa.action == "load_model"
        assert sa.target == "M1"
        assert sa.params["model"] == "qwen3-8b"


# ===========================================================================
# Node stats from DB
# ===========================================================================

class TestNodeStats:
    def test_empty_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_dispatch_db(db_path)
        scaler = AutoScaler(db_path=db_path)
        stats = scaler._get_node_stats()
        assert stats == {}

    def test_stats_with_data(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        rows = [
            {"node": "M1", "success": 1, "latency_ms": 500},
            {"node": "M1", "success": 1, "latency_ms": 700},
            {"node": "M1", "success": 0, "latency_ms": 3000},
            {"node": "OL1", "success": 1, "latency_ms": 200},
        ]
        _create_dispatch_db(db_path, rows)
        scaler = AutoScaler(db_path=db_path)
        stats = scaler._get_node_stats()
        assert "M1" in stats
        assert "OL1" in stats
        assert stats["M1"]["total"] == 3
        assert stats["OL1"]["total"] == 1

    def test_stats_db_error(self):
        scaler = AutoScaler(db_path="/nonexistent/path.db")
        stats = scaler._get_node_stats()
        assert stats == {}


# ===========================================================================
# Scale decisions
# ===========================================================================

class TestScaleDecisions:
    @pytest.mark.asyncio
    async def test_high_latency_action(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        rows = [{"node": "M3", "success": 1, "latency_ms": 40000} for _ in range(15)]
        _create_dispatch_db(db_path, rows)
        scaler = AutoScaler(db_path=db_path)

        # Mock httpx calls
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.auto_scaler.httpx.AsyncClient", return_value=mock_client):
            actions = await scaler.scale()

        reduce = [a for a in actions if a.get("action") == "reduce_load"]
        assert len(reduce) >= 1
        assert "M3" in reduce[0]["target"]

    @pytest.mark.asyncio
    async def test_low_success_action(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        rows = [{"node": "M2", "success": 0, "latency_ms": 1000} for _ in range(15)]
        _create_dispatch_db(db_path, rows)
        scaler = AutoScaler(db_path=db_path)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.auto_scaler.httpx.AsyncClient", return_value=mock_client):
            actions = await scaler.scale()

        shift = [a for a in actions if a.get("action") == "shift_traffic"]
        assert len(shift) >= 1

    @pytest.mark.asyncio
    async def test_m1_offline_alert(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_dispatch_db(db_path)
        scaler = AutoScaler(db_path=db_path)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("src.auto_scaler.httpx.AsyncClient", return_value=mock_client):
            actions = await scaler.scale()

        alerts = [a for a in actions if a.get("action") == "alert"]
        assert len(alerts) >= 1

    @pytest.mark.asyncio
    async def test_no_model_loaded(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_dispatch_db(db_path)
        scaler = AutoScaler(db_path=db_path)

        call_count = 0
        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if "1234" in url:
                resp.json.return_value = {"data": []}
            else:
                resp.json.return_value = {"models": [{"name": "qwen3:1.7b"}]}
            resp.status_code = 200
            return resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = mock_get

        with patch("src.auto_scaler.httpx.AsyncClient", return_value=mock_client):
            actions = await scaler.scale()

        load = [a for a in actions if a.get("action") == "load_model"]
        assert len(load) >= 1

    @pytest.mark.asyncio
    async def test_too_many_models_loaded(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_dispatch_db(db_path)
        scaler = AutoScaler(db_path=db_path)

        async def mock_get(url, **kwargs):
            resp = MagicMock()
            if "1234" in url:
                resp.json.return_value = {"data": [
                    {"key": "m1", "loaded_instances": 1},
                    {"key": "m2", "loaded_instances": 1},
                    {"key": "m3", "loaded_instances": 1},
                ]}
            else:
                resp.json.return_value = {"models": []}
            resp.status_code = 200
            return resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = mock_get

        with patch("src.auto_scaler.httpx.AsyncClient", return_value=mock_client):
            actions = await scaler.scale()

        unload = [a for a in actions if a.get("action") == "unload_excess"]
        assert len(unload) >= 1

    @pytest.mark.asyncio
    async def test_cluster_alert_low_overall(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        rows = [{"node": "M1", "success": 0, "latency_ms": 500} for _ in range(25)]
        _create_dispatch_db(db_path, rows)
        scaler = AutoScaler(db_path=db_path)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"key": "qwen3-8b", "loaded_instances": 1}]}
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.auto_scaler.httpx.AsyncClient", return_value=mock_client):
            actions = await scaler.scale()

        cluster = [a for a in actions if a.get("action") == "cluster_alert"]
        assert len(cluster) >= 1

    @pytest.mark.asyncio
    async def test_rebalance_m1_overloaded(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        rows = [{"node": "M1", "success": 1, "latency_ms": 25000} for _ in range(55)]
        rows += [{"node": "OL1", "success": 1, "latency_ms": 300} for _ in range(10)]
        _create_dispatch_db(db_path, rows)
        scaler = AutoScaler(db_path=db_path)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"key": "qwen3-8b", "loaded_instances": 1}]}
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.auto_scaler.httpx.AsyncClient", return_value=mock_client):
            actions = await scaler.scale()

        rebalance = [a for a in actions if a.get("action") == "rebalance"]
        assert len(rebalance) >= 1


# ===========================================================================
# Auto-heal
# ===========================================================================

class TestAutoHeal:
    @pytest.mark.asyncio
    async def test_auto_heal_loads_model(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_dispatch_db(db_path)
        scaler = AutoScaler(db_path=db_path)

        async def mock_get(url, **kwargs):
            resp = MagicMock()
            if "1234" in url:
                resp.json.return_value = {"data": []}
            else:
                resp.json.return_value = {"models": []}
            resp.status_code = 200
            return resp

        async def mock_post(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            return resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = mock_get
        mock_client.post = mock_post

        with patch("src.auto_scaler.httpx.AsyncClient", return_value=mock_client):
            healed = await scaler.auto_heal()

        loaded = [h for h in healed if h.get("action") == "loaded"]
        assert len(loaded) >= 1

    @pytest.mark.asyncio
    async def test_auto_heal_handles_failure(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_dispatch_db(db_path)
        scaler = AutoScaler(db_path=db_path)

        async def mock_get(url, **kwargs):
            resp = MagicMock()
            if "1234" in url:
                resp.json.return_value = {"data": []}
            else:
                resp.json.return_value = {"models": []}
            resp.status_code = 200
            return resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = mock_get
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))

        with patch("src.auto_scaler.httpx.AsyncClient", return_value=mock_client):
            healed = await scaler.auto_heal()

        failed = [h for h in healed if h.get("action") == "load_failed"]
        assert len(failed) >= 1


# ===========================================================================
# Thresholds
# ===========================================================================

class TestThresholds:
    def test_default_thresholds(self):
        scaler = AutoScaler.__new__(AutoScaler)
        assert AutoScaler.HIGH_LATENCY_MS == 30000
        assert AutoScaler.LOW_SUCCESS_RATE == 0.7
        assert AutoScaler.MIN_DISPATCHES == 10

    def test_node_max_concurrent(self):
        assert AutoScaler.NODE_MAX_CONCURRENT["M1"] == 6
        assert AutoScaler.NODE_MAX_CONCURRENT["OL1"] == 3
