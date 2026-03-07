"""Tests for src/config_vault.py — Secure secrets storage with namespaces, TTL, audit.

Covers: SecretEntry, ConfigVault (set_secret, get_secret, delete_secret, has_secret,
list_namespaces, list_keys, delete_namespace, rotate_secret, get_audit_log,
get_stats, persistence), config_vault singleton.
Uses tmp_path for file isolation.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_vault import SecretEntry, ConfigVault, config_vault


# ===========================================================================
# SecretEntry
# ===========================================================================

class TestSecretEntry:
    def test_defaults(self):
        e = SecretEntry(key="api_key", value="encoded_val")
        assert e.namespace == "default"
        assert e.ttl == 0
        assert e.access_count == 0
        assert e.is_expired is False

    def test_expired(self):
        e = SecretEntry(key="k", value="v", ttl=1,
                        created_at=time.time() - 10)
        assert e.is_expired is True

    def test_not_expired(self):
        e = SecretEntry(key="k", value="v", ttl=9999)
        assert e.is_expired is False


# ===========================================================================
# ConfigVault — encode/decode
# ===========================================================================

class TestEncodeDecode:
    def test_roundtrip(self):
        original = "my_secret_value_123"
        encoded = ConfigVault._encode(original)
        assert encoded != original
        assert ConfigVault._decode(encoded) == original


# ===========================================================================
# ConfigVault — CRUD
# ===========================================================================

class TestCrud:
    def test_set_and_get(self):
        cv = ConfigVault()
        cv.set_secret("api_key", "sk-12345")
        assert cv.get_secret("api_key") == "sk-12345"

    def test_get_missing(self):
        cv = ConfigVault()
        assert cv.get_secret("nope") is None

    def test_set_with_namespace(self):
        cv = ConfigVault()
        cv.set_secret("token", "abc", namespace="telegram")
        assert cv.get_secret("token", namespace="telegram") == "abc"
        assert cv.get_secret("token", namespace="default") is None

    def test_delete(self):
        cv = ConfigVault()
        cv.set_secret("key", "val")
        assert cv.delete_secret("key") is True
        assert cv.get_secret("key") is None

    def test_delete_nonexistent(self):
        cv = ConfigVault()
        assert cv.delete_secret("nope") is False

    def test_has_secret(self):
        cv = ConfigVault()
        cv.set_secret("key", "val")
        assert cv.has_secret("key") is True
        assert cv.has_secret("nope") is False

    def test_overwrite(self):
        cv = ConfigVault()
        cv.set_secret("key", "v1")
        cv.set_secret("key", "v2")
        assert cv.get_secret("key") == "v2"


# ===========================================================================
# ConfigVault — TTL
# ===========================================================================

class TestTTL:
    def test_expired_secret_returns_none(self):
        cv = ConfigVault()
        cv.set_secret("temp", "val", ttl=1)
        # Manually expire it
        full_key = cv._make_key("default", "temp")
        cv._secrets[full_key].created_at = time.time() - 10
        assert cv.get_secret("temp") is None

    def test_has_secret_expired(self):
        cv = ConfigVault()
        cv.set_secret("temp", "val", ttl=1)
        full_key = cv._make_key("default", "temp")
        cv._secrets[full_key].created_at = time.time() - 10
        assert cv.has_secret("temp") is False

    def test_non_expired_works(self):
        cv = ConfigVault()
        cv.set_secret("temp", "val", ttl=9999)
        assert cv.get_secret("temp") == "val"


# ===========================================================================
# ConfigVault — namespaces
# ===========================================================================

class TestNamespaces:
    def test_list_namespaces(self):
        cv = ConfigVault()
        cv.set_secret("a", "1", namespace="ns1")
        cv.set_secret("b", "2", namespace="ns2")
        ns = cv.list_namespaces()
        assert set(ns) == {"ns1", "ns2"}

    def test_list_keys(self):
        cv = ConfigVault()
        cv.set_secret("a", "1", namespace="ns1")
        cv.set_secret("b", "2", namespace="ns1")
        cv.set_secret("c", "3", namespace="ns2")
        keys = cv.list_keys("ns1")
        assert sorted(keys) == ["a", "b"]

    def test_delete_namespace(self):
        cv = ConfigVault()
        cv.set_secret("a", "1", namespace="temp")
        cv.set_secret("b", "2", namespace="temp")
        cv.set_secret("c", "3", namespace="keep")
        removed = cv.delete_namespace("temp")
        assert removed == 2
        assert cv.list_keys("temp") == []
        assert cv.list_keys("keep") == ["c"]


# ===========================================================================
# ConfigVault — rotation
# ===========================================================================

class TestRotation:
    def test_rotate(self):
        cv = ConfigVault()
        cv.set_secret("key", "old_val")
        assert cv.rotate_secret("key", "new_val") is True
        assert cv.get_secret("key") == "new_val"

    def test_rotate_nonexistent(self):
        cv = ConfigVault()
        assert cv.rotate_secret("nope", "val") is False


# ===========================================================================
# ConfigVault — audit
# ===========================================================================

class TestAudit:
    def test_audit_log(self):
        cv = ConfigVault()
        cv.set_secret("key", "val")
        cv.get_secret("key")
        log = cv.get_audit_log()
        assert len(log) >= 2  # set + get
        actions = [e["action"] for e in log]
        assert "set" in actions
        assert "get" in actions

    def test_audit_get_miss(self):
        cv = ConfigVault()
        cv.get_secret("nope")
        log = cv.get_audit_log()
        assert log[-1]["action"] == "get_miss"

    def test_access_count(self):
        cv = ConfigVault()
        cv.set_secret("key", "val")
        cv.get_secret("key")
        cv.get_secret("key")
        full_key = cv._make_key("default", "key")
        assert cv._secrets[full_key].access_count == 2


# ===========================================================================
# ConfigVault — persistence
# ===========================================================================

class TestPersistence:
    def test_save_and_load(self, tmp_path):
        store = tmp_path / "vault.json"
        cv = ConfigVault(store_path=store)
        cv.set_secret("api_key", "sk-12345", namespace="prod")
        assert store.exists()

        cv2 = ConfigVault(store_path=store)
        assert cv2.get_secret("api_key", namespace="prod") == "sk-12345"

    def test_no_store_path(self):
        cv = ConfigVault()
        cv.set_secret("key", "val")
        # Should not crash, just not persist
        assert cv.get_secret("key") == "val"


# ===========================================================================
# ConfigVault — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        cv = ConfigVault()
        cv.set_secret("a", "1", namespace="ns1")
        cv.set_secret("b", "2", namespace="ns2")
        stats = cv.get_stats()
        assert stats["total_secrets"] == 2
        assert stats["namespaces"] == 2
        assert stats["expired"] == 0

    def test_stats_empty(self):
        cv = ConfigVault()
        stats = cv.get_stats()
        assert stats["total_secrets"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert config_vault is not None
        assert isinstance(config_vault, ConfigVault)
