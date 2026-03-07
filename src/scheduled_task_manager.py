"""Scheduled Task Manager — Windows Task Scheduler inventory.

List, search, and filter scheduled tasks via schtasks.exe /Query /FO CSV.
Read-only — no creation/deletion of tasks.
Designed for JARVIS autonomous system monitoring.
"""

from __future__ import annotations

import csv
import io
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.scheduled_task_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class ScheduledTask:
    """A scheduled task entry."""
    name: str
    status: str = ""
    next_run: str = ""
    last_run: str = ""
    last_result: str = ""


@dataclass
class SchedEvent:
    """Record of a scheduler action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class ScheduledTaskManager:
    """Windows Task Scheduler inventory (read-only)."""

    def __init__(self) -> None:
        self._events: list[SchedEvent] = []
        self._lock = threading.Lock()

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all scheduled tasks via schtasks /Query /FO CSV."""
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                tasks = []
                reader = csv.reader(io.StringIO(result.stdout.strip()))
                for row in reader:
                    if len(row) >= 3:
                        tasks.append({
                            "name": row[0].strip('"'),
                            "next_run": row[1].strip('"') if len(row) > 1 else "",
                            "status": row[2].strip('"') if len(row) > 2 else "",
                        })
                self._record("list_tasks", True, f"{len(tasks)} tasks")
                return tasks
        except Exception as e:
            self._record("list_tasks", False, str(e))
        return []

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search tasks by name."""
        q = query.lower()
        return [t for t in self.list_tasks() if q in t.get("name", "").lower()]

    def count_by_status(self) -> dict[str, int]:
        """Count tasks by status."""
        counts: dict[str, int] = {}
        for t in self.list_tasks():
            s = t.get("status", "Unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    def get_task_detail(self, task_name: str) -> dict[str, Any]:
        """Get detailed info for a specific task via schtasks /Query /V."""
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST", "/V"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                detail: dict[str, str] = {}
                for line in result.stdout.splitlines():
                    if ":" in line:
                        key, _, val = line.partition(":")
                        detail[key.strip()] = val.strip()
                self._record("get_task_detail", True, task_name)
                return detail
        except Exception as e:
            self._record("get_task_detail", False, str(e))
        return {}

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(SchedEvent(action=action, success=success, detail=detail))

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


scheduled_task_manager = ScheduledTaskManager()
