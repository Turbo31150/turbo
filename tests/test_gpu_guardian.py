"""Tests for src/gpu_guardian.py -- GPU Guardian module.

Comprehensive tests covering GPUSnapshot, GuardianConfig, GPUGuardian class:
imports, thresholds, snapshot parsing, alert logic, throttling, trend analysis,
status reporting, emergency unload, rate limiting, and event emission.

All external dependencies (nvidia-smi, LM Studio API, event_bus) are mocked.
"""

import sys
import time
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gpu_guardian import GPUSnapshot, GuardianConfig, GPUGuardian, gpu_guardian


# ---------------------------------------------------------------------------
# 1. Import sanity
# ---------------------------------------------------------------------------

class TestImports:
    """Verify module-level imports and singleton."""

    def test_gpu_snapshot_importable(self):
        assert GPUSnapshot is not None

    def test_guardian_config_importable(self):
        assert GuardianConfig is not None

    def test_gpu_guardian_class_importable(self):
        assert GPUGuardian is not None

    def test_singleton_exists(self):
        assert isinstance(gpu_guardian, GPUGuardian)


# ---------------------------------------------------------------------------
# 2. GPUSnapshot dataclass
# ---------------------------------------------------------------------------

class TestGPUSnapshot:
    """Tests for the GPUSnapshot dataclass and its properties."""

    def test_default_values(self):
        snap = GPUSnapshot()
        assert snap.temperature == 0
        assert snap.vram_used_mb == 0
        assert snap.vram_total_mb == 0
        assert snap.vram_percent == 0.0
        assert snap.power_draw_w == 0.0
        assert snap.gpu_util_pct == 0
        assert isinstance(snap.ts, float)

    def test_custom_values(self):
        snap = GPUSnapshot(
            temperature=72,
            vram_used_mb=4000,
            vram_total_mb=8000,
            vram_percent=50.0,
            power_draw_w=120.5,
            gpu_util_pct=65,
        )
        assert snap.temperature == 72
        assert snap.vram_used_mb == 4000
        assert snap.vram_total_mb == 8000
        assert snap.vram_percent == 50.0
        assert snap.power_draw_w == 120.5
        assert snap.gpu_util_pct == 65

    def test_is_warning_temperature_above_75(self):
        snap = GPUSnapshot(temperature=76, vram_percent=50.0)
        assert snap.is_warning is True

    def test_is_warning_vram_above_85(self):
        snap = GPUSnapshot(temperature=60, vram_percent=86.0)
        assert snap.is_warning is True

    def test_is_warning_false_below_thresholds(self):
        snap = GPUSnapshot(temperature=70, vram_percent=80.0)
        assert snap.is_warning is False

    def test_is_warning_boundary_75_exactly(self):
        snap = GPUSnapshot(temperature=75, vram_percent=85.0)
        assert snap.is_warning is False  # > not >=

    def test_is_critical_temperature_above_85(self):
        snap = GPUSnapshot(temperature=86, vram_percent=50.0)
        assert snap.is_critical is True

    def test_is_critical_vram_above_95(self):
        snap = GPUSnapshot(temperature=60, vram_percent=96.0)
        assert snap.is_critical is True

    def test_is_critical_false_below_thresholds(self):
        snap = GPUSnapshot(temperature=80, vram_percent=90.0)
        assert snap.is_critical is False

    def test_is_critical_boundary_85_exactly(self):
        snap = GPUSnapshot(temperature=85, vram_percent=95.0)
        assert snap.is_critical is False  # > not >=


# ---------------------------------------------------------------------------
# 3. GuardianConfig defaults
# ---------------------------------------------------------------------------

class TestGuardianConfig:
    """Tests for GuardianConfig defaults and custom overrides."""

    def test_default_thresholds(self):
        cfg = GuardianConfig()
        assert cfg.temp_warning == 75
        assert cfg.temp_critical == 85
        assert cfg.temp_emergency == 90
        assert cfg.vram_warning_pct == 85.0
        assert cfg.vram_critical_pct == 95.0
        assert cfg.check_interval_s == 30.0
        assert cfg.cooldown_after_unload_s == 120.0
        assert cfg.max_unloads_per_hour == 3

    def test_custom_thresholds(self):
        cfg = GuardianConfig(temp_warning=70, temp_critical=80, max_unloads_per_hour=5)
        assert cfg.temp_warning == 70
        assert cfg.temp_critical == 80
        assert cfg.max_unloads_per_hour == 5


# ---------------------------------------------------------------------------
# 4. GPUGuardian initialization
# ---------------------------------------------------------------------------

class TestGPUGuardianInit:
    """Tests for GPUGuardian constructor and initial state."""

    def test_default_config(self):
        g = GPUGuardian()
        assert isinstance(g.config, GuardianConfig)
        assert g.running is False
        assert g._task is None
        assert g.history == []
        assert g._max_history == 1000
        assert g._unload_timestamps == []
        assert g._last_alert_time == 0
        assert g._alert_cooldown_s == 300.0

    def test_custom_config(self):
        cfg = GuardianConfig(temp_warning=65, check_interval_s=10.0)
        g = GPUGuardian(config=cfg)
        assert g.config.temp_warning == 65
        assert g.config.check_interval_s == 10.0

    def test_initial_stats(self):
        g = GPUGuardian()
        expected_keys = {"checks", "warnings", "criticals", "emergency_unloads", "errors"}
        assert set(g.stats.keys()) == expected_keys
        for v in g.stats.values():
            assert v == 0


# ---------------------------------------------------------------------------
# 5. Snapshot parsing (_take_snapshot)
# ---------------------------------------------------------------------------

class TestTakeSnapshot:
    """Tests for nvidia-smi output parsing."""

    @pytest.mark.asyncio
    async def test_parse_nvidia_smi_output(self):
        """Simulate nvidia-smi CSV output and verify parsed snapshot."""
        g = GPUGuardian()
        fake_stdout = b"72, 4096, 8192, 145.3, 55\n"
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(fake_stdout, b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            snap = await g._take_snapshot()

        assert snap is not None
        assert snap.temperature == 72
        assert snap.vram_used_mb == 4096
        assert snap.vram_total_mb == 8192
        assert abs(snap.vram_percent - 50.0) < 0.1
        assert snap.power_draw_w == 145.3
        assert snap.gpu_util_pct == 55

    @pytest.mark.asyncio
    async def test_parse_minimal_output_3_fields(self):
        """nvidia-smi output with only 3 fields (no power, no util)."""
        g = GPUGuardian()
        fake_stdout = b"60, 2000, 6000\n"
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(fake_stdout, b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            snap = await g._take_snapshot()

        assert snap is not None
        assert snap.temperature == 60
        assert snap.vram_used_mb == 2000
        assert snap.vram_total_mb == 6000
        assert snap.power_draw_w == 0
        assert snap.gpu_util_pct == 0

    @pytest.mark.asyncio
    async def test_snapshot_returns_none_on_failure(self):
        """When nvidia-smi fails, _take_snapshot returns None."""
        g = GPUGuardian()
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("nvidia-smi not found")):
            snap = await g._take_snapshot()
        assert snap is None

    @pytest.mark.asyncio
    async def test_snapshot_returns_none_on_timeout(self):
        """When nvidia-smi times out, _take_snapshot returns None."""
        g = GPUGuardian()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            snap = await g._take_snapshot()
        assert snap is None


# ---------------------------------------------------------------------------
# 6. Evaluate logic (_evaluate)
# ---------------------------------------------------------------------------

class TestEvaluate:
    """Tests for the _evaluate decision logic."""

    @pytest.mark.asyncio
    async def test_emergency_temp_triggers_unload(self):
        """Temperature >= temp_emergency triggers emergency unload."""
        g = GPUGuardian()
        g._emergency_unload = AsyncMock()
        g._emit_event = AsyncMock()
        snap = GPUSnapshot(temperature=91, vram_percent=50.0)

        await g._evaluate(snap)

        assert g.stats["criticals"] == 1
        g._emit_event.assert_any_call("gpu.temperature_emergency", {
            "temperature": 91,
            "vram_percent": 50.0
        })
        g._emergency_unload.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_critical_vram_triggers_overload_event(self):
        """VRAM > 95% triggers gpu.overload event."""
        g = GPUGuardian()
        g._emergency_unload = AsyncMock()
        g._emit_event = AsyncMock()
        snap = GPUSnapshot(temperature=60, vram_percent=96.0)

        await g._evaluate(snap)

        assert g.stats["criticals"] == 1
        g._emit_event.assert_any_call("gpu.overload", {
            "temperature": 60,
            "vram_percent": 96.0,
            "power_draw_w": 0.0
        })

    @pytest.mark.asyncio
    async def test_warning_triggers_alert_with_cooldown(self):
        """Warning emits gpu.warning event respecting cooldown."""
        g = GPUGuardian()
        g._emit_event = AsyncMock()
        g._last_alert_time = 0  # Never alerted before
        snap = GPUSnapshot(temperature=78, vram_percent=50.0)

        await g._evaluate(snap)

        assert g.stats["warnings"] == 1
        g._emit_event.assert_awaited_once()
        assert g._last_alert_time > 0

    @pytest.mark.asyncio
    async def test_warning_suppressed_within_cooldown(self):
        """Warning within cooldown period does NOT emit event."""
        g = GPUGuardian()
        g._emit_event = AsyncMock()
        g._last_alert_time = time.time()  # Just alerted
        snap = GPUSnapshot(temperature=78, vram_percent=50.0)

        await g._evaluate(snap)

        assert g.stats["warnings"] == 1
        g._emit_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_normal_snapshot_no_action(self):
        """Normal temperature and VRAM triggers no events."""
        g = GPUGuardian()
        g._emit_event = AsyncMock()
        g._emergency_unload = AsyncMock()
        snap = GPUSnapshot(temperature=55, vram_percent=40.0)

        await g._evaluate(snap)

        assert g.stats["warnings"] == 0
        assert g.stats["criticals"] == 0
        g._emit_event.assert_not_awaited()
        g._emergency_unload.assert_not_awaited()


# ---------------------------------------------------------------------------
# 7. Rate limiting (_can_unload)
# ---------------------------------------------------------------------------

class TestCanUnload:
    """Tests for the unload rate limiter."""

    def test_can_unload_when_fresh(self):
        g = GPUGuardian()
        assert g._can_unload() is True

    def test_cannot_unload_at_limit(self):
        g = GPUGuardian()
        now = time.time()
        g._unload_timestamps = [now - 100, now - 200, now - 300]
        assert g._can_unload() is False

    def test_can_unload_after_old_timestamps_expire(self):
        g = GPUGuardian()
        old = time.time() - 4000  # More than 1 hour ago
        g._unload_timestamps = [old, old, old]
        assert g._can_unload() is True
        # Old timestamps should have been pruned
        assert len(g._unload_timestamps) == 0

    def test_rate_limit_with_custom_max(self):
        cfg = GuardianConfig(max_unloads_per_hour=1)
        g = GPUGuardian(config=cfg)
        g._unload_timestamps = [time.time()]
        assert g._can_unload() is False


# ---------------------------------------------------------------------------
# 8. Emergency unload (_emergency_unload)
# ---------------------------------------------------------------------------

class TestEmergencyUnload:
    """Tests for model unloading via LM Studio API (mocked)."""

    @pytest.mark.asyncio
    async def test_unload_successful(self):
        """Successful unload path: lists models, unloads first, records timestamp."""
        g = GPUGuardian()
        g._emit_event = AsyncMock()
        snap = GPUSnapshot(temperature=92, vram_percent=97.0)

        models_resp = json.dumps({"data": [{"id": "qwen3-8b"}]}).encode()
        unload_resp = b'{"ok": true}'

        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=models_resp)))
        mock_urlopen.__exit__ = MagicMock(return_value=False)

        call_count = 0

        def fake_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # GET /v1/models
                ctx = MagicMock()
                ctx.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=models_resp)))
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx
            else:
                # POST /v1/models/unload
                return MagicMock(read=MagicMock(return_value=unload_resp))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with patch("urllib.request.Request") as mock_request:
                mock_request.side_effect = lambda *a, **kw: MagicMock()
                await g._emergency_unload(snap, reason="Test unload")

        assert g.stats["emergency_unloads"] == 1
        assert len(g._unload_timestamps) == 1
        g._emit_event.assert_awaited()

    @pytest.mark.asyncio
    async def test_unload_no_models_loaded(self):
        """When no models are loaded, nothing is unloaded."""
        g = GPUGuardian()
        g._emit_event = AsyncMock()
        snap = GPUSnapshot(temperature=92, vram_percent=97.0)

        models_resp = json.dumps({"data": []}).encode()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=models_resp)))
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_ctx):
            with patch("urllib.request.Request", return_value=MagicMock()):
                await g._emergency_unload(snap, reason="Test")

        assert g.stats["emergency_unloads"] == 0

    @pytest.mark.asyncio
    async def test_unload_blocked_by_rate_limit(self):
        """Unload is skipped when rate limit is hit."""
        g = GPUGuardian()
        now = time.time()
        g._unload_timestamps = [now - 10, now - 20, now - 30]
        snap = GPUSnapshot(temperature=92, vram_percent=97.0)

        await g._emergency_unload(snap, reason="Rate limited")
        assert g.stats["emergency_unloads"] == 0

    @pytest.mark.asyncio
    async def test_unload_handles_api_error(self):
        """API error during unload is caught gracefully."""
        g = GPUGuardian()
        g._emit_event = AsyncMock()
        snap = GPUSnapshot(temperature=92, vram_percent=97.0)

        with patch("urllib.request.urlopen", side_effect=ConnectionError("refused")):
            with patch("urllib.request.Request", return_value=MagicMock()):
                await g._emergency_unload(snap, reason="API down")

        # No crash, no unload recorded
        assert g.stats["emergency_unloads"] == 0


# ---------------------------------------------------------------------------
# 9. Event emission (_emit_event)
# ---------------------------------------------------------------------------

class TestEmitEvent:
    """Tests for event_bus integration."""

    @pytest.mark.asyncio
    async def test_emit_event_calls_event_bus(self):
        """Event is forwarded to event_bus.emit()."""
        g = GPUGuardian()
        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()

        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
            await g._emit_event("gpu.test", {"value": 42})

        mock_bus.emit.assert_awaited_once()
        call_args = mock_bus.emit.call_args
        assert call_args[0][0] == "gpu.test"
        assert call_args[0][1]["value"] == 42
        assert "ts" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_emit_event_swallows_import_error(self):
        """If event_bus import fails, no exception propagates."""
        g = GPUGuardian()
        with patch.dict("sys.modules", {"src.event_bus": None}):
            # Should not raise
            await g._emit_event("gpu.test", {"x": 1})


# ---------------------------------------------------------------------------
# 10. Status report
# ---------------------------------------------------------------------------

class TestStatus:
    """Tests for the status() method."""

    def test_status_no_history(self):
        g = GPUGuardian()
        s = g.status()
        assert s["running"] is False
        assert s["latest"] is None
        assert s["history_size"] == 0
        assert "config" in s
        assert s["config"]["temp_warning"] == 75
        assert s["config"]["temp_critical"] == 85
        assert s["config"]["temp_emergency"] == 90

    def test_status_with_history(self):
        g = GPUGuardian()
        g.history.append(GPUSnapshot(
            temperature=68, vram_used_mb=3000, vram_total_mb=8000,
            vram_percent=37.5, power_draw_w=100.0, gpu_util_pct=40
        ))
        s = g.status()
        assert s["latest"] is not None
        assert s["latest"]["temperature"] == 68
        assert s["latest"]["vram_percent"] == 37.5
        assert s["latest"]["gpu_util_pct"] == 40
        assert s["latest"]["power_draw_w"] == 100.0
        assert s["history_size"] == 1


# ---------------------------------------------------------------------------
# 11. Trend analysis
# ---------------------------------------------------------------------------

class TestTrend:
    """Tests for the trend() method."""

    def test_trend_no_data(self):
        g = GPUGuardian()
        t = g.trend(minutes=30)
        assert t == {"samples": 0}

    def test_trend_with_recent_data(self):
        g = GPUGuardian()
        now = time.time()
        g.history = [
            GPUSnapshot(temperature=60, vram_percent=40.0, ts=now - 60),
            GPUSnapshot(temperature=62, vram_percent=42.0, ts=now - 30),
            GPUSnapshot(temperature=64, vram_percent=44.0, ts=now),
        ]
        t = g.trend(minutes=5)
        assert t["samples"] == 3
        assert t["temp_min"] == 60
        assert t["temp_max"] == 64
        assert t["temp_avg"] == pytest.approx(62.0, abs=0.1)
        assert t["vram_avg"] == pytest.approx(42.0, abs=0.1)
        assert t["vram_max"] == 44.0
        assert t["temp_trend"] == "rising"  # 64 > 60 + 3

    def test_trend_stable(self):
        g = GPUGuardian()
        now = time.time()
        g.history = [
            GPUSnapshot(temperature=70, vram_percent=50.0, ts=now - 120),
            GPUSnapshot(temperature=71, vram_percent=51.0, ts=now - 60),
            GPUSnapshot(temperature=70, vram_percent=50.0, ts=now),
        ]
        t = g.trend(minutes=5)
        assert t["temp_trend"] == "stable"

    def test_trend_falling(self):
        g = GPUGuardian()
        now = time.time()
        g.history = [
            GPUSnapshot(temperature=80, vram_percent=60.0, ts=now - 120),
            GPUSnapshot(temperature=75, vram_percent=55.0, ts=now - 60),
            GPUSnapshot(temperature=72, vram_percent=50.0, ts=now),
        ]
        t = g.trend(minutes=5)
        assert t["temp_trend"] == "falling"  # 72 < 80 - 3

    def test_trend_old_data_excluded(self):
        g = GPUGuardian()
        now = time.time()
        g.history = [
            GPUSnapshot(temperature=90, vram_percent=99.0, ts=now - 7200),  # 2h ago
            GPUSnapshot(temperature=65, vram_percent=45.0, ts=now),
        ]
        t = g.trend(minutes=30)
        assert t["samples"] == 1
        assert t["temp_avg"] == 65.0


# ---------------------------------------------------------------------------
# 12. Start / Stop lifecycle
# ---------------------------------------------------------------------------

class TestStartStop:
    """Tests for start() and stop() lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        g = GPUGuardian()
        g._take_snapshot = AsyncMock(return_value=None)

        await g.start()
        assert g.running is True
        assert g._task is not None

        g.stop()
        assert g.running is False
        assert g._task is None

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Calling start() twice does not create a second task."""
        g = GPUGuardian()
        g._take_snapshot = AsyncMock(return_value=None)

        await g.start()
        task1 = g._task
        await g.start()
        task2 = g._task

        assert task1 is task2
        g.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self):
        """stop() on a never-started guardian is safe."""
        g = GPUGuardian()
        g.stop()  # Should not raise
        assert g.running is False


# ---------------------------------------------------------------------------
# 13. Monitor loop behavior
# ---------------------------------------------------------------------------

class TestMonitorLoop:
    """Tests for the _monitor_loop method."""

    @pytest.mark.asyncio
    async def test_loop_appends_snapshot_to_history(self):
        g = GPUGuardian()
        snap = GPUSnapshot(temperature=55, vram_percent=30.0)
        call_count = 0

        async def fake_snapshot():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                g.running = False
            return snap

        g._take_snapshot = fake_snapshot
        g._evaluate = AsyncMock()
        g.config.check_interval_s = 0.01
        g.running = True

        await g._monitor_loop()

        assert len(g.history) >= 1
        assert g.stats["checks"] >= 1
        g._evaluate.assert_awaited()

    @pytest.mark.asyncio
    async def test_loop_handles_snapshot_none(self):
        g = GPUGuardian()
        call_count = 0

        async def fake_snapshot():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                g.running = False
            return None

        g._take_snapshot = fake_snapshot
        g._evaluate = AsyncMock()
        g.config.check_interval_s = 0.01
        g.running = True

        await g._monitor_loop()

        assert len(g.history) == 0
        assert g.stats["checks"] == 0
        g._evaluate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_loop_caps_history_at_max(self):
        g = GPUGuardian()
        g._max_history = 5
        g._evaluate = AsyncMock()
        g.config.check_interval_s = 0.001

        call_count = 0

        async def fake_snapshot():
            nonlocal call_count
            call_count += 1
            if call_count > 8:
                g.running = False
                return None
            return GPUSnapshot(temperature=50 + call_count, vram_percent=30.0)

        g._take_snapshot = fake_snapshot
        g.running = True

        await g._monitor_loop()

        assert len(g.history) <= 5

    @pytest.mark.asyncio
    async def test_loop_increments_errors_on_exception(self):
        g = GPUGuardian()
        call_count = 0

        async def exploding_snapshot():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                g.running = False
                return None
            raise RuntimeError("GPU exploded")

        g._take_snapshot = exploding_snapshot
        g.config.check_interval_s = 0.01
        g.running = True

        await g._monitor_loop()

        assert g.stats["errors"] >= 1


# ---------------------------------------------------------------------------
# 14. URL validation (127.0.0.1 not localhost)
# ---------------------------------------------------------------------------

class TestURLs:
    """Verify all URLs in the module use 127.0.0.1, not localhost."""

    def test_no_localhost_in_source(self):
        src_path = Path(__file__).parent.parent / "src" / "gpu_guardian.py"
        content = src_path.read_text(encoding="utf-8")
        # The module should use 127.0.0.1 for LM Studio API
        assert "127.0.0.1:1234" in content
        assert "localhost:1234" not in content
