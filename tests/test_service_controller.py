"""Tests for src/service_controller.py — Windows Services management.

Covers: ServiceInfo, ServiceEvent, ServiceController (watch, unwatch,
list_watched, _record, get_events, get_stats, search, start/stop/restart
with mocked subprocess), service_controller singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.service_controller import (
    ServiceInfo, ServiceEvent, ServiceController, service_controller,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestServiceInfo:
    def test_defaults(self):
        s = ServiceInfo(name="wuauserv")
        assert s.display_name == ""
        assert s.status == ""
        assert s.pid == 0


class TestServiceEvent:
    def test_defaults(self):
        e = ServiceEvent(service="wuauserv", action="start")
        assert e.success is True
        assert e.detail == ""
        assert e.timestamp > 0


# ===========================================================================
# ServiceController — watch/unwatch
# ===========================================================================

class TestWatch:
    def test_watch_existing(self):
        sc = ServiceController()
        with patch.object(sc, "get_service", return_value={"exists": True, "status": "RUNNING"}):
            assert sc.watch("wuauserv") is True
        assert len(sc.list_watched()) == 1

    def test_watch_nonexistent(self):
        sc = ServiceController()
        with patch.object(sc, "get_service", return_value={"exists": False}):
            assert sc.watch("fake_service") is False

    def test_unwatch(self):
        sc = ServiceController()
        sc._watched["test"] = "RUNNING"
        assert sc.unwatch("test") is True
        assert sc.unwatch("test") is False

    def test_list_watched(self):
        sc = ServiceController()
        sc._watched["svc1"] = "RUNNING"
        sc._watched["svc2"] = "STOPPED"
        result = sc.list_watched()
        assert len(result) == 2

    def test_check_watched_no_change(self):
        sc = ServiceController()
        sc._watched["svc1"] = "RUNNING"
        with patch.object(sc, "get_service", return_value={"status": "RUNNING"}):
            changes = sc.check_watched()
        assert changes == []

    def test_check_watched_status_change(self):
        sc = ServiceController()
        sc._watched["svc1"] = "RUNNING"
        with patch.object(sc, "get_service", return_value={"status": "STOPPED"}):
            changes = sc.check_watched()
        assert len(changes) == 1
        assert changes[0]["old_status"] == "RUNNING"
        assert changes[0]["new_status"] == "STOPPED"


# ===========================================================================
# ServiceController — start/stop/restart (mocked subprocess)
# ===========================================================================

class TestControl:
    def test_start_success(self):
        sc = ServiceController()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "SERVICE_NAME: test\n  STATE: RUNNING"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = sc.start_service("test")
        assert result["success"] is True

    def test_start_failure(self):
        sc = ServiceController()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Access denied"
        with patch("subprocess.run", return_value=mock_result):
            result = sc.start_service("test")
        assert result["success"] is False

    def test_stop_success(self):
        sc = ServiceController()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "STOPPED"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = sc.stop_service("test")
        assert result["success"] is True

    def test_restart(self):
        sc = ServiceController()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "OK"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result), \
             patch("time.sleep"):
            result = sc.restart_service("test")
        assert result["success"] is True

    def test_start_exception(self):
        sc = ServiceController()
        with patch("subprocess.run", side_effect=Exception("timeout")):
            result = sc.start_service("test")
        assert result["success"] is False
        assert "timeout" in result["error"]


# ===========================================================================
# ServiceController — search (mocked)
# ===========================================================================

class TestSearch:
    def test_search(self):
        sc = ServiceController()
        mock_services = [
            {"name": "wuauserv", "display_name": "Windows Update"},
            {"name": "Spooler", "display_name": "Print Spooler"},
        ]
        with patch.object(sc, "list_services", return_value=mock_services):
            results = sc.search("update")
        assert len(results) == 1
        assert results[0]["name"] == "wuauserv"


# ===========================================================================
# ServiceController — events / stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        sc = ServiceController()
        assert sc.get_events() == []

    def test_events_recorded(self):
        sc = ServiceController()
        sc._record("test", "start", True, "ok")
        events = sc.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "start"

    def test_stats(self):
        sc = ServiceController()
        sc._record("a", "start", True)
        sc._watched["svc1"] = "RUNNING"
        stats = sc.get_stats()
        assert stats["total_events"] == 1
        assert stats["watched_services"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert service_controller is not None
        assert isinstance(service_controller, ServiceController)
