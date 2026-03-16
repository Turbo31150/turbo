"""Window Manager — Windows window control and enumeration.

List open windows, focus, minimize, maximize, move, resize, close.
Uses ctypes for Win32 API calls (no external dependencies).
Designed for JARVIS autonomous window management on Windows.
"""

from __future__ import annotations

import ctypes
try:
    import ctypes.wintypes
except (ImportError, ValueError):
    pass
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "WindowEvent",
    "WindowInfo",
    "WindowManager",
]

logger = logging.getLogger("jarvis.window_manager")

if hasattr(ctypes, "windll"):
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
else:
    user32 = None
    kernel32 = None


@dataclass
class WindowInfo:
    """Information about a window."""
    hwnd: int
    title: str
    class_name: str = ""
    visible: bool = True
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    pid: int = 0


@dataclass
class WindowEvent:
    """Record of a window action."""
    hwnd: int
    title: str
    action: str
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class WindowManager:
    """Manage Windows windows via Win32 API."""

    def __init__(self) -> None:
        self._events: list[WindowEvent] = []
        self._lock = threading.Lock()

    # ── Enumeration ─────────────────────────────────────────────────

    def list_windows(self, visible_only: bool = True) -> list[dict[str, Any]]:
        """List all open windows."""
        windows: list[WindowInfo] = []

        def enum_callback(hwnd, _):
            if visible_only and not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if not title.strip():
                return True

            # Class name
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)

            # Position/size
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            # PID
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            windows.append(WindowInfo(
                hwnd=hwnd, title=title, class_name=cls_buf.value,
                visible=bool(user32.IsWindowVisible(hwnd)),
                x=rect.left, y=rect.top,
                width=rect.right - rect.left, height=rect.bottom - rect.top,
                pid=pid.value,
            ))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

        return [
            {"hwnd": w.hwnd, "title": w.title, "class_name": w.class_name,
             "visible": w.visible, "x": w.x, "y": w.y,
             "width": w.width, "height": w.height, "pid": w.pid}
            for w in windows
        ]

    def find_window(self, title_contains: str) -> list[dict[str, Any]]:
        """Find windows by partial title match."""
        q = title_contains.lower()
        return [w for w in self.list_windows() if q in w["title"].lower()]

    def get_foreground(self) -> dict[str, Any] | None:
        """Get the currently focused window."""
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return {"hwnd": hwnd, "title": buf.value}

    # ── Actions ─────────────────────────────────────────────────────

    def focus(self, hwnd: int) -> bool:
        """Bring window to foreground."""
        try:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            result = user32.SetForegroundWindow(hwnd)
            self._record(hwnd, "focus", bool(result))
            return bool(result)
        except Exception:
            return False

    def minimize(self, hwnd: int) -> bool:
        """Minimize a window."""
        try:
            result = user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
            self._record(hwnd, "minimize", bool(result))
            return bool(result)
        except Exception:
            return False

    def maximize(self, hwnd: int) -> bool:
        """Maximize a window."""
        try:
            result = user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
            self._record(hwnd, "maximize", bool(result))
            return bool(result)
        except Exception:
            return False

    def restore(self, hwnd: int) -> bool:
        """Restore a window."""
        try:
            result = user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            self._record(hwnd, "restore", bool(result))
            return bool(result)
        except Exception:
            return False

    def close(self, hwnd: int) -> bool:
        """Close a window (sends WM_CLOSE)."""
        try:
            WM_CLOSE = 0x0010
            result = user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            self._record(hwnd, "close", bool(result))
            return bool(result)
        except Exception:
            return False

    def move_resize(self, hwnd: int, x: int, y: int, width: int, height: int) -> bool:
        """Move and resize a window."""
        try:
            result = user32.MoveWindow(hwnd, x, y, width, height, True)
            self._record(hwnd, "move_resize", bool(result))
            return bool(result)
        except Exception:
            return False

    def set_topmost(self, hwnd: int, topmost: bool = True) -> bool:
        """Set window always on top."""
        try:
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            flag = HWND_TOPMOST if topmost else HWND_NOTOPMOST
            result = user32.SetWindowPos(hwnd, flag, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            self._record(hwnd, "topmost" if topmost else "untopmost", bool(result))
            return bool(result)
        except Exception:
            return False

    # ── Helpers ─────────────────────────────────────────────────────

    def _record(self, hwnd: int, action: str, success: bool) -> None:
        """Record a window action event."""
        title = ""
        try:
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
        except Exception:
            pass
        with self._lock:
            self._events.append(WindowEvent(hwnd=hwnd, title=title, action=action, success=success))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get window action history."""
        with self._lock:
            return [
                {"hwnd": e.hwnd, "title": e.title, "action": e.action,
                 "timestamp": e.timestamp, "success": e.success}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        """Get window manager statistics."""
        windows = self.list_windows()
        with self._lock:
            return {
                "open_windows": len(windows),
                "total_events": len(self._events),
                "actions": list(set(e.action for e in self._events)),
            }


# ── Singleton ───────────────────────────────────────────────────────
window_manager = WindowManager()
