"""Plugin Manager — Dynamic plugin discovery and lifecycle management.

Plugins are directories under a configurable plugins_dir with a manifest.json.
Each plugin can register tools, handlers, and hooks.
"""

from __future__ import annotations

import json
import logging
import time
import importlib
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("jarvis.plugin_manager")


@dataclass
class PluginInfo:
    """Metadata for a loaded plugin."""
    name: str
    version: str
    description: str
    author: str
    path: Path
    enabled: bool = True
    loaded_at: float = field(default_factory=time.time)
    tools: list[str] = field(default_factory=list)
    hooks: dict[str, list[Callable]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class PluginManager:
    """Discovers, loads, and manages JARVIS plugins."""

    def __init__(self, plugins_dir: Path | None = None):
        self._plugins_dir = plugins_dir or Path("plugins")
        self._plugins: dict[str, PluginInfo] = {}
        self._hooks: dict[str, list[Callable]] = {}

    @property
    def plugins_dir(self) -> Path:
        return self._plugins_dir

    def discover(self) -> list[str]:
        """Scan plugins directory for valid plugins. Returns list of discovered names."""
        if not self._plugins_dir.exists():
            return []
        discovered = []
        for p in self._plugins_dir.iterdir():
            if p.is_dir() and (p / "manifest.json").exists():
                discovered.append(p.name)
        return sorted(discovered)

    def load(self, name: str) -> PluginInfo:
        """Load a plugin by name from the plugins directory."""
        plugin_dir = self._plugins_dir / name
        manifest_path = plugin_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Plugin '{name}' manifest not found at {manifest_path}")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        info = PluginInfo(
            name=manifest.get("name", name),
            version=manifest.get("version", "0.0.0"),
            description=manifest.get("description", ""),
            author=manifest.get("author", "unknown"),
            path=plugin_dir,
            tools=manifest.get("tools", []),
        )

        # Try loading main module
        main_file = plugin_dir / manifest.get("main", "main.py")
        if main_file.exists():
            try:
                spec = importlib.util.spec_from_file_location(f"plugins.{name}", str(main_file))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    # Register hooks if plugin defines them
                    if hasattr(mod, "on_load"):
                        self._register_hook("on_load", mod.on_load)
                        info.hooks.setdefault("on_load", []).append(mod.on_load)
                    if hasattr(mod, "on_unload"):
                        self._register_hook("on_unload", mod.on_unload)
                        info.hooks.setdefault("on_unload", []).append(mod.on_unload)
            except Exception as e:
                info.errors.append(f"Load error: {e}")
                logger.warning("Plugin %s load error: %s", name, e)

        self._plugins[name] = info
        self._fire_hook("on_load", name)
        return info

    def unload(self, name: str) -> bool:
        """Unload a plugin."""
        if name not in self._plugins:
            return False
        self._fire_hook("on_unload", name)
        del self._plugins[name]
        return True

    def enable(self, name: str) -> bool:
        if name in self._plugins:
            self._plugins[name].enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        if name in self._plugins:
            self._plugins[name].enabled = False
            return True
        return False

    def get_plugin(self, name: str) -> PluginInfo | None:
        return self._plugins.get(name)

    def list_plugins(self) -> list[dict]:
        """List all loaded plugins as dicts."""
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "enabled": p.enabled,
                "tools": p.tools,
                "errors": p.errors,
                "loaded_at": p.loaded_at,
            }
            for p in self._plugins.values()
        ]

    def _register_hook(self, event: str, callback: Callable) -> None:
        self._hooks.setdefault(event, []).append(callback)

    def _fire_hook(self, event: str, *args: Any) -> None:
        for cb in self._hooks.get(event, []):
            try:
                cb(*args)
            except Exception as e:
                logger.warning("Hook %s error: %s", event, e)

    def get_stats(self) -> dict:
        return {
            "total_plugins": len(self._plugins),
            "enabled": sum(1 for p in self._plugins.values() if p.enabled),
            "disabled": sum(1 for p in self._plugins.values() if not p.enabled),
            "total_tools": sum(len(p.tools) for p in self._plugins.values()),
            "hooks_registered": {k: len(v) for k, v in self._hooks.items()},
            "plugins_dir": str(self._plugins_dir),
        }


# ── Singleton ────────────────────────────────────────────────────────────────
plugin_manager = PluginManager()
