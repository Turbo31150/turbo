"""Tests for src/api_gateway.py — Centralized routing with rate limiting.

Covers: RouteConfig, ClientState, ApiGateway (register_route, remove_route,
request, get_routes, get_clients, get_request_log, get_stats),
api_gateway singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api_gateway import RouteConfig, ClientState, ApiGateway, api_gateway


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestRouteConfig:
    def test_defaults(self):
        rc = RouteConfig(path="/api/test", service="test-svc")
        assert rc.rate_limit == 100
        assert rc.enabled is True
        assert rc.call_count == 0


class TestClientState:
    def test_defaults(self):
        cs = ClientState(client_id="c1")
        assert cs.request_count == 0
        assert cs.total_requests == 0


# ===========================================================================
# ApiGateway — routes
# ===========================================================================

class TestRoutes:
    def test_register_route(self):
        gw = ApiGateway()
        gw.register_route("/api/test", "test-svc")
        routes = gw.get_routes()
        assert len(routes) == 1
        assert routes[0]["path"] == "/api/test"

    def test_register_with_handler(self):
        gw = ApiGateway()
        gw.register_route("/api/echo", "echo-svc", handler=lambda d: d)
        result = gw.request("/api/echo", data={"msg": "hi"})
        assert result["status"] == 200
        assert result["data"] == {"msg": "hi"}

    def test_remove_route(self):
        gw = ApiGateway()
        gw.register_route("/api/test", "svc")
        assert gw.remove_route("/api/test") is True
        assert gw.remove_route("/api/test") is False

    def test_request_unknown_route(self):
        gw = ApiGateway()
        result = gw.request("/api/unknown")
        assert result["status"] == 404


# ===========================================================================
# ApiGateway — request processing
# ===========================================================================

class TestRequest:
    def test_basic_request(self):
        gw = ApiGateway()
        gw.register_route("/api/test", "svc")
        result = gw.request("/api/test", client_id="user1")
        assert result["status"] == 200

    def test_handler_exception(self):
        gw = ApiGateway()
        def bad_handler(data):
            raise ValueError("boom")
        gw.register_route("/api/fail", "svc", handler=bad_handler)
        result = gw.request("/api/fail")
        assert result["status"] == 500
        assert "boom" in result["error"]

    def test_disabled_route(self):
        gw = ApiGateway()
        gw.register_route("/api/test", "svc")
        gw._routes["/api/test"].enabled = False
        result = gw.request("/api/test")
        assert result["status"] == 404

    def test_increments_counters(self):
        gw = ApiGateway()
        gw.register_route("/api/test", "svc")
        gw.request("/api/test", client_id="u1")
        gw.request("/api/test", client_id="u1")
        routes = gw.get_routes()
        assert routes[0]["call_count"] == 2


# ===========================================================================
# ApiGateway — rate limiting
# ===========================================================================

class TestRateLimiting:
    def test_rate_limit_exceeded(self):
        gw = ApiGateway()
        gw.register_route("/api/test", "svc", rate_limit=3)
        for _ in range(3):
            gw.request("/api/test", client_id="u1")
        result = gw.request("/api/test", client_id="u1")
        assert result["status"] == 429

    def test_different_clients_independent(self):
        gw = ApiGateway()
        gw.register_route("/api/test", "svc", rate_limit=2)
        gw.request("/api/test", client_id="u1")
        gw.request("/api/test", client_id="u1")
        # u1 is limited, but u2 is fine
        result = gw.request("/api/test", client_id="u2")
        assert result["status"] == 200


# ===========================================================================
# ApiGateway — clients & logs
# ===========================================================================

class TestClientsLogs:
    def test_get_clients(self):
        gw = ApiGateway()
        gw.register_route("/api/test", "svc")
        gw.request("/api/test", client_id="u1")
        clients = gw.get_clients()
        assert len(clients) == 1
        assert clients[0]["client_id"] == "u1"
        assert clients[0]["total_requests"] == 1

    def test_get_request_log(self):
        gw = ApiGateway()
        gw.register_route("/api/test", "svc")
        gw.request("/api/test")
        log = gw.get_request_log()
        assert len(log) == 1
        assert log[0]["path"] == "/api/test"
        assert log[0]["status"] == 200


# ===========================================================================
# ApiGateway — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        gw = ApiGateway()
        gw.register_route("/api/a", "svc1")
        gw.register_route("/api/b", "svc2")
        gw.request("/api/a", client_id="u1")
        stats = gw.get_stats()
        assert stats["total_routes"] == 2
        assert stats["total_clients"] == 1
        assert stats["total_requests"] == 1

    def test_stats_empty(self):
        gw = ApiGateway()
        stats = gw.get_stats()
        assert stats["total_routes"] == 0
        assert stats["total_requests"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert api_gateway is not None
        assert isinstance(api_gateway, ApiGateway)
