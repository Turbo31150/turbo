"""Tests for src/health_probe_registry.py -- Health Probe Registry.

Comprehensive test suite covering:
- Module import
- Probe registration (all 10 probes)
- Individual check functions (LM Studio, Ollama, GPU, DB, event bus, etc.)
- Result formatting and status logic
- Error/fallback paths

All external dependencies are mocked: no network, no socket, no aiohttp, no subprocess.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Test 1 -- Module imports without error
# ---------------------------------------------------------------------------
class TestImports:
    def test_module_imports(self):
        """health_probe_registry can be imported."""
        import src.health_probe_registry as mod
        assert hasattr(mod, "register_all_probes")

    def test_health_probe_imports(self):
        """health_probe module exposes HealthProbe, HealthStatus, CheckResult."""
        from src.health_probe import HealthProbe, HealthStatus, CheckResult, ProbeConfig
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"


# ---------------------------------------------------------------------------
# Test 2 -- register_all_probes wires every probe
# ---------------------------------------------------------------------------
class TestRegisterAllProbes:
    def test_registers_all_10_probes(self):
        """register_all_probes registers exactly 10 probes and returns dict."""
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()

        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            result = register_all_probes()
        finally:
            hp_mod.health_probe = original_hp

        assert isinstance(result, dict)
        assert len(result) == 10
        expected_keys = {
            "lm_studio_m1", "ollama_local", "gpu_vram", "database",
            "event_bus", "autonomous_loop", "disk_space_f", "mcp_server",
            "cloudflare_tunnel", "trading_engine",
        }
        assert set(result.keys()) == expected_keys
        # All should be True (registered successfully)
        assert all(v is True for v in result.values())

    def test_probes_registered_in_health_probe_instance(self):
        """After register_all_probes, HealthProbe._probes has all 10 entries."""
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()

        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp

        probe_names = list(fake_probe._probes.keys())
        assert len(probe_names) == 10
        assert "lm_studio_m1" in probe_names
        assert "ollama_local" in probe_names

    def test_critical_vs_noncritical_flags(self):
        """Critical probes: m1, ollama, gpu, db, disk. Non-critical: rest."""
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()

        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp

        critical_names = {n for n, p in fake_probe._probes.items() if p.critical}
        noncritical_names = {n for n, p in fake_probe._probes.items() if not p.critical}

        assert critical_names == {"lm_studio_m1", "ollama_local", "gpu_vram", "database", "disk_space_f"}
        assert noncritical_names == {"event_bus", "autonomous_loop", "mcp_server", "cloudflare_tunnel", "trading_engine"}


# ---------------------------------------------------------------------------
# Test 3 -- Individual check functions via run_check
# ---------------------------------------------------------------------------
class TestCheckLmStudioM1:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_lm_studio_m1_success(self):
        """LM Studio M1 returns HEALTHY when http 200."""
        fake_probe = self._setup_probe()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fake_probe.run_check("lm_studio_m1")

        assert result is not None
        assert result.status.value == "healthy"
        assert result.message == "OK"

    def test_lm_studio_m1_failure(self):
        """LM Studio M1 returns DEGRADED when unreachable (returns string)."""
        fake_probe = self._setup_probe()

        with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("Connection refused")):
            result = fake_probe.run_check("lm_studio_m1")

        assert result is not None
        # Returns a string -> DEGRADED
        assert result.status.value == "degraded"
        assert "M1 unreachable" in result.message


class TestCheckOllama:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_ollama_success(self):
        """Ollama check returns HEALTHY when http 200."""
        fake_probe = self._setup_probe()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fake_probe.run_check("ollama_local")

        assert result.status.value == "healthy"

    def test_ollama_failure(self):
        """Ollama check returns DEGRADED when unreachable."""
        fake_probe = self._setup_probe()

        with patch("urllib.request.urlopen", side_effect=OSError("Network unreachable")):
            result = fake_probe.run_check("ollama_local")

        assert result.status.value == "degraded"
        assert "Ollama unreachable" in result.message


class TestCheckGpuVram:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_gpu_healthy(self):
        """GPU check returns HEALTHY for normal temps and VRAM usage."""
        fake_probe = self._setup_probe()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "4096, 8192, 55\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = fake_probe.run_check("gpu_vram")

        assert result.status.value == "healthy"

    def test_gpu_high_temp(self):
        """GPU check returns DEGRADED (string) when temperature > 90C."""
        fake_probe = self._setup_probe()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "4096, 8192, 95\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = fake_probe.run_check("gpu_vram")

        assert result.status.value == "degraded"
        assert "CRITICAL" in result.message
        assert "95" in result.message

    def test_gpu_high_vram(self):
        """GPU check returns DEGRADED when VRAM > 95%."""
        fake_probe = self._setup_probe()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "7900, 8192, 60\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = fake_probe.run_check("gpu_vram")

        assert result.status.value == "degraded"
        assert "VRAM CRITICAL" in result.message

    def test_gpu_nvidia_smi_fails(self):
        """GPU check returns DEGRADED when nvidia-smi returns non-zero."""
        fake_probe = self._setup_probe()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "nvidia-smi not found"

        with patch("subprocess.run", return_value=mock_result):
            result = fake_probe.run_check("gpu_vram")

        assert result.status.value == "degraded"
        assert "nvidia-smi failed" in result.message


class TestCheckDatabase:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_database_healthy(self):
        """Database check HEALTHY when PRAGMA integrity_check returns 'ok'."""
        fake_probe = self._setup_probe()
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = ("ok",)

        with patch.dict("sys.modules", {"src.database": MagicMock(db=mock_db)}):
            result = fake_probe.run_check("database")

        assert result.status.value == "healthy"

    def test_database_integrity_issue(self):
        """Database check DEGRADED when integrity_check returns something else."""
        fake_probe = self._setup_probe()
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = ("corruption found",)

        with patch.dict("sys.modules", {"src.database": MagicMock(db=mock_db)}):
            result = fake_probe.run_check("database")

        assert result.status.value == "degraded"
        assert "integrity issue" in result.message


class TestCheckEventBus:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_event_bus_with_subscribers(self):
        """Event bus returns HEALTHY when subscribers > 0."""
        fake_probe = self._setup_probe()
        mock_bus = MagicMock()
        mock_bus._subscriptions = {"event1": [MagicMock()], "event2": [MagicMock()]}

        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
            result = fake_probe.run_check("event_bus")

        assert result.status.value == "healthy"

    def test_event_bus_zero_subscribers(self):
        """Event bus returns DEGRADED when 0 subscribers."""
        fake_probe = self._setup_probe()
        mock_bus = MagicMock()
        mock_bus._subscriptions = {}

        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
            result = fake_probe.run_check("event_bus")

        assert result.status.value == "degraded"
        assert "0 subscribers" in result.message


class TestCheckAutonomousLoop:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_autonomous_loop_running(self):
        """Autonomous loop returns HEALTHY when running=True."""
        fake_probe = self._setup_probe()
        mock_loop = MagicMock()
        mock_loop.running = True

        with patch.dict("sys.modules", {"src.autonomous_loop": MagicMock(autonomous_loop=mock_loop)}):
            result = fake_probe.run_check("autonomous_loop")

        assert result.status.value == "healthy"

    def test_autonomous_loop_not_running(self):
        """Autonomous loop returns DEGRADED when not running."""
        fake_probe = self._setup_probe()
        mock_loop = MagicMock()
        mock_loop.running = False

        with patch.dict("sys.modules", {"src.autonomous_loop": MagicMock(autonomous_loop=mock_loop)}):
            result = fake_probe.run_check("autonomous_loop")

        assert result.status.value == "degraded"
        assert "NOT running" in result.message


class TestCheckDiskSpace:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_disk_healthy(self):
        """Disk check returns HEALTHY when free > 20GB."""
        fake_probe = self._setup_probe()
        # 100GB free out of 500GB total
        mock_usage = MagicMock()
        mock_usage.free = 100 * (1024**3)
        mock_usage.used = 400 * (1024**3)
        mock_usage.total = 500 * (1024**3)

        with patch("shutil.disk_usage", return_value=mock_usage):
            result = fake_probe.run_check("disk_space_f")

        assert result.status.value == "healthy"

    def test_disk_warning(self):
        """Disk check returns DEGRADED (WARNING) when 5 < free < 20 GB."""
        fake_probe = self._setup_probe()
        mock_usage = MagicMock()
        mock_usage.free = 10 * (1024**3)  # 10GB free
        mock_usage.used = 490 * (1024**3)
        mock_usage.total = 500 * (1024**3)

        with patch("shutil.disk_usage", return_value=mock_usage):
            result = fake_probe.run_check("disk_space_f")

        assert result.status.value == "degraded"
        assert "WARNING" in result.message

    def test_disk_critical(self):
        """Disk check returns DEGRADED (CRITICAL) when free < 5 GB."""
        fake_probe = self._setup_probe()
        mock_usage = MagicMock()
        mock_usage.free = 3 * (1024**3)  # 3GB free
        mock_usage.used = 497 * (1024**3)
        mock_usage.total = 500 * (1024**3)

        with patch("shutil.disk_usage", return_value=mock_usage):
            result = fake_probe.run_check("disk_space_f")

        assert result.status.value == "degraded"
        assert "CRITICAL" in result.message


class TestCheckMcpPort:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_mcp_port_open(self):
        """MCP server check returns HEALTHY when port 8901 is listening."""
        fake_probe = self._setup_probe()
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0

        with patch("socket.socket", return_value=mock_sock):
            result = fake_probe.run_check("mcp_server")

        assert result.status.value == "healthy"
        # Verify it connected to 127.0.0.1:8901
        mock_sock.connect_ex.assert_called_once_with(('127.0.0.1', 8901))

    def test_mcp_port_closed(self):
        """MCP server check returns DEGRADED when port 8901 not listening."""
        fake_probe = self._setup_probe()
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1  # Connection refused

        with patch("socket.socket", return_value=mock_sock):
            result = fake_probe.run_check("mcp_server")

        assert result.status.value == "degraded"
        assert "not listening" in result.message


class TestCheckCloudflare:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_tunnel_running(self):
        """Cloudflare tunnel returns HEALTHY when cloudflared.exe found."""
        fake_probe = self._setup_probe()
        mock_result = MagicMock()
        mock_result.stdout = "cloudflared.exe    1234 Console  1  12,345 K"

        with patch("subprocess.run", return_value=mock_result):
            result = fake_probe.run_check("cloudflare_tunnel")

        assert result.status.value == "healthy"

    def test_tunnel_not_running(self):
        """Cloudflare tunnel returns DEGRADED when not found."""
        fake_probe = self._setup_probe()
        mock_result = MagicMock()
        mock_result.stdout = "INFO: No tasks are running which match the specified criteria."

        with patch("subprocess.run", return_value=mock_result):
            result = fake_probe.run_check("cloudflare_tunnel")

        assert result.status.value == "degraded"
        assert "not running" in result.message


class TestCheckTrading:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_trading_connected(self):
        """Trading engine returns HEALTHY when connected=True."""
        fake_probe = self._setup_probe()
        mock_engine = MagicMock()
        mock_engine.status.return_value = {"connected": True}

        with patch.dict("sys.modules", {"src.trading_engine": MagicMock(trading_engine=mock_engine)}):
            result = fake_probe.run_check("trading_engine")

        assert result.status.value == "healthy"

    def test_trading_not_connected(self):
        """Trading engine returns DEGRADED when connected=False."""
        fake_probe = self._setup_probe()
        mock_engine = MagicMock()
        mock_engine.status.return_value = {"connected": False, "error": "API timeout"}

        with patch.dict("sys.modules", {"src.trading_engine": MagicMock(trading_engine=mock_engine)}):
            result = fake_probe.run_check("trading_engine")

        assert result.status.value == "degraded"
        assert "not connected" in result.message

    def test_trading_import_error_is_ok(self):
        """Trading engine returns HEALTHY on ImportError (module not loaded)."""
        fake_probe = self._setup_probe()

        # Remove the module from sys.modules to force ImportError
        with patch.dict("sys.modules", {"src.trading_engine": None}):
            # When a module is set to None in sys.modules, import raises ImportError
            result = fake_probe.run_check("trading_engine")

        assert result.status.value == "healthy"


# ---------------------------------------------------------------------------
# Test 4 -- Result formatting (CheckResult fields)
# ---------------------------------------------------------------------------
class TestResultFormatting:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_check_result_has_latency(self):
        """CheckResult includes latency_ms > 0."""
        fake_probe = self._setup_probe()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fake_probe.run_check("lm_studio_m1")

        assert result.latency_ms >= 0
        assert isinstance(result.latency_ms, float)

    def test_check_result_has_timestamp(self):
        """CheckResult includes a timestamp."""
        fake_probe = self._setup_probe()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fake_probe.run_check("ollama_local")

        assert result.timestamp > 0

    def test_check_result_stored_in_history(self):
        """After run_check, result appears in probe history."""
        fake_probe = self._setup_probe()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            fake_probe.run_check("lm_studio_m1")

        history = fake_probe.get_history("lm_studio_m1")
        assert len(history) == 1
        assert history[0]["status"] == "healthy"
        assert history[0]["name"] == "lm_studio_m1"

    def test_list_probes_format(self):
        """list_probes returns correctly formatted dicts."""
        fake_probe = self._setup_probe()
        probes = fake_probe.list_probes()
        assert len(probes) == 10
        for p in probes:
            assert "name" in p
            assert "critical" in p
            assert "timeout_s" in p
            assert "interval_s" in p
            assert "last_status" in p
            # Before any run, status is unknown
            assert p["last_status"] == "unknown"


# ---------------------------------------------------------------------------
# Test 5 -- Overall status after running probes
# ---------------------------------------------------------------------------
class TestOverallStatus:
    def _setup_probe(self):
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        import src.health_probe as hp_mod
        original_hp = hp_mod.health_probe
        hp_mod.health_probe = fake_probe
        try:
            from src.health_probe_registry import register_all_probes
            register_all_probes()
        finally:
            hp_mod.health_probe = original_hp
        return fake_probe

    def test_overall_unknown_before_checks(self):
        """Overall status is UNKNOWN before any checks have run."""
        fake_probe = self._setup_probe()
        assert fake_probe.overall_status().value == "unknown"

    def test_stats_after_checks(self):
        """get_stats returns correct counters after running checks."""
        fake_probe = self._setup_probe()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        # Run a few checks with healthy responses
        with patch("urllib.request.urlopen", return_value=mock_resp):
            fake_probe.run_check("lm_studio_m1")
            fake_probe.run_check("ollama_local")

        stats = fake_probe.get_stats()
        assert stats["total_probes"] == 10
        assert stats["total_checks"] == 2
        assert stats["healthy"] == 2
        assert stats["avg_latency_ms"] >= 0


# ---------------------------------------------------------------------------
# Test 6 -- Registration failure handling
# ---------------------------------------------------------------------------
class TestRegistrationFailure:
    def test_register_fails_gracefully(self):
        """If health_probe.register raises, the probe is marked False."""
        mock_hp_module = MagicMock()
        mock_probe = MagicMock()
        # Make register always raise
        mock_probe.register.side_effect = RuntimeError("probe full")
        mock_hp_module.health_probe = mock_probe
        mock_hp_module.HealthStatus = MagicMock()

        with patch.dict("sys.modules", {"src.health_probe": mock_hp_module}):
            from src.health_probe_registry import register_all_probes
            result = register_all_probes()

        # All 10 should be False since register always raises
        assert len(result) == 10
        assert all(v is False for v in result.values())


# ---------------------------------------------------------------------------
# Test 7 -- run_check on unknown probe returns None
# ---------------------------------------------------------------------------
class TestRunCheckUnknown:
    def test_run_check_nonexistent_probe(self):
        """run_check returns None for a probe that doesn't exist."""
        from src.health_probe import HealthProbe
        fake_probe = HealthProbe()
        result = fake_probe.run_check("nonexistent_probe_xyz")
        assert result is None
