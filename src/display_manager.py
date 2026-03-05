"""Display Manager — Windows display and monitor management.

Resolution, refresh rate, multi-monitor layout, DPI, orientation.
Uses ctypes user32 EnumDisplaySettings/ChangeDisplaySettings.
Designed for JARVIS autonomous display configuration.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.display_manager")

user32 = ctypes.windll.user32


# ── Win32 Structures (not in ctypes.wintypes) ─────────────────────
class POINTL(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.wintypes.DWORD),
        ("DeviceName", ctypes.c_wchar * 32),
        ("DeviceString", ctypes.c_wchar * 128),
        ("StateFlags", ctypes.wintypes.DWORD),
        ("DeviceID", ctypes.c_wchar * 128),
        ("DeviceKey", ctypes.c_wchar * 128),
    ]


class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", ctypes.wintypes.WORD),
        ("dmDriverVersion", ctypes.wintypes.WORD),
        ("dmSize", ctypes.wintypes.WORD),
        ("dmDriverExtra", ctypes.wintypes.WORD),
        ("dmFields", ctypes.wintypes.DWORD),
        ("dmPosition", POINTL),
        ("dmDisplayOrientation", ctypes.wintypes.DWORD),
        ("dmDisplayFixedOutput", ctypes.wintypes.DWORD),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.wintypes.WORD),
        ("dmBitsPerPel", ctypes.wintypes.DWORD),
        ("dmPelsWidth", ctypes.wintypes.DWORD),
        ("dmPelsHeight", ctypes.wintypes.DWORD),
        ("dmDisplayFlags", ctypes.wintypes.DWORD),
        ("dmDisplayFrequency", ctypes.wintypes.DWORD),
    ]


# Display orientation constants
DMDO_DEFAULT = 0
DMDO_90 = 1
DMDO_180 = 2
DMDO_270 = 3

ORIENTATIONS = {0: "landscape", 1: "portrait", 2: "landscape_flipped", 3: "portrait_flipped"}


@dataclass
class DisplayInfo:
    """Information about a display."""
    device_name: str
    width: int
    height: int
    refresh_rate: int
    bits_per_pixel: int
    orientation: str = "landscape"
    x: int = 0
    y: int = 0
    is_primary: bool = False


@dataclass
class DisplayEvent:
    """Record of a display action."""
    action: str
    device: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class DisplayManager:
    """Windows display management with multi-monitor support."""

    def __init__(self) -> None:
        self._events: list[DisplayEvent] = []
        self._lock = threading.Lock()

    # ── Display Info ──────────────────────────────────────────────────

    def list_displays(self) -> list[dict[str, Any]]:
        """List all connected displays with current settings."""
        displays = []
        i = 0
        while True:
            device = DISPLAY_DEVICEW()
            device.cb = ctypes.sizeof(device)
            if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(device), 0):
                break
            i += 1
            # Skip non-active devices
            if not (device.StateFlags & 0x1):  # DISPLAY_DEVICE_ATTACHED_TO_DESKTOP
                continue

            devmode = DEVMODEW()
            devmode.dmSize = ctypes.sizeof(devmode)
            if user32.EnumDisplaySettingsW(device.DeviceName, -1, ctypes.byref(devmode)):  # ENUM_CURRENT_SETTINGS
                orientation = ORIENTATIONS.get(devmode.dmDisplayOrientation, "unknown")
                displays.append({
                    "device_name": device.DeviceName,
                    "width": devmode.dmPelsWidth,
                    "height": devmode.dmPelsHeight,
                    "refresh_rate": devmode.dmDisplayFrequency,
                    "bits_per_pixel": devmode.dmBitsPerPel,
                    "orientation": orientation,
                    "x": devmode.dmPosition.x,
                    "y": devmode.dmPosition.y,
                    "is_primary": bool(device.StateFlags & 0x4),  # DISPLAY_DEVICE_PRIMARY
                })
        return displays

    def get_primary(self) -> dict[str, Any]:
        """Get primary display info."""
        for d in self.list_displays():
            if d.get("is_primary"):
                return d
        # Fallback to screen metrics
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        return {"width": w, "height": h, "is_primary": True}

    def get_supported_modes(self, device_name: str = "") -> list[dict[str, Any]]:
        """List supported display modes for a device."""
        modes = []
        dev_name = device_name or None
        i = 0
        seen = set()
        while True:
            devmode = DEVMODEW()
            devmode.dmSize = ctypes.sizeof(devmode)
            if not user32.EnumDisplaySettingsW(dev_name, i, ctypes.byref(devmode)):
                break
            i += 1
            key = (devmode.dmPelsWidth, devmode.dmPelsHeight, devmode.dmDisplayFrequency)
            if key not in seen:
                seen.add(key)
                modes.append({
                    "width": devmode.dmPelsWidth,
                    "height": devmode.dmPelsHeight,
                    "refresh_rate": devmode.dmDisplayFrequency,
                    "bits_per_pixel": devmode.dmBitsPerPel,
                })
        return modes

    # ── Screen Metrics ────────────────────────────────────────────────

    def get_dpi(self) -> dict[str, int]:
        """Get system DPI settings."""
        try:
            hdc = user32.GetDC(0)
            gdi32 = ctypes.windll.gdi32
            dpi_x = gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            dpi_y = gdi32.GetDeviceCaps(hdc, 90)  # LOGPIXELSY
            user32.ReleaseDC(0, hdc)
            return {"dpi_x": dpi_x, "dpi_y": dpi_y, "scale": round(dpi_x / 96 * 100)}
        except Exception:
            return {"dpi_x": 96, "dpi_y": 96, "scale": 100}

    def get_screen_size(self) -> dict[str, int]:
        """Get primary screen resolution."""
        return {
            "width": user32.GetSystemMetrics(0),
            "height": user32.GetSystemMetrics(1),
        }

    def get_virtual_screen(self) -> dict[str, int]:
        """Get combined virtual screen (all monitors)."""
        return {
            "x": user32.GetSystemMetrics(76),
            "y": user32.GetSystemMetrics(77),
            "width": user32.GetSystemMetrics(78),
            "height": user32.GetSystemMetrics(79),
        }

    def get_monitor_count(self) -> int:
        return user32.GetSystemMetrics(80)

    # ── Query ─────────────────────────────────────────────────────────

    def _record(self, action: str, device: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(DisplayEvent(
                action=action, device=device, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "device": e.device,
                 "timestamp": e.timestamp, "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        displays = self.list_displays()
        dpi = self.get_dpi()
        with self._lock:
            return {
                "display_count": len(displays),
                "monitor_count": self.get_monitor_count(),
                "dpi_scale": dpi.get("scale", 100),
                "total_events": len(self._events),
                "primary_resolution": f"{displays[0]['width']}x{displays[0]['height']}" if displays else "unknown",
            }


# ── Singleton ───────────────────────────────────────────────────────
display_manager = DisplayManager()
