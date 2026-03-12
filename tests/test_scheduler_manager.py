"""Tests for src/scheduler_manager.py — Windows Task Scheduler management.

Covers: ScheduledTask, SchedulerEvent, SchedulerManager (list_tasks,
_parse_csv, get_task, search_tasks, count_by_status, list_folders,
get_events, get_stats), scheduler_manager singleton.
All subprocess calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.scheduler_manager import (
    ScheduledTask, SchedulerEvent, SchedulerManager, scheduler_manager,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_scheduled_task(self):
        t = ScheduledTask(name="test")
        assert t.folder == "/"
        assert t.status == ""

    def test_scheduler_event(self):
        e = SchedulerEvent(action="list", task_name="t1")
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# SchedulerManager — _parse_csv
# ===========================================================================

CSV_OUTPUT = (
    '"TaskName","Status","Next Run Time","Last Run Time","Last Result","Author","Task To Run"\n'
    '"/JARVIS_Boot","Ready","3/7/2026 8:00:00","3/6/2026 8:00:00","0","JARVIS","python boot.py"\n'
    '"/JARVIS_Backup","Disabled","N/A","3/5/2026 12:00:00","0","JARVIS","python backup.py"\n'
)


class TestParseCSV:
    def test_parse(self):
        sm = SchedulerManager()
        tasks = sm._parse_csv(CSV_OUTPUT)
        assert len(tasks) == 2
        assert tasks[0]["name"] == "/JARVIS_Boot"
        assert tasks[0]["status"] == "Ready"
        assert tasks[1]["status"] == "Disabled"

    def test_parse_empty(self):
        sm = SchedulerManager()
        tasks = sm._parse_csv("")
        assert tasks == []


# ===========================================================================
# SchedulerManager — list_tasks (mocked)
# ===========================================================================

class TestListTasks:
    def test_success(self):
        sm = SchedulerManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CSV_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            tasks = sm.list_tasks()
        assert len(tasks) == 2

    def test_failure(self):
        sm = SchedulerManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            tasks = sm.list_tasks()
        assert tasks == []

    def test_records_event(self):
        sm = SchedulerManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CSV_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            sm.list_tasks()
        events = sm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "list_tasks"


# ===========================================================================
# SchedulerManager — get_task (mocked)
# ===========================================================================

class TestGetTask:
    def test_success(self):
        sm = SchedulerManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CSV_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            task = sm.get_task("/JARVIS_Boot")
        assert task is not None
        assert task["name"] == "/JARVIS_Boot"

    def test_not_found(self):
        sm = SchedulerManager()
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            task = sm.get_task("/nope")
        assert task is None

    def test_exception(self):
        sm = SchedulerManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            task = sm.get_task("/test")
        assert task is None


# ===========================================================================
# SchedulerManager — search_tasks
# ===========================================================================

class TestSearchTasks:
    def test_search(self):
        sm = SchedulerManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CSV_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            results = sm.search_tasks("boot")
        assert len(results) == 1
        assert "Boot" in results[0]["name"]


# ===========================================================================
# SchedulerManager — count_by_status
# ===========================================================================

class TestCountByStatus:
    def test_count(self):
        sm = SchedulerManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CSV_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            counts = sm.count_by_status()
        assert counts.get("Ready") == 1
        assert counts.get("Disabled") == 1


# ===========================================================================
# SchedulerManager — list_folders
# ===========================================================================

class TestListFolders:
    def test_success(self):
        sm = SchedulerManager()
        csv = (
            '"TaskName","Status"\n'
            '"/Microsoft/Windows/Update","Ready"\n'
            '"/JARVIS/Boot","Ready"\n'
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = csv
        with patch("subprocess.run", return_value=mock_result):
            folders = sm.list_folders()
        assert "/Microsoft/Windows" in folders
        assert "/JARVIS" in folders

    def test_failure(self):
        sm = SchedulerManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            folders = sm.list_folders()
        assert folders == []


# ===========================================================================
# SchedulerManager — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        sm = SchedulerManager()
        assert sm.get_events() == []

    def test_stats(self):
        sm = SchedulerManager()
        stats = sm.get_stats()
        assert stats["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert scheduler_manager is not None
        assert isinstance(scheduler_manager, SchedulerManager)
