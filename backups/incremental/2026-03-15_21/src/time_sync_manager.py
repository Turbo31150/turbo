"""Time Sync Manager — Windows time synchronization management.

NTP status, time source, last sync, drift detection.
Uses w32tm command + PowerShell (no external deps).
Designed for JARVIS autonomous time management.
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
    "TimeSyncEvent",
    "TimeSyncInfo",
    "TimeSyncManager",
]

logger = logging.getLogger("jarvis.time_sync_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class TimeSyncInfo:
    """Time sync information."""
    source: str = ""
    last_sync: str = ""
    stratum: int = 0


@dataclass
class TimeSyncEvent:
    """Record of a time sync action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class TimeSyncManager:
    """Windows time synchronization management."""

    def __init__(self) -> None:
        self._events: list[TimeSyncEvent] = []
        self._lock = threading.Lock()

    # ── Time Status ───────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Get W32Time service status."""
        try:
            result = subprocess.run(
                ["w32tm", "/query", "/status"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                info = self._parse_w32tm(result.stdout)
                self._record("get_status", True)
                return info
        except Exception as e:
            self._record("get_status", False, str(e))
        return {"error": "Unable to query time status"}

    def get_source(self) -> dict[str, Any]:
        """Get current time source."""
        try:
            result = subprocess.run(
                ["w32tm", "/query", "/source"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                return {"source": result.stdout.strip()}
        except Exception:
            pass
        return {"source": "unknown"}

    def get_peers(self) -> list[dict[str, Any]]:
        """Get NTP peers."""
        try:
            result = subprocess.run(
                ["w32tm", "/query", "/peers"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                return self._parse_peers(result.stdout)
        except Exception:
            pass
        return []

    def get_configuration(self) -> dict[str, Any]:
        """Get W32Time configuration."""
        try:
            result = subprocess.run(
                ["w32tm", "/query", "/configuration"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                return self._parse_config(result.stdout)
        except Exception:
            pass
        return {}

    # ── Parsers ───────────────────────────────────────────────────────────

    def _parse_w32tm(self, output: str) -> dict[str, Any]:
        """Parse w32tm /query /status output."""
        info: dict[str, Any] = {}
        for line in output.split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                if key:
                    info[key] = value
        return info

    def _parse_peers(self, output: str) -> list[dict[str, Any]]:
        """Parse w32tm /query /peers output."""
        peers: list[dict[str, Any]] = []
        current: dict[str, Any] = {}
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("Peer:") or line.startswith("Homologue"):
                if current:
                    peers.append(current)
                current = {"peer": line.split(":", 1)[-1].strip()}
            elif ":" in line and current:
                key, _, value = line.partition(":")
                current[key.strip().lower().replace(" ", "_")] = value.strip()
        if current:
            peers.append(current)
        return peers

    def _parse_config(self, output: str) -> dict[str, Any]:
        """Parse w32tm /query /configuration output (key-value pairs)."""
        config: dict[str, Any] = {}
        for line in output.split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("["):
                key, _, value = line.partition(":")
                key = key.strip()
                if key:
                    config[key] = value.strip()
        return config

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(TimeSyncEvent(
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
time_sync_manager = TimeSyncManager()
