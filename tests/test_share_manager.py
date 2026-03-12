"""Tests for src/share_manager.py — Windows network share management.

Covers: ShareInfo, ShareEvent, ShareManager (list_shares, _list_shares_net,
list_mapped_drives, search_shares, get_events, get_stats),
share_manager singleton.
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

from src.share_manager import ShareInfo, ShareEvent, ShareManager, share_manager


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_share_info(self):
        s = ShareInfo(name="Public")
        assert s.path == ""
        assert s.share_type == ""

    def test_share_event(self):
        e = ShareEvent(action="list")
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# ShareManager — list_shares (mocked PowerShell)
# ===========================================================================

PS_SHARES_JSON = json.dumps([
    {"Name": "ADMIN$", "Path": "/\Windows", "Description": "Admin", "ShareType": 0},
    {"Name": "Public", "Path": "/\Users/Public", "Description": "Public folder", "ShareType": 0},
])


class TestListShares:
    def test_success(self):
        sm = ShareManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = PS_SHARES_JSON
        with patch("subprocess.run", return_value=mock_result):
            shares = sm.list_shares()
        assert len(shares) == 2
        assert shares[0]["name"] == "ADMIN$"
        assert shares[1]["name"] == "Public"

    def test_single_share_dict(self):
        sm = ShareManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"Name": "Solo", "Path": "/\Solo", "Description": "", "ShareType": 0})
        with patch("subprocess.run", return_value=mock_result):
            shares = sm.list_shares()
        assert len(shares) == 1

    def test_failure_falls_back_to_net(self):
        sm = ShareManager()
        with patch("subprocess.run", side_effect=Exception("ps fail")):
            with patch.object(sm, "_list_shares_net", return_value=[]) as mock_net:
                shares = sm.list_shares()
            mock_net.assert_called_once()
        assert shares == []


# ===========================================================================
# ShareManager — _list_shares_net (fallback)
# ===========================================================================

NET_SHARE_OUTPUT = """Share name   Resource                        Remark

-------------------------------------------------------------------------------
ADMIN$       /\Windows                       Remote Admin
C$           /\                              Default share
The command completed successfully.
"""


class TestListSharesNet:
    def test_parse(self):
        sm = ShareManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = NET_SHARE_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            shares = sm._list_shares_net()
        assert len(shares) >= 1

    def test_failure(self):
        sm = ShareManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            shares = sm._list_shares_net()
        assert shares == []


# ===========================================================================
# ShareManager — list_mapped_drives
# ===========================================================================

NET_USE_OUTPUT = """New connections will be remembered.

Status       Local     Remote                    Network
-------------------------------------------------------------------------------
OK           Z:        //server/share            Microsoft Windows Network
Disconnected Y:        //nas/backup              Microsoft Windows Network
The command completed successfully.
"""


class TestListMappedDrives:
    def test_success(self):
        sm = ShareManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = NET_USE_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            drives = sm.list_mapped_drives()
        assert len(drives) == 2
        assert drives[0]["drive"] == "Z:"
        assert drives[0]["status"] == "OK"
        assert drives[1]["status"] == "Disconnected"

    def test_failure(self):
        sm = ShareManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            drives = sm.list_mapped_drives()
        assert drives == []


# ===========================================================================
# ShareManager — search
# ===========================================================================

class TestSearch:
    def test_search(self):
        sm = ShareManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = PS_SHARES_JSON
        with patch("subprocess.run", return_value=mock_result):
            results = sm.search_shares("public")
        assert len(results) == 1
        assert results[0]["name"] == "Public"


# ===========================================================================
# ShareManager — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        sm = ShareManager()
        assert sm.get_events() == []

    def test_stats(self):
        sm = ShareManager()
        stats = sm.get_stats()
        assert stats["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert share_manager is not None
        assert isinstance(share_manager, ShareManager)
