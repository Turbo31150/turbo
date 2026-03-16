"""Printer Manager — Printer inventory and management.

Lists printers, default printer, print events tracking.
Uses subprocess for printer queries.
"""
from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["PrinterInfo", "PrintEvent", "PrinterManager", "printer_manager"]

logger = logging.getLogger("jarvis.printer_manager")


@dataclass
class PrinterInfo:
    """Information about a printer."""
    name: str = ""
    status: str = "Unknown"
    manufacturer: str = ""
    is_default: bool = False
    port: str = ""


@dataclass
class PrintEvent:
    """A printer-related event."""
    action: str = ""
    success: bool = True
    detail: str = ""
    timestamp: float = field(default_factory=time.time)


class PrinterManager:
    """Printer management via subprocess."""

    def __init__(self) -> None:
        self._events: list[PrintEvent] = []

    def list_printers(self) -> list[dict[str, Any]]:
        """List printers."""
        try:
            result = subprocess.run(
                ["lpstat", "-p"], capture_output=True, text=True, timeout=5
            )
            printers = []
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        printers.append({
                            "name": parts[1],
                            "status": parts[3] if len(parts) > 3 else "Unknown",
                            "manufacturer": "CUPS Native",
                        })
            self._events.append(PrintEvent(action="list", detail=f"{len(printers)} printers"))
            return printers
        except Exception as e:
            self._events.append(PrintEvent(action="list", success=False, detail=str(e)))
            return []

    def get_default_printer(self) -> str:
        """Get the default printer name."""
        try:
            r = subprocess.run(["lpstat", "-d"], capture_output=True, text=True, timeout=5)
            return r.stdout.split(":")[-1].strip() if r.returncode == 0 else "None"
        except Exception:
            return "None"

    def get_events(self) -> list[dict[str, Any]]:
        """Get printer events."""
        return [{"action": e.action, "success": e.success, "detail": e.detail}
                for e in self._events]

    def get_stats(self) -> dict[str, Any]:
        """Get stats."""
        return {"total_events": len(self._events)}


printer_manager = PrinterManager()
