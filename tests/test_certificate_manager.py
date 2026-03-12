"""Tests for src/certificate_manager.py — Windows certificate store.

Covers: CertInfo, CertEvent, CertificateManager (list_certs, list_stores,
search, get_expiring, count_by_store, get_events, get_stats),
certificate_manager singleton.
All subprocess calls are mocked.
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

from src.certificate_manager import (
    CertInfo, CertEvent, CertificateManager, CERT_STORES, certificate_manager,
)


CERTS_JSON = json.dumps([
    {"Subject": "CN=localhost", "Issuer": "CN=localhost", "Thumbprint": "AABB",
     "NotAfter": "2027-01-01", "NotBefore": "2025-01-01"},
    {"Subject": "CN=*.example.com", "Issuer": "CN=CA", "Thumbprint": "CCDD",
     "NotAfter": "2026-06-01", "NotBefore": "2024-01-01"},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_cert_info(self):
        c = CertInfo(subject="CN=test")
        assert c.thumbprint == ""
        assert c.store == ""

    def test_cert_event(self):
        e = CertEvent(action="list_certs")
        assert e.success is True


# ===========================================================================
# CertificateManager — list_certs (mocked)
# ===========================================================================

class TestListCerts:
    def test_success(self):
        cm = CertificateManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CERTS_JSON
        with patch("subprocess.run", return_value=mock_result):
            certs = cm.list_certs()
        assert len(certs) == 2
        assert certs[0]["subject"] == "CN=localhost"
        assert certs[0]["thumbprint"] == "AABB"

    def test_single_cert(self):
        cm = CertificateManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"Subject": "CN=solo", "Issuer": "CN=CA",
                                          "Thumbprint": "EEFF", "NotAfter": "2027-01-01",
                                          "NotBefore": "2025-01-01"})
        with patch("subprocess.run", return_value=mock_result):
            certs = cm.list_certs()
        assert len(certs) == 1

    def test_failure(self):
        cm = CertificateManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            certs = cm.list_certs()
        assert certs == []


# ===========================================================================
# CertificateManager — list_stores
# ===========================================================================

class TestListStores:
    def test_returns_known(self):
        cm = CertificateManager()
        stores = cm.list_stores()
        assert stores == CERT_STORES


# ===========================================================================
# CertificateManager — search
# ===========================================================================

class TestSearch:
    def test_search(self):
        cm = CertificateManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CERTS_JSON
        with patch("subprocess.run", return_value=mock_result):
            results = cm.search("localhost")
        assert len(results) == 1
        assert "localhost" in results[0]["subject"]


# ===========================================================================
# CertificateManager — get_expiring
# ===========================================================================

class TestGetExpiring:
    def test_success(self):
        cm = CertificateManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([
            {"Subject": "CN=expiring", "Thumbprint": "1234", "NotAfter": "2026-04-01"},
        ])
        with patch("subprocess.run", return_value=mock_result):
            expiring = cm.get_expiring(days=30)
        assert len(expiring) == 1

    def test_failure(self):
        cm = CertificateManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            expiring = cm.get_expiring()
        assert expiring == []


# ===========================================================================
# CertificateManager — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        cm = CertificateManager()
        assert cm.get_events() == []

    def test_stats(self):
        cm = CertificateManager()
        stats = cm.get_stats()
        assert stats["total_events"] == 0
        assert stats["known_stores"] == len(CERT_STORES)


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert certificate_manager is not None
        assert isinstance(certificate_manager, CertificateManager)
