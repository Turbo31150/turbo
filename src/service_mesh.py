"""Service Mesh — Service discovery, load balancing, health-aware routing."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any


class LBStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONN = "least_connections"


class ServiceStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ServiceInstance:
    service_id: str
    name: str
    host: str
    port: int
    status: ServiceStatus = ServiceStatus.HEALTHY
    metadata: dict = field(default_factory=dict)
    active_connections: int = 0
    total_requests: int = 0
    total_errors: int = 0
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)


class ServiceMesh:
    """Service discovery and load balancing."""

    def __init__(self, heartbeat_timeout: float = 60.0):
        self._services: dict[str, ServiceInstance] = {}
        self._rr_counters: dict[str, int] = {}
        self._heartbeat_timeout = heartbeat_timeout
        self._lock = Lock()

    # ── Registration ────────────────────────────────────────────────
    def register(self, service_id: str, name: str, host: str, port: int,
                 metadata: dict | None = None) -> ServiceInstance:
        inst = ServiceInstance(
            service_id=service_id, name=name, host=host, port=port,
            metadata=metadata or {},
        )
        with self._lock:
            self._services[service_id] = inst
        return inst

    def deregister(self, service_id: str) -> bool:
        with self._lock:
            return self._services.pop(service_id, None) is not None

    def heartbeat(self, service_id: str) -> bool:
        inst = self._services.get(service_id)
        if not inst:
            return False
        with self._lock:
            inst.last_heartbeat = time.time()
            if inst.status == ServiceStatus.UNHEALTHY:
                inst.status = ServiceStatus.HEALTHY
        return True

    def set_status(self, service_id: str, status: ServiceStatus) -> bool:
        inst = self._services.get(service_id)
        if not inst:
            return False
        with self._lock:
            inst.status = status
        return True

    # ── Discovery ───────────────────────────────────────────────────
    def discover(self, name: str, healthy_only: bool = True) -> list[ServiceInstance]:
        with self._lock:
            instances = [s for s in self._services.values() if s.name == name]
            if healthy_only:
                instances = [s for s in instances if s.status != ServiceStatus.UNHEALTHY]
            return instances

    def get_instance(self, service_id: str) -> ServiceInstance | None:
        return self._services.get(service_id)

    def list_services(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "service_id": s.service_id, "name": s.name,
                    "host": s.host, "port": s.port,
                    "status": s.status.value,
                    "active_connections": s.active_connections,
                    "total_requests": s.total_requests,
                }
                for s in self._services.values()
            ]

    def list_service_names(self) -> list[str]:
        with self._lock:
            return list(set(s.name for s in self._services.values()))

    # ── Load Balancing ──────────────────────────────────────────────
    def resolve(self, name: str, strategy: LBStrategy = LBStrategy.ROUND_ROBIN) -> ServiceInstance | None:
        instances = self.discover(name, healthy_only=True)
        if not instances:
            return None
        if strategy == LBStrategy.RANDOM:
            return random.choice(instances)
        if strategy == LBStrategy.LEAST_CONN:
            return min(instances, key=lambda s: s.active_connections)
        # ROUND_ROBIN
        with self._lock:
            idx = self._rr_counters.get(name, 0)
            self._rr_counters[name] = (idx + 1) % len(instances)
        return instances[idx % len(instances)]

    # ── Connection Tracking ─────────────────────────────────────────
    def connect(self, service_id: str) -> bool:
        inst = self._services.get(service_id)
        if not inst:
            return False
        with self._lock:
            inst.active_connections += 1
            inst.total_requests += 1
        return True

    def disconnect(self, service_id: str) -> bool:
        inst = self._services.get(service_id)
        if not inst:
            return False
        with self._lock:
            inst.active_connections = max(0, inst.active_connections - 1)
        return True

    def record_error(self, service_id: str) -> None:
        inst = self._services.get(service_id)
        if inst:
            with self._lock:
                inst.total_errors += 1

    # ── Health Check ────────────────────────────────────────────────
    def check_heartbeats(self) -> list[str]:
        """Mark instances as unhealthy if heartbeat timed out. Return expired IDs."""
        now = time.time()
        expired = []
        with self._lock:
            for s in self._services.values():
                if now - s.last_heartbeat > self._heartbeat_timeout:
                    if s.status != ServiceStatus.UNHEALTHY:
                        s.status = ServiceStatus.UNHEALTHY
                        expired.append(s.service_id)
        return expired

    # ── Stats ───────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._services)
            healthy = sum(1 for s in self._services.values() if s.status == ServiceStatus.HEALTHY)
            degraded = sum(1 for s in self._services.values() if s.status == ServiceStatus.DEGRADED)
            unhealthy = sum(1 for s in self._services.values() if s.status == ServiceStatus.UNHEALTHY)
            total_conns = sum(s.active_connections for s in self._services.values())
            total_reqs = sum(s.total_requests for s in self._services.values())
            return {
                "total_instances": total,
                "healthy": healthy,
                "degraded": degraded,
                "unhealthy": unhealthy,
                "service_names": len(set(s.name for s in self._services.values())),
                "active_connections": total_conns,
                "total_requests": total_reqs,
            }


service_mesh = ServiceMesh()
