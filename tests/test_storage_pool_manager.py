"""Tests for src/storage_pool_manager.py — Windows Storage Spaces.

Covers: StoragePool, StorageEvent, StoragePoolManager (list_pools,
get_physical_disks, get_events, get_stats), storage_pool_manager singleton.
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

from src.storage_pool_manager import (
    StoragePool, StorageEvent, StoragePoolManager, storage_pool_manager,
)

GB = 1024 ** 3

POOLS_JSON = json.dumps([
    {"FriendlyName": "Storage Pool 1", "HealthStatus": "Healthy",
     "OperationalStatus": "OK", "Size": 2000 * GB,
     "AllocatedSize": 1500 * GB, "IsReadOnly": False},
])

DISKS_JSON = json.dumps([
    {"FriendlyName": "Samsung SSD", "MediaType": "SSD",
     "HealthStatus": "Healthy", "Size": 500 * GB,
     "BusType": "NVMe", "OperationalStatus": "OK"},
])


class TestDataclasses:
    def test_storage_pool(self):
        s = StoragePool(name="Pool1")
        assert s.health_status == ""

    def test_storage_event(self):
        e = StorageEvent(action="list_pools")
        assert e.success is True


class TestListPools:
    def test_success(self):
        spm = StoragePoolManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = POOLS_JSON
        with patch("subprocess.run", return_value=mock_result):
            pools = spm.list_pools()
        assert len(pools) == 1
        assert pools[0]["name"] == "Storage Pool 1"
        assert pools[0]["size_gb"] == 2000.0

    def test_failure(self):
        spm = StoragePoolManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert spm.list_pools() == []


class TestGetPhysicalDisks:
    def test_success(self):
        spm = StoragePoolManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = DISKS_JSON
        with patch("subprocess.run", return_value=mock_result):
            disks = spm.get_physical_disks()
        assert len(disks) == 1
        assert disks[0]["media_type"] == "SSD"

    def test_failure(self):
        spm = StoragePoolManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert spm.get_physical_disks() == []


class TestEventsStats:
    def test_events_empty(self):
        assert StoragePoolManager().get_events() == []

    def test_stats(self):
        assert StoragePoolManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(storage_pool_manager, StoragePoolManager)
