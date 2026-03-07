"""Tests for src/mcp_server_sse.py — MCP remote server tool sets.

Covers: PERPLEXITY_TOOLS, FULL_TOOLS sets, DEFAULT_PORT,
build_light_app filtering logic.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mock heavy dependencies before import
_mcp_mocks = {}
for mod in ("mcp", "mcp.server", "mcp.server.lowlevel", "mcp.server.streamable_http_manager",
            "mcp.server.sse", "mcp.types", "uvicorn",
            "starlette", "starlette.applications", "starlette.middleware",
            "starlette.middleware.cors", "starlette.routing", "starlette.responses"):
    if mod not in sys.modules:
        _mcp_mocks[mod] = sys.modules.setdefault(mod, MagicMock())

# Mock the mcp_server import to avoid loading all handlers
sys.modules.setdefault("src.mcp_server", MagicMock(
    TOOL_DEFINITIONS=[
        ("lm_query", "Query LM", {}, MagicMock()),
        ("consensus", "Consensus", {}, MagicMock()),
        ("system_info", "System", {}, MagicMock()),
        ("powershell_run", "PS run", {}, MagicMock()),
        ("sql_query", "SQL", {}, MagicMock()),
        ("unknown_tool_xyz", "Unknown", {}, MagicMock()),
    ],
    HANDLERS={},
    _build_input_schema=MagicMock(return_value={}),
    _text=MagicMock(side_effect=lambda x: [{"type": "text", "text": x}]),
    _error=MagicMock(side_effect=lambda x: [{"type": "text", "text": f"ERROR: {x}"}]),
))

from src.mcp_server_sse import PERPLEXITY_TOOLS, FULL_TOOLS, DEFAULT_PORT, build_light_app

# Restore modules
for mod in _mcp_mocks:
    if mod in sys.modules and sys.modules[mod] is _mcp_mocks[mod]:
        del sys.modules[mod]


# ===========================================================================
# PERPLEXITY_TOOLS (light set)
# ===========================================================================

class TestPerplexityTools:
    def test_not_empty(self):
        assert len(PERPLEXITY_TOOLS) >= 20

    def test_is_set(self):
        assert isinstance(PERPLEXITY_TOOLS, set)

    def test_core_tools(self):
        for tool in ("lm_query", "consensus", "system_info", "gpu_info",
                      "brain_status", "trading_pipeline_v2"):
            assert tool in PERPLEXITY_TOOLS, f"Missing: {tool}"

    def test_no_dangerous_without_purpose(self):
        # Light tier should include powershell for system control
        assert "powershell_run" in PERPLEXITY_TOOLS

    def test_all_strings(self):
        for t in PERPLEXITY_TOOLS:
            assert isinstance(t, str)
            assert len(t) > 0


# ===========================================================================
# FULL_TOOLS
# ===========================================================================

class TestFullTools:
    def test_not_empty(self):
        assert len(FULL_TOOLS) >= 80

    def test_is_set(self):
        assert isinstance(FULL_TOOLS, set)

    def test_superset_of_light(self):
        assert PERPLEXITY_TOOLS.issubset(FULL_TOOLS)

    def test_includes_advanced_tools(self):
        for tool in ("browser_open", "browser_navigate", "browser_click",
                      "cache_stats", "optimizer_optimize"):
            assert tool in FULL_TOOLS, f"Missing: {tool}"

    def test_categories_represented(self):
        # Check tools from various categories
        categories = {
            "cluster": "lm_query",
            "trading": "trading_pipeline_v2",
            "memory": "memory_recall",
            "security": "security_score",
            "database": "sql_query",
            "browser": "browser_open",
        }
        for cat, tool in categories.items():
            assert tool in FULL_TOOLS, f"Category {cat} missing tool {tool}"

    def test_all_strings(self):
        for t in FULL_TOOLS:
            assert isinstance(t, str)


# ===========================================================================
# DEFAULT_PORT
# ===========================================================================

class TestDefaults:
    def test_default_port(self):
        assert DEFAULT_PORT == 8901


# ===========================================================================
# build_light_app
# ===========================================================================

class TestBuildLightApp:
    def test_returns_server(self):
        app = build_light_app(tool_whitelist={"lm_query", "consensus"})
        assert app is not None

    def test_no_whitelist_includes_all(self):
        app = build_light_app(tool_whitelist=None)
        assert app is not None

    def test_empty_whitelist(self):
        app = build_light_app(tool_whitelist=set())
        assert app is not None
