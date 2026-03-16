"""Config Vault — Secure secrets storage with namespaces, TTL, and access audit."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass
class SecretEntry:
    key: str
    value: str  # stored obfuscated (base64)
    namespace: str = "default"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    ttl: float = 0  # 0 = no expiry
    access_count: int = 0
    last_accessed: float = 0.0

    @property
    def is_expired(self) -> bool:
        if self.ttl <= 0:
            return False
        return time.time() - self.created_at > self.ttl


class ConfigVault:
    """Secure configuration and secrets storage."""

    def __init__(self, store_path: Path | None = None):
        self._secrets: dict[str, SecretEntry] = {}
        self._access_log: list[dict] = []
        self._max_log = 500
        self._store_path = store_path
        self._lock = Lock()
        if store_path and store_path.exists():
            self._load()

    # ── Obfuscation (base64, not encryption — for demo) ────────────
    @staticmethod
    def _encode(value: str) -> str:
        return base64.b64encode(value.encode()).decode()

    @staticmethod
    def _decode(value: str) -> str:
        return base64.b64decode(value.encode()).decode()

    def _make_key(self, namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    # ── CRUD ────────────────────────────────────────────────────────
    def set_secret(self, key: str, value: str, namespace: str = "default",
                   ttl: float = 0) -> None:
        full_key = self._make_key(namespace, key)
        with self._lock:
            self._secrets[full_key] = SecretEntry(
                key=key, value=self._encode(value),
                namespace=namespace, ttl=ttl,
            )
            self._audit("set", namespace, key)
            self._save()

    def get_secret(self, key: str, namespace: str = "default") -> str | None:
        full_key = self._make_key(namespace, key)
        with self._lock:
            entry = self._secrets.get(full_key)
            if not entry:
                self._audit("get_miss", namespace, key)
                return None
            if entry.is_expired:
                del self._secrets[full_key]
                self._audit("expired", namespace, key)
                self._save()
                return None
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._audit("get", namespace, key)
            return self._decode(entry.value)

    def delete_secret(self, key: str, namespace: str = "default") -> bool:
        full_key = self._make_key(namespace, key)
        with self._lock:
            removed = self._secrets.pop(full_key, None) is not None
            if removed:
                self._audit("delete", namespace, key)
                self._save()
            return removed

    def has_secret(self, key: str, namespace: str = "default") -> bool:
        full_key = self._make_key(namespace, key)
        entry = self._secrets.get(full_key)
        if not entry:
            return False
        if entry.is_expired:
            with self._lock:
                self._secrets.pop(full_key, None)
                self._save()
            return False
        return True

    # ── Namespaces ──────────────────────────────────────────────────
    def list_namespaces(self) -> list[str]:
        with self._lock:
            return list(set(e.namespace for e in self._secrets.values()))

    def list_keys(self, namespace: str = "default") -> list[str]:
        with self._lock:
            return [
                e.key for e in self._secrets.values()
                if e.namespace == namespace and not e.is_expired
            ]

    def delete_namespace(self, namespace: str) -> int:
        with self._lock:
            keys_to_del = [k for k, v in self._secrets.items() if v.namespace == namespace]
            for k in keys_to_del:
                del self._secrets[k]
            if keys_to_del:
                self._audit("delete_namespace", namespace, f"{len(keys_to_del)} keys")
                self._save()
            return len(keys_to_del)

    # ── Rotation ────────────────────────────────────────────────────
    def rotate_secret(self, key: str, new_value: str, namespace: str = "default") -> bool:
        full_key = self._make_key(namespace, key)
        with self._lock:
            entry = self._secrets.get(full_key)
            if not entry:
                return False
            entry.value = self._encode(new_value)
            entry.updated_at = time.time()
            self._audit("rotate", namespace, key)
            self._save()
            return True

    # ── Audit ───────────────────────────────────────────────────────
    def _audit(self, action: str, namespace: str, key: str) -> None:
        self._access_log.append({
            "action": action, "namespace": namespace, "key": key,
            "timestamp": time.time(),
        })
        if len(self._access_log) > self._max_log:
            self._access_log = self._access_log[-self._max_log:]

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return self._access_log[-limit:]

    # ── Persistence ─────────────────────────────────────────────────
    def _save(self) -> None:
        if not self._store_path:
            return
        data = {}
        for fk, entry in self._secrets.items():
            data[fk] = {
                "key": entry.key, "value": entry.value,
                "namespace": entry.namespace, "ttl": entry.ttl,
                "created_at": entry.created_at, "updated_at": entry.updated_at,
                "access_count": entry.access_count,
            }
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        try:
            raw = json.loads(self._store_path.read_text())
            for fk, d in raw.items():
                self._secrets[fk] = SecretEntry(
                    key=d["key"], value=d["value"],
                    namespace=d["namespace"], ttl=d.get("ttl", 0),
                    created_at=d.get("created_at", time.time()),
                    updated_at=d.get("updated_at", time.time()),
                    access_count=d.get("access_count", 0),
                )
        except (json.JSONDecodeError, KeyError):
            pass

    # ── Stats ───────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._secrets)
            namespaces = set(e.namespace for e in self._secrets.values())
            expired = sum(1 for e in self._secrets.values() if e.is_expired)
            total_access = sum(e.access_count for e in self._secrets.values())
            return {
                "total_secrets": total,
                "namespaces": len(namespaces),
                "expired": expired,
                "total_access_count": total_access,
                "audit_entries": len(self._access_log),
            }


config_vault = ConfigVault()
