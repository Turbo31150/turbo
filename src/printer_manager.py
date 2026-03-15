"""Printer Manager — Linux CUPS printers inventory.
Adapted from Windows WMI for Ubuntu 22.04 LTS.
"""
from __future__ import annotations
import logging
import subprocess
from typing import Any

__all__ = ["PrinterManager"]

logger = logging.getLogger("jarvis.printer_manager")

class PrinterManager:
    """Linux printers management via lpstat/CUPS."""

    def list_printers(self) -> list[dict[str, Any]]:
        """List printers via lpstat."""
        try:
            result = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, timeout=5)
            printers = []
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    # Format: printer <name> is idle.  enabled since ...
                    parts = line.split()
                    if len(parts) >= 2:
                        printers.append({
                            "name": parts[1],
                            "status": parts[3] if len(parts) > 3 else "Unknown",
                            "manufacturer": "CUPS Native"
                        })
            return printers
        except: return []

    def get_default_printer(self) -> str:
        try:
            r = subprocess.run(["lpstat", "-d"], capture_output=True, text=True)
            return r.stdout.split(':')[-1].strip() if result.returncode == 0 else "None"
        except: return "None"

printer_manager = PrinterManager()
