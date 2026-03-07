"""Tests for src/plugin_manager.py — Dynamic plugin lifecycle.

Covers: PluginInfo, PluginManager (discover, load, unload, enable, disable,
get_plugin, list_plugins, hooks, get_stats), plugin_manager singleton.
Uses tmp_path for plugin directory isolation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.plugin_manager import PluginInfo, PluginManager, plugin_manager


def _create_plugin(plugins_dir: Path, name: str, manifest: dict | None = None,
                   main_code: str = "") -> Path:
    """Helper to create a plugin directory with manifest."""
    pdir = plugins_dir / name
    pdir.mkdir(parents=True)
    m = manifest or {"name": name, "version": "1.0", "description": "Test", "author": "test"}
    (pdir / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    if main_code:
        (pdir / "main.py").write_text(main_code, encoding="utf-8")
    return pdir


# ===========================================================================
# PluginInfo
# ===========================================================================

class TestPluginInfo:
    def test_defaults(self):
        p = PluginInfo(name="test", version="1.0", description="d",
                       author="a", path=Path("."))
        assert p.enabled is True
        assert p.tools == []
        assert p.errors == []


# ===========================================================================
# PluginManager — discover
# ===========================================================================

class TestDiscover:
    def test_discover(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        _create_plugin(tmp_path, "alpha")
        _create_plugin(tmp_path, "beta")
        names = pm.discover()
        assert names == ["alpha", "beta"]

    def test_discover_empty(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        assert pm.discover() == []

    def test_discover_no_manifest(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        (tmp_path / "nomanifest").mkdir()
        assert pm.discover() == []

    def test_discover_nonexistent_dir(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path / "nope")
        assert pm.discover() == []


# ===========================================================================
# PluginManager — load & unload
# ===========================================================================

class TestLoadUnload:
    def test_load(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        _create_plugin(tmp_path, "myplugin", {"name": "myplugin", "version": "2.0",
                                               "description": "My Plugin", "author": "me"})
        info = pm.load("myplugin")
        assert info.name == "myplugin"
        assert info.version == "2.0"
        assert pm.get_plugin("myplugin") is not None

    def test_load_with_main(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        code = "def on_load(name): pass\ndef on_unload(name): pass\n"
        _create_plugin(tmp_path, "hooked", main_code=code)
        info = pm.load("hooked")
        assert "on_load" in info.hooks

    def test_load_manifest_not_found(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            pm.load("nonexistent")

    def test_load_bad_main(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        _create_plugin(tmp_path, "bad", main_code="raise RuntimeError('broken')")
        info = pm.load("bad")
        assert len(info.errors) >= 1

    def test_unload(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        _create_plugin(tmp_path, "temp")
        pm.load("temp")
        assert pm.unload("temp") is True
        assert pm.get_plugin("temp") is None

    def test_unload_nonexistent(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        assert pm.unload("nope") is False


# ===========================================================================
# PluginManager — enable/disable
# ===========================================================================

class TestEnableDisable:
    def test_enable_disable(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        _create_plugin(tmp_path, "toggle")
        pm.load("toggle")
        assert pm.disable("toggle") is True
        assert pm.get_plugin("toggle").enabled is False
        assert pm.enable("toggle") is True
        assert pm.get_plugin("toggle").enabled is True

    def test_enable_nonexistent(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        assert pm.enable("nope") is False
        assert pm.disable("nope") is False


# ===========================================================================
# PluginManager — list & stats
# ===========================================================================

class TestListStats:
    def test_list_plugins(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        _create_plugin(tmp_path, "a", {"name": "a", "version": "1.0",
                                        "description": "A", "author": "x",
                                        "tools": ["tool1", "tool2"]})
        pm.load("a")
        plugins = pm.list_plugins()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "a"
        assert plugins[0]["tools"] == ["tool1", "tool2"]

    def test_stats(self, tmp_path):
        pm = PluginManager(plugins_dir=tmp_path)
        _create_plugin(tmp_path, "a", {"name": "a", "version": "1.0",
                                        "description": "", "author": "",
                                        "tools": ["t1"]})
        _create_plugin(tmp_path, "b", {"name": "b", "version": "1.0",
                                        "description": "", "author": ""})
        pm.load("a")
        pm.load("b")
        pm.disable("b")
        stats = pm.get_stats()
        assert stats["total_plugins"] == 2
        assert stats["enabled"] == 1
        assert stats["disabled"] == 1
        assert stats["total_tools"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert plugin_manager is not None
        assert isinstance(plugin_manager, PluginManager)
