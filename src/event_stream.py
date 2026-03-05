"""JARVIS Event Stream — Real-time event broadcasting for dashboard and consumers.

Implements a pub/sub event bus with:
  - In-memory event queue per topic
  - SSE (Server-Sent Events) compatible output
  - Event history with configurable retention
  - Topic-based filtering (dispatch, health, benchmark, alert, scale)
  - Consumer tracking (who's listening)

Usage:
    from src.event_stream import EventStream, get_stream
    stream = get_stream()
    stream.emit("dispatch", {"pattern": "code", "node": "M1", "quality": 0.9})
    events = stream.get_events("dispatch", since_id=42)
    # SSE generator for FastAPI:
    async for event in stream.sse_generator("dispatch"):
        yield event
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

logger = logging.getLogger("jarvis.event_stream")


@dataclass
class Event:
    """A single event in the stream."""
    id: int
    topic: str
    data: dict
    timestamp: float
    source: str = ""

    def to_sse(self) -> str:
        """Format as SSE (Server-Sent Events) line."""
        return f"id: {self.id}\nevent: {self.topic}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
        }


class EventStream:
    """Real-time event broadcasting system."""

    # Standard topics
    TOPICS = {
        "dispatch": "Agent dispatch events (start, complete, fail)",
        "health": "Node health changes (up, down, degraded)",
        "benchmark": "Benchmark progress and results",
        "alert": "System alerts (quality drop, latency spike, error burst)",
        "scale": "Auto-scaling events (scale up, down, redistribute)",
        "feedback": "Quality feedback events",
        "discovery": "Pattern discovery events",
        "memory": "Episodic memory events (store, recall)",
        "pipeline": "Full pipeline events (dispatch_engine)",
        "system": "System events (startup, shutdown, config change)",
    }

    MAX_EVENTS_PER_TOPIC = 500
    MAX_TOTAL_EVENTS = 5000

    def __init__(self):
        self._events: dict[str, deque[Event]] = defaultdict(lambda: deque(maxlen=self.MAX_EVENTS_PER_TOPIC))
        self._all_events: deque[Event] = deque(maxlen=self.MAX_TOTAL_EVENTS)
        self._counter = 0
        self._consumers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._stats = defaultdict(int)

    def emit(self, topic: str, data: dict, source: str = ""):
        """Emit an event to a topic."""
        self._counter += 1
        event = Event(
            id=self._counter,
            topic=topic,
            data=data,
            timestamp=time.time(),
            source=source,
        )

        self._events[topic].append(event)
        self._all_events.append(event)
        self._stats[topic] += 1

        # Notify async consumers
        for queue in self._consumers.get(topic, []):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Consumer too slow, drop

        # Also notify "all" subscribers
        for queue in self._consumers.get("*", []):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        return event.id

    def emit_dispatch(self, pattern: str, node: str, quality: float,
                      latency_ms: float, success: bool, **extra):
        """Convenience: emit a dispatch event."""
        return self.emit("dispatch", {
            "pattern": pattern, "node": node,
            "quality": quality, "latency_ms": latency_ms,
            "success": success, **extra,
        }, source="dispatch_engine")

    def emit_health(self, node: str, status: str, detail: str = ""):
        """Convenience: emit a health event."""
        return self.emit("health", {
            "node": node, "status": status, "detail": detail,
        }, source="health_guardian")

    def emit_alert(self, level: str, message: str, pattern: str = "", node: str = ""):
        """Convenience: emit an alert event."""
        return self.emit("alert", {
            "level": level, "message": message,
            "pattern": pattern, "node": node,
        }, source="alert_system")

    def get_events(self, topic: Optional[str] = None,
                   since_id: int = 0, limit: int = 100) -> list[dict]:
        """Get events, optionally filtered by topic and since_id."""
        if topic:
            source = self._events.get(topic, deque())
        else:
            source = self._all_events

        events = [e.to_dict() for e in source if e.id > since_id]
        return events[-limit:]

    def get_latest(self, topic: Optional[str] = None, n: int = 10) -> list[dict]:
        """Get N most recent events."""
        if topic:
            source = list(self._events.get(topic, deque()))
        else:
            source = list(self._all_events)
        return [e.to_dict() for e in source[-n:]]

    async def subscribe(self, topic: str = "*") -> asyncio.Queue:
        """Subscribe to events (returns an async queue to read from)."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._consumers[topic].append(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue):
        """Unsubscribe from events."""
        consumers = self._consumers.get(topic, [])
        if queue in consumers:
            consumers.remove(queue)

    async def sse_generator(self, topic: str = "*",
                            timeout: float = 30.0) -> AsyncGenerator[str, None]:
        """Generate SSE events for streaming HTTP responses.

        Usage with FastAPI:
            @app.get("/events/{topic}")
            async def stream(topic: str):
                return StreamingResponse(
                    get_stream().sse_generator(topic),
                    media_type="text/event-stream"
                )
        """
        queue = await self.subscribe(topic)
        try:
            # Send initial heartbeat
            yield f": connected to {topic}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=timeout)
                    yield event.to_sse()
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive {time.time():.0f}\n\n"
        finally:
            self.unsubscribe(topic, queue)

    def get_stats(self) -> dict:
        """Event stream statistics."""
        return {
            "total_events": self._counter,
            "topics": {
                topic: {
                    "total_emitted": self._stats.get(topic, 0),
                    "in_buffer": len(self._events.get(topic, deque())),
                    "consumers": len(self._consumers.get(topic, [])),
                }
                for topic in self.TOPICS
            },
            "all_consumers": sum(len(q) for q in self._consumers.values()),
            "buffer_size": len(self._all_events),
        }

    def get_topics(self) -> dict:
        """List available topics with descriptions."""
        return {
            topic: {
                "description": desc,
                "event_count": self._stats.get(topic, 0),
                "buffered": len(self._events.get(topic, deque())),
            }
            for topic, desc in self.TOPICS.items()
        }

    def clear(self, topic: Optional[str] = None):
        """Clear events for a topic or all events."""
        if topic:
            self._events[topic].clear()
        else:
            for t in self._events:
                self._events[t].clear()
            self._all_events.clear()


# Singleton
_stream: Optional[EventStream] = None

def get_stream() -> EventStream:
    global _stream
    if _stream is None:
        _stream = EventStream()
    return _stream
