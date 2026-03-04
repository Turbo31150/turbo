"""
agent_communication.py - Communication inter-agents
Message bus async pub/sub, request/response delegation, broadcast alertes
Pour F:\BUREAU\turbo\src\
"""

import asyncio
import json
import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger("jarvis.comm")

# ──────────────────── Message Types ────────────────────

class MessageType(str, Enum):
    EVENT = "event"           # Fire-and-forget
    REQUEST = "request"       # Expects response
    RESPONSE = "response"     # Response to request
    BROADCAST = "broadcast"   # Cluster-wide alert
    HEARTBEAT = "heartbeat"   # Agent alive signal

class MessagePriority(int, Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3

# ──────────────────── Message Model ────────────────────

@dataclass
class Message:
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    msg_type: MessageType = MessageType.EVENT
    topic: str = ""
    sender: str = ""
    target: Optional[str] = None  # None = broadcast
    payload: dict = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: Optional[str] = None  # For request/response
    timestamp: float = field(default_factory=time.time)
    ttl: float = 60.0  # seconds
    hops: int = 0

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "topic": self.topic,
            "sender": self.sender,
            "target": self.target,
            "payload": self.payload,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
            "hops": self.hops,
        }

    def to_bytes(self) -> bytes:
        """Sérialisation MessagePack-like (JSON fallback)."""
        try:
            import msgpack
            return msgpack.packb(self.to_dict(), use_bin_type=True)
        except ImportError:
            return json.dumps(self.to_dict(), default=str).encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        try:
            import msgpack
            d = msgpack.unpackb(data, raw=False)
        except (ImportError, Exception):
            d = json.loads(data.decode())
        return cls(
            msg_id=d.get("msg_id", ""),
            msg_type=MessageType(d.get("msg_type", "event")),
            topic=d.get("topic", ""),
            sender=d.get("sender", ""),
            target=d.get("target"),
            payload=d.get("payload", {}),
            priority=MessagePriority(d.get("priority", 2)),
            correlation_id=d.get("correlation_id"),
            timestamp=d.get("timestamp", time.time()),
            ttl=d.get("ttl", 60.0),
            hops=d.get("hops", 0),
        )# ──────────────────── Subscription ────────────────────

@dataclass
class Subscription:
    sub_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic_pattern: str = ""  # e.g. "agent.*", "trading.signal"
    handler: Optional[Callable] = None
    queue: Optional[asyncio.Queue] = None
    agent_id: str = ""

    def matches(self, topic: str) -> bool:
        """Glob-like matching: 'agent.*' matches 'agent.start', 'agent.stop'."""
        parts = self.topic_pattern.split(".")
        topic_parts = topic.split(".")
        for i, pat in enumerate(parts):
            if pat == "*":
                return True
            if i >= len(topic_parts) or pat != topic_parts[i]:
                return False
        return len(parts) == len(topic_parts)

# ──────────────────── Message Bus ────────────────────

class MessageBus:
    """Bus de messages async pub/sub inter-agents."""

    def __init__(self, max_queue_size: int = 10000):
        self._subscriptions: list[Subscription] = []
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._message_log: list[dict] = []
        self._max_log = 1000
        self._stats = {
            "published": 0,
            "delivered": 0,
            "dropped": 0,
            "requests": 0,
            "responses": 0,
        }
        self._lock = asyncio.Lock()

    # ──── Pub/Sub ────

    def subscribe(
        self,
        topic_pattern: str,
        handler: Optional[Callable] = None,
        agent_id: str = "",
    ) -> Subscription:
        """S'abonner à un topic. Handler reçoit (Message)."""
        sub = Subscription(
            topic_pattern=topic_pattern,
            handler=handler,
            queue=asyncio.Queue(maxsize=1000) if not handler else None,
            agent_id=agent_id,
        )
        self._subscriptions.append(sub)
        logger.debug(f"Subscribed {agent_id} to '{topic_pattern}'")
        return sub

    def unsubscribe(self, sub_id: str):
        self._subscriptions = [s for s in self._subscriptions if s.sub_id != sub_id]

    async def publish(self, message: Message):
        """Publier un message sur le bus."""
        self._stats["published"] += 1
        self._log_message(message)

        # Check TTL
        if time.time() - message.timestamp > message.ttl:
            self._stats["dropped"] += 1
            return

        # Check if it's a response to a pending request
        if message.msg_type == MessageType.RESPONSE and message.correlation_id:
            self._stats["responses"] += 1
            future = self._pending_responses.pop(message.correlation_id, None)
            if future and not future.done():
                future.set_result(message)
            return

        # Dispatch to matching subscribers
        for sub in self._subscriptions:
            if not sub.matches(message.topic):
                continue
            if message.target and sub.agent_id and message.target != sub.agent_id:
                continue

            try:
                if sub.handler:
                    asyncio.create_task(self._safe_call(sub.handler, message))
                elif sub.queue:
                    try:
                        sub.queue.put_nowait(message)
                    except asyncio.QueueFull:
                        self._stats["dropped"] += 1
                self._stats["delivered"] += 1
            except Exception as e:
                logger.error(f"Error delivering to {sub.sub_id}: {e}")

    async def _safe_call(self, handler: Callable, message: Message):
        try:
            result = handler(message)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Handler error for {message.topic}: {e}")
    # ──── Request/Response ────

    async def request(
        self,
        topic: str,
        payload: dict,
        sender: str,
        target: Optional[str] = None,
        timeout: float = 30.0,
    ) -> Optional[Message]:
        """Envoyer une requête et attendre la réponse."""
        correlation_id = str(uuid.uuid4())[:12]
        self._stats["requests"] += 1

        # Create future for response
        future: asyncio.Future[Message] = asyncio.get_event_loop().create_future()
        self._pending_responses[correlation_id] = future

        # Send request
        msg = Message(
            msg_type=MessageType.REQUEST,
            topic=topic,
            sender=sender,
            target=target,
            payload=payload,
            correlation_id=correlation_id,
        )
        await self.publish(msg)

        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self._pending_responses.pop(correlation_id, None)
            logger.warning(f"Request timeout: {topic} from {sender}")
            return None

    async def respond(
        self,
        original: Message,
        payload: dict,
        sender: str,
    ):
        """Répondre à une requête."""
        response = Message(
            msg_type=MessageType.RESPONSE,
            topic=f"{original.topic}.response",
            sender=sender,
            target=original.sender,
            payload=payload,
            correlation_id=original.correlation_id,
        )
        await self.publish(response)

    # ──── Broadcast ────

    async def broadcast(
        self,
        topic: str,
        payload: dict,
        sender: str,
        priority: MessagePriority = MessagePriority.HIGH,
    ):
        """Broadcast cluster-wide alert."""
        msg = Message(
            msg_type=MessageType.BROADCAST,
            topic=topic,
            sender=sender,
            payload=payload,
            priority=priority,
        )
        await self.publish(msg)
        logger.info(f"BROADCAST [{topic}] from {sender}: {payload.get('message', '')}")

    # ──── Convenience Methods ────

    async def emit(self, topic: str, payload: dict, sender: str = "system"):
        """Fire-and-forget event."""
        await self.publish(Message(
            msg_type=MessageType.EVENT, topic=topic,
            sender=sender, payload=payload,
        ))

    # ──── Delegation ────

    async def delegate_task(
        self,
        task_name: str,
        payload: dict,
        sender: str,
        target_agent: str,
        timeout: float = 60.0,
    ) -> Optional[dict]:
        """Déléguer une sous-tâche à un agent spécifique."""
        response = await self.request(
            topic=f"agent.{target_agent}.task",
            payload={"task_name": task_name, **payload},
            sender=sender,
            target=target_agent,
            timeout=timeout,
        )
        if response:
            return response.payload
        return None
    # ──── Logging ────

    def _log_message(self, message: Message):
        self._message_log.append(message.to_dict())
        if len(self._message_log) > self._max_log:
            self._message_log = self._message_log[-500:]

    def get_recent_messages(self, limit: int = 50, topic: Optional[str] = None) -> list[dict]:
        msgs = self._message_log
        if topic:
            msgs = [m for m in msgs if m["topic"].startswith(topic)]
        return msgs[-limit:]

    def replay(self, topic: str, since: float = 0, limit: int = 1000) -> list[dict]:
        """Replay messages depuis un timestamp."""
        return [
            m for m in self._message_log
            if m["topic"].startswith(topic) and m["timestamp"] >= since
        ][:limit]

    # ──── Stats ────

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "subscriptions": len(self._subscriptions),
            "pending_responses": len(self._pending_responses),
            "log_size": len(self._message_log),
        }


# ──────────────────── Global Bus Instance ────────────────────

_bus: Optional[MessageBus] = None

def get_bus() -> MessageBus:
    global _bus
    if _bus is None:
        _bus = MessageBus()
    return _bus


# ──────────────────── Agent Communication Mixin ────────────────────

class CommunicatingAgent:
    """Mixin pour ajouter la communication à un AutonomousAgent."""

    def __init__(self, agent_id: str):
        self._comm_agent_id = agent_id
        self._bus = get_bus()
        self._subscriptions: list[Subscription] = []

    def listen(self, topic_pattern: str, handler: Callable):
        sub = self._bus.subscribe(topic_pattern, handler, self._comm_agent_id)
        self._subscriptions.append(sub)

    async def say(self, topic: str, payload: dict):
        await self._bus.emit(topic, payload, self._comm_agent_id)

    async def ask(self, topic: str, payload: dict, target: Optional[str] = None, timeout: float = 30.0):
        return await self._bus.request(topic, payload, self._comm_agent_id, target, timeout)

    async def reply(self, original: Message, payload: dict):
        await self._bus.respond(original, payload, self._comm_agent_id)

    async def alert(self, message: str, level: str = "warning"):
        await self._bus.broadcast(
            f"system.alert.{level}",
            {"message": message, "agent": self._comm_agent_id, "level": level},
            self._comm_agent_id,
            priority=MessagePriority.CRITICAL if level == "critical" else MessagePriority.HIGH,
        )

    async def delegate(self, task_name: str, payload: dict, target_agent: str, timeout: float = 60.0):
        return await self._bus.delegate_task(task_name, payload, self._comm_agent_id, target_agent, timeout)

    def cleanup_comm(self):
        for sub in self._subscriptions:
            self._bus.unsubscribe(sub.sub_id)
        self._subscriptions.clear()