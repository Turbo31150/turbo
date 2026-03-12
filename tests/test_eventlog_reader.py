"""Tests for src/eventlog_reader.py — Windows Event Log reader.

Covers: EventLogEntry, ReaderEvent, EventLogReader (read_log, list_logs,
count_by_level, get_errors, search_events, get_events, get_stats),
eventlog_reader singleton.
All subprocess calls are mocked.
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

from src.eventlog_reader import (
    EventLogEntry, ReaderEvent, EventLogReader, KNOWN_LOGS, eventlog_reader,
)


EVENTS_JSON = json.dumps([
    {"Id": 1001, "LevelDisplayName": "Error", "Message": "Disk failure detected",
     "ProviderName": "disk", "TimeCreated": "2026-03-07T10:00:00"},
    {"Id": 7036, "LevelDisplayName": "Information", "Message": "Service started",
     "ProviderName": "ServiceControl", "TimeCreated": "2026-03-07T09:00:00"},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_event_log_entry(self):
        e = EventLogEntry(log_name="System", event_id=1001)
        assert e.level == ""

    def test_reader_event(self):
        e = ReaderEvent(action="read_log")
        assert e.success is True


# ===========================================================================
# EventLogReader — read_log (mocked)
# ===========================================================================

class TestReadLog:
    def test_success(self):
        elr = EventLogReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = EVENTS_JSON
        with patch("subprocess.run", return_value=mock_result):
            events = elr.read_log("System")
        assert len(events) == 2
        assert events[0]["event_id"] == 1001
        assert events[0]["level"] == "Error"

    def test_failure(self):
        elr = EventLogReader()
        with patch("subprocess.run", side_effect=Exception("fail")):
            events = elr.read_log("System")
        assert events == []

    def test_single_event(self):
        elr = EventLogReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"Id": 42, "LevelDisplayName": "Warning",
                                          "Message": "test", "ProviderName": "src",
                                          "TimeCreated": "2026-01-01"})
        with patch("subprocess.run", return_value=mock_result):
            events = elr.read_log("Application")
        assert len(events) == 1

    def test_with_level_filter(self):
        elr = EventLogReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "[]"
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            elr.read_log("System", level="error")
        cmd = mock_run.call_args[0][0][2]
        assert "Level=2" in cmd


# ===========================================================================
# EventLogReader — list_logs
# ===========================================================================

class TestListLogs:
    def test_success(self):
        elr = EventLogReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "System\nApplication\nSecurity\n"
        with patch("subprocess.run", return_value=mock_result):
            logs = elr.list_logs()
        assert "System" in logs

    def test_failure_returns_known(self):
        elr = EventLogReader()
        with patch("subprocess.run", side_effect=Exception("fail")):
            logs = elr.list_logs()
        assert logs == KNOWN_LOGS


# ===========================================================================
# EventLogReader — count_by_level, get_errors, search
# ===========================================================================

class TestHelpers:
    def test_count_by_level(self):
        elr = EventLogReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = EVENTS_JSON
        with patch("subprocess.run", return_value=mock_result):
            counts = elr.count_by_level()
        assert counts.get("Error") == 1
        assert counts.get("Information") == 1

    def test_get_errors(self):
        elr = EventLogReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = EVENTS_JSON
        with patch("subprocess.run", return_value=mock_result):
            errors = elr.get_errors()
        assert isinstance(errors, list)

    def test_search_events(self):
        elr = EventLogReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = EVENTS_JSON
        with patch("subprocess.run", return_value=mock_result):
            results = elr.search_events("disk")
        assert len(results) == 1
        assert "Disk" in results[0]["message"]


# ===========================================================================
# EventLogReader — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        elr = EventLogReader()
        assert elr.get_events() == []

    def test_stats(self):
        elr = EventLogReader()
        stats = elr.get_stats()
        assert stats["total_reads"] == 0
        assert stats["known_logs"] == KNOWN_LOGS


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert eventlog_reader is not None
        assert isinstance(eventlog_reader, EventLogReader)
