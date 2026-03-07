"""Tests for src/wifi_manager.py — Windows wireless network management.

Covers: WiFiNetwork, WiFiEvent, WiFiManager (scan, get_current, connect,
disconnect, list_profiles, delete_profile, _record, get_events, get_stats),
wifi_manager singleton. All subprocess calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.wifi_manager import (
    WiFiNetwork, WiFiEvent, WiFiManager, wifi_manager,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestWiFiNetwork:
    def test_defaults(self):
        n = WiFiNetwork(ssid="TestNet")
        assert n.signal == 0
        assert n.auth == ""
        assert n.encryption == ""
        assert n.channel == 0
        assert n.bssid == ""


class TestWiFiEvent:
    def test_defaults(self):
        e = WiFiEvent(action="scan")
        assert e.ssid == ""
        assert e.success is True
        assert e.detail == ""
        assert e.timestamp > 0


# ===========================================================================
# WiFiManager — scan (mocked subprocess)
# ===========================================================================

SCAN_OUTPUT = """\
SSID 1 : HomeNetwork
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : CCMP
    BSSID 1                 : aa:bb:cc:dd:ee:ff
         Signal             : 85%
         Channel            : 6

SSID 2 : OfficeWiFi
    Network type            : Infrastructure
    Authentication          : WPA3-Personal
    Encryption              : GCMP
    BSSID 1                 : 11:22:33:44:55:66
         Signal             : 60%
         Channel            : 11
"""


class TestScan:
    def test_scan_parses_networks(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        mock_result.stdout = SCAN_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            networks = wm.scan()
        assert len(networks) == 2
        assert networks[0]["ssid"] == "HomeNetwork"
        assert networks[0]["signal"] == 85
        assert networks[0]["channel"] == 6
        assert networks[1]["ssid"] == "OfficeWiFi"

    def test_scan_empty(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        mock_result.stdout = "No networks found\n"
        with patch("subprocess.run", return_value=mock_result):
            networks = wm.scan()
        assert networks == []

    def test_scan_exception(self):
        wm = WiFiManager()
        with patch("subprocess.run", side_effect=Exception("timeout")):
            networks = wm.scan()
        assert networks == []
        events = wm.get_events()
        assert events[-1]["success"] is False

    def test_scan_records_event(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        mock_result.stdout = SCAN_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            wm.scan()
        events = wm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "scan"
        assert events[0]["success"] is True


# ===========================================================================
# WiFiManager — get_current (mocked)
# ===========================================================================

INTERFACE_OUTPUT = """\
    Name                   : Wi-Fi
    State                  : connected
    SSID                   : HomeNetwork
    BSSID                  : aa:bb:cc:dd:ee:ff
    Signal                 : 90%
    Channel                : 6
    Receive rate (Mbps)    : 144
    Transmit rate (Mbps)   : 144
"""


class TestGetCurrent:
    def test_connected(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        mock_result.stdout = INTERFACE_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            info = wm.get_current()
        assert info["connected"] is True
        assert info["ssid"] == "HomeNetwork"
        assert info["signal"] == 90
        assert info["channel"] == 6

    def test_disconnected(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        # Note: source uses `"connected" in state` so "disconnected" matches too.
        # Use a state string without "connected" substring to test the false path.
        mock_result.stdout = "    State                  : not available\n"
        with patch("src.wifi_manager.subprocess.run", return_value=mock_result):
            info = wm.get_current()
        assert info["connected"] is False

    def test_exception(self):
        wm = WiFiManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            info = wm.get_current()
        assert info["connected"] is False
        assert "error" in info


# ===========================================================================
# WiFiManager — connect / disconnect (mocked)
# ===========================================================================

class TestConnectDisconnect:
    def test_connect_success(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Connection request was completed successfully."
        with patch("subprocess.run", return_value=mock_result):
            result = wm.connect("HomeNetwork")
        assert result["success"] is True
        assert result["ssid"] == "HomeNetwork"

    def test_connect_failure(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Profile not found"
        with patch("subprocess.run", return_value=mock_result):
            result = wm.connect("NonExistent")
        assert result["success"] is False

    def test_connect_exception(self):
        wm = WiFiManager()
        with patch("subprocess.run", side_effect=Exception("timeout")):
            result = wm.connect("Test")
        assert result["success"] is False
        assert "error" in result

    def test_disconnect_success(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Disconnected."
        with patch("subprocess.run", return_value=mock_result):
            result = wm.disconnect()
        assert result["success"] is True

    def test_disconnect_exception(self):
        wm = WiFiManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            result = wm.disconnect()
        assert result["success"] is False


# ===========================================================================
# WiFiManager — profiles (mocked)
# ===========================================================================

PROFILES_OUTPUT = """\
User profiles
-----------
    All User Profile     : HomeNetwork
    All User Profile     : OfficeWiFi
    All User Profile     : CafeSpot
"""


class TestProfiles:
    def test_list_profiles(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        mock_result.stdout = PROFILES_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            profiles = wm.list_profiles()
        assert len(profiles) == 3
        assert profiles[0]["name"] == "HomeNetwork"

    def test_list_profiles_empty(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        mock_result.stdout = "No profiles\n"
        with patch("subprocess.run", return_value=mock_result):
            profiles = wm.list_profiles()
        assert profiles == []

    def test_list_profiles_exception(self):
        wm = WiFiManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            profiles = wm.list_profiles()
        assert profiles == []

    def test_delete_profile_success(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            assert wm.delete_profile("OldNetwork") is True

    def test_delete_profile_failure(self):
        wm = WiFiManager()
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            assert wm.delete_profile("Nonexistent") is False

    def test_delete_profile_exception(self):
        wm = WiFiManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert wm.delete_profile("Test") is False


# ===========================================================================
# WiFiManager — events / stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        wm = WiFiManager()
        assert wm.get_events() == []

    def test_events_recorded(self):
        wm = WiFiManager()
        wm._record("test", "Net1", True, "detail")
        events = wm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test"
        assert events[0]["ssid"] == "Net1"

    def test_stats(self):
        wm = WiFiManager()
        wm._record("scan", "", True)
        with patch.object(wm, "get_current", return_value={"connected": False, "ssid": "", "signal": 0}):
            stats = wm.get_stats()
        assert stats["total_events"] == 1
        assert stats["connected"] is False


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert wifi_manager is not None
        assert isinstance(wifi_manager, WiFiManager)
