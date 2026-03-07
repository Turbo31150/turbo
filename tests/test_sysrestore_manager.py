"""Tests for src/sysrestore_manager.py — Windows System Restore points.

Covers: RestorePoint, RestoreEvent, SysRestoreManager (list_points,
get_latest, count_points, search, get_events, get_stats),
sysrestore_manager singleton.
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

from src.sysrestore_manager import (
    RestorePoint, RestoreEvent, SysRestoreManager, sysrestore_manager,
)

POINTS_JSON = json.dumps([
    {"SequenceNumber": 1, "Description": "Windows Update",
     "RestorePointType": 0, "CreationTime": "2026-03-01T10:00:00"},
    {"SequenceNumber": 2, "Description": "Installed NVIDIA Driver",
     "RestorePointType": 10, "CreationTime": "2026-03-05T14:30:00"},
])


class TestDataclasses:
    def test_restore_point(self):
        rp = RestorePoint(sequence=1)
        assert rp.description == ""

    def test_restore_event(self):
        e = RestoreEvent(action="list_points")
        assert e.success is True


class TestListPoints:
    def test_success(self):
        sm = SysRestoreManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = POINTS_JSON
        with patch("subprocess.run", return_value=mock_result):
            points = sm.list_points()
        assert len(points) == 2
        assert points[0]["sequence"] == 1
        assert points[0]["type"] == "APPLICATION_INSTALL"
        assert points[1]["type"] == "DEVICE_DRIVER_INSTALL"

    def test_single_dict(self):
        sm = SysRestoreManager()
        data = json.dumps({"SequenceNumber": 5, "Description": "Manual",
                           "RestorePointType": 12, "CreationTime": ""})
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            points = sm.list_points()
        assert len(points) == 1
        assert points[0]["type"] == "MODIFY_SETTINGS"

    def test_unknown_type(self):
        sm = SysRestoreManager()
        data = json.dumps([{"SequenceNumber": 1, "Description": "X",
                            "RestorePointType": 99, "CreationTime": ""}])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            points = sm.list_points()
        assert points[0]["type"] == "99"

    def test_failure(self):
        sm = SysRestoreManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert sm.list_points() == []


class TestGetLatest:
    def test_latest(self):
        sm = SysRestoreManager()
        fake = [{"sequence": 1}, {"sequence": 2}]
        with patch.object(sm, "list_points", return_value=fake):
            assert sm.get_latest()["sequence"] == 2

    def test_empty(self):
        sm = SysRestoreManager()
        with patch.object(sm, "list_points", return_value=[]):
            assert sm.get_latest() is None


class TestCountPoints:
    def test_count(self):
        sm = SysRestoreManager()
        with patch.object(sm, "list_points", return_value=[{}, {}, {}]):
            assert sm.count_points() == 3


class TestSearch:
    def test_search(self):
        sm = SysRestoreManager()
        fake = [{"description": "Windows Update"}, {"description": "NVIDIA Driver"}]
        with patch.object(sm, "list_points", return_value=fake):
            assert len(sm.search("nvidia")) == 1

    def test_search_no_match(self):
        sm = SysRestoreManager()
        with patch.object(sm, "list_points", return_value=[{"description": "X"}]):
            assert len(sm.search("nope")) == 0


class TestEventsStats:
    def test_events_empty(self):
        assert SysRestoreManager().get_events() == []

    def test_stats(self):
        assert SysRestoreManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(sysrestore_manager, SysRestoreManager)
