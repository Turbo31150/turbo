"""IP Config Manager — Windows IP configuration.

Network interfaces, IP addresses, DNS, DHCP, gateway info.
Uses ipconfig /all parsing (no external deps).
Designed for JARVIS autonomous network diagnostics.
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "IPConfigEvent",
    "IPConfigManager",
    "IPInterface",
]

logger = logging.getLogger("jarvis.ip_config_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class IPInterface:
    """A network interface."""
    name: str
    ipv4: str = ""
    subnet: str = ""
    gateway: str = ""
    dhcp_enabled: bool = False


@dataclass
class IPConfigEvent:
    """Record of an ipconfig action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class IPConfigManager:
    """Windows IP configuration reader."""

    def __init__(self) -> None:
        self._events: list[IPConfigEvent] = []
        self._lock = threading.Lock()

    def get_all(self) -> list[dict[str, Any]]:
        """Get full ipconfig /all parsed output."""
        try:
            result = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                interfaces = self._parse_ipconfig(result.stdout)
                self._record("get_all", True, f"{len(interfaces)} interfaces")
                return interfaces
        except Exception as e:
            self._record("get_all", False, str(e))
        return []

    def get_dns_servers(self) -> list[str]:
        """Extract all DNS server addresses."""
        dns = []
        for iface in self.get_all():
            for d in iface.get("dns_servers", []):
                if d and d not in dns:
                    dns.append(d)
        return dns

    def get_gateways(self) -> list[str]:
        """Extract all default gateways."""
        gws = []
        for iface in self.get_all():
            gw = iface.get("gateway", "")
            if gw and gw not in gws:
                gws.append(gw)
        return gws

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search interfaces by name."""
        q = query.lower()
        return [i for i in self.get_all() if q in i.get("name", "").lower()]

    def _parse_ipconfig(self, output: str) -> list[dict[str, Any]]:
        """Parse ipconfig /all output."""
        interfaces = []
        current: dict[str, Any] | None = None
        dns_collecting = False

        for line in output.split("\n"):
            stripped = line.strip()
            if not stripped:
                dns_collecting = False
                continue

            # New adapter section
            if not line.startswith(" ") and "adapter" in line.lower() and ":" in line:
                if current:
                    interfaces.append(current)
                name = line.split(":", 1)[0].strip()
                # Remove "Ethernet adapter", "Wireless LAN adapter" prefix
                for prefix in ("Ethernet adapter", "Wireless LAN adapter",
                               "Carte Ethernet", "Carte r\\xe9seau sans fil"):
                    if name.startswith(prefix):
                        name = name[len(prefix):].strip()
                current = {"name": name, "dns_servers": []}
                dns_collecting = False
                continue

            if current is None:
                continue

            # Key: Value pairs
            if ". :" in stripped or ":" in stripped:
                key_val = stripped.split(":", 1)
                if len(key_val) == 2:
                    key = key_val[0].strip(" .").lower()
                    val = key_val[1].strip()

                    if "ipv4" in key or "adresse ipv4" in key:
                        current["ipv4"] = val.split("(")[0].strip()
                    elif "subnet" in key or "masque" in key:
                        current["subnet"] = val
                    elif "default gateway" in key or "passerelle" in key:
                        current["gateway"] = val
                    elif "dhcp enabled" in key or "dhcp activ" in key:
                        current["dhcp_enabled"] = val.lower() in ("yes", "oui")
                    elif "physical address" in key or "adresse physique" in key:
                        current["mac"] = val
                    elif "dns server" in key or "serveurs dns" in key:
                        if val:
                            current["dns_servers"].append(val)
                        dns_collecting = True
                        continue

            # Continuation of DNS servers (indented IPs)
            if dns_collecting and re.match(r"^\d+\.\d+\.\d+\.\d+", stripped):
                current["dns_servers"].append(stripped)

            if ":" in stripped:
                dns_collecting = False

        if current:
            interfaces.append(current)
        return interfaces

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(IPConfigEvent(action=action, success=success, detail=detail))

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


ip_config_manager = IPConfigManager()
