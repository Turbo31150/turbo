"""Shortcut Manager — Global hotkey registration and management.

Register keyboard shortcuts with callbacks, groups, enable/disable,
activation history, and conflict detection. Designed for JARVIS
Windows hotkey control (no external deps, uses internal registry).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


__all__ = [
    "ActivationEvent",
    "Shortcut",
    "ShortcutManager",
]

logger = logging.getLogger("jarvis.shortcut_manager")


@dataclass
class Shortcut:
    """A registered keyboard shortcut."""
    name: str
    keys: str  # e.g. "Ctrl+Shift+J"
    callback: Callable[[], Any] | None = None
    description: str = ""
    group: str = "default"
    enabled: bool = True
    activation_count: int = 0
    last_activated: float | None = None
    created_at: float = field(default_factory=time.time)


@dataclass
class ActivationEvent:
    """Record of a shortcut activation."""
    name: str
    keys: str
    timestamp: float = field(default_factory=time.time)
    result: str = ""
    success: bool = True


class ShortcutManager:
    """Manage keyboard shortcuts with groups and activation tracking."""

    def __init__(self) -> None:
        self._shortcuts: dict[str, Shortcut] = {}
        self._key_map: dict[str, str] = {}  # keys -> name
        self._activations: list[ActivationEvent] = []
        self._lock = threading.Lock()

    # ── Registration ────────────────────────────────────────────────

    def register(
        self,
        name: str,
        keys: str,
        callback: Callable[[], Any] | None = None,
        description: str = "",
        group: str = "default",
    ) -> Shortcut:
        """Register a keyboard shortcut."""
        normalized = self._normalize_keys(keys)
        shortcut = Shortcut(
            name=name,
            keys=normalized,
            callback=callback,
            description=description,
            group=group,
        )
        with self._lock:
            # Check for key conflict
            if normalized in self._key_map and self._key_map[normalized] != name:
                existing = self._key_map[normalized]
                logger.warning("Key conflict: %s already bound to %s", normalized, existing)
            self._shortcuts[name] = shortcut
            self._key_map[normalized] = name
        return shortcut

    def unregister(self, name: str) -> bool:
        """Remove a shortcut."""
        with self._lock:
            sc = self._shortcuts.get(name)
            if not sc:
                return False
            self._key_map.pop(sc.keys, None)
            del self._shortcuts[name]
            return True

    @staticmethod
    def _normalize_keys(keys: str) -> str:
        """Normalize key combination string."""
        parts = [p.strip().capitalize() for p in keys.split("+")]
        return "+".join(sorted(parts))

    # ── Activation ──────────────────────────────────────────────────

    def activate(self, name: str) -> dict[str, Any]:
        """Trigger a shortcut by name."""
        with self._lock:
            sc = self._shortcuts.get(name)
            if not sc:
                return {"success": False, "error": "not found"}
            if not sc.enabled:
                return {"success": False, "error": "disabled"}

        result_val = None
        success = True
        try:
            if sc.callback:
                result_val = sc.callback()
        except Exception as e:
            success = False
            result_val = str(e)

        with self._lock:
            sc.activation_count += 1
            sc.last_activated = time.time()
            self._activations.append(ActivationEvent(
                name=name, keys=sc.keys,
                result=str(result_val) if result_val else "",
                success=success,
            ))

        return {"success": success, "result": result_val, "name": name, "keys": sc.keys}

    def activate_by_keys(self, keys: str) -> dict[str, Any]:
        """Trigger a shortcut by key combination."""
        normalized = self._normalize_keys(keys)
        with self._lock:
            name = self._key_map.get(normalized)
        if not name:
            return {"success": False, "error": f"No shortcut bound to {keys}"}
        return self.activate(name)

    # ── Management ──────────────────────────────────────────────────

    def enable(self, name: str) -> bool:
        with self._lock:
            sc = self._shortcuts.get(name)
            if sc:
                sc.enabled = True
                return True
            return False

    def disable(self, name: str) -> bool:
        with self._lock:
            sc = self._shortcuts.get(name)
            if sc:
                sc.enabled = False
                return True
            return False

    def get(self, name: str) -> Shortcut | None:
        with self._lock:
            return self._shortcuts.get(name)

    # ── Query ───────────────────────────────────────────────────────

    def list_shortcuts(self, group: str | None = None) -> list[dict[str, Any]]:
        """List all shortcuts."""
        with self._lock:
            result = []
            for sc in self._shortcuts.values():
                if group and sc.group != group:
                    continue
                result.append({
                    "name": sc.name,
                    "keys": sc.keys,
                    "description": sc.description,
                    "group": sc.group,
                    "enabled": sc.enabled,
                    "activation_count": sc.activation_count,
                    "last_activated": sc.last_activated,
                })
            return result

    def list_groups(self) -> list[str]:
        """List all shortcut groups."""
        with self._lock:
            return list(set(sc.group for sc in self._shortcuts.values()))

    def check_conflicts(self) -> list[dict[str, Any]]:
        """Check for key binding conflicts."""
        with self._lock:
            keys_to_names: dict[str, list[str]] = {}
            for sc in self._shortcuts.values():
                keys_to_names.setdefault(sc.keys, []).append(sc.name)
            return [
                {"keys": k, "shortcuts": names}
                for k, names in keys_to_names.items()
                if len(names) > 1
            ]

    def get_activations(self, name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Get activation history."""
        with self._lock:
            events = self._activations
            if name:
                events = [e for e in events if e.name == name]
            return [
                {"name": e.name, "keys": e.keys, "timestamp": e.timestamp,
                 "result": e.result, "success": e.success}
                for e in events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        """Get shortcut manager statistics."""
        with self._lock:
            enabled = sum(1 for sc in self._shortcuts.values() if sc.enabled)
            groups = set(sc.group for sc in self._shortcuts.values())
            total_activations = sum(sc.activation_count for sc in self._shortcuts.values())
            return {
                "total_shortcuts": len(self._shortcuts),
                "enabled": enabled,
                "disabled": len(self._shortcuts) - enabled,
                "groups": len(groups),
                "total_activations": total_activations,
                "history_size": len(self._activations),
            }


# ── Singleton ───────────────────────────────────────────────────────
shortcut_manager = ShortcutManager()
