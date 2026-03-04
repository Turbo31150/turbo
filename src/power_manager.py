"""Power Manager — Windows power control and monitoring.

Sleep, hibernate, shutdown timer, screen off, battery status,
power plan management. Designed for JARVIS energy management.
"""

from __future__ import annotations

import ctypes
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("jarvis.power_manager")


class PowerAction(Enum):
    SLEEP = "sleep"
    HIBERNATE = "hibernate"
    SHUTDOWN = "shutdown"
    RESTART = "restart"
    LOCK = "lock"
    SCREEN_OFF = "screen_off"
    CANCEL_SHUTDOWN = "cancel_shutdown"


@dataclass
class PowerEvent:
    """Record of a power action."""
    action: str
    timestamp: float = field(default_factory=time.time)
    scheduled: bool = False
    delay_seconds: int = 0
    success: bool = True
    detail: str = ""


@dataclass
class ScheduledAction:
    """A scheduled power action."""
    action: PowerAction
    execute_at: float
    created_at: float = field(default_factory=time.time)
    cancelled: bool = False


class PowerManager:
    """Windows power management with scheduling and history."""

    def __init__(self) -> None:
        self._events: list[PowerEvent] = []
        self._scheduled: list[ScheduledAction] = []
        self._lock = threading.Lock()

    # ── Actions ─────────────────────────────────────────────────────

    def lock_screen(self) -> bool:
        """Lock the workstation."""
        try:
            ctypes.windll.user32.LockWorkStation()
            self._record("lock", True)
            return True
        except Exception as e:
            self._record("lock", False, str(e))
            return False

    def screen_off(self) -> bool:
        """Turn off the screen."""
        try:
            SC_MONITORPOWER = 0xF170
            WM_SYSCOMMAND = 0x0112
            HWND_BROADCAST = 0xFFFF
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)
            self._record("screen_off", True)
            return True
        except Exception as e:
            self._record("screen_off", False, str(e))
            return False

    def sleep(self) -> bool:
        """Put computer to sleep."""
        try:
            subprocess.run(
                ["powershell", "-Command", "Add-Type -Assembly System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"],
                timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._record("sleep", True)
            return True
        except Exception as e:
            self._record("sleep", False, str(e))
            return False

    def schedule_shutdown(self, delay_seconds: int = 60, restart: bool = False) -> dict[str, Any]:
        """Schedule a shutdown or restart."""
        action = "restart" if restart else "shutdown"
        flag = "/r" if restart else "/s"
        try:
            subprocess.run(
                ["shutdown", flag, "/t", str(delay_seconds)],
                timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._lock:
                self._scheduled.append(ScheduledAction(
                    action=PowerAction.RESTART if restart else PowerAction.SHUTDOWN,
                    execute_at=time.time() + delay_seconds,
                ))
            self._record(action, True, f"in {delay_seconds}s")
            return {"success": True, "action": action, "delay": delay_seconds}
        except Exception as e:
            self._record(action, False, str(e))
            return {"success": False, "error": str(e)}

    def cancel_shutdown(self) -> bool:
        """Cancel a scheduled shutdown."""
        try:
            subprocess.run(
                ["shutdown", "/a"],
                timeout=5, capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._lock:
                for sa in self._scheduled:
                    if not sa.cancelled:
                        sa.cancelled = True
            self._record("cancel_shutdown", True)
            return True
        except Exception as e:
            self._record("cancel_shutdown", False, str(e))
            return False

    # ── Battery ─────────────────────────────────────────────────────

    def get_battery_status(self) -> dict[str, Any]:
        """Get battery status (if available)."""
        try:
            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_byte),
                    ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.wintypes.DWORD),
                    ("BatteryFullLifeTime", ctypes.wintypes.DWORD),
                ]
            status = SYSTEM_POWER_STATUS()
            ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
            return {
                "ac_power": status.ACLineStatus == 1,
                "battery_percent": status.BatteryLifePercent if status.BatteryLifePercent != 255 else None,
                "charging": bool(status.BatteryFlag & 8),
                "has_battery": status.BatteryFlag != 128,
                "battery_life_seconds": status.BatteryLifeTime if status.BatteryLifeTime != 0xFFFFFFFF else None,
            }
        except Exception:
            return {"ac_power": True, "has_battery": False}

    # ── Power Plan ──────────────────────────────────────────────────

    def get_power_plan(self) -> dict[str, Any]:
        """Get current power plan."""
        try:
            result = subprocess.run(
                ["powercfg", "/getactivescheme"],
                capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                return {"plan": result.stdout.strip(), "raw": result.stdout.strip()}
        except Exception:
            pass
        return {"plan": "unknown"}

    # ── Query ───────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(PowerEvent(action=action, success=success, detail=detail))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_scheduled(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": s.action.value, "execute_at": s.execute_at,
                 "created_at": s.created_at, "cancelled": s.cancelled}
                for s in self._scheduled
            ]

    def get_stats(self) -> dict[str, Any]:
        battery = self.get_battery_status()
        with self._lock:
            return {
                "total_events": len(self._events),
                "scheduled_actions": len(self._scheduled),
                "ac_power": battery.get("ac_power"),
                "battery_percent": battery.get("battery_percent"),
                "has_battery": battery.get("has_battery"),
            }


# ── Singleton ───────────────────────────────────────────────────────
power_manager = PowerManager()
