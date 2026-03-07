"""Network Scanner — Local network host discovery and port scanning.

Ping hosts, scan ports, detect network changes, maintain scan history.
Designed for JARVIS autonomous network surveillance on Windows.
"""

from __future__ import annotations

import logging
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.network_scanner")


@dataclass
class HostInfo:
    """Information about a network host."""
    ip: str
    hostname: str = ""
    alive: bool = False
    open_ports: list[int] = field(default_factory=list)
    last_seen: float = 0.0
    response_ms: float = 0.0


@dataclass
class ScanResult:
    """Result of a network scan."""
    scan_id: str
    scan_type: str  # ping, port, full
    target: str
    hosts_found: int = 0
    hosts: list[HostInfo] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0


@dataclass
class ScanProfile:
    """Reusable scan configuration."""
    name: str
    targets: list[str] = field(default_factory=list)  # IPs or ranges
    ports: list[int] = field(default_factory=list)
    scan_type: str = "ping"
    timeout_ms: int = 1000


class NetworkScanner:
    """Network scanning with host discovery and port checking."""

    def __init__(self) -> None:
        self._profiles: dict[str, ScanProfile] = {}
        self._history: list[ScanResult] = []
        self._known_hosts: dict[str, HostInfo] = {}
        self._scan_counter = 0
        self._lock = threading.Lock()

        # Default profiles
        self._profiles["cluster"] = ScanProfile(
            name="cluster",
            targets=["127.0.0.1", "192.168.1.26", "192.168.1.113"],
            ports=[1234, 11434, 9742],
            scan_type="port",
        )
        self._profiles["local"] = ScanProfile(
            name="local",
            targets=["127.0.0.1"],
            ports=[1234, 8080, 9742, 11434, 18789, 18800],
            scan_type="port",
        )

    # ── Profiles ────────────────────────────────────────────────────

    def register_profile(self, name: str, targets: list[str], ports: list[int] | None = None,
                         scan_type: str = "ping", timeout_ms: int = 1000) -> ScanProfile:
        """Register a scan profile."""
        profile = ScanProfile(name=name, targets=targets, ports=ports or [], scan_type=scan_type, timeout_ms=timeout_ms)
        with self._lock:
            self._profiles[name] = profile
        return profile

    def remove_profile(self, name: str) -> bool:
        with self._lock:
            if name in self._profiles:
                del self._profiles[name]
                return True
            return False

    def list_profiles(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": p.name, "targets": p.targets, "ports": p.ports,
                 "scan_type": p.scan_type, "timeout_ms": p.timeout_ms}
                for p in self._profiles.values()
            ]

    # ── Scanning ────────────────────────────────────────────────────

    def ping(self, ip: str, timeout_ms: int = 1000) -> dict[str, Any]:
        """Ping a single host."""
        start = time.time()
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout_ms), ip],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_ms / 1000 + 2,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            alive = result.returncode == 0
            ms = round((time.time() - start) * 1000, 1)
            host = HostInfo(ip=ip, alive=alive, response_ms=ms if alive else 0, last_seen=time.time() if alive else 0)
            # Try hostname resolution
            try:
                host.hostname = socket.gethostbyaddr(ip)[0]
            except (socket.herror, socket.gaierror):
                pass
            with self._lock:
                if alive:
                    self._known_hosts[ip] = host
            return {"ip": ip, "alive": alive, "response_ms": ms, "hostname": host.hostname}
        except Exception as e:
            return {"ip": ip, "alive": False, "error": str(e)}

    def check_port(self, ip: str, port: int, timeout_ms: int = 1000) -> dict[str, Any]:
        """Check if a specific port is open."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_ms / 1000)
            result = sock.connect_ex((ip, port))
            sock.close()
            is_open = result == 0
            return {"ip": ip, "port": port, "open": is_open}
        except Exception as e:
            return {"ip": ip, "port": port, "open": False, "error": str(e)}

    def scan_ports(self, ip: str, ports: list[int], timeout_ms: int = 1000) -> list[dict[str, Any]]:
        """Scan multiple ports on a host."""
        return [self.check_port(ip, p, timeout_ms) for p in ports]

    def run_profile(self, profile_name: str) -> ScanResult | None:
        """Execute a scan profile."""
        with self._lock:
            profile = self._profiles.get(profile_name)
            if not profile:
                return None
            self._scan_counter += 1
            scan_id = f"scan_{self._scan_counter}"

        start = time.time()
        hosts: list[HostInfo] = []

        for target in profile.targets:
            if profile.scan_type == "ping":
                result = self.ping(target, profile.timeout_ms)
                hosts.append(HostInfo(
                    ip=target, alive=result.get("alive", False),
                    response_ms=result.get("response_ms", 0),
                    hostname=result.get("hostname", ""),
                    last_seen=time.time() if result.get("alive") else 0,
                ))
            elif profile.scan_type == "port":
                ping_result = self.ping(target, profile.timeout_ms)
                port_results = self.scan_ports(target, profile.ports, profile.timeout_ms)
                open_ports = [r["port"] for r in port_results if r["open"]]
                hosts.append(HostInfo(
                    ip=target, alive=ping_result.get("alive", False) or len(open_ports) > 0,
                    open_ports=open_ports,
                    response_ms=ping_result.get("response_ms", 0),
                    hostname=ping_result.get("hostname", ""),
                    last_seen=time.time() if ping_result.get("alive") or open_ports else 0,
                ))

        duration = round((time.time() - start) * 1000, 1)
        scan = ScanResult(
            scan_id=scan_id, scan_type=profile.scan_type,
            target=",".join(profile.targets),
            hosts_found=sum(1 for h in hosts if h.alive),
            hosts=hosts, duration_ms=duration,
        )
        with self._lock:
            self._history.append(scan)
        return scan

    # ── Query ───────────────────────────────────────────────────────

    def get_known_hosts(self) -> list[dict[str, Any]]:
        """Get all known alive hosts."""
        with self._lock:
            return [
                {"ip": h.ip, "hostname": h.hostname, "alive": h.alive,
                 "open_ports": h.open_ports, "last_seen": h.last_seen}
                for h in self._known_hosts.values()
            ]

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get scan history."""
        with self._lock:
            return [
                {"scan_id": s.scan_id, "scan_type": s.scan_type, "target": s.target,
                 "hosts_found": s.hosts_found, "timestamp": s.timestamp, "duration_ms": s.duration_ms}
                for s in self._history[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        """Get scanner statistics."""
        with self._lock:
            return {
                "total_profiles": len(self._profiles),
                "total_scans": len(self._history),
                "known_hosts": len(self._known_hosts),
                "profiles": list(self._profiles.keys()),
            }


# ── Singleton ───────────────────────────────────────────────────────
network_scanner = NetworkScanner()
