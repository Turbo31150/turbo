"""Linux Workspace Manager — Virtual desktop / workspace management.

Uses wmctrl, xdotool, gsettings for workspace management.
Designed for JARVIS autonomous workspace management.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "DesktopEvent",
    "DesktopInfo",
    "LinuxWorkspaceManager",
]

logger = logging.getLogger("jarvis.linux_workspace_manager")


@dataclass
class DesktopInfo:
    """A virtual desktop/workspace."""
    index: int
    name: str = ""
    is_current: bool = False


@dataclass
class DesktopEvent:
    """Record of a desktop action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class LinuxWorkspaceManager:
    """Linux virtual workspace management."""

    def __init__(self) -> None:
        self._events: list[DesktopEvent] = []
        self._lock = threading.Lock()

    # ── Desktop Info ───────────────────────────────────────────────────

    def get_desktop_count(self) -> int:
        """Get number of virtual workspaces."""
        # Essayer wmctrl
        try:
            result = subprocess.run(
                ["wmctrl", "-d"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                count = len(result.stdout.strip().splitlines())
                self._record("get_desktop_count", True, str(count))
                return count
        except FileNotFoundError:
            pass
        except Exception:
            pass
        # Fallback: gsettings
        try:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.wm.preferences", "num-workspaces"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                count = int(result.stdout.strip())
                self._record("get_desktop_count", True, str(count))
                return count
        except Exception:
            pass
        return 1

    def list_desktops(self) -> list[dict[str, Any]]:
        """List virtual workspaces."""
        # Essayer wmctrl
        try:
            result = subprocess.run(
                ["wmctrl", "-d"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                desktops = []
                for line in result.stdout.strip().splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        index = int(parts[0])
                        is_current = parts[1] == "*"
                        # Le nom est le dernier champ après les géométries
                        name = parts[-1] if len(parts) > 8 else f"Workspace {index + 1}"
                        desktops.append({
                            "index": index,
                            "id": str(index),
                            "name": name,
                            "is_current": is_current,
                        })
                self._record("list_desktops", True, f"{len(desktops)} desktops")
                return desktops
        except FileNotFoundError:
            pass
        except Exception as e:
            self._record("list_desktops", False, str(e))
        return [{"index": 0, "name": "Workspace 1", "is_current": True}]

    def get_current_desktop(self) -> dict[str, Any]:
        """Get current active workspace."""
        for d in self.list_desktops():
            if d.get("is_current"):
                return d
        return {"index": 0, "name": "Workspace 1", "is_current": True}

    def switch_desktop(self, index: int) -> bool:
        """Switch to a specific workspace by index."""
        # Essayer wmctrl
        try:
            result = subprocess.run(
                ["wmctrl", "-s", str(index)],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                self._record("switch_desktop", True, f"switched to {index}")
                return True
        except FileNotFoundError:
            pass
        except Exception:
            pass
        # Fallback: xdotool
        try:
            result = subprocess.run(
                ["xdotool", "set_desktop", str(index)],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                self._record("switch_desktop", True, f"switched to {index}")
                return True
        except FileNotFoundError:
            pass
        except Exception:
            pass
        self._record("switch_desktop", False, "no tool available")
        return False

    def set_num_workspaces(self, count: int) -> bool:
        """Set the number of workspaces (GNOME)."""
        try:
            result = subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.wm.preferences",
                 "num-workspaces", str(count)],
                capture_output=True, text=True, timeout=5,
            )
            success = result.returncode == 0
            self._record("set_num_workspaces", success, str(count))
            return success
        except Exception as e:
            self._record("set_num_workspaces", False, str(e))
            return False

    def get_screen_info(self) -> dict[str, Any]:
        """Get screen metrics for current desktop."""
        # Essayer xrandr
        try:
            result = subprocess.run(
                ["xrandr", "--query"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                monitors = 0
                width = 0
                height = 0
                for line in result.stdout.splitlines():
                    if " connected" in line:
                        monitors += 1
                        # Chercher la résolution active (marquée avec *)
                    if "*" in line:
                        parts = line.strip().split()
                        if parts:
                            res = parts[0]
                            if "x" in res:
                                w, h = res.split("x")
                                try:
                                    cw, ch = int(w), int(h)
                                    if cw > width:
                                        width = cw
                                    if ch > height:
                                        height = ch
                                except ValueError:
                                    pass
                return {
                    "width": width,
                    "height": height,
                    "monitors": monitors,
                }
        except FileNotFoundError:
            pass
        except Exception:
            pass
        # Fallback: xdpyinfo
        try:
            result = subprocess.run(
                ["xdpyinfo"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "dimensions:" in line:
                        parts = line.split()
                        for p in parts:
                            if "x" in p and p[0].isdigit():
                                w, h = p.split("x")
                                return {
                                    "width": int(w),
                                    "height": int(h),
                                    "monitors": 1,
                                }
        except Exception:
            pass
        return {"width": 0, "height": 0, "monitors": 0}

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(DesktopEvent(
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
linux_workspace_manager = LinuxWorkspaceManager()
