"""Tests for src/local_security_policy.py — Windows security policy reader.

Covers: SecuritySetting, SecPolEvent, LocalSecurityPolicy (export_policy,
get_password_policy, get_audit_policy, get_sections, get_events, get_stats),
local_security_policy singleton.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.local_security_policy import (
    SecuritySetting, SecPolEvent, LocalSecurityPolicy, local_security_policy,
)

POLICY_CONTENT = """\
[System Access]
MinimumPasswordAge = 0
MaximumPasswordAge = 42
MinimumPasswordLength = 8
PasswordComplexity = 1

[Event Audit]
AuditLogonEvents = 3
AuditObjectAccess = 0

[Registry Values]
MACHINE\\Software\\Policies = 4,1
"""


class TestDataclasses:
    def test_security_setting(self):
        s = SecuritySetting(section="System Access", key="MinPwdLen")
        assert s.value == ""

    def test_sec_pol_event(self):
        e = SecPolEvent(action="export_policy")
        assert e.success is True


class TestExportPolicy:
    def test_success(self, tmp_path):
        lsp = LocalSecurityPolicy()
        inf_file = tmp_path / "policy.inf"
        inf_path = str(inf_file)

        def fake_run(cmd, **kwargs):
            # Write policy file as secedit would (utf-16-le like real secedit)
            inf_file.write_text(POLICY_CONTENT, encoding="utf-16-le")
            mock = MagicMock()
            mock.returncode = 0
            return mock

        # Mock NamedTemporaryFile in the module where it's used
        with patch("subprocess.run", side_effect=fake_run), \
             patch("src.local_security_policy.tempfile") as mock_tf:
            ctx = MagicMock()
            ctx.__enter__ = lambda s: s
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.name = inf_path
            mock_tf.NamedTemporaryFile.return_value = ctx

            policy = lsp.export_policy()

        assert "System Access" in policy
        assert policy["System Access"]["MinimumPasswordLength"] == "8"
        assert "Event Audit" in policy
        assert policy["Event Audit"]["AuditLogonEvents"] == "3"

    def test_failure(self):
        lsp = LocalSecurityPolicy()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert lsp.export_policy() == {}


class TestPasswordPolicy:
    def test_get_password_policy(self):
        lsp = LocalSecurityPolicy()
        fake_policy = {"System Access": {"MinimumPasswordLength": "8"}}
        with patch.object(lsp, "export_policy", return_value=fake_policy):
            pp = lsp.get_password_policy()
        assert pp["MinimumPasswordLength"] == "8"

    def test_no_section(self):
        lsp = LocalSecurityPolicy()
        with patch.object(lsp, "export_policy", return_value={}):
            assert lsp.get_password_policy() == {}


class TestAuditPolicy:
    def test_get_audit_policy(self):
        lsp = LocalSecurityPolicy()
        fake_policy = {"Event Audit": {"AuditLogonEvents": "3"}}
        with patch.object(lsp, "export_policy", return_value=fake_policy):
            ap = lsp.get_audit_policy()
        assert ap["AuditLogonEvents"] == "3"


class TestGetSections:
    def test_sections(self):
        lsp = LocalSecurityPolicy()
        fake_policy = {"System Access": {}, "Event Audit": {}}
        with patch.object(lsp, "export_policy", return_value=fake_policy):
            sections = lsp.get_sections()
        assert "System Access" in sections
        assert "Event Audit" in sections


class TestEventsStats:
    def test_events_empty(self):
        assert LocalSecurityPolicy().get_events() == []

    def test_stats(self):
        assert LocalSecurityPolicy().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(local_security_policy, LocalSecurityPolicy)
