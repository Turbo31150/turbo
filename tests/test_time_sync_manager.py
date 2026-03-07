"""Tests for src/time_sync_manager.py — Windows time synchronization management.

Covers: TimeSyncInfo, TimeSyncEvent, TimeSyncManager (get_status, get_source,
get_peers, get_configuration, _parse_w32tm, _parse_peers, _parse_config,
get_events, get_stats), time_sync_manager singleton.
All subprocess calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.time_sync_manager import (
    TimeSyncInfo, TimeSyncEvent, TimeSyncManager, time_sync_manager,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestTimeSyncInfo:
    def test_defaults(self):
        t = TimeSyncInfo()
        assert t.source == ""
        assert t.stratum == 0


class TestTimeSyncEvent:
    def test_defaults(self):
        e = TimeSyncEvent(action="get_status")
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# TimeSyncManager — parsers
# ===========================================================================

W32TM_STATUS = (
    "Leap Indicator: 0(no warning)\n"
    "Stratum: 3\n"
    "Source: time.windows.com\n"
    "Last Successful Sync Time: 3/7/2026 10:00:00\n"
)

PEERS_OUTPUT = (
    "Peer: time.windows.com\n"
    "State: Active\n"
    "Time Remaining: 1234s\n"
    "\n"
    "Peer: pool.ntp.org\n"
    "State: Pending\n"
)

CONFIG_OUTPUT = (
    "[TimeProviders]\n"
    "NtpServer: time.windows.com,0x9\n"
    "Type: NTP\n"
    "Enabled: 1\n"
)


class TestParsers:
    def test_parse_w32tm(self):
        tsm = TimeSyncManager()
        info = tsm._parse_w32tm(W32TM_STATUS)
        assert "stratum" in info
        assert info["stratum"] == "3"
        assert info["source"] == "time.windows.com"

    def test_parse_peers(self):
        tsm = TimeSyncManager()
        peers = tsm._parse_peers(PEERS_OUTPUT)
        assert len(peers) == 2
        assert peers[0]["peer"] == "time.windows.com"
        assert peers[1]["peer"] == "pool.ntp.org"

    def test_parse_config(self):
        tsm = TimeSyncManager()
        config = tsm._parse_config(CONFIG_OUTPUT)
        assert "NtpServer" in config
        assert config["Type"] == "NTP"


# ===========================================================================
# TimeSyncManager — get_status (mocked)
# ===========================================================================

class TestGetStatus:
    def test_success(self):
        tsm = TimeSyncManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = W32TM_STATUS
        with patch("subprocess.run", return_value=mock_result):
            status = tsm.get_status()
        assert "source" in status

    def test_failure(self):
        tsm = TimeSyncManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            status = tsm.get_status()
        assert "error" in status


# ===========================================================================
# TimeSyncManager — get_source (mocked)
# ===========================================================================

class TestGetSource:
    def test_success(self):
        tsm = TimeSyncManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "time.windows.com\n"
        with patch("subprocess.run", return_value=mock_result):
            source = tsm.get_source()
        assert source["source"] == "time.windows.com"

    def test_failure(self):
        tsm = TimeSyncManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            source = tsm.get_source()
        assert source["source"] == "unknown"


# ===========================================================================
# TimeSyncManager — get_peers (mocked)
# ===========================================================================

class TestGetPeers:
    def test_success(self):
        tsm = TimeSyncManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = PEERS_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            peers = tsm.get_peers()
        assert len(peers) == 2

    def test_failure(self):
        tsm = TimeSyncManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            peers = tsm.get_peers()
        assert peers == []


# ===========================================================================
# TimeSyncManager — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        tsm = TimeSyncManager()
        assert tsm.get_events() == []

    def test_stats(self):
        tsm = TimeSyncManager()
        stats = tsm.get_stats()
        assert stats["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert time_sync_manager is not None
        assert isinstance(time_sync_manager, TimeSyncManager)
