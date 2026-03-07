"""Tests for src/permission_manager.py — Role-Based Access Control.

Covers: Role, User, PermissionManager (create_role, delete_role,
add_permission, remove_permission, assign_role, revoke_role,
check_permission, get_user_permissions, list_roles, list_users, get_stats),
permission_manager singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.permission_manager import Role, User, PermissionManager, permission_manager


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_role(self):
        r = Role(name="test")
        assert r.permissions == set()

    def test_user(self):
        u = User(user_id="u1")
        assert u.roles == set()


# ===========================================================================
# PermissionManager — default roles
# ===========================================================================

class TestDefaults:
    def test_has_default_roles(self):
        pm = PermissionManager()
        roles = {r["name"] for r in pm.list_roles()}
        assert "admin" in roles
        assert "operator" in roles
        assert "viewer" in roles


# ===========================================================================
# PermissionManager — create/delete role
# ===========================================================================

class TestRoles:
    def test_create_role(self):
        pm = PermissionManager()
        role = pm.create_role("custom", {"read", "write"}, "Custom role")
        assert role.name == "custom"
        assert "read" in role.permissions

    def test_delete_role(self):
        pm = PermissionManager()
        pm.create_role("temp")
        assert pm.delete_role("temp") is True
        assert pm.delete_role("temp") is False

    def test_add_permission(self):
        pm = PermissionManager()
        pm.create_role("test")
        assert pm.add_permission("test", "new_perm") is True
        assert pm.add_permission("nonexistent", "perm") is False

    def test_remove_permission(self):
        pm = PermissionManager()
        pm.create_role("test", {"perm1", "perm2"})
        assert pm.remove_permission("test", "perm1") is True
        assert pm.remove_permission("nonexistent", "perm1") is False


# ===========================================================================
# PermissionManager — assign/revoke role
# ===========================================================================

class TestAssignRevoke:
    def test_assign_role(self):
        pm = PermissionManager()
        assert pm.assign_role("user1", "admin") is True
        users = pm.list_users()
        assert any(u["user_id"] == "user1" for u in users)

    def test_assign_nonexistent_role(self):
        pm = PermissionManager()
        assert pm.assign_role("user1", "nonexistent") is False

    def test_revoke_role(self):
        pm = PermissionManager()
        pm.assign_role("user1", "admin")
        assert pm.revoke_role("user1", "admin") is True

    def test_revoke_nonexistent_user(self):
        pm = PermissionManager()
        assert pm.revoke_role("nobody", "admin") is False


# ===========================================================================
# PermissionManager — check_permission
# ===========================================================================

class TestCheckPermission:
    def test_admin_has_all(self):
        pm = PermissionManager()
        pm.assign_role("admin_user", "admin")
        assert pm.check_permission("admin_user", "anything") is True

    def test_operator_has_cluster(self):
        pm = PermissionManager()
        pm.assign_role("op", "operator")
        assert pm.check_permission("op", "cluster.read") is True
        assert pm.check_permission("op", "admin.delete") is False

    def test_unknown_user(self):
        pm = PermissionManager()
        assert pm.check_permission("nobody", "read") is False

    def test_viewer_limited(self):
        pm = PermissionManager()
        pm.assign_role("viewer1", "viewer")
        assert pm.check_permission("viewer1", "cluster.read") is True
        assert pm.check_permission("viewer1", "cluster.write") is False


# ===========================================================================
# PermissionManager — get_user_permissions
# ===========================================================================

class TestGetPermissions:
    def test_permissions(self):
        pm = PermissionManager()
        pm.assign_role("user1", "viewer")
        perms = pm.get_user_permissions("user1")
        assert "cluster.read" in perms

    def test_unknown_user(self):
        pm = PermissionManager()
        assert pm.get_user_permissions("nobody") == set()

    def test_multi_role(self):
        pm = PermissionManager()
        pm.assign_role("user1", "viewer")
        pm.assign_role("user1", "operator")
        perms = pm.get_user_permissions("user1")
        assert "cluster.write" in perms  # from operator
        assert "metrics.read" in perms   # from viewer


# ===========================================================================
# PermissionManager — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        pm = PermissionManager()
        pm.assign_role("user1", "admin")
        pm.check_permission("user1", "test")
        pm.check_permission("nobody", "test")
        stats = pm.get_stats()
        assert stats["total_roles"] >= 3
        assert stats["total_users"] == 1
        assert stats["check_count"] == 2
        assert stats["denied_count"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert permission_manager is not None
        assert isinstance(permission_manager, PermissionManager)
