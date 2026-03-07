"""Disk Monitor — Windows disk space monitoring and alerts.

Monitor disk usage, set thresholds, track history, detect drives.
Uses shutil.disk_usage and ctypes (no external dependencies).
Designed for JARVIS autonomous storage management.
"""

from __future__ import annotations

import ctypes
import logging
import shutil
import string
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "DiskAlert",
    "DiskMonitor",
    "DiskSnapshot",
    "DriveInfo",
]

logger = logging.getLogger("jarvis.disk_monitor")


@dataclass
class DriveInfo:
    """Information about a disk drive."""
    letter: str
    total_gb: float
    used_gb: float
    free_gb: float
    percent_used: float
    label: str = ""
    drive_type: str = ""


@dataclass
class DiskAlert:
    """A disk space alert."""
    drive: str
    threshold: float  # percent
    current: float
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False


@dataclass
class DiskSnapshot:
    """A point-in-time snapshot of all drives."""
    snapshot_id: str
    drives: list[dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


# Drive type mapping from GetDriveTypeW
DRIVE_TYPES = {
    0: "unknown",
    1: "no_root",
    2: "removable",
    3: "fixed",
    4: "network",
    5: "cdrom",
    6: "ramdisk",
}


class DiskMonitor:
    """Disk space monitoring with alerts and history."""

    def __init__(self) -> None:
        self._thresholds: dict[str, float] = {}  # drive -> percent threshold
        self._alerts: list[DiskAlert] = []
        self._snapshots: list[DiskSnapshot] = []
        self._snap_counter = 0
        self._lock = threading.Lock()

    # ── Drive Info ────────────────────────────────────────────────────

    def list_drives(self) -> list[dict[str, Any]]:
        """List all available drives with usage info."""
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if bitmask & (1 << i):
                path = f"{letter}:\\"
                try:
                    total, used, free = shutil.disk_usage(path)
                    total_gb = round(total / (1024**3), 2)
                    free_gb = round(free / (1024**3), 2)
                    used_gb = round(used / (1024**3), 2)
                    pct = round(used / total * 100, 1) if total > 0 else 0

                    # Drive type
                    dtype = DRIVE_TYPES.get(
                        ctypes.windll.kernel32.GetDriveTypeW(path), "unknown"
                    )

                    drives.append({
                        "letter": letter, "total_gb": total_gb,
                        "used_gb": used_gb, "free_gb": free_gb,
                        "percent_used": pct, "drive_type": dtype,
                    })
                except (OSError, PermissionError):
                    drives.append({
                        "letter": letter, "total_gb": 0, "used_gb": 0,
                        "free_gb": 0, "percent_used": 0, "drive_type": "inaccessible",
                    })
        return drives

    def get_drive(self, letter: str) -> dict[str, Any]:
        """Get info for a specific drive."""
        letter = letter.upper().rstrip(":\\")
        path = f"{letter}:\\"
        try:
            total, used, free = shutil.disk_usage(path)
            return {
                "letter": letter,
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "percent_used": round(used / total * 100, 1) if total > 0 else 0,
                "drive_type": DRIVE_TYPES.get(
                    ctypes.windll.kernel32.GetDriveTypeW(path), "unknown"
                ),
            }
        except Exception as e:
            return {"letter": letter, "error": str(e)}

    # ── Thresholds & Alerts ───────────────────────────────────────────

    def set_threshold(self, drive: str, percent: float) -> None:
        """Set usage alert threshold for a drive (e.g., 90.0 = 90%)."""
        with self._lock:
            self._thresholds[drive.upper()] = percent

    def remove_threshold(self, drive: str) -> bool:
        with self._lock:
            if drive.upper() in self._thresholds:
                del self._thresholds[drive.upper()]
                return True
            return False

    def check_thresholds(self) -> list[dict[str, Any]]:
        """Check all drives against thresholds, return new alerts."""
        new_alerts = []
        with self._lock:
            thresholds = dict(self._thresholds)
        for letter, threshold in thresholds.items():
            info = self.get_drive(letter)
            pct = info.get("percent_used", 0)
            if pct >= threshold:
                alert = DiskAlert(drive=letter, threshold=threshold, current=pct)
                with self._lock:
                    self._alerts.append(alert)
                new_alerts.append({
                    "drive": letter, "threshold": threshold,
                    "current": pct, "timestamp": alert.timestamp,
                })
        return new_alerts

    def get_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"drive": a.drive, "threshold": a.threshold,
                 "current": a.current, "timestamp": a.timestamp,
                 "resolved": a.resolved}
                for a in self._alerts[-limit:]
            ]

    # ── Snapshots ─────────────────────────────────────────────────────

    def take_snapshot(self) -> DiskSnapshot:
        """Take a snapshot of all drive usage."""
        drives = self.list_drives()
        with self._lock:
            self._snap_counter += 1
            sid = f"dsnap_{self._snap_counter}"
        snap = DiskSnapshot(snapshot_id=sid, drives=drives)
        with self._lock:
            self._snapshots.append(snap)
        return snap

    def list_snapshots(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"id": s.snapshot_id, "drive_count": len(s.drives),
                 "timestamp": s.timestamp}
                for s in self._snapshots[-limit:]
            ]

    def compare_snapshots(self, id_a: str, id_b: str) -> dict[str, Any]:
        """Compare two snapshots to see disk usage changes."""
        with self._lock:
            snap_a = next((s for s in self._snapshots if s.snapshot_id == id_a), None)
            snap_b = next((s for s in self._snapshots if s.snapshot_id == id_b), None)
        if not snap_a or not snap_b:
            return {"error": "Snapshot not found"}
        changes = []
        drives_a = {d["letter"]: d for d in snap_a.drives}
        drives_b = {d["letter"]: d for d in snap_b.drives}
        all_letters = set(drives_a.keys()) | set(drives_b.keys())
        for letter in sorted(all_letters):
            a = drives_a.get(letter, {})
            b = drives_b.get(letter, {})
            delta = b.get("used_gb", 0) - a.get("used_gb", 0)
            if abs(delta) > 0.01:
                changes.append({
                    "drive": letter,
                    "used_before": a.get("used_gb", 0),
                    "used_after": b.get("used_gb", 0),
                    "delta_gb": round(delta, 2),
                })
        return {"changes": changes, "snapshot_a": id_a, "snapshot_b": id_b}

    # ── Query ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        drives = self.list_drives()
        total_space = sum(d.get("total_gb", 0) for d in drives)
        total_free = sum(d.get("free_gb", 0) for d in drives)
        with self._lock:
            return {
                "drive_count": len(drives),
                "total_space_gb": round(total_space, 1),
                "total_free_gb": round(total_free, 1),
                "total_alerts": len(self._alerts),
                "total_snapshots": len(self._snapshots),
                "thresholds": dict(self._thresholds),
            }


# ── Singleton ───────────────────────────────────────────────────────
disk_monitor = DiskMonitor()
