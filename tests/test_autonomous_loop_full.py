"""Supplementary tests for src.autonomous_loop — CronSchedule and AutonomousLoop.

Covers areas NOT tested in test_autonomous_loop_module.py:
- CronSchedule.matches_now with mocked datetime (deterministic, no flakiness)
- register + unregister full lifecycle
- enable / disable toggle and impact on execution
- run_once semantics (_run_loop single iteration with mocked tasks)
- _log_event ring buffer truncation at _max_log
- _run_task exception re-raise path
- CronSchedule edge cases: weekday mismatch, all-None, boundary values
- Task interval not elapsed -> skipped
- Multiple tasks with mixed cron/no-cron
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.autonomous_loop import AutonomousLoop, AutonomousTask, CronSchedule


# ============================================================================
# Helpers
# ============================================================================

def _make_loop() -> AutonomousLoop:
    """Create an AutonomousLoop with no builtin tasks for clean testing."""
    loop = AutonomousLoop(tick_interval=100.0)
    loop._tasks.clear()
    loop._event_log.clear()
    return loop


def _fake_datetime(year=2026, month=3, day=9, hour=14, minute=30, weekday=0):
    """Return a mock datetime class where .now() returns a fixed time.

    weekday: 0=Monday ... 6=Sunday.  The day parameter is adjusted so that
    the actual weekday returned by the real datetime constructor may differ
    from the desired weekday.  We override .weekday() on the returned object.
    """
    mock_now = MagicMock(spec=datetime)
    mock_now.hour = hour
    mock_now.minute = minute
    mock_now.weekday.return_value = weekday
    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = mock_now
    return mock_dt


# ============================================================================
# CronSchedule.matches_now — deterministic tests with mocked datetime
# ============================================================================

class TestCronScheduleDeterministic:
    """CronSchedule.matches_now with mocked datetime for deterministic results."""

    def test_all_none_always_matches(self):
        """CronSchedule with all fields None matches any time."""
        c = CronSchedule()
        # Even without mocking, all-None should always match
        assert c.matches_now() is True

    def test_hour_match(self):
        fake_dt = _fake_datetime(hour=14, minute=30, weekday=0)
        c = CronSchedule(hour=14)
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is True

    def test_hour_mismatch(self):
        fake_dt = _fake_datetime(hour=14, minute=30, weekday=0)
        c = CronSchedule(hour=10)
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is False

    def test_minute_match(self):
        fake_dt = _fake_datetime(hour=14, minute=30, weekday=0)
        c = CronSchedule(minute=30)
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is True

    def test_minute_mismatch(self):
        fake_dt = _fake_datetime(hour=14, minute=30, weekday=0)
        c = CronSchedule(minute=0)
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is False

    def test_weekday_match(self):
        fake_dt = _fake_datetime(hour=14, minute=30, weekday=2)  # Wednesday
        c = CronSchedule(weekdays=[1, 2, 3])
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is True

    def test_weekday_mismatch(self):
        fake_dt = _fake_datetime(hour=14, minute=30, weekday=5)  # Saturday
        c = CronSchedule(weekdays=[0, 1, 2, 3, 4])  # Mon-Fri only
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is False

    def test_combined_all_match(self):
        fake_dt = _fake_datetime(hour=3, minute=0, weekday=6)  # Sunday 3:00
        c = CronSchedule(hour=3, minute=0, weekdays=[6])
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is True

    def test_combined_hour_ok_minute_fail(self):
        fake_dt = _fake_datetime(hour=3, minute=15, weekday=6)
        c = CronSchedule(hour=3, minute=0, weekdays=[6])
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is False

    def test_combined_weekday_fail_rest_ok(self):
        fake_dt = _fake_datetime(hour=3, minute=0, weekday=5)  # Saturday, not Sunday
        c = CronSchedule(hour=3, minute=0, weekdays=[6])
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is False

    def test_weekday_empty_list_never_matches(self):
        """An empty weekdays list means no day matches."""
        fake_dt = _fake_datetime(hour=12, minute=0, weekday=3)
        c = CronSchedule(weekdays=[])
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is False

    def test_boundary_hour_0(self):
        fake_dt = _fake_datetime(hour=0, minute=0, weekday=0)
        c = CronSchedule(hour=0)
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is True

    def test_boundary_hour_23(self):
        fake_dt = _fake_datetime(hour=23, minute=59, weekday=0)
        c = CronSchedule(hour=23, minute=59)
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is True

    def test_boundary_minute_0(self):
        fake_dt = _fake_datetime(hour=12, minute=0, weekday=0)
        c = CronSchedule(minute=0)
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is True

    def test_boundary_minute_59(self):
        fake_dt = _fake_datetime(hour=12, minute=59, weekday=0)
        c = CronSchedule(minute=59)
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is True

    def test_weekday_sunday_is_6(self):
        fake_dt = _fake_datetime(hour=4, minute=0, weekday=6)
        c = CronSchedule(weekdays=[6])
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is True

    def test_weekday_monday_is_0(self):
        fake_dt = _fake_datetime(hour=4, minute=0, weekday=0)
        c = CronSchedule(weekdays=[0])
        with patch("src.autonomous_loop.datetime", fake_dt):
            assert c.matches_now() is True


# ============================================================================
# AutonomousLoop.register / unregister full lifecycle
# ============================================================================

class TestRegisterUnregisterLifecycle:
    """Full register -> verify -> unregister -> verify lifecycle."""

    def test_register_adds_task_with_correct_attributes(self):
        loop = _make_loop()

        async def my_fn():
            return {"x": 1}

        loop.register("my_task", my_fn, interval_s=42.0)

        assert "my_task" in loop._tasks
        task = loop._tasks["my_task"]
        assert task.name == "my_task"
        assert task.interval_s == 42.0
        assert task.enabled is True
        assert task.cron is None
        assert task.run_count == 0
        assert task.fail_count == 0
        assert task.fn is my_fn

    def test_register_with_cron(self):
        loop = _make_loop()

        async def my_fn():
            return {}

        cron = CronSchedule(hour=2, minute=30, weekdays=[0, 4])
        loop.register("cron_task", my_fn, interval_s=3600, cron=cron)

        task = loop._tasks["cron_task"]
        assert task.cron is cron
        assert task.cron.hour == 2
        assert task.cron.minute == 30
        assert task.cron.weekdays == [0, 4]

    def test_unregister_removes_task(self):
        loop = _make_loop()

        async def my_fn():
            return {}

        loop.register("removable", my_fn, interval_s=10)
        assert "removable" in loop._tasks

        loop.unregister("removable")
        assert "removable" not in loop._tasks

    def test_unregister_then_register_again(self):
        loop = _make_loop()

        async def fn_v1():
            return {"v": 1}

        async def fn_v2():
            return {"v": 2}

        loop.register("reusable", fn_v1, interval_s=10)
        loop.unregister("reusable")
        loop.register("reusable", fn_v2, interval_s=20)

        assert loop._tasks["reusable"].fn is fn_v2
        assert loop._tasks["reusable"].interval_s == 20

    def test_register_overwrites_preserves_no_old_state(self):
        """Re-registering a task creates a fresh AutonomousTask (run_count reset)."""
        loop = _make_loop()

        async def fn():
            return {}

        loop.register("stateful", fn, interval_s=10)
        loop._tasks["stateful"].run_count = 5
        loop._tasks["stateful"].fail_count = 2

        # Re-register -> fresh task
        loop.register("stateful", fn, interval_s=30)
        assert loop._tasks["stateful"].run_count == 0
        assert loop._tasks["stateful"].fail_count == 0
        assert loop._tasks["stateful"].interval_s == 30

    def test_unregister_nonexistent_no_error(self):
        loop = _make_loop()
        loop.unregister("ghost")  # Should not raise
        assert len(loop._tasks) == 0

    def test_register_multiple_tasks(self):
        loop = _make_loop()

        async def fn():
            return {}

        for i in range(10):
            loop.register(f"task_{i}", fn, interval_s=i + 1)

        assert len(loop._tasks) == 10
        for i in range(10):
            assert f"task_{i}" in loop._tasks
            assert loop._tasks[f"task_{i}"].interval_s == i + 1


# ============================================================================
# AutonomousLoop.enable / disable
# ============================================================================

class TestEnableDisable:
    """enable() and disable() toggle and their effects."""

    def test_disable_task(self):
        loop = _make_loop()

        async def fn():
            return {}

        loop.register("toggleable", fn)
        assert loop._tasks["toggleable"].enabled is True

        loop.enable("toggleable", False)
        assert loop._tasks["toggleable"].enabled is False

    def test_enable_task(self):
        loop = _make_loop()

        async def fn():
            return {}

        loop.register("toggleable", fn)
        loop.enable("toggleable", False)
        loop.enable("toggleable", True)
        assert loop._tasks["toggleable"].enabled is True

    def test_enable_default_true(self):
        """enable(name) with no second arg defaults to True."""
        loop = _make_loop()

        async def fn():
            return {}

        loop.register("t", fn)
        loop.enable("t", False)
        loop.enable("t")  # default = True
        assert loop._tasks["t"].enabled is True

    def test_enable_nonexistent_is_noop(self):
        loop = _make_loop()
        loop.enable("nope", False)  # Should not raise
        loop.enable("nope", True)  # Should not raise

    @pytest.mark.asyncio
    async def test_disabled_task_not_run_by_run_task_selection(self):
        """Verify that _run_loop skips disabled tasks (using a single iteration)."""
        calls = []

        async def tracked():
            calls.append(1)
            return {}

        loop = _make_loop()
        loop._tick = 0.02
        loop.register("dis", tracked, interval_s=0)
        loop.enable("dis", False)

        # Run one iteration manually
        await loop.start()
        await asyncio.sleep(0.06)
        loop.stop()

        assert len(calls) == 0

    @pytest.mark.asyncio
    async def test_reenable_task_runs_again(self):
        """After re-enabling, the task should run on next tick."""
        calls = []

        async def tracked():
            calls.append(1)
            return {}

        loop = _make_loop()
        loop._tick = 0.02
        loop.register("re", tracked, interval_s=0)
        loop.enable("re", False)

        await loop.start()
        await asyncio.sleep(0.06)
        # No calls yet
        assert len(calls) == 0

        loop.enable("re", True)
        await asyncio.sleep(0.06)
        loop.stop()

        assert len(calls) >= 1


# ============================================================================
# dynamic_register
# ============================================================================

class TestDynamicRegisterSupplemental:
    """Supplemental tests for dynamic_register not in the existing test file."""

    @pytest.mark.asyncio
    async def test_dynamic_register_emits_event(self):
        """Verify that event_bus.emit is called with the correct event name."""
        loop = _make_loop()

        async def fn():
            return {}

        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock(return_value=None)
        fake_module = ModuleType("src.event_bus")
        fake_module.event_bus = mock_bus  # type: ignore[attr-defined]

        with patch.dict("sys.modules", {"src.event_bus": fake_module}):
            await loop.dynamic_register("evt_task", fn, interval_s=100)

        mock_bus.emit.assert_awaited_once()
        call_args = mock_bus.emit.call_args
        assert call_args[0][0] == "autonomous.task_created"
        assert call_args[0][1]["name"] == "evt_task"
        assert call_args[0][1]["interval_s"] == 100

    @pytest.mark.asyncio
    async def test_dynamic_register_import_error_does_not_raise(self):
        """If src.event_bus cannot be imported, dynamic_register completes."""
        loop = _make_loop()

        async def fn():
            return {}

        # Remove src.event_bus from modules so import fails
        saved = sys.modules.pop("src.event_bus", None)
        try:
            with patch.dict("sys.modules", {"src.event_bus": None}):
                # import of src.event_bus will raise ImportError
                await loop.dynamic_register("import_fail", fn, interval_s=50)
        finally:
            if saved is not None:
                sys.modules["src.event_bus"] = saved

        assert "import_fail" in loop._tasks

    @pytest.mark.asyncio
    async def test_dynamic_register_logs_info_event(self):
        """The _event_log should contain an info entry after dynamic_register."""
        loop = _make_loop()

        async def fn():
            return {}

        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock(return_value=None)
        fake_module = ModuleType("src.event_bus")
        fake_module.event_bus = mock_bus  # type: ignore[attr-defined]

        with patch.dict("sys.modules", {"src.event_bus": fake_module}):
            await loop.dynamic_register("log_check", fn, interval_s=60)

        info_events = [e for e in loop._event_log if e["level"] == "info"]
        assert len(info_events) == 1
        assert "log_check" in info_events[0]["task"]
        assert "Dynamic task registered" in info_events[0]["message"]
        assert "60" in info_events[0]["message"]


# ============================================================================
# AutonomousLoop.run_once semantics (single _run_loop iteration with mocks)
# ============================================================================

class TestRunOnce:
    """Test _run_loop behavior for a single iteration with mocked tasks."""

    @pytest.mark.asyncio
    async def test_run_once_executes_due_tasks(self):
        """Tasks with interval elapsed should be executed."""
        results = []

        async def task_a():
            results.append("a")
            return {"task": "a"}

        async def task_b():
            results.append("b")
            return {"task": "b"}

        loop = _make_loop()
        loop._tick = 0.02
        loop.register("a", task_a, interval_s=0)  # always due
        loop.register("b", task_b, interval_s=0)  # always due

        await loop.start()
        await asyncio.sleep(0.06)
        loop.stop()

        assert "a" in results
        assert "b" in results

    @pytest.mark.asyncio
    async def test_run_once_skips_not_due_tasks(self):
        """Tasks whose interval has not elapsed should be skipped."""
        results = []

        async def task_quick():
            results.append("quick")
            return {}

        async def task_slow():
            results.append("slow")
            return {}

        loop = _make_loop()
        loop._tick = 0.02
        loop.register("quick", task_quick, interval_s=0)
        loop.register("slow", task_slow, interval_s=999999)
        # Pre-fill last_run so the interval check sees it as "just ran"
        loop._tasks["slow"].last_run = time.time()

        await loop.start()
        await asyncio.sleep(0.06)
        loop.stop()

        assert "quick" in results
        assert "slow" not in results

    @pytest.mark.asyncio
    async def test_run_once_task_raises_increments_fail_count(self):
        """A task that raises should increment fail_count via gather exception path."""
        async def bad():
            raise ValueError("test error")

        loop = _make_loop()
        loop._tick = 0.02
        loop.register("bad", bad, interval_s=0)

        await loop.start()
        await asyncio.sleep(0.08)
        loop.stop()

        assert loop._tasks["bad"].fail_count >= 1

    @pytest.mark.asyncio
    async def test_run_once_task_raises_does_not_stop_loop(self):
        """A failing task should not prevent subsequent ticks."""
        ok_calls = []

        async def ok():
            ok_calls.append(1)
            return {}

        async def bad():
            raise RuntimeError("boom")

        loop = _make_loop()
        loop._tick = 0.02
        loop.register("ok", ok, interval_s=0)
        loop.register("bad", bad, interval_s=0)

        await loop.start()
        await asyncio.sleep(0.10)
        loop.stop()

        # ok should have been called multiple times across ticks
        assert len(ok_calls) >= 2

    @pytest.mark.asyncio
    async def test_run_once_with_cron_match(self):
        """Task with matching cron should run."""
        calls = []

        async def cron_task():
            calls.append(1)
            return {}

        fake_dt = _fake_datetime(hour=3, minute=0, weekday=6)
        cron = CronSchedule(hour=3, minute=0, weekdays=[6])

        loop = _make_loop()
        loop._tick = 0.02
        loop.register("cron_yes", cron_task, interval_s=0, cron=cron)

        with patch("src.autonomous_loop.datetime", fake_dt):
            await loop.start()
            await asyncio.sleep(0.06)
            loop.stop()

        assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_run_once_with_cron_no_match(self):
        """Task with non-matching cron should NOT run."""
        calls = []

        async def cron_task():
            calls.append(1)
            return {}

        fake_dt = _fake_datetime(hour=10, minute=0, weekday=3)
        cron = CronSchedule(hour=3, minute=0, weekdays=[6])

        loop = _make_loop()
        loop._tick = 0.02
        loop.register("cron_no", cron_task, interval_s=0, cron=cron)

        with patch("src.autonomous_loop.datetime", fake_dt):
            await loop.start()
            await asyncio.sleep(0.06)
            loop.stop()

        assert len(calls) == 0

    @pytest.mark.asyncio
    async def test_run_once_mixed_cron_and_regular(self):
        """Mix of cron-gated and regular tasks in the same loop."""
        calls = {"regular": 0, "cron_match": 0, "cron_miss": 0}

        async def regular():
            calls["regular"] += 1
            return {}

        async def cron_match_fn():
            calls["cron_match"] += 1
            return {}

        async def cron_miss_fn():
            calls["cron_miss"] += 1
            return {}

        fake_dt = _fake_datetime(hour=12, minute=0, weekday=1)  # Tuesday noon

        loop = _make_loop()
        loop._tick = 0.02
        loop.register("regular", regular, interval_s=0)
        loop.register("cron_match", cron_match_fn, interval_s=0,
                       cron=CronSchedule(hour=12))
        loop.register("cron_miss", cron_miss_fn, interval_s=0,
                       cron=CronSchedule(hour=5))

        with patch("src.autonomous_loop.datetime", fake_dt):
            await loop.start()
            await asyncio.sleep(0.06)
            loop.stop()

        assert calls["regular"] >= 1
        assert calls["cron_match"] >= 1
        assert calls["cron_miss"] == 0


# ============================================================================
# _run_task detailed behavior
# ============================================================================

class TestRunTaskDetailed:
    """Detailed _run_task tests: exception re-raise, timeout, stats."""

    @pytest.mark.asyncio
    async def test_run_task_exception_reraises(self):
        """_run_task should re-raise exceptions (not timeout) after logging."""
        async def explode():
            raise RuntimeError("kaboom")

        loop = _make_loop()
        task = AutonomousTask(name="explode", fn=explode)

        with pytest.raises(RuntimeError, match="kaboom"):
            await loop._run_task(task)

        assert task.fail_count == 1
        assert task.run_count == 1
        # Error event should be logged
        error_events = [e for e in loop._event_log if e["level"] == "error"]
        assert len(error_events) == 1
        assert "kaboom" in error_events[0]["message"]

    @pytest.mark.asyncio
    async def test_run_task_timeout_does_not_reraise(self):
        """TimeoutError should be caught and return error dict, not re-raise."""
        async def hang():
            await asyncio.sleep(9999)
            return {}

        loop = _make_loop()
        task = AutonomousTask(name="hang", fn=hang)

        with patch("src.autonomous_loop.asyncio.wait_for",
                   side_effect=asyncio.TimeoutError):
            result = await loop._run_task(task)

        assert result == {"error": "timeout"}
        assert task.fail_count == 1

    @pytest.mark.asyncio
    async def test_run_task_updates_last_result_on_success(self):
        async def success():
            return {"status": "ok", "value": 42}

        loop = _make_loop()
        task = AutonomousTask(name="success", fn=success)
        result = await loop._run_task(task)

        assert result == {"status": "ok", "value": 42}
        assert task.last_result == {"status": "ok", "value": 42}
        assert task.run_count == 1
        assert task.fail_count == 0

    @pytest.mark.asyncio
    async def test_run_task_does_not_update_last_result_on_exception(self):
        """On exception, last_result should remain the default (not updated)."""
        async def fail():
            raise ValueError("nope")

        loop = _make_loop()
        task = AutonomousTask(name="fail", fn=fail)

        with pytest.raises(ValueError):
            await loop._run_task(task)

        assert task.last_result == {}  # unchanged default

    @pytest.mark.asyncio
    async def test_run_task_alert_logged(self):
        """If result contains 'alert', an alert event is logged."""
        async def alerting():
            return {"alert": "disk 90% full", "status": "warn"}

        loop = _make_loop()
        task = AutonomousTask(name="disk", fn=alerting)
        await loop._run_task(task)

        alert_events = [e for e in loop._event_log if e["level"] == "alert"]
        assert len(alert_events) == 1
        assert alert_events[0]["task"] == "disk"
        assert "disk 90% full" in alert_events[0]["message"]

    @pytest.mark.asyncio
    async def test_run_task_no_alert_no_event(self):
        """If result has no 'alert' key, no alert event is logged."""
        async def clean():
            return {"status": "ok"}

        loop = _make_loop()
        task = AutonomousTask(name="clean", fn=clean)
        await loop._run_task(task)

        alert_events = [e for e in loop._event_log if e["level"] == "alert"]
        assert len(alert_events) == 0

    @pytest.mark.asyncio
    async def test_run_task_consecutive_runs_increment_counts(self):
        call_n = 0

        async def sometimes_fail():
            nonlocal call_n
            call_n += 1
            if call_n % 2 == 0:
                raise RuntimeError("even fail")
            return {"n": call_n}

        loop = _make_loop()
        task = AutonomousTask(name="mixed", fn=sometimes_fail)

        # Run 1: success
        await loop._run_task(task)
        assert task.run_count == 1
        assert task.fail_count == 0

        # Run 2: fail
        with pytest.raises(RuntimeError):
            await loop._run_task(task)
        assert task.run_count == 2
        assert task.fail_count == 1

        # Run 3: success
        await loop._run_task(task)
        assert task.run_count == 3
        assert task.fail_count == 1


# ============================================================================
# _log_event ring buffer truncation
# ============================================================================

class TestLogEventRingBuffer:
    """Verify the ring buffer (_max_log) behavior of _log_event."""

    def test_ring_buffer_truncates_at_max_log(self):
        loop = _make_loop()
        loop._max_log = 10

        for i in range(25):
            loop._log_event("t", "info", f"msg_{i}")

        assert len(loop._event_log) == 10
        # Should keep the last 10
        assert loop._event_log[0]["message"] == "msg_15"
        assert loop._event_log[-1]["message"] == "msg_24"

    def test_ring_buffer_exact_max_no_truncation(self):
        loop = _make_loop()
        loop._max_log = 5

        for i in range(5):
            loop._log_event("t", "info", f"m_{i}")

        assert len(loop._event_log) == 5
        assert loop._event_log[0]["message"] == "m_0"

    def test_ring_buffer_one_over_truncates(self):
        loop = _make_loop()
        loop._max_log = 5

        for i in range(6):
            loop._log_event("t", "info", f"m_{i}")

        assert len(loop._event_log) == 5
        assert loop._event_log[0]["message"] == "m_1"

    def test_event_structure_fields(self):
        loop = _make_loop()
        before = time.time()
        loop._log_event("my_task", "critical", "system down")

        assert len(loop._event_log) == 1
        ev = loop._event_log[0]
        assert ev["task"] == "my_task"
        assert ev["level"] == "critical"
        assert ev["message"] == "system down"
        assert ev["ts"] >= before
        assert ev["ts"] <= time.time()


# ============================================================================
# get_status / get_events
# ============================================================================

class TestGetStatusGetEvents:
    """get_status and get_events output correctness."""

    def test_get_status_running_flag(self):
        loop = _make_loop()
        status = loop.get_status()
        assert status["running"] is False

    def test_get_status_tick_interval(self):
        loop = AutonomousLoop(tick_interval=42.0)
        loop._tasks.clear()
        status = loop.get_status()
        assert status["tick_interval_s"] == 42.0

    def test_get_status_tasks_dict(self):
        loop = _make_loop()

        async def fn():
            return {}

        loop.register("s1", fn, interval_s=10)
        loop.register("s2", fn, interval_s=20)

        status = loop.get_status()
        assert "s1" in status["tasks"]
        assert "s2" in status["tasks"]
        assert status["tasks"]["s1"]["interval_s"] == 10
        assert status["tasks"]["s2"]["interval_s"] == 20
        assert status["tasks"]["s1"]["enabled"] is True

    def test_get_status_empty_loop(self):
        loop = _make_loop()
        status = loop.get_status()
        assert status["tasks"] == {}
        assert status["event_count"] == 0
        assert status["recent_events"] == []

    def test_get_events_empty(self):
        loop = _make_loop()
        assert loop.get_events() == []
        assert loop.get_events(limit=10) == []

    def test_get_events_default_limit_50(self):
        loop = _make_loop()
        for i in range(60):
            loop._log_event("t", "info", f"e_{i}")

        events = loop.get_events()  # default limit=50
        assert len(events) == 50

    def test_get_events_custom_limit(self):
        loop = _make_loop()
        for i in range(20):
            loop._log_event("t", "info", f"e_{i}")

        assert len(loop.get_events(limit=5)) == 5
        assert len(loop.get_events(limit=100)) == 20


# ============================================================================
# AutonomousLoop constructor
# ============================================================================

class TestLoopConstructor:
    """Verify AutonomousLoop constructor and _register_builtin_tasks."""

    def test_default_tick_interval(self):
        loop = AutonomousLoop()
        assert loop._tick == 10.0

    def test_custom_tick_interval(self):
        loop = AutonomousLoop(tick_interval=5.0)
        assert loop._tick == 5.0

    def test_builtin_tasks_registered(self):
        """A fresh AutonomousLoop should have builtin tasks registered."""
        loop = AutonomousLoop()
        expected = [
            "health_check", "gpu_monitor", "drift_reroute",
            "budget_alert", "auto_tune_sample", "self_heal",
            "proactive_suggest", "db_backup", "weekly_cleanup",
            "brain_auto_learn", "improve_cycle", "predict_next_actions",
            "auto_develop",
        ]
        for name in expected:
            assert name in loop._tasks, f"Builtin task '{name}' not found"

    def test_builtin_db_backup_has_cron(self):
        loop = AutonomousLoop()
        task = loop._tasks["db_backup"]
        assert task.cron is not None
        assert task.cron.hour == 3
        assert task.cron.minute == 0

    def test_builtin_weekly_cleanup_has_sunday_cron(self):
        loop = AutonomousLoop()
        task = loop._tasks["weekly_cleanup"]
        assert task.cron is not None
        assert task.cron.weekdays == [6]

    def test_initial_state(self):
        loop = AutonomousLoop()
        assert loop.is_running is False
        assert loop._loop_task is None
        assert loop._event_log == []


# ============================================================================
# Global singleton
# ============================================================================

class TestGlobalSingleton:
    """The module-level autonomous_loop singleton."""

    def test_singleton_exists(self):
        from src.autonomous_loop import autonomous_loop
        assert isinstance(autonomous_loop, AutonomousLoop)

    def test_singleton_has_builtin_tasks(self):
        from src.autonomous_loop import autonomous_loop
        assert len(autonomous_loop._tasks) >= 9
