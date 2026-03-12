"""Webhook Manager — Outbound webhook dispatch with retry, HMAC signing, history."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable



__all__ = [
    "DeliveryRecord",
    "WebhookEndpoint",
    "WebhookManager",
]

@dataclass
class WebhookEndpoint:
    name: str
    url: str
    secret: str = ""
    events: list[str] = field(default_factory=list)  # empty = all events
    active: bool = True
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)


@dataclass
class DeliveryRecord:
    delivery_id: str
    webhook_name: str
    event: str
    url: str
    payload: dict
    status: str = "pending"  # pending, success, failed
    attempts: int = 0
    response_code: int = 0
    error: str = ""
    timestamp: float = field(default_factory=time.time)


class WebhookManager:
    """Manages outbound webhook endpoints and delivery."""

    def __init__(self, max_history: int = 500):
        self._endpoints: dict[str, WebhookEndpoint] = {}
        self._history: list[DeliveryRecord] = []
        self._max_history = max_history
        self._transport: Callable | None = None  # injectable for testing
        self._lock = Lock()

    # ── Endpoint Management ─────────────────────────────────────────
    def register(self, name: str, url: str, secret: str = "",
                 events: list[str] | None = None, max_retries: int = 3) -> WebhookEndpoint:
        ep = WebhookEndpoint(name=name, url=url, secret=secret,
                             events=events or [], max_retries=max_retries)
        with self._lock:
            self._endpoints[name] = ep
        return ep

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._endpoints.pop(name, None) is not None

    def get_endpoint(self, name: str) -> WebhookEndpoint | None:
        return self._endpoints.get(name)

    def list_endpoints(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "name": ep.name, "url": ep.url, "active": ep.active,
                    "events": ep.events, "max_retries": ep.max_retries,
                }
                for ep in self._endpoints.values()
            ]

    def set_active(self, name: str, active: bool) -> bool:
        ep = self._endpoints.get(name)
        if not ep:
            return False
        ep.active = active
        return True

    # ── Signing ─────────────────────────────────────────────────────
    @staticmethod
    def sign_payload(payload: dict, secret: str) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def verify_signature(payload: dict, secret: str, signature: str) -> bool:
        expected = WebhookManager.sign_payload(payload, secret)
        return hmac.compare_digest(expected, signature)

    # ── Transport ───────────────────────────────────────────────────
    def set_transport(self, fn: Callable):
        """Set custom transport for testing (fn(url, payload, headers) -> (status_code, body))."""
        self._transport = fn

    # ── Dispatch ────────────────────────────────────────────────────
    def dispatch(self, event: str, payload: dict) -> list[DeliveryRecord]:
        records = []
        with self._lock:
            targets = [
                ep for ep in self._endpoints.values()
                if ep.active and (not ep.events or event in ep.events)
            ]

        for ep in targets:
            record = DeliveryRecord(
                delivery_id=uuid.uuid4().hex[:12],
                webhook_name=ep.name,
                event=event,
                url=ep.url,
                payload=payload,
            )
            headers = {"X-Event": event, "X-Delivery-ID": record.delivery_id}
            if ep.secret:
                headers["X-Signature"] = self.sign_payload(payload, ep.secret)

            success = False
            for attempt in range(1, ep.max_retries + 1):
                record.attempts = attempt
                try:
                    if self._transport:
                        code, _ = self._transport(ep.url, payload, headers)
                        record.response_code = code
                        if 200 <= code < 300:
                            success = True
                            break
                    else:
                        # No real HTTP — mark as failed without transport
                        record.error = "no transport configured"
                        break
                except Exception as exc:
                    record.error = str(exc)

            record.status = "success" if success else "failed"
            with self._lock:
                self._history.append(record)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]
            records.append(record)

        return records

    # ── History ─────────────────────────────────────────────────────
    def get_history(self, webhook_name: str | None = None, limit: int = 50) -> list[dict]:
        with self._lock:
            items = self._history
            if webhook_name:
                items = [r for r in items if r.webhook_name == webhook_name]
            return [
                {
                    "delivery_id": r.delivery_id, "webhook": r.webhook_name,
                    "event": r.event, "status": r.status, "attempts": r.attempts,
                    "response_code": r.response_code, "error": r.error,
                    "timestamp": r.timestamp,
                }
                for r in items[-limit:]
            ]

    # ── Stats ───────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._history)
            ok = sum(1 for r in self._history if r.status == "success")
            fail = sum(1 for r in self._history if r.status == "failed")
            return {
                "endpoints": len(self._endpoints),
                "active_endpoints": sum(1 for ep in self._endpoints.values() if ep.active),
                "total_deliveries": total,
                "successful": ok,
                "failed": fail,
                "success_rate": round(ok / total * 100, 1) if total else 0,
            }


webhook_manager = WebhookManager()
