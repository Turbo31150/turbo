"""Tests for src/disk_monitor.py — Windows disk space monitoring and alerts.

Covers: DriveInfo, DiskAlert, DiskSnapshot, DRIVE_TYPES, DiskMonitor
(set/remove_threshold, check_thresholds, get_alerts, take_snapshot,
list_snapshots, compare_snapshots, get_stats), disk_monitor singleton.
Note: list_drives/get_drive use ctypes/shutil — tested via mock.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.disk_monitor import (
    DriveInfo, DiskAlert, DiskSnapshot, DRIVE_TYPES, DiskMonitor, disk_monitor,
)


# ===========================================================================
# Dataclasses & Constants
# ===========================================================================

class TestDriveInfo:
    def test_defaults(self):
        d = DriveInfo(letter="C", total_gb=500, used_gb=300, free_gb=200, percent_used=60.0)
        assert d.label == ""
        assert d.drive_type == ""


class TestDiskAlert:
    def test_defaults(self):
        a = DiskAlert(drive="C", threshold=90, current=95)
        assert a.resolved is False
        assert a.timestamp > 0


class TestDiskSnapshot:
    def test_defaults(self):
        s = DiskSnapshot(snapshot_id="s1")
        assert s.drives == []
        assert s.timestamp > 0


class TestDriveTypes:
    def test_known_types(self):
        assert DRIVE_TYPES[3] == "fixed"
        assert DRIVE_TYPES[2] == "removable"
        assert DRIVE_TYPES[4] == "network"


# ===========================================================================
# DiskMonitor — thresholds
# ===========================================================================

class TestThresholds:
    def test_set_threshold(self):
        dm = DiskMonitor()
        dm.set_threshold("C", 90.0)
        assert dm._thresholds["C"] == 90.0

    def test_set_threshold_case(self):
        dm = DiskMonitor()
        dm.set_threshold("c", 85.0)
        assert dm._thresholds["C"] == 85.0

    def test_remove_threshold(self):
        dm = DiskMonitor()
        dm.set_threshold("C", 90.0)
        assert dm.remove_threshold("C") is True
        assert dm.remove_threshold("C") is False

    def test_check_thresholds_triggered(self):
        dm = DiskMonitor()
        dm.set_threshold("C", 80.0)
        with patch.object(dm, "get_drive", return_value={"percent_used": 95.0}):
            alerts = dm.check_thresholds()
        assert len(alerts) == 1
        assert alerts[0]["drive"] == "C"
        assert alerts[0]["current"] == 95.0

    def test_check_thresholds_ok(self):
        dm = DiskMonitor()
        dm.set_threshold("C", 90.0)
        with patch.object(dm, "get_drive", return_value={"percent_used": 50.0}):
            alerts = dm.check_thresholds()
        assert len(alerts) == 0


# ===========================================================================
# DiskMonitor — alerts
# ===========================================================================

class TestAlerts:
    def test_get_alerts_empty(self):
        dm = DiskMonitor()
        assert dm.get_alerts() == []

    def test_get_alerts_with_data(self):
        dm = DiskMonitor()
        dm._alerts.append(DiskAlert(drive="C", threshold=90, current=95))
        alerts = dm.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]["drive"] == "C"


# ===========================================================================
# DiskMonitor — snapshots
# ===========================================================================

class TestSnapshots:
    def test_take_snapshot(self):
        dm = DiskMonitor()
        mock_drives = [
            {"letter": "C", "total_gb": 500, "used_gb": 300, "free_gb": 200, "percent_used": 60.0},
        ]
        with patch.object(dm, "list_drives", return_value=mock_drives):
            snap = dm.take_snapshot()
        assert snap.snapshot_id == "dsnap_1"
        assert len(snap.drives) == 1

    def test_list_snapshots(self):
        dm = DiskMonitor()
        with patch.object(dm, "list_drives", return_value=[]):
            dm.take_snapshot()
            dm.take_snapshot()
        result = dm.list_snapshots()
        assert len(result) == 2

    def test_compare_snapshots(self):
        dm = DiskMonitor()
        with patch.object(dm, "list_drives", side_effect=[
            [{"letter": "C", "total_gb": 500, "used_gb": 300, "free_gb": 200, "percent_used": 60.0}],
            [{"letter": "C", "total_gb": 500, "used_gb": 350, "free_gb": 150, "percent_used": 70.0}],
        ]):
            s1 = dm.take_snapshot()
            s2 = dm.take_snapshot()
        result = dm.compare_snapshots(s1.snapshot_id, s2.snapshot_id)
        assert len(result["changes"]) == 1
        assert result["changes"][0]["delta_gb"] == 50.0

    def test_compare_not_found(self):
        dm = DiskMonitor()
        result = dm.compare_snapshots("nope_a", "nope_b")
        assert "error" in result


# ===========================================================================
# DiskMonitor — get_stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        dm = DiskMonitor()
        mock_drives = [
            {"letter": "C", "total_gb": 500, "free_gb": 200},
            {"letter": "F", "total_gb": 400, "free_gb": 100},
        ]
        with patch.object(dm, "list_drives", return_value=mock_drives):
            dm.set_threshold("C", 90)
            stats = dm.get_stats()
        assert stats["drive_count"] == 2
        assert stats["total_space_gb"] == 900.0
        assert stats["total_free_gb"] == 300.0
        assert stats["thresholds"]["C"] == 90


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert disk_monitor is not None
        assert isinstance(disk_monitor, DiskMonitor)
