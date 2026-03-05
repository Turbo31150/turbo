"""Font Manager — Windows font enumeration and management.

List installed fonts, search, get details.
Uses Windows Registry (no external deps).
Designed for JARVIS autonomous font management.
"""

from __future__ import annotations

import logging
import threading
import time
import winreg
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.font_manager")

FONTS_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"


@dataclass
class FontInfo:
    """An installed font."""
    name: str
    file: str = ""
    font_type: str = ""


@dataclass
class FontEvent:
    """Record of a font action."""
    action: str
    font_name: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class FontManager:
    """Windows font management via Registry."""

    def __init__(self) -> None:
        self._events: list[FontEvent] = []
        self._lock = threading.Lock()
        self._cache: list[dict[str, Any]] | None = None
        self._cache_time: float = 0

    # ── Font Listing ───────────────────────────────────────────────────

    def list_fonts(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List all installed fonts from Registry."""
        if use_cache and self._cache and (time.time() - self._cache_time) < 60:
            return self._cache

        fonts = []
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, FONTS_KEY)
            try:
                i = 0
                while True:
                    try:
                        name, file, _ = winreg.EnumValue(key, i)
                        font_type = self._detect_type(name, file)
                        fonts.append({
                            "name": name,
                            "file": file,
                            "type": font_type,
                        })
                        i += 1
                    except OSError:
                        break
            finally:
                winreg.CloseKey(key)
            self._record("list_fonts", "", True, f"{len(fonts)} fonts")
            self._cache = fonts
            self._cache_time = time.time()
        except Exception as e:
            self._record("list_fonts", "", False, str(e))
        return fonts

    def _detect_type(self, name: str, file: str) -> str:
        """Detect font type from name/file."""
        lower_file = file.lower()
        if lower_file.endswith(".ttf"):
            return "TrueType"
        elif lower_file.endswith(".otf"):
            return "OpenType"
        elif lower_file.endswith(".ttc"):
            return "TrueType Collection"
        elif lower_file.endswith(".fon"):
            return "Raster"
        name_lower = name.lower()
        if "truetype" in name_lower:
            return "TrueType"
        elif "opentype" in name_lower:
            return "OpenType"
        return "unknown"

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search fonts by name."""
        q = query.lower()
        return [f for f in self.list_fonts() if q in f.get("name", "").lower()]

    def get_font(self, name: str) -> dict[str, Any] | None:
        """Get font by exact name match."""
        for f in self.list_fonts():
            if f.get("name", "").lower() == name.lower():
                return f
        return None

    def count_by_type(self) -> dict[str, int]:
        """Count fonts by type."""
        fonts = self.list_fonts()
        counts: dict[str, int] = {}
        for f in fonts:
            t = f.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return counts

    def get_font_families(self) -> list[str]:
        """Get unique font family names."""
        families = set()
        for f in self.list_fonts():
            name = f.get("name", "")
            # Strip type suffix like "(TrueType)"
            if "(" in name:
                name = name[:name.rfind("(")].strip()
            # Strip style suffix
            for suffix in (" Bold", " Italic", " Light", " Regular", " Thin", " Medium"):
                if name.endswith(suffix):
                    name = name[:-len(suffix)]
                    break
            if name:
                families.add(name)
        return sorted(families)

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, font_name: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(FontEvent(
                action=action, font_name=font_name, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "font_name": e.font_name,
                 "timestamp": e.timestamp, "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        fonts = self.list_fonts()
        types = self.count_by_type()
        with self._lock:
            return {
                "total_fonts": len(fonts),
                "types": types,
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
font_manager = FontManager()
