"""Tests for src/notification_hub.py — Multi-channel notification dispatch.

Covers: Channel, Notification, LEVELS, NotificationHub (add/remove/enable_channel,
register_template, send with level filtering + throttle, _dispatch console/file/
event_bus/custom, get_history, get_channels, get_stats), _telegram_handler,
notification_hub singleton.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.notification_hub import (
    Channel, Notification, LEVELS, NotificationHub, _telegram_handler,
    notification_hub,
)


# ===========================================================================
# Dataclasses & Constants
# ===========================================================================

class TestChannel:
    def test_defaults(self):
        ch = Channel(name="test", channel_type="console")
        assert ch.min_level == "info"
        assert ch.enabled is True
        assert ch.throttle_s == 0.0
        assert ch.handler is None
        assert ch.sent_count == 0
        assert ch.error_count == 0


class TestNotification:
    def test_defaults(self):
        n = Notification(message="Hello")
        assert n.level == "info"
        assert n.source == "system"
        assert n.title == ""
        assert n.metadata == {}
        assert n.ts > 0


class TestLevels:
    def test_order(self):
        assert LEVELS["debug"] < LEVELS["info"]
        assert LEVELS["info"] < LEVELS["warning"]
        assert LEVELS["warning"] < LEVELS["critical"]


# ===========================================================================
# NotificationHub — channel management
# ===========================================================================

class TestChannelManagement:
    def test_default_channels(self):
        hub = NotificationHub()
        channels = hub.get_channels()
        names = [ch["name"] for ch in channels]
        assert "console" in names
        assert "file" in names

    def test_add_channel(self):
        hub = NotificationHub()
        hub.add_channel("custom1", "custom", min_level="warning")
        channels = hub.get_channels()
        custom = [ch for ch in channels if ch["name"] == "custom1"]
        assert len(custom) == 1
        assert custom[0]["min_level"] == "warning"

    def test_remove_channel(self):
        hub = NotificationHub()
        hub.add_channel("temp", "console")
        assert hub.remove_channel("temp") is True
        assert hub.remove_channel("temp") is False

    def test_enable_channel(self):
        hub = NotificationHub()
        hub.enable_channel("console", False)
        ch = [c for c in hub.get_channels() if c["name"] == "console"][0]
        assert ch["enabled"] is False
        hub.enable_channel("console", True)
        ch = [c for c in hub.get_channels() if c["name"] == "console"][0]
        assert ch["enabled"] is True

    def test_enable_nonexistent(self):
        hub = NotificationHub()
        assert hub.enable_channel("nope") is False


# ===========================================================================
# NotificationHub — templates
# ===========================================================================

class TestTemplates:
    def test_register_and_use(self):
        hub = NotificationHub()
        hub.remove_channel("file")  # avoid file I/O
        hub.register_template("alert", "[{source}] {message}")
        sent = hub.send("down", source="monitor", template="alert")
        assert sent >= 1
        history = hub.get_history()
        assert "[monitor] down" in history[-1]["message"]

    def test_template_with_metadata(self):
        hub = NotificationHub()
        hub.remove_channel("file")
        hub.register_template("deploy", "Deploy {app} v{version}: {message}")
        sent = hub.send("ok", template="deploy", metadata={"app": "jarvis", "version": "12.4"})
        history = hub.get_history()
        assert "jarvis" in history[-1]["message"]
        assert "12.4" in history[-1]["message"]

    def test_unknown_template_ignored(self):
        hub = NotificationHub()
        hub.remove_channel("file")
        sent = hub.send("raw message", template="nonexistent")
        history = hub.get_history()
        assert history[-1]["message"] == "raw message"


# ===========================================================================
# NotificationHub — send / dispatch
# ===========================================================================

class TestSend:
    def test_send_to_console(self):
        hub = NotificationHub()
        hub.remove_channel("file")
        sent = hub.send("test message", level="info")
        assert sent >= 1
        history = hub.get_history()
        assert len(history) == 1
        assert history[0]["message"] == "test message"

    def test_send_level_filtering(self):
        hub = NotificationHub()
        hub.remove_channel("console")
        hub.remove_channel("file")
        hub.add_channel("warn_only", "console", min_level="warning")
        sent = hub.send("info msg", level="info")
        assert sent == 0  # info < warning -> filtered out

    def test_send_level_warning_passes(self):
        hub = NotificationHub()
        hub.remove_channel("console")
        hub.remove_channel("file")
        hub.add_channel("warn_only", "console", min_level="warning")
        sent = hub.send("warn msg", level="warning")
        assert sent == 1

    def test_send_disabled_channel(self):
        hub = NotificationHub()
        hub.remove_channel("file")
        hub.enable_channel("console", False)
        sent = hub.send("test")
        assert sent == 0

    def test_send_throttle(self):
        hub = NotificationHub()
        hub.remove_channel("console")
        hub.remove_channel("file")
        hub.add_channel("throttled", "console", throttle_s=60.0)
        sent1 = hub.send("first")
        sent2 = hub.send("second")
        assert sent1 == 1
        assert sent2 == 0  # throttled

    def test_send_custom_handler(self):
        received = []
        hub = NotificationHub()
        hub.remove_channel("console")
        hub.remove_channel("file")
        hub.add_channel("custom", "custom", handler=lambda n: received.append(n.message))
        hub.send("hello custom")
        assert received == ["hello custom"]

    def test_send_custom_handler_error(self):
        hub = NotificationHub()
        hub.remove_channel("console")
        hub.remove_channel("file")
        hub.add_channel("bad", "custom", handler=lambda n: 1 / 0)
        sent = hub.send("boom")
        assert sent == 0
        channels = hub.get_channels()
        bad = [c for c in channels if c["name"] == "bad"][0]
        assert bad["error_count"] == 1

    def test_send_file_channel(self, tmp_path):
        hub = NotificationHub(log_dir=tmp_path)
        hub.remove_channel("console")
        # File channel min_level is warning by default
        sent = hub.send("test warning", level="warning")
        assert sent >= 1
        log_file = tmp_path / "notifications.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "test warning" in content

    def test_send_event_bus_channel(self):
        hub = NotificationHub()
        hub.remove_channel("console")
        hub.remove_channel("file")
        hub.add_channel("bus", "event_bus")
        mock_bus = MagicMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
            sent = hub.send("bus msg")
        assert sent == 1
        mock_bus.emit_sync.assert_called_once()


# ===========================================================================
# NotificationHub — history
# ===========================================================================

class TestHistory:
    def test_history_empty(self):
        hub = NotificationHub()
        assert hub.get_history() == []

    def test_history_limit(self):
        hub = NotificationHub()
        hub.remove_channel("file")
        for i in range(100):
            hub.send(f"msg {i}")
        result = hub.get_history(limit=10)
        assert len(result) == 10

    def test_history_level_filter(self):
        hub = NotificationHub()
        hub.remove_channel("file")
        hub.send("info msg", level="info")
        hub.send("warn msg", level="warning")
        result = hub.get_history(level="warning")
        assert len(result) == 1
        assert result[0]["level"] == "warning"

    def test_history_max_size(self):
        hub = NotificationHub()
        hub._max_history = 10
        hub.remove_channel("file")
        for i in range(20):
            hub.send(f"msg {i}")
        assert len(hub._history) == 10


# ===========================================================================
# NotificationHub — get_channels / get_stats
# ===========================================================================

class TestStats:
    def test_get_channels(self):
        hub = NotificationHub()
        channels = hub.get_channels()
        assert len(channels) >= 2
        ch = channels[0]
        assert "name" in ch
        assert "type" in ch
        assert "min_level" in ch
        assert "enabled" in ch
        assert "sent_count" in ch

    def test_get_stats(self):
        hub = NotificationHub()
        hub.remove_channel("file")
        hub.register_template("t1", "test {message}")
        hub.send("test")
        stats = hub.get_stats()
        assert stats["total_channels"] >= 1
        assert stats["enabled_channels"] >= 1
        assert stats["total_sent"] >= 1
        assert stats["total_errors"] == 0
        assert "t1" in stats["templates"]
        assert stats["history_size"] == 1


# ===========================================================================
# _telegram_handler (mocked urllib)
# ===========================================================================

class TestTelegramHandler:
    def test_no_token(self):
        n = Notification(message="test", level="warning")
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "", "TELEGRAM_CHAT": ""}):
            _telegram_handler(n)  # should not raise

    def test_sends_request(self):
        n = Notification(message="alert", level="critical", source="test")
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "fake", "TELEGRAM_CHAT": "123"}), \
             patch("urllib.request.urlopen") as mock_open:
            _telegram_handler(n)
        assert mock_open.called

    def test_with_title(self):
        n = Notification(message="details", level="warning", source="sys", title="Alert!")
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "fake", "TELEGRAM_CHAT": "123"}), \
             patch("urllib.request.urlopen"):
            _telegram_handler(n)  # should not raise

    def test_exception_handled(self):
        n = Notification(message="fail", level="info")
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "fake", "TELEGRAM_CHAT": "123"}), \
             patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            _telegram_handler(n)  # should not raise


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert notification_hub is not None
        assert isinstance(notification_hub, NotificationHub)

    def test_has_telegram_channel(self):
        channels = notification_hub.get_channels()
        telegram = [c for c in channels if c["name"] == "telegram"]
        assert len(telegram) == 1
        assert telegram[0]["type"] == "custom"
        assert telegram[0]["min_level"] == "warning"
