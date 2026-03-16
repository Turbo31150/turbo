"""Linux Journal Reader — Read systemd journal entries.

Query system logs via journalctl (systemd journal).
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
    "JournalEntry",
    "LogReaderEvent",
    "LinuxJournalReader",
]

logger = logging.getLogger("jarvis.linux_journal_reader")

# Équivalents Linux des logs Windows
COMMON_LOGS = ["syslog", "kernel", "auth"]

# Mapping priorité journalctl
PRIORITY_MAP = {
    "0": "Emergency",
    "1": "Alert",
    "2": "Critical",
    "3": "Error",
    "4": "Warning",
    "5": "Notice",
    "6": "Informational",
    "7": "Debug",
}


@dataclass
class JournalEntry:
    """A systemd journal entry."""
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


class LinuxJournalReader:
    """Linux systemd journal reader (read-only)."""

    def __init__(self) -> None:
        self._events: list[LogReaderEvent] = []
        self._lock = threading.Lock()

    def get_recent(self, log_name: str = "syslog", max_events: int = 20) -> list[dict[str, Any]]:
        """Get recent events from systemd journal.

        log_name can be a unit name (e.g. 'ssh', 'nginx') or a category
        like 'syslog', 'kernel', 'auth'.
        """
        safe_max = min(max_events, 100)
        cmd: list[str] = ["journalctl", "--no-pager", "-o", "json", f"-n{safe_max}"]

        # Adapter le filtre selon le type de log
        log_lower = log_name.lower()
        if log_lower == "kernel":
            cmd.append("-k")
        elif log_lower == "auth":
            cmd.extend(["-t", "sshd", "-t", "sudo", "-t", "login", "-t", "systemd-logind"])
        elif log_lower == "syslog":
            pass  # Pas de filtre = tout le journal
        else:
            # Traiter comme un nom d'unité systemd
            cmd.extend(["-u", log_name])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=20,
            )
            if result.returncode == 0 and result.stdout.strip():
                entries = []
                for line in result.stdout.strip().splitlines():
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    priority = str(data.get("PRIORITY", "6"))
                    level = PRIORITY_MAP.get(priority, "Informational")
                    msg = data.get("MESSAGE", "") or ""
                    if isinstance(msg, list):
                        msg = " ".join(str(m) for m in msg)
                    timestamp = data.get("__REALTIME_TIMESTAMP", "")
                    # Convertir timestamp microseconds → lisible
                    ts_str = ""
                    if timestamp:
                        try:
                            ts_float = int(timestamp) / 1_000_000
                            ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_float))
                        except (ValueError, OSError):
                            ts_str = str(timestamp)
                    entries.append({
                        "event_id": int(data.get("_PID", 0) or 0),
                        "level": level,
                        "provider": data.get("SYSLOG_IDENTIFIER", "") or data.get("_COMM", "") or "",
                        "message": msg[:200] if len(msg) > 200 else msg,
                        "time_created": ts_str,
                    })
                self._record("get_recent", True, f"{log_name}: {len(entries)} events")
                return entries
        except FileNotFoundError:
            self._record("get_recent", False, "journalctl not found")
        except Exception as e:
            self._record("get_recent", False, str(e))
        return []

    def count_by_level(self, log_name: str = "syslog", max_events: int = 100) -> dict[str, int]:
        """Count events by level in a log."""
        events = self.get_recent(log_name, max_events)
        counts: dict[str, int] = {}
        for e in events:
            lvl = e.get("level", "Unknown") or "Unknown"
            counts[lvl] = counts.get(lvl, 0) + 1
        return counts

    def list_logs(self) -> list[str]:
        """List available log categories."""
        return list(COMMON_LOGS)

    def search_events(self, log_name: str, keyword: str, max_events: int = 50) -> list[dict[str, Any]]:
        """Search events by keyword in message."""
        kw = keyword.lower()
        events = self.get_recent(log_name, max_events)
        return [e for e in events if kw in e.get("message", "").lower()]

    def get_errors_since(self, since: str = "1h ago") -> list[dict[str, Any]]:
        """Get error-level and above entries since a given time.

        Useful for quick health checks.
        Args:
            since: journalctl --since format, e.g. '1h ago', '2025-01-01', 'today'
        """
        try:
            result = subprocess.run(
                ["journalctl", "--no-pager", "-o", "json", "-p", "err",
                 "--since", since],
                capture_output=True, text=True, timeout=20,
            )
            if result.returncode == 0 and result.stdout.strip():
                entries = []
                for line in result.stdout.strip().splitlines():
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = data.get("MESSAGE", "") or ""
                    if isinstance(msg, list):
                        msg = " ".join(str(m) for m in msg)
                    entries.append({
                        "level": PRIORITY_MAP.get(str(data.get("PRIORITY", "3")), "Error"),
                        "provider": data.get("SYSLOG_IDENTIFIER", "") or "",
                        "message": msg[:200] if len(msg) > 200 else msg,
                    })
                return entries
        except Exception:
            pass
        return []

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


linux_journal_reader = LinuxJournalReader()
