"""Tests for src/retry_policy.py — Configurable retry strategies.

Covers: BackoffType, RetryPolicy (get_delay), RetryResult,
RetryPolicyManager (register, get, remove, list_policies, execute,
execute_no_wait, get_history, get_stats), retry_manager singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retry_policy import (
    BackoffType, RetryPolicy, RetryResult, RetryPolicyManager,
    retry_manager,
)


# ===========================================================================
# RetryPolicy
# ===========================================================================

class TestRetryPolicy:
    def test_defaults(self):
        p = RetryPolicy(name="test")
        assert p.max_attempts == 3
        assert p.backoff == BackoffType.EXPONENTIAL

    def test_get_delay_fixed(self):
        p = RetryPolicy(name="t", backoff=BackoffType.FIXED, base_delay=2.0, jitter=False)
        assert p.get_delay(1) == 2.0
        assert p.get_delay(5) == 2.0

    def test_get_delay_linear(self):
        p = RetryPolicy(name="t", backoff=BackoffType.LINEAR, base_delay=1.0, jitter=False)
        assert p.get_delay(1) == 1.0
        assert p.get_delay(3) == 3.0

    def test_get_delay_exponential(self):
        p = RetryPolicy(name="t", backoff=BackoffType.EXPONENTIAL, base_delay=1.0, jitter=False)
        assert p.get_delay(1) == 1.0
        assert p.get_delay(2) == 2.0
        assert p.get_delay(3) == 4.0

    def test_get_delay_max_cap(self):
        p = RetryPolicy(name="t", backoff=BackoffType.EXPONENTIAL,
                         base_delay=10.0, max_delay=15.0, jitter=False)
        assert p.get_delay(5) == 15.0

    def test_get_delay_jitter(self):
        p = RetryPolicy(name="t", backoff=BackoffType.FIXED, base_delay=2.0, jitter=True)
        delay = p.get_delay(1)
        assert 1.0 <= delay <= 2.0


# ===========================================================================
# RetryPolicyManager — policies
# ===========================================================================

class TestPolicyManagement:
    def test_default_policies_exist(self):
        rpm = RetryPolicyManager()
        assert rpm.get("default") is not None
        assert rpm.get("aggressive") is not None
        assert rpm.get("gentle") is not None

    def test_register(self):
        rpm = RetryPolicyManager()
        rpm.register("custom", max_attempts=10)
        p = rpm.get("custom")
        assert p is not None
        assert p.max_attempts == 10

    def test_remove(self):
        rpm = RetryPolicyManager()
        rpm.register("temp", max_attempts=1)
        assert rpm.remove("temp") is True
        assert rpm.get("temp") is None

    def test_remove_nonexistent(self):
        rpm = RetryPolicyManager()
        assert rpm.remove("nope") is False

    def test_list_policies(self):
        rpm = RetryPolicyManager()
        policies = rpm.list_policies()
        names = [p["name"] for p in policies]
        assert "default" in names


# ===========================================================================
# RetryPolicyManager — execute_no_wait
# ===========================================================================

class TestExecuteNoWait:
    def test_success_first_try(self):
        rpm = RetryPolicyManager()
        result = rpm.execute_no_wait(lambda: "ok")
        assert result.success is True
        assert result.result == "ok"
        assert result.attempts == 1

    def test_retries_then_succeeds(self):
        rpm = RetryPolicyManager()
        counter = {"n": 0}
        def flaky():
            counter["n"] += 1
            if counter["n"] < 3:
                raise ValueError("fail")
            return "ok"
        result = rpm.execute_no_wait(flaky)
        assert result.success is True
        assert result.attempts == 3

    def test_all_attempts_exhausted(self):
        rpm = RetryPolicyManager()
        def always_fail():
            raise ValueError("boom")
        result = rpm.execute_no_wait(always_fail)
        assert result.success is False
        assert result.last_error == "boom"

    def test_custom_policy(self):
        rpm = RetryPolicyManager()
        rpm.register("once", max_attempts=1)
        result = rpm.execute_no_wait(lambda: (_ for _ in ()).throw(ValueError("x")),
                                      policy_name="once")
        assert result.success is False
        assert result.attempts == 1


# ===========================================================================
# RetryPolicyManager — history & stats
# ===========================================================================

class TestHistoryStats:
    def test_history(self):
        rpm = RetryPolicyManager()
        rpm.execute_no_wait(lambda: "ok")
        history = rpm.get_history()
        assert len(history) == 1
        assert history[0]["success"] is True

    def test_stats(self):
        rpm = RetryPolicyManager()
        rpm.execute_no_wait(lambda: "ok")
        rpm.execute_no_wait(lambda: (_ for _ in ()).throw(ValueError("x")))
        stats = rpm.get_stats()
        assert stats["total_executions"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1

    def test_stats_empty(self):
        rpm = RetryPolicyManager()
        stats = rpm.get_stats()
        assert stats["total_executions"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert retry_manager is not None
        assert isinstance(retry_manager, RetryPolicyManager)
