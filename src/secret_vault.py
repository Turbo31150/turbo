"""Secret Vault — Encrypted secrets storage.

Stores API keys, tokens, and credentials encrypted on disk
using Fernet symmetric encryption. Master key derived from
a passphrase or auto-generated.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.secret_vault")

# Use cryptography if available, fallback to base64 obfuscation
try:
    from cryptography.fernet import Fernet
    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False
    logger.warning("cryptography not installed — using base64 obfuscation (NOT secure)")


def _derive_key(passphrase: str) -> bytes:
    """Derive a Fernet key from a passphrase via SHA-256."""
    digest = hashlib.sha256(passphrase.encode()).digest()
    return base64.urlsafe_b64encode(digest)


class SecretVault:
    """Encrypted key-value secret storage."""

    def __init__(self, vault_path: Path | None = None, passphrase: str | None = None):
        self._path = vault_path or Path("data/.vault.enc")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._secrets: dict[str, dict] = {}

        # Setup encryption
        if HAS_FERNET:
            key = _derive_key(passphrase or "jarvis-default-key-change-me")
            self._fernet = Fernet(key)
        else:
            self._fernet = None

        self._load()

    def _encrypt(self, data: str) -> str:
        if self._fernet:
            return self._fernet.encrypt(data.encode()).decode()
        return base64.b64encode(data.encode()).decode()

    def _decrypt(self, data: str) -> str:
        if self._fernet:
            return self._fernet.decrypt(data.encode()).decode()
        return base64.b64decode(data.encode()).decode()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            decrypted = self._decrypt(raw)
            self._secrets = json.loads(decrypted)
        except Exception as e:
            logger.warning("Vault load failed (corrupted or wrong key): %s", e)
            self._secrets = {}

    def _save(self) -> None:
        try:
            data = json.dumps(self._secrets, indent=2)
            encrypted = self._encrypt(data)
            self._path.write_text(encrypted, encoding="utf-8")
        except Exception as e:
            logger.error("Vault save failed: %s", e)

    def set(self, key: str, value: str, metadata: dict | None = None) -> None:
        """Store a secret."""
        with self._lock:
            self._secrets[key] = {
                "value": value,
                "metadata": metadata or {},
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            self._save()

    def get(self, key: str) -> str | None:
        """Retrieve a secret value. Returns None if not found."""
        with self._lock:
            entry = self._secrets.get(key)
            return entry["value"] if entry else None

    def get_with_metadata(self, key: str) -> dict | None:
        """Get secret entry with metadata (excludes value for safety)."""
        with self._lock:
            entry = self._secrets.get(key)
            if not entry:
                return None
            return {
                "key": key,
                "metadata": entry.get("metadata", {}),
                "created_at": entry.get("created_at"),
                "updated_at": entry.get("updated_at"),
                "has_value": True,
            }

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._secrets:
                del self._secrets[key]
                self._save()
                return True
            return False

    def exists(self, key: str) -> bool:
        with self._lock:
            return key in self._secrets

    def list_keys(self) -> list[str]:
        """List all secret keys (not values)."""
        with self._lock:
            return list(self._secrets.keys())

    def list_entries(self) -> list[dict]:
        """List all entries with metadata (no values exposed)."""
        with self._lock:
            return [
                {
                    "key": k,
                    "metadata": v.get("metadata", {}),
                    "created_at": v.get("created_at"),
                    "updated_at": v.get("updated_at"),
                }
                for k, v in self._secrets.items()
            ]

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_secrets": len(self._secrets),
                "vault_path": str(self._path),
                "encrypted": HAS_FERNET,
                "vault_exists": self._path.exists(),
            }


# ── Singleton ────────────────────────────────────────────────────────────────
secret_vault = SecretVault()
