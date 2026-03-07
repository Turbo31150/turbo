"""Tests for src/defender_status.py — Windows Defender monitoring.

Covers: DefenderInfo, DefenderEvent, DefenderStatus (get_status,
get_threat_history, is_protected, get_events, get_stats),
defender_status singleton. All subprocess calls are mocked.
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

from src.defender_status import (
    DefenderInfo, DefenderEvent, DefenderStatus, defender_status,
)

STATUS_JSON = json.dumps({
    "AntivirusEnabled": True,
    "RealTimeProtectionEnabled": True,
    "AntispywareEnabled": True,
    "AntivirusSignatureVersion": "1.401.123.0",
    "AntivirusSignatureLastUpdated": {"DateTime": "2026-03-06T10:00:00"},
    "QuickScanEndTime": {"DateTime": "2026-03-05T08:00:00"},
    "FullScanEndTime": "2026-03-01T02:00:00",
    "ComputerState": 0,
})

THREATS_JSON = json.dumps([
    {"ThreatID": 12345, "ProcessName": "test.exe",
     "DomainUser": "DESKTOP\\user",
     "InitialDetectionTime": {"DateTime": "2026-03-05"},
     "ActionSuccess": True},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_defender_info(self):
        d = DefenderInfo()
        assert d.realtime_enabled is False

    def test_defender_event(self):
        e = DefenderEvent(action="get_status")
        assert e.success is True


# ===========================================================================
# DefenderStatus — get_status
# ===========================================================================

class TestGetStatus:
    def test_success(self):
        ds = DefenderStatus()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = STATUS_JSON
        with patch("subprocess.run", return_value=mock_result):
            status = ds.get_status()
        assert status["antivirus_enabled"] is True
        assert status["realtime_protection"] is True
        assert status["signature_version"] == "1.401.123.0"

    def test_failure(self):
        ds = DefenderStatus()
        with patch("subprocess.run", side_effect=Exception("fail")):
            status = ds.get_status()
        assert "error" in status


# ===========================================================================
# DefenderStatus — get_threat_history
# ===========================================================================

class TestThreatHistory:
    def test_success(self):
        ds = DefenderStatus()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = THREATS_JSON
        with patch("subprocess.run", return_value=mock_result):
            threats = ds.get_threat_history()
        assert len(threats) == 1
        assert threats[0]["threat_id"] == 12345
        assert threats[0]["action_success"] is True

    def test_failure(self):
        ds = DefenderStatus()
        with patch("subprocess.run", side_effect=Exception("fail")):
            threats = ds.get_threat_history()
        assert threats == []


# ===========================================================================
# DefenderStatus — is_protected
# ===========================================================================

class TestIsProtected:
    def test_protected(self):
        ds = DefenderStatus()
        fake_status = {"antivirus_enabled": True, "realtime_protection": True}
        with patch.object(ds, "get_status", return_value=fake_status):
            assert ds.is_protected() is True

    def test_not_protected(self):
        ds = DefenderStatus()
        fake_status = {"antivirus_enabled": True, "realtime_protection": False}
        with patch.object(ds, "get_status", return_value=fake_status):
            assert ds.is_protected() is False


# ===========================================================================
# DefenderStatus — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        ds = DefenderStatus()
        assert ds.get_events() == []

    def test_stats(self):
        ds = DefenderStatus()
        assert ds.get_stats()["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert defender_status is not None
        assert isinstance(defender_status, DefenderStatus)
