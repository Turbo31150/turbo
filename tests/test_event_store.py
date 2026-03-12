"""Tests for src/event_store.py — Append-only event log.

Covers: Event, Snapshot, EventStore (append, get_stream, get_all, get_by_type,
count, streams, save_snapshot, get_snapshot, replay, register_projection,
project, subscribe, unsubscribe, get_stats), event_store singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.event_store import Event, Snapshot, EventStore, event_store


# ===========================================================================
# Event & Snapshot dataclasses
# ===========================================================================

class TestDataclasses:
    def test_event(self):
        e = Event(stream="orders", event_type="created", data={"id": 1})
        assert e.stream == "orders"
        assert e.version == 0

    def test_snapshot(self):
        s = Snapshot(stream="orders", state={"total": 5}, version=3)
        assert s.version == 3


# ===========================================================================
# EventStore — append & query
# ===========================================================================

class TestAppendQuery:
    def test_append(self):
        es = EventStore()
        evt = es.append("orders", "created", {"id": 1})
        assert evt.version == 1
        assert evt.stream == "orders"

    def test_versioning(self):
        es = EventStore()
        es.append("orders", "created")
        es.append("orders", "updated")
        events = es.get_stream("orders")
        assert events[0].version == 1
        assert events[1].version == 2

    def test_get_stream(self):
        es = EventStore()
        es.append("orders", "created")
        es.append("users", "joined")
        assert len(es.get_stream("orders")) == 1

    def test_get_stream_since_version(self):
        es = EventStore()
        es.append("orders", "a")
        es.append("orders", "b")
        es.append("orders", "c")
        events = es.get_stream("orders", since_version=1)
        assert len(events) == 2

    def test_get_all(self):
        es = EventStore()
        es.append("a", "x")
        es.append("b", "y")
        assert len(es.get_all()) == 2

    def test_get_by_type(self):
        es = EventStore()
        es.append("a", "created")
        es.append("b", "deleted")
        es.append("c", "created")
        assert len(es.get_by_type("created")) == 2

    def test_count(self):
        es = EventStore()
        es.append("a", "x")
        es.append("a", "y")
        es.append("b", "z")
        assert es.count() == 3
        assert es.count("a") == 2

    def test_streams(self):
        es = EventStore()
        es.append("orders", "x")
        es.append("users", "y")
        assert set(es.streams()) == {"orders", "users"}

    def test_max_events(self):
        es = EventStore(max_events=5)
        for i in range(10):
            es.append("s", "e", {"i": i})
        assert es.count() == 5


# ===========================================================================
# EventStore — snapshots & replay
# ===========================================================================

class TestSnapshotReplay:
    def test_snapshot(self):
        es = EventStore()
        es.append("orders", "created")
        snap = es.save_snapshot("orders", {"count": 1})
        assert snap.version == 1
        assert es.get_snapshot("orders") is not None

    def test_get_snapshot_none(self):
        es = EventStore()
        assert es.get_snapshot("nope") is None

    def test_replay(self):
        es = EventStore()
        es.append("counter", "increment", {"value": 1})
        es.append("counter", "increment", {"value": 2})

        def reducer(state, event):
            state["total"] = state.get("total", 0) + event.data.get("value", 0)
            return state

        result = es.replay("counter", reducer)
        assert result["total"] == 3

    def test_replay_with_snapshot(self):
        es = EventStore()
        es.append("counter", "inc", {"v": 1})
        es.save_snapshot("counter", {"total": 1})
        es.append("counter", "inc", {"v": 5})

        def reducer(state, event):
            state["total"] = state.get("total", 0) + event.data.get("v", 0)
            return state

        result = es.replay("counter", reducer)
        assert result["total"] == 6


# ===========================================================================
# EventStore — projections
# ===========================================================================

class TestProjections:
    def test_project(self):
        es = EventStore()
        es.append("counter", "add", {"n": 3})
        es.append("counter", "add", {"n": 7})
        es.register_projection("sum", lambda s, e: {**s, "total": s.get("total", 0) + e.data.get("n", 0)})
        result = es.project("sum", "counter")
        assert result["total"] == 10

    def test_project_nonexistent(self):
        es = EventStore()
        assert es.project("nope", "x") is None


# ===========================================================================
# EventStore — subscriptions
# ===========================================================================

class TestSubscriptions:
    def test_subscribe(self):
        es = EventStore()
        received = []
        es.subscribe("orders", lambda e: received.append(e))
        es.append("orders", "created")
        assert len(received) == 1

    def test_wildcard_subscribe(self):
        es = EventStore()
        received = []
        es.subscribe("*", lambda e: received.append(e))
        es.append("orders", "x")
        es.append("users", "y")
        assert len(received) == 2

    def test_unsubscribe(self):
        es = EventStore()
        es.subscribe("orders", lambda e: None)
        es.unsubscribe("orders")
        # No error after unsubscribe
        es.append("orders", "x")


# ===========================================================================
# EventStore — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        es = EventStore()
        es.append("a", "created")
        es.append("b", "deleted")
        es.save_snapshot("a", {})
        es.register_projection("p", lambda s, e: s)
        es.subscribe("a", lambda e: None)
        stats = es.get_stats()
        assert stats["total_events"] == 2
        assert stats["streams"] == 2
        assert stats["event_types"] == 2
        assert stats["snapshots"] == 1
        assert stats["projections"] == 1
        assert stats["subscribers"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert event_store is not None
        assert isinstance(event_store, EventStore)
