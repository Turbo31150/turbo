"""Printer Manager — Windows printer management.

List printers, get status, print queue, default printer.
Uses subprocess with PowerShell/wmic (no external deps).
Designed for JARVIS autonomous printer management.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "PrintEvent",
    "PrinterInfo",
    "PrinterManager",
]

logger = logging.getLogger("jarvis.printer_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class PrinterInfo:
    """A detected printer."""
    name: str
    port: str = ""
    driver: str = ""
    status: str = ""
    is_default: bool = False
    is_network: bool = False


@dataclass
class PrintEvent:
    """Record of a printer action."""
    action: str
    printer: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class PrinterManager:
    """Windows printer management with status tracking."""

    def __init__(self) -> None:
        self._events: list[PrintEvent] = []
        self._lock = threading.Lock()

    # ── Printer Listing ────────────────────────────────────────────────

    def list_printers(self) -> list[dict[str, Any]]:
        """List all installed printers."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Printer | Select-Object Name, PortName, DriverName, "
                 "PrinterStatus, Type | ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                default = self._get_default_name()
                printers = []
                for p in data:
                    name = p.get("Name", "")
                    printers.append({
                        "name": name,
                        "port": p.get("PortName", ""),
                        "driver": p.get("DriverName", ""),
                        "status": str(p.get("PrinterStatus", "")),
                        "type": p.get("Type", ""),
                        "is_default": name == default,
                    })
                self._record("list_printers", "", True, f"{len(printers)} printers")
                return printers
        except Exception as e:
            self._record("list_printers", "", False, str(e))
        return self._list_printers_wmic()

    def _list_printers_wmic(self) -> list[dict[str, Any]]:
        """Fallback via wmic."""
        try:
            result = subprocess.run(
                ["wmic", "printer", "get", "Name,PortName,DriverName,Default", "/format:csv"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            printers = []
            for line in result.stdout.strip().split("\n"):
                parts = line.strip().split(",")
                if len(parts) >= 4 and parts[1]:
                    printers.append({
                        "name": parts[2] if len(parts) > 2 else "",
                        "port": parts[3] if len(parts) > 3 else "",
                        "driver": parts[1],
                        "is_default": parts[0].upper() == "TRUE" if parts[0] else False,
                    })
            return printers
        except Exception:
            return []

    def _get_default_name(self) -> str:
        """Get default printer name."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance Win32_Printer | Where-Object {$_.Default}).Name"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    def get_default(self) -> dict[str, Any]:
        """Get default printer info."""
        for p in self.list_printers():
            if p.get("is_default"):
                return p
        printers = self.list_printers()
        return printers[0] if printers else {"name": "none", "is_default": False}

    # ── Print Queue ────────────────────────────────────────────────────

    def get_queue(self, printer_name: str = "") -> list[dict[str, Any]]:
        """Get print queue for a printer."""
        cmd = "Get-PrintJob"
        if printer_name:
            cmd += f" -PrinterName '{printer_name}'"
        cmd += " | Select-Object Id, DocumentName, UserName, SubmittedTime, " \
               "JobStatus, Size | ConvertTo-Json -Depth 1"
        try:
            result = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                return [
                    {
                        "id": j.get("Id", 0),
                        "document": j.get("DocumentName", ""),
                        "user": j.get("UserName", ""),
                        "status": j.get("JobStatus", ""),
                        "size": j.get("Size", 0),
                    }
                    for j in data
                ]
        except Exception as e:
            self._record("get_queue", printer_name, False, str(e))
        return []

    # ── Printer Search ─────────────────────────────────────────────────

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search printers by name."""
        q = query.lower()
        return [p for p in self.list_printers() if q in p.get("name", "").lower()]

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, printer: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(PrintEvent(
                action=action, printer=printer, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "printer": e.printer,
                 "timestamp": e.timestamp, "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        printers = self.list_printers()
        default = next((p["name"] for p in printers if p.get("is_default")), "none")
        with self._lock:
            return {
                "total_printers": len(printers),
                "default_printer": default,
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
printer_manager = PrinterManager()
