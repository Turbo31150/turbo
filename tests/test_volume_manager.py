"""Tests for src/volume_manager.py — Windows volume/partition management.

Covers: VolumeInfo, VolumeEvent, VolumeManager (list_volumes, list_partitions,
get_space_summary, search, get_events, get_stats), volume_manager singleton.
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

from src.volume_manager import (
    VolumeInfo, VolumeEvent, VolumeManager, volume_manager,
)

GB = 1024 ** 3

VOLUMES_JSON = json.dumps([
    {"DriveLetter": "C", "FileSystemLabel": "Windows", "FileSystem": "NTFS",
     "DriveType": "Fixed", "Size": 500 * GB, "SizeRemaining": 100 * GB,
     "HealthStatus": "Healthy"},
    {"DriveLetter": "F", "FileSystemLabel": "Data", "FileSystem": "NTFS",
     "DriveType": "Fixed", "Size": 450 * GB, "SizeRemaining": 140 * GB,
     "HealthStatus": "Healthy"},
])

PARTITIONS_JSON = json.dumps([
    {"DiskNumber": 0, "PartitionNumber": 1, "DriveLetter": "C",
     "Size": 500 * GB, "Type": "Basic", "IsActive": True},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_volume_info(self):
        v = VolumeInfo(drive_letter="C")
        assert v.file_system == ""
        assert v.size_gb == 0.0

    def test_volume_event(self):
        e = VolumeEvent(action="list_volumes")
        assert e.success is True


# ===========================================================================
# VolumeManager — list_volumes
# ===========================================================================

class TestListVolumes:
    def test_success(self):
        vm = VolumeManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = VOLUMES_JSON
        with patch("subprocess.run", return_value=mock_result):
            vols = vm.list_volumes()
        assert len(vols) == 2
        assert vols[0]["drive_letter"] == "C"
        assert vols[0]["label"] == "Windows"
        assert vols[0]["size_gb"] == 500.0
        assert vols[0]["free_gb"] == 100.0
        assert vols[0]["used_percent"] == 80.0

    def test_single_volume(self):
        vm = VolumeManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"DriveLetter": "D", "FileSystemLabel": "Solo", "FileSystem": "NTFS",
             "DriveType": "Fixed", "Size": 200 * GB, "SizeRemaining": 50 * GB,
             "HealthStatus": "Healthy"}
        )
        with patch("subprocess.run", return_value=mock_result):
            vols = vm.list_volumes()
        assert len(vols) == 1

    def test_failure(self):
        vm = VolumeManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            vols = vm.list_volumes()
        assert vols == []


# ===========================================================================
# VolumeManager — list_partitions
# ===========================================================================

class TestListPartitions:
    def test_success(self):
        vm = VolumeManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = PARTITIONS_JSON
        with patch("subprocess.run", return_value=mock_result):
            parts = vm.list_partitions()
        assert len(parts) == 1
        assert parts[0]["disk_number"] == 0
        assert parts[0]["drive_letter"] == "C"
        assert parts[0]["is_active"] is True

    def test_failure(self):
        vm = VolumeManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            parts = vm.list_partitions()
        assert parts == []


# ===========================================================================
# VolumeManager — get_space_summary
# ===========================================================================

class TestSpaceSummary:
    def test_summary(self):
        vm = VolumeManager()
        fake_vols = [
            {"size_gb": 500.0, "free_gb": 100.0},
            {"size_gb": 450.0, "free_gb": 140.0},
        ]
        with patch.object(vm, "list_volumes", return_value=fake_vols):
            summary = vm.get_space_summary()
        assert summary["volume_count"] == 2
        assert summary["total_gb"] == 950.0
        assert summary["free_gb"] == 240.0
        assert summary["used_gb"] == 710.0


# ===========================================================================
# VolumeManager — search
# ===========================================================================

class TestSearch:
    def test_search_by_letter(self):
        vm = VolumeManager()
        fake_vols = [
            {"drive_letter": "C", "label": "Windows"},
            {"drive_letter": "F", "label": "Data"},
        ]
        with patch.object(vm, "list_volumes", return_value=fake_vols):
            results = vm.search("c")
        assert len(results) == 1

    def test_search_by_label(self):
        vm = VolumeManager()
        fake_vols = [
            {"drive_letter": "C", "label": "Windows"},
            {"drive_letter": "F", "label": "Data"},
        ]
        with patch.object(vm, "list_volumes", return_value=fake_vols):
            results = vm.search("data")
        assert len(results) == 1


# ===========================================================================
# VolumeManager — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        vm = VolumeManager()
        assert vm.get_events() == []

    def test_stats(self):
        vm = VolumeManager()
        assert vm.get_stats()["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert volume_manager is not None
        assert isinstance(volume_manager, VolumeManager)
