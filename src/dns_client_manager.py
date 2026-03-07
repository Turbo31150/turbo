"""DNS Client Manager — Windows DNS client configuration and cache.

Read DNS cache, client settings via Get-DnsClientCache, Get-DnsClientServerAddress.
Designed for JARVIS autonomous network diagnostics.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.dns_client_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class DNSCacheEntry:
    """A DNS cache entry."""
    name: str
    record_type: str = ""
    data: str = ""
    ttl: int = 0


@dataclass
class DNSEvent:
    """Record of a DNS client action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class DNSClientManager:
    """Windows DNS client configuration reader (read-only)."""

    def __init__(self) -> None:
        self._events: list[DNSEvent] = []
        self._lock = threading.Lock()

    def get_server_addresses(self) -> list[dict[str, Any]]:
        """Get DNS server addresses per interface."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-DnsClientServerAddress -ErrorAction SilentlyContinue | "
                 "Where-Object { $_.ServerAddresses.Count -gt 0 } | "
                 "Select-Object InterfaceAlias, AddressFamily, ServerAddresses | "
                 "ConvertTo-Json -Depth 2 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                entries = []
                for d in data:
                    entries.append({
                        "interface": d.get("InterfaceAlias", "") or "",
                        "address_family": d.get("AddressFamily", 0),
                        "servers": d.get("ServerAddresses", []) or [],
                    })
                self._record("get_server_addresses", True, f"{len(entries)} interfaces")
                return entries
        except Exception as e:
            self._record("get_server_addresses", False, str(e))
        return []

    def get_cache(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get DNS client cache entries."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"Get-DnsClientCache -ErrorAction SilentlyContinue | "
                 f"Select-Object -First {min(limit, 200)} Entry, RecordName, Data, TimeToLive, Type | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, timeout=15,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                entries = []
                for d in data:
                    entries.append({
                        "entry": d.get("Entry", d.get("RecordName", "")) or "",
                        "data": str(d.get("Data", "")),
                        "ttl": d.get("TimeToLive", 0) or 0,
                        "type": d.get("Type", 0),
                    })
                self._record("get_cache", True, f"{len(entries)} entries")
                return entries
        except Exception as e:
            self._record("get_cache", False, str(e))
        return []

    def search_cache(self, query: str) -> list[dict[str, Any]]:
        """Search DNS cache by entry name."""
        q = query.lower()
        return [e for e in self.get_cache(200) if q in e.get("entry", "").lower()]

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(DNSEvent(action=action, success=success, detail=detail))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {"total_events": len(self._events)}


dns_client_manager = DNSClientManager()
