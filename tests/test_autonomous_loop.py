"""Tests for src/autonomous_loop.py — Autonomous loop infrastructure.

Covers: CronSchedule, AutonomousTask, AutonomousLoop (register, unregister,
enable, start, stop, get_status, get_events, _run_task, _log_event).
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.autonomous_loop import CronSchedule, AutonomousTask, AutonomousLoop


# ===========================================================================
# CronSchedule
# ===========================================================================

class TestCronSchedule:
    def test_any_matches(self):
        cron = CronSchedule()
        assert cron.matches_now() is True

    def test_hour_match(self):
        now = datetime.now()
        cron = CronSchedule(hour=now.hour)
        assert cron.matches_now() is True

    def test_hour_no_match(self):
        now = datetime.now()
        wrong_hour = (now.hour + 12) % 24
        cron = CronSchedule(hour=wrong_hour)
        assert cron.matches_now() is False

    def test_weekday_match(self):
        now = datetime.now()
        cron = CronSchedule(weekdays=[now.weekday()])
        assert cron.matches_now() is True

    def test_weekday_no_match(self):
        now = datetime.now()
        wrong_day = (now.weekday() + 3) % 7
        cron = CronSchedule(weekdays=[wrong_day])
        assert cron.matches_now() is False

    def test_minute_match(self):
        now = datetime.now()
        cron = CronSchedule(minute=now.minute)
        assert cron.matches_now() is True

    def test_combined_match(self):
        now = datetime.now()
        cron = CronSchedule(hour=now.hour, minute=now.minute, weekdays=[now.weekday()])
        assert cron.matches_now() is True

    def test_combined_partial_mismatch(self):
        now = datetime.now()
        wrong_hour = (now.hour + 12) % 24
        cron = CronSchedule(hour=wrong_hour, minute=now.minute)
        assert cron.matches_now() is False


# ===========================================================================
# AutonomousTask
# ===========================================================================

class TestAutonomousTask:
    def test_defaults(self):
        async def dummy():
            return {}
        task = AutonomousTask(name="test", fn=dummy)
        assert task.interval_s == 30.0
        assert task.last_run == 0.0
        assert task.run_count == 0
        assert task.fail_count == 0
        assert task.enabled is True
        assert task.cron is None

    def test_with_cron(self):
        async def dummy():
            return {}
        cron = CronSchedule(hour=3)
        task = AutonomousTask(name="test", fn=dummy, cron=cron)
        assert task.cron.hour == 3


# ===========================================================================
# AutonomousLoop — Registration
# ===========================================================================

class TestAutonomousLoopRegistration:
    def test_init(self):
        loop = AutonomousLoop(tick_interval=5.0)
        assert loop._tick == 5.0
        assert loop._running is False
        assert len(loop._tasks) > 0  # builtin tasks registered

    def test_builtin_tasks_registered(self):
        loop = AutonomousLoop()
        assert "health_check" in loop._tasks
        assert "gpu_monitor" in loop._tasks
        assert "self_heal" in loop._tasks
        assert "db_backup" in loop._tasks

    def test_register_custom(self):
        loop = AutonomousLoop()
        async def my_task():
            return {"ok": True}
        loop.register("custom", my_task, interval_s=60.0)
        assert "custom" in loop._tasks
        assert loop._tasks["custom"].interval_s == 60.0

    def test_register_with_cron(self):
        loop = AutonomousLoop()
        async def my_task():
            return {}
        cron = CronSchedule(hour=2, minute=30)
        loop.register("cron_task", my_task, cron=cron)
        assert loop._tasks["cron_task"].cron.hour == 2

    def test_unregister(self):
        loop = AutonomousLoop()
        async def my_task():
            return {}
        loop.register("temp", my_task)
        assert "temp" in loop._tasks
        loop.unregister("temp")
        assert "temp" not in loop._tasks

    def test_unregister_nonexistent(self):
        loop = AutonomousLoop()
        loop.unregister("nonexistent")  # should not raise

    def test_enable_disable(self):
        loop = AutonomousLoop()
        loop.enable("health_check", False)
        assert loop._tasks["health_check"].enabled is False
        loop.enable("health_check", True)
        assert loop._tasks["health_check"].enabled is True

    def test_enable_nonexistent(self):
        loop = AutonomousLoop()
        loop.enable("nonexistent", True)  # should not raise


# ===========================================================================
# AutonomousLoop — Start/Stop
# ===========================================================================

class TestAutonomousLoopStartStop:
    @pytest.mark.asyncio
    async def test_start(self):
        loop = AutonomousLoop(tick_interval=100)
        # Disable all builtin tasks to avoid import errors
        for task in loop._tasks.values():
            task.enabled = False
        await loop.start()
        assert loop.is_running is True
        loop.stop()
        assert loop.is_running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        loop = AutonomousLoop(tick_interval=100)
        for task in loop._tasks.values():
            task.enabled = False
        await loop.start()
        await loop.start()  # second call should be no-op
        assert loop.is_running is True
        loop.stop()

    def test_stop_when_not_running(self):
        loop = AutonomousLoop()
        loop.stop()  # should not raise
        assert loop.is_running is False


# ===========================================================================
# AutonomousLoop — _log_event
# ===========================================================================

class TestLogEvent:
    def test_log_event(self):
        loop = AutonomousLoop()
        loop._log_event("test_task", "info", "test message")
        assert len(loop._event_log) == 1
        assert loop._event_log[0]["task"] == "test_task"
        assert loop._event_log[0]["level"] == "info"

    def test_log_event_ring_buffer(self):
        loop = AutonomousLoop()
        for i in range(250):
            loop._log_event("t", "info", f"msg_{i}")
        assert len(loop._event_log) == 200


# ===========================================================================
# AutonomousLoop — _run_task
# ===========================================================================

class TestRunTask:
    @pytest.mark.asyncio
    async def test_success(self):
        loop = AutonomousLoop()
        async def good_task():
            return {"status": "ok"}
        task = AutonomousTask(name="good", fn=good_task)
        result = await loop._run_task(task)
        assert result["status"] == "ok"
        assert task.run_count == 1
        assert task.fail_count == 0

    @pytest.mark.asyncio
    async def test_with_alert(self):
        loop = AutonomousLoop()
        async def alert_task():
            return {"alert": "Something happened"}
        task = AutonomousTask(name="alert", fn=alert_task)
        await loop._run_task(task)
        assert any("Something happened" in e["message"] for e in loop._event_log)

    @pytest.mark.asyncio
    async def test_timeout(self):
        loop = AutonomousLoop()
        async def slow_task():
            await asyncio.sleep(60)
            return {}
        task = AutonomousTask(name="slow", fn=slow_task)
        # _run_task has 30s timeout, but we'll patch wait_for to raise immediately
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            result = await loop._run_task(task)
        assert result["error"] == "timeout"
        assert task.fail_count == 1

    @pytest.mark.asyncio
    async def test_exception(self):
        loop = AutonomousLoop()
        async def bad_task():
            raise ValueError("broken")
        task = AutonomousTask(name="bad", fn=bad_task)
        with pytest.raises(ValueError, match="broken"):
            await loop._run_task(task)
        assert task.fail_count == 1


# ===========================================================================
# AutonomousLoop — get_status / get_events
# ===========================================================================

class TestStatus:
    def test_get_status(self):
        loop = AutonomousLoop()
        status = loop.get_status()
        assert status["running"] is False
        assert "tasks" in status
        assert "health_check" in status["tasks"]
        assert status["tasks"]["health_check"]["enabled"] is True

    def test_get_events_empty(self):
        loop = AutonomousLoop()
        events = loop.get_events()
        assert isinstance(events, list)

    def test_get_events_with_limit(self):
        loop = AutonomousLoop()
        for i in range(20):
            loop._log_event("t", "info", f"msg_{i}")
        events = loop.get_events(limit=5)
        assert len(events) == 5

    def test_status_after_register(self):
        loop = AutonomousLoop()
        async def my_task():
            return {}
        loop.register("custom_status", my_task, interval_s=42)
        status = loop.get_status()
        assert "custom_status" in status["tasks"]
        assert status["tasks"]["custom_status"]["interval_s"] == 42


# ===========================================================================
# AutonomousLoop — dynamic_register
# ===========================================================================

class TestDynamicRegister:
    @pytest.mark.asyncio
    async def test_dynamic_register(self):
        loop = AutonomousLoop()
        async def dyn_task():
            return {"dyn": True}
        with patch("src.autonomous_loop.event_bus", create=True) as mock_bus:
            with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=AsyncMock())}):
                try:
                    await loop.dynamic_register("dynamic_one", dyn_task, interval_s=120)
                except Exception:
                    pass  # event_bus import may fail, task still registered
        assert "dynamic_one" in loop._tasks
