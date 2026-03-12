"""Tests for src/service_mesh.py — Service discovery, load balancing, health routing.

Covers: LBStrategy, ServiceStatus, ServiceInstance, ServiceMesh (register,
deregister, heartbeat, set_status, discover, get_instance, list_services,
list_service_names, resolve, connect, disconnect, record_error,
check_heartbeats, get_stats), service_mesh singleton.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.service_mesh import (
    LBStrategy, ServiceStatus, ServiceInstance, ServiceMesh, service_mesh,
)


# ===========================================================================
# Dataclasses / Enums
# ===========================================================================

class TestServiceInstance:
    def test_defaults(self):
        si = ServiceInstance(service_id="s1", name="api", host="localhost", port=8080)
        assert si.status == ServiceStatus.HEALTHY
        assert si.active_connections == 0
        assert si.total_requests == 0
        assert si.total_errors == 0


# ===========================================================================
# ServiceMesh — registration
# ===========================================================================

class TestRegistration:
    def test_register(self):
        sm = ServiceMesh()
        inst = sm.register("s1", "api", "127.0.0.1", 8080)
        assert inst.service_id == "s1"
        assert inst.name == "api"
        assert sm.get_instance("s1") is inst

    def test_register_with_metadata(self):
        sm = ServiceMesh()
        inst = sm.register("s1", "api", "127.0.0.1", 8080, metadata={"version": "1.0"})
        assert inst.metadata["version"] == "1.0"

    def test_deregister(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "127.0.0.1", 8080)
        assert sm.deregister("s1") is True
        assert sm.get_instance("s1") is None

    def test_deregister_nonexistent(self):
        sm = ServiceMesh()
        assert sm.deregister("nope") is False


# ===========================================================================
# ServiceMesh — heartbeat & status
# ===========================================================================

class TestHeartbeatStatus:
    def test_heartbeat(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "127.0.0.1", 8080)
        assert sm.heartbeat("s1") is True

    def test_heartbeat_restores_health(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "127.0.0.1", 8080)
        sm.set_status("s1", ServiceStatus.UNHEALTHY)
        sm.heartbeat("s1")
        assert sm.get_instance("s1").status == ServiceStatus.HEALTHY

    def test_heartbeat_nonexistent(self):
        sm = ServiceMesh()
        assert sm.heartbeat("nope") is False

    def test_set_status(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "127.0.0.1", 8080)
        assert sm.set_status("s1", ServiceStatus.DEGRADED) is True
        assert sm.get_instance("s1").status == ServiceStatus.DEGRADED

    def test_set_status_nonexistent(self):
        sm = ServiceMesh()
        assert sm.set_status("nope", ServiceStatus.HEALTHY) is False


# ===========================================================================
# ServiceMesh — discovery
# ===========================================================================

class TestDiscovery:
    def test_discover_by_name(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        sm.register("s2", "api", "h2", 8080)
        sm.register("s3", "db", "h3", 5432)
        instances = sm.discover("api")
        assert len(instances) == 2

    def test_discover_healthy_only(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        sm.register("s2", "api", "h2", 8080)
        sm.set_status("s2", ServiceStatus.UNHEALTHY)
        instances = sm.discover("api", healthy_only=True)
        assert len(instances) == 1

    def test_discover_include_unhealthy(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        sm.set_status("s1", ServiceStatus.UNHEALTHY)
        instances = sm.discover("api", healthy_only=False)
        assert len(instances) == 1

    def test_list_services(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        sm.register("s2", "db", "h2", 5432)
        services = sm.list_services()
        assert len(services) == 2
        assert services[0]["service_id"] in ("s1", "s2")

    def test_list_service_names(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        sm.register("s2", "api", "h2", 8080)
        sm.register("s3", "db", "h3", 5432)
        names = sm.list_service_names()
        assert set(names) == {"api", "db"}


# ===========================================================================
# ServiceMesh — load balancing
# ===========================================================================

class TestResolve:
    def test_resolve_round_robin(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        sm.register("s2", "api", "h2", 8080)
        first = sm.resolve("api", LBStrategy.ROUND_ROBIN)
        second = sm.resolve("api", LBStrategy.ROUND_ROBIN)
        assert first.service_id != second.service_id

    def test_resolve_random(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        result = sm.resolve("api", LBStrategy.RANDOM)
        assert result is not None

    def test_resolve_least_connections(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        sm.register("s2", "api", "h2", 8080)
        sm.connect("s1")
        sm.connect("s1")
        result = sm.resolve("api", LBStrategy.LEAST_CONN)
        assert result.service_id == "s2"

    def test_resolve_no_instances(self):
        sm = ServiceMesh()
        assert sm.resolve("nonexistent") is None


# ===========================================================================
# ServiceMesh — connection tracking
# ===========================================================================

class TestConnectionTracking:
    def test_connect_disconnect(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        sm.connect("s1")
        assert sm.get_instance("s1").active_connections == 1
        assert sm.get_instance("s1").total_requests == 1
        sm.disconnect("s1")
        assert sm.get_instance("s1").active_connections == 0

    def test_connect_nonexistent(self):
        sm = ServiceMesh()
        assert sm.connect("nope") is False

    def test_disconnect_nonexistent(self):
        sm = ServiceMesh()
        assert sm.disconnect("nope") is False

    def test_disconnect_no_negative(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        sm.disconnect("s1")
        assert sm.get_instance("s1").active_connections == 0

    def test_record_error(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        sm.record_error("s1")
        assert sm.get_instance("s1").total_errors == 1


# ===========================================================================
# ServiceMesh — health check
# ===========================================================================

class TestCheckHeartbeats:
    def test_expired_heartbeat(self):
        sm = ServiceMesh(heartbeat_timeout=1.0)
        sm.register("s1", "api", "h1", 8080)
        sm.get_instance("s1").last_heartbeat = time.time() - 10
        expired = sm.check_heartbeats()
        assert "s1" in expired
        assert sm.get_instance("s1").status == ServiceStatus.UNHEALTHY

    def test_no_expired(self):
        sm = ServiceMesh(heartbeat_timeout=60.0)
        sm.register("s1", "api", "h1", 8080)
        expired = sm.check_heartbeats()
        assert expired == []


# ===========================================================================
# ServiceMesh — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        sm = ServiceMesh()
        sm.register("s1", "api", "h1", 8080)
        sm.register("s2", "db", "h2", 5432)
        sm.set_status("s2", ServiceStatus.DEGRADED)
        stats = sm.get_stats()
        assert stats["total_instances"] == 2
        assert stats["healthy"] == 1
        assert stats["degraded"] == 1
        assert stats["service_names"] == 2

    def test_stats_empty(self):
        sm = ServiceMesh()
        stats = sm.get_stats()
        assert stats["total_instances"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert service_mesh is not None
        assert isinstance(service_mesh, ServiceMesh)
