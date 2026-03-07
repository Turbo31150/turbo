"""Tests for src/shadow_copy_manager.py — Windows Volume Shadow Copy.

Covers: ShadowCopy, ShadowEvent, ShadowCopyManager (list_copies,
count_copies, get_summary, get_events, get_stats),
shadow_copy_manager singleton.
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

from src.shadow_copy_manager import (
    ShadowCopy, ShadowEvent, ShadowCopyManager, shadow_copy_manager,
)

COPIES_JSON = json.dumps([
    {"ID": "{abc-123}", "VolumeName": "\\\\?\\Volume{aaa}\\",
     "InstallDate": "2026-03-01T10:00:00", "State": 12,
     "DeviceObject": "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1"},
    {"ID": "{def-456}", "VolumeName": "\\\\?\\Volume{aaa}\\",
     "InstallDate": {"DateTime": "2026-03-05"}, "State": 12,
     "DeviceObject": "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy2"},
])


class TestDataclasses:
    def test_shadow_copy(self):
        s = ShadowCopy()
        assert s.shadow_id == ""
        assert s.state == ""

    def test_shadow_event(self):
        e = ShadowEvent(action="list_copies")
        assert e.success is True


class TestListCopies:
    def test_success(self):
        scm = ShadowCopyManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = COPIES_JSON
        with patch("subprocess.run", return_value=mock_result):
            copies = scm.list_copies()
        assert len(copies) == 2
        assert copies[0]["shadow_id"] == "{abc-123}"
        assert copies[0]["state"] == "12"

    def test_install_date_dict(self):
        scm = ShadowCopyManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = COPIES_JSON
        with patch("subprocess.run", return_value=mock_result):
            copies = scm.list_copies()
        assert "2026-03-05" in copies[1]["install_date"]

    def test_single_dict(self):
        scm = ShadowCopyManager()
        data = json.dumps({"ID": "{x}", "VolumeName": "V",
                           "InstallDate": "", "State": 0, "DeviceObject": ""})
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            assert len(scm.list_copies()) == 1

    def test_failure(self):
        scm = ShadowCopyManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert scm.list_copies() == []


class TestCountCopies:
    def test_count(self):
        scm = ShadowCopyManager()
        with patch.object(scm, "list_copies", return_value=[{}, {}, {}]):
            assert scm.count_copies() == 3


class TestGetSummary:
    def test_summary(self):
        scm = ShadowCopyManager()
        fake = [{"volume_name": "V1"}, {"volume_name": "V1"}, {"volume_name": "V2"}]
        with patch.object(scm, "list_copies", return_value=fake):
            s = scm.get_summary()
        assert s["total_copies"] == 3
        assert s["volumes_with_copies"] == 2

    def test_summary_empty(self):
        scm = ShadowCopyManager()
        with patch.object(scm, "list_copies", return_value=[]):
            s = scm.get_summary()
        assert s["total_copies"] == 0
        assert s["volumes_with_copies"] == 0


class TestEventsStats:
    def test_events_empty(self):
        assert ShadowCopyManager().get_events() == []

    def test_stats(self):
        assert ShadowCopyManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(shadow_copy_manager, ShadowCopyManager)
