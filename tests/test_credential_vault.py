"""Tests for src/credential_vault.py — Windows Credential Manager.

Covers: CredentialEntry, VaultEvent, CredentialVault (list_credentials,
_parse_cmdkey, search, count_by_type, has_credential, get_events, get_stats),
credential_vault singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.credential_vault import (
    CredentialEntry, VaultEvent, CredentialVault, credential_vault,
)

CMDKEY_OUTPUT = """\
Currently stored credentials:

    Target: TERMSRV/server1
    Type: Domain Password
    User: DOMAIN/admin
    Persistence: Enterprise

    Target: git:https://github.com
    Type: Generic
    User: user@mail.com
    Persistence: Local Machine
"""


class TestDataclasses:
    def test_credential_entry(self):
        c = CredentialEntry(target="test")
        assert c.cred_type == ""

    def test_vault_event(self):
        e = VaultEvent(action="list")
        assert e.success is True


class TestParseCmdkey:
    def test_parse(self):
        cv = CredentialVault()
        creds = cv._parse_cmdkey(CMDKEY_OUTPUT)
        assert len(creds) == 2
        assert creds[0]["target"] == "TERMSRV/server1"
        assert creds[0]["type"] == "Domain Password"
        assert creds[1]["user"] == "user@mail.com"

    def test_parse_empty(self):
        cv = CredentialVault()
        assert cv._parse_cmdkey("") == []


class TestListCredentials:
    def test_success(self):
        cv = CredentialVault()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CMDKEY_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            creds = cv.list_credentials()
        assert len(creds) == 2

    def test_failure(self):
        cv = CredentialVault()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert cv.list_credentials() == []


class TestSearch:
    def test_search(self):
        cv = CredentialVault()
        fake = [{"target": "TERMSRV/server1"}, {"target": "git:github.com"}]
        with patch.object(cv, "list_credentials", return_value=fake):
            assert len(cv.search("github")) == 1

    def test_has_credential(self):
        cv = CredentialVault()
        fake = [{"target": "git:github.com"}]
        with patch.object(cv, "list_credentials", return_value=fake):
            assert cv.has_credential("github") is True
            assert cv.has_credential("nope") is False


class TestCountByType:
    def test_count(self):
        cv = CredentialVault()
        fake = [{"type": "Generic"}, {"type": "Generic"}, {"type": "Domain Password"}]
        with patch.object(cv, "list_credentials", return_value=fake):
            counts = cv.count_by_type()
        assert counts["Generic"] == 2


class TestEventsStats:
    def test_events_empty(self):
        assert CredentialVault().get_events() == []

    def test_stats(self):
        assert CredentialVault().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(credential_vault, CredentialVault)
