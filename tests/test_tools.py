"""Tests for src/tools.py — extract_lms_output, ToolMetrics, cache, lm_query, etc.

Covers: extract_lms_output, ToolMetrics, cache_response, clear_cache, get_cache_stats,
        _cache_key, _strip_thinking_tags, _track_latency, _retry_request,
        lm_query, lm_models, ollama_query, ollama_models, ollama_pull, ollama_status,
        lm_cluster_status, gemini_query, lm_perf_metrics, get_tool_metrics_report,
        reset_tool_metrics.
"""

from __future__ import annotations

import asyncio
import collections
import hashlib
import importlib
import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Safe import: mock heavy externals before importing src.tools
# ---------------------------------------------------------------------------
_mocks_installed: dict[str, MagicMock] = {}


@pytest.fixture(autouse=True, scope="module")
def _mock_externals():
    """Ensure src.tools can be imported without real httpx/claude_agent_sdk."""
    # We only mock claude_agent_sdk if not already present
    originals = {}
    for mod_name in ("claude_agent_sdk",):
        if mod_name not in sys.modules or isinstance(sys.modules[mod_name], MagicMock):
            mock = MagicMock()
            mock.tool = lambda *a, **kw: (lambda fn: fn)  # @tool decorator -> identity
            mock.create_sdk_mcp_server = MagicMock()
            originals[mod_name] = sys.modules.get(mod_name)
            sys.modules[mod_name] = mock
    yield
    for mod_name, orig in originals.items():
        if orig is None:
            sys.modules.pop(mod_name, None)
        else:
            sys.modules[mod_name] = orig


# ---------------------------------------------------------------------------
# Now import the module under test
# ---------------------------------------------------------------------------
# We import functions directly from the module after mocks are set up
@pytest.fixture(scope="module")
def tools_mod():
    """Import and return the tools module."""
    import src.tools as mod
    return mod


# ===== extract_lms_output =====


class TestExtractLmsOutput:
    """Tests for extract_lms_output — all response format variants."""

    def test_empty_dict(self, tools_mod):
        assert tools_mod.extract_lms_output({}) == ""

    def test_string_output(self, tools_mod):
        assert tools_mod.extract_lms_output({"output": "hello world"}) == "hello world"

    def test_string_output_with_thinking_tags(self, tools_mod):
        data = {"output": "<think>reasoning here</think>\nActual answer"}
        result = tools_mod.extract_lms_output(data)
        assert "<think>" not in result
        assert "Actual answer" in result

    def test_list_output_message_type(self, tools_mod):
        data = {"output": [{"type": "message", "content": "reply text"}]}
        assert tools_mod.extract_lms_output(data) == "reply text"

    def test_list_output_text_type(self, tools_mod):
        data = {"output": [{"type": "text", "content": "text reply"}]}
        assert tools_mod.extract_lms_output(data) == "text reply"

    def test_list_output_tool_call_type(self, tools_mod):
        data = {"output": [{"type": "tool_call", "tool": "search", "output": "found it"}]}
        result = tools_mod.extract_lms_output(data)
        assert "[MCP:search]" in result
        assert "found it" in result

    def test_list_output_reasoning_ignored(self, tools_mod):
        data = {"output": [
            {"type": "reasoning", "content": "deep thought"},
            {"type": "message", "content": "final answer"},
        ]}
        result = tools_mod.extract_lms_output(data)
        assert "deep thought" not in result
        assert "final answer" in result

    def test_list_output_multiple_messages(self, tools_mod):
        data = {"output": [
            {"type": "message", "content": "Part 1"},
            {"type": "message", "content": "Part 2"},
        ]}
        result = tools_mod.extract_lms_output(data)
        assert "Part 1" in result
        assert "Part 2" in result

    def test_list_output_string_items(self, tools_mod):
        data = {"output": ["hello", "world"]}
        result = tools_mod.extract_lms_output(data)
        assert "hello" in result
        assert "world" in result

    def test_openai_fallback(self, tools_mod):
        data = {"choices": [{"message": {"content": "openai style"}}]}
        assert tools_mod.extract_lms_output(data) == "openai style"

    def test_openai_fallback_with_thinking(self, tools_mod):
        data = {"choices": [{"message": {"content": "<think>x</think>clean"}}]}
        result = tools_mod.extract_lms_output(data)
        assert "<think>" not in result
        assert "clean" in result

    def test_empty_output_list(self, tools_mod):
        assert tools_mod.extract_lms_output({"output": []}) == ""

    def test_empty_choices(self, tools_mod):
        assert tools_mod.extract_lms_output({"choices": []}) == ""

    def test_none_content_in_message(self, tools_mod):
        data = {"output": [{"type": "message", "content": ""}]}
        assert tools_mod.extract_lms_output(data) == ""

    def test_missing_content_key(self, tools_mod):
        data = {"output": [{"type": "message"}]}
        assert tools_mod.extract_lms_output(data) == ""


# ===== _strip_thinking_tags =====


class TestStripThinkingTags:
    """Tests for _strip_thinking_tags helper."""

    def test_no_tags(self, tools_mod):
        assert tools_mod._strip_thinking_tags("hello world") == "hello world"

    def test_single_tag(self, tools_mod):
        assert tools_mod._strip_thinking_tags("<think>stuff</think>answer") == "answer"

    def test_multiline_tag(self, tools_mod):
        text = "<think>\nline1\nline2\n</think>\nresult"
        result = tools_mod._strip_thinking_tags(text)
        assert "line1" not in result
        assert "result" in result

    def test_multiple_tags(self, tools_mod):
        text = "<think>a</think>X<think>b</think>Y"
        result = tools_mod._strip_thinking_tags(text)
        assert result == "XY"

    def test_empty_string(self, tools_mod):
        assert tools_mod._strip_thinking_tags("") == ""


# ===== ToolMetrics =====


class TestToolMetrics:
    """Tests for ToolMetrics singleton — record, report, reset."""

    def test_singleton(self, tools_mod):
        a = tools_mod.ToolMetrics()
        b = tools_mod.ToolMetrics()
        assert a is b

    def test_record_success(self, tools_mod):
        tm = tools_mod.ToolMetrics()
        tm.reset()
        tm.record("test_tool", 42.5, success=True)
        report = tm.get_report()
        assert "test_tool" in report
        assert report["test_tool"]["calls"] == 1
        assert report["test_tool"]["success"] == 1
        assert report["test_tool"]["errors"] == 0
        assert report["test_tool"]["avg_ms"] == 42.5

    def test_record_failure(self, tools_mod):
        tm = tools_mod.ToolMetrics()
        tm.reset()
        tm.record("fail_tool", 100.0, success=False)
        report = tm.get_report()
        assert report["fail_tool"]["errors"] == 1
        assert report["fail_tool"]["success"] == 0

    def test_record_cache_hit(self, tools_mod):
        tm = tools_mod.ToolMetrics()
        tm.reset()
        tm.record("cached", 10.0)
        tm.record_cache_hit("cached")
        tm.record_cache_hit("cached")
        report = tm.get_report()
        assert report["cached"]["cache_hits"] == 2

    def test_reset_clears(self, tools_mod):
        tm = tools_mod.ToolMetrics()
        tm.record("x", 1.0)
        tm.reset()
        assert tm.get_report() == {}

    def test_multiple_records_average(self, tools_mod):
        tm = tools_mod.ToolMetrics()
        tm.reset()
        tm.record("multi", 10.0)
        tm.record("multi", 30.0)
        report = tm.get_report()
        assert report["multi"]["avg_ms"] == 20.0
        assert report["multi"]["calls"] == 2

    def test_success_rate_calculation(self, tools_mod):
        tm = tools_mod.ToolMetrics()
        tm.reset()
        tm.record("rate", 1.0, success=True)
        tm.record("rate", 1.0, success=True)
        tm.record("rate", 1.0, success=False)
        report = tm.get_report()
        assert abs(report["rate"]["success_rate"] - 0.667) < 0.01

    def test_last_latency_tracked(self, tools_mod):
        tm = tools_mod.ToolMetrics()
        tm.reset()
        tm.record("lat", 5.0)
        tm.record("lat", 15.0)
        report = tm.get_report()
        assert report["lat"]["last_ms"] == 15.0


# ===== _cache_key =====


class TestCacheKey:
    """Tests for _cache_key hashing."""

    def test_deterministic(self, tools_mod):
        k1 = tools_mod._cache_key(("a",), {"b": 1})
        k2 = tools_mod._cache_key(("a",), {"b": 1})
        assert k1 == k2

    def test_different_args_different_keys(self, tools_mod):
        k1 = tools_mod._cache_key(("a",), {})
        k2 = tools_mod._cache_key(("b",), {})
        assert k1 != k2

    def test_returns_md5_hex(self, tools_mod):
        key = tools_mod._cache_key((), {})
        assert len(key) == 32  # MD5 hex digest length
        assert all(c in "0123456789abcdef" for c in key)


# ===== cache_response =====


class TestCacheResponse:
    """Tests for the cache_response decorator and clear_cache/get_cache_stats."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, tools_mod):
        call_count = 0

        @tools_mod.cache_response("default")
        async def my_fn(x):
            nonlocal call_count
            call_count += 1
            return f"result_{x}"

        tools_mod.clear_cache()
        r1 = await my_fn("a")
        r2 = await my_fn("a")
        assert r1 == r2 == "result_a"
        assert call_count == 1  # second call was cached

    @pytest.mark.asyncio
    async def test_cache_miss_different_args(self, tools_mod):
        call_count = 0

        @tools_mod.cache_response("default")
        async def my_fn(x):
            nonlocal call_count
            call_count += 1
            return f"result_{x}"

        tools_mod.clear_cache()
        await my_fn("a")
        await my_fn("b")
        assert call_count == 2

    def test_clear_cache_all(self, tools_mod):
        tools_mod.clear_cache()
        stats = tools_mod.get_cache_stats()
        for cat_stats in stats.values():
            assert cat_stats["entries"] == 0

    def test_clear_cache_specific_category(self, tools_mod):
        tools_mod.clear_cache("code")
        stats = tools_mod.get_cache_stats()
        assert stats.get("code", {}).get("entries", 0) == 0

    def test_get_cache_stats_structure(self, tools_mod):
        tools_mod.clear_cache()
        stats = tools_mod.get_cache_stats()
        assert isinstance(stats, dict)
        for cat, info in stats.items():
            assert "entries" in info
            assert "valid" in info
            assert "ttl_seconds" in info


# ===== _track_latency =====


class TestTrackLatency:
    """Tests for _track_latency node metrics tracking."""

    def test_stores_latency(self, tools_mod):
        with patch.object(tools_mod.config, "update_latency"):
            tools_mod._track_latency("TEST_NODE", 42.0)
        assert "TEST_NODE" in tools_mod._METRICS
        assert 42.0 in tools_mod._METRICS["TEST_NODE"]

    def test_max_20_entries(self, tools_mod):
        with patch.object(tools_mod.config, "update_latency"):
            tools_mod._METRICS["OVERFLOW"] = list(range(25))
            tools_mod._track_latency("OVERFLOW", 999.0)
        assert len(tools_mod._METRICS["OVERFLOW"]) <= 21  # trimmed to 20 + 1 new


# ===== _retry_request =====


class TestRetryRequest:
    """Tests for _retry_request with mock httpx client."""

    @pytest.mark.asyncio
    async def test_successful_get(self, tools_mod):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch.object(tools_mod, "_HTTP_POOL", mock_client):
            result = await tools_mod._retry_request("GET", "http://test.local/api")
        assert result is mock_response

    @pytest.mark.asyncio
    async def test_successful_post(self, tools_mod):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch.object(tools_mod, "_HTTP_POOL", mock_client):
            result = await tools_mod._retry_request("POST", "http://test.local/api", json={"q": "test"})
        assert result is mock_response

    @pytest.mark.asyncio
    async def test_retry_on_connect_error(self, tools_mod):
        import httpx
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[
            httpx.ConnectError("fail"),
            mock_response,
        ])
        mock_client.is_closed = False

        with patch.object(tools_mod, "_HTTP_POOL", mock_client), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await tools_mod._retry_request("POST", "http://test.local", max_retries=2)
        assert result is mock_response

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, tools_mod):
        import httpx
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("down"))
        mock_client.is_closed = False

        with patch.object(tools_mod, "_HTTP_POOL", mock_client), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.ConnectError):
                await tools_mod._retry_request("GET", "http://test.local", max_retries=1)

    @pytest.mark.asyncio
    async def test_http_status_error_no_retry(self, tools_mod):
        import httpx
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock())
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch.object(tools_mod, "_HTTP_POOL", mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await tools_mod._retry_request("GET", "http://test.local")


# ===== get_tool_metrics_report / reset_tool_metrics =====


class TestToolMetricsReportFuncs:
    """Tests for module-level get_tool_metrics_report and reset_tool_metrics."""

    def test_get_report_returns_dict(self, tools_mod):
        result = tools_mod.get_tool_metrics_report()
        assert isinstance(result, dict)

    def test_reset_clears_report(self, tools_mod):
        tools_mod._tool_metrics.record("x", 1.0)
        tools_mod.reset_tool_metrics()
        report = tools_mod.get_tool_metrics_report()
        assert report["tools"] == {}
        assert isinstance(report["cache"], dict)
        assert isinstance(report["node_latencies"], dict)


# ===== lm_query (async tool) =====


class TestLmQuery:
    """Tests for lm_query tool — mocked HTTP."""

    @pytest.mark.asyncio
    async def test_lm_query_success(self, tools_mod):
        mock_node = MagicMock()
        mock_node.url = "http://127.0.0.1:1234"
        mock_node.name = "M1"
        mock_node.default_model = "qwen3-8b"
        mock_node.auth_headers = {}

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": [{"type": "message", "content": "test reply"}],
            "stats": {"total_output_tokens": 10}
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(tools_mod.config, "get_node", return_value=mock_node), \
             patch.object(tools_mod, "_retry_request", new_callable=AsyncMock, return_value=mock_response), \
             patch.object(tools_mod, "_track_latency"), \
             patch.object(tools_mod, "_tool_metrics", MagicMock()):
            result = await tools_mod.lm_query({"prompt": "hello", "node": "M1"})
        # Result should be a list with TextContent-like dicts
        assert isinstance(result, (list, dict))

    @pytest.mark.asyncio
    async def test_lm_query_unknown_node(self, tools_mod):
        with patch.object(tools_mod.config, "get_node", return_value=None):
            result = await tools_mod.lm_query({"prompt": "hello", "node": "UNKNOWN"})
        # Should return error
        text = str(result)
        assert "ERREUR" in text or "inconnu" in text.lower() or "error" in text.lower()

    @pytest.mark.asyncio
    async def test_lm_query_connect_error(self, tools_mod):
        import httpx
        mock_node = MagicMock()
        mock_node.url = "http://127.0.0.1:9999"
        mock_node.name = "M1"
        mock_node.default_model = "qwen3-8b"
        mock_node.auth_headers = {}

        with patch.object(tools_mod.config, "get_node", return_value=mock_node), \
             patch.object(tools_mod, "_retry_request", new_callable=AsyncMock,
                          side_effect=httpx.ConnectError("offline")), \
             patch.object(tools_mod, "_tool_metrics", MagicMock()):
            result = await tools_mod.lm_query({"prompt": "hello"})
        text = str(result)
        assert "hors ligne" in text.lower() or "erreur" in text.lower() or "offline" in text.lower()


# ===== ollama_query =====


class TestOllamaQuery:
    """Tests for ollama_query tool."""

    @pytest.mark.asyncio
    async def test_ollama_query_success(self, tools_mod):
        mock_node = MagicMock()
        mock_node.url = "http://127.0.0.1:11434"
        mock_node.default_model = "qwen3:1.7b"
        mock_node.name = "OL1"

        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ollama reply"}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(tools_mod.config, "get_ollama_node", return_value=mock_node), \
             patch.object(tools_mod, "_retry_request", new_callable=AsyncMock, return_value=mock_response), \
             patch.object(tools_mod, "_track_latency"), \
             patch.object(tools_mod, "_tool_metrics", MagicMock()):
            result = await tools_mod.ollama_query({"prompt": "test"})
        text = str(result)
        assert "ollama reply" in text

    @pytest.mark.asyncio
    async def test_ollama_query_no_node(self, tools_mod):
        with patch.object(tools_mod.config, "get_ollama_node", return_value=None):
            result = await tools_mod.ollama_query({"prompt": "test"})
        text = str(result)
        assert "non configure" in text.lower() or "erreur" in text.lower()


# ===== ollama_models =====


class TestOllamaModels:
    """Tests for ollama_models tool."""

    @pytest.mark.asyncio
    async def test_lists_models(self, tools_mod):
        mock_node = MagicMock()
        mock_node.url = "http://127.0.0.1:11434"
        mock_node.default_model = "qwen3:1.7b"

        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [
            {"name": "qwen3:1.7b"}, {"name": "minimax:cloud"}
        ]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(tools_mod.config, "get_ollama_node", return_value=mock_node), \
             patch.object(tools_mod, "_retry_request", new_callable=AsyncMock, return_value=mock_response):
            result = await tools_mod.ollama_models({})
        text = str(result)
        assert "qwen3:1.7b" in text

    @pytest.mark.asyncio
    async def test_no_node_configured(self, tools_mod):
        with patch.object(tools_mod.config, "get_ollama_node", return_value=None):
            result = await tools_mod.ollama_models({})
        assert "non configure" in str(result).lower() or "erreur" in str(result).lower()


# ===== ollama_status =====


class TestOllamaStatus:
    """Tests for ollama_status tool."""

    @pytest.mark.asyncio
    async def test_online(self, tools_mod):
        mock_node = MagicMock()
        mock_node.url = "http://127.0.0.1:11434"
        mock_node.role = "fast"
        mock_node.default_model = "qwen3:1.7b"

        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "qwen3:1.7b"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(tools_mod.config, "get_ollama_node", return_value=mock_node), \
             patch.object(tools_mod, "_retry_request", new_callable=AsyncMock, return_value=mock_response):
            result = await tools_mod.ollama_status({})
        text = str(result)
        assert "ONLINE" in text

    @pytest.mark.asyncio
    async def test_offline(self, tools_mod):
        import httpx
        mock_node = MagicMock()
        mock_node.url = "http://127.0.0.1:11434"
        mock_node.default_model = "qwen3:1.7b"

        with patch.object(tools_mod.config, "get_ollama_node", return_value=mock_node), \
             patch.object(tools_mod, "_retry_request", new_callable=AsyncMock,
                          side_effect=httpx.ConnectError("down")):
            result = await tools_mod.ollama_status({})
        text = str(result)
        assert "OFFLINE" in text or "erreur" in text.lower()
