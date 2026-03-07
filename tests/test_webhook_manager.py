"""Tests for src/webhook_manager.py — Outbound webhook dispatch with retry.

Covers: WebhookEndpoint, DeliveryRecord, WebhookManager (register, unregister,
get_endpoint, list_endpoints, set_active, sign_payload, verify_signature,
dispatch, get_history, get_stats), webhook_manager singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.webhook_manager import (
    WebhookEndpoint, DeliveryRecord, WebhookManager, webhook_manager,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestWebhookEndpoint:
    def test_defaults(self):
        ep = WebhookEndpoint(name="test", url="https://example.com/hook")
        assert ep.secret == ""
        assert ep.active is True
        assert ep.max_retries == 3


class TestDeliveryRecord:
    def test_defaults(self):
        dr = DeliveryRecord(delivery_id="d1", webhook_name="w1",
                            event="test", url="http://x", payload={})
        assert dr.status == "pending"
        assert dr.attempts == 0


# ===========================================================================
# WebhookManager — endpoint management
# ===========================================================================

class TestEndpoints:
    def test_register(self):
        wm = WebhookManager()
        ep = wm.register("hook1", "https://example.com/hook")
        assert ep.name == "hook1"
        assert wm.get_endpoint("hook1") is ep

    def test_unregister(self):
        wm = WebhookManager()
        wm.register("hook1", "https://example.com")
        assert wm.unregister("hook1") is True
        assert wm.get_endpoint("hook1") is None

    def test_unregister_nonexistent(self):
        wm = WebhookManager()
        assert wm.unregister("nope") is False

    def test_list_endpoints(self):
        wm = WebhookManager()
        wm.register("h1", "http://a")
        wm.register("h2", "http://b")
        eps = wm.list_endpoints()
        assert len(eps) == 2

    def test_set_active(self):
        wm = WebhookManager()
        wm.register("h1", "http://a")
        assert wm.set_active("h1", False) is True
        assert wm.get_endpoint("h1").active is False

    def test_set_active_nonexistent(self):
        wm = WebhookManager()
        assert wm.set_active("nope", True) is False


# ===========================================================================
# WebhookManager — signing
# ===========================================================================

class TestSigning:
    def test_sign_and_verify(self):
        payload = {"event": "test", "data": "hello"}
        secret = "my_secret"
        sig = WebhookManager.sign_payload(payload, secret)
        assert isinstance(sig, str)
        assert WebhookManager.verify_signature(payload, secret, sig) is True

    def test_wrong_signature(self):
        payload = {"event": "test"}
        assert WebhookManager.verify_signature(payload, "secret", "wrong_sig") is False


# ===========================================================================
# WebhookManager — dispatch
# ===========================================================================

class TestDispatch:
    def test_dispatch_success(self):
        wm = WebhookManager()
        wm.register("h1", "http://a")
        wm.set_transport(lambda url, payload, headers: (200, "OK"))
        records = wm.dispatch("test_event", {"key": "val"})
        assert len(records) == 1
        assert records[0].status == "success"
        assert records[0].response_code == 200

    def test_dispatch_failure(self):
        wm = WebhookManager()
        wm.register("h1", "http://a", max_retries=2)
        wm.set_transport(lambda url, payload, headers: (500, "Error"))
        records = wm.dispatch("test_event", {})
        assert records[0].status == "failed"
        assert records[0].attempts == 2

    def test_dispatch_no_transport(self):
        wm = WebhookManager()
        wm.register("h1", "http://a")
        records = wm.dispatch("test", {})
        assert records[0].status == "failed"
        assert "no transport" in records[0].error

    def test_dispatch_event_filter(self):
        wm = WebhookManager()
        wm.register("h1", "http://a", events=["deploy"])
        wm.register("h2", "http://b")  # all events
        wm.set_transport(lambda url, payload, headers: (200, "OK"))
        records = wm.dispatch("test_event", {})
        # h1 filtered out, only h2
        assert len(records) == 1
        assert records[0].webhook_name == "h2"

    def test_dispatch_inactive_skipped(self):
        wm = WebhookManager()
        wm.register("h1", "http://a")
        wm.set_active("h1", False)
        wm.set_transport(lambda url, payload, headers: (200, "OK"))
        records = wm.dispatch("test", {})
        assert len(records) == 0

    def test_dispatch_with_secret(self):
        wm = WebhookManager()
        wm.register("h1", "http://a", secret="s3cret")
        headers_seen = {}
        def capture(url, payload, headers):
            headers_seen.update(headers)
            return (200, "OK")
        wm.set_transport(capture)
        wm.dispatch("test", {"k": "v"})
        assert "X-Signature" in headers_seen

    def test_dispatch_transport_exception(self):
        wm = WebhookManager()
        wm.register("h1", "http://a", max_retries=1)
        wm.set_transport(lambda url, p, h: (_ for _ in ()).throw(ConnectionError("timeout")))
        records = wm.dispatch("test", {})
        assert records[0].status == "failed"


# ===========================================================================
# WebhookManager — history & stats
# ===========================================================================

class TestHistoryStats:
    def test_get_history(self):
        wm = WebhookManager()
        wm.register("h1", "http://a")
        wm.set_transport(lambda u, p, h: (200, "OK"))
        wm.dispatch("e1", {})
        history = wm.get_history()
        assert len(history) == 1

    def test_get_history_filtered(self):
        wm = WebhookManager()
        wm.register("h1", "http://a")
        wm.register("h2", "http://b")
        wm.set_transport(lambda u, p, h: (200, "OK"))
        wm.dispatch("e1", {})
        history = wm.get_history(webhook_name="h1")
        assert len(history) == 1

    def test_stats(self):
        wm = WebhookManager()
        wm.register("h1", "http://a")
        wm.set_transport(lambda u, p, h: (200, "OK"))
        wm.dispatch("e1", {})
        stats = wm.get_stats()
        assert stats["endpoints"] == 1
        assert stats["total_deliveries"] == 1
        assert stats["successful"] == 1

    def test_stats_empty(self):
        wm = WebhookManager()
        stats = wm.get_stats()
        assert stats["total_deliveries"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert webhook_manager is not None
        assert isinstance(webhook_manager, WebhookManager)
