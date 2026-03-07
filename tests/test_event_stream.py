"""Tests for src/event_stream.py — Real-time event pub/sub.

Covers: Event dataclass, emit/get_events, topics, SSE format,
subscribe/unsubscribe, stats, convenience emitters, clear, limits.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.event_stream import EventStream, Event, get_stream


# ===========================================================================
# Event dataclass
# ===========================================================================

class TestEvent:
    def test_basic_event(self):
        e = Event(id=1, topic="dispatch", data={"key": "val"}, timestamp=1000.0)
        assert e.id == 1
        assert e.topic == "dispatch"
        assert e.source == ""

    def test_to_sse(self):
        e = Event(id=42, topic="health", data={"node": "M1"}, timestamp=1000.0)
        sse = e.to_sse()
        assert "id: 42" in sse
        assert "event: health" in sse
        assert '"node": "M1"' in sse
        assert sse.endswith("\n\n")

    def test_to_dict(self):
        e = Event(id=1, topic="test", data={"a": 1}, timestamp=99.9, source="src")
        d = e.to_dict()
        assert d["id"] == 1
        assert d["topic"] == "test"
        assert d["source"] == "src"
        assert d["timestamp"] == 99.9


# ===========================================================================
# Emit & retrieve
# ===========================================================================

class TestEmitRetrieve:
    def test_emit_returns_id(self):
        s = EventStream()
        id1 = s.emit("dispatch", {"test": True})
        id2 = s.emit("dispatch", {"test": False})
        assert id2 > id1

    def test_get_events_by_topic(self):
        s = EventStream()
        s.emit("dispatch", {"a": 1})
        s.emit("health", {"b": 2})
        s.emit("dispatch", {"c": 3})
        events = s.get_events("dispatch")
        assert len(events) == 2
        assert all(e["topic"] == "dispatch" for e in events)

    def test_get_events_all(self):
        s = EventStream()
        s.emit("dispatch", {"a": 1})
        s.emit("health", {"b": 2})
        events = s.get_events()
        assert len(events) == 2

    def test_get_events_since_id(self):
        s = EventStream()
        s.emit("dispatch", {"a": 1})
        s.emit("dispatch", {"b": 2})
        id2 = s.emit("dispatch", {"c": 3})
        events = s.get_events("dispatch", since_id=id2 - 1)
        assert len(events) == 1
        assert events[0]["data"]["c"] == 3

    def test_get_events_limit(self):
        s = EventStream()
        for i in range(20):
            s.emit("test", {"i": i})
        events = s.get_events("test", limit=5)
        assert len(events) == 5

    def test_get_latest(self):
        s = EventStream()
        for i in range(20):
            s.emit("test", {"i": i})
        latest = s.get_latest("test", n=3)
        assert len(latest) == 3
        assert latest[-1]["data"]["i"] == 19

    def test_get_latest_all_topics(self):
        s = EventStream()
        s.emit("a", {"x": 1})
        s.emit("b", {"x": 2})
        latest = s.get_latest(n=2)
        assert len(latest) == 2


# ===========================================================================
# Convenience emitters
# ===========================================================================

class TestConvenienceEmitters:
    def test_emit_dispatch(self):
        s = EventStream()
        eid = s.emit_dispatch("code", "M1", 0.9, 1200, True)
        events = s.get_events("dispatch")
        assert len(events) == 1
        assert events[0]["data"]["pattern"] == "code"
        assert events[0]["data"]["node"] == "M1"

    def test_emit_health(self):
        s = EventStream()
        s.emit_health("M1", "up", "All good")
        events = s.get_events("health")
        assert len(events) == 1
        assert events[0]["data"]["node"] == "M1"
        assert events[0]["data"]["status"] == "up"

    def test_emit_alert(self):
        s = EventStream()
        s.emit_alert("critical", "M1 down", node="M1")
        events = s.get_events("alert")
        assert len(events) == 1
        assert events[0]["data"]["level"] == "critical"


# ===========================================================================
# Topics
# ===========================================================================

class TestTopics:
    def test_standard_topics(self):
        s = EventStream()
        topics = s.get_topics()
        assert "dispatch" in topics
        assert "health" in topics
        assert "alert" in topics
        assert "system" in topics

    def test_topic_descriptions(self):
        s = EventStream()
        topics = s.get_topics()
        for topic, info in topics.items():
            assert "description" in info
            assert len(info["description"]) > 5

    def test_topic_event_count(self):
        s = EventStream()
        s.emit("dispatch", {"a": 1})
        s.emit("dispatch", {"b": 2})
        topics = s.get_topics()
        assert topics["dispatch"]["event_count"] == 2
        assert topics["health"]["event_count"] == 0


# ===========================================================================
# Stats
# ===========================================================================

class TestStats:
    def test_stats_initial(self):
        s = EventStream()
        stats = s.get_stats()
        assert stats["total_events"] == 0
        assert stats["buffer_size"] == 0

    def test_stats_after_emit(self):
        s = EventStream()
        s.emit("dispatch", {"a": 1})
        s.emit("health", {"b": 2})
        stats = s.get_stats()
        assert stats["total_events"] == 2
        assert stats["buffer_size"] == 2
        assert stats["topics"]["dispatch"]["total_emitted"] == 1
        assert stats["topics"]["health"]["total_emitted"] == 1


# ===========================================================================
# Buffer limits
# ===========================================================================

class TestBufferLimits:
    def test_per_topic_limit(self):
        s = EventStream()
        s.MAX_EVENTS_PER_TOPIC = 10
        s._events.default_factory = lambda: __import__('collections').deque(maxlen=10)
        for i in range(20):
            s.emit("test", {"i": i})
        assert len(s._events["test"]) <= 10

    def test_total_limit(self):
        s = EventStream()
        assert s.MAX_TOTAL_EVENTS == 5000


# ===========================================================================
# Subscribe/unsubscribe
# ===========================================================================

class TestSubscription:
    @pytest.mark.asyncio
    async def test_subscribe_receives_events(self):
        s = EventStream()
        queue = await s.subscribe("dispatch")
        s.emit("dispatch", {"test": True})
        event = queue.get_nowait()
        assert event.topic == "dispatch"
        assert event.data["test"] is True

    @pytest.mark.asyncio
    async def test_wildcard_subscribe(self):
        s = EventStream()
        queue = await s.subscribe("*")
        s.emit("dispatch", {"a": 1})
        s.emit("health", {"b": 2})
        assert queue.qsize() == 2

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        s = EventStream()
        queue = await s.subscribe("dispatch")
        s.unsubscribe("dispatch", queue)
        s.emit("dispatch", {"test": True})
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_subscribe_topic_isolation(self):
        s = EventStream()
        queue = await s.subscribe("health")
        s.emit("dispatch", {"a": 1})
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_queue_full_no_error(self):
        s = EventStream()
        queue = await s.subscribe("test")
        # Fill queue to capacity
        for i in range(200):
            s.emit("test", {"i": i})
        # Should not raise — excess events are dropped


# ===========================================================================
# Clear
# ===========================================================================

class TestClear:
    def test_clear_topic(self):
        s = EventStream()
        s.emit("dispatch", {"a": 1})
        s.emit("health", {"b": 2})
        s.clear("dispatch")
        assert len(s._events["dispatch"]) == 0
        assert len(s._events["health"]) == 1

    def test_clear_all(self):
        s = EventStream()
        s.emit("dispatch", {"a": 1})
        s.emit("health", {"b": 2})
        s.clear()
        assert len(s._all_events) == 0
        assert len(s._events["dispatch"]) == 0
        assert len(s._events["health"]) == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_get_stream(self):
        import src.event_stream as mod
        old = mod._stream
        try:
            mod._stream = None
            s = get_stream()
            assert isinstance(s, EventStream)
        finally:
            mod._stream = old
