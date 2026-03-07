"""Tests for src/hosts_manager.py — Windows hosts file management.

Covers: HostEntry, HostsEvent, HostsManager (read_entries, search,
get_entry, count_entries, get_raw, get_events, get_stats),
hosts_manager singleton. File reads are mocked via tmp_path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hosts_manager import (
    HostEntry, HostsEvent, HostsManager, hosts_manager,
)

HOSTS_CONTENT = """\
# Hosts file
127.0.0.1       localhost
::1             localhost
192.168.1.100   server.local  # my server
10.0.0.1        gateway.local
"""


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_host_entry(self):
        h = HostEntry(ip="127.0.0.1", hostname="localhost")
        assert h.comment == ""

    def test_hosts_event(self):
        e = HostsEvent(action="read_entries")
        assert e.success is True


# ===========================================================================
# HostsManager — read_entries
# ===========================================================================

class TestReadEntries:
    def test_parse(self, tmp_path):
        hosts = tmp_path / "hosts"
        hosts.write_text(HOSTS_CONTENT, encoding="utf-8")
        hm = HostsManager()
        with patch("src.hosts_manager.HOSTS_PATH", str(hosts)):
            entries = hm.read_entries()
        assert len(entries) >= 4
        ips = [e["ip"] for e in entries]
        assert "127.0.0.1" in ips
        assert "10.0.0.1" in ips

    def test_inline_comment(self, tmp_path):
        hosts = tmp_path / "hosts"
        hosts.write_text("192.168.1.1 myhost # comment\n", encoding="utf-8")
        hm = HostsManager()
        with patch("src.hosts_manager.HOSTS_PATH", str(hosts)):
            entries = hm.read_entries()
        assert entries[0]["comment"] == "comment"

    def test_file_not_found(self):
        hm = HostsManager()
        with patch("src.hosts_manager.HOSTS_PATH", "/nonexistent/hosts"):
            entries = hm.read_entries()
        assert entries == []


# ===========================================================================
# HostsManager — search
# ===========================================================================

class TestSearch:
    def test_by_hostname(self):
        hm = HostsManager()
        fake = [{"hostname": "server.local", "ip": "192.168.1.1"},
                {"hostname": "gateway.local", "ip": "10.0.0.1"}]
        with patch.object(hm, "read_entries", return_value=fake):
            results = hm.search("server")
        assert len(results) == 1

    def test_by_ip(self):
        hm = HostsManager()
        fake = [{"hostname": "server.local", "ip": "192.168.1.1"},
                {"hostname": "gateway.local", "ip": "10.0.0.1"}]
        with patch.object(hm, "read_entries", return_value=fake):
            results = hm.search("192.168")
        assert len(results) == 1


# ===========================================================================
# HostsManager — get_entry
# ===========================================================================

class TestGetEntry:
    def test_found(self):
        hm = HostsManager()
        fake = [{"hostname": "localhost", "ip": "127.0.0.1"}]
        with patch.object(hm, "read_entries", return_value=fake):
            entry = hm.get_entry("localhost")
        assert entry is not None

    def test_not_found(self):
        hm = HostsManager()
        with patch.object(hm, "read_entries", return_value=[]):
            assert hm.get_entry("nope") is None


# ===========================================================================
# HostsManager — get_raw
# ===========================================================================

class TestGetRaw:
    def test_raw(self, tmp_path):
        hosts = tmp_path / "hosts"
        hosts.write_text(HOSTS_CONTENT, encoding="utf-8")
        hm = HostsManager()
        with patch("src.hosts_manager.HOSTS_PATH", str(hosts)):
            raw = hm.get_raw()
        assert "localhost" in raw

    def test_raw_not_found(self):
        hm = HostsManager()
        with patch("src.hosts_manager.HOSTS_PATH", "/nonexistent"):
            raw = hm.get_raw()
        assert raw == ""


# ===========================================================================
# Events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        hm = HostsManager()
        assert hm.get_events() == []

    def test_stats(self):
        hm = HostsManager()
        fake = [{"ip": "127.0.0.1", "hostname": "localhost"}]
        with patch.object(hm, "read_entries", return_value=fake):
            stats = hm.get_stats()
        assert stats["total_entries"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert hosts_manager is not None
        assert isinstance(hosts_manager, HostsManager)
