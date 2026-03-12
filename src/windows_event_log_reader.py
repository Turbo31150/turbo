"""Windows Event Log Reader — Read Windows Event Log entries.

Query System, Application, Security logs via Get-WinEvent.
Designed for JARVIS autonomous monitoring and alerting.
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
    "LogReaderEvent",
    "WindowsEventLogReader",
]

logger = logging.getLogger("jarvis.windows_event_log_reader")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

COMMON_LOGS = ["System", "Application", "Security"]


@dataclass
class EventLogEntry:
    """A Windows Event Log entry."""
    log_name: str
    event_id: int = 0
    level: str = ""
    message: str = ""
    time_created: str = ""


@dataclass
class LogReaderEvent:
    """Record of a log reader action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class WindowsEventLogReader:
    """Windows Event Log reader (read-only)."""

    def __init__(self) -> None:
        self._events: list[LogReaderEvent] = []
        self._lock = threading.Lock()

    def get_recent(self, log_name: str = "System", max_events: int = 20) -> list[dict[str, Any]]:
        """Get recent events from a Windows log."""
        safe_log = "".join(c for c in log_name if c.isalnum() or c in "-_/ ")
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"Get-WinEvent -LogName '{safe_log}' -MaxEvents {min(max_events, 100)} "
                 "-ErrorAction SilentlyContinue | "
                 "Select-Object Id, LevelDisplayName, Message, TimeCreated, ProviderName | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                entries = []
                for e in data:
                    tc = e.get("TimeCreated", "") or ""
                    if isinstance(tc, dict):
                        tc = str(tc.get("DateTime", tc.get("value", "")))
                    msg = e.get("Message", "") or ""
                    entries.append({
                        "event_id": e.get("Id", 0),
                        "level": e.get("LevelDisplayName", "") or "",
                        "provider": e.get("ProviderName", "") or "",
                        "message": msg[:200] if len(msg) > 200 else msg,
                        "time_created": tc,
                    })
                self._record("get_recent", True, f"{safe_log}: {len(entries)} events")
                return entries
        except Exception as e:
            self._record("get_recent", False, str(e))
        return []

    def count_by_level(self, log_name: str = "System", max_events: int = 100) -> dict[str, int]:
        """Count events by level in a log."""
        events = self.get_recent(log_name, max_events)
        counts: dict[str, int] = {}
        for e in events:
            lvl = e.get("level", "Unknown") or "Unknown"
            counts[lvl] = counts.get(lvl, 0) + 1
        return counts

    def list_logs(self) -> list[str]:
        """List available log names."""
        return list(COMMON_LOGS)

    def search_events(self, log_name: str, keyword: str, max_events: int = 50) -> list[dict[str, Any]]:
        """Search events by keyword in message."""
        kw = keyword.lower()
        events = self.get_recent(log_name, max_events)
        return [e for e in events if kw in e.get("message", "").lower()]

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(LogReaderEvent(action=action, success=success, detail=detail))

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


windows_event_log_reader = WindowsEventLogReader()
