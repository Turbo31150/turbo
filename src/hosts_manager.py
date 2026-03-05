"""Hosts Manager — Windows hosts file management.

Read, search, and query the Windows hosts file.
Direct file access to C:\\Windows\\System32\\drivers\\etc\\hosts.
Designed for JARVIS autonomous network configuration.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.hosts_manager")

HOSTS_PATH = os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"),
                          "System32", "drivers", "etc", "hosts")


@dataclass
class HostEntry:
    """A hosts file entry."""
    ip: str
    hostname: str
    comment: str = ""
    line_number: int = 0


@dataclass
class HostsEvent:
    """Record of a hosts action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class HostsManager:
    """Windows hosts file management."""

    def __init__(self) -> None:
        self._events: list[HostsEvent] = []
        self._lock = threading.Lock()

    # ── Reading ────────────────────────────────────────────────────────

    def read_entries(self) -> list[dict[str, Any]]:
        """Read all entries from hosts file."""
        entries = []
        try:
            with open(HOSTS_PATH, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    # Handle inline comments
                    comment = ""
                    if "#" in stripped:
                        stripped, _, comment = stripped.partition("#")
                        stripped = stripped.strip()
                        comment = comment.strip()
                    parts = stripped.split()
                    if len(parts) >= 2:
                        ip = parts[0]
                        for hostname in parts[1:]:
                            entries.append({
                                "ip": ip,
                                "hostname": hostname,
                                "comment": comment,
                                "line_number": i,
                            })
            self._record("read_entries", True, f"{len(entries)} entries")
        except Exception as e:
            self._record("read_entries", False, str(e))
        return entries

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search hosts by hostname or IP."""
        q = query.lower()
        return [
            e for e in self.read_entries()
            if q in e.get("hostname", "").lower() or q in e.get("ip", "").lower()
        ]

    def get_entry(self, hostname: str) -> dict[str, Any] | None:
        """Get entry for a specific hostname."""
        h = hostname.lower()
        for e in self.read_entries():
            if e.get("hostname", "").lower() == h:
                return e
        return None

    def count_entries(self) -> dict[str, int]:
        """Count entries by IP."""
        entries = self.read_entries()
        counts: dict[str, int] = {}
        for e in entries:
            ip = e.get("ip", "")
            counts[ip] = counts.get(ip, 0) + 1
        return counts

    def get_raw(self) -> str:
        """Get raw hosts file content."""
        try:
            with open(HOSTS_PATH, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return content[:5000]
        except Exception:
            return ""

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(HostsEvent(
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
        entries = self.read_entries()
        with self._lock:
            return {
                "total_entries": len(entries),
                "hosts_file": HOSTS_PATH,
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
hosts_manager = HostsManager()
