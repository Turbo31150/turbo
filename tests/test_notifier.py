"""Tests for src/notifier.py — Unified notification system.

Covers: Level, Notification, Notifier (alert, info, warn, critical,
_send_toast, _send_tts, get_history, get_stats, cooldown),
notifier singleton.
All subprocess/TTS calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.notifier import Notifier, Level, Notification, notifier


# ===========================================================================
# Level & Notification
# ===========================================================================

class TestDataclasses:
    def test_level_values(self):
        assert Level.INFO == "info"
        assert Level.WARNING == "warning"
        assert Level.CRITICAL == "critical"

    def test_notification_defaults(self):
        n = Notification(message="test", level=Level.INFO)
        assert n.delivered is False
        assert n.ts > 0
        assert n.source == ""


# ===========================================================================
# Notifier — alert (async)
# ===========================================================================

class TestAlert:
    @pytest.mark.asyncio
    async def test_info_always_delivered(self):
        n = Notifier()
        result = await n.alert("hello", level="info")
        assert result is True

    @pytest.mark.asyncio
    async def test_warning_sends_toast(self):
        n = Notifier()
        with patch.object(n, "_send_toast", new_callable=AsyncMock, return_value=True) as mock_toast:
            result = await n.alert("warning msg", level="warning")
        assert result is True
        mock_toast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_critical_sends_tts(self):
        n = Notifier()
        with patch.object(n, "_send_tts", new_callable=AsyncMock, return_value=True) as mock_tts:
            result = await n.alert("critical!", level="critical")
        assert result is True
        mock_tts.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_critical_fallback_to_toast(self):
        n = Notifier()
        with patch.object(n, "_send_tts", new_callable=AsyncMock, return_value=False), \
             patch.object(n, "_send_toast", new_callable=AsyncMock, return_value=True) as mock_toast:
            result = await n.alert("fallback", level="critical")
        assert result is True
        mock_toast.assert_awaited_once()


# ===========================================================================
# Notifier — cooldown
# ===========================================================================

class TestCooldown:
    @pytest.mark.asyncio
    async def test_cooldown_blocks_duplicate(self):
        n = Notifier()
        await n.alert("same msg", level="info")
        result = await n.alert("same msg", level="info")
        assert result is False

    @pytest.mark.asyncio
    async def test_cooldown_allows_different(self):
        n = Notifier()
        r1 = await n.alert("msg A", level="info")
        r2 = await n.alert("msg B", level="info")
        assert r1 is True
        assert r2 is True


# ===========================================================================
# Notifier — convenience methods
# ===========================================================================

class TestConvenience:
    @pytest.mark.asyncio
    async def test_info(self):
        n = Notifier()
        result = await n.info("test info")
        assert result is True

    @pytest.mark.asyncio
    async def test_warn(self):
        n = Notifier()
        with patch.object(n, "_send_toast", new_callable=AsyncMock, return_value=True):
            result = await n.warn("test warn")
        assert result is True

    @pytest.mark.asyncio
    async def test_critical(self):
        n = Notifier()
        with patch.object(n, "_send_tts", new_callable=AsyncMock, return_value=True):
            result = await n.critical("test crit")
        assert result is True


# ===========================================================================
# Notifier — _send_toast (mocked)
# ===========================================================================

class TestSendToast:
    @pytest.mark.asyncio
    async def test_toast_disabled(self):
        n = Notifier()
        n._toast_enabled = False
        result = await n._send_toast("msg")
        assert result is False

    @pytest.mark.asyncio
    async def test_toast_success(self):
        n = Notifier()
        import asyncio
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=None):
            result = await n._send_toast("msg", "title")
        assert result is True

    @pytest.mark.asyncio
    async def test_toast_exception(self):
        n = Notifier()
        with patch("asyncio.to_thread", new_callable=AsyncMock, side_effect=Exception("fail")):
            result = await n._send_toast("msg")
        assert result is False


# ===========================================================================
# Notifier — _send_tts (mocked)
# ===========================================================================

class TestSendTts:
    @pytest.mark.asyncio
    async def test_tts_disabled(self):
        n = Notifier()
        n._tts_enabled = False
        result = await n._send_tts("msg")
        assert result is False

    @pytest.mark.asyncio
    async def test_tts_exception(self):
        n = Notifier()
        with patch.dict("sys.modules", {"edge_tts": None}):
            result = await n._send_tts("msg")
        assert result is False


# ===========================================================================
# Notifier — history & stats
# ===========================================================================

class TestHistoryStats:
    @pytest.mark.asyncio
    async def test_history(self):
        n = Notifier()
        await n.info("one")
        await n.info("two")
        history = n.get_history()
        assert len(history) == 2
        assert history[0]["level"] == "info"

    def test_stats_empty(self):
        n = Notifier()
        stats = n.get_stats()
        assert stats["total"] == 0
        assert stats["tts_enabled"] is True

    @pytest.mark.asyncio
    async def test_stats_after_alerts(self):
        n = Notifier()
        await n.info("a")
        await n.info("b")
        stats = n.get_stats()
        assert stats["total"] == 2
        assert stats["by_level"]["info"] == 2

    @pytest.mark.asyncio
    async def test_history_cap(self):
        n = Notifier(max_history=5)
        for i in range(10):
            await n.alert(f"msg{i}", level="info")
        assert len(n._history) == 5


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert notifier is not None
        assert isinstance(notifier, Notifier)
