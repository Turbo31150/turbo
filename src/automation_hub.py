"""JARVIS Automation Hub — Central orchestration wiring.

Connects autonomous_loop + task_scheduler + task_queue + domino_executor
into a single entry point started from FastAPI lifespan.

Usage:
    from src.automation_hub import automation_hub
    await automation_hub.start()   # in FastAPI startup
    await automation_hub.stop()    # in FastAPI shutdown
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("jarvis.automation_hub")


class AutomationHub:
    """Wires all orchestration subsystems together."""

    def __init__(self) -> None:
        self._running = False
        self._queue_task: asyncio.Task | None = None
        self._started_at = 0.0

    async def start(self) -> dict[str, str]:
        """Start all automation subsystems. Returns status per subsystem."""
        if self._running:
            return {"status": "already_running"}
        self._running = True
        self._started_at = time.time()
        report: dict[str, str] = {}

        # 1. Autonomous loop (already has real task implementations)
        try:
            from src.autonomous_loop import autonomous_loop
            await autonomous_loop.start()
            report["autonomous_loop"] = f"ok ({len(autonomous_loop._tasks)} tasks)"
        except Exception as e:
            logger.warning("autonomous_loop start failed: %s", e)
            report["autonomous_loop"] = f"error: {e}"

        # 2. Task scheduler — register handlers then start
        try:
            from src.task_scheduler import task_scheduler
            self._register_scheduler_handlers(task_scheduler)
            await task_scheduler.start(check_interval=10.0)
            stats = task_scheduler.get_stats()
            report["task_scheduler"] = (
                f"ok ({stats['enabled_jobs']} jobs, "
                f"{len(stats['registered_handlers'])} handlers)"
            )
        except Exception as e:
            logger.warning("task_scheduler start failed: %s", e)
            report["task_scheduler"] = f"error: {e}"

        # 3. Task queue — background processor loop
        try:
            self._queue_task = asyncio.create_task(self._queue_processor_loop())
            report["task_queue"] = "ok (processor started)"
        except Exception as e:
            logger.warning("task_queue processor failed: %s", e)
            report["task_queue"] = f"error: {e}"

        # 4. Seed default scheduler jobs if empty
        try:
            from src.task_scheduler import task_scheduler
            self._seed_default_jobs(task_scheduler)
        except Exception as e:
            logger.warning("job seeding failed: %s", e)

        logger.info("Automation Hub started: %s", report)
        return report

    async def stop(self) -> None:
        """Graceful shutdown of all subsystems."""
        self._running = False

        # Stop queue processor
        if self._queue_task and not self._queue_task.done():
            self._queue_task.cancel()
            try:
                await self._queue_task
            except asyncio.CancelledError:
                pass
            self._queue_task = None

        # Stop task scheduler
        try:
            from src.task_scheduler import task_scheduler
            await task_scheduler.stop()
        except Exception as e:
            logger.warning("task_scheduler stop: %s", e)

        # Stop autonomous loop
        try:
            from src.autonomous_loop import autonomous_loop
            autonomous_loop.stop()
        except Exception as e:
            logger.warning("autonomous_loop stop: %s", e)

        logger.info("Automation Hub stopped")

    # ── Default jobs seeding ────────────────────────────────────────────

    @staticmethod
    def _seed_default_jobs(scheduler) -> None:
        """Seed default scheduled jobs if the scheduler DB is empty."""
        existing = scheduler.list_jobs()
        if existing:
            return  # Already has jobs

        default_jobs = [
            ("Cluster health check", "health_check", 120, {}),
            ("GPU temperature monitor", "gpu_monitor", 300, {}),
            ("Self-heal offline nodes", "self_heal", 600, {}),
            ("Database backup (daily)", "backup", 86400, {}),
            ("Weekly cleanup", "cleanup", 604800, {}),
        ]
        for name, action, interval, params in default_jobs:
            scheduler.add_job(name=name, action=action,
                              interval_s=interval, params=params)
        logger.info("Seeded %d default scheduler jobs", len(default_jobs))

    # ── Queue processor ──────────────────────────────────────────────────

    async def _queue_processor_loop(self) -> None:
        """Background loop: process pending tasks from the queue."""
        from src.task_queue import task_queue

        while self._running:
            try:
                result = await task_queue.process_next()
                if result:
                    logger.info(
                        "Queue processed: %s [%s] -> %s",
                        result["id"], result["task_type"], result["status"],
                    )
                    # Emit event for dashboard
                    try:
                        from src.event_bus import event_bus
                        await event_bus.emit("queue.task_done", {
                            "id": result["id"],
                            "status": result["status"],
                            "node": result.get("node", ""),
                        })
                    except Exception:
                        pass
                    # Short delay between tasks to avoid saturating nodes
                    await asyncio.sleep(1.0)
                else:
                    # No pending tasks — wait longer
                    await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Queue processor error: %s", e)
                await asyncio.sleep(10.0)

    # ── Scheduler handlers ───────────────────────────────────────────────

    @staticmethod
    def _register_scheduler_handlers(scheduler) -> None:
        """Register action handlers for all known job types."""

        async def _handle_dispatch(params: dict) -> str:
            """Dispatch a prompt to the cluster."""
            from src.dispatch_engine import DispatchEngine
            engine = DispatchEngine()
            result = await engine.dispatch(
                params.get("prompt", ""),
                pattern=params.get("pattern", "simple"),
            )
            return f"{result.get('node', '?')}: {str(result.get('content', ''))[:200]}"

        async def _handle_domino(params: dict) -> str:
            """Run a domino pipeline."""
            from src.domino_pipelines import find_domino
            from src.domino_executor import DominoExecutor
            domino = find_domino(params.get("pipeline_id", ""))
            if not domino:
                return f"Pipeline not found: {params.get('pipeline_id')}"
            executor = DominoExecutor()
            result = await asyncio.to_thread(executor.run, domino)
            return f"passed={result.get('passed', 0)} failed={result.get('failed', 0)}"

        async def _handle_health_check(params: dict) -> str:
            """Run cluster health check."""
            from src.autonomous_loop import autonomous_loop
            result = await autonomous_loop._task_health_check()
            score = result.get("health_score", "?")
            return f"health={score}/100 alerts={result.get('alert_count', 0)}"

        async def _handle_backup(params: dict) -> str:
            """Run database backup."""
            from src.autonomous_loop import autonomous_loop
            result = await autonomous_loop._task_db_backup()
            return result.get("backup_path", result.get("error", "unknown"))

        async def _handle_gpu_monitor(params: dict) -> str:
            """GPU temperature/VRAM check."""
            from src.autonomous_loop import autonomous_loop
            result = await autonomous_loop._task_gpu_monitor()
            gpus = result.get("gpus", [])
            if gpus:
                temps = ", ".join(f"GPU{g['index']}:{g['temp_c']}C" for g in gpus)
                return temps
            return result.get("error", "no GPU data")

        async def _handle_self_heal(params: dict) -> str:
            """Self-heal offline nodes."""
            from src.autonomous_loop import autonomous_loop
            result = await autonomous_loop._task_self_heal()
            return (
                f"online={result.get('online', [])} "
                f"offline={result.get('offline', [])} "
                f"healed={result.get('healed', [])}"
            )

        async def _handle_queue_enqueue(params: dict) -> str:
            """Enqueue a task into the priority queue."""
            from src.task_queue import task_queue
            task_id = task_queue.enqueue(
                prompt=params.get("prompt", ""),
                task_type=params.get("task_type", "code"),
                priority=params.get("priority", 5),
            )
            return f"enqueued: {task_id}"

        async def _handle_notify(params: dict) -> str:
            """Send a notification."""
            try:
                from src.notifier import notifier
                await notifier.info(
                    params.get("message", "scheduled notification"),
                    source="scheduler",
                )
                return "notified"
            except Exception as e:
                return f"notify failed: {e}"

        async def _handle_cleanup(params: dict) -> str:
            """Run cleanup tasks."""
            from src.autonomous_loop import autonomous_loop
            result = await autonomous_loop._task_weekly_cleanup()
            return str(result)

        async def _handle_self_improve(params: dict) -> str:
            """Run self-improvement cycle."""
            from src.self_improve_engine import self_improve_engine
            report = await self_improve_engine.run_cycle()
            return f"cycle={report['cycle']} actions={report['actions_taken']}"

        async def _handle_noop(params: dict) -> str:
            """No-op handler for test jobs."""
            return "noop"

        # Register all handlers
        handlers = {
            "dispatch": _handle_dispatch,
            "domino": _handle_domino,
            "health_check": _handle_health_check,
            "backup": _handle_backup,
            "gpu_monitor": _handle_gpu_monitor,
            "self_heal": _handle_self_heal,
            "self_improve": _handle_self_improve,
            "queue_enqueue": _handle_queue_enqueue,
            "notify": _handle_notify,
            "cleanup": _handle_cleanup,
            "noop": _handle_noop,
        }
        for action, handler in handlers.items():
            scheduler.register_handler(action, handler)

        logger.info("Registered %d scheduler handlers: %s", len(handlers), list(handlers.keys()))

    # ── Status API ───────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Full status report of all subsystems."""
        status: dict[str, Any] = {
            "running": self._running,
            "uptime_s": round(time.time() - self._started_at, 1) if self._started_at else 0,
        }

        try:
            from src.autonomous_loop import autonomous_loop
            loop_status = autonomous_loop.get_status()
            status["autonomous_loop"] = {
                "running": loop_status["running"],
                "task_count": len(loop_status["tasks"]),
                "event_count": loop_status["event_count"],
            }
        except Exception as e:
            status["autonomous_loop"] = {"error": str(e)}

        try:
            from src.task_scheduler import task_scheduler
            status["task_scheduler"] = task_scheduler.get_stats()
        except Exception as e:
            status["task_scheduler"] = {"error": str(e)}

        try:
            from src.task_queue import task_queue
            status["task_queue"] = task_queue.get_stats()
        except Exception as e:
            status["task_queue"] = {"error": str(e)}

        status["queue_processor"] = (
            "running" if self._queue_task and not self._queue_task.done()
            else "stopped"
        )

        return status


# ── Singleton ────────────────────────────────────────────────────────────────
automation_hub = AutomationHub()
