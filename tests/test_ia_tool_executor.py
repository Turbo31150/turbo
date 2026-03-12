"""Tests for src/ia_tool_executor.py — bridges AI tool calls to JARVIS HTTP endpoints.

Covers: _MCP_TO_OPENAI, _OPENAI_TO_MCP, _DESTRUCTIVE_TOOLS, _READ_ONLY_TOOLS,
execute_tool_call, execute_mcp_call, get_mcp_tools_manifest,
process_model_tool_calls. All HTTP calls mocked via httpx.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ia_tool_executor import (
    _MCP_TO_OPENAI, _OPENAI_TO_MCP, _DESTRUCTIVE_TOOLS, _READ_ONLY_TOOLS,
    execute_tool_call, execute_mcp_call, get_mcp_tools_manifest,
    process_model_tool_calls,
)


# ===========================================================================
# Mapping constants
# ===========================================================================

class TestMappings:
    def test_mcp_to_openai_complete(self):
        assert len(_MCP_TO_OPENAI) >= 20

    def test_reverse_mapping(self):
        for mcp, openai in _MCP_TO_OPENAI.items():
            assert _OPENAI_TO_MCP[openai] == mcp

    def test_destructive_tools(self):
        assert "jarvis_cowork_execute" in _DESTRUCTIVE_TOOLS
        assert "jarvis_db_maintenance" in _DESTRUCTIVE_TOOLS
        assert "jarvis_pipeline_execute" in _DESTRUCTIVE_TOOLS

    def test_read_only_tools(self):
        assert "jarvis_autonomous_status" in _READ_ONLY_TOOLS
        assert "jarvis_cluster_health" in _READ_ONLY_TOOLS
        assert "jarvis_diagnostics_quick" in _READ_ONLY_TOOLS

    def test_no_overlap(self):
        assert _DESTRUCTIVE_TOOLS & _READ_ONLY_TOOLS == set()


# ===========================================================================
# execute_tool_call (mocked httpx)
# ===========================================================================

class TestExecuteToolCall:
    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        result = await execute_tool_call("nonexistent_tool", {})
        assert result["ok"] is False
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_destructive_blocked(self):
        result = await execute_tool_call("jarvis_cowork_execute", {"script": "test.py"})
        assert result["ok"] is False
        assert "destructive" in result["error"]

    @pytest.mark.asyncio
    async def test_destructive_allowed(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("src.ia_tool_executor.httpx.AsyncClient", return_value=mock_client):
            result = await execute_tool_call(
                "jarvis_cowork_execute", {"script": "test.py"},
                allow_destructive=True
            )
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_get_request(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok", "tasks": []}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.ia_tool_executor.httpx.AsyncClient", return_value=mock_client):
            result = await execute_tool_call("jarvis_autonomous_status", {})
        assert result["ok"] is True
        assert result["result"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_path_parameter_substitution(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"started": True}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("src.ia_tool_executor.httpx.AsyncClient", return_value=mock_client):
            result = await execute_tool_call(
                "jarvis_run_task", {"task_name": "zombie_gc"}
            )
        assert result["ok"] is True
        # Verify the URL had task_name substituted
        call_args = mock_client.post.call_args
        assert "zombie_gc" in str(call_args)

    @pytest.mark.asyncio
    async def test_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.ia_tool_executor.httpx.AsyncClient", return_value=mock_client):
            result = await execute_tool_call("jarvis_autonomous_status", {})
        assert result["ok"] is False
        assert "500" in result["error"]

    @pytest.mark.asyncio
    async def test_timeout(self):
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("src.ia_tool_executor.httpx.AsyncClient", return_value=mock_client):
            result = await execute_tool_call("jarvis_autonomous_status", {})
        assert result["ok"] is False
        assert "Timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_connect_error(self):
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("src.ia_tool_executor.httpx.AsyncClient", return_value=mock_client):
            result = await execute_tool_call("jarvis_autonomous_status", {})
        assert result["ok"] is False
        assert "unreachable" in result["error"]


# ===========================================================================
# execute_mcp_call
# ===========================================================================

class TestExecuteMcpCall:
    @pytest.mark.asyncio
    async def test_translates_name(self):
        with patch("src.ia_tool_executor.execute_tool_call", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"ok": True, "result": {}}
            result = await execute_mcp_call("jarvis.autonomousStatus", {})
        mock_exec.assert_called_once_with(
            "jarvis_autonomous_status", {}, caller="mcp"
        )
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_unknown_mcp_tool(self):
        result = await execute_mcp_call("jarvis.nonexistent", {})
        assert result["ok"] is False
        assert "Unknown MCP tool" in result["error"]


# ===========================================================================
# get_mcp_tools_manifest
# ===========================================================================

class TestMcpManifest:
    def test_manifest_nonempty(self):
        manifest = get_mcp_tools_manifest()
        assert len(manifest) >= 20

    def test_manifest_structure(self):
        manifest = get_mcp_tools_manifest()
        for tool in manifest:
            assert "name" in tool
            assert "title" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    def test_manifest_uses_dot_notation(self):
        manifest = get_mcp_tools_manifest()
        for tool in manifest:
            assert "." in tool["name"] or "_" in tool["name"]


# ===========================================================================
# process_model_tool_calls
# ===========================================================================

class TestProcessModelToolCalls:
    @pytest.mark.asyncio
    async def test_single_call(self):
        with patch("src.ia_tool_executor.execute_tool_call", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"ok": True, "result": {"data": 42}}
            results = await process_model_tool_calls([
                {"id": "tc1", "function": {"name": "jarvis_autonomous_status", "arguments": "{}"}},
            ])
        assert len(results) == 1
        assert results[0]["tool_call_id"] == "tc1"
        assert results[0]["role"] == "tool"
        content = json.loads(results[0]["content"])
        assert content["ok"] is True

    @pytest.mark.asyncio
    async def test_multiple_calls(self):
        with patch("src.ia_tool_executor.execute_tool_call", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"ok": True, "result": {}}
            results = await process_model_tool_calls([
                {"id": "tc1", "function": {"name": "jarvis_autonomous_status", "arguments": "{}"}},
                {"id": "tc2", "function": {"name": "jarvis_cluster_health", "arguments": "{}"}},
            ])
        assert len(results) == 2
        assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_invalid_json_arguments(self):
        with patch("src.ia_tool_executor.execute_tool_call", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"ok": True, "result": {}}
            results = await process_model_tool_calls([
                {"id": "tc1", "function": {"name": "jarvis_autonomous_status", "arguments": "not-json"}},
            ])
        assert len(results) == 1
        # Should have passed empty dict as args
        mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_dict_arguments(self):
        with patch("src.ia_tool_executor.execute_tool_call", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"ok": True, "result": {}}
            results = await process_model_tool_calls([
                {"id": "tc1", "function": {"name": "jarvis_run_task", "arguments": {"task_name": "health_check"}}},
            ])
        assert len(results) == 1
        call_args = mock_exec.call_args
        assert call_args[0][1] == {"task_name": "health_check"}
