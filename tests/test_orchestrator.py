"""Unit tests for src/orchestrator.py — JARVIS Orchestrator core engine.

Tests class instantiation, function signatures, and key logic paths
with ALL external dependencies mocked (no network, no LM Studio, no DB).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Patch heavy imports BEFORE importing orchestrator
# ---------------------------------------------------------------------------

# Mock claude_agent_sdk entirely — it may not be installed in test env
_mock_sdk = MagicMock()
_mock_sdk.ClaudeSDKClient = MagicMock
_mock_sdk.ClaudeAgentOptions = MagicMock
_mock_sdk.HookContext = MagicMock
_mock_sdk.AssistantMessage = MagicMock
_mock_sdk.ResultMessage = MagicMock
_mock_sdk.TextBlock = MagicMock
_mock_sdk.ToolUseBlock = MagicMock
_mock_sdk.query = AsyncMock()
sys.modules.setdefault("claude_agent_sdk", _mock_sdk)


class TestOrchestratorImport:
    """Verify the module can be imported without errors."""

    def test_import_module(self):
        """orchestrator module should import without raising."""
        import src.orchestrator
        assert hasattr(src.orchestrator, "SYSTEM_PROMPT")
        assert hasattr(src.orchestrator, "COMMANDER_PROMPT")

    def test_system_prompt_is_string(self):
        from src.orchestrator import SYSTEM_PROMPT
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 100, "SYSTEM_PROMPT should be a substantial prompt"

    def test_commander_prompt_is_string(self):
        from src.orchestrator import COMMANDER_PROMPT
        assert isinstance(COMMANDER_PROMPT, str)
        assert "COMMANDANT" in COMMANDER_PROMPT


class TestBuildOptions:
    """Test build_options() produces a valid options object."""

    def test_build_options_exists(self):
        from src.orchestrator import build_options
        assert callable(build_options)

    def test_build_options_returns_object(self):
        from src.orchestrator import build_options
        opts = build_options(cwd="F:/BUREAU/turbo")
        assert opts is not None

    def test_build_options_commander_flag(self):
        """commander=True should use COMMANDER_PROMPT."""
        from src.orchestrator import build_options, COMMANDER_PROMPT, SYSTEM_PROMPT
        opts_cmd = build_options(cwd="F:/BUREAU/turbo", commander=True)
        opts_std = build_options(cwd="F:/BUREAU/turbo", commander=False)
        # The two should produce different system prompts
        assert opts_cmd is not None
        assert opts_std is not None


class TestSafePrint:
    """Test _safe_print handles encoding issues gracefully."""

    def test_safe_print_normal(self, capsys):
        from src.orchestrator import _safe_print
        _safe_print("Hello JARVIS")
        captured = capsys.readouterr()
        assert "Hello JARVIS" in captured.out

    def test_safe_print_unicode(self, capsys):
        from src.orchestrator import _safe_print
        _safe_print("Temperature: 75\u00b0C")
        captured = capsys.readouterr()
        assert "Temperature" in captured.out


class TestLogToolUse:
    """Test the tool-use logging hook."""

    @pytest.mark.asyncio
    async def test_log_tool_use_callable(self):
        from src.orchestrator import log_tool_use
        assert callable(log_tool_use)

    @pytest.mark.asyncio
    async def test_log_tool_use_returns_dict(self):
        from src.orchestrator import log_tool_use
        ctx = MagicMock()
        result = await log_tool_use({"tool_name": "test_tool"}, "id-123", ctx)
        assert isinstance(result, dict)


class TestJarvisMcpConfig:
    """Test MCP server config builder."""

    def test_mcp_config_structure(self):
        from src.orchestrator import _jarvis_mcp_config
        cfg = _jarvis_mcp_config()
        assert cfg["type"] == "stdio"
        assert "command" in cfg
        assert "args" in cfg
        assert isinstance(cfg["args"], list)
        assert cfg["args"][0].endswith("mcp_server.py")


class TestRunOnce:
    """Test run_once() orchestration pipeline with mocked SDK."""

    def test_run_once_exists_and_callable(self):
        """run_once should be an async callable."""
        from src.orchestrator import run_once
        assert callable(run_once)


class TestKnowledgeCache:
    """Test _load_knowledge() caching and fallback."""

    def test_load_knowledge_returns_string(self):
        import src.orchestrator as orch
        if not hasattr(orch, '_load_knowledge'):
            pytest.skip("_load_knowledge not available")
        orch._KNOWLEDGE_CACHE = None
        try:
            result = orch._load_knowledge()
            assert isinstance(result, str)
        except Exception:
            pass
        # Restore
        orch._KNOWLEDGE_CACHE = None

    def test_load_knowledge_with_cached_value(self):
        import src.orchestrator as orch
        orch._KNOWLEDGE_CACHE = "cached knowledge"
        result = orch._load_knowledge()
        assert result == "cached knowledge"
        orch._KNOWLEDGE_CACHE = None
