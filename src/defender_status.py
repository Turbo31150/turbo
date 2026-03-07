"""Defender Status — Windows Defender / Security status.

Antivirus state, signature dates, scan history, threat detection.
Uses PowerShell Get-MpComputerStatus (no external deps).
Designed for JARVIS autonomous security monitoring.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.defender_status")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class DefenderInfo:
    """Defender status information."""
    realtime_enabled: bool = False
    signature_version: str = ""
    last_scan: str = ""


@dataclass
class DefenderEvent:
    """Record of a defender action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class DefenderStatus:
    """Windows Defender status monitoring (read-only)."""

    def __init__(self) -> None:
        self._events: list[DefenderEvent] = []
        self._lock = threading.Lock()

    def get_status(self) -> dict[str, Any]:
        """Get Defender computer status."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-MpComputerStatus | Select-Object "
                 "AntivirusEnabled, RealTimeProtectionEnabled, "
                 "AntivirusSignatureLastUpdated, "
                 "AntivirusSignatureVersion, "
                 "AntispywareEnabled, "
                 "QuickScanEndTime, FullScanEndTime, "
                 "ComputerState | ConvertTo-Json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                sig_updated = data.get("AntivirusSignatureLastUpdated", "")
                if isinstance(sig_updated, dict):
                    sig_updated = str(sig_updated.get("DateTime", ""))
                quick_scan = data.get("QuickScanEndTime", "")
                if isinstance(quick_scan, dict):
                    quick_scan = str(quick_scan.get("DateTime", ""))
                full_scan = data.get("FullScanEndTime", "")
                if isinstance(full_scan, dict):
                    full_scan = str(full_scan.get("DateTime", ""))
                status = {
                    "antivirus_enabled": data.get("AntivirusEnabled", False),
                    "realtime_protection": data.get("RealTimeProtectionEnabled", False),
                    "antispyware_enabled": data.get("AntispywareEnabled", False),
                    "signature_version": data.get("AntivirusSignatureVersion", ""),
                    "signature_updated": str(sig_updated),
                    "quick_scan_end": str(quick_scan),
                    "full_scan_end": str(full_scan),
                    "computer_state": data.get("ComputerState", 0),
                }
                self._record("get_status", True)
                return status
        except Exception as e:
            self._record("get_status", False, str(e))
        return {"error": "Unable to query Defender status"}

    def get_threat_history(self) -> list[dict[str, Any]]:
        """Get recent threat detections."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-MpThreatDetection | Select-Object -First 20 "
                 "ThreatID, ProcessName, DomainUser, "
                 "InitialDetectionTime, ActionSuccess | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                threats = []
                for t in data:
                    det_time = t.get("InitialDetectionTime", "")
                    if isinstance(det_time, dict):
                        det_time = str(det_time.get("DateTime", ""))
                    threats.append({
                        "threat_id": t.get("ThreatID", 0),
                        "process": t.get("ProcessName", "") or "",
                        "user": t.get("DomainUser", "") or "",
                        "detected": str(det_time),
                        "action_success": t.get("ActionSuccess", False),
                    })
                return threats
        except Exception:
            pass
        return []

    def is_protected(self) -> bool:
        """Quick check: is Defender active and protecting?"""
        status = self.get_status()
        return (
            status.get("antivirus_enabled", False)
            and status.get("realtime_protection", False)
        )

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(DefenderEvent(action=action, success=success, detail=detail))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {"total_events": len(self._events)}


defender_status = DefenderStatus()
