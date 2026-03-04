"""Feature Flags — Dynamic feature toggling with conditions.

Toggle features at runtime with rule-based conditions:
percentage rollout, time windows, node whitelist.
Thread-safe, persistent via JSON file.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.feature_flags")


@dataclass
class Flag:
    name: str
    enabled: bool = False
    description: str = ""
    percentage: float = 100.0  # rollout %
    whitelist: list[str] = field(default_factory=list)
    blacklist: list[str] = field(default_factory=list)
    start_ts: float | None = None  # time window start
    end_ts: float | None = None    # time window end
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    check_count: int = 0


class FeatureFlagManager:
    """Runtime feature flag management."""

    def __init__(self, store_path: Path | None = None):
        self._flags: dict[str, Flag] = {}
        self._store = store_path or Path("data/feature_flags.json")
        self._lock = threading.Lock()
        self._load()

    # ── Core API ──────────────────────────────────────────────────

    def create(
        self,
        name: str,
        enabled: bool = False,
        description: str = "",
        percentage: float = 100.0,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
        start_ts: float | None = None,
        end_ts: float | None = None,
        metadata: dict | None = None,
    ) -> Flag:
        with self._lock:
            flag = Flag(
                name=name, enabled=enabled, description=description,
                percentage=percentage,
                whitelist=whitelist or [], blacklist=blacklist or [],
                start_ts=start_ts, end_ts=end_ts,
                metadata=metadata or {},
            )
            self._flags[name] = flag
            self._save()
            return flag

    def is_enabled(self, name: str, context: str | None = None) -> bool:
        """Check if flag is active for optional context (node/user id)."""
        with self._lock:
            flag = self._flags.get(name)
            if not flag:
                return False
            flag.check_count += 1
            if not flag.enabled:
                return False
            # Time window
            now = time.time()
            if flag.start_ts and now < flag.start_ts:
                return False
            if flag.end_ts and now > flag.end_ts:
                return False
            # Blacklist
            if context and context in flag.blacklist:
                return False
            # Whitelist bypass
            if context and flag.whitelist and context in flag.whitelist:
                return True
            # Percentage rollout
            if flag.percentage < 100.0:
                if context:
                    roll = hash(f"{name}:{context}") % 100
                else:
                    roll = random.randint(0, 99)
                if roll >= flag.percentage:
                    return False
            return True

    def toggle(self, name: str, enabled: bool | None = None) -> bool:
        with self._lock:
            flag = self._flags.get(name)
            if not flag:
                return False
            flag.enabled = not flag.enabled if enabled is None else enabled
            flag.updated_at = time.time()
            self._save()
            return True

    def delete(self, name: str) -> bool:
        with self._lock:
            removed = self._flags.pop(name, None) is not None
            if removed:
                self._save()
            return removed

    def get_flag(self, name: str) -> dict | None:
        flag = self._flags.get(name)
        return asdict(flag) if flag else None

    def list_flags(self) -> list[dict]:
        return [
            {"name": f.name, "enabled": f.enabled, "description": f.description,
             "percentage": f.percentage, "check_count": f.check_count}
            for f in self._flags.values()
        ]

    def get_stats(self) -> dict:
        flags = list(self._flags.values())
        return {
            "total_flags": len(flags),
            "enabled": sum(1 for f in flags if f.enabled),
            "disabled": sum(1 for f in flags if not f.enabled),
            "total_checks": sum(f.check_count for f in flags),
        }

    # ── Persistence ───────────────────────────────────────────────

    def _save(self) -> None:
        try:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            data = {n: asdict(f) for n, f in self._flags.items()}
            self._store.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug("feature_flags save error: %s", e)

    def _load(self) -> None:
        try:
            if self._store.exists():
                raw = json.loads(self._store.read_text(encoding="utf-8"))
                for name, d in raw.items():
                    self._flags[name] = Flag(**d)
        except Exception as e:
            logger.debug("feature_flags load error: %s", e)


# ── Singleton ────────────────────────────────────────────────────────────────
feature_flags = FeatureFlagManager()
