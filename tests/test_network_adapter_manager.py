"""Tests for src/network_adapter_manager.py — Windows network adapters.

Covers: NetworkAdapter, NetAdapterEvent, NetworkAdapterManager (list_adapters,
search, count_by_status, get_events, get_stats),
network_adapter_manager singleton.
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

from src.network_adapter_manager import (
    NetworkAdapter, NetAdapterEvent, NetworkAdapterManager, network_adapter_manager,
)

ADAPTERS_JSON = json.dumps([
    {"Name": "Ethernet", "InterfaceDescription": "Intel I211 Gigabit",
     "Status": "Up", "LinkSpeed": "1 Gbps", "MacAddress": "AA-BB-CC-DD-EE-FF",
     "ifIndex": 5, "MediaType": "802.3"},
    {"Name": "Wi-Fi", "InterfaceDescription": "Intel AX200",
     "Status": "Disconnected", "LinkSpeed": "", "MacAddress": "11-22-33-44-55-66",
     "ifIndex": 8, "MediaType": "Native 802.11"},
])


class TestDataclasses:
    def test_network_adapter(self):
        a = NetworkAdapter(name="Ethernet")
        assert a.status == ""
        assert a.mac_address == ""

    def test_net_adapter_event(self):
        e = NetAdapterEvent(action="list")
        assert e.success is True


class TestListAdapters:
    def test_success(self):
        nam = NetworkAdapterManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ADAPTERS_JSON
        with patch("subprocess.run", return_value=mock_result):
            adapters = nam.list_adapters()
        assert len(adapters) == 2
        assert adapters[0]["name"] == "Ethernet"
        assert adapters[0]["link_speed"] == "1 Gbps"
        assert adapters[1]["status"] == "Disconnected"

    def test_single_dict(self):
        nam = NetworkAdapterManager()
        data = json.dumps({"Name": "Eth", "InterfaceDescription": "Test",
                           "Status": "Up", "LinkSpeed": "100 Mbps",
                           "MacAddress": "AA-BB", "ifIndex": 1, "MediaType": ""})
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            assert len(nam.list_adapters()) == 1

    def test_failure(self):
        nam = NetworkAdapterManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert nam.list_adapters() == []


class TestSearch:
    def test_search_by_name(self):
        nam = NetworkAdapterManager()
        fake = [{"name": "Ethernet", "description": "Intel"},
                {"name": "Wi-Fi", "description": "AX200"}]
        with patch.object(nam, "list_adapters", return_value=fake):
            assert len(nam.search("ethernet")) == 1

    def test_search_by_description(self):
        nam = NetworkAdapterManager()
        fake = [{"name": "Ethernet", "description": "Intel I211"}]
        with patch.object(nam, "list_adapters", return_value=fake):
            assert len(nam.search("intel")) == 1


class TestCountByStatus:
    def test_count(self):
        nam = NetworkAdapterManager()
        fake = [{"status": "Up"}, {"status": "Up"}, {"status": "Disconnected"}]
        with patch.object(nam, "list_adapters", return_value=fake):
            counts = nam.count_by_status()
        assert counts["Up"] == 2
        assert counts["Disconnected"] == 1


class TestEventsStats:
    def test_events_empty(self):
        assert NetworkAdapterManager().get_events() == []

    def test_stats(self):
        assert NetworkAdapterManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(network_adapter_manager, NetworkAdapterManager)
