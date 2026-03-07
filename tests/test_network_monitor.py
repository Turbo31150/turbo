"""Tests for src/network_monitor.py — Windows network adapter and connectivity monitoring.

Covers: NetworkAdapter, NetworkEvent, NetworkMonitor (list_adapters, get_ip_config,
get_dns_servers, ping, get_connections, _record, get_events, get_stats),
network_monitor singleton. All subprocess calls are mocked.
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

from src.network_monitor import (
    NetworkAdapter, NetworkEvent, NetworkMonitor, network_monitor,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestNetworkAdapter:
    def test_defaults(self):
        a = NetworkAdapter(name="Ethernet")
        assert a.status == ""
        assert a.ip_address == ""
        assert a.mac_address == ""
        assert a.speed == ""
        assert a.adapter_type == ""


class TestNetworkEvent:
    def test_defaults(self):
        e = NetworkEvent(action="ping")
        assert e.detail == ""
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# NetworkMonitor — list_adapters (mocked powershell)
# ===========================================================================

ADAPTERS_JSON = json.dumps([
    {"Name": "Ethernet", "Status": "Up", "MacAddress": "AA-BB-CC-DD-EE-FF",
     "LinkSpeed": "1 Gbps", "InterfaceDescription": "Realtek PCIe GbE"},
    {"Name": "Wi-Fi", "Status": "Disconnected", "MacAddress": "11-22-33-44-55-66",
     "LinkSpeed": "0 bps", "InterfaceDescription": "Intel Wi-Fi 6"},
])


class TestListAdapters:
    def test_parses_adapters(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ADAPTERS_JSON
        with patch("subprocess.run", return_value=mock_result):
            adapters = nm.list_adapters()
        assert len(adapters) == 2
        assert adapters[0]["name"] == "Ethernet"
        assert adapters[0]["status"] == "Up"
        assert adapters[1]["name"] == "Wi-Fi"

    def test_single_adapter_dict(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"Name": "Ethernet", "Status": "Up", "MacAddress": "AA",
             "LinkSpeed": "1 Gbps", "InterfaceDescription": "desc"})
        with patch("subprocess.run", return_value=mock_result):
            adapters = nm.list_adapters()
        assert len(adapters) == 1

    def test_empty_output(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            adapters = nm.list_adapters()
        assert adapters == []

    def test_exception(self):
        nm = NetworkMonitor()
        with patch("subprocess.run", side_effect=Exception("fail")):
            adapters = nm.list_adapters()
        assert adapters == []
        events = nm.get_events()
        assert events[-1]["success"] is False

    def test_records_event(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ADAPTERS_JSON
        with patch("subprocess.run", return_value=mock_result):
            nm.list_adapters()
        events = nm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "list_adapters"
        assert events[0]["success"] is True


# ===========================================================================
# NetworkMonitor — get_ip_config (mocked)
# ===========================================================================

IP_CONFIG_JSON = json.dumps([
    {"InterfaceAlias": "Ethernet", "IPAddress": "192.168.1.10", "PrefixLength": 24},
    {"InterfaceAlias": "Loopback", "IPAddress": "127.0.0.1", "PrefixLength": 8},
])


class TestGetIpConfig:
    def test_parses_config(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = IP_CONFIG_JSON
        with patch("subprocess.run", return_value=mock_result):
            configs = nm.get_ip_config()
        assert len(configs) == 2
        assert configs[0]["interface"] == "Ethernet"
        assert configs[0]["ip_address"] == "192.168.1.10"
        assert configs[0]["prefix_length"] == 24

    def test_single_result_dict(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"InterfaceAlias": "Ethernet", "IPAddress": "10.0.0.1", "PrefixLength": 16})
        with patch("subprocess.run", return_value=mock_result):
            configs = nm.get_ip_config()
        assert len(configs) == 1

    def test_empty(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert nm.get_ip_config() == []

    def test_exception(self):
        nm = NetworkMonitor()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert nm.get_ip_config() == []


# ===========================================================================
# NetworkMonitor — get_dns_servers (mocked)
# ===========================================================================

DNS_JSON = json.dumps([
    {"InterfaceAlias": "Ethernet", "ServerAddresses": ["8.8.8.8", "8.8.4.4"]},
])


class TestGetDnsServers:
    def test_parses_dns(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = DNS_JSON
        with patch("subprocess.run", return_value=mock_result):
            dns = nm.get_dns_servers()
        assert len(dns) == 1
        assert dns[0]["interface"] == "Ethernet"
        assert "8.8.8.8" in dns[0]["servers"]

    def test_empty(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert nm.get_dns_servers() == []

    def test_exception(self):
        nm = NetworkMonitor()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert nm.get_dns_servers() == []


# ===========================================================================
# NetworkMonitor — ping (mocked)
# ===========================================================================

PING_OUTPUT = """\
Pinging 8.8.8.8 with 32 bytes of data:
Reply from 8.8.8.8: bytes=32 time=12ms TTL=117
Reply from 8.8.8.8: bytes=32 time=11ms TTL=117

Ping statistics for 8.8.8.8:
    Minimum = 11ms, Maximum = 12ms, Average = 11ms
"""


class TestPing:
    def test_ping_success(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = PING_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            result = nm.ping("8.8.8.8", count=2)
        assert result["success"] is True
        assert result["host"] == "8.8.8.8"
        assert result["avg_ms"] == 11.0

    def test_ping_failure(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Request timed out.\n"
        with patch("subprocess.run", return_value=mock_result):
            result = nm.ping("10.0.0.99")
        assert result["success"] is False

    def test_ping_exception(self):
        nm = NetworkMonitor()
        with patch("subprocess.run", side_effect=Exception("timeout")):
            result = nm.ping("10.0.0.1")
        assert result["success"] is False
        assert "timeout" in result["output"]

    def test_ping_records_event(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = PING_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            nm.ping("8.8.8.8")
        events = nm.get_events()
        assert events[-1]["action"] == "ping"
        assert events[-1]["success"] is True

    def test_ping_count_capped(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Average = 5ms\n"
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            nm.ping("8.8.8.8", count=100)
        # count capped at 10
        call_args = mock_run.call_args[0][0]
        assert "10" in call_args

    def test_ping_french_moyenne(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Moyenne = 15ms\n"
        with patch("subprocess.run", return_value=mock_result):
            result = nm.ping("8.8.8.8")
        assert result["avg_ms"] == 15.0


# ===========================================================================
# NetworkMonitor — get_connections (mocked)
# ===========================================================================

CONNECTIONS_JSON = json.dumps([
    {"LocalAddress": "192.168.1.10", "LocalPort": 55000,
     "RemoteAddress": "142.250.74.206", "RemotePort": 443, "OwningProcess": 1234},
])


class TestGetConnections:
    def test_parses_connections(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CONNECTIONS_JSON
        with patch("subprocess.run", return_value=mock_result):
            conns = nm.get_connections()
        assert len(conns) == 1
        assert "192.168.1.10:55000" in conns[0]["local"]
        assert conns[0]["pid"] == 1234

    def test_empty(self):
        nm = NetworkMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert nm.get_connections() == []

    def test_exception(self):
        nm = NetworkMonitor()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert nm.get_connections() == []


# ===========================================================================
# NetworkMonitor — events / stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        nm = NetworkMonitor()
        assert nm.get_events() == []

    def test_events_recorded(self):
        nm = NetworkMonitor()
        nm._record("test_action", True, "detail")
        events = nm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test_action"
        assert events[0]["success"] is True

    def test_stats(self):
        nm = NetworkMonitor()
        nm._record("a", True)
        nm._record("b", False)
        stats = nm.get_stats()
        assert stats["total_events"] == 2


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert network_monitor is not None
        assert isinstance(network_monitor, NetworkMonitor)
