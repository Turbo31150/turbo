"""Tests for src/windows_event_log_reader.py — Windows Event Log reader.

Covers: EventLogEntry, LogReaderEvent, WindowsEventLogReader (get_recent,
count_by_level, list_logs, search_events, get_events, get_stats),
windows_event_log_reader singleton.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.windows_event_log_reader import (
    EventLogEntry, LogReaderEvent, WindowsEventLogReader, windows_event_log_reader,
)

EVENTS_JSON = json.dumps([
    {"Id": 7036, "LevelDisplayName": "Information", "ProviderName": "Service Control Manager",
     "Message": "The BITS service entered the running state.", "TimeCreated": "2026-03-07T10:00:00"},
    {"Id": 41, "LevelDisplayName": "Critical", "ProviderName": "Kernel-Power",
     "Message": "The system has rebooted without cleanly shutting down.", "TimeCreated": "2026-03-06T23:00:00"},
    {"Id": 1001, "LevelDisplayName": "Error", "ProviderName": "Windows Error Reporting",
     "Message": "Fault bucket.", "TimeCreated": {"DateTime": "2026-03-06T22:00:00"}},
])


class TestDataclasses:
    def test_event_log_entry(self):
        e = EventLogEntry(log_name="System")
        assert e.event_id == 0
        assert e.level == ""

    def test_log_reader_event(self):
        e = LogReaderEvent(action="get_recent")
        assert e.success is True


class TestGetRecent:
    def test_success(self):
        r = WindowsEventLogReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = EVENTS_JSON
        with patch("subprocess.run", return_value=mock_result):
            events = r.get_recent("System", 10)
        assert len(events) == 3
        assert events[0]["event_id"] == 7036
        assert events[0]["level"] == "Information"
        assert events[1]["level"] == "Critical"

    def test_time_created_dict(self):
        r = WindowsEventLogReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = EVENTS_JSON
        with patch("subprocess.run", return_value=mock_result):
            events = r.get_recent()
        # Third event has dict TimeCreated
        assert "2026-03-06" in events[2]["time_created"]

    def test_message_truncation(self):
        r = WindowsEventLogReader()
        long_msg = "x" * 300
        data = json.dumps([{"Id": 1, "LevelDisplayName": "Info",
                            "ProviderName": "Test", "Message": long_msg,
                            "TimeCreated": ""}])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            events = r.get_recent()
        assert len(events[0]["message"]) == 200

    def test_failure(self):
        r = WindowsEventLogReader()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert r.get_recent() == []


class TestCountByLevel:
    def test_count(self):
        r = WindowsEventLogReader()
        fake = [{"level": "Information"}, {"level": "Information"}, {"level": "Error"}]
        with patch.object(r, "get_recent", return_value=fake):
            counts = r.count_by_level()
        assert counts["Information"] == 2
        assert counts["Error"] == 1


class TestListLogs:
    def test_list(self):
        r = WindowsEventLogReader()
        logs = r.list_logs()
        assert "System" in logs
        assert "Application" in logs
        assert "Security" in logs


class TestSearchEvents:
    def test_search(self):
        r = WindowsEventLogReader()
        fake = [{"message": "BITS service started"}, {"message": "Disk error"}]
        with patch.object(r, "get_recent", return_value=fake):
            results = r.search_events("System", "BITS")
        assert len(results) == 1

    def test_search_no_match(self):
        r = WindowsEventLogReader()
        fake = [{"message": "test"}]
        with patch.object(r, "get_recent", return_value=fake):
            assert len(r.search_events("System", "nope")) == 0


class TestEventsStats:
    def test_events_empty(self):
        assert WindowsEventLogReader().get_events() == []

    def test_stats(self):
        assert WindowsEventLogReader().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(windows_event_log_reader, WindowsEventLogReader)
