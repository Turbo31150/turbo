"""Tests for src/event_bus_wiring.py — Event Bus Wiring module.

Comprehensive tests covering:
- Module import and structure
- wire_all() subscription wiring
- Each event handler (drift, cluster, gpu, trading, brain, autonomous,
  security, audit, voice, budget)
- _notify() helper
- status() introspection
- Error resilience in handlers

All external dependencies are mocked — no network, no database, no real event bus.
"""

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeEventBus:
    """Lightweight fake EventBus that records subscribe/emit calls."""

    def __init__(self):
        self._subscriptions: list = []
        self._handlers: dict[str, list] = {}
        self.total_events: int = 0
        self._emitted: list[tuple[str, dict]] = []

    def subscribe(self, pattern: str, handler, priority: int = 0):
        self._subscriptions.append((pattern, handler, priority))
        self._handlers.setdefault(pattern, []).append(handler)

    async def emit(self, event: str, data: dict | None = None):
        data = data or {}
        self._emitted.append((event, data))
        self.total_events += 1

    async def fire_handlers(self, pattern: str, data: dict):
        """Test utility: call all handlers registered for exact pattern."""
        for h in self._handlers.get(pattern, []):
            await h(data)


@pytest.fixture
def fake_bus():
    return FakeEventBus()


@pytest.fixture
def patch_event_bus(fake_bus):
    """Patch 'src.event_bus.event_bus' everywhere it is lazily imported."""
    with patch.dict("sys.modules", {
        "src.event_bus": MagicMock(event_bus=fake_bus),
    }):
        yield fake_bus


# ---------------------------------------------------------------------------
# 1. Import tests
# ---------------------------------------------------------------------------

class TestImports:
    """Verify the module can be imported and exposes expected symbols."""

    def test_import_module(self):
        from src import event_bus_wiring
        assert hasattr(event_bus_wiring, "wire_all")
        assert hasattr(event_bus_wiring, "status")
        assert hasattr(event_bus_wiring, "_notify")

    def test_wire_all_is_coroutine(self):
        from src.event_bus_wiring import wire_all
        import asyncio
        assert asyncio.iscoroutinefunction(wire_all)

    def test_status_is_coroutine(self):
        from src.event_bus_wiring import status
        import asyncio
        assert asyncio.iscoroutinefunction(status)

    def test_notify_is_coroutine(self):
        from src.event_bus_wiring import _notify
        import asyncio
        assert asyncio.iscoroutinefunction(_notify)


# ---------------------------------------------------------------------------
# 2. wire_all() subscription registration
# ---------------------------------------------------------------------------

class TestWireAll:
    """Test that wire_all() registers the correct number of subscriptions."""

    @pytest.mark.asyncio
    async def test_wire_all_returns_counts(self, patch_event_bus):
        from src.event_bus_wiring import wire_all
        counts = await wire_all()
        assert isinstance(counts, dict)

    @pytest.mark.asyncio
    async def test_wire_all_has_all_categories(self, patch_event_bus):
        from src.event_bus_wiring import wire_all
        counts = await wire_all()
        expected_categories = {
            "drift", "cluster", "gpu", "trading", "brain",
            "autonomous", "security", "audit", "voice", "budget"
        }
        assert set(counts.keys()) == expected_categories

    @pytest.mark.asyncio
    async def test_wire_all_subscription_counts(self, patch_event_bus):
        from src.event_bus_wiring import wire_all
        counts = await wire_all()
        assert counts["drift"] == 2
        assert counts["cluster"] == 2
        assert counts["gpu"] == 2
        assert counts["trading"] == 2
        assert counts["brain"] == 1
        assert counts["autonomous"] == 2
        assert counts["security"] == 1
        assert counts["audit"] == 1
        assert counts["voice"] == 1
        assert counts["budget"] == 2

    @pytest.mark.asyncio
    async def test_wire_all_total_subscriptions(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        counts = await wire_all()
        total = sum(counts.values())
        assert total == 16
        # Also verify the fake bus recorded the same number
        assert len(fake_bus._subscriptions) == 16

    @pytest.mark.asyncio
    async def test_wire_all_subscription_patterns(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        await wire_all()
        patterns = [s[0] for s in fake_bus._subscriptions]
        assert "drift.*" in patterns
        assert "model.quality_drop" in patterns
        assert "cluster.node_offline" in patterns
        assert "cluster.node_online" in patterns
        assert "gpu.overload" in patterns
        assert "gpu.temperature_critical" in patterns
        assert "trading.signal_detected" in patterns
        assert "trading.risk_alert" in patterns
        assert "brain.pattern_detected" in patterns
        assert "autonomous.task_failed" in patterns
        assert "autonomous.task_error" in patterns
        assert "security.*" in patterns
        assert "*" in patterns
        assert "voice.command_processed" in patterns
        assert "budget.warning" in patterns
        assert "budget.exhausted" in patterns


# ---------------------------------------------------------------------------
# 3. Individual handler tests
# ---------------------------------------------------------------------------

class TestDriftHandler:
    """Test drift detection handler."""

    @pytest.mark.asyncio
    async def test_drift_handler_emits_reroute(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            # Trigger drift handler
            await fake_bus.fire_handlers("drift.*", {
                "model": "M2", "severity": "critical"
            })
            mock_notify.assert_awaited_once()
            assert "M2" in mock_notify.call_args[0][0]
            # Check reroute event was emitted
            assert any(e[0] == "orchestrator.reroute_triggered" for e in fake_bus._emitted)

    @pytest.mark.asyncio
    async def test_drift_handler_error_resilience(self, patch_event_bus):
        """Handler should not raise even if internal import fails."""
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock, side_effect=Exception("boom")):
            await wire_all()
            # Should not raise
            await fake_bus.fire_handlers("drift.*", {"model": "X"})


class TestClusterHandler:
    """Test cluster health handlers."""

    @pytest.mark.asyncio
    async def test_node_offline_emits_heal(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("cluster.node_offline", {"node": "M3"})
            mock_notify.assert_awaited_once()
            assert "M3" in mock_notify.call_args[0][0]
            assert any(e[0] == "cluster.heal_requested" for e in fake_bus._emitted)

    @pytest.mark.asyncio
    async def test_node_online_notifies(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("cluster.node_online", {"node": "M1"})
            mock_notify.assert_awaited_once()
            assert "M1" in mock_notify.call_args[0][0]
            assert mock_notify.call_args[0][1] == "info"


class TestGpuHandler:
    """Test GPU monitoring handler."""

    @pytest.mark.asyncio
    async def test_gpu_overload_notifies(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("gpu.overload", {
                "temperature": 70, "vram_percent": 80
            })
            mock_notify.assert_awaited_once()
            # Below threshold: should NOT emit emergency_unload
            assert not any(e[0] == "gpu.emergency_unload" for e in fake_bus._emitted)

    @pytest.mark.asyncio
    async def test_gpu_emergency_unload_on_critical(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock):
            await wire_all()
            await fake_bus.fire_handlers("gpu.overload", {
                "temperature": 90, "vram_percent": 97
            })
            assert any(e[0] == "gpu.emergency_unload" for e in fake_bus._emitted)

    @pytest.mark.asyncio
    async def test_gpu_emergency_at_temp_boundary(self, patch_event_bus):
        """Temp exactly 85 should NOT trigger (> 85 required)."""
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock):
            await wire_all()
            await fake_bus.fire_handlers("gpu.overload", {
                "temperature": 85, "vram_percent": 90
            })
            assert not any(e[0] == "gpu.emergency_unload" for e in fake_bus._emitted)

    @pytest.mark.asyncio
    async def test_gpu_emergency_at_vram_boundary(self, patch_event_bus):
        """VRAM exactly 95 should NOT trigger (> 95 required)."""
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock):
            await wire_all()
            await fake_bus.fire_handlers("gpu.overload", {
                "temperature": 50, "vram_percent": 95
            })
            assert not any(e[0] == "gpu.emergency_unload" for e in fake_bus._emitted)


class TestTradingHandler:
    """Test trading signal and risk handlers."""

    @pytest.mark.asyncio
    async def test_trading_signal_below_threshold_no_notify(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("trading.signal_detected", {
                "symbol": "BTC", "score": 50, "direction": "LONG"
            })
            mock_notify.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_trading_signal_high_score_warning(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("trading.signal_detected", {
                "symbol": "ETH", "score": 85, "direction": "SHORT"
            })
            mock_notify.assert_awaited_once()
            assert mock_notify.call_args[0][1] == "warning"

    @pytest.mark.asyncio
    async def test_trading_signal_very_high_score_critical(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("trading.signal_detected", {
                "symbol": "SOL", "score": 95, "direction": "LONG"
            })
            mock_notify.assert_awaited_once()
            assert mock_notify.call_args[0][1] == "critical"

    @pytest.mark.asyncio
    async def test_trading_risk_alert(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("trading.risk_alert", {
                "message": "Drawdown > 5%"
            })
            mock_notify.assert_awaited_once()
            assert "Drawdown" in mock_notify.call_args[0][0]
            assert mock_notify.call_args[0][1] == "critical"


class TestBrainPatternHandler:
    """Test brain pattern detection handler."""

    @pytest.mark.asyncio
    async def test_pattern_low_confidence_no_emit(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("brain.pattern_detected", {
                "pattern": "greet_user", "confidence": 0.5
            })
            mock_notify.assert_not_awaited()
            assert not any(e[0] == "brain.skill_auto_created" for e in fake_bus._emitted)

    @pytest.mark.asyncio
    async def test_pattern_high_confidence_emits_skill(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("brain.pattern_detected", {
                "pattern": "auto_deploy", "confidence": 0.9
            })
            mock_notify.assert_awaited_once()
            assert any(e[0] == "brain.skill_auto_created" for e in fake_bus._emitted)

    @pytest.mark.asyncio
    async def test_pattern_boundary_confidence_08(self, patch_event_bus):
        """Confidence exactly 0.8 should trigger (>= 0.8)."""
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("brain.pattern_detected", {
                "pattern": "boundary_test", "confidence": 0.8
            })
            mock_notify.assert_awaited_once()
            assert any(e[0] == "brain.skill_auto_created" for e in fake_bus._emitted)


class TestAutonomousHandler:
    """Test autonomous loop failure handler."""

    @pytest.mark.asyncio
    async def test_task_failed_below_threshold(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("autonomous.task_failed", {
                "task": "heartbeat", "fail_count": 1, "error": "timeout"
            })
            mock_notify.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_task_failed_two_times_logs_warning(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            # fail_count=2 logs warning but does not notify
            await fake_bus.fire_handlers("autonomous.task_failed", {
                "task": "heartbeat", "fail_count": 2, "error": "timeout"
            })
            mock_notify.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_task_failed_three_times_notifies_critical(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("autonomous.task_failed", {
                "task": "heartbeat", "fail_count": 3, "error": "timeout"
            })
            mock_notify.assert_awaited_once()
            assert mock_notify.call_args[0][1] == "critical"


class TestSecurityHandler:
    """Test security alert handler."""

    @pytest.mark.asyncio
    async def test_security_alert_notifies(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("security.*", {
                "message": "Brute force detected", "level": "critical"
            })
            mock_notify.assert_awaited_once()
            assert "Brute force" in mock_notify.call_args[0][0]
            assert mock_notify.call_args[0][1] == "critical"

    @pytest.mark.asyncio
    async def test_security_handler_defaults(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("security.*", {})
            mock_notify.assert_awaited_once()
            # Default level is "warning"
            assert mock_notify.call_args[0][1] == "warning"


class TestAuditHandler:
    """Test audit logger handler."""

    @pytest.mark.asyncio
    async def test_audit_handler_logs_event(self, patch_event_bus):
        fake_bus = patch_event_bus
        mock_audit = MagicMock()
        mock_audit.log = MagicMock()
        from src.event_bus_wiring import wire_all
        with patch.dict("sys.modules", {
            "src.audit_trail": MagicMock(audit_trail=mock_audit)
        }):
            await wire_all()
            await fake_bus.fire_handlers("*", {
                "_event_type": "test.event", "key": "value"
            })
            mock_audit.log.assert_called_once()
            call_kwargs = mock_audit.log.call_args[1]
            assert call_kwargs["action_type"] == "event_bus"
            assert call_kwargs["source"] == "event_bus_wiring"
            assert call_kwargs["status"] == "ok"

    @pytest.mark.asyncio
    async def test_audit_handler_never_raises(self, patch_event_bus):
        """Audit handler must silently swallow all exceptions."""
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch.dict("sys.modules", {
            "src.audit_trail": MagicMock(side_effect=ImportError("no audit"))
        }):
            await wire_all()
            # Should not raise
            await fake_bus.fire_handlers("*", {"_event_type": "broken"})


class TestVoiceHandler:
    """Test voice command handler."""

    @pytest.mark.asyncio
    async def test_voice_command_logs_to_brain(self, patch_event_bus):
        fake_bus = patch_event_bus
        mock_log_action = MagicMock()
        from src.event_bus_wiring import wire_all
        with patch("src.skills.log_action", mock_log_action):
            await wire_all()
            await fake_bus.fire_handlers("voice.command_processed", {
                "text": "ouvre le dashboard", "intent": "open_dashboard",
                "confidence": 0.95
            })
            mock_log_action.assert_called_once_with(
                "voice_command",
                "open_dashboard: ouvre le dashboard",
                True
            )

    @pytest.mark.asyncio
    async def test_voice_command_empty_text_skipped(self, patch_event_bus):
        fake_bus = patch_event_bus
        mock_brain = MagicMock()
        mock_brain.log_action = MagicMock()
        from src.event_bus_wiring import wire_all
        with patch.dict("sys.modules", {
            "src.brain": MagicMock(brain=mock_brain)
        }):
            await wire_all()
            await fake_bus.fire_handlers("voice.command_processed", {
                "text": "", "intent": "", "confidence": 0
            })
            mock_brain.log_action.assert_not_called()


class TestBudgetHandler:
    """Test budget warning handler."""

    @pytest.mark.asyncio
    async def test_budget_warning_notifies(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("budget.warning", {
                "used_percent": 85, "remaining_tokens": 15000
            })
            mock_notify.assert_awaited_once()
            assert "85" in mock_notify.call_args[0][0]
            assert mock_notify.call_args[0][1] == "warning"

    @pytest.mark.asyncio
    async def test_budget_exhausted_notifies(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        with patch("src.event_bus_wiring._notify", new_callable=AsyncMock) as mock_notify:
            await wire_all()
            await fake_bus.fire_handlers("budget.exhausted", {
                "used_percent": 100, "remaining_tokens": 0
            })
            mock_notify.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. _notify() helper
# ---------------------------------------------------------------------------

class TestNotify:
    """Test the _notify() helper function."""

    @pytest.mark.asyncio
    async def test_notify_dispatches_via_notification_hub(self):
        mock_hub = MagicMock()
        mock_hub.dispatch = MagicMock()
        with patch.dict("sys.modules", {
            "src.notification_hub": MagicMock(notification_hub=mock_hub)
        }):
            from src.event_bus_wiring import _notify
            await _notify("Test message", "info")
            mock_hub.dispatch.assert_called_once_with(
                message="Test message", level="info", source="event_bus_wiring"
            )

    @pytest.mark.asyncio
    async def test_notify_falls_back_to_logger_on_import_error(self):
        """If notification_hub is not available, _notify should just log."""
        with patch.dict("sys.modules", {
            "src.notification_hub": None  # Simulate ImportError
        }):
            from src.event_bus_wiring import _notify
            # Should not raise
            await _notify("Fallback test", "warning")

    @pytest.mark.asyncio
    async def test_notify_default_level_is_info(self):
        mock_hub = MagicMock()
        mock_hub.dispatch = MagicMock()
        with patch.dict("sys.modules", {
            "src.notification_hub": MagicMock(notification_hub=mock_hub)
        }):
            from src.event_bus_wiring import _notify
            await _notify("Default level")
            assert mock_hub.dispatch.call_args[1]["level"] == "info"


# ---------------------------------------------------------------------------
# 5. status()
# ---------------------------------------------------------------------------

class TestStatus:
    """Test the status() function."""

    @pytest.mark.asyncio
    async def test_status_returns_dict(self, patch_event_bus):
        from src.event_bus_wiring import status
        result = await status()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_status_has_expected_keys(self, patch_event_bus):
        from src.event_bus_wiring import status
        result = await status()
        assert "subscriptions" in result
        assert "total_events" in result
        assert "categories" in result

    @pytest.mark.asyncio
    async def test_status_categories_list(self, patch_event_bus):
        from src.event_bus_wiring import status
        result = await status()
        expected = [
            "drift", "cluster", "gpu", "trading", "brain",
            "autonomous", "security", "audit", "voice", "budget"
        ]
        assert result["categories"] == expected

    @pytest.mark.asyncio
    async def test_status_subscription_count(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all, status
        await wire_all()
        result = await status()
        assert result["subscriptions"] == len(fake_bus._subscriptions)

    @pytest.mark.asyncio
    async def test_status_total_events(self, patch_event_bus):
        fake_bus = patch_event_bus
        from src.event_bus_wiring import status
        fake_bus.total_events = 42
        result = await status()
        assert result["total_events"] == 42


# ---------------------------------------------------------------------------
# 6. Priority ordering
# ---------------------------------------------------------------------------

class TestPriorities:
    """Verify that subscriptions use correct priorities."""

    @pytest.mark.asyncio
    async def test_high_priority_handlers(self, patch_event_bus):
        """Critical handlers (drift, cluster offline, gpu, security) should have priority 10."""
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        await wire_all()

        high_prio = {s[0] for s in fake_bus._subscriptions if s[2] == 10}
        assert "drift.*" in high_prio
        assert "model.quality_drop" in high_prio
        assert "cluster.node_offline" in high_prio
        assert "gpu.overload" in high_prio
        assert "gpu.temperature_critical" in high_prio
        assert "security.*" in high_prio
        assert "budget.exhausted" in high_prio

    @pytest.mark.asyncio
    async def test_audit_has_lowest_priority(self, patch_event_bus):
        """Audit catch-all (*) should have priority -10 (runs last)."""
        fake_bus = patch_event_bus
        from src.event_bus_wiring import wire_all
        await wire_all()
        audit_subs = [s for s in fake_bus._subscriptions if s[0] == "*"]
        assert len(audit_subs) == 1
        assert audit_subs[0][2] == -10
