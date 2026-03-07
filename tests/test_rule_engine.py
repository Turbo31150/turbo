"""Tests for src/rule_engine.py — Condition-based rule evaluation.

Covers: Rule, RuleEngine (add_rule, remove_rule, enable_rule, disable_rule,
get_rule, list_rules, list_groups, evaluate, evaluate_first,
get_evaluation_log, get_stats), rule_engine singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rule_engine import Rule, RuleEngine, rule_engine


# ===========================================================================
# Rule dataclass
# ===========================================================================

class TestRule:
    def test_defaults(self):
        r = Rule(name="test", condition=lambda c: True, action=lambda c: "ok")
        assert r.priority == 0
        assert r.group == "default"
        assert r.enabled is True
        assert r.fire_count == 0


# ===========================================================================
# RuleEngine — add/remove/enable/disable
# ===========================================================================

class TestManagement:
    def test_add_rule(self):
        re = RuleEngine()
        rule = re.add_rule("r1", condition=lambda c: True, action=lambda c: "ok")
        assert rule.name == "r1"
        assert re.get_rule("r1") is not None

    def test_remove_rule(self):
        re = RuleEngine()
        re.add_rule("r1", condition=lambda c: True, action=lambda c: None)
        assert re.remove_rule("r1") is True
        assert re.remove_rule("r1") is False

    def test_enable_disable(self):
        re = RuleEngine()
        re.add_rule("r1", condition=lambda c: True, action=lambda c: None)
        assert re.disable_rule("r1") is True
        assert re.get_rule("r1").enabled is False
        assert re.enable_rule("r1") is True
        assert re.get_rule("r1").enabled is True

    def test_enable_nonexistent(self):
        re = RuleEngine()
        assert re.enable_rule("nope") is False
        assert re.disable_rule("nope") is False

    def test_list_rules(self):
        re = RuleEngine()
        re.add_rule("a", condition=lambda c: True, action=lambda c: None, priority=5)
        re.add_rule("b", condition=lambda c: True, action=lambda c: None, priority=10)
        rules = re.list_rules()
        assert len(rules) == 2
        assert rules[0]["name"] == "b"  # higher priority first

    def test_list_rules_by_group(self):
        re = RuleEngine()
        re.add_rule("a", condition=lambda c: True, action=lambda c: None, group="alerts")
        re.add_rule("b", condition=lambda c: True, action=lambda c: None, group="system")
        rules = re.list_rules(group="alerts")
        assert len(rules) == 1
        assert rules[0]["name"] == "a"

    def test_list_groups(self):
        re = RuleEngine()
        re.add_rule("a", condition=lambda c: True, action=lambda c: None, group="g1")
        re.add_rule("b", condition=lambda c: True, action=lambda c: None, group="g2")
        groups = re.list_groups()
        assert "g1" in groups
        assert "g2" in groups


# ===========================================================================
# RuleEngine — evaluate
# ===========================================================================

class TestEvaluate:
    def test_matching_rule(self):
        re = RuleEngine()
        re.add_rule("high_cpu",
                     condition=lambda c: c.get("cpu", 0) > 90,
                     action=lambda c: "alert")
        results = re.evaluate({"cpu": 95})
        assert len(results) == 1
        assert results[0]["fired"] is True
        assert results[0]["result"] == "alert"

    def test_no_match(self):
        re = RuleEngine()
        re.add_rule("high_cpu",
                     condition=lambda c: c.get("cpu", 0) > 90,
                     action=lambda c: "alert")
        results = re.evaluate({"cpu": 50})
        assert len(results) == 0

    def test_disabled_rule_skipped(self):
        re = RuleEngine()
        re.add_rule("r1", condition=lambda c: True, action=lambda c: "fired")
        re.disable_rule("r1")
        results = re.evaluate({})
        assert len(results) == 0

    def test_first_match(self):
        re = RuleEngine()
        re.add_rule("a", condition=lambda c: True, action=lambda c: "a", priority=10)
        re.add_rule("b", condition=lambda c: True, action=lambda c: "b", priority=5)
        results = re.evaluate({}, first_match=True)
        assert len(results) == 1
        assert results[0]["rule"] == "a"

    def test_exception_in_rule(self):
        re = RuleEngine()
        re.add_rule("bad", condition=lambda c: True,
                     action=lambda c: 1/0)
        results = re.evaluate({})
        assert len(results) == 1
        assert results[0]["fired"] is False
        assert "error" in results[0]

    def test_group_filter(self):
        re = RuleEngine()
        re.add_rule("a", condition=lambda c: True, action=lambda c: "a", group="g1")
        re.add_rule("b", condition=lambda c: True, action=lambda c: "b", group="g2")
        results = re.evaluate({}, group="g1")
        assert len(results) == 1
        assert results[0]["rule"] == "a"

    def test_fire_count_incremented(self):
        re = RuleEngine()
        re.add_rule("counter", condition=lambda c: True, action=lambda c: "ok")
        re.evaluate({})
        re.evaluate({})
        rule = re.get_rule("counter")
        assert rule.fire_count == 2


# ===========================================================================
# RuleEngine — evaluate_first
# ===========================================================================

class TestEvaluateFirst:
    def test_returns_first(self):
        re = RuleEngine()
        re.add_rule("a", condition=lambda c: True, action=lambda c: "first")
        result = re.evaluate_first({})
        assert result is not None
        assert result["result"] == "first"

    def test_returns_none(self):
        re = RuleEngine()
        re.add_rule("a", condition=lambda c: False, action=lambda c: "nope")
        result = re.evaluate_first({})
        assert result is None


# ===========================================================================
# RuleEngine — log & stats
# ===========================================================================

class TestLogStats:
    def test_log_empty(self):
        re = RuleEngine()
        assert re.get_evaluation_log() == []

    def test_log_after_eval(self):
        re = RuleEngine()
        re.add_rule("r1", condition=lambda c: True, action=lambda c: None)
        re.evaluate({})
        log = re.get_evaluation_log()
        assert len(log) == 1
        assert log[0]["rule"] == "r1"

    def test_stats(self):
        re = RuleEngine()
        re.add_rule("a", condition=lambda c: True, action=lambda c: None)
        re.add_rule("b", condition=lambda c: True, action=lambda c: None)
        re.disable_rule("b")
        stats = re.get_stats()
        assert stats["total_rules"] == 2
        assert stats["enabled"] == 1
        assert stats["disabled"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert rule_engine is not None
        assert isinstance(rule_engine, RuleEngine)
