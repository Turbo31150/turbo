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

        # 5. Initialize decision engine
        try:
            from src.decision_engine import decision_engine
            report["decision_engine"] = (
                f"ok ({decision_engine.get_stats()['rules_count']} rules, "
                f"{decision_engine.get_stats()['handlers_count']} handlers)"
            )
        except Exception as e:
            logger.warning("decision_engine init failed: %s", e)
            report["decision_engine"] = f"error: {e}"

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

        async def _handle_auto_improve(params: dict) -> str:
            """Run production auto-improve cycle (validate + fix)."""
            import subprocess as _sp
            try:
                r = _sp.run(
                    ["uv", "run", "python", "scripts/production_auto_improve.py", "--once"],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(Path(__file__).resolve().parent.parent),
                )
                if r.returncode == 0:
                    import json as _j
                    try:
                        data = _j.loads(r.stdout)
                        return f"grade={data.get('grade','?')} score={data.get('score','?')} fixes={len(data.get('fixes',[]))}"
                    except _j.JSONDecodeError:
                        return f"completed (rc=0)"
                return f"failed rc={r.returncode}: {r.stderr[:200]}"
            except _sp.TimeoutExpired:
                return "timeout (120s)"
            except Exception as e:
                return f"error: {e}"

        async def _handle_auto_scan(params: dict) -> str:
            """Run autonomous system scan (cluster + DB + GPU + services)."""
            import subprocess as _sp
            try:
                r = _sp.run(
                    ["uv", "run", "python", "scripts/jarvis_auto_scan.py", "--once"],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(Path(__file__).resolve().parent.parent),
                )
                if r.returncode == 0:
                    import json as _j
                    try:
                        data = _j.loads(r.stdout)
                        return f"health={data.get('health_score','?')} issues={len(data.get('issues',[]))}"
                    except _j.JSONDecodeError:
                        return "completed (rc=0)"
                return f"failed rc={r.returncode}: {r.stderr[:200]}"
            except _sp.TimeoutExpired:
                return "timeout (120s)"
            except Exception as e:
                return f"error: {e}"

        async def _handle_noop(params: dict) -> str:
            """No-op handler for test jobs."""
            return "noop"

        async def _handle_trading_scan(params: dict) -> str:
            """Trigger trading scan via event bus."""
            from src.event_bus import event_bus
            await event_bus.emit("trading.scan_requested", params)
            return "scan_triggered"

        async def _handle_brain_analyze(params: dict) -> str:
            """Run brain pattern analysis."""
            from src.brain import analyze_and_learn
            result = analyze_and_learn()
            return f"patterns={len(result) if isinstance(result, list) else result}"

        async def _handle_db_vacuum(params: dict) -> str:
            """Optimize database."""
            from src.database import get_connection
            get_connection().execute("PRAGMA optimize")
            return "optimized"

        async def _handle_drift_check(params: dict) -> str:
            """Trigger drift check via event bus."""
            from src.event_bus import event_bus
            await event_bus.emit("quality.drift_check", params)
            return "drift_check_triggered"

        async def _handle_security_scan(params: dict) -> str:
            """Trigger security scan via event bus."""
            from src.event_bus import event_bus
            await event_bus.emit("security.scan_requested", params)
            return "security_scan_triggered"

        async def _handle_skill(params: dict) -> str:
            """Execute a scheduled skill."""
            skill_name = params.get("skill", "unknown")
            from src.event_bus import event_bus
            await event_bus.emit("skill.execute", {"skill": skill_name})
            return f"skill={skill_name}"

        async def _handle_cowork_batch(params: dict) -> str:
            """Run a batch of cowork improvement scripts."""
            import subprocess
            import sys
            from pathlib import Path
            scripts = params.get("scripts", [
                "auto_monitor", "auto_healer", "auto_learner",
                "autonomous_health_guard", "adaptive_load_balancer",
            ])
            cowork_dir = Path(__file__).parent.parent / "cowork" / "dev"
            results = []
            for name in scripts:
                script = cowork_dir / f"{name}.py"
                if not script.exists():
                    results.append(f"{name}: NOT_FOUND")
                    continue
                try:
                    r = await asyncio.to_thread(
                        subprocess.run,
                        [sys.executable, str(script), "--once"],
                        capture_output=True, text=True, timeout=30,
                        cwd=str(cowork_dir),
                    )
                    status = "OK" if r.returncode == 0 else f"FAIL({r.returncode})"
                    results.append(f"{name}: {status}")
                except subprocess.TimeoutExpired:
                    results.append(f"{name}: TIMEOUT")
                except Exception as e:
                    results.append(f"{name}: ERROR({e})")
            return " | ".join(results)

        async def _handle_self_diagnostic(params: dict) -> str:
            """Run self-diagnostic analysis."""
            from src.self_diagnostic import self_diagnostic
            result = await self_diagnostic.diagnose()
            return f"health={result.get('health_score','?')} issues={len(result.get('issues',[]))} recs={len(result.get('recommendations',[]))}"

        async def _handle_cache_clear(params: dict) -> str:
            """Clear dispatch cache."""
            from src.dispatch_engine import _dispatch_cache
            _dispatch_cache.clear()
            return "cache cleared"

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
            "auto_improve": _handle_auto_improve,
            "auto_scan": _handle_auto_scan,
            "trading_scan": _handle_trading_scan,
            "brain_analyze": _handle_brain_analyze,
            "db_vacuum": _handle_db_vacuum,
            "drift_check": _handle_drift_check,
            "security_scan": _handle_security_scan,
            "skill": _handle_skill,
            "cowork_batch": _handle_cowork_batch,
            "self_diagnostic": _handle_self_diagnostic,
            "cache_clear": _handle_cache_clear,
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

        try:
            from src.decision_engine import decision_engine
            status["decision_engine"] = decision_engine.get_stats()
        except Exception as e:
            status["decision_engine"] = {"error": str(e)}

        return status


# ── Singleton ────────────────────────────────────────────────────────────────
automation_hub = AutomationHub()
