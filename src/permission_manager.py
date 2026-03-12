"""Permission Manager — Role-Based Access Control.

RBAC system for cluster access: roles, permissions,
user assignments, check_permission(). Thread-safe.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any


__all__ = [
    "PermissionManager",
    "Role",
    "User",
]

logger = logging.getLogger("jarvis.permission_manager")


@dataclass
class Role:
    name: str
    permissions: set[str] = field(default_factory=set)
    description: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class User:
    user_id: str
    roles: set[str] = field(default_factory=set)
    metadata: dict = field(default_factory=dict)


class PermissionManager:
    """RBAC permission system."""

    def __init__(self):
        self._roles: dict[str, Role] = {}
        self._users: dict[str, User] = {}
        self._lock = threading.Lock()
        self._check_count = 0
        self._denied_count = 0

        # Default roles
        self.create_role("admin", {"*"}, "Full access")
        self.create_role("operator", {
            "cluster.read", "cluster.write", "models.read", "models.load",
            "trading.read", "trading.execute", "voice.use",
        }, "Cluster operator")
        self.create_role("viewer", {
            "cluster.read", "models.read", "trading.read", "metrics.read",
        }, "Read-only access")

    def create_role(self, name: str, permissions: set[str] | None = None, description: str = "") -> Role:
        with self._lock:
            role = Role(name=name, permissions=permissions or set(), description=description)
            self._roles[name] = role
            return role

    def delete_role(self, name: str) -> bool:
        with self._lock:
            return self._roles.pop(name, None) is not None

    def add_permission(self, role_name: str, permission: str) -> bool:
        with self._lock:
            role = self._roles.get(role_name)
            if not role:
                return False
            role.permissions.add(permission)
            return True

    def remove_permission(self, role_name: str, permission: str) -> bool:
        with self._lock:
            role = self._roles.get(role_name)
            if not role:
                return False
            role.permissions.discard(permission)
            return True

    def assign_role(self, user_id: str, role_name: str) -> bool:
        with self._lock:
            if role_name not in self._roles:
                return False
            if user_id not in self._users:
                self._users[user_id] = User(user_id=user_id)
            self._users[user_id].roles.add(role_name)
            return True

    def revoke_role(self, user_id: str, role_name: str) -> bool:
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                return False
            user.roles.discard(role_name)
            return True

    def check_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has the given permission (via any assigned role)."""
        with self._lock:
            self._check_count += 1
            user = self._users.get(user_id)
            if not user:
                self._denied_count += 1
                return False
            for role_name in user.roles:
                role = self._roles.get(role_name)
                if role:
                    if "*" in role.permissions or permission in role.permissions:
                        return True
            self._denied_count += 1
            return False

    def get_user_permissions(self, user_id: str) -> set[str]:
        user = self._users.get(user_id)
        if not user:
            return set()
        perms = set()
        for role_name in user.roles:
            role = self._roles.get(role_name)
            if role:
                perms |= role.permissions
        return perms

    def list_roles(self) -> list[dict]:
        return [
            {"name": r.name, "permissions": sorted(r.permissions),
             "description": r.description}
            for r in self._roles.values()
        ]

    def list_users(self) -> list[dict]:
        return [
            {"user_id": u.user_id, "roles": sorted(u.roles)}
            for u in self._users.values()
        ]

    def get_stats(self) -> dict:
        return {
            "total_roles": len(self._roles),
            "total_users": len(self._users),
            "check_count": self._check_count,
            "denied_count": self._denied_count,
        }


# ── Singleton ────────────────────────────────────────────────────────────────
permission_manager = PermissionManager()
