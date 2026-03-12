"""Environment Manager — Config profiles for dev/staging/prod.

Manages environment variables per profile with merge,
override, and active profile switching. Thread-safe.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.env_manager")


class EnvManager:
    """Multi-environment configuration manager."""

    def __init__(self, store_path: Path | None = None):
        self._profiles: dict[str, dict[str, str]] = {
            "dev": {}, "staging": {}, "prod": {},
        }
        self._active: str = "dev"
        self._store = store_path or Path("data/env_profiles.json")
        self._lock = threading.Lock()
        self._load()

    @property
    def active_profile(self) -> str:
        return self._active

    def set_active(self, profile: str) -> bool:
        with self._lock:
            if profile not in self._profiles:
                return False
            self._active = profile
            self._save()
            return True

    def create_profile(self, name: str, variables: dict[str, str] | None = None) -> bool:
        with self._lock:
            if name in self._profiles:
                return False
            self._profiles[name] = variables or {}
            self._save()
            return True

    def delete_profile(self, name: str) -> bool:
        with self._lock:
            if name in ("dev", "staging", "prod"):
                return False  # protected
            removed = self._profiles.pop(name, None) is not None
            if removed:
                self._save()
            return removed

    def set_var(self, key: str, value: str, profile: str | None = None) -> bool:
        with self._lock:
            p = profile or self._active
            if p not in self._profiles:
                return False
            self._profiles[p][key] = value
            self._save()
            return True

    def get_var(self, key: str, profile: str | None = None) -> str | None:
        p = profile or self._active
        prof = self._profiles.get(p, {})
        return prof.get(key)

    def delete_var(self, key: str, profile: str | None = None) -> bool:
        with self._lock:
            p = profile or self._active
            if p not in self._profiles:
                return False
            removed = self._profiles[p].pop(key, None) is not None
            if removed:
                self._save()
            return removed

    def get_profile(self, name: str | None = None) -> dict[str, str]:
        p = name or self._active
        return dict(self._profiles.get(p, {}))

    def merge_profiles(self, base: str, overlay: str) -> dict[str, str]:
        """Merge two profiles (overlay wins on conflicts)."""
        base_vars = dict(self._profiles.get(base, {}))
        overlay_vars = self._profiles.get(overlay, {})
        base_vars.update(overlay_vars)
        return base_vars

    def list_profiles(self) -> list[dict]:
        return [
            {"name": n, "var_count": len(v), "active": n == self._active}
            for n, v in self._profiles.items()
        ]

    def get_stats(self) -> dict:
        return {
            "total_profiles": len(self._profiles),
            "active_profile": self._active,
            "total_vars": sum(len(v) for v in self._profiles.values()),
        }

    def _save(self) -> None:
        try:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            data = {"profiles": self._profiles, "active": self._active}
            self._store.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug("env save error: %s", e)

    def _load(self) -> None:
        try:
            if self._store.exists():
                data = json.loads(self._store.read_text(encoding="utf-8"))
                self._profiles.update(data.get("profiles", {}))
                self._active = data.get("active", "dev")
        except Exception as e:
            logger.debug("env load error: %s", e)


# ── Singleton ────────────────────────────────────────────────────────────────
env_manager = EnvManager()
