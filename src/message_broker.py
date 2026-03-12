"""Message Broker — In-memory pub/sub with topics, persistence, and dead letter queue."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable


@dataclass
class Message:
    topic: str
    payload: Any
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    delivered: int = 0
    failed: int = 0


class MessageBroker:
    """In-memory pub/sub message broker with topics."""

    def __init__(self, max_messages: int = 1000, max_dlq: int = 200):
        self._subscribers: dict[str, list[tuple[str, Callable]]] = {}
        self._messages: list[Message] = []
        self._dlq: list[dict] = []
        self._max_messages = max_messages
        self._max_dlq = max_dlq
        self._lock = Lock()

    # ── Subscribe / Unsubscribe ─────────────────────────────────────
    def subscribe(self, topic: str, handler: Callable, subscriber_id: str = "") -> str:
        sid = subscriber_id or uuid.uuid4().hex[:8]
        with self._lock:
            self._subscribers.setdefault(topic, []).append((sid, handler))
        return sid

    def unsubscribe(self, topic: str, subscriber_id: str) -> bool:
        with self._lock:
            subs = self._subscribers.get(topic, [])
            before = len(subs)
            self._subscribers[topic] = [(sid, h) for sid, h in subs if sid != subscriber_id]
            return len(self._subscribers[topic]) < before

    def list_topics(self) -> list[str]:
        with self._lock:
            return list(self._subscribers.keys())

    def subscriber_count(self, topic: str) -> int:
        return len(self._subscribers.get(topic, []))

    # ── Publish ─────────────────────────────────────────────────────
    def publish(self, topic: str, payload: Any) -> Message:
        msg = Message(topic=topic, payload=payload)
        with self._lock:
            self._messages.append(msg)
            if len(self._messages) > self._max_messages:
                self._messages = self._messages[-self._max_messages:]
            subs = list(self._subscribers.get(topic, []))

        for sid, handler in subs:
            try:
                handler(msg)
                msg.delivered += 1
            except Exception as exc:
                msg.failed += 1
                with self._lock:
                    self._dlq.append({
                        "message_id": msg.message_id, "topic": topic,
                        "subscriber": sid, "error": str(exc),
                        "timestamp": time.time(),
                    })
                    if len(self._dlq) > self._max_dlq:
                        self._dlq = self._dlq[-self._max_dlq:]

        # Also deliver to wildcard subscribers
        with self._lock:
            wildcards = list(self._subscribers.get("*", []))
        for sid, handler in wildcards:
            if topic != "*":
                try:
                    handler(msg)
                    msg.delivered += 1
                except Exception:
                    msg.failed += 1

        return msg

    # ── Message History ─────────────────────────────────────────────
    def get_messages(self, topic: str | None = None, limit: int = 50) -> list[dict]:
        with self._lock:
            msgs = self._messages
            if topic:
                msgs = [m for m in msgs if m.topic == topic]
            return [
                {
                    "message_id": m.message_id, "topic": m.topic,
                    "payload": m.payload, "delivered": m.delivered,
                    "failed": m.failed, "timestamp": m.timestamp,
                }
                for m in msgs[-limit:]
            ]

    def get_dlq(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return self._dlq[-limit:]

    def clear_dlq(self) -> int:
        with self._lock:
            count = len(self._dlq)
            self._dlq.clear()
            return count

    # ── Stats ───────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with self._lock:
            total_msgs = len(self._messages)
            total_delivered = sum(m.delivered for m in self._messages)
            total_failed = sum(m.failed for m in self._messages)
            total_subs = sum(len(v) for v in self._subscribers.values())
            return {
                "topics": len(self._subscribers),
                "total_subscribers": total_subs,
                "total_messages": total_msgs,
                "total_delivered": total_delivered,
                "total_failed": total_failed,
                "dlq_size": len(self._dlq),
            }


message_broker = MessageBroker()
