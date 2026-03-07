"""Network Adapter Manager — Windows network adapters inventory.

List, search network adapters via Get-NetAdapter.
Designed for JARVIS autonomous network management.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.network_adapter_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class NetworkAdapter:
    """A network adapter entry."""
    name: str
    interface_description: str = ""
    status: str = ""
    link_speed: str = ""
    mac_address: str = ""


@dataclass
class NetAdapterEvent:
    """Record of a network adapter action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class NetworkAdapterManager:
    """Windows network adapter inventory (read-only)."""

    def __init__(self) -> None:
        self._events: list[NetAdapterEvent] = []
        self._lock = threading.Lock()

    def list_adapters(self) -> list[dict[str, Any]]:
        """List all network adapters via Get-NetAdapter."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-NetAdapter -ErrorAction SilentlyContinue | "
                 "Select-Object Name, InterfaceDescription, Status, "
                 "LinkSpeed, MacAddress, ifIndex, MediaType | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                adapters = []
                for a in data:
                    adapters.append({
                        "name": a.get("Name", "") or "",
                        "description": a.get("InterfaceDescription", "") or "",
                        "status": str(a.get("Status", "")),
                        "link_speed": a.get("LinkSpeed", "") or "",
                        "mac_address": a.get("MacAddress", "") or "",
                        "if_index": a.get("ifIndex", 0),
                        "media_type": a.get("MediaType", "") or "",
                    })
                self._record("list_adapters", True, f"{len(adapters)} adapters")
                return adapters
        except Exception as e:
            self._record("list_adapters", False, str(e))
        return []

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search adapters by name or description."""
        q = query.lower()
        return [
            a for a in self.list_adapters()
            if q in a.get("name", "").lower() or q in a.get("description", "").lower()
        ]

    def count_by_status(self) -> dict[str, int]:
        """Count adapters by status."""
        counts: dict[str, int] = {}
        for a in self.list_adapters():
            s = a.get("status", "Unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(NetAdapterEvent(action=action, success=success, detail=detail))

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


network_adapter_manager = NetworkAdapterManager()
