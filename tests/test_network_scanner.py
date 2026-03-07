"""Tests for src/network_scanner.py — Local network host discovery and port scanning.

Covers: HostInfo, ScanResult, ScanProfile, NetworkScanner (register/remove/list
profiles, ping, check_port, scan_ports, run_profile, get_known_hosts,
get_history, get_stats), network_scanner singleton.
All subprocess and socket calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.network_scanner import (
    HostInfo, ScanResult, ScanProfile, NetworkScanner, network_scanner,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestHostInfo:
    def test_defaults(self):
        h = HostInfo(ip="192.168.1.1")
        assert h.hostname == ""
        assert h.alive is False
        assert h.open_ports == []
        assert h.last_seen == 0.0
        assert h.response_ms == 0.0


class TestScanResult:
    def test_defaults(self):
        s = ScanResult(scan_id="s1", scan_type="ping", target="192.168.1.0/24")
        assert s.hosts_found == 0
        assert s.hosts == []
        assert s.timestamp > 0
        assert s.duration_ms == 0.0


class TestScanProfile:
    def test_defaults(self):
        p = ScanProfile(name="test")
        assert p.targets == []
        assert p.ports == []
        assert p.scan_type == "ping"
        assert p.timeout_ms == 1000


# ===========================================================================
# NetworkScanner — profiles
# ===========================================================================

class TestProfiles:
    def test_default_profiles(self):
        ns = NetworkScanner()
        profiles = ns.list_profiles()
        names = [p["name"] for p in profiles]
        assert "cluster" in names
        assert "local" in names

    def test_register_profile(self):
        ns = NetworkScanner()
        p = ns.register_profile("custom", ["10.0.0.1"], ports=[80, 443])
        assert p.name == "custom"
        assert p.ports == [80, 443]
        profiles = ns.list_profiles()
        assert any(p["name"] == "custom" for p in profiles)

    def test_remove_profile(self):
        ns = NetworkScanner()
        ns.register_profile("temp", ["1.1.1.1"])
        assert ns.remove_profile("temp") is True
        assert ns.remove_profile("temp") is False

    def test_remove_nonexistent(self):
        ns = NetworkScanner()
        assert ns.remove_profile("nope") is False


# ===========================================================================
# NetworkScanner — ping (mocked subprocess)
# ===========================================================================

class TestPing:
    def test_ping_alive(self):
        ns = NetworkScanner()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result), \
             patch("socket.gethostbyaddr", return_value=("myhost", [], [])):
            result = ns.ping("127.0.0.1")
        assert result["alive"] is True
        assert result["hostname"] == "myhost"

    def test_ping_dead(self):
        ns = NetworkScanner()
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result), \
             patch("socket.gethostbyaddr", side_effect=Exception):
            result = ns.ping("10.0.0.99")
        assert result["alive"] is False

    def test_ping_exception(self):
        ns = NetworkScanner()
        with patch("subprocess.run", side_effect=Exception("timeout")):
            result = ns.ping("10.0.0.1")
        assert result["alive"] is False
        assert "error" in result

    def test_ping_hostname_resolution_failure(self):
        ns = NetworkScanner()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("src.network_scanner.subprocess") as mock_sub:
            mock_sub.run.return_value = mock_result
            mock_sub.CREATE_NO_WINDOW = 0
            import socket
            with patch.object(socket, "gethostbyaddr", side_effect=socket.herror("no host")):
                result = ns.ping("127.0.0.1")
        assert result["alive"] is True
        assert result["hostname"] == ""


# ===========================================================================
# NetworkScanner — port scanning (mocked socket)
# ===========================================================================

class TestPortScan:
    def test_check_port_open(self):
        ns = NetworkScanner()
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        with patch("socket.socket", return_value=mock_sock):
            result = ns.check_port("127.0.0.1", 9742)
        assert result["open"] is True
        assert result["port"] == 9742

    def test_check_port_closed(self):
        ns = NetworkScanner()
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1
        with patch("socket.socket", return_value=mock_sock):
            result = ns.check_port("127.0.0.1", 12345)
        assert result["open"] is False

    def test_check_port_exception(self):
        ns = NetworkScanner()
        with patch("socket.socket", side_effect=Exception("refused")):
            result = ns.check_port("127.0.0.1", 80)
        assert result["open"] is False
        assert "error" in result

    def test_scan_ports(self):
        ns = NetworkScanner()
        mock_sock = MagicMock()
        mock_sock.connect_ex.side_effect = [0, 1, 0]
        with patch("socket.socket", return_value=mock_sock):
            results = ns.scan_ports("127.0.0.1", [80, 443, 9742])
        assert len(results) == 3
        assert results[0]["open"] is True
        assert results[1]["open"] is False
        assert results[2]["open"] is True


# ===========================================================================
# NetworkScanner — run_profile (mocked)
# ===========================================================================

class TestRunProfile:
    def test_run_ping_profile(self):
        ns = NetworkScanner()
        ns.register_profile("test_ping", ["127.0.0.1"], scan_type="ping")
        mock_result = MagicMock()
        mock_result.returncode = 0
        import socket
        with patch("src.network_scanner.subprocess") as mock_sub, \
             patch.object(socket, "gethostbyaddr", side_effect=socket.herror("no host")):
            mock_sub.run.return_value = mock_result
            mock_sub.CREATE_NO_WINDOW = 0
            scan = ns.run_profile("test_ping")
        assert scan is not None
        assert scan.scan_type == "ping"
        assert scan.hosts_found >= 1

    def test_run_port_profile(self):
        ns = NetworkScanner()
        ns.register_profile("test_port", ["127.0.0.1"], ports=[80], scan_type="port")
        mock_sub = MagicMock()
        mock_sub.returncode = 0
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        with patch("subprocess.run", return_value=mock_sub), \
             patch("socket.socket", return_value=mock_sock), \
             patch("socket.gethostbyaddr", side_effect=Exception):
            scan = ns.run_profile("test_port")
        assert scan is not None
        assert scan.hosts[0].open_ports == [80]

    def test_run_nonexistent_profile(self):
        ns = NetworkScanner()
        assert ns.run_profile("nope") is None


# ===========================================================================
# NetworkScanner — query
# ===========================================================================

class TestQuery:
    def test_known_hosts_empty(self):
        ns = NetworkScanner()
        assert ns.get_known_hosts() == []

    def test_known_hosts_populated(self):
        ns = NetworkScanner()
        ns._known_hosts["127.0.0.1"] = HostInfo(ip="127.0.0.1", alive=True)
        result = ns.get_known_hosts()
        assert len(result) == 1
        assert result[0]["ip"] == "127.0.0.1"

    def test_history_empty(self):
        ns = NetworkScanner()
        assert ns.get_history() == []

    def test_stats(self):
        ns = NetworkScanner()
        stats = ns.get_stats()
        assert stats["total_profiles"] >= 2  # cluster + local
        assert stats["total_scans"] == 0
        assert "cluster" in stats["profiles"]


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert network_scanner is not None
        assert isinstance(network_scanner, NetworkScanner)
