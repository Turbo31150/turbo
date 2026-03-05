"""JARVIS Autonomous Loop — Self-managing background agent.

Runs continuously, performing health checks, GPU monitoring, drift rerouting,
and auto-optimization without human intervention.

Includes cron-like scheduling: tasks can run at specific hours/minutes/weekdays.

Usage:
    from src.autonomous_loop import autonomous_loop
    asyncio.create_task(autonomous_loop.start())  # in FastAPI startup
    autonomous_loop.stop()                         # graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Awaitable

logger = logging.getLogger("jarvis.autonomous")


@dataclass
class CronSchedule:
    """Cron-like schedule: hour, minute, weekdays (0=Mon..6=Sun)."""
    hour: int | None = None     # 0-23, None = any
    minute: int | None = None   # 0-59, None = any
    weekdays: list[int] | None = None  # [0..6], None = every day

    def matches_now(self) -> bool:
        now = datetime.now()
        if self.weekdays is not None and now.weekday() not in self.weekdays:
            return False
        if self.hour is not None and now.hour != self.hour:
            return False
        if self.minute is not None and now.minute != self.minute:
            return False
        return True


@dataclass
class AutonomousTask:
    """A recurring autonomous task."""
    name: str
    fn: Callable[[], Awaitable[dict[str, Any]]]
    interval_s: float = 30.0
    last_run: float = 0.0
    last_result: dict[str, Any] = field(default_factory=dict)
    run_count: int = 0
    fail_count: int = 0
    enabled: bool = True
    cron: CronSchedule | None = None  # if set, only runs when cron matches


class AutonomousLoop:
    """Self-managing background loop for JARVIS cluster."""

    def __init__(self, tick_interval: float = 10.0) -> None:
        self._tick = tick_interval
        self._tasks: dict[str, AutonomousTask] = {}
        self._running = False
        self._loop_task: asyncio.Task | None = None
        self._event_log: list[dict[str, Any]] = []
        self._max_log = 200
        self._register_builtin_tasks()

    def _register_builtin_tasks(self) -> None:
        """Register default autonomous tasks."""
        self.register("health_check", self._task_health_check, interval_s=30.0)
        self.register("gpu_monitor", self._task_gpu_monitor, interval_s=60.0)
        self.register("drift_reroute", self._task_drift_reroute, interval_s=120.0)
        self.register("budget_alert", self._task_budget_alert, interval_s=300.0)
        self.register("auto_tune_sample", self._task_auto_tune_sample, interval_s=60.0)
        self.register("self_heal", self._task_self_heal, interval_s=90.0)
        self.register("proactive_suggest", self._task_proactive, interval_s=600.0)
        # Cron-scheduled tasks
        self.register("db_backup", self._task_db_backup, interval_s=3600,
                       cron=CronSchedule(hour=3, minute=0))  # daily 3h00
        self.register("weekly_cleanup", self._task_weekly_cleanup, interval_s=86400,
                       cron=CronSchedule(hour=4, minute=0, weekdays=[6]))  # Sunday 4h00

        # ── v2.0 Autonomous tasks ────────────────────────────────────────
        self.register("brain_auto_learn", self._task_brain_auto_learn, interval_s=1800)  # 30min
        self.register("improve_cycle", self._task_improve_cycle, interval_s=86400,
                       cron=CronSchedule(hour=2, minute=0))  # daily 2h00
        self.register("predict_next_actions", self._task_predict_next, interval_s=300)  # 5min
        self.register("auto_develop", self._task_auto_develop, interval_s=86400,
                       cron=CronSchedule(hour=3, minute=30))  # daily 3h30

    def register(self, name: str, fn: Callable[[], Awaitable[dict[str, Any]]],
                 interval_s: float = 30.0, cron: CronSchedule | None = None) -> None:
        """Register a new autonomous task. If cron is set, only runs when cron matches."""
        self._tasks[name] = AutonomousTask(name=name, fn=fn, interval_s=interval_s, cron=cron)

    async def dynamic_register(self, name: str, fn: Callable[[], Awaitable[dict[str, Any]]],
                               interval_s: float = 60.0, cron: CronSchedule | None = None) -> None:
        """Register a task dynamically at runtime (from brain, telegram, etc.)."""
        self._tasks[name] = AutonomousTask(name=name, fn=fn, interval_s=interval_s, cron=cron)
        self._log_event(name, "info", f"Dynamic task registered (interval={interval_s}s)")
        try:
            from src.event_bus import event_bus
            await event_bus.emit("autonomous.task_created", {"name": name, "interval_s": interval_s})
        except Exception:
            pass
        logger.info("Dynamic task registered: %s (interval=%ds)", name, interval_s)

    def unregister(self, name: str) -> None:
        """Remove a task."""
        self._tasks.pop(name, None)

    def enable(self, name: str, enabled: bool = True) -> None:
        """Enable/disable a task."""
        if name in self._tasks:
            self._tasks[name].enabled = enabled

    async def start(self) -> None:
        """Start the autonomous loop."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("Autonomous loop started (tick=%.1fs, %d tasks)", self._tick, len(self._tasks))

    def stop(self) -> None:
        """Stop the loop."""
        self._running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
        logger.info("Autonomous loop stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _run_loop(self) -> None:
        """Main loop — check which tasks are due and run them."""
        while self._running:
            now = time.time()
            due_tasks = [
                t for t in self._tasks.values()
                if t.enabled and (now - t.last_run) >= t.interval_s
                and (t.cron is None or t.cron.matches_now())
            ]
            if due_tasks:
                results = await asyncio.gather(
                    *[self._run_task(t) for t in due_tasks],
                    return_exceptions=True,
                )
                for task, result in zip(due_tasks, results):
                    if isinstance(result, Exception):
                        task.fail_count += 1
                        self._log_event(task.name, "error", str(result))
                        logger.warning("Autonomous task %s failed: %s", task.name, result)
            try:
                await asyncio.sleep(self._tick)
            except asyncio.CancelledError:
                break

    async def _run_task(self, task: AutonomousTask) -> dict[str, Any]:
        """Execute a single task, update stats."""
        task.last_run = time.time()
        task.run_count += 1
        try:
            result = await asyncio.wait_for(task.fn(), timeout=30.0)
            task.last_result = result
            if result.get("alert"):
                self._log_event(task.name, "alert", result["alert"])
            return result
        except asyncio.TimeoutError:
            task.fail_count += 1
            self._log_event(task.name, "timeout", f"{task.name} timed out")
            return {"error": "timeout"}
        except Exception as e:
            task.fail_count += 1
            self._log_event(task.name, "error", str(e))
            raise

    def _log_event(self, task: str, level: str, message: str) -> None:
        """Log an event to the in-memory ring buffer."""
        self._event_log.append({
            "ts": time.time(),
            "task": task,
            "level": level,
            "message": message,
        })
        if len(self._event_log) > self._max_log:
            self._event_log = self._event_log[-self._max_log:]

    # ── Built-in tasks ──────────────────────────────────────────────────

    @staticmethod
    async def _task_health_check() -> dict[str, Any]:
        """Check cluster health via orchestrator_v2."""
        from src.orchestrator_v2 import orchestrator_v2
        score = orchestrator_v2.health_check()
        alerts = orchestrator_v2.get_alerts()
        result: dict[str, Any] = {"health_score": score, "alert_count": len(alerts)}
        if score < 50:
            result["alert"] = f"Cluster health critical: {score}/100"
        return result

    @staticmethod
    async def _task_gpu_monitor() -> dict[str, Any]:
        """Monitor GPU temperatures and VRAM."""
        import subprocess
        try:
            r = await asyncio.to_thread(
                subprocess.run,
                ["nvidia-smi", "--query-gpu=index,temperature.gpu,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0:
                return {"error": "nvidia-smi failed"}
            gpus = []
            alert = None
            for line in r.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    temp = int(parts[1])
                    gpu = {
                        "index": int(parts[0]),
                        "temp_c": temp,
                        "used_mb": int(parts[2]),
                        "total_mb": int(parts[3]),
                        "util_pct": int(parts[4]),
                    }
                    gpus.append(gpu)
                    if temp >= 85:
                        alert = f"GPU {parts[0]} critical temp: {temp}C"
                    elif temp >= 75 and alert is None:
                        alert = f"GPU {parts[0]} high temp: {temp}C"
            result: dict[str, Any] = {"gpus": gpus}
            if alert:
                result["alert"] = alert
            return result
        except FileNotFoundError:
            return {"error": "nvidia-smi not found"}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def _task_drift_reroute() -> dict[str, Any]:
        """Check drift and suggest rerouting if models degraded."""
        from src.drift_detector import drift_detector
        from src.orchestrator_v2 import orchestrator_v2
        degraded = drift_detector.get_degraded_models()
        if not degraded:
            return {"degraded": [], "action": "none"}
        # Get alternative routing for code tasks
        chain = orchestrator_v2.fallback_chain("code", exclude=set(degraded))
        result: dict[str, Any] = {
            "degraded": degraded,
            "suggested_chain": chain,
            "action": "reroute_suggested",
        }
        if len(degraded) >= 3:
            result["alert"] = f"{len(degraded)} models degraded: {', '.join(degraded)}"
        return result

    @staticmethod
    async def _task_budget_alert() -> dict[str, Any]:
        """Alert if token budget is high."""
        from src.orchestrator_v2 import orchestrator_v2
        budget = orchestrator_v2.get_budget_report()
        total = budget.get("total_tokens", 0)
        rate = budget.get("tokens_per_minute", 0)
        result: dict[str, Any] = {"total_tokens": total, "tokens_per_minute": rate}
        if total > 500_000:
            result["alert"] = f"High token usage: {total:,} tokens ({rate:.0f}/min)"
        return result

    @staticmethod
    async def _task_self_heal() -> dict[str, Any]:
        """Detect offline nodes and attempt recovery."""
        import httpx

        probes = {
            "M1": "http://127.0.0.1:1234/api/v1/models",
            "OL1": "http://127.0.0.1:11434/api/tags",
            "M2": "http://192.168.1.26:1234/api/v1/models",
            "M3": "http://192.168.1.113:1234/api/v1/models",
        }
        online = []
        offline = []
        healed = []

        async with httpx.AsyncClient(timeout=3) as client:
            for node, url in probes.items():
                try:
                    r = await client.get(url)
                    if r.status_code == 200:
                        online.append(node)
                    else:
                        offline.append(node)
                except Exception:
                    offline.append(node)

        # Attempt self-heal for local nodes
        for node in offline:
            if node == "OL1":
                try:
                    import subprocess
                    await asyncio.to_thread(
                        subprocess.run,
                        ["powershell", "-NoProfile", "-Command",
                         "Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden"],
                        capture_output=True, timeout=5,
                    )
                    healed.append(node)
                except Exception:
                    pass

        # Notify if critical
        result: dict[str, Any] = {
            "online": online, "offline": offline, "healed": healed,
        }
        if offline:
            try:
                from src.notifier import notifier
                msg = f"Noeuds offline: {', '.join(offline)}"
                if healed:
                    msg += f" — tentative restart: {', '.join(healed)}"
                level = "critical" if len(offline) >= 3 else "warning"
                await notifier.alert(msg, level=level, source="self_heal")
            except Exception:
                pass
            result["alert"] = f"{len(offline)} nodes offline"

        # Record in orchestrator_v2
        try:
            from src.orchestrator_v2 import orchestrator_v2
            for node in offline:
                orchestrator_v2.record_call(node, latency_ms=0, success=False)
        except Exception:
            pass

        return result

    @staticmethod
    async def _task_auto_tune_sample() -> dict[str, Any]:
        """Take a resource sample for auto-tuning."""
        from src.auto_tune import auto_tune
        sample = auto_tune.sample_resources()
        return {"sample": sample}

    @staticmethod
    async def _task_proactive() -> dict[str, Any]:
        """Run proactive analysis + auto-execute high-confidence suggestions."""
        from src.proactive_agent import proactive_agent
        report = await proactive_agent.analyze_and_execute()
        result: dict[str, Any] = {
            "suggestions": report["total"],
            "auto_executed": len(report["executed"]),
            "skipped": len(report["skipped"]),
        }
        if report["executed"]:
            try:
                from src.notifier import notifier
                names = [e["key"] for e in report["executed"]]
                await notifier.info(
                    f"Auto-execute: {', '.join(names)}", source="proactive"
                )
            except Exception:
                pass
        # Still notify high-priority non-executed suggestions
        suggestions = proactive_agent.get_last()
        high = [s for s in suggestions if s.get("priority") == "high"]
        if high:
            try:
                from src.notifier import notifier
                for s in high[:2]:
                    await notifier.warn(s["message"], source="proactive")
            except Exception:
                pass
            result["alert"] = f"{len(high)} high-priority suggestions"
        return result

    @staticmethod
    async def _task_db_backup() -> dict[str, Any]:
        """Backup databases (daily at 3h00)."""
        try:
            from src.database import backup_database
            path = await asyncio.to_thread(backup_database)
            return {"backup_path": str(path)}
        except Exception as e:
            return {"error": str(e), "alert": f"DB backup failed: {e}"}

    @staticmethod
    async def _task_weekly_cleanup() -> dict[str, Any]:
        """Weekly cleanup: old task queue entries, DB maintenance, log rotation."""
        results = {}
        try:
            from src.task_queue import task_queue
            cleaned = task_queue.cleanup(days=7)
            results["task_queue_cleaned"] = cleaned
        except Exception as e:
            results["task_queue_error"] = str(e)

        try:
            from src.database import auto_maintenance
            await asyncio.to_thread(auto_maintenance, True)
            results["db_maintenance"] = "done"
        except Exception as e:
            results["db_maintenance_error"] = str(e)

        return results

    # ── v2.0 Autonomous tasks ────────────────────────────────────────────

    @staticmethod
    async def _task_brain_auto_learn() -> dict[str, Any]:
        """Auto-learn: detect patterns and create skills (every 30min)."""
        try:
            from src.brain import analyze_and_learn
            report = analyze_and_learn(auto_create=True, min_confidence=0.7)
            result: dict[str, Any] = {
                "patterns_found": report["patterns_found"],
                "skills_created": report["skills_created"],
            }
            if report["skills_created"]:
                try:
                    from src.event_bus import event_bus
                    for name in report["skills_created"]:
                        await event_bus.emit("brain.skill_created", {"name": name})
                except Exception:
                    pass
                result["alert"] = f"Brain created {len(report['skills_created'])} skills"
            return result
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def _task_improve_cycle() -> dict[str, Any]:
        """Run improve loop cycles (daily 2h00 AM)."""
        try:
            import subprocess
            r = await asyncio.to_thread(
                subprocess.run,
                ["uv", "run", "python", "canvas/improve_loop.py"],
                capture_output=True, text=True, timeout=600,
                cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
            )
            output = r.stdout[-500:] if r.stdout else ""
            result: dict[str, Any] = {
                "returncode": r.returncode,
                "output_tail": output,
            }
            try:
                from src.event_bus import event_bus
                await event_bus.emit("improve.cycle_done", {"returncode": r.returncode})
            except Exception:
                pass
            if r.returncode != 0:
                result["alert"] = f"Improve cycle failed: {r.stderr[-200:]}"
            return result
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def _task_predict_next() -> dict[str, Any]:
        """Pre-warm predictions for likely next user actions (every 5min)."""
        try:
            from src.prediction_engine import prediction_engine
            await prediction_engine.pre_warm()
            predictions = prediction_engine.predict_next(n=3)
            return {"predictions": len(predictions), "top": predictions[:2]}
        except ImportError:
            return {"status": "prediction_engine not yet available"}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def _task_auto_develop() -> dict[str, Any]:
        """Auto-develop: analyze gaps + generate commands (daily 3h30)."""
        try:
            from src.auto_developer import auto_developer
            report = await auto_developer.run_cycle(max_gaps=5)
            result: dict[str, Any] = {
                "gaps": report["gaps"],
                "registered": report["registered"],
            }
            if report["registered"] > 0:
                result["alert"] = f"AutoDev: {report['registered']} new commands created"
            return result
        except Exception as e:
            return {"error": str(e)}

    # ── Status & API ────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Return full status of the autonomous loop."""
        tasks_info = {}
        for name, t in self._tasks.items():
            tasks_info[name] = {
                "enabled": t.enabled,
                "interval_s": t.interval_s,
                "run_count": t.run_count,
                "fail_count": t.fail_count,
                "last_run": t.last_run,
                "last_result": t.last_result,
            }
        return {
            "running": self._running,
            "tick_interval_s": self._tick,
            "tasks": tasks_info,
            "event_count": len(self._event_log),
            "recent_events": self._event_log[-10:],
        }

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent events."""
        return self._event_log[-limit:]


# Global singleton
autonomous_loop = AutonomousLoop()
