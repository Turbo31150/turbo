"""Network Monitor — Windows network adapter and connectivity monitoring.

List adapters, IP addresses, DNS, ping, connection status.
Uses subprocess with ipconfig/netsh (no external deps).
Designed for JARVIS autonomous network monitoring.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.network_monitor")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class NetworkAdapter:
    """A network adapter."""
    name: str
    status: str = ""
    ip_address: str = ""
    mac_address: str = ""
    speed: str = ""
    adapter_type: str = ""


@dataclass
class NetworkEvent:
    """Record of a network action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class NetworkMonitor:
    """Windows network monitoring."""

    def __init__(self) -> None:
        self._events: list[NetworkEvent] = []
        self._lock = threading.Lock()

    # ── Adapter Listing ────────────────────────────────────────────────

    def list_adapters(self) -> list[dict[str, Any]]:
        """List all network adapters."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-NetAdapter | Select-Object Name, Status, MacAddress, "
                 "LinkSpeed, InterfaceDescription | ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, timeout=15,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                adapters = []
                for a in data:
                    adapters.append({
                        "name": a.get("Name", ""),
                        "status": a.get("Status", ""),
                        "mac_address": a.get("MacAddress", ""),
                        "speed": a.get("LinkSpeed", ""),
                        "description": a.get("InterfaceDescription", ""),
                    })
                self._record("list_adapters", True, f"{len(adapters)} adapters")
                return adapters
        except Exception as e:
            self._record("list_adapters", False, str(e))
        return []

    def get_ip_config(self) -> list[dict[str, Any]]:
        """Get IP configuration for all adapters."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-NetIPAddress -AddressFamily IPv4 | "
                 "Select-Object InterfaceAlias, IPAddress, PrefixLength | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                return [
                    {
                        "interface": d.get("InterfaceAlias", ""),
                        "ip_address": d.get("IPAddress", ""),
                        "prefix_length": d.get("PrefixLength", 0),
                    }
                    for d in data
                ]
        except Exception:
            pass
        return []

    def get_dns_servers(self) -> list[dict[str, Any]]:
        """Get configured DNS servers."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-DnsClientServerAddress -AddressFamily IPv4 | "
                 "Where-Object {$_.ServerAddresses.Count -gt 0} | "
                 "Select-Object InterfaceAlias, ServerAddresses | "
                 "ConvertTo-Json -Depth 2"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                return [
                    {
                        "interface": d.get("InterfaceAlias", ""),
                        "servers": d.get("ServerAddresses", []),
                    }
                    for d in data
                ]
        except Exception:
            pass
        return []

    def ping(self, host: str = "8.8.8.8", count: int = 4) -> dict[str, Any]:
        """Ping a host and return results."""
        try:
            result = subprocess.run(
                ["ping", "-n", str(min(count, 10)), host],
                capture_output=True, text=True, timeout=30,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            output = result.stdout
            # Parse average time
            avg_ms = 0.0
            for line in output.split("\n"):
                if "Average" in line or "Moyenne" in line:
                    parts = line.split("=")
                    if parts:
                        try:
                            avg_ms = float(parts[-1].strip().replace("ms", ""))
                        except ValueError:
                            pass
            success = result.returncode == 0
            self._record("ping", success, f"{host}: {'ok' if success else 'fail'}")
            return {
                "host": host,
                "success": success,
                "avg_ms": avg_ms,
                "output": output[:500],
            }
        except Exception as e:
            self._record("ping", False, str(e))
            return {"host": host, "success": False, "avg_ms": 0, "output": str(e)}

    def get_connections(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get active TCP connections."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"Get-NetTCPConnection -State Established | "
                 f"Select-Object -First {limit} LocalAddress, LocalPort, "
                 f"RemoteAddress, RemotePort, OwningProcess | "
                 f"ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, timeout=15,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                return [
                    {
                        "local": f"{c.get('LocalAddress', '')}:{c.get('LocalPort', '')}",
                        "remote": f"{c.get('RemoteAddress', '')}:{c.get('RemotePort', '')}",
                        "pid": c.get("OwningProcess", 0),
                    }
                    for c in data
                ]
        except Exception:
            pass
        return []

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(NetworkEvent(
                action=action, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
network_monitor = NetworkMonitor()
