"""Tests for src/ip_config_manager.py — Windows IP configuration.

Covers: IPInterface, IPConfigEvent, IPConfigManager (get_all,
get_dns_servers, get_gateways, search, _parse_ipconfig, get_events,
get_stats), ip_config_manager singleton.
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

from src.ip_config_manager import (
    IPInterface, IPConfigEvent, IPConfigManager, ip_config_manager,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_ip_interface(self):
        iface = IPInterface(name="Ethernet")
        assert iface.ipv4 == ""
        assert iface.dhcp_enabled is False

    def test_ip_config_event(self):
        e = IPConfigEvent(action="get_all")
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# IPConfigManager — _parse_ipconfig
# ===========================================================================

IPCONFIG_OUTPUT = """
Windows IP Configuration

Ethernet adapter Ethernet:

   IPv4 Address. . . . . . . . . . . : 192.168.1.100(Preferred)
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 192.168.1.1
   DHCP Enabled. . . . . . . . . . . : Yes
   Physical Address. . . . . . . . . : AA-BB-CC-DD-EE-FF
   DNS Servers . . . . . . . . . . . : 8.8.8.8
                                        8.8.4.4

Wireless LAN adapter Wi-Fi:

   IPv4 Address. . . . . . . . . . . : 10.0.0.50
   Subnet Mask . . . . . . . . . . . : 255.255.0.0
   Default Gateway . . . . . . . . . : 10.0.0.1
   DHCP Enabled. . . . . . . . . . . : No
"""


class TestParseIPConfig:
    def test_parse_interfaces(self):
        mgr = IPConfigManager()
        interfaces = mgr._parse_ipconfig(IPCONFIG_OUTPUT)
        assert len(interfaces) == 2

    def test_parse_ipv4(self):
        mgr = IPConfigManager()
        interfaces = mgr._parse_ipconfig(IPCONFIG_OUTPUT)
        eth = interfaces[0]
        assert eth["ipv4"] == "192.168.1.100"

    def test_parse_gateway(self):
        mgr = IPConfigManager()
        interfaces = mgr._parse_ipconfig(IPCONFIG_OUTPUT)
        assert interfaces[0]["gateway"] == "192.168.1.1"

    def test_parse_dhcp(self):
        mgr = IPConfigManager()
        interfaces = mgr._parse_ipconfig(IPCONFIG_OUTPUT)
        assert interfaces[0]["dhcp_enabled"] is True
        assert interfaces[1]["dhcp_enabled"] is False

    def test_parse_dns(self):
        mgr = IPConfigManager()
        interfaces = mgr._parse_ipconfig(IPCONFIG_OUTPUT)
        dns = interfaces[0].get("dns_servers", [])
        assert "8.8.8.8" in dns
        assert "8.8.4.4" in dns

    def test_parse_mac(self):
        mgr = IPConfigManager()
        interfaces = mgr._parse_ipconfig(IPCONFIG_OUTPUT)
        assert interfaces[0]["mac"] == "AA-BB-CC-DD-EE-FF"

    def test_parse_empty(self):
        mgr = IPConfigManager()
        interfaces = mgr._parse_ipconfig("")
        assert interfaces == []


# ===========================================================================
# IPConfigManager — get_all (mocked)
# ===========================================================================

class TestGetAll:
    def test_success(self):
        mgr = IPConfigManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = IPCONFIG_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            interfaces = mgr.get_all()
        assert len(interfaces) == 2

    def test_failure(self):
        mgr = IPConfigManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            interfaces = mgr.get_all()
        assert interfaces == []


# ===========================================================================
# IPConfigManager — get_dns_servers, get_gateways
# ===========================================================================

class TestDnsGateways:
    def test_dns_servers(self):
        mgr = IPConfigManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = IPCONFIG_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            dns = mgr.get_dns_servers()
        assert "8.8.8.8" in dns

    def test_gateways(self):
        mgr = IPConfigManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = IPCONFIG_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            gws = mgr.get_gateways()
        assert "192.168.1.1" in gws
        assert "10.0.0.1" in gws


# ===========================================================================
# IPConfigManager — search
# ===========================================================================

class TestSearch:
    def test_search(self):
        mgr = IPConfigManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = IPCONFIG_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            results = mgr.search("wi-fi")
        assert len(results) == 1


# ===========================================================================
# IPConfigManager — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        mgr = IPConfigManager()
        assert mgr.get_events() == []

    def test_stats(self):
        mgr = IPConfigManager()
        stats = mgr.get_stats()
        assert stats["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert ip_config_manager is not None
        assert isinstance(ip_config_manager, IPConfigManager)
