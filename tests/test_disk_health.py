"""Tests for src/disk_health.py — Windows disk health monitoring.

Covers: DiskInfo, DiskHealthEvent, DiskHealthMonitor (list_disks,
get_reliability, get_health_summary, get_events, get_stats),
disk_health singleton. All subprocess calls are mocked.
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

from src.disk_health import (
    DiskInfo, DiskHealthEvent, DiskHealthMonitor, disk_health,
)

GB = 1024 ** 3

DISKS_JSON = json.dumps([
    {"FriendlyName": "Samsung SSD 970", "MediaType": "SSD",
     "HealthStatus": "Healthy", "OperationalStatus": "OK",
     "Size": 500 * GB, "BusType": "NVMe"},
    {"FriendlyName": "WDC WD10", "MediaType": "HDD",
     "HealthStatus": "Healthy", "OperationalStatus": "OK",
     "Size": 1000 * GB, "BusType": "SATA"},
])

RELIABILITY_JSON = json.dumps([
    {"DeviceId": "0", "Temperature": 35, "Wear": 2,
     "ReadErrorsTotal": 0, "WriteErrorsTotal": 0, "PowerOnHours": 12000},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_disk_info(self):
        d = DiskInfo(friendly_name="Test Disk")
        assert d.media_type == ""
        assert d.health_status == ""

    def test_disk_health_event(self):
        e = DiskHealthEvent(action="list_disks")
        assert e.success is True


# ===========================================================================
# DiskHealthMonitor — list_disks
# ===========================================================================

class TestListDisks:
    def test_success(self):
        dhm = DiskHealthMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = DISKS_JSON
        with patch("subprocess.run", return_value=mock_result):
            disks = dhm.list_disks()
        assert len(disks) == 2
        assert disks[0]["friendly_name"] == "Samsung SSD 970"
        assert disks[0]["media_type"] == "SSD"
        assert disks[0]["size_gb"] == 500.0

    def test_single_disk(self):
        dhm = DiskHealthMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"FriendlyName": "Solo", "MediaType": "SSD",
             "HealthStatus": "Healthy", "OperationalStatus": "OK",
             "Size": 256 * GB, "BusType": "NVMe"}
        )
        with patch("subprocess.run", return_value=mock_result):
            disks = dhm.list_disks()
        assert len(disks) == 1

    def test_failure(self):
        dhm = DiskHealthMonitor()
        with patch("subprocess.run", side_effect=Exception("fail")):
            disks = dhm.list_disks()
        assert disks == []


# ===========================================================================
# DiskHealthMonitor — get_reliability
# ===========================================================================

class TestGetReliability:
    def test_success(self):
        dhm = DiskHealthMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = RELIABILITY_JSON
        with patch("subprocess.run", return_value=mock_result):
            counters = dhm.get_reliability()
        assert len(counters) == 1
        assert counters[0]["temperature"] == 35
        assert counters[0]["power_on_hours"] == 12000

    def test_failure(self):
        dhm = DiskHealthMonitor()
        with patch("subprocess.run", side_effect=Exception("fail")):
            counters = dhm.get_reliability()
        assert counters == []


# ===========================================================================
# DiskHealthMonitor — get_health_summary
# ===========================================================================

class TestHealthSummary:
    def test_all_healthy(self):
        dhm = DiskHealthMonitor()
        fake_disks = [
            {"health_status": "Healthy"},
            {"health_status": "Healthy"},
        ]
        with patch.object(dhm, "list_disks", return_value=fake_disks):
            summary = dhm.get_health_summary()
        assert summary["total_disks"] == 2
        assert summary["healthy"] == 2
        assert summary["unhealthy"] == 0
        assert summary["all_healthy"] is True

    def test_some_unhealthy(self):
        dhm = DiskHealthMonitor()
        fake_disks = [
            {"health_status": "Healthy"},
            {"health_status": "Warning"},
        ]
        with patch.object(dhm, "list_disks", return_value=fake_disks):
            summary = dhm.get_health_summary()
        assert summary["unhealthy"] == 1
        assert summary["all_healthy"] is False

    def test_no_disks(self):
        dhm = DiskHealthMonitor()
        with patch.object(dhm, "list_disks", return_value=[]):
            summary = dhm.get_health_summary()
        assert summary["all_healthy"] is False


# ===========================================================================
# DiskHealthMonitor — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        dhm = DiskHealthMonitor()
        assert dhm.get_events() == []

    def test_stats(self):
        dhm = DiskHealthMonitor()
        assert dhm.get_stats()["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert disk_health is not None
        assert isinstance(disk_health, DiskHealthMonitor)
