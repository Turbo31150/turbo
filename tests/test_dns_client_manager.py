"""Tests for src/dns_client_manager.py — Windows DNS client configuration.

Covers: DNSCacheEntry, DNSEvent, DNSClientManager (get_server_addresses,
get_cache, search_cache, get_events, get_stats), dns_client_manager singleton.
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

from src.dns_client_manager import (
    DNSCacheEntry, DNSEvent, DNSClientManager, dns_client_manager,
)

SERVERS_JSON = json.dumps([
    {"InterfaceAlias": "Ethernet", "AddressFamily": 2,
     "ServerAddresses": ["8.8.8.8", "8.8.4.4"]},
    {"InterfaceAlias": "Wi-Fi", "AddressFamily": 23,
     "ServerAddresses": ["2001:4860:4860::8888"]},
])

SINGLE_SERVER_JSON = json.dumps(
    {"InterfaceAlias": "Ethernet", "AddressFamily": 2,
     "ServerAddresses": ["1.1.1.1"]}
)

CACHE_JSON = json.dumps([
    {"Entry": "google.com", "RecordName": "google.com",
     "Data": "142.250.74.206", "TimeToLive": 300, "Type": 1},
    {"Entry": "github.com", "RecordName": "github.com",
     "Data": "140.82.121.4", "TimeToLive": 60, "Type": 1},
])


class TestDataclasses:
    def test_dns_cache_entry(self):
        c = DNSCacheEntry(name="test.com")
        assert c.record_type == ""
        assert c.ttl == 0

    def test_dns_event(self):
        e = DNSEvent(action="get_cache")
        assert e.success is True


class TestGetServerAddresses:
    def test_success_multiple(self):
        dm = DNSClientManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SERVERS_JSON
        with patch("subprocess.run", return_value=mock_result):
            addrs = dm.get_server_addresses()
        assert len(addrs) == 2
        assert addrs[0]["interface"] == "Ethernet"
        assert "8.8.8.8" in addrs[0]["servers"]

    def test_success_single_dict(self):
        dm = DNSClientManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SINGLE_SERVER_JSON
        with patch("subprocess.run", return_value=mock_result):
            addrs = dm.get_server_addresses()
        assert len(addrs) == 1
        assert addrs[0]["servers"] == ["1.1.1.1"]

    def test_null_fields(self):
        dm = DNSClientManager()
        data = json.dumps([{"InterfaceAlias": None, "AddressFamily": None,
                            "ServerAddresses": None}])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            addrs = dm.get_server_addresses()
        assert addrs[0]["interface"] == ""
        assert addrs[0]["servers"] == []

    def test_failure(self):
        dm = DNSClientManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert dm.get_server_addresses() == []


class TestGetCache:
    def test_success(self):
        dm = DNSClientManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CACHE_JSON
        with patch("subprocess.run", return_value=mock_result):
            cache = dm.get_cache()
        assert len(cache) == 2
        assert cache[0]["entry"] == "google.com"
        assert cache[0]["ttl"] == 300

    def test_failure(self):
        dm = DNSClientManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert dm.get_cache() == []


class TestSearchCache:
    def test_search(self):
        dm = DNSClientManager()
        fake = [{"entry": "google.com"}, {"entry": "github.com"}]
        with patch.object(dm, "get_cache", return_value=fake):
            assert len(dm.search_cache("google")) == 1

    def test_search_no_match(self):
        dm = DNSClientManager()
        fake = [{"entry": "google.com"}]
        with patch.object(dm, "get_cache", return_value=fake):
            assert len(dm.search_cache("bing")) == 0


class TestEventsStats:
    def test_events_empty(self):
        assert DNSClientManager().get_events() == []

    def test_stats(self):
        assert DNSClientManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(dns_client_manager, DNSClientManager)
