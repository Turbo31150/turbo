"""Event Store — Append-only event log with streams, snapshots, and replay."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable


@dataclass
class Event:
    stream: str
    event_type: str
    data: dict
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    version: int = 0


@dataclass
class Snapshot:
    stream: str
    state: dict
    version: int
    timestamp: float = field(default_factory=time.time)


class EventStore:
    """Append-only event log with stream-based organization."""

    def __init__(self, max_events: int = 10000):
        self._events: list[Event] = []
        self._snapshots: dict[str, Snapshot] = {}
        self._projections: dict[str, Callable] = {}
        self._subscribers: dict[str, list[Callable]] = {}
        self._max_events = max_events
        self._lock = Lock()

    # ── Append ──────────────────────────────────────────────────────
    def append(self, stream: str, event_type: str, data: dict | None = None) -> Event:
        with self._lock:
            version = sum(1 for e in self._events if e.stream == stream) + 1
            evt = Event(stream=stream, event_type=event_type, data=data or {}, version=version)
            self._events.append(evt)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]
            # Notify subscribers
            for cb in self._subscribers.get(stream, []):
                try:
                    cb(evt)
                except Exception:
                    pass
            for cb in self._subscribers.get("*", []):
                try:
                    cb(evt)
                except Exception:
                    pass
            return evt

    # ── Query ───────────────────────────────────────────────────────
    def get_stream(self, stream: str, since_version: int = 0) -> list[Event]:
        with self._lock:
            return [e for e in self._events if e.stream == stream and e.version > since_version]

    def get_all(self, limit: int = 100, since: float = 0) -> list[Event]:
        with self._lock:
            filtered = [e for e in self._events if e.timestamp > since] if since else list(self._events)
            return filtered[-limit:]

    def get_by_type(self, event_type: str, limit: int = 50) -> list[Event]:
        with self._lock:
            return [e for e in self._events if e.event_type == event_type][-limit:]

    def count(self, stream: str | None = None) -> int:
        with self._lock:
            if stream:
                return sum(1 for e in self._events if e.stream == stream)
            return len(self._events)

    def streams(self) -> list[str]:
        with self._lock:
            return list(dict.fromkeys(e.stream for e in self._events))

    # ── Snapshots ───────────────────────────────────────────────────
    def save_snapshot(self, stream: str, state: dict) -> Snapshot:
        with self._lock:
            version = sum(1 for e in self._events if e.stream == stream)
            snap = Snapshot(stream=stream, state=state, version=version)
            self._snapshots[stream] = snap
            return snap

    def get_snapshot(self, stream: str) -> Snapshot | None:
        return self._snapshots.get(stream)

    # ── Replay ──────────────────────────────────────────────────────
    def replay(self, stream: str, reducer: Callable[[dict, Event], dict],
               initial: dict | None = None) -> dict:
        snap = self._snapshots.get(stream)
        if snap:
            state = dict(snap.state)
            events = self.get_stream(stream, since_version=snap.version)
        else:
            state = dict(initial or {})
            events = self.get_stream(stream)
        for evt in events:
            state = reducer(state, evt)
        return state

    # ── Projections ─────────────────────────────────────────────────
    def register_projection(self, name: str, reducer: Callable[[dict, Event], dict]):
        self._projections[name] = reducer

    def project(self, name: str, stream: str, initial: dict | None = None) -> dict | None:
        reducer = self._projections.get(name)
        if not reducer:
            return None
        return self.replay(stream, reducer, initial)

    # ── Subscriptions ───────────────────────────────────────────────
    def subscribe(self, stream: str, callback: Callable[[Event], None]):
        self._subscribers.setdefault(stream, []).append(callback)

    def unsubscribe(self, stream: str):
        self._subscribers.pop(stream, None)

    # ── Stats ───────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with self._lock:
            stream_set = set(e.stream for e in self._events)
            type_set = set(e.event_type for e in self._events)
            return {
                "total_events": len(self._events),
                "streams": len(stream_set),
                "event_types": len(type_set),
                "snapshots": len(self._snapshots),
                "projections": len(self._projections),
                "subscribers": sum(len(v) for v in self._subscribers.values()),
                "max_events": self._max_events,
            }


event_store = EventStore()
