"""Tests for src/dashboard.py — Dashboard helper functions.

Covers: _fetch_cluster, _fetch_system, _fetch_trading (async helpers).
The Textual TUI widgets are not unit-tested (require full Textual runtime).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dashboard import _fetch_cluster, _fetch_system, _fetch_trading


# ===========================================================================
# _fetch_cluster
# ===========================================================================

class TestFetchCluster:
    @pytest.mark.asyncio
    async def test_returns_list(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"loaded_instances": 1}]}
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        with patch("src.dashboard._get_http", new_callable=AsyncMock, return_value=mock_client):
            result = await _fetch_cluster()
        assert isinstance(result, list)
        assert len(result) > 0
        for node in result:
            assert "name" in node
            assert "online" in node

    @pytest.mark.asyncio
    async def test_offline_node(self):
        import httpx
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with patch("src.dashboard._get_http", new_callable=AsyncMock, return_value=mock_client):
            result = await _fetch_cluster()
        assert isinstance(result, list)
        for node in result:
            assert node["online"] is False

    @pytest.mark.asyncio
    async def test_node_structure(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": []}
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        with patch("src.dashboard._get_http", new_callable=AsyncMock, return_value=mock_client):
            result = await _fetch_cluster()
        for node in result:
            assert "role" in node
            assert "url" in node
            assert "gpus" in node
            assert "vram" in node
            assert "model" in node


# ===========================================================================
# _fetch_system
# ===========================================================================

class TestFetchSystem:
    @pytest.mark.asyncio
    async def test_returns_string(self):
        mock_result = MagicMock()
        mock_result.stdout = "CPU: Intel i7|RAM: 16/32 GB|Uptime: 5j 3h|Disks: C: 67/476GB"
        with patch("subprocess.run", return_value=mock_result):
            result = await _fetch_system()
        assert isinstance(result, str)
        assert "CPU" in result

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 15)):
            result = await _fetch_system()
        assert "Erreur" in result

    @pytest.mark.asyncio
    async def test_os_error(self):
        with patch("subprocess.run", side_effect=OSError("No PS")):
            result = await _fetch_system()
        assert "Erreur" in result


# ===========================================================================
# _fetch_trading
# ===========================================================================

class TestFetchTrading:
    @pytest.mark.asyncio
    async def test_with_positions(self):
        mock_status = {
            "positions": [{"pair": "BTC"}],
            "pending_signals": 3,
            "pnl": "+2.5%",
        }
        with patch("src.dashboard.pipeline_status", create=True) as mock_ps:
            with patch.dict("sys.modules", {"src.trading": MagicMock(pipeline_status=lambda: mock_status)}):
                # Re-import to pick up the mock
                import importlib
                import src.dashboard as dash
                result = await dash._fetch_trading()
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_import_error(self):
        with patch.dict("sys.modules", {"src.trading": None}):
            result = await _fetch_trading()
        assert isinstance(result, str)
        assert "Trading" in result or "trading" in result.lower()

    @pytest.mark.asyncio
    async def test_string_status(self):
        mock_mod = MagicMock()
        mock_mod.pipeline_status.return_value = "Pipeline idle"
        with patch.dict("sys.modules", {"src.trading": mock_mod}):
            result = await _fetch_trading()
        assert isinstance(result, str)
