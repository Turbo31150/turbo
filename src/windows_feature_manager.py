"""Windows Feature Manager — Windows optional features management.

List, search, filter optional features (WSL, Hyper-V, etc.).
Uses PowerShell Get-WindowsOptionalFeature (no external deps).
Designed for JARVIS autonomous feature discovery.
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
    "FeatureEvent",
    "WindowsFeature",
    "WindowsFeatureManager",
]

logger = logging.getLogger("jarvis.windows_feature_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class WindowsFeature:
    """A Windows optional feature."""
    name: str
    state: str = ""


@dataclass
class FeatureEvent:
    """Record of a feature action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class WindowsFeatureManager:
    """Windows optional features management (read-only)."""

    def __init__(self) -> None:
        self._events: list[FeatureEvent] = []
        self._lock = threading.Lock()

    # ── Features ──────────────────────────────────────────────────────────

    def list_features(self) -> list[dict[str, Any]]:
        """List all optional features."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WindowsOptionalFeature -Online | "
                 "Select-Object FeatureName, State | "
                 "ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                features = []
                for f in data:
                    state_val = f.get("State", "")
                    # State can be int (2=Enabled, 0/1=Disabled) or string
                    if isinstance(state_val, int):
                        state_str = "Enabled" if state_val == 2 else "Disabled"
                    else:
                        state_str = str(state_val)
                    features.append({
                        "name": f.get("FeatureName", ""),
                        "state": state_str,
                    })
                self._record("list_features", True, f"{len(features)} features")
                return features
        except Exception as e:
            self._record("list_features", False, str(e))
        return []

    def list_enabled(self) -> list[dict[str, Any]]:
        """List enabled features only."""
        return [f for f in self.list_features() if f.get("state") == "Enabled"]

    def list_disabled(self) -> list[dict[str, Any]]:
        """List disabled features only."""
        return [f for f in self.list_features() if f.get("state") != "Enabled"]

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search features by name."""
        q = query.lower()
        return [f for f in self.list_features() if q in f.get("name", "").lower()]

    def is_enabled(self, feature_name: str) -> bool:
        """Check if a specific feature is enabled."""
        fn = feature_name.lower()
        for f in self.list_features():
            if f.get("name", "").lower() == fn:
                return f.get("state") == "Enabled"
        return False

    def count_by_state(self) -> dict[str, int]:
        """Count features by state."""
        counts: dict[str, int] = {}
        for f in self.list_features():
            s = f.get("state", "Unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(FeatureEvent(
                action=action, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
windows_feature_manager = WindowsFeatureManager()
