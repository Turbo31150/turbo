"""Crash Dump Reader — Windows BSOD and crash dump analysis.

Read minidump files, BSOD event log entries, crash history.
Uses PowerShell Get-WinEvent + file system (no external deps).
Designed for JARVIS autonomous crash diagnostics.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "CrashDump",
    "CrashDumpReader",
    "CrashEvent",
]

logger = logging.getLogger("jarvis.crash_dump_reader")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

MINIDUMP_DIR = os.path.join(os.environ.get("SystemRoot", "/\Windows"), "Minidump")


@dataclass
class CrashDump:
    """A crash dump file."""
    filename: str
    size_kb: int = 0
    created: str = ""


@dataclass
class CrashEvent:
    """Record of a crash reader action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class CrashDumpReader:
    """Windows crash dump and BSOD reader."""

    def __init__(self) -> None:
        self._events: list[CrashEvent] = []
        self._lock = threading.Lock()

    # ── Minidumps ─────────────────────────────────────────────────────────

    def list_minidumps(self) -> list[dict[str, Any]]:
        """List minidump files."""
        dumps = []
        try:
            if os.path.isdir(MINIDUMP_DIR):
                for f in os.listdir(MINIDUMP_DIR):
                    if f.lower().endswith(".dmp"):
                        full_path = os.path.join(MINIDUMP_DIR, f)
                        try:
                            stat = os.stat(full_path)
                            dumps.append({
                                "filename": f,
                                "path": full_path,
                                "size_kb": round(stat.st_size / 1024),
                                "created": time.strftime(
                                    "%Y-%m-%d %H:%M:%S",
                                    time.localtime(stat.st_ctime),
                                ),
                            })
                        except OSError:
                            continue
            self._record("list_minidumps", True, f"{len(dumps)} dumps")
        except Exception as e:
            self._record("list_minidumps", False, str(e))
        return sorted(dumps, key=lambda d: d.get("created", ""), reverse=True)

    # ── BSOD Events ──────────────────────────────────────────────────────

    def get_bsod_events(self, max_events: int = 20) -> list[dict[str, Any]]:
        """Get BSOD/BugCheck events from System event log."""
        try:
            result = subprocess.run(
                ["bash", "-Command",
                 f"Get-WinEvent -FilterHashtable @{{LogName='System';"
                 f"Id=1001}} -MaxEvents {max_events} -ErrorAction SilentlyContinue | "
                 "Select-Object TimeCreated, Id, Message | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                events = []
                for e in data:
                    tc = e.get("TimeCreated", "")
                    if isinstance(tc, dict):
                        tc = str(tc.get("DateTime", ""))
                    msg = e.get("Message", "") or ""
                    events.append({
                        "time": str(tc),
                        "event_id": e.get("Id", 0),
                        "message": msg[:500],  # Truncate long messages
                    })
                self._record("get_bsod_events", True, f"{len(events)} events")
                return events
        except Exception as e:
            self._record("get_bsod_events", False, str(e))
        return []

    # ── Summary ───────────────────────────────────────────────────────────

    def get_crash_summary(self) -> dict[str, Any]:
        """Get crash dump summary."""
        dumps = self.list_minidumps()
        return {
            "minidump_count": len(dumps),
            "minidump_dir": MINIDUMP_DIR,
            "minidump_dir_exists": os.path.isdir(MINIDUMP_DIR),
            "latest_dump": dumps[0] if dumps else None,
        }

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(CrashEvent(
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
crash_dump_reader = CrashDumpReader()
