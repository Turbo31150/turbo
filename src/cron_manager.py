"""Cron Manager — Periodic task execution with cron-like scheduling.

Run callbacks at intervals (every N seconds), daily at specific time,
or weekly. Supports enable/disable, execution history, next_run tracking.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


__all__ = [
    "CronExecution",
    "CronJob",
    "CronManager",
    "ScheduleType",
]

logger = logging.getLogger("jarvis.cron_manager")


class ScheduleType(Enum):
    INTERVAL = "interval"   # every N seconds
    DAILY = "daily"         # at HH:MM every day
    WEEKLY = "weekly"       # at HH:MM on specific day


@dataclass
class CronJob:
    """A scheduled periodic task."""
    name: str
    schedule_type: ScheduleType
    callback: Callable[[], Any] | None = None
    interval_seconds: float = 60.0
    time_str: str = "00:00"  # HH:MM for daily/weekly
    day_of_week: int = 0     # 0=Monday for weekly
    group: str = "default"
    enabled: bool = True
    # Runtime
    run_count: int = 0
    last_run: float | None = None
    last_result: str = ""
    last_error: str = ""
    created_at: float = field(default_factory=time.time)

    @property
    def next_run_in(self) -> float | None:
        """Seconds until next run (for interval type)."""
        if self.schedule_type == ScheduleType.INTERVAL and self.last_run:
            elapsed = time.time() - self.last_run
            remaining = self.interval_seconds - elapsed
            return max(0, remaining)
        return None


@dataclass
class CronExecution:
    """Record of a cron job execution."""
    name: str
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    result: str = ""
    error: str = ""
    duration_ms: float = 0.0


class CronManager:
    """Manage periodic tasks with scheduling and execution tracking."""

    def __init__(self) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._executions: list[CronExecution] = []
        self._lock = threading.Lock()

    # ── Job Management ──────────────────────────────────────────────

    def add_job(
        self,
        name: str,
        callback: Callable[[], Any] | None = None,
        schedule_type: ScheduleType = ScheduleType.INTERVAL,
        interval_seconds: float = 60.0,
        time_str: str = "00:00",
        day_of_week: int = 0,
        group: str = "default",
    ) -> CronJob:
        """Add a cron job."""
        job = CronJob(
            name=name,
            callback=callback,
            schedule_type=schedule_type,
            interval_seconds=interval_seconds,
            time_str=time_str,
            day_of_week=day_of_week,
            group=group,
        )
        with self._lock:
            self._jobs[name] = job
        return job

    def remove_job(self, name: str) -> bool:
        """Remove a cron job."""
        with self._lock:
            if name in self._jobs:
                del self._jobs[name]
                return True
            return False

    def enable(self, name: str) -> bool:
        with self._lock:
            job = self._jobs.get(name)
            if job:
                job.enabled = True
                return True
            return False

    def disable(self, name: str) -> bool:
        with self._lock:
            job = self._jobs.get(name)
            if job:
                job.enabled = False
                return True
            return False

    def get(self, name: str) -> CronJob | None:
        with self._lock:
            return self._jobs.get(name)

    # ── Execution ───────────────────────────────────────────────────

    def run_job(self, name: str) -> dict[str, Any]:
        """Manually trigger a job execution."""
        with self._lock:
            job = self._jobs.get(name)
            if not job:
                return {"success": False, "error": "not found"}
            if not job.enabled:
                return {"success": False, "error": "disabled"}

        start = time.time()
        success = True
        result_val = ""
        error_val = ""

        try:
            if job.callback:
                r = job.callback()
                result_val = str(r) if r is not None else ""
        except Exception as e:
            success = False
            error_val = str(e)

        duration = round((time.time() - start) * 1000, 3)

        with self._lock:
            job.run_count += 1
            job.last_run = time.time()
            job.last_result = result_val
            job.last_error = error_val
            self._executions.append(CronExecution(
                name=name, success=success,
                result=result_val, error=error_val,
                duration_ms=duration,
            ))

        return {"success": success, "result": result_val, "error": error_val, "duration_ms": duration}

    def check_and_run_due(self) -> list[str]:
        """Check all jobs and run those that are due. Returns names of executed jobs."""
        now = time.time()
        due_jobs: list[str] = []

        with self._lock:
            for job in self._jobs.values():
                if not job.enabled:
                    continue
                if job.schedule_type == ScheduleType.INTERVAL:
                    if job.last_run is None or (now - job.last_run) >= job.interval_seconds:
                        due_jobs.append(job.name)

        executed = []
        for name in due_jobs:
            result = self.run_job(name)
            if result.get("success") is not None:
                executed.append(name)
        return executed

    # ── Query ───────────────────────────────────────────────────────

    def list_jobs(self, group: str | None = None) -> list[dict[str, Any]]:
        """List all jobs."""
        with self._lock:
            result = []
            for job in self._jobs.values():
                if group and job.group != group:
                    continue
                result.append({
                    "name": job.name,
                    "schedule_type": job.schedule_type.value,
                    "interval_seconds": job.interval_seconds,
                    "time_str": job.time_str,
                    "group": job.group,
                    "enabled": job.enabled,
                    "run_count": job.run_count,
                    "last_run": job.last_run,
                    "next_run_in": job.next_run_in,
                })
            return result

    def list_groups(self) -> list[str]:
        with self._lock:
            return list(set(j.group for j in self._jobs.values()))

    def get_executions(self, name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Get execution history."""
        with self._lock:
            execs = self._executions
            if name:
                execs = [e for e in execs if e.name == name]
            return [
                {"name": e.name, "timestamp": e.timestamp, "success": e.success,
                 "result": e.result, "error": e.error, "duration_ms": e.duration_ms}
                for e in execs[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        """Get cron manager statistics."""
        with self._lock:
            enabled = sum(1 for j in self._jobs.values() if j.enabled)
            total_runs = sum(j.run_count for j in self._jobs.values())
            groups = set(j.group for j in self._jobs.values())
            failed = sum(1 for e in self._executions if not e.success)
            return {
                "total_jobs": len(self._jobs),
                "enabled": enabled,
                "disabled": len(self._jobs) - enabled,
                "groups": len(groups),
                "total_executions": total_runs,
                "failed_executions": failed,
                "history_size": len(self._executions),
            }


# ── Singleton ───────────────────────────────────────────────────────
cron_manager = CronManager()
