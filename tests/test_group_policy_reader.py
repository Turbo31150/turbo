"""Tests for src/group_policy_reader.py — Windows GPO reading.

Covers: GPOInfo, GPOEvent, GroupPolicyReader (get_rsop, get_raw,
get_applied_gpos, _parse_gpresult, get_events, get_stats),
group_policy_reader singleton.
All subprocess calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.group_policy_reader import (
    GPOInfo, GPOEvent, GroupPolicyReader, group_policy_reader,
)


GPRESULT_OUTPUT = """
Microsoft (R) Windows (R) Operating System Group Policy Result tool v2.0

Computer name: DESKTOP-123
Domain name: WORKGROUP
Site name: N/A

COMPUTER SETTINGS
-----------------

Applied Group Policy Objects
    Default Domain Policy
    Local Group Policy

SOFTWARE SETTINGS
"""


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_gpo_info(self):
        g = GPOInfo(name="Default Policy")
        assert g.link_location == ""

    def test_gpo_event(self):
        e = GPOEvent(action="get_rsop")
        assert e.success is True


# ===========================================================================
# GroupPolicyReader — _parse_gpresult
# ===========================================================================

class TestParser:
    def test_parse_computer_name(self):
        gpr = GroupPolicyReader()
        result = gpr._parse_gpresult(GPRESULT_OUTPUT)
        assert result["computer_name"] == "DESKTOP-123"

    def test_parse_domain(self):
        gpr = GroupPolicyReader()
        result = gpr._parse_gpresult(GPRESULT_OUTPUT)
        assert result["domain"] == "WORKGROUP"

    def test_parse_applied_gpos(self):
        gpr = GroupPolicyReader()
        result = gpr._parse_gpresult(GPRESULT_OUTPUT)
        gpo_names = [g["name"] for g in result["applied_gpos"]]
        assert "Default Domain Policy" in gpo_names
        assert "Local Group Policy" in gpo_names

    def test_parse_empty(self):
        gpr = GroupPolicyReader()
        result = gpr._parse_gpresult("")
        assert result["computer_name"] == ""
        assert result["applied_gpos"] == []


# ===========================================================================
# GroupPolicyReader — get_rsop (mocked)
# ===========================================================================

class TestGetRsop:
    def test_success(self):
        gpr = GroupPolicyReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = GPRESULT_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            rsop = gpr.get_rsop()
        assert rsop["computer_name"] == "DESKTOP-123"
        assert len(rsop["applied_gpos"]) >= 2

    def test_failure(self):
        gpr = GroupPolicyReader()
        with patch("subprocess.run", side_effect=Exception("fail")):
            rsop = gpr.get_rsop()
        assert "error" in rsop


# ===========================================================================
# GroupPolicyReader — get_raw
# ===========================================================================

class TestGetRaw:
    def test_get_raw_after_rsop(self):
        gpr = GroupPolicyReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = GPRESULT_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            gpr.get_rsop()
        raw = gpr.get_raw()
        assert "DESKTOP-123" in raw


# ===========================================================================
# GroupPolicyReader — get_applied_gpos
# ===========================================================================

class TestGetApplied:
    def test_get_applied(self):
        gpr = GroupPolicyReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = GPRESULT_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            gpos = gpr.get_applied_gpos()
        assert len(gpos) >= 2


# ===========================================================================
# GroupPolicyReader — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        gpr = GroupPolicyReader()
        assert gpr.get_events() == []

    def test_stats(self):
        gpr = GroupPolicyReader()
        stats = gpr.get_stats()
        assert stats["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert group_policy_reader is not None
        assert isinstance(group_policy_reader, GroupPolicyReader)
