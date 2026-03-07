"""Tests for src/message_broker.py — In-memory pub/sub.

Covers: Message, MessageBroker (subscribe, unsubscribe, list_topics,
subscriber_count, publish, get_messages, get_dlq, clear_dlq, get_stats),
message_broker singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.message_broker import Message, MessageBroker, message_broker


class TestMessage:
    def test_defaults(self):
        m = Message(topic="test", payload="data")
        assert m.delivered == 0
        assert m.failed == 0


class TestSubscribe:
    def test_subscribe(self):
        mb = MessageBroker()
        sid = mb.subscribe("orders", lambda m: None)
        assert mb.subscriber_count("orders") == 1

    def test_unsubscribe(self):
        mb = MessageBroker()
        sid = mb.subscribe("orders", lambda m: None)
        assert mb.unsubscribe("orders", sid) is True
        assert mb.subscriber_count("orders") == 0

    def test_unsubscribe_nonexistent(self):
        mb = MessageBroker()
        assert mb.unsubscribe("nope", "x") is False

    def test_list_topics(self):
        mb = MessageBroker()
        mb.subscribe("a", lambda m: None)
        mb.subscribe("b", lambda m: None)
        assert set(mb.list_topics()) == {"a", "b"}


class TestPublish:
    def test_publish(self):
        mb = MessageBroker()
        received = []
        mb.subscribe("orders", lambda m: received.append(m.payload))
        msg = mb.publish("orders", {"id": 1})
        assert msg.delivered == 1
        assert received[0]["id"] == 1

    def test_publish_multiple_subs(self):
        mb = MessageBroker()
        count = [0]
        mb.subscribe("test", lambda m: count.__setitem__(0, count[0] + 1))
        mb.subscribe("test", lambda m: count.__setitem__(0, count[0] + 1))
        mb.publish("test", "data")
        assert count[0] == 2

    def test_wildcard_subscriber(self):
        mb = MessageBroker()
        received = []
        mb.subscribe("*", lambda m: received.append(m.topic))
        mb.publish("orders", "data")
        mb.publish("users", "data")
        assert len(received) == 2

    def test_handler_error_goes_to_dlq(self):
        mb = MessageBroker()
        mb.subscribe("test", lambda m: (_ for _ in ()).throw(RuntimeError("boom")))
        msg = mb.publish("test", "data")
        assert msg.failed == 1
        dlq = mb.get_dlq()
        assert len(dlq) == 1
        assert "boom" in dlq[0]["error"]


class TestMessages:
    def test_get_messages(self):
        mb = MessageBroker()
        mb.publish("a", "x")
        mb.publish("b", "y")
        assert len(mb.get_messages()) == 2
        assert len(mb.get_messages(topic="a")) == 1

    def test_clear_dlq(self):
        mb = MessageBroker()
        mb.subscribe("test", lambda m: (_ for _ in ()).throw(ValueError("err")))
        mb.publish("test", "data")
        assert mb.clear_dlq() == 1
        assert len(mb.get_dlq()) == 0


class TestStats:
    def test_stats(self):
        mb = MessageBroker()
        mb.subscribe("a", lambda m: None)
        mb.publish("a", "data")
        stats = mb.get_stats()
        assert stats["topics"] == 1
        assert stats["total_subscribers"] == 1
        assert stats["total_messages"] == 1
        assert stats["total_delivered"] == 1


class TestSingleton:
    def test_exists(self):
        assert isinstance(message_broker, MessageBroker)
