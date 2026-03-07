"""Tests for src/event_bus.py — Async pub/sub event bus.

Covers: Subscription, EventBus (subscribe, emit, emit_sync, clear,
subscriber_count, get_events, get_stats), event_bus singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.event_bus import Subscription, EventBus, event_bus


# ===========================================================================
# Subscription
# ===========================================================================

class TestSubscription:
    def test_exact_match(self):
        s = Subscription(pattern="cluster.offline", handler=lambda d: None)
        assert s.matches("cluster.offline") is True
        assert s.matches("cluster.online") is False

    def test_wildcard_match(self):
        s = Subscription(pattern="cluster.*", handler=lambda d: None)
        assert s.matches("cluster.offline") is True
        assert s.matches("cluster.online") is True
        assert s.matches("trading.buy") is False

    def test_global_wildcard(self):
        s = Subscription(pattern="*", handler=lambda d: None)
        assert s.matches("anything") is True


# ===========================================================================
# EventBus — subscribe & emit
# ===========================================================================

class TestSubscribeEmit:
    @pytest.mark.asyncio
    async def test_emit(self):
        eb = EventBus()
        received = []
        async def handler(data):
            received.append(data)
        eb.subscribe("test.event", handler)
        count = await eb.emit("test.event", {"key": "val"})
        assert count == 1
        assert received[0]["key"] == "val"

    @pytest.mark.asyncio
    async def test_wildcard_emit(self):
        eb = EventBus()
        received = []
        async def handler(data):
            received.append(data)
        eb.subscribe("cluster.*", handler)
        await eb.emit("cluster.offline", {"node": "M2"})
        await eb.emit("trading.buy", {})
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_no_subscribers(self):
        eb = EventBus()
        count = await eb.emit("nobody.listens")
        assert count == 0

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        eb = EventBus()
        received = []
        async def handler(data):
            received.append(data)
        unsub = eb.subscribe("test", handler)
        unsub()
        await eb.emit("test")
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_priority(self):
        eb = EventBus()
        order = []
        async def high(data):
            order.append("high")
        async def low(data):
            order.append("low")
        eb.subscribe("test", low, priority=0)
        eb.subscribe("test", high, priority=10)
        await eb.emit("test")
        assert order == ["high", "low"]

    @pytest.mark.asyncio
    async def test_handler_error(self):
        eb = EventBus()
        async def bad_handler(data):
            raise RuntimeError("boom")
        async def good_handler(data):
            pass
        eb.subscribe("test", bad_handler)
        eb.subscribe("test", good_handler)
        # Should not raise, but only count successful
        count = await eb.emit("test")
        assert count == 1  # good_handler succeeded


# ===========================================================================
# EventBus — emit_sync
# ===========================================================================

class TestEmitSync:
    def test_emit_sync_no_loop(self):
        eb = EventBus()
        # No running loop — should not raise
        eb.emit_sync("test.event", {"key": "val"})
        assert eb.get_stats()["total_events_emitted"] >= 1


# ===========================================================================
# EventBus — clear & subscriber_count
# ===========================================================================

class TestClearCount:
    def test_clear(self):
        eb = EventBus()
        async def h(d): pass
        eb.subscribe("a", h)
        eb.subscribe("b", h)
        eb.clear()
        assert eb.subscriber_count() == 0

    def test_subscriber_count(self):
        eb = EventBus()
        async def h(d): pass
        eb.subscribe("cluster.*", h)
        eb.subscribe("cluster.offline", h)
        assert eb.subscriber_count() == 2
        assert eb.subscriber_count("cluster.offline") == 2


# ===========================================================================
# EventBus — get_events & get_stats
# ===========================================================================

class TestEventsStats:
    @pytest.mark.asyncio
    async def test_get_events(self):
        eb = EventBus()
        await eb.emit("test.a")
        await eb.emit("test.b")
        events = eb.get_events()
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_stats(self):
        eb = EventBus()
        async def h(d): pass
        eb.subscribe("test", h)
        await eb.emit("test")
        stats = eb.get_stats()
        assert stats["total_subscriptions"] == 1
        assert stats["total_events_emitted"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert event_bus is not None
        assert isinstance(event_bus, EventBus)
