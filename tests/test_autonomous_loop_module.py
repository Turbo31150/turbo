"""Tests for src.autonomous_loop — AutonomousLoop, CronSchedule, AutonomousTask.

Focuses on methods NOT covered by tests/test_phase4.py:
- start/stop lifecycle
- _run_loop due-task selection and exception gathering
- dynamic_register with event_bus emission
- _run_task timeout and alert paths
- CronSchedule minute filter and combined filters
- get_status task-level detail
- get_events with limit
- edge cases for enable/unregister on missing tasks
- _log_event structure
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.autonomous_loop import AutonomousLoop, AutonomousTask, CronSchedule


# ---------------------------------------------------------------------------
# CronSchedule tests (minute filter, combined filters)
# ---------------------------------------------------------------------------

class TestCronScheduleMinute:
    """CronSchedule.matches_now — minute and combined filters."""

    def test_minute_matches_current(self):
        now_minute = datetime.now().minute
        c = CronSchedule(minute=now_minute)
        assert c.matches_now()

    def test_minute_does_not_match(self):
        now_minute = datetime.now().minute
        c = CronSchedule(minute=(now_minute + 1) % 60)
        assert not c.matches_now()

    def test_combined_hour_minute_weekday_match(self):
        now = datetime.now()
        c = CronSchedule(hour=now.hour, minute=now.minute, weekdays=[now.weekday()])
        assert c.matches_now()

    def test_combined_hour_matches_minute_no(self):
        now = datetime.now()
        c = CronSchedule(hour=now.hour, minute=(now.minute + 1) % 60)
        assert not c.matches_now()


# ---------------------------------------------------------------------------
# AutonomousTask dataclass
# ---------------------------------------------------------------------------

class TestAutonomousTaskDefaults:
    """Verify AutonomousTask default field values."""

    def test_defaults(self):
        async def noop():
            return {}

        t = AutonomousTask(name="x", fn=noop)
        assert t.interval_s == 30.0
        assert t.last_run == 0.0
        assert t.last_result == {}
        assert t.run_count == 0
        assert t.fail_count == 0
        assert t.enabled is True
        assert t.cron is None


# ---------------------------------------------------------------------------
# AutonomousLoop lifecycle (start / stop)
# ---------------------------------------------------------------------------

class TestLoopLifecycle:
    """start(), stop(), is_running property."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        loop = AutonomousLoop(tick_interval=100.0)
        # Remove all builtin tasks so the loop does nothing heavy
        loop._tasks.clear()
        await loop.start()
        assert loop.is_running is True
        assert loop._loop_task is not None
        loop.stop()
        assert loop.is_running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Calling start twice does not create a second internal task."""
        loop = AutonomousLoop(tick_interval=100.0)
        loop._tasks.clear()
        await loop.start()
        first_task = loop._loop_task
        await loop.start()  # second call — should be a no-op
        assert loop._loop_task is first_task
        loop.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_loop_task(self):
        loop = AutonomousLoop(tick_interval=100.0)
        loop._tasks.clear()
        await loop.start()
        internal = loop._loop_task
        loop.stop()
        # Give a tick for cancellation to propagate
        await asyncio.sleep(0.05)
        assert internal.cancelled() or internal.done()

    def test_stop_when_not_started(self):
        """stop() on a never-started loop should not raise."""
        loop = AutonomousLoop()
        loop.stop()  # no-op, no error
        assert loop.is_running is False


# ---------------------------------------------------------------------------
# _run_loop — due task selection, cron filtering, exception handling
# ---------------------------------------------------------------------------

class TestRunLoop:
    """Verifies that _run_loop selects due tasks, respects cron, and handles exceptions."""

    @pytest.mark.asyncio
    async def test_due_tasks_are_executed(self):
        """Tasks whose interval has elapsed should be executed by the loop."""
        call_log = []

        async def tracked():
            call_log.append(time.time())
            return {"ok": True}

        loop = AutonomousLoop(tick_interval=0.05)
        loop._tasks.clear()
        loop.register("tracked", tracked, interval_s=0)  # always due

        await loop.start()
        await asyncio.sleep(0.15)
        loop.stop()

        assert len(call_log) >= 1, "Task should have been called at least once"

    @pytest.mark.asyncio
    async def test_cron_mismatch_skips_task(self):
        """A task with a cron that doesn't match now should not run."""
        call_log = []

        async def should_not_run():
            call_log.append(1)
            return {}

        now = datetime.now()
        bad_cron = CronSchedule(hour=(now.hour + 12) % 24)

        loop = AutonomousLoop(tick_interval=0.05)
        loop._tasks.clear()
        loop.register("cron_skip", should_not_run, interval_s=0, cron=bad_cron)

        await loop.start()
        await asyncio.sleep(0.15)
        loop.stop()

        assert len(call_log) == 0, "Task with non-matching cron should not run"

    @pytest.mark.asyncio
    async def test_disabled_task_skipped(self):
        """Disabled tasks should not execute in the loop."""
        call_log = []

        async def disabled_fn():
            call_log.append(1)
            return {}

        loop = AutonomousLoop(tick_interval=0.05)
        loop._tasks.clear()
        loop.register("disabled_t", disabled_fn, interval_s=0)
        loop.enable("disabled_t", False)

        await loop.start()
        await asyncio.sleep(0.15)
        loop.stop()

        assert len(call_log) == 0

    @pytest.mark.asyncio
    async def test_exception_in_task_does_not_crash_loop(self):
        """An exception from asyncio.gather (return_exceptions) should be caught."""
        ok_calls = []

        async def ok_task():
            ok_calls.append(1)
            return {"ok": True}

        async def bad_task():
            raise RuntimeError("boom")

        loop = AutonomousLoop(tick_interval=0.05)
        loop._tasks.clear()
        loop.register("ok", ok_task, interval_s=0)
        loop.register("bad", bad_task, interval_s=0)

        await loop.start()
        await asyncio.sleep(0.20)
        loop.stop()

        # The loop should still be ticking — ok_task should have been called
        assert len(ok_calls) >= 1
        # bad task fail_count should be incremented via gather exception path
        assert loop._tasks["bad"].fail_count >= 1


# ---------------------------------------------------------------------------
# _run_task — timeout and alert paths
# ---------------------------------------------------------------------------

class TestRunTask:
    """_run_task timeout handling and alert logging."""

    @pytest.mark.asyncio
    async def test_timeout_returns_error_dict(self):
        async def slow():
            await asyncio.sleep(999)
            return {}

        loop = AutonomousLoop()
        task = AutonomousTask(name="slow", fn=slow)

        # Patch wait_for timeout to something short
        with patch("src.autonomous_loop.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await loop._run_task(task)

        assert result == {"error": "timeout"}
        assert task.fail_count == 1
        # A timeout event should be logged
        events = loop.get_events()
        timeout_events = [e for e in events if e["level"] == "timeout"]
        assert len(timeout_events) >= 1

    @pytest.mark.asyncio
    async def test_alert_in_result_is_logged(self):
        async def alerting():
            return {"alert": "disk full", "status": "warn"}

        loop = AutonomousLoop()
        task = AutonomousTask(name="alerter", fn=alerting)
        result = await loop._run_task(task)

        assert result["alert"] == "disk full"
        assert task.last_result == result
        events = loop.get_events()
        alert_events = [e for e in events if e["level"] == "alert"]
        assert len(alert_events) == 1
        assert "disk full" in alert_events[0]["message"]

    @pytest.mark.asyncio
    async def test_run_task_updates_last_run_and_run_count(self):
        async def simple():
            return {"v": 42}

        loop = AutonomousLoop()
        task = AutonomousTask(name="simple", fn=simple)
        before = time.time()
        await loop._run_task(task)

        assert task.run_count == 1
        assert task.last_run >= before
        assert task.last_result == {"v": 42}


# ---------------------------------------------------------------------------
# dynamic_register
# ---------------------------------------------------------------------------

class TestDynamicRegister:
    """dynamic_register() — async registration with event_bus."""

    @pytest.mark.asyncio
    async def test_dynamic_register_adds_task(self):
        async def dyn():
            return {"dynamic": True}

        loop = AutonomousLoop()
        initial_count = len(loop._tasks)

        with patch("src.autonomous_loop.event_bus", create=True) as mock_bus:
            mock_bus.emit = AsyncMock()
            with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
                await loop.dynamic_register("dyn_task", dyn, interval_s=45.0)

        assert "dyn_task" in loop._tasks
        assert loop._tasks["dyn_task"].interval_s == 45.0
        assert len(loop._tasks) == initial_count + 1

    @pytest.mark.asyncio
    async def test_dynamic_register_logs_event(self):
        async def dyn():
            return {}

        loop = AutonomousLoop()

        with patch("src.autonomous_loop.event_bus", create=True) as mock_bus:
            mock_bus.emit = AsyncMock()
            with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
                await loop.dynamic_register("logged_task", dyn, interval_s=10.0)

        events = loop.get_events()
        info_events = [e for e in events if e["level"] == "info"]
        assert any("Dynamic task registered" in e["message"] for e in info_events)

    @pytest.mark.asyncio
    async def test_dynamic_register_event_bus_failure_does_not_raise(self):
        """If event_bus.emit raises, dynamic_register should still complete."""
        async def dyn():
            return {}

        loop = AutonomousLoop()
        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock(side_effect=RuntimeError("bus down"))

        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
            # Should not raise
            await loop.dynamic_register("robust_task", dyn, interval_s=20.0)

        assert "robust_task" in loop._tasks

    @pytest.mark.asyncio
    async def test_dynamic_register_with_cron(self):
        async def dyn():
            return {}

        loop = AutonomousLoop()
        cron = CronSchedule(hour=12, minute=30)

        with patch("src.autonomous_loop.event_bus", create=True) as mock_bus:
            mock_bus.emit = AsyncMock()
            with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
                await loop.dynamic_register("cron_dyn", dyn, interval_s=3600, cron=cron)

        assert loop._tasks["cron_dyn"].cron is not None
        assert loop._tasks["cron_dyn"].cron.hour == 12


# ---------------------------------------------------------------------------
# Edge cases: enable / unregister on missing tasks
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge-case behavior for missing task names."""

    def test_unregister_nonexistent_is_noop(self):
        loop = AutonomousLoop()
        count_before = len(loop._tasks)
        loop.unregister("does_not_exist")
        assert len(loop._tasks) == count_before

    def test_enable_nonexistent_is_noop(self):
        loop = AutonomousLoop()
        # Should not raise
        loop.enable("nonexistent_task", False)
        assert "nonexistent_task" not in loop._tasks

    def test_register_overwrites_existing(self):
        async def fn1():
            return {"v": 1}

        async def fn2():
            return {"v": 2}

        loop = AutonomousLoop()
        loop.register("dup", fn1, interval_s=10)
        loop.register("dup", fn2, interval_s=20)
        assert loop._tasks["dup"].interval_s == 20


# ---------------------------------------------------------------------------
# _log_event structure and get_events limit
# ---------------------------------------------------------------------------

class TestLogEventAndGetEvents:
    """_log_event entry structure and get_events(limit=...)."""

    def test_log_event_structure(self):
        loop = AutonomousLoop()
        before = time.time()
        loop._log_event("my_task", "warning", "something happened")
        events = loop.get_events()
        assert len(events) == 1
        e = events[0]
        assert e["task"] == "my_task"
        assert e["level"] == "warning"
        assert e["message"] == "something happened"
        assert e["ts"] >= before

    def test_get_events_respects_limit(self):
        loop = AutonomousLoop()
        for i in range(20):
            loop._log_event("t", "info", f"msg {i}")
        assert len(loop.get_events(limit=5)) == 5
        assert len(loop.get_events(limit=100)) == 20

    def test_get_events_returns_tail(self):
        """get_events should return the most recent entries."""
        loop = AutonomousLoop()
        for i in range(10):
            loop._log_event("t", "info", f"msg {i}")
        last_3 = loop.get_events(limit=3)
        assert last_3[0]["message"] == "msg 7"
        assert last_3[-1]["message"] == "msg 9"


# ---------------------------------------------------------------------------
# get_status task-level detail
# ---------------------------------------------------------------------------

class TestGetStatusDetail:
    """get_status returns detailed per-task information."""

    @pytest.mark.asyncio
    async def test_status_reflects_run_count_and_fail_count(self):
        call_count = 0

        async def counting():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("first run fails")
            return {"ok": True}

        loop = AutonomousLoop()
        loop._tasks.clear()
        loop.register("counter", counting, interval_s=999)

        task = loop._tasks["counter"]
        # Run once (will fail)
        with pytest.raises(ValueError):
            await loop._run_task(task)
        # Run again (will succeed)
        await loop._run_task(task)

        status = loop.get_status()
        t_info = status["tasks"]["counter"]
        assert t_info["run_count"] == 2
        assert t_info["fail_count"] == 1
        assert t_info["last_result"] == {"ok": True}
        assert t_info["enabled"] is True
        assert t_info["interval_s"] == 999

    def test_status_event_count_matches(self):
        loop = AutonomousLoop()
        loop._log_event("a", "info", "x")
        loop._log_event("b", "info", "y")
        status = loop.get_status()
        assert status["event_count"] == 2

    def test_status_recent_events_capped_at_10(self):
        loop = AutonomousLoop()
        for i in range(15):
            loop._log_event("t", "info", f"e{i}")
        status = loop.get_status()
        assert len(status["recent_events"]) == 10
        # Should be the last 10
        assert status["recent_events"][0]["message"] == "e5"
