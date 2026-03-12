"""Tests for src/service_registry.py — Microservice discovery.

Covers: ServiceEntry, ServiceRegistry (register, deregister, heartbeat,
get, find, list_services, cleanup_stale, get_stats),
service_registry singleton.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.service_registry import ServiceEntry, ServiceRegistry, service_registry


# ===========================================================================
# ServiceEntry
# ===========================================================================

class TestServiceEntry:
    def test_defaults(self):
        s = ServiceEntry(name="api", url="http://localhost:8000")
        assert s.service_type == "generic"
        assert s.health_status == "unknown"
        assert s.is_alive is True

    def test_is_alive_expired(self):
        s = ServiceEntry(name="old", url="http://x", ttl_s=0.01)
        time.sleep(0.02)
        assert s.is_alive is False


# ===========================================================================
# ServiceRegistry — register & deregister
# ===========================================================================

class TestRegisterDeregister:
    def test_register(self):
        sr = ServiceRegistry()
        entry = sr.register("api", "http://localhost:8000", service_type="rest")
        assert entry.name == "api"
        assert sr.get("api") is not None

    def test_register_update(self):
        sr = ServiceRegistry()
        sr.register("api", "http://old")
        sr.register("api", "http://new")
        assert sr.get("api").url == "http://new"
        assert sr.get("api").heartbeat_count == 1

    def test_deregister(self):
        sr = ServiceRegistry()
        sr.register("temp", "http://x")
        assert sr.deregister("temp") is True
        assert sr.get("temp") is None

    def test_deregister_nonexistent(self):
        sr = ServiceRegistry()
        assert sr.deregister("nope") is False


# ===========================================================================
# ServiceRegistry — heartbeat
# ===========================================================================

class TestHeartbeat:
    def test_heartbeat(self):
        sr = ServiceRegistry()
        sr.register("api", "http://x")
        assert sr.heartbeat("api", "healthy") is True
        assert sr.get("api").health_status == "healthy"
        assert sr.get("api").heartbeat_count == 1

    def test_heartbeat_nonexistent(self):
        sr = ServiceRegistry()
        assert sr.heartbeat("nope") is False


# ===========================================================================
# ServiceRegistry — find
# ===========================================================================

class TestFind:
    def test_find_by_type(self):
        sr = ServiceRegistry()
        sr.register("api", "http://a", service_type="rest")
        sr.register("ws", "ws://b", service_type="websocket")
        results = sr.find(service_type="rest")
        assert len(results) == 1
        assert results[0].name == "api"

    def test_find_healthy_only(self):
        sr = ServiceRegistry()
        sr.register("api", "http://a")
        sr.heartbeat("api", "healthy")
        sr.register("bad", "http://b")
        sr.heartbeat("bad", "unhealthy")
        results = sr.find(healthy_only=True)
        assert len(results) == 1
        assert results[0].name == "api"


# ===========================================================================
# ServiceRegistry — list_services
# ===========================================================================

class TestListServices:
    def test_list(self):
        sr = ServiceRegistry()
        sr.register("a", "http://a")
        sr.register("b", "http://b")
        services = sr.list_services()
        assert len(services) == 2
        names = {s["name"] for s in services}
        assert names == {"a", "b"}


# ===========================================================================
# ServiceRegistry — cleanup_stale
# ===========================================================================

class TestCleanupStale:
    def test_cleanup(self):
        sr = ServiceRegistry()
        sr.register("stale", "http://x", ttl_s=0.01)
        time.sleep(0.02)
        count = sr.cleanup_stale()
        assert count == 1
        assert sr.get("stale") is None

    def test_cleanup_keeps_alive(self):
        sr = ServiceRegistry()
        sr.register("alive", "http://x", ttl_s=300)
        count = sr.cleanup_stale()
        assert count == 0
        assert sr.get("alive") is not None


# ===========================================================================
# ServiceRegistry — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        sr = ServiceRegistry()
        sr.register("a", "http://a", service_type="rest")
        sr.register("b", "http://b", service_type="ws")
        sr.deregister("b")
        stats = sr.get_stats()
        assert stats["total_services"] == 1
        assert stats["total_deregistered"] == 1
        assert "rest" in stats["types"]


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert service_registry is not None
        assert isinstance(service_registry, ServiceRegistry)
