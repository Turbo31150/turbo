"""Snapshot Manager — System state snapshots with comparison and rollback.

Capture system state (config, processes, environment, custom data),
compare snapshots with diff, tag and restore, maintain history.
Designed for JARVIS diagnostic and rollback capabilities.
"""

from __future__ import annotations

import copy
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.snapshot_manager")


@dataclass
class Snapshot:
    """A captured system state snapshot."""
    snapshot_id: str
    name: str
    data: dict[str, Any]
    tags: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    description: str = ""

    @property
    def size(self) -> int:
        """Approximate size in keys."""
        return sum(len(v) if isinstance(v, (list, dict)) else 1 for v in self.data.values())


class SnapshotManager:
    """Manage system state snapshots with diff and restore."""

    def __init__(self) -> None:
        self._snapshots: dict[str, Snapshot] = {}
        self._counter = 0
        self._lock = threading.Lock()
        self._restore_history: list[dict[str, Any]] = []

    # ── Capture ─────────────────────────────────────────────────────

    def capture(
        self,
        name: str,
        data: dict[str, Any],
        tags: list[str] | None = None,
        description: str = "",
    ) -> Snapshot:
        """Capture a snapshot of the given data."""
        with self._lock:
            self._counter += 1
            sid = f"snap_{self._counter}"
            snapshot = Snapshot(
                snapshot_id=sid,
                name=name,
                data=copy.deepcopy(data),
                tags=tags or [],
                description=description,
            )
            self._snapshots[sid] = snapshot
            return snapshot

    def capture_env(self, name: str = "env", tags: list[str] | None = None) -> Snapshot:
        """Capture current environment variables as a snapshot."""
        env_data = {"environment": dict(os.environ)}
        return self.capture(name, env_data, tags=tags, description="Environment variables snapshot")

    # ── Query ───────────────────────────────────────────────────────

    def get(self, snapshot_id: str) -> Snapshot | None:
        """Get a snapshot by ID."""
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def list_snapshots(self, tag: str | None = None) -> list[dict[str, Any]]:
        """List all snapshots."""
        with self._lock:
            result = []
            for s in self._snapshots.values():
                if tag and tag not in s.tags:
                    continue
                result.append({
                    "id": s.snapshot_id,
                    "name": s.name,
                    "tags": s.tags,
                    "timestamp": s.timestamp,
                    "description": s.description,
                    "size": s.size,
                })
            return result

    def delete(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        with self._lock:
            if snapshot_id in self._snapshots:
                del self._snapshots[snapshot_id]
                return True
            return False

    # ── Diff ────────────────────────────────────────────────────────

    def diff(self, id_a: str, id_b: str) -> dict[str, Any]:
        """Compare two snapshots and return differences."""
        with self._lock:
            snap_a = self._snapshots.get(id_a)
            snap_b = self._snapshots.get(id_b)
            if not snap_a or not snap_b:
                return {"error": "Snapshot not found"}

        return self._compute_diff(snap_a.data, snap_b.data)

    def _compute_diff(self, a: dict, b: dict) -> dict[str, Any]:
        """Compute diff between two dicts."""
        added = {k: b[k] for k in b if k not in a}
        removed = {k: a[k] for k in a if k not in b}
        changed = {}
        for k in a:
            if k in b and a[k] != b[k]:
                if isinstance(a[k], dict) and isinstance(b[k], dict):
                    nested = self._compute_diff(a[k], b[k])
                    if any(nested.values()):
                        changed[k] = nested
                else:
                    changed[k] = {"old": a[k], "new": b[k]}
        return {
            "added": added,
            "removed": removed,
            "changed": changed,
            "identical": len(added) == 0 and len(removed) == 0 and len(changed) == 0,
        }

    # ── Restore ─────────────────────────────────────────────────────

    def restore(self, snapshot_id: str) -> dict[str, Any] | None:
        """Restore data from a snapshot (returns the data for caller to apply)."""
        with self._lock:
            snap = self._snapshots.get(snapshot_id)
            if not snap:
                return None
            self._restore_history.append({
                "snapshot_id": snapshot_id,
                "name": snap.name,
                "timestamp": time.time(),
            })
            return copy.deepcopy(snap.data)

    def get_restore_history(self) -> list[dict[str, Any]]:
        """Get restore history."""
        with self._lock:
            return list(self._restore_history)

    # ── Tags ────────────────────────────────────────────────────────

    def add_tag(self, snapshot_id: str, tag: str) -> bool:
        """Add a tag to a snapshot."""
        with self._lock:
            snap = self._snapshots.get(snapshot_id)
            if snap and tag not in snap.tags:
                snap.tags.append(tag)
                return True
            return False

    def remove_tag(self, snapshot_id: str, tag: str) -> bool:
        """Remove a tag from a snapshot."""
        with self._lock:
            snap = self._snapshots.get(snapshot_id)
            if snap and tag in snap.tags:
                snap.tags.remove(tag)
                return True
            return False

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get snapshot manager statistics."""
        with self._lock:
            all_tags = set()
            for s in self._snapshots.values():
                all_tags.update(s.tags)
            return {
                "total_snapshots": len(self._snapshots),
                "total_tags": len(all_tags),
                "total_restores": len(self._restore_history),
                "tags": sorted(all_tags),
            }


# ── Singleton ───────────────────────────────────────────────────────
snapshot_manager = SnapshotManager()
