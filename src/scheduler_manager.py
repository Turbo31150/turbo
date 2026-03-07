"""Scheduler Manager — Windows Task Scheduler management.

List, create, delete, enable/disable scheduled tasks.
Uses schtasks.exe via subprocess (no external deps).
Designed for JARVIS autonomous task scheduling.
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


__all__ = [
    "ScheduledTask",
    "SchedulerEvent",
    "SchedulerManager",
]

logger = logging.getLogger("jarvis.scheduler_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class ScheduledTask:
    """A scheduled task."""
    name: str
    folder: str = "\\"
    status: str = ""
    next_run: str = ""
    last_run: str = ""
    last_result: str = ""
    author: str = ""


@dataclass
class SchedulerEvent:
    """Record of a scheduler action."""
    action: str
    task_name: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class SchedulerManager:
    """Windows Task Scheduler management via schtasks.exe."""

    def __init__(self) -> None:
        self._events: list[SchedulerEvent] = []
        self._lock = threading.Lock()

    # ── Task Listing ───────────────────────────────────────────────────

    def list_tasks(self, folder: str = "\\") -> list[dict[str, Any]]:
        """List scheduled tasks in a folder."""
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/FO", "CSV", "/V", "/TN", folder],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                tasks = self._parse_csv(result.stdout)
                self._record("list_tasks", folder, True, f"{len(tasks)} tasks")
                return tasks
        except Exception as e:
            self._record("list_tasks", folder, False, str(e))
        return []

    def _parse_csv(self, output: str) -> list[dict[str, Any]]:
        """Parse schtasks CSV output."""
        tasks = []
        try:
            reader = csv.DictReader(io.StringIO(output))
            for row in reader:
                name = row.get("TaskName", row.get("Nom de la t\u00e2che", ""))
                if not name:
                    continue
                tasks.append({
                    "name": name,
                    "status": row.get("Status", row.get("Statut", "")),
                    "next_run": row.get("Next Run Time", row.get("Prochaine ex\u00e9cution", "")),
                    "last_run": row.get("Last Run Time", row.get("Derni\u00e8re ex\u00e9cution", "")),
                    "last_result": row.get("Last Result", row.get("Dernier r\u00e9sultat", "")),
                    "author": row.get("Author", row.get("Auteur", "")),
                    "task_to_run": row.get("Task To Run", row.get("T\u00e2che \u00e0 ex\u00e9cuter", "")),
                })
        except Exception as e:
            logger.debug("CSV parse error: %s", e)
        return tasks

    def get_task(self, name: str) -> dict[str, Any] | None:
        """Get details of a specific task."""
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/FO", "CSV", "/V", "/TN", name],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0:
                tasks = self._parse_csv(result.stdout)
                return tasks[0] if tasks else None
        except Exception:
            pass
        return None

    def search_tasks(self, query: str) -> list[dict[str, Any]]:
        """Search tasks by name."""
        q = query.lower()
        return [t for t in self.list_tasks() if q in t.get("name", "").lower()]

    # ── Task Count ─────────────────────────────────────────────────────

    def count_by_status(self) -> dict[str, int]:
        """Count tasks by status."""
        tasks = self.list_tasks()
        counts: dict[str, int] = {}
        for t in tasks:
            s = t.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    # ── Folders ─────────────────────────────────────────────────────────

    def list_folders(self) -> list[str]:
        """List top-level task folders."""
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/FO", "CSV"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            folders = set()
            reader = csv.DictReader(io.StringIO(result.stdout))
            for row in reader:
                name = row.get("TaskName", row.get("Nom de la t\u00e2che", ""))
                if name and "\\" in name:
                    parts = name.rsplit("\\", 1)
                    if parts[0]:
                        folders.add(parts[0])
            return sorted(folders)
        except Exception:
            return []

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, task_name: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(SchedulerEvent(
                action=action, task_name=task_name, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "task_name": e.task_name,
                 "timestamp": e.timestamp, "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
scheduler_manager = SchedulerManager()
