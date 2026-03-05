"""App Launcher — Windows application launcher and registry.

Register applications with paths, arguments, and launch profiles.
Support groups, templates, launch history, and favorites.
Designed for JARVIS voice-controlled app launching on Windows.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.app_launcher")


@dataclass
class AppEntry:
    """A registered application."""
    name: str
    path: str
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    group: str = "default"
    description: str = ""
    icon: str = ""
    favorite: bool = False
    launch_count: int = 0
    last_launched: float | None = None
    created_at: float = field(default_factory=time.time)


@dataclass
class LaunchEvent:
    """Record of an app launch."""
    app_name: str
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    pid: int | None = None
    error: str = ""


class AppLauncher:
    """Windows application launcher with registry and history."""

    def __init__(self) -> None:
        self._apps: dict[str, AppEntry] = {}
        self._launches: list[LaunchEvent] = []
        self._lock = threading.Lock()

    # ── Registration ────────────────────────────────────────────────

    def register(
        self,
        name: str,
        path: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        group: str = "default",
        description: str = "",
        favorite: bool = False,
    ) -> AppEntry:
        """Register an application."""
        app = AppEntry(
            name=name, path=path, args=args or [],
            cwd=cwd, group=group, description=description,
            favorite=favorite,
        )
        with self._lock:
            self._apps[name] = app
        return app

    def unregister(self, name: str) -> bool:
        """Remove an application."""
        with self._lock:
            if name in self._apps:
                del self._apps[name]
                return True
            return False

    def set_favorite(self, name: str, favorite: bool = True) -> bool:
        """Toggle favorite status."""
        with self._lock:
            app = self._apps.get(name)
            if app:
                app.favorite = favorite
                return True
            return False

    # ── Launching ───────────────────────────────────────────────────

    def launch(self, name: str, extra_args: list[str] | None = None) -> dict[str, Any]:
        """Launch a registered application."""
        with self._lock:
            app = self._apps.get(name)
            if not app:
                return {"success": False, "error": f"App '{name}' not found"}

        cmd = [app.path] + app.args + (extra_args or [])
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=app.cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._lock:
                app.launch_count += 1
                app.last_launched = time.time()
                self._launches.append(LaunchEvent(app_name=name, pid=proc.pid))
            logger.info("Launched %s (PID %d)", name, proc.pid)
            return {"success": True, "pid": proc.pid, "app": name}
        except Exception as e:
            with self._lock:
                self._launches.append(LaunchEvent(app_name=name, success=False, error=str(e)))
            return {"success": False, "error": str(e)}

    def launch_path(self, path: str, args: list[str] | None = None) -> dict[str, Any]:
        """Launch an unregistered application by path."""
        try:
            cmd = [path] + (args or [])
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._lock:
                self._launches.append(LaunchEvent(app_name=os.path.basename(path), pid=proc.pid))
            return {"success": True, "pid": proc.pid}
        except Exception as e:
            logger.exception("Failed to launch %s", path)
            return {"success": False, "error": str(e)}

    # ── Query ───────────────────────────────────────────────────────

    def get(self, name: str) -> AppEntry | None:
        with self._lock:
            return self._apps.get(name)

    def list_apps(self, group: str | None = None, favorites_only: bool = False) -> list[dict[str, Any]]:
        """List registered applications."""
        with self._lock:
            result = []
            for app in self._apps.values():
                if group and app.group != group:
                    continue
                if favorites_only and not app.favorite:
                    continue
                result.append({
                    "name": app.name,
                    "path": app.path,
                    "group": app.group,
                    "description": app.description,
                    "favorite": app.favorite,
                    "launch_count": app.launch_count,
                    "last_launched": app.last_launched,
                })
            return result

    def list_groups(self) -> list[str]:
        with self._lock:
            return list(set(a.group for a in self._apps.values()))

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search apps by name or description."""
        q = query.lower()
        with self._lock:
            return [
                {"name": a.name, "path": a.path, "description": a.description, "group": a.group}
                for a in self._apps.values()
                if q in a.name.lower() or q in a.description.lower()
            ]

    def get_history(self, app_name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Get launch history."""
        with self._lock:
            events = self._launches
            if app_name:
                events = [e for e in events if e.app_name == app_name]
            return [
                {"app_name": e.app_name, "timestamp": e.timestamp,
                 "success": e.success, "pid": e.pid, "error": e.error}
                for e in events[-limit:]
            ]

    def get_most_used(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most launched apps."""
        with self._lock:
            sorted_apps = sorted(self._apps.values(), key=lambda a: a.launch_count, reverse=True)
            return [
                {"name": a.name, "launch_count": a.launch_count, "group": a.group}
                for a in sorted_apps[:limit]
            ]

    def get_stats(self) -> dict[str, Any]:
        """Get app launcher statistics."""
        with self._lock:
            favorites = sum(1 for a in self._apps.values() if a.favorite)
            groups = set(a.group for a in self._apps.values())
            total_launches = sum(a.launch_count for a in self._apps.values())
            failed = sum(1 for e in self._launches if not e.success)
            return {
                "total_apps": len(self._apps),
                "favorites": favorites,
                "groups": len(groups),
                "total_launches": total_launches,
                "failed_launches": failed,
                "history_size": len(self._launches),
            }


# ── Singleton ───────────────────────────────────────────────────────
app_launcher = AppLauncher()
