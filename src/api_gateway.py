"""API Gateway — Centralized routing with rate limiting.

Routes API requests to backend services with per-client
rate limiting, request logging, and health checks.
Thread-safe.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Callable

logger = logging.getLogger("jarvis.api_gateway")


@dataclass
class RouteConfig:
    """
    Configuration for a route.
    """
    path: str
    service: str
    handler: Callable | None = None
    rate_limit: int = 100  # requests per window
    window_s: float = 60.0
    enabled: bool = True
    call_count: int = 0
    error_count: int = 0


@dataclass
class ClientState:
    """
    State representation for a client.
    """
    client_id: str
    request_count: int = 0
    window_start: float = field(default_factory=time.time)
    blocked_until: float = 0.0
    total_requests: int = 0


class ApiGateway:
    """Centralized API gateway with routing and rate limiting."""

    def __init__(self, global_rate_limit: int = 1000, window_s: float = 60.0):
        self._routes: dict[str, RouteConfig] = {}
        self._clients: dict[str, ClientState] = {}
        self._lock = threading.Lock()
        self._global_rate_limit = global_rate_limit
        self._window_s = window_s
        self._request_log: list[dict] = []
        self._max_log = 500

    def register_route(
        self,
        path: str,
        service: str,
        handler: Callable | None = None,
        rate_limit: int = 100,
    ) -> None:
        self._routes[path] = RouteConfig(
            path=path, service=service, handler=handler, rate_limit=rate_limit,
        )

    def remove_route(self, path: str) -> bool:
        """
        Remove a route from the routes dictionary and return True if it existed.
        """
        return self._routes.pop(path, None) is not None

    def request(self, path: str, client_id: str = "anonymous", data: dict | None = None) -> dict:
        """Process an API request through the gateway."""
        now = time.time()

        with self._lock:
            # Check route
            route = self._routes.get(path)
            if not route or not route.enabled:
                return {"status": 404, "error": "Route not found or disabled"}

            # Check client rate limit
            client = self._clients.get(client_id)
            if not client:
                client = ClientState(client_id=client_id)
                self._clients[client_id] = client

            # Reset window if expired
            if now - client.window_start > self._window_s:
                client.request_count = 0
                client.window_start = now

            # Check block
            if client.blocked_until > now:
                return {"status": 429, "error": "Client blocked", "retry_after": client.blocked_until - now}

            # Check rate limit
            if client.request_count >= route.rate_limit:
                client.blocked_until = now + self._window_s
                return {"status": 429, "error": "Rate limit exceeded"}

            client.request_count += 1
            client.total_requests += 1
            route.call_count += 1

        # Execute handler outside lock
        result = {"status": 200, "data": None}
        if route.handler:
            try:
                result["data"] = route.handler(data or {})
            except Exception as e:
                with self._lock:
                    route.error_count += 1
                result = {"status": 500, "error": str(e)}

        # Log request
        with self._lock:
            self._request_log.append({
                "ts": now, "path": path, "client": client_id,
                "status": result["status"],
            })
            if len(self._request_log) > self._max_log:
                self._request_log = self._request_log[-self._max_log:]

        return result

    def get_routes(self) -> list[dict]:
        """
        Returns a list of routes with their configuration details.
        """
        return [
            {"path": r.path, "service": r.service, "enabled": r.enabled,
             "rate_limit": r.rate_limit, "call_count": r.call_count,
             "error_count": r.error_count}
            for r in self._routes.values()
        ]

    def get_clients(self) -> list[dict]:
        """
        RÃ©cupÃ¨re les informations des clients.
        """
        return [
            {"client_id": c.client_id, "total_requests": c.total_requests,
             "current_window_count": c.request_count}
            for c in self._clients.values()
        ]

    def get_request_log(self, limit: int = 50) -> list[dict]:
        """
        Retrieve the last N request logs.

        Args:
            limit (int): Number of logs to retrieve. Defaults to 50.

        Returns:
            list[dict]: List of the last N request logs.
        """
        return self._request_log[-limit:]

    def get_stats(self) -> dict:
        """
        Returns statistics about the API gateway, including total number of routes.
        """
        routes = list(self._routes.values())
        return {
            "total_routes": len(routes),
            "enabled_routes": sum(1 for r in routes if r.enabled),
            "total_clients": len(self._clients),
            "total_requests": sum(c.total_requests for c in self._clients.values()),
            "total_errors": sum(r.error_count for r in routes),
            "log_size": len(self._request_log),
        }


# ── Singleton ────────────────────────────────────────────────────────────────
api_gateway = ApiGateway()
