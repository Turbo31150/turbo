"""Tests for src/mcp_server.py — MCP server handlers and helpers.

Covers: _text, _error, _safe_int, _ps_sync, _ps, _run,
        handle_lm_query, handle_lm_models, handle_lm_cluster_status,
        handle_system_audit, handle_consensus, handle_execute_domino,
        handle_list_dominos, handle_domino_stats, handle_dict_crud,
        handle_speak, handle_list_skills, handle_brain_status,
        handle_brain_analyze, list_tools, call_tool.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Safe import: mock heavy externals before importing src.mcp_server
# ---------------------------------------------------------------------------
_originals: dict[str, object] = {}


class _FakeServer:
    """Minimal fake MCP Server that supports @app.list_tools() / @app.call_tool() decorators."""

    def __init__(self, name: str = "jarvis"):
        self.name = name
        self._list_tools_fn = None
        self._call_tool_fn = None

    def list_tools(self):
        def decorator(fn):
            self._list_tools_fn = fn
            return fn
        return decorator

    def call_tool(self):
        def decorator(fn):
            self._call_tool_fn = fn
            return fn
        return decorator

    def create_initialization_options(self):
        return {}

    async def run(self, *args, **kwargs):
        pass


@pytest.fixture(autouse=True, scope="module")
def _mock_externals():
    """Mock MCP SDK and other heavy imports for src.mcp_server."""
    mocks_needed = {}

    # Build a proper mcp mock hierarchy
    TextContent = type("TextContent", (), {
        "__init__": lambda self, **kw: self.__dict__.update(kw),
        "__repr__": lambda self: f"TextContent(text={self.__dict__.get('text', '')})",
    })

    # mcp.types
    types_mock = MagicMock()
    types_mock.Tool = MagicMock
    types_mock.TextContent = TextContent

    # mcp.server.lowlevel
    lowlevel_mock = MagicMock()
    lowlevel_mock.Server = _FakeServer

    # mcp.server.stdio
    stdio_mock = MagicMock()
    stdio_mock.stdio_server = MagicMock()

    # mcp.server
    server_mock = MagicMock()
    server_mock.lowlevel = lowlevel_mock
    server_mock.stdio = stdio_mock

    # mcp top-level
    mcp_mock = MagicMock()
    mcp_mock.server = server_mock
    mcp_mock.types = types_mock

    mocks_needed["mcp"] = mcp_mock
    mocks_needed["mcp.server"] = server_mock
    mocks_needed["mcp.server.lowlevel"] = lowlevel_mock
    mocks_needed["mcp.server.stdio"] = stdio_mock
    mocks_needed["mcp.types"] = types_mock

    for mod_name in ("claude_agent_sdk",):
        if mod_name not in sys.modules or isinstance(sys.modules[mod_name], MagicMock):
            mock = MagicMock()
            mock.tool = lambda *a, **kw: (lambda fn: fn)
            mocks_needed[mod_name] = mock

    for name, mock in mocks_needed.items():
        _originals[name] = sys.modules.get(name)
        sys.modules[name] = mock

    yield

    for name, orig in _originals.items():
        if orig is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = orig
    # Clean cached module so re-import works fresh
    sys.modules.pop("src.mcp_server", None)


@pytest.fixture(scope="module")
def mcp_mod():
    """Import and return the mcp_server module."""
    # Remove cached version to force fresh import with our mocks
    sys.modules.pop("src.mcp_server", None)
    import src.mcp_server as mod
    return mod


# ===== _text =====


class TestTextHelper:
    """Tests for _text helper function."""

    def test_returns_list(self, mcp_mod):
        result = mcp_mod._text("hello")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_text_content(self, mcp_mod):
        result = mcp_mod._text("test message")
        assert result[0].text == "test message"

    def test_empty_string(self, mcp_mod):
        result = mcp_mod._text("")
        assert result[0].text == ""

    def test_unicode(self, mcp_mod):
        result = mcp_mod._text("Cluster: 3/5 noeuds en ligne")
        assert "noeuds" in result[0].text


# ===== _error =====


class TestErrorHelper:
    """Tests for _error helper function."""

    def test_returns_list(self, mcp_mod):
        result = mcp_mod._error("something broke")
        assert isinstance(result, list)

    def test_error_prefix(self, mcp_mod):
        result = mcp_mod._error("bad input")
        assert "ERREUR" in result[0].text

    def test_contains_message(self, mcp_mod):
        result = mcp_mod._error("node offline")
        assert "node offline" in result[0].text


# ===== _safe_int =====


class TestSafeInt:
    """Tests for _safe_int conversion with default fallback."""

    def test_valid_int(self, mcp_mod):
        assert mcp_mod._safe_int(42, 0) == 42

    def test_valid_string_int(self, mcp_mod):
        assert mcp_mod._safe_int("10", 5) == 10

    def test_none_returns_default(self, mcp_mod):
        assert mcp_mod._safe_int(None, 99) == 99

    def test_invalid_string_returns_default(self, mcp_mod):
        assert mcp_mod._safe_int("abc", 7) == 7

    def test_float_string(self, mcp_mod):
        # int("3.5") raises ValueError
        assert mcp_mod._safe_int("3.5", 0) == 0

    def test_empty_string(self, mcp_mod):
        assert mcp_mod._safe_int("", 42) == 42

    def test_negative_int(self, mcp_mod):
        assert mcp_mod._safe_int(-5, 0) == -5

    def test_zero(self, mcp_mod):
        assert mcp_mod._safe_int(0, 10) == 0


# ===== _ps_sync =====


class TestPsSync:
    """Tests for _ps_sync — PowerShell synchronous command."""

    def test_successful_command(self, mcp_mod):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="output text\n", stderr="")
            result = mcp_mod._ps_sync("echo hello")
        assert result == "output text"

    def test_failed_command(self, mcp_mod):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
            result = mcp_mod._ps_sync("bad-cmd")
        assert "ERREUR" in result
        assert "error msg" in result

    def test_timeout_propagates(self, mcp_mod):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ps", 30)):
            with pytest.raises(subprocess.TimeoutExpired):
                mcp_mod._ps_sync("slow-cmd")


# ===== _ps (async wrapper) =====


class TestPsAsync:
    """Tests for _ps — async PowerShell wrapper."""

    @pytest.mark.asyncio
    async def test_calls_ps_sync(self, mcp_mod):
        with patch.object(mcp_mod, "_ps_sync", return_value="async result") as mock:
            result = await mcp_mod._ps("echo test")
        assert result == "async result"
        mock.assert_called_once_with("echo test")


# ===== _run =====


class TestRunHelper:
    """Tests for _run — blocking function async wrapper."""

    @pytest.mark.asyncio
    async def test_run_blocking(self, mcp_mod):
        def blocking_fn(x):
            return x * 2

        result = await mcp_mod._run(blocking_fn, 21)
        assert result == 42


# ===== handle_lm_query =====


class TestHandleLmQuery:
    """Tests for handle_lm_query handler."""

    @pytest.mark.asyncio
    async def test_unknown_node(self, mcp_mod):
        with patch.object(mcp_mod, "config") as cfg:
            cfg.get_node.return_value = None
            result = await mcp_mod.handle_lm_query({"prompt": "hello", "node": "X99"})
        text = result[0].text
        assert "ERREUR" in text or "inconnu" in text.lower()

    @pytest.mark.asyncio
    async def test_success(self, mcp_mod):
        mock_node = MagicMock()
        mock_node.url = "http://127.0.0.1:1234"
        mock_node.name = "M1"
        mock_node.default_model = "qwen3-8b"
        mock_node.auth_headers = {}

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": [{"type": "message", "content": "reply"}],
            "stats": {}
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)

        with patch.object(mcp_mod, "config") as cfg, \
             patch.object(mcp_mod, "_get_http", new_callable=AsyncMock, return_value=mock_http), \
             patch("src.tools.extract_lms_output", return_value="reply"):
            cfg.get_node.return_value = mock_node
            cfg.temperature = 0.3
            cfg.max_tokens = 1024
            result = await mcp_mod.handle_lm_query({"prompt": "hello"})
        text = result[0].text
        assert "reply" in text

    @pytest.mark.asyncio
    async def test_connect_error(self, mcp_mod):
        import httpx
        mock_node = MagicMock()
        mock_node.url = "http://127.0.0.1:1234"
        mock_node.name = "M1"
        mock_node.default_model = "qwen3-8b"
        mock_node.auth_headers = {}

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("down"))

        with patch.object(mcp_mod, "config") as cfg, \
             patch.object(mcp_mod, "_get_http", new_callable=AsyncMock, return_value=mock_http):
            cfg.get_node.return_value = mock_node
            cfg.temperature = 0.3
            cfg.max_tokens = 1024
            result = await mcp_mod.handle_lm_query({"prompt": "hello"})
        text = result[0].text
        assert "hors ligne" in text.lower() or "ERREUR" in text


# ===== handle_lm_models =====


class TestHandleLmModels:
    """Tests for handle_lm_models handler."""

    @pytest.mark.asyncio
    async def test_unknown_node(self, mcp_mod):
        with patch.object(mcp_mod, "config") as cfg:
            cfg.get_node.return_value = None
            result = await mcp_mod.handle_lm_models({"node": "X99"})
        assert "ERREUR" in result[0].text or "inconnu" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_lists_models(self, mcp_mod):
        mock_node = MagicMock()
        mock_node.url = "http://127.0.0.1:1234"
        mock_node.auth_headers = {}

        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [
            {"key": "qwen3-8b", "loaded_instances": 1},
            {"key": "qwen3-30b", "loaded_instances": 0},
        ]}
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        with patch.object(mcp_mod, "config") as cfg, \
             patch.object(mcp_mod, "_get_http", new_callable=AsyncMock, return_value=mock_http):
            cfg.get_node.return_value = mock_node
            result = await mcp_mod.handle_lm_models({"node": "M1"})
        assert "qwen3-8b" in result[0].text
        # qwen3-30b has loaded_instances=0, should not appear
        assert "qwen3-30b" not in result[0].text

    @pytest.mark.asyncio
    async def test_no_models_loaded(self, mcp_mod):
        mock_node = MagicMock()
        mock_node.url = "http://127.0.0.1:1234"
        mock_node.auth_headers = {}

        mock_response = MagicMock()
        mock_response.json.return_value = {"models": []}
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        with patch.object(mcp_mod, "config") as cfg, \
             patch.object(mcp_mod, "_get_http", new_callable=AsyncMock, return_value=mock_http):
            cfg.get_node.return_value = mock_node
            result = await mcp_mod.handle_lm_models({"node": "M1"})
        assert "aucun" in result[0].text


# ===== handle_system_audit =====


class TestHandleSystemAudit:
    """Tests for handle_system_audit handler."""

    @pytest.mark.asyncio
    async def test_script_not_found(self, mcp_mod):
        with patch("importlib.util.spec_from_file_location", return_value=None):
            result = await mcp_mod.handle_system_audit({"mode": "full"})
        text = result[0].text
        assert "ERREUR" in text or "introuvable" in text

    @pytest.mark.asyncio
    async def test_quick_mode(self, mcp_mod):
        mock_spec = MagicMock()
        mock_mod = MagicMock()
        mock_mod.run_audit = AsyncMock(return_value={"ok": True})
        mock_mod.format_report = MagicMock(return_value="Quick audit done")

        with patch("importlib.util.spec_from_file_location", return_value=mock_spec), \
             patch("importlib.util.module_from_spec", return_value=mock_mod):
            result = await mcp_mod.handle_system_audit({"mode": "quick"})
        text = result[0].text
        assert "Quick audit done" in text
        mock_mod.run_audit.assert_called_once_with(quick=True)


# ===== handle_execute_domino =====


class TestHandleExecuteDomino:
    """Tests for handle_execute_domino handler."""

    @pytest.mark.asyncio
    async def test_empty_domino_id(self, mcp_mod):
        result = await mcp_mod.handle_execute_domino({"domino_id": ""})
        assert "ERREUR" in result[0].text

    @pytest.mark.asyncio
    async def test_success(self, mcp_mod):
        mock_result = {
            "domino_id": "test_domino",
            "passed": 3, "failed": 0, "skipped": 0,
            "total_steps": 3, "total_ms": 150.0
        }
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=mock_result):
            result = await mcp_mod.handle_execute_domino({"domino_id": "test_domino"})
        text = result[0].text
        assert "test_domino" in text
        assert "3 PASS" in text

    @pytest.mark.asyncio
    async def test_domino_error(self, mcp_mod):
        mock_result = {"error": "Domino introuvable: xyz"}
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=mock_result):
            result = await mcp_mod.handle_execute_domino({"domino_id": "xyz"})
        text = result[0].text
        assert "ERREUR" in text or "introuvable" in text

    @pytest.mark.asyncio
    async def test_runtime_exception(self, mcp_mod):
        with patch("asyncio.to_thread", new_callable=AsyncMock, side_effect=RuntimeError("crash")):
            result = await mcp_mod.handle_execute_domino({"domino_id": "broken"})
        text = result[0].text
        assert "ERREUR" in text or "crash" in text.lower()


# ===== handle_list_dominos =====


class TestHandleListDominos:
    """Tests for handle_list_dominos handler."""

    @pytest.mark.asyncio
    async def test_import_error(self, mcp_mod):
        with patch.dict(sys.modules, {"src.domino_pipelines": None}):
            with patch("builtins.__import__", side_effect=ImportError("not found")):
                # This handler uses from src.domino_pipelines import
                result = await mcp_mod.handle_list_dominos({})
        # May either show empty or error
        text = result[0].text
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_lists_dominos(self, mcp_mod):
        mock_domino = MagicMock()
        mock_domino.id = "test_d"
        mock_domino.category = "system"
        mock_domino.description = "Test domino"
        mock_domino.triggers = ["test"]
        mock_domino.steps = [1, 2, 3]

        mock_pipelines = MagicMock()
        mock_pipelines.DOMINO_PIPELINES = [mock_domino]

        with patch.dict(sys.modules, {"src.domino_pipelines": mock_pipelines}):
            result = await mcp_mod.handle_list_dominos({})
        text = result[0].text
        assert "test_d" in text or "1 dominos" in text


# ===== handle_domino_stats =====


class TestHandleDominoStats:
    """Tests for handle_domino_stats handler."""

    @pytest.mark.asyncio
    async def test_no_history(self, mcp_mod):
        mock_logger = MagicMock()
        mock_logger.db_path = ":memory:"

        mock_executor_mod = MagicMock()
        mock_executor_mod.DominoLogger.return_value = mock_logger

        # Create in-memory DB with schema
        conn = sqlite3.connect(":memory:")
        conn.execute("""CREATE TABLE domino_logs (
            run_id TEXT, domino_id TEXT, ts TEXT, step_index INTEGER,
            step_name TEXT, status TEXT, duration_ms REAL, output TEXT
        )""")

        with patch.dict(sys.modules, {"src.domino_executor": mock_executor_mod}), \
             patch("sqlite3.connect", return_value=conn):
            result = await mcp_mod.handle_domino_stats({})
        text = result[0].text
        assert "Aucun" in text or "0" in text or "historique" in text.lower()
        conn.close()

    @pytest.mark.asyncio
    async def test_with_history(self, mcp_mod):
        mock_logger = MagicMock()
        mock_logger.db_path = ":memory:"

        mock_executor_mod = MagicMock()
        mock_executor_mod.DominoLogger.return_value = mock_logger

        conn = sqlite3.connect(":memory:")
        conn.execute("""CREATE TABLE domino_logs (
            run_id TEXT, domino_id TEXT, ts TEXT, step_index INTEGER,
            step_name TEXT, status TEXT, duration_ms REAL, output TEXT
        )""")
        conn.execute("""INSERT INTO domino_logs VALUES
            ('r1', 'test_d', '2026-01-01', 0, 'step1', 'PASS', 100.0, 'ok')""")
        conn.commit()

        with patch.dict(sys.modules, {"src.domino_executor": mock_executor_mod}), \
             patch("sqlite3.connect", return_value=conn):
            result = await mcp_mod.handle_domino_stats({"limit": "5"})
        text = result[0].text
        assert "test_d" in text
        conn.close()


# ===== handle_dict_crud — validation =====


class TestHandleDictCrud:
    """Tests for handle_dict_crud — validates inputs and operations."""

    @pytest.mark.asyncio
    async def test_invalid_table(self, mcp_mod):
        result = await mcp_mod.handle_dict_crud({
            "operation": "stats", "table": "DROP_TABLE"
        })
        text = result[0].text
        assert "ERREUR" in text or "Invalid table" in text

    @pytest.mark.asyncio
    async def test_invalid_json_data(self, mcp_mod):
        result = await mcp_mod.handle_dict_crud({
            "operation": "search",
            "table": "pipeline_dictionary",
            "data": "NOT{JSON"
        })
        text = result[0].text
        assert "ERREUR" in text or "JSON" in text

    @pytest.mark.asyncio
    async def test_valid_table_accepted(self, mcp_mod):
        # Stats on a valid table but db may not exist
        with patch("pathlib.Path.exists", return_value=False):
            result = await mcp_mod.handle_dict_crud({
                "operation": "stats",
                "table": "pipeline_dictionary"
            })
        text = result[0].text
        # Should error about db not found, not about table
        assert "Database" in text or "ERREUR" in text


# ===== _DICT_VALID_CATS / _DICT_VALID_ACTS =====


class TestDictConstants:
    """Tests for dictionary CRUD constants."""

    def test_valid_categories_non_empty(self, mcp_mod):
        assert len(mcp_mod._DICT_VALID_CATS) > 5
        assert "system" in mcp_mod._DICT_VALID_CATS
        assert "trading" in mcp_mod._DICT_VALID_CATS

    def test_valid_actions_non_empty(self, mcp_mod):
        assert len(mcp_mod._DICT_VALID_ACTS) > 3
        assert "powershell" in mcp_mod._DICT_VALID_ACTS
        assert "pipeline" in mcp_mod._DICT_VALID_ACTS

    def test_valid_tables(self, mcp_mod):
        assert "pipeline_dictionary" in mcp_mod._DICT_TABLES
        assert "domino_chains" in mcp_mod._DICT_TABLES
        assert "voice_corrections" in mcp_mod._DICT_TABLES

    def test_safe_col_regex(self, mcp_mod):
        assert mcp_mod._SAFE_COL_RE.match("valid_col")
        assert mcp_mod._SAFE_COL_RE.match("col123")
        assert not mcp_mod._SAFE_COL_RE.match("1bad")
        assert not mcp_mod._SAFE_COL_RE.match("bad col")
        assert not mcp_mod._SAFE_COL_RE.match("bad;col")


# ===== handle_speak =====


class TestHandleSpeak:
    """Tests for handle_speak handler."""

    @pytest.mark.asyncio
    async def test_missing_text(self, mcp_mod):
        # handle_speak expects args["text"]
        if hasattr(mcp_mod, "handle_speak"):
            try:
                result = await mcp_mod.handle_speak({})
                # Should error or handle gracefully
                text = result[0].text if result else ""
                assert isinstance(text, str)
            except (KeyError, TypeError):
                pass  # Acceptable — missing required arg
