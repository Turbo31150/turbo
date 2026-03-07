"""Tests for src/notification_manager.py — Windows toast notification management.

Covers: Notification, NotifEvent, NotificationManager (send, _send_powershell,
send_template, get_history, clear_history, search_history, list_templates,
add_template, get_events, get_stats), notification_manager singleton.
subprocess calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.notification_manager import (
    Notification, NotifEvent, NotificationManager, notification_manager,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestNotification:
    def test_defaults(self):
        n = Notification(title="Test", message="Hello")
        assert n.priority == "normal"
        assert n.source == "JARVIS"
        assert n.sent is False
        assert n.timestamp > 0


class TestNotifEvent:
    def test_defaults(self):
        e = NotifEvent(action="send")
        assert e.detail == ""
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# NotificationManager — send (mocked)
# ===========================================================================

class TestSend:
    def test_send_success(self):
        nm = NotificationManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = nm.send("Title", "Message")
        assert result is True
        history = nm.get_history()
        assert len(history) == 1
        assert history[0]["title"] == "Title"
        assert history[0]["sent"] is True

    def test_send_failure(self):
        nm = NotificationManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            result = nm.send("Title", "Message")
        assert result is False
        history = nm.get_history()
        assert history[0]["sent"] is False

    def test_send_nonzero_returncode(self):
        nm = NotificationManager()
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            result = nm.send("Title", "Message")
        assert result is False

    def test_send_records_event(self):
        nm = NotificationManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            nm.send("Title", "Msg")
        events = nm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "send"

    def test_send_max_history(self):
        nm = NotificationManager(max_history=3)
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            for i in range(5):
                nm.send(f"T{i}", f"M{i}")
        assert len(nm.get_history(limit=100)) == 3


# ===========================================================================
# NotificationManager — templates
# ===========================================================================

class TestTemplates:
    def test_send_template(self):
        nm = NotificationManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = nm.send_template("warning", "Disk full")
        assert result is True
        history = nm.get_history()
        assert history[0]["title"] == "JARVIS Warning"

    def test_send_template_unknown_falls_back(self):
        nm = NotificationManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = nm.send_template("nonexistent", "msg")
        assert result is True
        history = nm.get_history()
        assert history[0]["title"] == "JARVIS Info"  # fallback to info

    def test_list_templates(self):
        nm = NotificationManager()
        templates = nm.list_templates()
        assert "info" in templates
        assert "warning" in templates
        assert "error" in templates

    def test_add_template(self):
        nm = NotificationManager()
        nm.add_template("custom", "My Title", priority="high")
        templates = nm.list_templates()
        assert "custom" in templates
        assert templates["custom"]["title"] == "My Title"


# ===========================================================================
# NotificationManager — history & search
# ===========================================================================

class TestHistorySearch:
    def test_get_history(self):
        nm = NotificationManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            nm.send("T1", "M1")
            nm.send("T2", "M2")
        history = nm.get_history()
        assert len(history) == 2

    def test_clear_history(self):
        nm = NotificationManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            nm.send("T", "M")
        count = nm.clear_history()
        assert count == 1
        assert nm.get_history() == []

    def test_search_history(self):
        nm = NotificationManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            nm.send("GPU Alert", "Temperature high")
            nm.send("Disk Alert", "Space low")
            nm.send("Update", "System updated")
        results = nm.search_history("alert")
        assert len(results) == 2

    def test_search_no_match(self):
        nm = NotificationManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            nm.send("Title", "Message")
        results = nm.search_history("xyz")
        assert results == []


# ===========================================================================
# NotificationManager — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        nm = NotificationManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            nm.send("T", "M")
        stats = nm.get_stats()
        assert stats["total_notifications"] == 1
        assert stats["sent_success"] == 1
        assert stats["templates"] == 4

    def test_stats_empty(self):
        nm = NotificationManager()
        stats = nm.get_stats()
        assert stats["total_notifications"] == 0
        assert stats["sent_success"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert notification_manager is not None
        assert isinstance(notification_manager, NotificationManager)
