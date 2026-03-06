"""Tests for src.cluster_startup — Cluster boot-time optimization.

Covers: LM Studio CLI operations, inference warmup/benchmarking,
GPU monitoring, thermal checks, Ollama checks, M2 checks,
main startup sequence, on-demand model loading, health checks,
service discovery, version checks, and startup logging.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

# ---------------------------------------------------------------------------
# Patch external dependencies before importing the module under test
# ---------------------------------------------------------------------------

import src.cluster_startup as cs


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for all CLI operations."""
    with patch("src.cluster_startup.subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture
def mock_config():
    """Mock the config object used throughout cluster_startup."""
    with patch("src.cluster_startup.config") as cfg:
        # LMStudioNode-like mock for M1
        m1 = MagicMock()
        m1.url = "http://127.0.0.1:1234"
        m1.auth_headers = {}
        m1.default_model = "qwen/qwen3-8b"

        # LMStudioNode-like mock for M2
        m2 = MagicMock()
        m2.url = "http://192.168.1.26:1234"
        m2.auth_headers = {"Authorization": "Bearer test-key"}
        m2.default_model = "deepseek-r1-0528-qwen3-8b"

        # OllamaNode-like mock for OL1
        ol1 = MagicMock()
        ol1.url = "http://127.0.0.1:11434"

        # Node lookups
        def get_node(name):
            return {"M1": m1, "M2": m2, "M3": None}.get(name)

        def get_ollama_node(name="OL1"):
            return ol1 if name == "OL1" else None

        def get_node_url(name):
            mapping = {"M1": "http://127.0.0.1:1234", "M2": "http://192.168.1.26:1234"}
            return mapping.get(name)

        cfg.get_node = get_node
        cfg.get_ollama_node = get_ollama_node
        cfg.get_node_url = get_node_url
        cfg.connect_timeout = 5.0
        cfg.health_timeout = 3.0
        cfg.gpu_thermal_warning = 75
        cfg.gpu_thermal_critical = 85

        yield cfg


@pytest.fixture(autouse=True)
def reset_thermal_cache():
    """Reset the thermal cache before each test to avoid cross-test pollution."""
    cs._thermal_cache.clear()
    cs._thermal_cache_ts = 0.0
    yield
    cs._thermal_cache.clear()
    cs._thermal_cache_ts = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Unit helpers
# ═══════════════════════════════════════════════════════════════════════════

class TestStripAnsi:
    """Tests for _strip_ansi helper."""

    def test_removes_color_codes(self):
        assert cs._strip_ansi("\x1b[32mOK\x1b[0m") == "OK"

    def test_removes_cursor_codes(self):
        # The regex matches [25h/[25l (no backslash) and [\25h/[\25l (with backslash)
        assert cs._strip_ansi("[25htext[25l") == "text"
        assert cs._strip_ansi("[\\25htext[\\25l") == "text"

    def test_passthrough_clean_text(self):
        assert cs._strip_ansi("hello world") == "hello world"

    def test_empty_string(self):
        assert cs._strip_ansi("") == ""


class TestLog:
    """Tests for _log helper."""

    def test_log_info(self):
        with patch.object(cs.logger, "info") as mock_info:
            cs._log("test message", "INFO")
            mock_info.assert_called_once_with("[startup] %s", "test message")

    def test_log_ok(self):
        with patch.object(cs.logger, "info") as mock_info:
            cs._log("all good", "OK")
            mock_info.assert_called_once()

    def test_log_error(self):
        with patch.object(cs.logger, "error") as mock_err:
            cs._log("failure", "ERREUR")
            mock_err.assert_called_once()

    def test_log_warning(self):
        with patch.object(cs.logger, "warning") as mock_warn:
            cs._log("caution", "WARN")
            mock_warn.assert_called_once()

    def test_log_unknown_level_defaults_info(self):
        with patch.object(cs.logger, "info") as mock_info:
            cs._log("test", "UNKNOWN")
            mock_info.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# LM Studio CLI Operations
# ═══════════════════════════════════════════════════════════════════════════

class TestLmsServerStatus:
    """Tests for _lms_server_status."""

    def test_server_running(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="Server is running on port 1234", stderr="")
        assert cs._lms_server_status() is True

    def test_server_not_running(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="Server is not running", stderr="")
        assert cs._lms_server_status() is False

    def test_server_status_exception(self, mock_subprocess):
        mock_subprocess.side_effect = OSError("No such file")
        assert cs._lms_server_status() is False

    def test_server_timeout(self, mock_subprocess):
        import subprocess as sp
        mock_subprocess.side_effect = sp.TimeoutExpired(cmd="lms", timeout=10)
        assert cs._lms_server_status() is False


class TestLmsServerStart:
    """Tests for _lms_server_start."""

    def test_start_success(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="success", stderr="")
        assert cs._lms_server_start() is True

    def test_already_running(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="already running", stderr="")
        assert cs._lms_server_start() is True

    def test_start_failure(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="error starting server", stderr="")
        assert cs._lms_server_start() is False

    def test_start_exception(self, mock_subprocess):
        mock_subprocess.side_effect = OSError("lms not found")
        assert cs._lms_server_start() is False


class TestLmsPs:
    """Tests for _lms_ps and _lms_ps_ids."""

    def test_parse_models(self, mock_subprocess):
        output = (
            "ID                          SIZE    CONTEXT  STATUS\n"
            "qwen/qwen3-8b              4.5GB   8192     IDLE\n"
            "nvidia/nemotron-3-nano     2.0GB   4096     RUNNING\n"
        )
        mock_subprocess.return_value = MagicMock(stdout=output, stderr="")
        models = cs._lms_ps()
        assert len(models) == 2
        assert models[0]["id"] == "qwen/qwen3-8b"
        assert models[0]["size"] == "4.5GB"
        assert models[0]["context"] == "8192"
        assert models[0]["status"] == "IDLE"

    def test_parse_empty_output(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="ID\n", stderr="")
        assert cs._lms_ps() == []

    def test_parse_exception(self, mock_subprocess):
        mock_subprocess.side_effect = OSError("fail")
        assert cs._lms_ps() == []

    def test_ps_ids(self, mock_subprocess):
        output = (
            "ID\n"
            "qwen/qwen3-8b 4.5GB 8192 IDLE\n"
            "other/model 2GB 4096 RUNNING\n"
        )
        mock_subprocess.return_value = MagicMock(stdout=output, stderr="")
        ids = cs._lms_ps_ids()
        assert ids == ["qwen/qwen3-8b", "other/model"]


class TestLmsUnload:
    """Tests for _lms_unload."""

    def test_unload_success(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="Model unloaded successfully", stderr="")
        assert cs._lms_unload("some/model") is True

    def test_unload_not_loaded(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="Model is not loaded", stderr="")
        assert cs._lms_unload("some/model") is True

    def test_unload_failure(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="error", stderr="")
        assert cs._lms_unload("some/model") is False

    def test_unload_exception(self, mock_subprocess):
        mock_subprocess.side_effect = OSError("fail")
        assert cs._lms_unload("some/model") is False


class TestLmsLoad:
    """Tests for _lms_load."""

    def test_load_success(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="Model loaded successfully", stderr="")
        assert cs._lms_load("qwen/qwen3-8b", gpu="max", context=8192, parallel=4) is True

    def test_load_already_loaded(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="Model already loaded", stderr="")
        assert cs._lms_load("qwen/qwen3-8b") is True

    def test_load_failure(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="error loading", stderr="")
        assert cs._lms_load("qwen/qwen3-8b") is False

    def test_load_timeout(self, mock_subprocess):
        import subprocess as sp
        mock_subprocess.side_effect = sp.TimeoutExpired(cmd="lms", timeout=180)
        assert cs._lms_load("qwen/qwen3-8b") is False

    def test_load_os_error(self, mock_subprocess):
        mock_subprocess.side_effect = OSError("binary not found")
        assert cs._lms_load("qwen/qwen3-8b") is False


# ═══════════════════════════════════════════════════════════════════════════
# Inference Warmup & Benchmarking
# ═══════════════════════════════════════════════════════════════════════════

class TestWarmupModel:
    """Tests for _warmup_model (async)."""

    @pytest.mark.asyncio
    async def test_warmup_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "output": [{"content": "OK"}],
            "stats": {"total_output_tokens": 2},
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await cs._warmup_model("http://127.0.0.1:1234", "qwen/qwen3-8b")

        assert result["ok"] is True
        assert result["latency_ms"] >= 0
        assert result["tokens_per_sec"] > 0

    @pytest.mark.asyncio
    async def test_warmup_http_error(self):
        import httpx
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await cs._warmup_model("http://127.0.0.1:1234", "qwen/qwen3-8b")

        assert result["ok"] is False
        assert result["latency_ms"] == -1
        assert "error" in result

    @pytest.mark.asyncio
    async def test_warmup_with_headers(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"stats": {"total_output_tokens": 1}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await cs._warmup_model(
                "http://127.0.0.1:1234", "model",
                headers={"Authorization": "Bearer test"},
            )

        assert result["ok"] is True
        # Verify headers were passed
        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs.get("headers") == {"Authorization": "Bearer test"} or \
               call_kwargs[1].get("headers") == {"Authorization": "Bearer test"}


class TestWarmupOllama:
    """Tests for _warmup_ollama (async)."""

    @pytest.mark.asyncio
    async def test_warmup_ollama_success(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"message": {"content": "OK"}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await cs._warmup_ollama("http://127.0.0.1:11434", "qwen3:1.7b")

        assert result["ok"] is True
        assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_warmup_ollama_failure(self):
        import httpx
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await cs._warmup_ollama("http://127.0.0.1:11434", "qwen3:1.7b")

        assert result["ok"] is False
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# GPU Monitoring
# ═══════════════════════════════════════════════════════════════════════════

class TestGetGpuStats:
    """Tests for _get_gpu_stats."""

    def test_parse_nvidia_smi_output(self, mock_subprocess):
        nvidia_output = (
            "0, NVIDIA GeForce RTX 2060, 4500, 6144, 45, 52\n"
            "1, NVIDIA GeForce GTX 1660S, 3000, 6144, 30, 48\n"
        )
        mock_subprocess.return_value = MagicMock(stdout=nvidia_output, stderr="")
        gpus = cs._get_gpu_stats()

        assert len(gpus) == 2
        assert gpus[0]["index"] == 0
        assert gpus[0]["name"] == "NVIDIA GeForce RTX 2060"
        assert gpus[0]["vram_used_mb"] == 4500
        assert gpus[0]["vram_total_mb"] == 6144
        assert gpus[0]["gpu_util"] == 45
        assert gpus[0]["temp_c"] == 52
        assert gpus[0]["vram_free_mb"] == 6144 - 4500
        assert gpus[0]["vram_pct"] == round(4500 / 6144 * 100, 1)

    def test_nvidia_smi_failure(self, mock_subprocess):
        mock_subprocess.side_effect = OSError("nvidia-smi not found")
        assert cs._get_gpu_stats() == []

    def test_nvidia_smi_empty_output(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(stdout="", stderr="")
        assert cs._get_gpu_stats() == []


class TestCheckThermalStatus:
    """Tests for check_thermal_status."""

    def test_normal_temps(self, mock_subprocess):
        nvidia_output = "0, RTX 2060, 4000, 6144, 40, 55\n"
        mock_subprocess.return_value = MagicMock(stdout=nvidia_output, stderr="")

        with patch("src.cluster_startup.config") as cfg:
            cfg.gpu_thermal_warning = 75
            cfg.gpu_thermal_critical = 85

            result = cs.check_thermal_status()
            assert result["ok"] is True
            assert result["status"] == "normal"
            assert result["max_temp"] == 55
            assert result["hot_gpus"] == []

    def test_warning_temps(self, mock_subprocess):
        nvidia_output = "0, RTX 2060, 4000, 6144, 80, 78\n"
        mock_subprocess.return_value = MagicMock(stdout=nvidia_output, stderr="")

        with patch("src.cluster_startup.config") as cfg:
            cfg.gpu_thermal_warning = 75
            cfg.gpu_thermal_critical = 85

            result = cs.check_thermal_status()
            assert result["ok"] is True
            assert result["status"] == "warning"
            assert len(result["hot_gpus"]) == 1

    def test_critical_temps(self, mock_subprocess):
        nvidia_output = "0, RTX 2060, 5000, 6144, 95, 90\n"
        mock_subprocess.return_value = MagicMock(stdout=nvidia_output, stderr="")

        with patch("src.cluster_startup.config") as cfg:
            cfg.gpu_thermal_warning = 75
            cfg.gpu_thermal_critical = 85

            result = cs.check_thermal_status()
            assert result["ok"] is False
            assert result["status"] == "critical"
            assert result["recommendation"] != ""

    def test_no_gpus_returns_unknown(self, mock_subprocess):
        mock_subprocess.side_effect = OSError("no nvidia-smi")

        result = cs.check_thermal_status()
        assert result["status"] == "unknown"
        assert result["ok"] is True

    def test_cache_ttl(self, mock_subprocess):
        """Thermal cache should return cached results within TTL."""
        nvidia_output = "0, RTX 2060, 4000, 6144, 40, 55\n"
        mock_subprocess.return_value = MagicMock(stdout=nvidia_output, stderr="")

        with patch("src.cluster_startup.config") as cfg:
            cfg.gpu_thermal_warning = 75
            cfg.gpu_thermal_critical = 85

            result1 = cs.check_thermal_status()
            # Change the subprocess output — should still get cached result
            mock_subprocess.return_value = MagicMock(stdout="0, RTX 2060, 5000, 6144, 95, 90\n", stderr="")
            result2 = cs.check_thermal_status()

            # Both should be identical (cached)
            assert result1 == result2
            assert result2["status"] == "normal"

    def test_cache_expired(self, mock_subprocess):
        """After TTL expires, fresh GPU data should be fetched."""
        nvidia_output = "0, RTX 2060, 4000, 6144, 40, 55\n"
        mock_subprocess.return_value = MagicMock(stdout=nvidia_output, stderr="")

        with patch("src.cluster_startup.config") as cfg:
            cfg.gpu_thermal_warning = 75
            cfg.gpu_thermal_critical = 85

            result1 = cs.check_thermal_status()
            assert result1["status"] == "normal"

            # Force cache expiry
            cs._thermal_cache_ts = time.monotonic() - cs._THERMAL_TTL - 1

            # Now return critical temps
            mock_subprocess.return_value = MagicMock(stdout="0, RTX 2060, 5000, 6144, 95, 90\n", stderr="")
            result2 = cs.check_thermal_status()
            assert result2["status"] == "critical"


# ═══════════════════════════════════════════════════════════════════════════
# Ollama Checks
# ═══════════════════════════════════════════════════════════════════════════

class TestCheckOllama:
    """Tests for _check_ollama (async)."""

    @pytest.mark.asyncio
    async def test_ollama_online(self, mock_config):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "qwen3:1.7b"},
                {"name": "minimax-m2.5:cloud"},
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await cs._check_ollama()

        assert result["ok"] is True
        assert result["count"] == 2
        assert result["has_correction_model"] is True

    @pytest.mark.asyncio
    async def test_ollama_no_correction_model(self, mock_config):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "models": [{"name": "mistral:7b"}]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await cs._check_ollama()

        assert result["ok"] is True
        assert result["has_correction_model"] is False

    @pytest.mark.asyncio
    async def test_ollama_offline(self, mock_config):
        import httpx
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await cs._check_ollama()

        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_ollama_not_configured(self):
        with patch("src.cluster_startup.config") as cfg:
            cfg.get_ollama_node.return_value = None

            result = await cs._check_ollama()

        assert result["ok"] is False
        assert "non configure" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════
# M2 Remote Checks
# ═══════════════════════════════════════════════════════════════════════════

class TestCheckM2:
    """Tests for _check_m2 (async)."""

    @pytest.mark.asyncio
    async def test_m2_online_with_coder(self, mock_config):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"key": "deepseek-r1-0528-qwen3-8b", "loaded_instances": 1},
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await cs._check_m2()

        assert result["ok"] is True
        assert result["has_coder"] is True
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_m2_not_configured(self):
        with patch("src.cluster_startup.config") as cfg:
            cfg.get_node.return_value = None

            result = await cs._check_m2()

        assert result["ok"] is False
        assert "non configure" in result["error"]

    @pytest.mark.asyncio
    async def test_m2_offline(self, mock_config):
        import httpx
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await cs._check_m2()

        assert result["ok"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Main Startup Sequence
# ═══════════════════════════════════════════════════════════════════════════

class TestEnsureClusterReady:
    """Tests for ensure_cluster_ready (async)."""

    @pytest.mark.asyncio
    async def test_full_startup_optimal(self, mock_config):
        """Full startup with everything online -> OPTIMAL."""
        with (
            patch("src.cluster_startup._lms_server_status", return_value=True),
            patch("src.cluster_startup._lms_ps_ids", return_value=["qwen/qwen3-8b"]),
            patch("src.cluster_startup._lms_ps", return_value=[{"id": "qwen/qwen3-8b", "status": "IDLE"}]),
            patch("src.cluster_startup._lms_load", return_value=True),
            patch("src.cluster_startup._warmup_model", new_callable=AsyncMock, return_value={"ok": True, "latency_ms": 50, "tokens_per_sec": 65.0}),
            patch("src.cluster_startup._check_m2", new_callable=AsyncMock, return_value={"ok": True, "count": 1, "has_coder": True, "models": ["deepseek"]}),
            patch("src.cluster_startup._check_ollama", new_callable=AsyncMock, return_value={"ok": True, "count": 2, "has_correction_model": True, "models": ["qwen3:1.7b"]}),
            patch("src.cluster_startup._warmup_ollama", new_callable=AsyncMock, return_value={"ok": True, "latency_ms": 100}),
            patch("src.cluster_startup._get_gpu_stats", return_value=[]),
            patch("src.cluster_startup.check_thermal_status", return_value={"ok": True, "status": "unknown", "max_temp": -1, "hot_gpus": [], "recommendation": ""}),
        ):
            report = await cs.ensure_cluster_ready(warmup=True, benchmark=True, verbose=False)

        assert report["status"] == "OPTIMAL"
        assert report["server_start"] == "deja actif"

    @pytest.mark.asyncio
    async def test_startup_server_needs_start(self, mock_config):
        """Server was stopped, gets auto-started."""
        with (
            patch("src.cluster_startup._lms_server_status", return_value=False),
            patch("src.cluster_startup._lms_server_start", return_value=True),
            patch("src.cluster_startup._lms_ps_ids", return_value=["qwen/qwen3-8b"]),
            patch("src.cluster_startup._lms_ps", return_value=[{"id": "qwen/qwen3-8b"}]),
            patch("src.cluster_startup._lms_load", return_value=True),
            patch("src.cluster_startup._warmup_model", new_callable=AsyncMock, return_value={"ok": True, "latency_ms": 50, "tokens_per_sec": 65.0}),
            patch("src.cluster_startup._check_m2", new_callable=AsyncMock, return_value={"ok": True, "count": 1, "has_coder": True, "models": []}),
            patch("src.cluster_startup._check_ollama", new_callable=AsyncMock, return_value={"ok": True, "count": 1, "has_correction_model": False, "models": []}),
            patch("src.cluster_startup._get_gpu_stats", return_value=[]),
            patch("src.cluster_startup.check_thermal_status", return_value={"ok": True, "status": "unknown", "max_temp": -1, "hot_gpus": [], "recommendation": ""}),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            report = await cs.ensure_cluster_ready(warmup=True, verbose=False)

        assert report["server_start"] == "OK"

    @pytest.mark.asyncio
    async def test_startup_server_start_fails(self, mock_config):
        """Server fails to start -> fatal error."""
        with (
            patch("src.cluster_startup._lms_server_status", return_value=False),
            patch("src.cluster_startup._lms_server_start", return_value=False),
        ):
            report = await cs.ensure_cluster_ready(warmup=False, verbose=False)

        assert report.get("fatal") == "server_start_failed"

    @pytest.mark.asyncio
    async def test_startup_unloads_blacklisted(self, mock_config):
        """Blacklisted models get unloaded."""
        with (
            patch("src.cluster_startup._lms_server_status", return_value=True),
            patch("src.cluster_startup._lms_ps_ids", side_effect=[
                ["qwen/qwen3-8b", "nvidia/nemotron-3-nano"],  # initial
                ["qwen/qwen3-8b"],  # after unload
            ]),
            patch("src.cluster_startup._lms_unload", return_value=True) as mock_unload,
            patch("src.cluster_startup._lms_ps", return_value=[{"id": "qwen/qwen3-8b"}]),
            patch("src.cluster_startup._warmup_model", new_callable=AsyncMock, return_value={"ok": True, "latency_ms": 50, "tokens_per_sec": 65.0}),
            patch("src.cluster_startup._check_m2", new_callable=AsyncMock, return_value={"ok": True, "count": 1, "has_coder": True, "models": []}),
            patch("src.cluster_startup._check_ollama", new_callable=AsyncMock, return_value={"ok": True, "count": 1, "has_correction_model": False, "models": []}),
            patch("src.cluster_startup._get_gpu_stats", return_value=[]),
            patch("src.cluster_startup.check_thermal_status", return_value={"ok": True, "status": "unknown", "max_temp": -1, "hot_gpus": [], "recommendation": ""}),
        ):
            report = await cs.ensure_cluster_ready(warmup=True, verbose=False)

        assert "nvidia/nemotron-3-nano" in report["m1_unloaded"]
        mock_unload.assert_called_once_with("nvidia/nemotron-3-nano")

    @pytest.mark.asyncio
    async def test_startup_partiel_m2_offline(self, mock_config):
        """M2 offline -> PARTIEL status."""
        with (
            patch("src.cluster_startup._lms_server_status", return_value=True),
            patch("src.cluster_startup._lms_ps_ids", return_value=["qwen/qwen3-8b"]),
            patch("src.cluster_startup._lms_ps", return_value=[{"id": "qwen/qwen3-8b"}]),
            patch("src.cluster_startup._warmup_model", new_callable=AsyncMock, return_value={"ok": True, "latency_ms": 50, "tokens_per_sec": 65.0}),
            patch("src.cluster_startup._check_m2", new_callable=AsyncMock, return_value={"ok": False, "error": "connection refused"}),
            patch("src.cluster_startup._check_ollama", new_callable=AsyncMock, return_value={"ok": True, "count": 1, "has_correction_model": False, "models": []}),
            patch("src.cluster_startup._get_gpu_stats", return_value=[]),
            patch("src.cluster_startup.check_thermal_status", return_value={"ok": True, "status": "unknown", "max_temp": -1, "hot_gpus": [], "recommendation": ""}),
        ):
            report = await cs.ensure_cluster_ready(warmup=True, verbose=False)

        assert report["status"] == "PARTIEL"

    @pytest.mark.asyncio
    async def test_startup_no_warmup(self, mock_config):
        """With warmup=False, no warmup calls are made."""
        with (
            patch("src.cluster_startup._lms_server_status", return_value=True),
            patch("src.cluster_startup._lms_ps_ids", return_value=["qwen/qwen3-8b"]),
            patch("src.cluster_startup._lms_ps", return_value=[{"id": "qwen/qwen3-8b"}]),
            patch("src.cluster_startup._warmup_model", new_callable=AsyncMock) as mock_warmup,
            patch("src.cluster_startup._check_m2", new_callable=AsyncMock, return_value={"ok": False, "error": "offline"}),
            patch("src.cluster_startup._check_ollama", new_callable=AsyncMock, return_value={"ok": False, "error": "offline"}),
            patch("src.cluster_startup._get_gpu_stats", return_value=[]),
            patch("src.cluster_startup.check_thermal_status", return_value={"ok": True, "status": "unknown", "max_temp": -1, "hot_gpus": [], "recommendation": ""}),
        ):
            report = await cs.ensure_cluster_ready(warmup=False, verbose=False)

        mock_warmup.assert_not_called()
        assert "warmup_qwen/qwen3-8b" not in report


# ═══════════════════════════════════════════════════════════════════════════
# On-Demand Model Loading
# ═══════════════════════════════════════════════════════════════════════════

class TestLoadModelOnDemand:
    """Tests for load_model_on_demand (async)."""

    @pytest.mark.asyncio
    async def test_model_not_available(self):
        result = await cs.load_model_on_demand("unknown/model")
        assert result["ok"] is False
        assert "non disponible" in result["error"]

    @pytest.mark.asyncio
    async def test_model_already_loaded(self):
        with patch("src.cluster_startup._lms_ps_ids", return_value=["qwen/qwen3-coder-30b"]):
            result = await cs.load_model_on_demand("qwen/qwen3-coder-30b")
        assert result["ok"] is True
        assert result["status"] == "deja charge"

    @pytest.mark.asyncio
    async def test_load_with_warmup(self, mock_config):
        with (
            patch("src.cluster_startup._lms_ps_ids", return_value=[]),
            patch("src.cluster_startup._lms_load", return_value=True),
            patch("src.cluster_startup._warmup_model", new_callable=AsyncMock, return_value={"ok": True, "latency_ms": 200, "tokens_per_sec": 30.0}),
        ):
            result = await cs.load_model_on_demand("qwen/qwen3-coder-30b")

        assert result["ok"] is True
        assert result["status"] == "charge + warmup"
        assert "bench" in result

    @pytest.mark.asyncio
    async def test_load_failure(self, mock_config):
        with (
            patch("src.cluster_startup._lms_ps_ids", return_value=[]),
            patch("src.cluster_startup._lms_load", return_value=False),
        ):
            result = await cs.load_model_on_demand("qwen/qwen3-coder-30b")

        assert result["ok"] is False
        assert result["status"] == "echec"

    @pytest.mark.asyncio
    async def test_unload_others_first(self, mock_config):
        with (
            patch("src.cluster_startup._lms_ps_ids", return_value=["qwen/qwen3-8b"]),
            patch("src.cluster_startup._lms_unload", return_value=True) as mock_unload,
            patch("src.cluster_startup._lms_load", return_value=True),
            patch("src.cluster_startup._warmup_model", new_callable=AsyncMock, return_value={"ok": True, "latency_ms": 100, "tokens_per_sec": 20.0}),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await cs.load_model_on_demand(
                "qwen/qwen3-coder-30b", unload_others=True,
            )

        mock_unload.assert_called_once_with("qwen/qwen3-8b")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_required_model_accepted(self, mock_config):
        """A model in M1_REQUIRED should also be accepted for on-demand loading."""
        with (
            patch("src.cluster_startup._lms_ps_ids", return_value=["qwen/qwen3-8b"]),
        ):
            result = await cs.load_model_on_demand("qwen/qwen3-8b")
        assert result["ok"] is True
        assert result["status"] == "deja charge"


class TestSwitchModes:
    """Tests for switch_to_coder_mode and switch_to_dev_mode."""

    @pytest.mark.asyncio
    async def test_switch_to_coder_mode(self, mock_config):
        with (
            patch("src.cluster_startup._lms_ps_ids", return_value=["qwen/qwen3-8b"]),
            patch("src.cluster_startup._lms_load", return_value=True),
            patch("src.cluster_startup._warmup_model", new_callable=AsyncMock, return_value={"ok": True, "latency_ms": 200, "tokens_per_sec": 30.0}),
        ):
            result = await cs.switch_to_coder_mode()
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_switch_to_dev_mode(self, mock_config):
        with (
            patch("src.cluster_startup._lms_ps_ids", return_value=["qwen/qwen3-8b"]),
            patch("src.cluster_startup._lms_load", return_value=True),
            patch("src.cluster_startup._warmup_model", new_callable=AsyncMock, return_value={"ok": True, "latency_ms": 200, "tokens_per_sec": 30.0}),
        ):
            result = await cs.switch_to_dev_mode()
        assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Quick Health Check
# ═══════════════════════════════════════════════════════════════════════════

class TestQuickHealthCheck:
    """Tests for quick_health_check (async)."""

    @pytest.mark.asyncio
    async def test_all_online(self, mock_config):
        m1_resp = MagicMock()
        m1_resp.raise_for_status = MagicMock()
        m1_resp.json.return_value = {
            "models": [{"key": "qwen3-8b-instruct", "loaded_instances": 1}]
        }
        m2_resp = MagicMock()
        m2_resp.raise_for_status = MagicMock()
        m2_resp.json.return_value = {"models": []}
        ol_resp = MagicMock()
        ol_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        # Return different responses based on URL
        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "1234" in url and call_count == 1:
                return m1_resp
            elif "1234" in url:
                return m2_resp
            else:
                return ol_resp

        mock_client.get = mock_get

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            status = await cs.quick_health_check()

        assert "m1" in status
        assert "OK" in status["m1"]

    @pytest.mark.asyncio
    async def test_all_offline(self, mock_config):
        import httpx
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("src.cluster_startup.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            status = await cs.quick_health_check()

        assert status.get("m1") == "OFFLINE"
        assert status.get("m2") == "OFFLINE"


# ═══════════════════════════════════════════════════════════════════════════
# Startup Report
# ═══════════════════════════════════════════════════════════════════════════

class TestPrintStartupReport:
    """Tests for print_startup_report."""

    def test_basic_report(self):
        report = {
            "timestamp": "12:00:00",
            "server_start": "OK",
            "m1_initial": ["qwen/qwen3-8b"],
            "m1_final": [{"id": "qwen/qwen3-8b"}],
            "m2": {"ok": True, "count": 1},
            "ollama": {"ok": False, "error": "offline"},
            "status": "PARTIEL",
        }
        with patch.object(cs.logger, "info") as mock_info:
            cs.print_startup_report(report)
            assert mock_info.call_count >= 4  # header + lines + footer

    def test_report_skips_internal_keys(self):
        report = {
            "timestamp": "12:00:00",
            "gpus": [],
            "m1_initial": [],
            "m1_final": [],
            "custom_key": "test_value",
        }
        with patch.object(cs.logger, "info") as mock_info:
            cs.print_startup_report(report)
            # The skipped keys (timestamp, gpus, m1_initial, m1_final) should not appear
            logged = " ".join(str(c) for c in mock_info.call_args_list)
            assert "custom_key" in logged or "Custom Key" in logged


# ═══════════════════════════════════════════════════════════════════════════
# Startup Logging (v2)
# ═══════════════════════════════════════════════════════════════════════════

class TestStartupLogging:
    """Tests for log_startup_event and get_startup_history."""

    def test_log_event(self, tmp_path):
        log_file = tmp_path / "startup_log.json"
        with patch.object(cs, "_STARTUP_LOG_FILE", log_file):
            cs.log_startup_event("test_event", {"key": "value"})

        entries = json.loads(log_file.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["event"] == "test_event"
        assert entries[0]["details"]["key"] == "value"
        assert "timestamp" in entries[0]

    def test_log_event_appends(self, tmp_path):
        log_file = tmp_path / "startup_log.json"
        with patch.object(cs, "_STARTUP_LOG_FILE", log_file):
            cs.log_startup_event("event1")
            cs.log_startup_event("event2")

        entries = json.loads(log_file.read_text(encoding="utf-8"))
        assert len(entries) == 2

    def test_log_event_truncates_at_200(self, tmp_path):
        log_file = tmp_path / "startup_log.json"
        initial = [{"timestamp": i, "event": f"e{i}", "details": {}} for i in range(199)]
        log_file.write_text(json.dumps(initial), encoding="utf-8")

        with patch.object(cs, "_STARTUP_LOG_FILE", log_file):
            cs.log_startup_event("new_event")

        entries = json.loads(log_file.read_text(encoding="utf-8"))
        assert len(entries) == 200
        assert entries[-1]["event"] == "new_event"

    def test_log_event_handles_corrupt_file(self, tmp_path):
        log_file = tmp_path / "startup_log.json"
        log_file.write_text("NOT JSON!!!", encoding="utf-8")

        with patch.object(cs, "_STARTUP_LOG_FILE", log_file):
            cs.log_startup_event("recovery_event")

        entries = json.loads(log_file.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["event"] == "recovery_event"

    def test_get_history(self, tmp_path):
        log_file = tmp_path / "startup_log.json"
        entries = [{"timestamp": i, "event": f"e{i}", "details": {}} for i in range(30)]
        log_file.write_text(json.dumps(entries), encoding="utf-8")

        with patch.object(cs, "_STARTUP_LOG_FILE", log_file):
            result = cs.get_startup_history(limit=10)

        assert len(result) == 10
        assert result[0]["event"] == "e20"

    def test_get_history_empty(self, tmp_path):
        log_file = tmp_path / "startup_log.json"
        with patch.object(cs, "_STARTUP_LOG_FILE", log_file):
            result = cs.get_startup_history()
        assert result == []

    def test_get_history_corrupt_file(self, tmp_path):
        log_file = tmp_path / "startup_log.json"
        log_file.write_text("CORRUPT", encoding="utf-8")
        with patch.object(cs, "_STARTUP_LOG_FILE", log_file):
            result = cs.get_startup_history()
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════
# Service Discovery
# ═══════════════════════════════════════════════════════════════════════════

class TestDiscoverServices:
    """Tests for discover_services (async)."""

    @pytest.mark.asyncio
    async def test_discover_all_online(self, mock_config, tmp_path):
        # Also mock M3 to None in config
        mock_response_lm = MagicMock()
        mock_response_lm.status_code = 200
        mock_response_lm.json.return_value = {
            "data": [
                {"id": "qwen/qwen3-8b", "loaded_instances": 1},
            ]
        }

        mock_response_ollama = MagicMock()
        mock_response_ollama.status_code = 200
        mock_response_ollama.json.return_value = {
            "models": [{"name": "qwen3:1.7b"}]
        }

        mock_response_health = MagicMock()
        mock_response_health.status_code = 200

        mock_client = AsyncMock()

        async def mock_get(url, **kwargs):
            if "api/v1/models" in url:
                return mock_response_lm
            elif "api/tags" in url:
                return mock_response_ollama
            else:
                return mock_response_health

        mock_client.get = mock_get

        with (
            patch("src.cluster_startup.httpx.AsyncClient") as MockClient,
            patch.object(cs, "_STARTUP_LOG_FILE", tmp_path / "log.json"),
        ):
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            services = await cs.discover_services()

        assert "M1" in services
        assert services["M1"]["status"] == "online"
        assert "OL1" in services

    @pytest.mark.asyncio
    async def test_discover_all_offline(self, mock_config, tmp_path):
        import httpx
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with (
            patch("src.cluster_startup.httpx.AsyncClient") as MockClient,
            patch.object(cs, "_STARTUP_LOG_FILE", tmp_path / "log.json"),
        ):
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            services = await cs.discover_services()

        # M1 and M2 should be offline
        assert services["M1"]["status"] == "offline"
        assert services["M2"]["status"] == "offline"


# ═══════════════════════════════════════════════════════════════════════════
# Version Checks
# ═══════════════════════════════════════════════════════════════════════════

class TestCheckVersions:
    """Tests for check_versions (async)."""

    @pytest.mark.asyncio
    async def test_versions_all_available(self, mock_config):
        ol_resp = MagicMock()
        ol_resp.status_code = 200
        ol_resp.json.return_value = {"version": "0.17.4"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=ol_resp)

        lms_result = MagicMock()
        lms_result.returncode = 0
        lms_result.stdout = "0.4.5"
        lms_result.stderr = ""

        with (
            patch("src.cluster_startup.httpx.AsyncClient") as MockClient,
            patch("src.cluster_startup.subprocess.run", return_value=lms_result),
            patch("src.config.JARVIS_VERSION", "10.6"),
        ):
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            versions = await cs.check_versions()

        assert versions["jarvis"] == "10.6"
        assert versions["ollama"] == "0.17.4"
        assert versions["lm_studio"] == "0.4.5"

    @pytest.mark.asyncio
    async def test_versions_offline(self, mock_config):
        import httpx
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("offline"))

        with (
            patch("src.cluster_startup.httpx.AsyncClient") as MockClient,
            patch("src.cluster_startup.subprocess.run", side_effect=FileNotFoundError("lms not found")),
            patch("src.config.JARVIS_VERSION", "10.6"),
        ):
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            versions = await cs.check_versions()

        assert versions["jarvis"] == "10.6"
        assert versions["ollama"] == "offline"
        assert versions["lm_studio"] == "?"


# ═══════════════════════════════════════════════════════════════════════════
# Constants & Module-level
# ═══════════════════════════════════════════════════════════════════════════

class TestModuleConstants:
    """Tests for module-level constants and configuration."""

    def test_m1_required_has_qwen3_8b(self):
        assert "qwen/qwen3-8b" in cs.M1_REQUIRED
        opts = cs.M1_REQUIRED["qwen/qwen3-8b"]
        assert opts["gpu"] == "max"
        assert opts["context"] == 8192
        assert opts["parallel"] == 4

    def test_m1_blacklist(self):
        assert "nvidia/nemotron-3-nano" in cs.M1_BLACKLIST
        assert "zai-org/glm-4.7-flash" in cs.M1_BLACKLIST

    def test_m1_available_models(self):
        assert "qwen/qwen3-30b-a3b-2507" in cs.M1_AVAILABLE
        assert "qwen/qwen3-coder-30b" in cs.M1_AVAILABLE

    def test_warmup_constants(self):
        assert cs.WARMUP_PROMPT == "Reponds OK."
        assert cs.WARMUP_MAX_TOKENS == 5

    def test_lms_cli_path(self):
        assert cs.LMS_CLI.endswith("lms.exe")
