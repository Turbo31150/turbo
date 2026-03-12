"""
event_bus.py - Bus d'événements asynchrone JARVIS
Pub/sub async, topic persistence SQLite, replay 1000, glob matching, TTL
Pour /home/turbo/jarvis-m1-ops/src/
"""

import asyncio
import fnmatch
import json
import logging
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger("jarvis.event_bus")

# ──────────────────── Event Models ────────────────────

class EventPriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    topic: str
    data: Any
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    source: str = "system"
    priority: EventPriority = EventPriority.NORMAL
    ttl: float = 3600.0  # 1h default
    metadata: dict = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "topic": self.topic,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
            "priority": self.priority.value,
            "ttl": self.ttl,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(
            topic=d["topic"],
            data=d["data"],
            event_id=d.get("event_id", uuid.uuid4().hex[:12]),
            timestamp=d.get("timestamp", time.time()),
            source=d.get("source", "system"),
            priority=EventPriority(d.get("priority", 1)),
            ttl=d.get("ttl", 3600.0),
            metadata=d.get("metadata", {}),
        )


# Type alias for subscriber callbacks
SubscriberCallback = Callable[[Event], Coroutine[Any, Any, None]]


@dataclass
class Subscription:
    sub_id: str
    topic_pattern: str  # Supports glob: "cluster.*", "trading.signals.*"
    callback: SubscriberCallback
    filter_fn: Optional[Callable[[Event], bool]] = None
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)


# ──────────────────── Replay Buffer ────────────────────

class ReplayBuffer:
    """Buffer circulaire pour replay des derniers événements."""

    def __init__(self, maxsize: int = 1000):
        self._buffer: deque[Event] = deque(maxlen=maxsize)
        self._topic_index: dict[str, deque[Event]] = defaultdict(
            lambda: deque(maxlen=200)
        )

    def append(self, event: Event):
        self._buffer.append(event)
        self._topic_index[event.topic].append(event)

    def replay(
        self,
        topic_pattern: str = "*",
        since: Optional[float] = None,
        limit: int = 100,
    ) -> list[Event]:
        """Replay events matching pattern since timestamp."""
        results = []
        for event in reversed(self._buffer):
            if len(results) >= limit:
                break
            if event.is_expired:
                continue
            if since and event.timestamp < since:
                break
            if fnmatch.fnmatch(event.topic, topic_pattern):
                results.append(event)
        return list(reversed(results))

    def replay_topic(self, topic: str, limit: int = 50) -> list[Event]:
        """Replay exact topic."""
        events = list(self._topic_index.get(topic, []))
        return events[-limit:]

    @property
    def size(self) -> int:
        return len(self._buffer)

    def clear(self):
        self._buffer.clear()
        self._topic_index.clear()


# ──────────────────── Event Persistence ────────────────────

class EventStore:
    """Persistence SQLite pour événements."""

    def __init__(self, db_path: str = "jarvis.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    data TEXT,
                    timestamp REAL NOT NULL,
                    source TEXT DEFAULT 'system',
                    priority INTEGER DEFAULT 1,
                    ttl REAL DEFAULT 3600,
                    metadata TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evt_topic ON events(topic)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evt_ts ON events(timestamp)")
            conn.commit()

    def persist(self, event: Event):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO events
                    (event_id, topic, data, timestamp, source, priority, ttl, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id, event.topic,
                    json.dumps(event.data, default=str),
                    event.timestamp, event.source,
                    event.priority.value, event.ttl,
                    json.dumps(event.metadata, default=str),
                ))
        except Exception as e:
            logger.error(f"Event persist error: {e}")

    def query(
        self,
        topic_pattern: str = "*",
        since: Optional[float] = None,
        limit: int = 100,
    ) -> list[dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = "SELECT event_id, topic, data, timestamp, source, priority FROM events WHERE 1=1"
                params: list = []

                if topic_pattern != "*":
                    # Convert glob to SQL LIKE
                    sql_pattern = topic_pattern.replace("*", "%").replace("?", "_")
                    query += " AND topic LIKE ?"
                    params.append(sql_pattern)

                if since:
                    query += " AND timestamp >= ?"
                    params.append(since)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                rows = conn.execute(query, params).fetchall()
                return [
                    {
                        "event_id": r[0], "topic": r[1],
                        "data": json.loads(r[2]) if r[2] else None,
                        "timestamp": r[3], "source": r[4],
                        "priority": r[5],
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Event query error: {e}")
            return []

    def cleanup(self, max_age_hours: float = 72.0) -> int:
        """Supprimer événements expirés."""
        cutoff = time.time() - max_age_hours * 3600
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM events WHERE timestamp < ?", (cutoff,)
                )
                deleted = cursor.rowcount
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old events")
                return deleted
        except Exception:
            return 0

    def count(self) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        except Exception:
            return 0


# ──────────────────── Dead Letter Queue ────────────────────

class DeadLetterQueue:
    """Queue pour événements qui ont échoué après max retries."""

    def __init__(self, maxsize: int = 500):
        self._queue: deque[tuple[Event, str, float]] = deque(maxlen=maxsize)

    def add(self, event: Event, error: str):
        self._queue.append((event, error, time.time()))
        logger.warning(f"DLQ: event {event.event_id} topic={event.topic}: {error}")

    def get_all(self) -> list[dict]:
        return [
            {
                "event": e.to_dict(),
                "error": err,
                "failed_at": ts,
            }
            for e, err, ts in self._queue
        ]

    @property
    def size(self) -> int:
        return len(self._queue)

    def clear(self):
        self._queue.clear()


# ──────────────────── Main Event Bus ────────────────────

class EventBus:
    """Bus d'événements asynchrone avec pub/sub, persistence, replay."""

    def __init__(self, db_path: str = "jarvis.db", persist: bool = True):
        self._subscriptions: dict[str, Subscription] = {}
        self._topic_subs: dict[str, set[str]] = defaultdict(set)
        self._replay = ReplayBuffer(maxsize=1000)
        self._store = EventStore(db_path) if persist else None
        self._dlq = DeadLetterQueue()
        self._persist = persist

        # Metrics
        self._published = 0
        self._delivered = 0
        self._failed = 0
        self._start_time = time.time()

        # Async queue for ordered processing
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=10000)
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None

    # ──── Lifecycle ────

    async def start(self):
        """Démarrer le processeur d'événements."""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_loop())
        logger.info("EventBus started")

    async def stop(self):
        """Arrêter proprement."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        # Flush remaining
        while not self._queue.empty():
            event = self._queue.get_nowait()
            await self._dispatch(event)
        logger.info(f"EventBus stopped. Published={self._published}, Delivered={self._delivered}")

    # ──── Subscribe ────

    def subscribe(
        self,
        topic_pattern: str,
        callback: SubscriberCallback,
        filter_fn: Optional[Callable[[Event], bool]] = None,
        sub_id: Optional[str] = None,
    ) -> str:
        """S'abonner à un topic (glob patterns supportés)."""
        sid = sub_id or f"sub_{uuid.uuid4().hex[:8]}"
        sub = Subscription(
            sub_id=sid,
            topic_pattern=topic_pattern,
            callback=callback,
            filter_fn=filter_fn,
        )
        self._subscriptions[sid] = sub
        self._topic_subs[topic_pattern].add(sid)
        logger.debug(f"Subscribed {sid} to '{topic_pattern}'")
        return sid

    def unsubscribe(self, sub_id: str) -> bool:
        """Se désabonner."""
        sub = self._subscriptions.pop(sub_id, None)
        if sub:
            self._topic_subs[sub.topic_pattern].discard(sub_id)
            logger.debug(f"Unsubscribed {sub_id}")
            return True
        return False

    # ──── Publish ────

    async def publish(self, event: Event):
        """Publier un événement."""
        self._published += 1
        self._replay.append(event)

        if self._persist and self._store:
            self._store.persist(event)

        if self._running:
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Event queue full, dispatching inline")
                await self._dispatch(event)
        else:
            await self._dispatch(event)

    async def emit(self, topic: str, data: Any, source: str = "system", **kwargs):
        """Shortcut pour publier rapidement."""
        event = Event(topic=topic, data=data, source=source, **kwargs)
        await self.publish(event)

    # ──── Processing ────

    async def _process_loop(self):
        """Boucle de traitement asynchrone."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Process loop error: {e}")

    async def _dispatch(self, event: Event):
        """Dispatcher un événement à tous les subscribers matching."""
        if event.is_expired:
            return

        matching_subs = self._find_matching_subs(event.topic)

        for sub in matching_subs:
            # Apply filter
            if sub.filter_fn:
                try:
                    if not sub.filter_fn(event):
                        continue
                except Exception:
                    continue

            # Deliver with retry
            delivered = False
            last_error = ""
            for attempt in range(sub.max_retries):
                try:
                    await asyncio.wait_for(sub.callback(event), timeout=10.0)
                    self._delivered += 1
                    delivered = True
                    break
                except asyncio.TimeoutError:
                    last_error = f"Timeout (attempt {attempt + 1})"
                except Exception as e:
                    last_error = f"{type(e).__name__}: {e} (attempt {attempt + 1})"

                if attempt < sub.max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))

            if not delivered:
                self._failed += 1
                self._dlq.add(event, f"sub={sub.sub_id}: {last_error}")

    def _find_matching_subs(self, topic: str) -> list[Subscription]:
        """Trouver tous les subscribers dont le pattern match le topic."""
        matching = []
        for pattern, sub_ids in self._topic_subs.items():
            if fnmatch.fnmatch(topic, pattern) or pattern == topic:
                for sid in sub_ids:
                    sub = self._subscriptions.get(sid)
                    if sub:
                        matching.append(sub)
        return matching

    # ──── Replay ────

    def replay(
        self,
        topic_pattern: str = "*",
        since: Optional[float] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Replay événements depuis le buffer mémoire."""
        events = self._replay.replay(topic_pattern, since, limit)
        return [e.to_dict() for e in events]

    def query_history(
        self,
        topic_pattern: str = "*",
        since: Optional[float] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query depuis la persistence SQLite."""
        if self._store:
            return self._store.query(topic_pattern, since, limit)
        return self.replay(topic_pattern, since, limit)

    # ──── Metrics ────

    def get_metrics(self) -> dict:
        uptime = time.time() - self._start_time
        return {
            "running": self._running,
            "uptime_seconds": round(uptime, 1),
            "published": self._published,
            "delivered": self._delivered,
            "failed": self._failed,
            "delivery_rate": round(
                self._delivered / max(self._published, 1), 3
            ),
            "queue_depth": self._queue.qsize() if self._running else 0,
            "subscriptions": len(self._subscriptions),
            "topics": len(self._topic_subs),
            "replay_buffer_size": self._replay.size,
            "dlq_size": self._dlq.size,
            "events_per_min": round(
                self._published / max(uptime / 60, 1), 1
            ),
            "persistent_events": self._store.count() if self._store else 0,
        }

    def get_dlq(self) -> list[dict]:
        return self._dlq.get_all()

    # ──── Maintenance ────

    def cleanup(self, max_age_hours: float = 72.0) -> dict:
        """Nettoyage des événements expirés."""
        deleted_db = 0
        if self._store:
            deleted_db = self._store.cleanup(max_age_hours)
        self._dlq.clear()
        return {"deleted_from_db": deleted_db, "dlq_cleared": True}

    def get_topics(self) -> list[dict]:
        """Lister tous les topics actifs avec leurs subscribers."""
        topics = []
        for pattern, sub_ids in self._topic_subs.items():
            topics.append({
                "pattern": pattern,
                "subscribers": len(sub_ids),
                "sub_ids": list(sub_ids),
            })
        return topics
