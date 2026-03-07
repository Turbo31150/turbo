"""Tests for src/recycle_bin_manager.py — Windows Recycle Bin management.

Covers: RecycleBinInfo, RecycleBinEvent, RecycleBinManager (get_info,
_get_info_fallback, is_empty, get_events, get_stats),
recycle_bin_manager singleton.
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

from src.recycle_bin_manager import (
    RecycleBinInfo, RecycleBinEvent, RecycleBinManager, recycle_bin_manager,
)

INFO_JSON = json.dumps({"count": 15, "size_bytes": 52428800})


class TestDataclasses:
    def test_recycle_bin_info(self):
        r = RecycleBinInfo()
        assert r.item_count == 0

    def test_recycle_bin_event(self):
        e = RecycleBinEvent(action="get_info")
        assert e.success is True


class TestGetInfo:
    def test_success(self):
        rbm = RecycleBinManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = INFO_JSON
        with patch("subprocess.run", return_value=mock_result):
            info = rbm.get_info()
        assert info["item_count"] == 15
        assert info["size_mb"] == 50.0

    def test_failure_uses_fallback(self):
        rbm = RecycleBinManager()
        fallback_result = MagicMock()
        fallback_result.returncode = 0
        fallback_result.stdout = "3"
        with patch("subprocess.run", side_effect=[Exception("fail"), fallback_result]):
            info = rbm.get_info()
        assert info["item_count"] == 3

    def test_total_failure(self):
        rbm = RecycleBinManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            info = rbm.get_info()
        assert info["item_count"] == 0


class TestGetInfoFallback:
    def test_fallback_success(self):
        rbm = RecycleBinManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "7"
        with patch("subprocess.run", return_value=mock_result):
            info = rbm._get_info_fallback()
        assert info["item_count"] == 7
        assert info["size_mb"] == 0

    def test_fallback_failure(self):
        rbm = RecycleBinManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            info = rbm._get_info_fallback()
        assert info["item_count"] == 0


class TestIsEmpty:
    def test_empty(self):
        rbm = RecycleBinManager()
        with patch.object(rbm, "get_info", return_value={"item_count": 0}):
            assert rbm.is_empty() is True

    def test_not_empty(self):
        rbm = RecycleBinManager()
        with patch.object(rbm, "get_info", return_value={"item_count": 5}):
            assert rbm.is_empty() is False


class TestEventsStats:
    def test_events_empty(self):
        assert RecycleBinManager().get_events() == []

    def test_stats(self):
        assert RecycleBinManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(recycle_bin_manager, RecycleBinManager)
