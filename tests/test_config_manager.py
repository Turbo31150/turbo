"""Tests for src/config_manager.py — Centralized configuration with hot-reload.

Covers: ConfigManager (get, set, reload, get_section, get_all, reset_section,
get_history, get_stats), config_manager singleton, DEFAULT_CONFIG.
Uses tmp_path for file isolation.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_manager import ConfigManager, config_manager, DEFAULT_CONFIG


# ===========================================================================
# DEFAULT_CONFIG
# ===========================================================================

class TestDefaults:
    def test_has_cluster_section(self):
        assert "cluster" in DEFAULT_CONFIG
        assert "M1" in DEFAULT_CONFIG["cluster"]["nodes"]

    def test_has_trading_section(self):
        assert "trading" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["trading"]["leverage"] == 10

    def test_has_voice_section(self):
        assert "voice" in DEFAULT_CONFIG


# ===========================================================================
# ConfigManager — get / set
# ===========================================================================

class TestGetSet:
    def test_get_dotted_path(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        assert cm.get("cluster.nodes.M1.weight") == 1.8

    def test_get_missing_returns_default(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        assert cm.get("nonexistent.key", "fallback") == "fallback"

    def test_get_top_level(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        cluster = cm.get("cluster")
        assert isinstance(cluster, dict)
        assert "nodes" in cluster

    def test_set_dotted_path(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        cm.set("cluster.nodes.M1.weight", 2.0)
        assert cm.get("cluster.nodes.M1.weight") == 2.0

    def test_set_creates_intermediate(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        cm.set("new.section.key", "value")
        assert cm.get("new.section.key") == "value"

    def test_set_records_history(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        cm.set("trading.leverage", 20)
        history = cm.get_history()
        assert len(history) >= 1
        assert history[-1]["key"] == "trading.leverage"
        assert history[-1]["old"] == 10
        assert history[-1]["new"] == 20

    def test_set_persists(self, tmp_path):
        config_path = tmp_path / "config.json"
        cm = ConfigManager(config_path=config_path)
        cm.set("trading.dry_run", False)
        # Reload from disk
        cm2 = ConfigManager(config_path=config_path)
        assert cm2.get("trading.dry_run") is False


# ===========================================================================
# ConfigManager — reload
# ===========================================================================

class TestReload:
    def test_reload_detects_changes(self, tmp_path):
        config_path = tmp_path / "config.json"
        cm = ConfigManager(config_path=config_path)
        # Manually modify file
        data = json.loads(config_path.read_text())
        data["trading"]["leverage"] = 50
        config_path.write_text(json.dumps(data))
        # Force mtime change
        import os
        os.utime(str(config_path), (time.time() + 1, time.time() + 1))
        assert cm.reload() is True
        assert cm.get("trading.leverage") == 50

    def test_reload_no_change(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        assert cm.reload() is False

    def test_reload_no_file(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        (tmp_path / "config.json").unlink()
        assert cm.reload() is False


# ===========================================================================
# ConfigManager — sections
# ===========================================================================

class TestSections:
    def test_get_section(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        trading = cm.get_section("trading")
        assert "leverage" in trading
        assert trading["leverage"] == 10

    def test_get_section_missing(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        assert cm.get_section("nonexistent") == {}

    def test_get_all(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        all_config = cm.get_all()
        assert "cluster" in all_config
        assert "trading" in all_config

    def test_reset_section(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        cm.set("trading.leverage", 100)
        cm.reset_section("trading")
        assert cm.get("trading.leverage") == 10


# ===========================================================================
# ConfigManager — stats
# ===========================================================================

class TestStats:
    def test_stats(self, tmp_path):
        cm = ConfigManager(config_path=tmp_path / "config.json")
        stats = cm.get_stats()
        assert "cluster" in stats["sections"]
        assert stats["total_changes"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert config_manager is not None
        assert isinstance(config_manager, ConfigManager)
