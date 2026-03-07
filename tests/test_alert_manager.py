"""Tests for src/alert_manager.py — Unified alert system with escalation.

Covers: Alert, AlertManager (fire, acknowledge, resolve, get_active, get_all,
get_history, get_stats, clear_resolved), alert_manager singleton.
Event bus and notifier are mocked.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alert_manager import Alert, AlertManager, alert_manager


# ===========================================================================
# Alert dataclass
# ===========================================================================

class TestAlert:
    def test_defaults(self):
        a = Alert(id="a1", key="gpu_hot", message="GPU hot", level="warning",
                  source="gpu_monitor", created_at=time.time(), updated_at=time.time())
        assert a.count == 1
        assert a.acknowledged is False
        assert a.resolved is False
        assert a.metadata == {}


# ===========================================================================
# AlertManager — fire
# ===========================================================================

class TestFire:
    @pytest.mark.asyncio
    async def test_fire_new_alert(self):
        am = AlertManager()
        with patch("src.alert_manager.event_bus", create=True) as mock_eb:
            mock_eb.emit = AsyncMock()
            with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_eb)}):
                result = await am.fire("test_key", "Test message", level="info", source="test")
        assert result is True
        active = am.get_active()
        assert len(active) == 1
        assert active[0]["key"] == "test_key"

    @pytest.mark.asyncio
    async def test_fire_dedup(self):
        am = AlertManager()
        am._cooldown_s = 0  # disable cooldown for test
        mock_eb = MagicMock()
        mock_eb.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_eb)}):
            await am.fire("k1", "msg1", level="info", source="s")
            await am.fire("k1", "msg2", level="info", source="s")
        active = am.get_active()
        assert len(active) == 1
        assert active[0]["count"] == 2
        assert active[0]["message"] == "msg2"

    @pytest.mark.asyncio
    async def test_fire_cooldown(self):
        am = AlertManager()
        am._cooldown_s = 999  # long cooldown
        mock_eb = MagicMock()
        mock_eb.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_eb)}):
            r1 = await am.fire("k1", "msg", level="info", source="s")
            r2 = await am.fire("k1", "msg", level="info", source="s")
        assert r1 is True
        assert r2 is False  # cooled down

    @pytest.mark.asyncio
    async def test_fire_escalation_info_to_warning(self):
        am = AlertManager()
        am._cooldown_s = 0
        mock_eb = MagicMock()
        mock_eb.emit = AsyncMock()
        mock_notifier = MagicMock()
        mock_notifier.warn = AsyncMock()
        mock_notifier.alert = AsyncMock()
        with patch.dict("sys.modules", {
            "src.event_bus": MagicMock(event_bus=mock_eb),
            "src.notifier": MagicMock(notifier=mock_notifier),
        }):
            for i in range(5):
                await am.fire("k1", f"msg{i}", level="info", source="s")
        active = am.get_active()
        # After 5 fires, info escalates to warning
        assert active[0]["level"] == "warning"

    @pytest.mark.asyncio
    async def test_fire_with_metadata(self):
        am = AlertManager()
        mock_eb = MagicMock()
        mock_eb.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_eb)}):
            await am.fire("k1", "msg", metadata={"temp": 85})
        active = am.get_active()
        assert active[0]["metadata"]["temp"] == 85


# ===========================================================================
# AlertManager — acknowledge / resolve
# ===========================================================================

class TestAckResolve:
    @pytest.mark.asyncio
    async def test_acknowledge(self):
        am = AlertManager()
        mock_eb = MagicMock()
        mock_eb.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_eb)}):
            await am.fire("k1", "msg", level="info")
        assert am.acknowledge("k1") is True
        assert am.get_active()[0]["acknowledged"] is True

    def test_acknowledge_nonexistent(self):
        am = AlertManager()
        assert am.acknowledge("nope") is False

    @pytest.mark.asyncio
    async def test_resolve(self):
        am = AlertManager()
        mock_eb = MagicMock()
        mock_eb.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_eb)}):
            await am.fire("k1", "msg", level="info")
        assert am.resolve("k1") is True
        assert am.get_active() == []

    def test_resolve_nonexistent(self):
        am = AlertManager()
        assert am.resolve("nope") is False


# ===========================================================================
# AlertManager — query
# ===========================================================================

class TestQuery:
    @pytest.mark.asyncio
    async def test_get_active_filtered(self):
        am = AlertManager()
        am._cooldown_s = 0
        mock_eb = MagicMock()
        mock_eb.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_eb)}):
            await am.fire("k1", "info msg", level="info")
            await am.fire("k2", "warn msg", level="warning", source="gpu")
        active_warn = am.get_active(level="warning")
        assert len(active_warn) == 1
        assert active_warn[0]["level"] == "warning"

    @pytest.mark.asyncio
    async def test_get_all(self):
        am = AlertManager()
        mock_eb = MagicMock()
        mock_eb.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_eb)}):
            await am.fire("k1", "msg1", level="info")
        am.resolve("k1")
        all_alerts = am.get_all()
        assert len(all_alerts) == 1
        assert all_alerts[0]["resolved"] is True

    @pytest.mark.asyncio
    async def test_get_history(self):
        am = AlertManager()
        am._cooldown_s = 0
        mock_eb = MagicMock()
        mock_eb.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_eb)}):
            await am.fire("k1", "msg1", level="info")
            await am.fire("k2", "msg2", level="info")
        history = am.get_history()
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_clear_resolved(self):
        am = AlertManager()
        mock_eb = MagicMock()
        mock_eb.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_eb)}):
            await am.fire("k1", "msg", level="info")
        am.resolve("k1")
        cleared = am.clear_resolved()
        assert cleared == 1
        assert am.get_all() == []


# ===========================================================================
# AlertManager — stats
# ===========================================================================

class TestStats:
    @pytest.mark.asyncio
    async def test_stats(self):
        am = AlertManager()
        am._cooldown_s = 0
        mock_eb = MagicMock()
        mock_eb.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_eb)}):
            await am.fire("k1", "msg1", level="info")
            await am.fire("k2", "msg2", level="warning", source="gpu")
        stats = am.get_stats()
        assert stats["total_alerts"] == 2
        assert stats["active_alerts"] == 2
        assert "info" in stats["by_level"]

    def test_stats_empty(self):
        am = AlertManager()
        stats = am.get_stats()
        assert stats["total_alerts"] == 0
        assert stats["active_alerts"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert alert_manager is not None
        assert isinstance(alert_manager, AlertManager)
