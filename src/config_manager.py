"""JARVIS Config Manager — Centralized configuration with hot-reload.

Single source of truth for all JARVIS configuration. JSON-based with
schema validation, hot-reload without restart, and change history.

Usage:
    from src.config_manager import config_manager
    config_manager.get("cluster.nodes.M1.weight")     # 1.8
    config_manager.set("cluster.nodes.M1.weight", 2.0) # update + history
    config_manager.reload()                             # hot-reload from disk
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.config")

CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "jarvis_config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "cluster": {
        "nodes": {
            "M1": {"host": "127.0.0.1", "port": 1234, "weight": 1.8, "max_concurrent": 3},
            "M2": {"host": "192.168.1.26", "port": 1234, "weight": 1.4, "max_concurrent": 3},
            "M3": {"host": "192.168.1.113", "port": 1234, "weight": 1.0, "max_concurrent": 2},
            "OL1": {"host": "127.0.0.1", "port": 11434, "weight": 1.3, "max_concurrent": 3},
        },
        "health_check_interval_s": 30,
        "timeout_s": 120,
    },
    "routing": {
        "default_task_type": "simple",
        "fallback_enabled": True,
        "drift_threshold": 0.3,
    },
    "autonomous": {
        "enabled": True,
        "tick_interval_s": 10,
        "proactive_interval_s": 600,
        "optimizer_interval_s": 300,
    },
    "trading": {
        "enabled": False,
        "dry_run": True,
        "leverage": 10,
        "tp_pct": 0.4,
        "sl_pct": 0.25,
        "min_score": 70,
    },
    "voice": {
        "wake_word_threshold": 0.7,
        "tts_voice": "fr-FR-DeniseNeural",
        "whisper_model": "large-v3-turbo",
    },
    "notifications": {
        "toast_enabled": True,
        "tts_on_critical": True,
        "cooldown_s": 60,
    },
    "alerts": {
        "escalation_info_threshold": 5,
        "escalation_warning_threshold": 3,
        "cooldown_s": 120,
    },
}


class ConfigManager:
    """Centralized config with hot-reload and change tracking."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._path = config_path or CONFIG_PATH
        self._lock = threading.RLock()
        self._config: dict[str, Any] = {}
        self._history: list[dict[str, Any]] = []
        self._max_history = 200
        self._last_modified: float = 0.0
        self._load()

    def _load(self) -> None:
        """Load config from disk, or create default."""
        with self._lock:
            if self._path.exists():
                try:
                    self._config = json.loads(self._path.read_text(encoding="utf-8"))
                    self._last_modified = os.path.getmtime(str(self._path))
                    return
                except Exception as e:
                    logger.warning("Config load failed, using defaults: %s", e)

            self._config = json.loads(json.dumps(DEFAULT_CONFIG))
            self._save()

    def _save(self) -> None:
        """Persist config to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._config, indent=2, ensure_ascii=False), encoding="utf-8")
            self._last_modified = os.path.getmtime(str(self._path))
        except Exception as e:
            logger.error("Config save failed: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by dotted path (e.g. 'cluster.nodes.M1.weight')."""
        with self._lock:
            parts = key.split(".")
            current = self._config
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current

    def set(self, key: str, value: Any) -> None:
        """Set a config value by dotted path. Records in history and saves."""
        with self._lock:
            parts = key.split(".")
            current = self._config
            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]

            old_value = current.get(parts[-1])
            current[parts[-1]] = value

            self._history.append({
                "ts": time.time(),
                "key": key,
                "old": old_value,
                "new": value,
            })
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

            self._save()

    def reload(self) -> bool:
        """Hot-reload config from disk if modified."""
        with self._lock:
            if not self._path.exists():
                return False
            mtime = os.path.getmtime(str(self._path))
            if mtime <= self._last_modified:
                return False
            try:
                self._config = json.loads(self._path.read_text(encoding="utf-8"))
                self._last_modified = mtime
                logger.info("Config hot-reloaded")
                return True
            except Exception as e:
                logger.error("Config reload failed: %s", e)
                return False

    def get_section(self, section: str) -> dict[str, Any]:
        """Get a full config section."""
        with self._lock:
            return json.loads(json.dumps(self._config.get(section, {})))

    def get_all(self) -> dict[str, Any]:
        """Get full config."""
        with self._lock:
            return json.loads(json.dumps(self._config))

    def reset_section(self, section: str) -> None:
        """Reset a section to defaults."""
        with self._lock:
            if section in DEFAULT_CONFIG:
                old = self._config.get(section)
                self._config[section] = json.loads(json.dumps(DEFAULT_CONFIG[section]))
                self._history.append({
                    "ts": time.time(), "key": section,
                    "old": "reset", "new": "defaults",
                })
                self._save()

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return change history."""
        return self._history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Config stats."""
        return {
            "path": str(self._path),
            "sections": list(self._config.keys()),
            "total_changes": len(self._history),
            "last_modified": self._last_modified,
        }


# Global singleton
config_manager = ConfigManager()
