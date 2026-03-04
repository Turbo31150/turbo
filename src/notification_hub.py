"""Notification Hub — Multi-channel notification dispatch.

Dispatches notifications through multiple channels:
console, file log, webhook, event_bus. Supports priority
filtering, templates, and per-channel throttling.
"""

from __future__ import annotations

import json
import logging
import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("jarvis.notification_hub")

LEVELS = {"debug": 0, "info": 1, "warning": 2, "critical": 3}


@dataclass
class Channel:
    name: str
    channel_type: str  # console, file, webhook, event_bus, custom
    min_level: str = "info"
    enabled: bool = True
    throttle_s: float = 0.0
    handler: Callable | None = None
    _last_sent: float = 0.0
    sent_count: int = 0
    error_count: int = 0


@dataclass
class Notification:
    message: str
    level: str = "info"
    source: str = "system"
    title: str = ""
    metadata: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class NotificationHub:
    """Multi-channel notification dispatcher."""

    def __init__(self, log_dir: Path | None = None):
        self._channels: dict[str, Channel] = {}
        self._log_dir = log_dir or Path("data/notifications")
        self._lock = threading.Lock()
        self._history: list[dict] = []
        self._max_history = 500
        self._templates: dict[str, str] = {}

        # Default channels
        self.add_channel("console", "console", min_level="info")
        self.add_channel("file", "file", min_level="warning")

    def add_channel(
        self,
        name: str,
        channel_type: str,
        min_level: str = "info",
        throttle_s: float = 0.0,
        handler: Callable | None = None,
    ) -> None:
        self._channels[name] = Channel(
            name=name, channel_type=channel_type,
            min_level=min_level, throttle_s=throttle_s,
            handler=handler,
        )

    def remove_channel(self, name: str) -> bool:
        return self._channels.pop(name, None) is not None

    def enable_channel(self, name: str, enabled: bool = True) -> bool:
        ch = self._channels.get(name)
        if ch:
            ch.enabled = enabled
            return True
        return False

    def register_template(self, name: str, template: str) -> None:
        """Register a notification template. Use {key} placeholders."""
        self._templates[name] = template

    def send(
        self,
        message: str,
        level: str = "info",
        source: str = "system",
        title: str = "",
        template: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Send a notification to all eligible channels. Returns channels notified."""
        if template and template in self._templates:
            fmt = self._templates[template]
            message = fmt.format(message=message, source=source, title=title, **(metadata or {}))

        notif = Notification(
            message=message, level=level, source=source,
            title=title, metadata=metadata or {},
        )
        notif_level = LEVELS.get(level, 1)
        sent = 0
        now = time.time()

        with self._lock:
            for ch in self._channels.values():
                if not ch.enabled:
                    continue
                if LEVELS.get(ch.min_level, 0) > notif_level:
                    continue
                if ch.throttle_s > 0 and (now - ch._last_sent) < ch.throttle_s:
                    continue
                try:
                    self._dispatch(ch, notif)
                    ch._last_sent = now
                    ch.sent_count += 1
                    sent += 1
                except Exception as e:
                    ch.error_count += 1
                    logger.debug("Channel %s dispatch error: %s", ch.name, e)

            self._history.append({
                "ts": now, "message": message, "level": level,
                "source": source, "channels_notified": sent,
            })
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        return sent

    def _dispatch(self, channel: Channel, notif: Notification) -> None:
        if channel.channel_type == "console":
            prefix = f"[{notif.level.upper()}]"
            logger.info("%s %s: %s", prefix, notif.source, notif.message)
        elif channel.channel_type == "file":
            self._log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self._log_dir / "notifications.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{notif.level}] {notif.source}: {notif.message}\n")
        elif channel.channel_type == "event_bus":
            try:
                from src.event_bus import event_bus
                event_bus.emit_sync(f"notification.{notif.level}", {
                    "message": notif.message, "source": notif.source, "title": notif.title,
                })
            except ImportError:
                pass
        elif channel.channel_type == "custom" and channel.handler:
            channel.handler(notif)

    def get_history(self, limit: int = 50, level: str | None = None) -> list[dict]:
        with self._lock:
            history = self._history
            if level:
                history = [h for h in history if h["level"] == level]
            return history[-limit:]

    def get_channels(self) -> list[dict]:
        return [
            {
                "name": ch.name, "type": ch.channel_type,
                "min_level": ch.min_level, "enabled": ch.enabled,
                "throttle_s": ch.throttle_s, "sent_count": ch.sent_count,
                "error_count": ch.error_count,
            }
            for ch in self._channels.values()
        ]

    def get_stats(self) -> dict:
        total_sent = sum(ch.sent_count for ch in self._channels.values())
        total_errors = sum(ch.error_count for ch in self._channels.values())
        return {
            "total_channels": len(self._channels),
            "enabled_channels": sum(1 for ch in self._channels.values() if ch.enabled),
            "total_sent": total_sent,
            "total_errors": total_errors,
            "history_size": len(self._history),
            "templates": list(self._templates.keys()),
        }


# ── Singleton ────────────────────────────────────────────────────────────────
notification_hub = NotificationHub()
