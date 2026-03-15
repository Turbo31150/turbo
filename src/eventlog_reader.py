"""Event Log Reader — Windows Event Log access.

Read System, Application, Security event logs.
Uses PowerShell Get-WinEvent (no external deps).
Designed for JARVIS autonomous system monitoring.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "EventLogEntry",
    "EventLogReader",
    "ReaderEvent",
]

logger = logging.getLogger("jarvis.eventlog_reader")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

KNOWN_LOGS = ["System", "Application", "Security", "Setup", "Microsoft-Windows-PowerShell/Operational"]


@dataclass
class EventLogEntry:
    """A Windows Event Log entry."""
    log_name: str
    event_id: int
    level: str = ""
    message: str = ""
    source: str = ""
    time_created: str = ""


@dataclass
class ReaderEvent:
    """Record of an event log read action."""
    action: str
    log_name: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class EventLogReader:
    """Windows Event Log reader via PowerShell."""

    def __init__(self) -> None:
        self._events: list[ReaderEvent] = []
        self._lock = threading.Lock()

    # ── Log Reading ────────────────────────────────────────────────────

    def read_log(self, log_name: str = "System", max_events: int = 50,
                 level: str = "") -> list[dict[str, Any]]:
        """Read events from a Windows Event Log."""
        filter_parts = [f"LogName='{log_name}'"]
        if level:
            level_map = {"critical": 1, "error": 2, "warning": 3, "information": 4, "verbose": 5}
            lvl = level_map.get(level.lower())
            if lvl:
                filter_parts.append(f"Level={lvl}")

        filter_xml = " and ".join(filter_parts)
        cmd = (
            f"Get-WinEvent -FilterHashtable @{{{filter_xml}}} -MaxEvents {max_events} "
            f"| Select-Object Id, LevelDisplayName, Message, ProviderName, TimeCreated "
            f"| ConvertTo-Json -Depth 1"
        )
        try:
            result = subprocess.run(
                ["bash", "-Command", cmd],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                entries = []
                for e in data:
                    msg = e.get("Message", "") or ""
                    entries.append({
                        "event_id": e.get("Id", 0),
                        "level": e.get("LevelDisplayName", ""),
                        "message": msg[:300],
                        "source": e.get("ProviderName", ""),
                        "time_created": str(e.get("TimeCreated", "")),
                    })
                self._record("read_log", log_name, True, f"{len(entries)} events")
                return entries
        except Exception as e:
            self._record("read_log", log_name, False, str(e))
        return []

    def list_logs(self) -> list[str]:
        """List available event log names."""
        try:
            result = subprocess.run(
                ["bash", "-Command",
                 "Get-WinEvent -ListLog * -ErrorAction SilentlyContinue | "
                 "Where-Object {$_.RecordCount -gt 0} | "
                 "Select-Object -ExpandProperty LogName | Sort-Object"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0:
                logs = [l.strip() for l in result.stdout.split("\n") if l.strip()]
                return logs
        except Exception:
            pass
        return KNOWN_LOGS

    def count_by_level(self, log_name: str = "System", max_events: int = 200) -> dict[str, int]:
        """Count events by level."""
        events = self.read_log(log_name=log_name, max_events=max_events)
        counts: dict[str, int] = {}
        for e in events:
            lvl = e.get("level", "unknown") or "unknown"
            counts[lvl] = counts.get(lvl, 0) + 1
        return counts

    def get_errors(self, log_name: str = "System", max_events: int = 20) -> list[dict[str, Any]]:
        """Get recent error events."""
        return self.read_log(log_name=log_name, max_events=max_events, level="error")

    def search_events(self, query: str, log_name: str = "System",
                      max_events: int = 100) -> list[dict[str, Any]]:
        """Search events by message content."""
        q = query.lower()
        events = self.read_log(log_name=log_name, max_events=max_events)
        return [e for e in events if q in e.get("message", "").lower()
                or q in e.get("source", "").lower()]

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, log_name: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(ReaderEvent(
                action=action, log_name=log_name, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "log_name": e.log_name,
                 "timestamp": e.timestamp, "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_reads": len(self._events),
                "known_logs": KNOWN_LOGS,
            }


# ── Singleton ───────────────────────────────────────────────────────
eventlog_reader = EventLogReader()
