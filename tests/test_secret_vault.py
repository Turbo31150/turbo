"""Tests for src/secret_vault.py — Encrypted secrets storage.

Covers: SecretVault (set, get, get_with_metadata, delete, exists,
list_keys, list_entries, get_stats, persistence), secret_vault singleton.
Uses tmp_path for vault file isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.secret_vault import SecretVault, secret_vault


# ===========================================================================
# SecretVault — set & get
# ===========================================================================

class TestSetGet:
    def test_set_and_get(self, tmp_path):
        sv = SecretVault(vault_path=tmp_path / "vault.enc", passphrase="test")
        sv.set("api_key", "sk-12345")
        assert sv.get("api_key") == "sk-12345"

    def test_get_nonexistent(self, tmp_path):
        sv = SecretVault(vault_path=tmp_path / "vault.enc", passphrase="test")
        assert sv.get("nope") is None

    def test_get_with_metadata(self, tmp_path):
        sv = SecretVault(vault_path=tmp_path / "vault.enc", passphrase="test")
        sv.set("token", "abc123", metadata={"service": "github"})
        info = sv.get_with_metadata("token")
        assert info is not None
        assert info["has_value"] is True
        assert info["metadata"]["service"] == "github"
        # Value should NOT be exposed
        assert "value" not in info or info.get("value") is None

    def test_get_with_metadata_nonexistent(self, tmp_path):
        sv = SecretVault(vault_path=tmp_path / "vault.enc", passphrase="test")
        assert sv.get_with_metadata("nope") is None

    def test_overwrite(self, tmp_path):
        sv = SecretVault(vault_path=tmp_path / "vault.enc", passphrase="test")
        sv.set("key", "old")
        sv.set("key", "new")
        assert sv.get("key") == "new"


# ===========================================================================
# SecretVault — delete & exists
# ===========================================================================

class TestDeleteExists:
    def test_delete(self, tmp_path):
        sv = SecretVault(vault_path=tmp_path / "vault.enc", passphrase="test")
        sv.set("temp", "val")
        assert sv.delete("temp") is True
        assert sv.get("temp") is None

    def test_delete_nonexistent(self, tmp_path):
        sv = SecretVault(vault_path=tmp_path / "vault.enc", passphrase="test")
        assert sv.delete("nope") is False

    def test_exists(self, tmp_path):
        sv = SecretVault(vault_path=tmp_path / "vault.enc", passphrase="test")
        sv.set("key", "val")
        assert sv.exists("key") is True
        assert sv.exists("nope") is False


# ===========================================================================
# SecretVault — list
# ===========================================================================

class TestList:
    def test_list_keys(self, tmp_path):
        sv = SecretVault(vault_path=tmp_path / "vault.enc", passphrase="test")
        sv.set("a", "1")
        sv.set("b", "2")
        keys = sv.list_keys()
        assert "a" in keys
        assert "b" in keys

    def test_list_entries(self, tmp_path):
        sv = SecretVault(vault_path=tmp_path / "vault.enc", passphrase="test")
        sv.set("a", "1", metadata={"type": "api_key"})
        entries = sv.list_entries()
        assert len(entries) == 1
        assert entries[0]["key"] == "a"
        assert entries[0]["metadata"]["type"] == "api_key"


# ===========================================================================
# SecretVault — persistence
# ===========================================================================

class TestPersistence:
    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "vault.enc"
        sv1 = SecretVault(vault_path=path, passphrase="mypass")
        sv1.set("secret", "value123")
        # New instance with same passphrase should load the vault
        sv2 = SecretVault(vault_path=path, passphrase="mypass")
        assert sv2.get("secret") == "value123"

    def test_wrong_passphrase(self, tmp_path):
        path = tmp_path / "vault.enc"
        sv1 = SecretVault(vault_path=path, passphrase="correct")
        sv1.set("secret", "value")
        # Wrong passphrase should fail to decrypt
        sv2 = SecretVault(vault_path=path, passphrase="wrong")
        # Either returns None or loads empty (depending on encryption)
        assert sv2.get("secret") is None


# ===========================================================================
# SecretVault — stats
# ===========================================================================

class TestStats:
    def test_stats(self, tmp_path):
        sv = SecretVault(vault_path=tmp_path / "vault.enc", passphrase="test")
        sv.set("a", "1")
        stats = sv.get_stats()
        assert stats["total_secrets"] == 1
        assert stats["vault_exists"] is True


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert secret_vault is not None
        assert isinstance(secret_vault, SecretVault)
