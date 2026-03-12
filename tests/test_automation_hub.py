"""Tests for src/automation_hub.py — Central automation wiring."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ===========================================================================
# AutomationHub — init & start
# ===========================================================================

class TestAutomationHubInit:
    def test_singleton_exists(self):
        from src.automation_hub import automation_hub
        assert automation_hub is not None
        assert automation_hub._running is False

    def test_fresh_instance(self):
        from src.automation_hub import AutomationHub
        hub = AutomationHub()
        assert hub._running is False
        assert hub._queue_task is None
        assert hub._started_at == 0.0


class TestAutomationHubStart:
    @pytest.mark.asyncio
    async def test_start_wires_all_subsystems(self):
        from src.automation_hub import AutomationHub

        mock_loop = MagicMock()
        mock_loop.start = AsyncMock()
        mock_loop._tasks = {"a": 1, "b": 2}

        mock_scheduler = MagicMock()
        mock_scheduler.start = AsyncMock()
        mock_scheduler.get_stats.return_value = {
            "enabled_jobs": 3,
            "registered_handlers": ["dispatch", "domino"],
        }

        mock_queue = MagicMock()
        mock_queue.process_next = AsyncMock(return_value=None)

        hub = AutomationHub()

        with patch("src.automation_hub.AutomationHub._register_scheduler_handlers"):
            with patch.dict(sys.modules, {
                "src.autonomous_loop": MagicMock(autonomous_loop=mock_loop),
                "src.task_scheduler": MagicMock(task_scheduler=mock_scheduler),
                "src.task_queue": MagicMock(task_queue=mock_queue),
            }):
                report = await hub.start()

        assert hub._running is True
        assert "autonomous_loop" in report
        assert "task_scheduler" in report
        assert "task_queue" in report
        mock_loop.start.assert_awaited_once()
        mock_scheduler.start.assert_awaited_once()

        # Cleanup
        hub._running = False
        if hub._queue_task and not hub._queue_task.done():
            hub._queue_task.cancel()
            try:
                await hub._queue_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        from src.automation_hub import AutomationHub
        hub = AutomationHub()
        hub._running = True
        result = await hub.start()
        assert result == {"status": "already_running"}


class TestAutomationHubStop:
    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self):
        from src.automation_hub import AutomationHub
        hub = AutomationHub()
        hub._running = True

        mock_scheduler = MagicMock()
        mock_scheduler.stop = AsyncMock()
        mock_loop = MagicMock()

        with patch.dict(sys.modules, {
            "src.task_scheduler": MagicMock(task_scheduler=mock_scheduler),
            "src.autonomous_loop": MagicMock(autonomous_loop=mock_loop),
        }):
            await hub.stop()

        assert hub._running is False
        mock_scheduler.stop.assert_awaited_once()
        mock_loop.stop.assert_called_once()


# ===========================================================================
# Scheduler handler registration
# ===========================================================================

class TestSchedulerHandlers:
    def test_registers_all_handlers(self):
        from src.automation_hub import AutomationHub

        mock_scheduler = MagicMock()
        registered = {}

        def capture_register(action, handler):
            registered[action] = handler

        mock_scheduler.register_handler = capture_register

        AutomationHub._register_scheduler_handlers(mock_scheduler)

        expected_min = {
            "dispatch", "domino", "health_check", "backup",
            "gpu_monitor", "self_heal", "self_improve", "queue_enqueue",
            "notify", "cleanup", "noop",
        }
        assert expected_min.issubset(set(registered.keys())), (
            f"Missing core handlers: {expected_min - set(registered.keys())}"
        )

    @pytest.mark.asyncio
    async def test_noop_handler(self):
        from src.automation_hub import AutomationHub

        mock_scheduler = MagicMock()
        registered = {}
        mock_scheduler.register_handler = lambda a, h: registered.update({a: h})

        AutomationHub._register_scheduler_handlers(mock_scheduler)

        result = await registered["noop"]({})
        assert result == "noop"


# ===========================================================================
# Status API
# ===========================================================================

class TestSeedDefaultJobs:
    def test_seeds_when_empty(self):
        from src.automation_hub import AutomationHub

        mock_scheduler = MagicMock()
        mock_scheduler.list_jobs.return_value = []

        AutomationHub._seed_default_jobs(mock_scheduler)
        assert mock_scheduler.add_job.call_count == 5

    def test_skips_when_jobs_exist(self):
        from src.automation_hub import AutomationHub

        mock_scheduler = MagicMock()
        mock_scheduler.list_jobs.return_value = [{"name": "existing"}]

        AutomationHub._seed_default_jobs(mock_scheduler)
        mock_scheduler.add_job.assert_not_called()


class TestQueueProcessorLoop:
    @pytest.mark.asyncio
    async def test_processes_task_then_sleeps(self):
        from src.automation_hub import AutomationHub

        hub = AutomationHub()
        hub._running = True

        mock_queue = MagicMock()
        call_count = 0

        async def fake_process():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"id": "t1", "task_type": "code", "status": "done", "node": "M1"}
            hub._running = False  # stop after second call
            return None

        mock_queue.process_next = fake_process

        with patch.dict(sys.modules, {
            "src.task_queue": MagicMock(task_queue=mock_queue),
            "src.event_bus": MagicMock(event_bus=MagicMock(emit=AsyncMock())),
        }):
            await hub._queue_processor_loop()

        assert call_count == 2


class TestGetStatus:
    def test_status_when_stopped(self):
        from src.automation_hub import AutomationHub
        hub = AutomationHub()
        status = hub.get_status()
        assert status["running"] is False
        assert status["queue_processor"] == "stopped"

    def test_status_with_subsystem_errors(self):
        from src.automation_hub import AutomationHub
        hub = AutomationHub()
        hub._running = True
        hub._started_at = 1000.0

        with patch.dict(sys.modules, {
            "src.autonomous_loop": MagicMock(
                autonomous_loop=MagicMock(
                    get_status=MagicMock(side_effect=ImportError("no module"))
                )
            ),
            "src.task_scheduler": MagicMock(
                task_scheduler=MagicMock(
                    get_stats=MagicMock(side_effect=ImportError("no module"))
                )
            ),
            "src.task_queue": MagicMock(
                task_queue=MagicMock(
                    get_stats=MagicMock(side_effect=ImportError("no module"))
                )
            ),
        }):
            status = hub.get_status()

        assert status["running"] is True
        assert "error" in status["autonomous_loop"]
        assert "error" in status["task_scheduler"]
        assert "error" in status["task_queue"]
