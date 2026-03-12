"""Tests for src/user_account_manager.py — Windows user accounts.

Covers: UserAccount, UserEvent, UserAccountManager (list_users, list_groups,
search_users, count_by_status, get_events, get_stats),
user_account_manager singleton. All subprocess calls are mocked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.user_account_manager import (
    UserAccount, UserEvent, UserAccountManager, user_account_manager,
)

USERS_JSON = json.dumps([
    {"Name": "franc", "Enabled": True, "FullName": "Franc",
     "Description": "Admin", "SID": {"Value": "S-1-5-21-123"}, "LastLogon": "2026-03-06"},
    {"Name": "Guest", "Enabled": False, "FullName": "",
     "Description": "Guest account", "SID": "S-1-5-21-456", "LastLogon": None},
])

GROUPS_JSON = json.dumps([
    {"Name": "Administrators", "Description": "Admin group",
     "SID": {"Value": "S-1-5-32-544"}},
    {"Name": "Users", "Description": "Users", "SID": "S-1-5-32-545"},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_user_account(self):
        u = UserAccount(name="test")
        assert u.enabled is True

    def test_user_event(self):
        e = UserEvent(action="list_users")
        assert e.success is True


# ===========================================================================
# UserAccountManager — list_users
# ===========================================================================

class TestListUsers:
    def test_success(self):
        uam = UserAccountManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = USERS_JSON
        with patch("subprocess.run", return_value=mock_result):
            users = uam.list_users()
        assert len(users) == 2
        assert users[0]["name"] == "franc"
        assert users[0]["sid"] == "S-1-5-21-123"
        assert users[1]["enabled"] is False

    def test_failure(self):
        uam = UserAccountManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            users = uam.list_users()
        assert users == []


# ===========================================================================
# UserAccountManager — list_groups
# ===========================================================================

class TestListGroups:
    def test_success(self):
        uam = UserAccountManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = GROUPS_JSON
        with patch("subprocess.run", return_value=mock_result):
            groups = uam.list_groups()
        assert len(groups) == 2
        assert groups[0]["name"] == "Administrators"

    def test_failure(self):
        uam = UserAccountManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            groups = uam.list_groups()
        assert groups == []


# ===========================================================================
# UserAccountManager — search & count
# ===========================================================================

class TestSearchCount:
    def test_search(self):
        uam = UserAccountManager()
        fake_users = [{"name": "franc"}, {"name": "Guest"}]
        with patch.object(uam, "list_users", return_value=fake_users):
            results = uam.search_users("franc")
        assert len(results) == 1

    def test_count_by_status(self):
        uam = UserAccountManager()
        fake_users = [{"enabled": True}, {"enabled": True}, {"enabled": False}]
        with patch.object(uam, "list_users", return_value=fake_users):
            counts = uam.count_by_status()
        assert counts["enabled"] == 2
        assert counts["disabled"] == 1


# ===========================================================================
# Events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        uam = UserAccountManager()
        assert uam.get_events() == []

    def test_stats(self):
        uam = UserAccountManager()
        assert uam.get_stats()["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert user_account_manager is not None
        assert isinstance(user_account_manager, UserAccountManager)
