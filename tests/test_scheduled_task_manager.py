"""Tests for src/scheduled_task_manager.py — Windows Task Scheduler inventory.

Covers: ScheduledTask, SchedEvent, ScheduledTaskManager (list_tasks, search,
count_by_status, get_task_detail, get_events, get_stats),
scheduled_task_manager singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.scheduled_task_manager import (
    ScheduledTask, SchedEvent, ScheduledTaskManager, scheduled_task_manager,
)

SCHTASKS_CSV = '''"/JARVIS_LinkedIn_Publish","07/03/2026 08:05:00","Ready"
"/JARVIS_LinkedIn_Routine","08/03/2026 07:30:00","Ready"
"/Microsoft/Windows/UpdateOrchestrator/Schedule Scan","N/A","Disabled"
'''

TASK_DETAIL_OUTPUT = """\
HostName:                             DESKTOP-TEST
TaskName:                             /JARVIS_LinkedIn_Publish
Next Run Time:                        07/03/2026 08:05:00
Status:                               Ready
Author:                               DESKTOP-TEST/franc
"""


class TestDataclasses:
    def test_scheduled_task(self):
        t = ScheduledTask(name="test")
        assert t.status == ""
        assert t.next_run == ""

    def test_sched_event(self):
        e = SchedEvent(action="list_tasks")
        assert e.success is True


class TestListTasks:
    def test_success(self):
        stm = ScheduledTaskManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SCHTASKS_CSV
        with patch("subprocess.run", return_value=mock_result):
            tasks = stm.list_tasks()
        assert len(tasks) == 3
        assert tasks[0]["name"] == "/JARVIS_LinkedIn_Publish"
        assert tasks[0]["status"] == "Ready"
        assert tasks[2]["status"] == "Disabled"

    def test_failure(self):
        stm = ScheduledTaskManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert stm.list_tasks() == []


class TestSearch:
    def test_search(self):
        stm = ScheduledTaskManager()
        fake = [{"name": "/JARVIS_Publish"}, {"name": "/Windows/Update"}]
        with patch.object(stm, "list_tasks", return_value=fake):
            assert len(stm.search("jarvis")) == 1

    def test_search_no_match(self):
        stm = ScheduledTaskManager()
        fake = [{"name": "/Windows/Update"}]
        with patch.object(stm, "list_tasks", return_value=fake):
            assert len(stm.search("nope")) == 0


class TestCountByStatus:
    def test_count(self):
        stm = ScheduledTaskManager()
        fake = [{"status": "Ready"}, {"status": "Ready"}, {"status": "Disabled"}]
        with patch.object(stm, "list_tasks", return_value=fake):
            counts = stm.count_by_status()
        assert counts["Ready"] == 2
        assert counts["Disabled"] == 1


class TestGetTaskDetail:
    def test_success(self):
        stm = ScheduledTaskManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = TASK_DETAIL_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            detail = stm.get_task_detail("/JARVIS_LinkedIn_Publish")
        assert "TaskName" in detail
        assert detail["Status"] == "Ready"

    def test_failure(self):
        stm = ScheduledTaskManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert stm.get_task_detail("test") == {}


class TestEventsStats:
    def test_events_empty(self):
        assert ScheduledTaskManager().get_events() == []

    def test_stats(self):
        assert ScheduledTaskManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(scheduled_task_manager, ScheduledTaskManager)
