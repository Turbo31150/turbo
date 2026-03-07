"""Tests for src/env_manager.py — Multi-environment configuration manager.

Covers: EnvManager (create_profile, delete_profile, set_active,
set_var, get_var, delete_var, get_profile, merge_profiles,
list_profiles, get_stats), env_manager singleton.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.env_manager import EnvManager, env_manager


class TestActiveProfile:
    def test_default_active(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.active_profile == "dev"

    def test_set_active(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.set_active("staging") is True
        assert em.active_profile == "staging"

    def test_set_active_nonexistent(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.set_active("nope") is False


class TestCreateDeleteProfile:
    def test_create(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.create_profile("test", {"KEY": "val"}) is True
        assert em.get_var("KEY", profile="test") == "val"

    def test_create_duplicate(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.create_profile("dev") is False

    def test_delete(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        em.create_profile("custom")
        assert em.delete_profile("custom") is True

    def test_delete_protected(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.delete_profile("dev") is False
        assert em.delete_profile("staging") is False
        assert em.delete_profile("prod") is False

    def test_delete_nonexistent(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.delete_profile("nope") is False


class TestVariables:
    def test_set_and_get(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.set_var("DB_HOST", "localhost") is True
        assert em.get_var("DB_HOST") == "localhost"

    def test_get_nonexistent(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.get_var("MISSING") is None

    def test_set_specific_profile(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        em.set_var("API_URL", "https://prod.api", profile="prod")
        assert em.get_var("API_URL", profile="prod") == "https://prod.api"
        assert em.get_var("API_URL", profile="dev") is None

    def test_set_invalid_profile(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.set_var("K", "V", profile="nope") is False

    def test_delete_var(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        em.set_var("KEY", "val")
        assert em.delete_var("KEY") is True
        assert em.get_var("KEY") is None

    def test_delete_var_nonexistent(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.delete_var("MISSING") is False

    def test_delete_var_invalid_profile(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.delete_var("K", profile="nope") is False


class TestGetProfile:
    def test_get_active(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        em.set_var("A", "1")
        p = em.get_profile()
        assert p == {"A": "1"}

    def test_get_named(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        em.set_var("B", "2", profile="staging")
        p = em.get_profile("staging")
        assert p == {"B": "2"}

    def test_get_nonexistent(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        assert em.get_profile("nope") == {}


class TestMergeProfiles:
    def test_merge(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        em.set_var("A", "base_a", profile="dev")
        em.set_var("B", "base_b", profile="dev")
        em.set_var("A", "overlay_a", profile="staging")
        merged = em.merge_profiles("dev", "staging")
        assert merged["A"] == "overlay_a"
        assert merged["B"] == "base_b"


class TestListProfiles:
    def test_list(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        profiles = em.list_profiles()
        names = [p["name"] for p in profiles]
        assert "dev" in names
        assert "staging" in names
        assert "prod" in names
        active = [p for p in profiles if p["active"]]
        assert len(active) == 1


class TestPersistence:
    def test_save_and_reload(self, tmp_path):
        store = tmp_path / "env.json"
        em1 = EnvManager(store_path=store)
        em1.set_var("KEY", "value")
        em1.set_active("staging")
        # Reload from same file
        em2 = EnvManager(store_path=store)
        assert em2.get_var("KEY", profile="dev") == "value"
        assert em2.active_profile == "staging"


class TestStats:
    def test_stats(self, tmp_path):
        em = EnvManager(store_path=tmp_path / "env.json")
        em.set_var("A", "1")
        em.set_var("B", "2", profile="prod")
        stats = em.get_stats()
        assert stats["total_profiles"] == 3
        assert stats["total_vars"] == 2
        assert stats["active_profile"] == "dev"


class TestSingleton:
    def test_exists(self):
        assert isinstance(env_manager, EnvManager)
