"""Service Registry — Dynamic microservice discovery with heartbeat.

Services register with a name, URL, and metadata.
Stale services are automatically deregistered after TTL expiry.
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.service_registry")

DEFAULT_TTL_S = 120.0  # 2 minutes


@dataclass
class ServiceEntry:
    name: str
    url: str
    service_type: str = "generic"
    metadata: dict = field(default_factory=dict)
    ttl_s: float = DEFAULT_TTL_S
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    health_status: str = "unknown"  # healthy, unhealthy, unknown
    heartbeat_count: int = 0

    @property
    def is_alive(self) -> bool:
        return (time.time() - self.last_heartbeat) < self.ttl_s


class ServiceRegistry:
    """Thread-safe service registry with TTL-based cleanup."""

    def __init__(self):
        self._services: dict[str, ServiceEntry] = {}
        self._lock = threading.RLock()
        self._deregistered: list[dict] = []

    def register(
        self,
        name: str,
        url: str,
        service_type: str = "generic",
        metadata: dict | None = None,
        ttl_s: float = DEFAULT_TTL_S,
    ) -> ServiceEntry:
        """Register or update a service."""
        with self._lock:
            if name in self._services:
                s = self._services[name]
                s.url = url
                s.service_type = service_type
                s.metadata = metadata or {}
                s.ttl_s = ttl_s
                s.last_heartbeat = time.time()
                s.heartbeat_count += 1
                return s
            entry = ServiceEntry(
                name=name, url=url, service_type=service_type,
                metadata=metadata or {}, ttl_s=ttl_s,
            )
            self._services[name] = entry
            return entry

    def deregister(self, name: str) -> bool:
        with self._lock:
            entry = self._services.pop(name, None)
            if entry:
                self._deregistered.append({
                    "name": entry.name, "url": entry.url,
                    "deregistered_at": time.time(),
                })
                return True
            return False

    def heartbeat(self, name: str, health_status: str = "healthy") -> bool:
        """Send heartbeat for a service. Returns False if not found."""
        with self._lock:
            entry = self._services.get(name)
            if not entry:
                return False
            entry.last_heartbeat = time.time()
            entry.health_status = health_status
            entry.heartbeat_count += 1
            return True

    def get(self, name: str) -> ServiceEntry | None:
        with self._lock:
            return self._services.get(name)

    def find(self, service_type: str | None = None, healthy_only: bool = False) -> list[ServiceEntry]:
        """Find services matching criteria."""
        with self._lock:
            results = list(self._services.values())
            if service_type:
                results = [s for s in results if s.service_type == service_type]
            if healthy_only:
                results = [s for s in results if s.is_alive and s.health_status == "healthy"]
            return results

    def list_services(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "name": s.name, "url": s.url, "type": s.service_type,
                    "health": s.health_status, "alive": s.is_alive,
                    "heartbeats": s.heartbeat_count,
                    "last_heartbeat": s.last_heartbeat,
                    "metadata": s.metadata,
                }
                for s in self._services.values()
            ]

    def cleanup_stale(self) -> int:
        """Remove services that haven't sent heartbeat within TTL. Returns count removed."""
        with self._lock:
            stale = [name for name, s in self._services.items() if not s.is_alive]
            for name in stale:
                entry = self._services.pop(name)
                self._deregistered.append({
                    "name": entry.name, "url": entry.url,
                    "deregistered_at": time.time(), "reason": "ttl_expired",
                })
            return len(stale)

    def get_stats(self) -> dict:
        with self._lock:
            alive = sum(1 for s in self._services.values() if s.is_alive)
            return {
                "total_services": len(self._services),
                "alive": alive,
                "stale": len(self._services) - alive,
                "total_deregistered": len(self._deregistered),
                "types": list(set(s.service_type for s in self._services.values())),
            }


# ── Singleton ────────────────────────────────────────────────────────────────
service_registry = ServiceRegistry()
