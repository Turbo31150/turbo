"""Memory Diagnostics — Linux memory error monitoring.
Adapted from Windows mdsched for Ubuntu 22.04 LTS.
"""
from __future__ import annotations
import logging
import subprocess
from typing import Any

__all__ = ["MemoryDiagnostics"]

logger = logging.getLogger("jarvis.memory_diagnostics")

class MemoryDiagnostics:
    """Linux memory health monitoring."""

    def check_memory_errors(self) -> list[str]:
        """Check journalctl for ECC or memory-related errors."""
        try:
            result = subprocess.run(
                ["journalctl", "-p", "3", "--since", "24h"],
                capture_output=True, text=True, timeout=5
            )
            errors = []
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "memory" in line.lower() or "ecc" in line.lower() or "segfault" in line.lower():
                        errors.append(line)
            return errors
        except: return []

    def get_mem_info(self) -> dict[str, Any]:
        import psutil
        mem = psutil.virtual_memory()
        return {"total": mem.total, "available": mem.available, "percent": mem.percent}

memory_diagnostics = MemoryDiagnostics()
