"""Tests for src/process_manager.py — Windows process lifecycle management.

Covers: ProcessStatus enum, ProcessProfile, ProcessEvent, ProcessManager
(register, unregister, start, stop, restart, kill, get, list_processes,
list_groups, is_running, check_health, get_events, get_stats),
process_manager singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.process_manager import (
    ProcessStatus, ProcessProfile, ProcessEvent, ProcessManager, process_manager,
)


# ===========================================================================
# ProcessStatus
# ===========================================================================

class TestProcessStatus:
    def test_values(self):
        assert ProcessStatus.STOPPED.value == "stopped"
        assert ProcessStatus.RUNNING.value == "running"
        assert ProcessStatus.CRASHED.value == "crashed"
        assert ProcessStatus.RESTARTING.value == "restarting"


# ===========================================================================
# ProcessProfile
# ===========================================================================

class TestProcessProfile:
    def test_defaults(self):
        p = ProcessProfile(name="test", command="echo")
        assert p.args == []
        assert p.cwd is None
        assert p.env == {}
        assert p.auto_restart is False
        assert p.max_restarts == 3
        assert p.group == "default"
        assert p.pid is None
        assert p.status == ProcessStatus.STOPPED


# ===========================================================================
# ProcessEvent
# ===========================================================================

class TestProcessEvent:
    def test_defaults(self):
        e = ProcessEvent(name="test", event="started")
        assert e.pid is None
        assert e.exit_code is None
        assert e.detail == ""
        assert e.timestamp > 0


# ===========================================================================
# ProcessManager — register / unregister
# ===========================================================================

class TestRegister:
    def test_register(self):
        pm = ProcessManager()
        p = pm.register("test_proc", "echo", args=["hello"])
        assert p.name == "test_proc"
        assert p.command == "echo"
        assert p.args == ["hello"]

    def test_register_with_options(self):
        pm = ProcessManager()
        p = pm.register("svc", "python", auto_restart=True, max_restarts=5,
                         group="services", cwd="/tmp")
        assert p.auto_restart is True
        assert p.max_restarts == 5
        assert p.group == "services"
        assert p.cwd == "/tmp"

    def test_unregister_existing(self):
        pm = ProcessManager()
        pm.register("x", "echo")
        assert pm.unregister("x") is True
        assert pm.get("x") is None

    def test_unregister_nonexistent(self):
        pm = ProcessManager()
        assert pm.unregister("missing") is False


# ===========================================================================
# ProcessManager — start / stop
# ===========================================================================

class TestStartStop:
    def test_start_not_registered(self):
        pm = ProcessManager()
        assert pm.start("nonexistent") is False

    def test_start_success(self):
        pm = ProcessManager()
        pm.register("test", "echo", args=["hi"])
        with patch("src.process_manager.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.poll.return_value = None
            mock_popen.return_value = mock_proc
            assert pm.start("test") is True
        profile = pm.get("test")
        assert profile.pid == 12345
        assert profile.status == ProcessStatus.RUNNING

    def test_start_already_running(self):
        pm = ProcessManager()
        pm.register("test", "echo")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        pm._processes["test"] = mock_proc
        assert pm.start("test") is False

    def test_start_failure(self):
        pm = ProcessManager()
        pm.register("test", "nonexistent_binary_xyz")
        with patch("src.process_manager.subprocess.Popen", side_effect=FileNotFoundError("no such file")):
            assert pm.start("test") is False
        profile = pm.get("test")
        assert profile.status == ProcessStatus.CRASHED

    def test_stop_not_running(self):
        pm = ProcessManager()
        assert pm.stop("nonexistent") is False

    def test_stop_success(self):
        pm = ProcessManager()
        pm.register("test", "echo")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        pm._processes["test"] = mock_proc
        assert pm.stop("test") is True
        assert "test" not in pm._processes
        profile = pm.get("test")
        assert profile.status == ProcessStatus.STOPPED


# ===========================================================================
# ProcessManager — restart
# ===========================================================================

class TestRestart:
    def test_restart_not_registered(self):
        pm = ProcessManager()
        assert pm.restart("nonexistent") is False

    def test_restart_increments_count(self):
        pm = ProcessManager()
        pm.register("test", "echo")
        with patch("src.process_manager.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 999
            mock_proc.poll.return_value = None
            mock_popen.return_value = mock_proc
            pm.restart("test")
        profile = pm.get("test")
        assert profile.restart_count == 1


# ===========================================================================
# ProcessManager — kill
# ===========================================================================

class TestKill:
    def test_kill_not_running(self):
        pm = ProcessManager()
        assert pm.kill("nonexistent") is False

    def test_kill_success(self):
        pm = ProcessManager()
        pm.register("test", "echo")
        mock_proc = MagicMock()
        pm._processes["test"] = mock_proc
        assert pm.kill("test") is True
        mock_proc.kill.assert_called_once()
        assert "test" not in pm._processes


# ===========================================================================
# ProcessManager — query
# ===========================================================================

class TestQuery:
    def test_get_existing(self):
        pm = ProcessManager()
        pm.register("test", "echo")
        assert pm.get("test") is not None

    def test_get_missing(self):
        pm = ProcessManager()
        assert pm.get("missing") is None

    def test_list_processes_empty(self):
        pm = ProcessManager()
        assert pm.list_processes() == []

    def test_list_processes_with_data(self):
        pm = ProcessManager()
        pm.register("a", "echo", group="g1")
        pm.register("b", "echo", group="g2")
        result = pm.list_processes()
        assert len(result) == 2
        assert all("name" in r for r in result)

    def test_list_processes_filter_group(self):
        pm = ProcessManager()
        pm.register("a", "echo", group="web")
        pm.register("b", "echo", group="db")
        result = pm.list_processes(group="web")
        assert len(result) == 1
        assert result[0]["name"] == "a"

    def test_list_groups(self):
        pm = ProcessManager()
        pm.register("a", "echo", group="web")
        pm.register("b", "echo", group="db")
        pm.register("c", "echo", group="web")
        groups = pm.list_groups()
        assert set(groups) == {"web", "db"}

    def test_is_running_false(self):
        pm = ProcessManager()
        assert pm.is_running("nonexistent") is False

    def test_is_running_true(self):
        pm = ProcessManager()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        pm._processes["test"] = mock_proc
        assert pm.is_running("test") is True

    def test_is_running_exited(self):
        pm = ProcessManager()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        pm._processes["test"] = mock_proc
        assert pm.is_running("test") is False


# ===========================================================================
# ProcessManager — health check
# ===========================================================================

class TestCheckHealth:
    def test_not_found(self):
        pm = ProcessManager()
        result = pm.check_health("missing")
        assert result["healthy"] is False
        assert "not found" in result["error"]

    def test_running_healthy(self):
        pm = ProcessManager()
        pm.register("test", "echo")
        profile = pm.get("test")
        profile.status = ProcessStatus.RUNNING
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        pm._processes["test"] = mock_proc
        result = pm.check_health("test")
        assert result["healthy"] is True
        assert result["running"] is True

    def test_custom_health_check_fails(self):
        pm = ProcessManager()
        pm.register("test", "echo", health_check=lambda: False)
        profile = pm.get("test")
        profile.status = ProcessStatus.RUNNING
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        pm._processes["test"] = mock_proc
        result = pm.check_health("test")
        assert result["healthy"] is False

    def test_check_all_health(self):
        pm = ProcessManager()
        pm.register("a", "echo")
        pm.register("b", "echo")
        results = pm.check_all_health()
        assert len(results) == 2


# ===========================================================================
# ProcessManager — events & stats
# ===========================================================================

class TestEventsAndStats:
    def test_get_events_empty(self):
        pm = ProcessManager()
        assert pm.get_events() == []

    def test_get_events_after_actions(self):
        pm = ProcessManager()
        pm.register("test", "echo")
        with patch("src.process_manager.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 1234
            mock_proc.poll.return_value = None
            mock_popen.return_value = mock_proc
            pm.start("test")
        events = pm.get_events()
        assert len(events) >= 1
        assert events[-1]["event"] == "started"

    def test_get_events_filter_name(self):
        pm = ProcessManager()
        pm._events.append(ProcessEvent("a", "started"))
        pm._events.append(ProcessEvent("b", "started"))
        events = pm.get_events(name="a")
        assert len(events) == 1

    def test_get_stats_empty(self):
        pm = ProcessManager()
        stats = pm.get_stats()
        assert stats["total_processes"] == 0
        assert stats["running"] == 0

    def test_get_stats_with_data(self):
        pm = ProcessManager()
        pm.register("a", "echo")
        pm.register("b", "echo")
        p = pm.get("a")
        p.status = ProcessStatus.RUNNING
        p.restart_count = 2
        stats = pm.get_stats()
        assert stats["total_processes"] == 2
        assert stats["running"] == 1
        assert stats["total_restarts"] == 2


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert process_manager is not None
        assert isinstance(process_manager, ProcessManager)
