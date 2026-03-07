"""Tests for src/crash_dump_reader.py — Windows crash dump analysis.

Covers: CrashDump, CrashEvent, CrashDumpReader (list_minidumps,
get_bsod_events, get_crash_summary, get_events, get_stats),
crash_dump_reader singleton. All subprocess/filesystem calls are mocked.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.crash_dump_reader import (
    CrashDump, CrashEvent, CrashDumpReader, crash_dump_reader,
)


BSOD_JSON = json.dumps([
    {"TimeCreated": {"DateTime": "2026-01-15T10:30:00"},
     "Id": 1001, "Message": "BugCheck 0x0000001E"},
    {"TimeCreated": {"DateTime": "2026-01-10T08:15:00"},
     "Id": 1001, "Message": "BugCheck 0x0000000A"},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_crash_dump(self):
        c = CrashDump(filename="mini.dmp")
        assert c.size_kb == 0
        assert c.created == ""

    def test_crash_event(self):
        e = CrashEvent(action="list_minidumps")
        assert e.success is True


# ===========================================================================
# CrashDumpReader — list_minidumps
# ===========================================================================

class TestListMinidumps:
    def test_with_dumps(self, tmp_path):
        dump_dir = tmp_path / "Minidump"
        dump_dir.mkdir()
        (dump_dir / "mini1.dmp").write_bytes(b"\x00" * 1024)
        (dump_dir / "mini2.dmp").write_bytes(b"\x00" * 2048)
        (dump_dir / "readme.txt").write_text("not a dump")

        cdr = CrashDumpReader()
        with patch("src.crash_dump_reader.MINIDUMP_DIR", str(dump_dir)):
            dumps = cdr.list_minidumps()
        assert len(dumps) == 2
        filenames = [d["filename"] for d in dumps]
        assert "mini1.dmp" in filenames
        assert "mini2.dmp" in filenames

    def test_no_dir(self):
        cdr = CrashDumpReader()
        with patch("src.crash_dump_reader.MINIDUMP_DIR", "/nonexistent/path"):
            dumps = cdr.list_minidumps()
        assert dumps == []

    def test_empty_dir(self, tmp_path):
        dump_dir = tmp_path / "Minidump"
        dump_dir.mkdir()
        cdr = CrashDumpReader()
        with patch("src.crash_dump_reader.MINIDUMP_DIR", str(dump_dir)):
            dumps = cdr.list_minidumps()
        assert dumps == []


# ===========================================================================
# CrashDumpReader — get_bsod_events
# ===========================================================================

class TestGetBsodEvents:
    def test_success(self):
        cdr = CrashDumpReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = BSOD_JSON
        with patch("subprocess.run", return_value=mock_result):
            events = cdr.get_bsod_events()
        assert len(events) == 2
        assert events[0]["event_id"] == 1001
        assert "BugCheck" in events[0]["message"]

    def test_failure(self):
        cdr = CrashDumpReader()
        with patch("subprocess.run", side_effect=Exception("fail")):
            events = cdr.get_bsod_events()
        assert events == []

    def test_single_event(self):
        cdr = CrashDumpReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"TimeCreated": "2026-01-15", "Id": 1001, "Message": "crash"}
        )
        with patch("subprocess.run", return_value=mock_result):
            events = cdr.get_bsod_events()
        assert len(events) == 1


# ===========================================================================
# CrashDumpReader — get_crash_summary
# ===========================================================================

class TestCrashSummary:
    def test_with_dumps(self):
        cdr = CrashDumpReader()
        fake_dumps = [
            {"filename": "a.dmp", "created": "2026-01-15"},
            {"filename": "b.dmp", "created": "2026-01-10"},
        ]
        with patch.object(cdr, "list_minidumps", return_value=fake_dumps):
            summary = cdr.get_crash_summary()
        assert summary["minidump_count"] == 2
        assert summary["latest_dump"]["filename"] == "a.dmp"

    def test_no_dumps(self):
        cdr = CrashDumpReader()
        with patch.object(cdr, "list_minidumps", return_value=[]):
            summary = cdr.get_crash_summary()
        assert summary["minidump_count"] == 0
        assert summary["latest_dump"] is None


# ===========================================================================
# CrashDumpReader — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        cdr = CrashDumpReader()
        assert cdr.get_events() == []

    def test_stats(self):
        cdr = CrashDumpReader()
        assert cdr.get_stats()["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert crash_dump_reader is not None
        assert isinstance(crash_dump_reader, CrashDumpReader)
