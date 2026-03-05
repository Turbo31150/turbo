"""Screen Capture — Windows screenshot and region capture.

Full screen and region screenshots via ctypes GDI BitBlt.
History, auto-save, multi-monitor support.
Designed for JARVIS autonomous visual monitoring.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.screen_capture")

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


@dataclass
class CaptureInfo:
    """Information about a captured screenshot."""
    capture_id: str
    filepath: str
    width: int
    height: int
    timestamp: float = field(default_factory=time.time)
    region: tuple[int, int, int, int] | None = None  # x, y, w, h
    size_bytes: int = 0


@dataclass
class CaptureEvent:
    """Record of a capture action."""
    action: str
    capture_id: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class ScreenCapture:
    """Screen capture with history and auto-save."""

    def __init__(self, save_dir: str = "") -> None:
        self._captures: list[CaptureInfo] = []
        self._events: list[CaptureEvent] = []
        self._counter = 0
        self._lock = threading.Lock()
        self._save_dir = save_dir or os.path.join(os.path.expanduser("~"), "Pictures", "JARVIS_Captures")

    # ── Screen Info ───────────────────────────────────────────────────

    def get_screen_size(self) -> dict[str, int]:
        """Get primary screen resolution."""
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        return {"width": w, "height": h}

    def get_virtual_screen(self) -> dict[str, int]:
        """Get virtual screen (all monitors combined)."""
        x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        w = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        h = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        return {"x": x, "y": y, "width": w, "height": h}

    def get_monitor_count(self) -> int:
        """Get number of monitors."""
        return user32.GetSystemMetrics(80)  # SM_CMONITORS

    # ── Capture ───────────────────────────────────────────────────────

    def capture_full(self, filename: str = "") -> CaptureInfo | None:
        """Capture full primary screen."""
        screen = self.get_screen_size()
        return self._capture_region(0, 0, screen["width"], screen["height"], filename)

    def capture_region(self, x: int, y: int, width: int, height: int,
                       filename: str = "") -> CaptureInfo | None:
        """Capture a specific screen region."""
        return self._capture_region(x, y, width, height, filename)

    def _capture_region(self, x: int, y: int, width: int, height: int,
                        filename: str = "") -> CaptureInfo | None:
        """Internal: capture a screen region to BMP file."""
        with self._lock:
            self._counter += 1
            cid = f"cap_{self._counter}"

        if not filename:
            os.makedirs(self._save_dir, exist_ok=True)
            filename = os.path.join(self._save_dir, f"capture_{cid}_{int(time.time())}.bmp")

        try:
            # Get device contexts
            hdc_screen = user32.GetDC(0)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
            old_bmp = gdi32.SelectObject(hdc_mem, hbmp)

            # BitBlt capture
            gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, x, y, 0x00CC0020)  # SRCCOPY

            # Save as BMP
            bmp_size = self._save_bmp(hdc_mem, hbmp, width, height, filename)

            # Cleanup
            gdi32.SelectObject(hdc_mem, old_bmp)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)

            info = CaptureInfo(
                capture_id=cid, filepath=filename,
                width=width, height=height,
                region=(x, y, width, height),
                size_bytes=bmp_size,
            )
            with self._lock:
                self._captures.append(info)
            self._record("capture", cid, True, f"{width}x{height}")
            return info

        except Exception as e:
            self._record("capture", cid, False, str(e))
            return None

    def _save_bmp(self, hdc: int, hbmp: int, width: int, height: int, filepath: str) -> int:
        """Save HBITMAP to BMP file."""

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.wintypes.DWORD),
                ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long),
                ("biPlanes", ctypes.wintypes.WORD),
                ("biBitCount", ctypes.wintypes.WORD),
                ("biCompression", ctypes.wintypes.DWORD),
                ("biSizeImage", ctypes.wintypes.DWORD),
                ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", ctypes.wintypes.DWORD),
                ("biClrImportant", ctypes.wintypes.DWORD),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = width
        bmi.biHeight = -height  # top-down
        bmi.biPlanes = 1
        bmi.biBitCount = 24
        bmi.biCompression = 0  # BI_RGB

        row_size = ((width * 3 + 3) // 4) * 4  # 4-byte aligned
        img_size = row_size * height
        bmi.biSizeImage = img_size

        buf = ctypes.create_string_buffer(img_size)
        gdi32.GetDIBits(hdc, hbmp, 0, height, buf, ctypes.byref(bmi), 0)

        # Write BMP file
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        file_size = 14 + ctypes.sizeof(BITMAPINFOHEADER) + img_size
        with open(filepath, "wb") as f:
            # BMP header
            f.write(b"BM")
            f.write(struct.pack("<I", file_size))
            f.write(struct.pack("<HH", 0, 0))
            f.write(struct.pack("<I", 14 + ctypes.sizeof(BITMAPINFOHEADER)))
            # DIB header
            f.write(bytes(bmi))
            # Pixel data
            f.write(buf.raw)

        return file_size

    # ── History ───────────────────────────────────────────────────────

    def list_captures(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"id": c.capture_id, "filepath": c.filepath,
                 "width": c.width, "height": c.height,
                 "timestamp": c.timestamp, "size_bytes": c.size_bytes,
                 "region": c.region}
                for c in self._captures[-limit:]
            ]

    def get_capture(self, capture_id: str) -> CaptureInfo | None:
        with self._lock:
            return next((c for c in self._captures if c.capture_id == capture_id), None)

    def delete_capture(self, capture_id: str) -> bool:
        """Delete a capture and its file."""
        with self._lock:
            cap = next((c for c in self._captures if c.capture_id == capture_id), None)
            if not cap:
                return False
            self._captures.remove(cap)
        try:
            if os.path.exists(cap.filepath):
                os.remove(cap.filepath)
        except OSError:
            pass
        self._record("delete", capture_id, True)
        return True

    # ── Query ─────────────────────────────────────────────────────────

    def _record(self, action: str, capture_id: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(CaptureEvent(
                action=action, capture_id=capture_id,
                success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "capture_id": e.capture_id,
                 "timestamp": e.timestamp, "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        screen = self.get_screen_size()
        with self._lock:
            total_bytes = sum(c.size_bytes for c in self._captures)
            return {
                "total_captures": len(self._captures),
                "total_events": len(self._events),
                "total_bytes": total_bytes,
                "screen_width": screen["width"],
                "screen_height": screen["height"],
                "monitor_count": self.get_monitor_count(),
                "save_dir": self._save_dir,
            }


# ── Singleton ───────────────────────────────────────────────────────
screen_capture = ScreenCapture()
