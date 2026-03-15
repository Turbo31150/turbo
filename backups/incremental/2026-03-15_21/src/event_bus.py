"""JARVIS Event Bus — Internal async pub/sub for inter-module communication.

Replaces direct cross-imports with loose coupling via events.
Supports wildcards, priorities, and async handlers.

Usage:
    from src.event_bus import event_bus

    async def on_node_offline(data):
        print(f"Node {data['node']} went offline")

    event_bus.subscribe("cluster.node_offline", on_node_offline)
    await event_bus.emit("cluster.node_offline", {"node": "M2"})
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger("jarvis.events")

Handler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class Subscription:
    """A single event subscription."""
    pattern: str
    handler: Handler
    priority: int = 0
    regex: re.Pattern | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        # Convert wildcard pattern to regex
        escaped = re.escape(self.pattern).replace(r"\*", ".*")
        self.regex = re.compile(f"^{escaped}$")

    def matches(self, event: str) -> bool:
        return bool(self.regex and self.regex.match(event))


class EventBus:
    """Async pub/sub event bus with wildcard support."""

    def __init__(self) -> None:
        self._subs: list[Subscription] = []
        self._event_log: list[dict[str, Any]] = []
        self._max_log = 500
        self._stats: dict[str, int] = defaultdict(int)

    def subscribe(self, pattern: str, handler: Handler, priority: int = 0) -> Callable[[], None]:
        """Subscribe to events matching pattern. Returns unsubscribe function.

        Patterns:
        - "cluster.node_offline" — exact match
        - "cluster.*" — any cluster event
        - "*" — all events
        """
        sub = Subscription(pattern=pattern, handler=handler, priority=priority)
        self._subs.append(sub)
        self._subs.sort(key=lambda s: s.priority, reverse=True)

        def unsubscribe() -> None:
            if sub in self._subs:
                self._subs.remove(sub)

        return unsubscribe

    async def emit(self, event: str, data: dict[str, Any] | None = None) -> int:
        """Emit an event. Returns number of handlers called."""
        data = data or {}
        self._stats[event] += 1

        # Log event
        self._event_log.append({
            "ts": time.time(),
            "event": event,
            "data_keys": list(data.keys()),
        })
        if len(self._event_log) > self._max_log:
            self._event_log = self._event_log[-self._max_log:]

        # Find matching handlers
        matching = [s for s in self._subs if s.matches(event)]
        if not matching:
            return 0

        called = 0
        for sub in matching:
            try:
                await sub.handler(data)
                called += 1
            except Exception as e:
                logger.warning("Event handler error for %s (%s): %s", event, sub.pattern, e)

        return called

    def emit_sync(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Fire-and-forget emit from sync context. Creates a task if loop is running."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event, data))
        except RuntimeError:
            # No running loop, skip
            self._stats[event] += 1

    def clear(self) -> None:
        """Remove all subscriptions."""
        self._subs.clear()

    def subscriber_count(self, event: str | None = None) -> int:
        """Count subscribers, optionally for a specific event."""
        if event is None:
            return len(self._subs)
        return sum(1 for s in self._subs if s.matches(event))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent events."""
        return self._event_log[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Event bus stats."""
        return {
            "total_subscriptions": len(self._subs),
            "total_events_emitted": sum(self._stats.values()),
            "event_counts": dict(self._stats),
            "log_size": len(self._event_log),
        }


# Global singleton
event_bus = EventBus()
