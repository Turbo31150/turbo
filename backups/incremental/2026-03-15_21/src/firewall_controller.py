"""Firewall Controller — Windows Firewall rule management.

List, add, remove, enable/disable firewall rules.
Uses netsh advfirewall via subprocess (no external deps).
Designed for JARVIS autonomous network security management.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "FirewallController",
    "FirewallEvent",
    "FirewallRule",
]

logger = logging.getLogger("jarvis.firewall_controller")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class FirewallRule:
    """A firewall rule."""
    name: str
    direction: str = ""
    action: str = ""
    protocol: str = ""
    local_port: str = ""
    remote_port: str = ""
    program: str = ""
    enabled: str = ""
    profile: str = ""


@dataclass
class FirewallEvent:
    """Record of a firewall action."""
    action: str
    rule_name: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class FirewallController:
    """Windows Firewall management via netsh advfirewall."""

    def __init__(self) -> None:
        self._events: list[FirewallEvent] = []
        self._lock = threading.Lock()

    # ── Firewall Status ────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Get firewall profiles status."""
        profiles = {}
        for profile in ("domain", "private", "public"):
            try:
                result = subprocess.run(
                    ["netsh", "advfirewall", "show", f"{profile}profile"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                    creationflags=_NO_WINDOW,
                )
                state = "unknown"
                for line in result.stdout.split("\n"):
                    if "State" in line and "ON" in line.upper():
                        state = "on"
                        break
                    elif "State" in line and "OFF" in line.upper():
                        state = "off"
                        break
                profiles[profile] = state
            except Exception:
                profiles[profile] = "error"
        return profiles

    # ── Rule Listing ───────────────────────────────────────────────────

    def list_rules(self, direction: str = "") -> list[dict[str, Any]]:
        """List firewall rules. direction: 'in' or 'out' or '' for all."""
        cmd = ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"]
        if direction.lower() in ("in", "inbound"):
            cmd.extend(["dir=in"])
        elif direction.lower() in ("out", "outbound"):
            cmd.extend(["dir=out"])
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                creationflags=_NO_WINDOW,
            )
            rules = self._parse_rules(result.stdout)
            self._record("list_rules", "", True, f"{len(rules)} rules")
            return rules
        except Exception as e:
            self._record("list_rules", "", False, str(e))
            return []

    def _parse_rules(self, output: str) -> list[dict[str, Any]]:
        """Parse netsh firewall output into rule dicts."""
        rules = []
        current: dict[str, str] = {}
        for line in output.split("\n"):
            line = line.strip()
            if not line or line.startswith("-"):
                if current.get("name"):
                    rules.append(current)
                    current = {}
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip().lower().replace(" ", "_")
                val = val.strip()
                # Normalize common field names
                field_map = {
                    "rule_name": "name", "direction": "direction",
                    "action": "action", "protocol": "protocol",
                    "localport": "local_port", "remoteport": "remote_port",
                    "program": "program", "enabled": "enabled",
                    "profiles": "profile",
                }
                mapped = field_map.get(key, key)
                current[mapped] = val
        if current.get("name"):
            rules.append(current)
        return rules

    def search_rules(self, query: str) -> list[dict[str, Any]]:
        """Search rules by name."""
        q = query.lower()
        return [r for r in self.list_rules() if q in r.get("name", "").lower()]

    def get_rule(self, name: str) -> dict[str, Any] | None:
        """Get a specific rule by exact name."""
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            rules = self._parse_rules(result.stdout)
            return rules[0] if rules else None
        except Exception:
            return None

    # ── Rule Count ─────────────────────────────────────────────────────

    def count_rules(self) -> dict[str, int]:
        """Count rules by direction."""
        rules = self.list_rules()
        counts: dict[str, int] = {"inbound": 0, "outbound": 0, "total": len(rules)}
        for r in rules:
            d = r.get("direction", "").lower()
            if "in" in d:
                counts["inbound"] += 1
            elif "out" in d:
                counts["outbound"] += 1
        return counts

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, rule_name: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(FirewallEvent(
                action=action, rule_name=rule_name, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "rule_name": e.rule_name,
                 "timestamp": e.timestamp, "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        status = self.get_status()
        with self._lock:
            return {
                "profiles": status,
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
firewall_controller = FirewallController()
