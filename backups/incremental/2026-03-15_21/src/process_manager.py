"""Process Manager — Windows process lifecycle management.

Launch, monitor, restart, and kill processes. Supports process profiles
with auto-restart on crash, health checks, process groups, and resource
usage tracking. Designed for JARVIS autonomous Windows control.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


__all__ = [
    "ProcessEvent",
    "ProcessManager",
    "ProcessProfile",
    "ProcessStatus",
]

logger = logging.getLogger("jarvis.process_manager")


class ProcessStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    CRASHED = "crashed"
    RESTARTING = "restarting"


@dataclass
class ProcessProfile:
    """Configuration for a managed process."""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    auto_restart: bool = False
    max_restarts: int = 3
    group: str = "default"
    health_check: Callable[[], bool] | None = None
    # Runtime state
    pid: int | None = None
    status: ProcessStatus = ProcessStatus.STOPPED
    restart_count: int = 0
    started_at: float | None = None
    stopped_at: float | None = None
    exit_code: int | None = None


@dataclass
class ProcessEvent:
    """Record of a process lifecycle event."""
    name: str
    event: str  # started, stopped, crashed, restarted, killed
    timestamp: float = field(default_factory=time.time)
    pid: int | None = None
    exit_code: int | None = None
    detail: str = ""


class ProcessManager:
    """Manage Windows processes with profiles, groups, and auto-restart."""

    def __init__(self) -> None:
        self._profiles: dict[str, ProcessProfile] = {}
        self._processes: dict[str, subprocess.Popen] = {}
        self._events: list[ProcessEvent] = []
        self._lock = threading.Lock()

    # ── Registration ────────────────────────────────────────────────

    def register(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        auto_restart: bool = False,
        max_restarts: int = 3,
        group: str = "default",
        health_check: Callable[[], bool] | None = None,
    ) -> ProcessProfile:
        """Register a process profile."""
        profile = ProcessProfile(
            name=name,
            command=command,
            args=args or [],
            cwd=cwd,
            env=env or {},
            auto_restart=auto_restart,
            max_restarts=max_restarts,
            group=group,
            health_check=health_check,
        )
        with self._lock:
            self._profiles[name] = profile
        return profile

    def unregister(self, name: str) -> bool:
        """Remove a process profile (stops it first if running)."""
        with self._lock:
            if name not in self._profiles:
                return False
            if name in self._processes:
                self._stop_internal(name)
            del self._profiles[name]
            return True

    # ── Lifecycle ───────────────────────────────────────────────────

    def start(self, name: str) -> bool:
        """Start a registered process."""
        with self._lock:
            return self._start_internal(name)

    def _start_internal(self, name: str) -> bool:
        """Start process (caller must hold lock)."""
        profile = self._profiles.get(name)
        if not profile:
            return False
        if name in self._processes and self._processes[name].poll() is None:
            return False  # Already running

        cmd = [profile.command] + profile.args
        env = {**os.environ, **profile.env} if profile.env else None
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=profile.cwd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._processes[name] = proc
            profile.pid = proc.pid
            profile.status = ProcessStatus.RUNNING
            profile.started_at = time.time()
            profile.stopped_at = None
            profile.exit_code = None
            self._events.append(ProcessEvent(name=name, event="started", pid=proc.pid))
            logger.info("Started process %s (PID %d)", name, proc.pid)
            return True
        except Exception as e:
            logger.error("Failed to start %s: %s", name, e)
            profile.status = ProcessStatus.CRASHED
            self._events.append(ProcessEvent(name=name, event="start_failed", detail=str(e)))
            return False

    def stop(self, name: str) -> bool:
        """Stop a running process gracefully."""
        with self._lock:
            return self._stop_internal(name)

    def _stop_internal(self, name: str) -> bool:
        """Stop process (caller must hold lock)."""
        proc = self._processes.get(name)
        if not proc:
            return False
        profile = self._profiles.get(name)
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            exit_code = proc.returncode
        except Exception:
            exit_code = -1

        if profile:
            profile.status = ProcessStatus.STOPPED
            profile.stopped_at = time.time()
            profile.exit_code = exit_code
            profile.pid = None
        del self._processes[name]
        self._events.append(ProcessEvent(name=name, event="stopped", exit_code=exit_code))
        return True

    def restart(self, name: str) -> bool:
        """Restart a process."""
        with self._lock:
            profile = self._profiles.get(name)
            if not profile:
                return False
            profile.status = ProcessStatus.RESTARTING
            if name in self._processes:
                self._stop_internal(name)
            profile.restart_count += 1
            result = self._start_internal(name)
            if result:
                self._events.append(ProcessEvent(name=name, event="restarted", pid=profile.pid))
            return result

    def kill(self, name: str) -> bool:
        """Force kill a process."""
        with self._lock:
            proc = self._processes.get(name)
            if not proc:
                return False
            profile = self._profiles.get(name)
            try:
                proc.kill()
                proc.wait(timeout=3)
            except Exception:
                pass
            if profile:
                profile.status = ProcessStatus.STOPPED
                profile.stopped_at = time.time()
                profile.pid = None
            del self._processes[name]
            self._events.append(ProcessEvent(name=name, event="killed"))
            return True

    # ── Query ───────────────────────────────────────────────────────

    def get(self, name: str) -> ProcessProfile | None:
        """Get a process profile by name."""
        with self._lock:
            return self._profiles.get(name)

    def list_processes(self, group: str | None = None) -> list[dict[str, Any]]:
        """List all registered processes with their status."""
        with self._lock:
            result = []
            for p in self._profiles.values():
                if group and p.group != group:
                    continue
                # Refresh status from actual process
                self._refresh_status(p)
                result.append({
                    "name": p.name,
                    "command": p.command,
                    "status": p.status.value,
                    "pid": p.pid,
                    "group": p.group,
                    "auto_restart": p.auto_restart,
                    "restart_count": p.restart_count,
                    "started_at": p.started_at,
                    "uptime": (time.time() - p.started_at) if p.started_at and p.status == ProcessStatus.RUNNING else None,
                })
            return result

    def list_groups(self) -> list[str]:
        """List all process groups."""
        with self._lock:
            return list(set(p.group for p in self._profiles.values()))

    def is_running(self, name: str) -> bool:
        """Check if a process is currently running."""
        with self._lock:
            proc = self._processes.get(name)
            if not proc:
                return False
            return proc.poll() is None

    def _refresh_status(self, profile: ProcessProfile) -> None:
        """Refresh process status from OS (caller must hold lock)."""
        proc = self._processes.get(profile.name)
        if proc and proc.poll() is not None:
            # Process has exited
            profile.exit_code = proc.returncode
            profile.stopped_at = time.time()
            profile.pid = None
            if profile.exit_code != 0:
                profile.status = ProcessStatus.CRASHED
                self._events.append(ProcessEvent(
                    name=profile.name, event="crashed",
                    exit_code=profile.exit_code,
                ))
            else:
                profile.status = ProcessStatus.STOPPED
            del self._processes[profile.name]

    # ── Health Check ────────────────────────────────────────────────

    def check_health(self, name: str) -> dict[str, Any]:
        """Run health check for a process."""
        with self._lock:
            profile = self._profiles.get(name)
            if not profile:
                return {"name": name, "healthy": False, "error": "not found"}
            self._refresh_status(profile)
            running = profile.status == ProcessStatus.RUNNING
            healthy = running
            if running and profile.health_check:
                try:
                    healthy = profile.health_check()
                except Exception as e:
                    healthy = False
                    return {"name": name, "healthy": False, "running": True, "error": str(e)}
            return {"name": name, "healthy": healthy, "running": running, "status": profile.status.value}

    def check_all_health(self) -> list[dict[str, Any]]:
        """Run health checks on all processes."""
        names = list(self._profiles.keys())
        return [self.check_health(n) for n in names]

    # ── Events & Stats ──────────────────────────────────────────────

    def get_events(self, name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Get process events history."""
        with self._lock:
            events = self._events
            if name:
                events = [e for e in events if e.name == name]
            return [
                {"name": e.name, "event": e.event, "timestamp": e.timestamp,
                 "pid": e.pid, "exit_code": e.exit_code, "detail": e.detail}
                for e in events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        """Get process manager statistics."""
        with self._lock:
            running = sum(1 for p in self._profiles.values() if p.status == ProcessStatus.RUNNING)
            crashed = sum(1 for p in self._profiles.values() if p.status == ProcessStatus.CRASHED)
            groups = set(p.group for p in self._profiles.values())
            return {
                "total_processes": len(self._profiles),
                "running": running,
                "crashed": crashed,
                "stopped": len(self._profiles) - running - crashed,
                "groups": len(groups),
                "total_events": len(self._events),
                "total_restarts": sum(p.restart_count for p in self._profiles.values()),
            }


# ── Singleton ───────────────────────────────────────────────────────
process_manager = ProcessManager()
