"""Service Controller — Windows Services management.

List, start, stop, restart Windows services via sc.exe.
Service monitoring, dependency tracking, history.
Designed for JARVIS autonomous system administration.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.service_controller")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class ServiceInfo:
    """Information about a Windows service."""
    name: str
    display_name: str = ""
    status: str = ""
    start_type: str = ""
    pid: int = 0


@dataclass
class ServiceEvent:
    """Record of a service action."""
    service: str
    action: str
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class ServiceController:
    """Windows Services management with history."""

    def __init__(self) -> None:
        self._events: list[ServiceEvent] = []
        self._watched: dict[str, str] = {}  # service_name -> last_known_status
        self._lock = threading.Lock()

    # ── List ──────────────────────────────────────────────────────────

    def list_services(self, state: str = "all") -> list[dict[str, Any]]:
        """List Windows services. state: all, running, stopped."""
        try:
            cmd = ["sc", "query", "type=", "service", "state=", state]
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            services = []
            current: dict[str, str] = {}
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("SERVICE_NAME:"):
                    if current:
                        services.append(current)
                    current = {"name": line.split(":", 1)[1].strip(), "display_name": "", "status": ""}
                elif line.startswith("DISPLAY_NAME:") and current:
                    current["display_name"] = line.split(":", 1)[1].strip()
                elif line.startswith("STATE") and current:
                    parts = line.split()
                    # STATE : 4 RUNNING
                    for p in parts:
                        if p in ("RUNNING", "STOPPED", "PAUSED", "START_PENDING", "STOP_PENDING"):
                            current["status"] = p
                            break
            if current and current.get("name"):
                services.append(current)
            return services
        except Exception as e:
            logger.warning("list_services failed: %s", e)
            return []

    def get_service(self, name: str) -> dict[str, Any]:
        """Get detailed info about a service."""
        try:
            result = subprocess.run(
                ["sc", "qc", name], capture_output=True, text=True,
                timeout=5, creationflags=_NO_WINDOW,
            )
            info: dict[str, Any] = {"name": name, "exists": result.returncode == 0}
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    line = line.strip()
                    if line.startswith("DISPLAY_NAME"):
                        info["display_name"] = line.split(":", 1)[1].strip()
                    elif line.startswith("START_TYPE"):
                        info["start_type"] = line.split(":", 1)[1].strip()
                    elif line.startswith("BINARY_PATH_NAME"):
                        info["binary_path"] = line.split(":", 1)[1].strip()
            # Also get current status
            status_result = subprocess.run(
                ["sc", "query", name], capture_output=True, text=True,
                timeout=5, creationflags=_NO_WINDOW,
            )
            if status_result.returncode == 0:
                for line in status_result.stdout.split("\n"):
                    if "STATE" in line:
                        for p in line.split():
                            if p in ("RUNNING", "STOPPED", "PAUSED", "START_PENDING", "STOP_PENDING"):
                                info["status"] = p
                                break
            return info
        except Exception as e:
            return {"name": name, "exists": False, "error": str(e)}

    # ── Control ───────────────────────────────────────────────────────

    def start_service(self, name: str) -> dict[str, Any]:
        """Start a Windows service."""
        try:
            result = subprocess.run(
                ["sc", "start", name], capture_output=True, text=True,
                timeout=10, creationflags=_NO_WINDOW,
            )
            success = result.returncode == 0
            self._record(name, "start", success, result.stdout.strip() if success else result.stderr.strip())
            return {"success": success, "service": name, "detail": result.stdout.strip()}
        except Exception as e:
            self._record(name, "start", False, str(e))
            return {"success": False, "service": name, "error": str(e)}

    def stop_service(self, name: str) -> dict[str, Any]:
        """Stop a Windows service."""
        try:
            result = subprocess.run(
                ["sc", "stop", name], capture_output=True, text=True,
                timeout=10, creationflags=_NO_WINDOW,
            )
            success = result.returncode == 0
            self._record(name, "stop", success, result.stdout.strip() if success else result.stderr.strip())
            return {"success": success, "service": name, "detail": result.stdout.strip()}
        except Exception as e:
            self._record(name, "stop", False, str(e))
            return {"success": False, "service": name, "error": str(e)}

    def restart_service(self, name: str) -> dict[str, Any]:
        """Restart a Windows service (stop + start)."""
        stop_result = self.stop_service(name)
        if not stop_result.get("success"):
            # Try starting anyway (might already be stopped)
            pass
        time.sleep(0.5)
        return self.start_service(name)

    # ── Watch ─────────────────────────────────────────────────────────

    def watch(self, name: str) -> bool:
        """Add a service to the watch list."""
        info = self.get_service(name)
        if not info.get("exists"):
            return False
        with self._lock:
            self._watched[name] = info.get("status", "UNKNOWN")
        return True

    def unwatch(self, name: str) -> bool:
        with self._lock:
            if name in self._watched:
                del self._watched[name]
                return True
            return False

    def check_watched(self) -> list[dict[str, Any]]:
        """Check watched services for status changes."""
        changes = []
        with self._lock:
            watched_copy = dict(self._watched)
        for svc_name, last_status in watched_copy.items():
            info = self.get_service(svc_name)
            current = info.get("status", "UNKNOWN")
            if current != last_status:
                changes.append({
                    "service": svc_name, "old_status": last_status,
                    "new_status": current,
                })
                with self._lock:
                    self._watched[svc_name] = current
        return changes

    def list_watched(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": n, "last_status": s}
                for n, s in self._watched.items()
            ]

    # ── Search ────────────────────────────────────────────────────────

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search services by name or display name."""
        q = query.lower()
        return [
            s for s in self.list_services()
            if q in s.get("name", "").lower() or q in s.get("display_name", "").lower()
        ]

    # ── Query ─────────────────────────────────────────────────────────

    def _record(self, service: str, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(ServiceEvent(
                service=service, action=action, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"service": e.service, "action": e.action,
                 "timestamp": e.timestamp, "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
                "watched_services": len(self._watched),
            }


# ── Singleton ───────────────────────────────────────────────────────
service_controller = ServiceController()
