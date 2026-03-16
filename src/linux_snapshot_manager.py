"""Linux Snapshot Manager — LVM snapshots, btrfs snapshots, timeshift.

Replaces Windows VSS (Volume Shadow Copy Service).
Designed for JARVIS autonomous backup management.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "SnapshotEvent",
    "SnapshotInfo",
    "LinuxSnapshotManager",
]

logger = logging.getLogger("jarvis.linux_snapshot_manager")


@dataclass
class SnapshotInfo:
    """A snapshot entry."""
    name: str
    volume: str = ""
    created: str = ""
    size: str = ""
    snapshot_type: str = ""  # lvm, btrfs, timeshift


@dataclass
class SnapshotEvent:
    """Record of a snapshot action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class LinuxSnapshotManager:
    """Linux snapshot management (LVM, btrfs, timeshift)."""

    def __init__(self) -> None:
        self._events: list[SnapshotEvent] = []
        self._lock = threading.Lock()

    def list_shadow_copies(self) -> list[dict[str, Any]]:
        """List all available snapshots across backends."""
        snapshots: list[dict[str, Any]] = []
        snapshots.extend(self._list_lvm_snapshots())
        snapshots.extend(self._list_btrfs_snapshots())
        snapshots.extend(self._list_timeshift_snapshots())
        self._record("list_shadow_copies", True, f"{len(snapshots)} snapshots")
        return snapshots

    def _list_lvm_snapshots(self) -> list[dict[str, Any]]:
        """List LVM snapshots."""
        try:
            result = subprocess.run(
                ["lvs", "--noheadings", "-o", "lv_name,vg_name,lv_size,lv_attr,snap_percent",
                 "--separator", "|"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                snapshots = []
                for line in result.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 4:
                        attrs = parts[3]
                        # LVM snapshot attr starts with 's' or 'S'
                        if attrs and attrs[0].lower() == "s":
                            snapshots.append({
                                "name": parts[0],
                                "volume": parts[1],
                                "size": parts[2],
                                "type": "lvm",
                                "snap_percent": parts[4] if len(parts) > 4 else "",
                            })
                return snapshots
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug("LVM snapshot list error: %s", e)
        return []

    def _list_btrfs_snapshots(self) -> list[dict[str, Any]]:
        """List btrfs snapshots."""
        try:
            result = subprocess.run(
                ["btrfs", "subvolume", "list", "-s", "/"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                snapshots = []
                for line in result.stdout.strip().splitlines():
                    # Format: ID xxx gen yyy path <path>
                    parts = line.split()
                    path = ""
                    for i, p in enumerate(parts):
                        if p == "path" and i + 1 < len(parts):
                            path = parts[i + 1]
                            break
                    if path:
                        snapshots.append({
                            "name": path.split("/")[-1] if "/" in path else path,
                            "volume": "/",
                            "size": "",
                            "type": "btrfs",
                            "path": path,
                        })
                return snapshots
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug("btrfs snapshot list error: %s", e)
        return []

    def _list_timeshift_snapshots(self) -> list[dict[str, Any]]:
        """List timeshift snapshots."""
        try:
            result = subprocess.run(
                ["timeshift", "--list"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                snapshots = []
                lines = result.stdout.strip().splitlines()
                in_table = False
                for line in lines:
                    if "---" in line:
                        in_table = True
                        continue
                    if in_table and line.strip():
                        parts = line.split()
                        if len(parts) >= 3:
                            snapshots.append({
                                "name": parts[2] if len(parts) > 2 else parts[0],
                                "volume": "",
                                "size": parts[3] if len(parts) > 3 else "",
                                "type": "timeshift",
                                "date": f"{parts[0]} {parts[1]}" if len(parts) > 1 else parts[0],
                            })
                return snapshots
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug("timeshift list error: %s", e)
        return []

    def create_shadow_copy(self, volume: str = "/") -> bool:
        """Create a snapshot.

        Tries timeshift first, then btrfs, then LVM.
        Args:
            volume: Mount point or LV path to snapshot.
        """
        # Timeshift
        try:
            result = subprocess.run(
                ["timeshift", "--create", "--comments", f"JARVIS snapshot {time.strftime('%Y-%m-%d %H:%M')}"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                self._record("create_shadow_copy", True, "timeshift")
                return True
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Btrfs
        if volume == "/" or volume.startswith("/"):
            try:
                snap_name = f"jarvis-snap-{int(time.time())}"
                result = subprocess.run(
                    ["btrfs", "subvolume", "snapshot", volume, f"/.snapshots/{snap_name}"],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    self._record("create_shadow_copy", True, "btrfs")
                    return True
            except FileNotFoundError:
                pass
            except Exception:
                pass

        logger.warning("No snapshot backend available for volume: %s", volume)
        self._record("create_shadow_copy", False, "No snapshot backend available")
        return False

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(SnapshotEvent(action=action, success=success, detail=detail))

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


linux_snapshot_manager = LinuxSnapshotManager()
