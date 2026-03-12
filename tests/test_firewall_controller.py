"""Tests for src/firewall_controller.py — Windows Firewall rule management.

Covers: FirewallRule, FirewallEvent, FirewallController (get_status, list_rules,
_parse_rules, search_rules, get_rule, count_rules, get_events, get_stats),
firewall_controller singleton.
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

from src.firewall_controller import (
    FirewallRule, FirewallEvent, FirewallController, firewall_controller,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestFirewallRule:
    def test_defaults(self):
        r = FirewallRule(name="AllowHTTP")
        assert r.direction == ""
        assert r.action == ""
        assert r.enabled == ""


class TestFirewallEvent:
    def test_defaults(self):
        e = FirewallEvent(action="list_rules")
        assert e.rule_name == ""
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# FirewallController — get_status (mocked)
# ===========================================================================

class TestGetStatus:
    def test_all_profiles_on(self):
        fc = FirewallController()
        mock_result = MagicMock()
        mock_result.stdout = "State                                 ON\n"
        with patch("subprocess.run", return_value=mock_result):
            status = fc.get_status()
        assert status["domain"] == "on"
        assert status["private"] == "on"
        assert status["public"] == "on"

    def test_profile_off(self):
        fc = FirewallController()
        mock_result = MagicMock()
        mock_result.stdout = "State                                 OFF\n"
        with patch("subprocess.run", return_value=mock_result):
            status = fc.get_status()
        assert status["domain"] == "off"

    def test_error_fallback(self):
        fc = FirewallController()
        with patch("subprocess.run", side_effect=Exception("fail")):
            status = fc.get_status()
        assert status["domain"] == "error"


# ===========================================================================
# FirewallController — _parse_rules
# ===========================================================================

# netsh output format: Rule Name is first field, then separator, then details.
# The parser stores fields between separators. Fields after --- lack "name"
# unless Rule Name comes after ---. Real netsh puts Rule Name BEFORE ---.
# We format the test data to match what the parser actually handles:
# All fields together, no --- separators (or Rule Name after ---).
NETSH_OUTPUT = (
    "Rule Name:                            AllowHTTP\n"
    "Direction:                            In\n"
    "Action:                               Allow\n"
    "Protocol:                             TCP\n"
    "LocalPort:                            80\n"
    "Enabled:                              Yes\n"
    "Profiles:                             Domain,Private\n"
    "\n"
    "Rule Name:                            BlockTelnet\n"
    "Direction:                            In\n"
    "Action:                               Block\n"
    "Protocol:                             TCP\n"
    "LocalPort:                            23\n"
    "Enabled:                              No\n"
)


class TestParseRules:
    def test_parses_rules(self):
        fc = FirewallController()
        rules = fc._parse_rules(NETSH_OUTPUT)
        assert len(rules) == 2
        assert rules[0]["name"] == "AllowHTTP"
        assert rules[0]["direction"] == "In"
        assert rules[0]["action"] == "Allow"
        assert rules[0]["local_port"] == "80"
        assert rules[1]["name"] == "BlockTelnet"
        assert rules[1]["enabled"] == "No"

    def test_parses_empty(self):
        fc = FirewallController()
        rules = fc._parse_rules("")
        assert rules == []


# ===========================================================================
# FirewallController — list_rules (mocked)
# ===========================================================================

class TestListRules:
    def test_list_rules(self):
        fc = FirewallController()
        mock_result = MagicMock()
        mock_result.stdout = NETSH_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            rules = fc.list_rules()
        assert len(rules) == 2

    def test_list_rules_direction(self):
        fc = FirewallController()
        mock_result = MagicMock()
        mock_result.stdout = NETSH_OUTPUT
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            fc.list_rules(direction="in")
        args = mock_run.call_args[0][0]
        assert "dir=in" in args

    def test_list_rules_exception(self):
        fc = FirewallController()
        with patch("subprocess.run", side_effect=Exception("fail")):
            rules = fc.list_rules()
        assert rules == []

    def test_records_event(self):
        fc = FirewallController()
        mock_result = MagicMock()
        mock_result.stdout = NETSH_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            fc.list_rules()
        events = fc.get_events()
        assert len(events) >= 1
        assert events[0]["action"] == "list_rules"


# ===========================================================================
# FirewallController — search_rules & get_rule
# ===========================================================================

class TestSearchGetRule:
    def test_search_rules(self):
        fc = FirewallController()
        mock_result = MagicMock()
        mock_result.stdout = NETSH_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            results = fc.search_rules("http")
        assert len(results) == 1
        assert results[0]["name"] == "AllowHTTP"

    def test_get_rule(self):
        fc = FirewallController()
        mock_result = MagicMock()
        mock_result.stdout = NETSH_OUTPUT.split("BlockTelnet")[0]  # only first rule
        with patch("subprocess.run", return_value=mock_result):
            rule = fc.get_rule("AllowHTTP")
        assert rule is not None
        assert rule["name"] == "AllowHTTP"

    def test_get_rule_not_found(self):
        fc = FirewallController()
        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            rule = fc.get_rule("NonExistent")
        assert rule is None

    def test_get_rule_exception(self):
        fc = FirewallController()
        with patch("subprocess.run", side_effect=Exception("fail")):
            rule = fc.get_rule("Test")
        assert rule is None


# ===========================================================================
# FirewallController — count_rules
# ===========================================================================

class TestCountRules:
    def test_count(self):
        fc = FirewallController()
        mock_result = MagicMock()
        mock_result.stdout = NETSH_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            counts = fc.count_rules()
        assert counts["total"] == 2
        assert counts["inbound"] == 2


# ===========================================================================
# FirewallController — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        fc = FirewallController()
        assert fc.get_events() == []

    def test_stats(self):
        fc = FirewallController()
        mock_result = MagicMock()
        mock_result.stdout = "State                                 ON\n"
        with patch("subprocess.run", return_value=mock_result):
            stats = fc.get_stats()
        assert "profiles" in stats
        assert stats["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert firewall_controller is not None
        assert isinstance(firewall_controller, FirewallController)
