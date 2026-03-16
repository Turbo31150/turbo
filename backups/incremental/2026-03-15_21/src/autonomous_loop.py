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


__all__ = [
    "AutonomousLoop",
    "AutonomousTask",
    "CronSchedule",
]

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
        self.register("auto_tune_sample", self._task_auto_tune_sample, interval_s=300.0)
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

        # ── v3.1 Self-improvement — autonomous cluster optimization ───────
        self.register("self_improve", self._task_self_improve, interval_s=600)  # 10min

        # ── v3.2 Self-improve feedback — weight change → scheduling re-eval ──
        self.register("self_improve_feedback", self._task_self_improve_feedback,
                       interval_s=660)  # 11min (offset from self_improve)

        # ── v3.0 System automation — IA-driven system management ─────────
        self.register("zombie_gc", self._task_zombie_gc, interval_s=600)  # 10min
        self.register("vram_audit", self._task_vram_audit, interval_s=600)  # 10min
        self.register("conversation_checkpoint", self._task_conv_checkpoint, interval_s=1800)  # 30min
        self.register("cluster_dispatch_check", self._task_cluster_dispatch, interval_s=120)  # 2min
        self.register("system_audit_escalation", self._task_system_audit, interval_s=600)  # 10min

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
        except Exception as e:
            logger.error("Error emitting event: %s", str(e))
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
            logger.error("nvidia-smi not found")
            return {"error": "nvidia-smi not found"}
        except Exception as e:
            logger.error(str(e))
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

        async with httpx.AsyncClient(timeout=12) as client:
            for node, url in probes.items():
                ok = False
                for attempt in range(2):
                    try:
                        r = await client.get(url, timeout=5.0)
                        if r.status_code == 200:
                            ok = True
                            break
                    except (httpx.TimeoutException, httpx.ConnectError):
                        if attempt == 0:
                            await asyncio.sleep(0.5)
                            continue
                    except Exception:
                        break
                if ok:
                    online.append(node)
                else:
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
                except Exception as e:
                    logger.error(f"Error healing node {node}: {str(e)}")
                    raise

        # Notify if critical — skip nodes with circuit already OPEN
        result: dict[str, Any] = {
            "online": online, "offline": offline, "healed": healed,
        }
        new_offline = offline[:]
        try:
            from src.adaptive_router import adaptive_router, CircuitState
            new_offline = [n for n in offline
                          if n not in adaptive_router.circuits
                          or adaptive_router.circuits[n].state == CircuitState.CLOSED]
        except Exception:
            pass
        if new_offline:
            try:
                from src.notifier import notifier
                msg = f"Noeuds offline: {', '.join(new_offline)}"
                if healed:
                    msg += f" — tentative restart: {', '.join(healed)}"
                level = "critical" if len(new_offline) >= 3 else "warning"
                await notifier.alert(msg, level=level, source="self_heal")
            except Exception as e:
                logger.error(f"Error during self-heal: {e}")
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
        sample = auto_tune.sample()
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
                capture_output=True, text=True,
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

    # ── v3.1 Self-improvement task ──────────────────────────────────

    @staticmethod
    async def _task_self_improve() -> dict[str, Any]:
        """Run self-improvement cycle: analyze metrics, adjust weights, optimize strategies."""
        try:
            from src.self_improve_engine import self_improve_engine
            report = await self_improve_engine.run_cycle()
            result: dict[str, Any] = {
                "cycle": report["cycle"],
                "actions": report["actions_taken"],
                "nodes": report.get("nodes_analyzed", 0),
            }
            if report["actions_taken"] > 0:
                result["alert"] = (
                    f"Self-improve: {report['actions_taken']} actions "
                    f"({', '.join(a['type'] for a in report.get('actions', [])[:3])})"
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    # ── v3.2 Self-improve feedback ──────────────────────────────────

    async def _task_self_improve_feedback(self) -> dict[str, Any]:
        """Run self-improve cycle and feed weight changes back into scheduling.

        If any node weight changed by >0.1, emit an event and re-evaluate
        task scheduling priorities (e.g. increase health_check frequency
        for volatile nodes).
        """
        try:
            from src.self_improve_engine import self_improve_engine
            from src.adaptive_router import get_router
        except ImportError as e:
            return {"error": f"import failed: {e}"}

        # Snapshot weights before
        router = get_router()
        weights_before: dict[str, float] = {}
        for node, health in router.health.items():
            weights_before[node] = health.base_weight

        # Run improvement cycle
        try:
            report = await self_improve_engine.run_cycle()
        except Exception as e:
            return {"error": f"run_cycle failed: {e}"}

        # Snapshot weights after and detect significant changes
        weight_deltas: dict[str, dict[str, float]] = {}
        for node, health in router.health.items():
            old_w = weights_before.get(node, health.base_weight)
            new_w = health.base_weight
            delta = abs(new_w - old_w)
            if delta > 0.1:
                weight_deltas[node] = {
                    "before": round(old_w, 2),
                    "after": round(new_w, 2),
                    "delta": round(new_w - old_w, 2),
                }

        result: dict[str, Any] = {
            "cycle": report.get("cycle", 0),
            "actions_taken": report.get("actions_taken", 0),
            "weight_changes": weight_deltas,
            "scheduling_adjusted": False,
        }

        if weight_deltas:
            logger.info(
                "Self-improve feedback: %d node(s) with significant weight change: %s",
                len(weight_deltas),
                ", ".join(f"{n} {d['before']}->{d['after']}" for n, d in weight_deltas.items()),
            )

            # Re-evaluate scheduling: boost health_check and drift_reroute frequency
            # for faster reaction to changed cluster topology
            if "health_check" in self._tasks:
                old_interval = self._tasks["health_check"].interval_s
                self._tasks["health_check"].interval_s = max(10.0, old_interval * 0.5)
                logger.info(
                    "Scheduling adjusted: health_check interval %.0fs -> %.0fs",
                    old_interval, self._tasks["health_check"].interval_s,
                )
            if "drift_reroute" in self._tasks:
                old_interval = self._tasks["drift_reroute"].interval_s
                self._tasks["drift_reroute"].interval_s = max(30.0, old_interval * 0.5)
                logger.info(
                    "Scheduling adjusted: drift_reroute interval %.0fs -> %.0fs",
                    old_interval, self._tasks["drift_reroute"].interval_s,
                )
            result["scheduling_adjusted"] = True

            # Emit event so other components (dashboard, notifier) can react
            try:
                from src.event_bus import event_bus
                await event_bus.emit("self_improve.weights_changed", {
                    "cycle": report.get("cycle", 0),
                    "deltas": weight_deltas,
                })
            except Exception as e:
                logger.warning("Failed to emit weights_changed event: %s", e)
        else:
            # No significant changes — restore default intervals if they were reduced
            if "health_check" in self._tasks and self._tasks["health_check"].interval_s < 30.0:
                self._tasks["health_check"].interval_s = 30.0
                logger.info("Scheduling restored: health_check interval -> 30s")
            if "drift_reroute" in self._tasks and self._tasks["drift_reroute"].interval_s < 120.0:
                self._tasks["drift_reroute"].interval_s = 120.0
                logger.info("Scheduling restored: drift_reroute interval -> 120s")

        return result

    # ── v3.0 System automation tasks ──────────────────────────────────

    @staticmethod
    async def _task_zombie_gc() -> dict[str, Any]:
        """Kill zombie Python processes (every 10min)."""
        import subprocess
        turbo = __import__("pathlib").Path("/home/turbo/jarvis-m1-ops")
        try:
            r = await asyncio.to_thread(
                subprocess.run,
                [__import__("sys").executable, str(turbo / "scripts" / "process_gc.py"), "--once"],
                capture_output=True, text=True, timeout=20,
                encoding="utf-8", errors="replace",
            )
            # Parse last line for killed count
            lines = (r.stdout or "").strip().split("\n")
            killed = 0
            for line in lines:
                if "killed" in line.lower():
                    import re
                    m = re.search(r"(\d+)\s+killed", line)
                    if m:
                        killed = int(m.group(1))
            result: dict[str, Any] = {"killed": killed, "returncode": r.returncode}
            if killed > 3:
                result["alert"] = f"Zombie GC killed {killed} processes"
            return result
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def _task_vram_audit() -> dict[str, Any]:
        """Monitor VRAM and pause cowork if critical (every 10min)."""
        import subprocess, json as _json
        turbo = __import__("pathlib").Path("/home/turbo/jarvis-m1-ops")
        try:
            r = await asyncio.to_thread(
                subprocess.run,
                [__import__("sys").executable, str(turbo / "scripts" / "vram_guard.py"), "--once", "--json"],
                capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
            )
            # Extract JSON from output (may have ANSI log lines before)
            text = r.stdout or ""
            data = {}
            if "{" in text:
                try:
                    data = _json.loads(text[text.find("{"):])
                except _json.JSONDecodeError:
                    pass
            vram_pct = data.get("max_vram_pct", 0)
            action = data.get("action", "unknown")
            result: dict[str, Any] = {"max_vram_pct": vram_pct, "action": action,
                                      "cowork_paused": data.get("cowork_paused", False)}
            if vram_pct >= 90:
                result["alert"] = f"VRAM critical: {vram_pct:.1f}% — cowork paused"
            elif vram_pct >= 85:
                result["alert"] = f"VRAM high: {vram_pct:.1f}%"
            return result
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def _task_conv_checkpoint() -> dict[str, Any]:
        """Summarize and GC old conversation checkpoints (every 30min)."""
        import subprocess
        turbo = __import__("pathlib").Path("/home/turbo/jarvis-m1-ops")
        script = turbo / "scripts" / "conversation_checkpoint.py"
        if not script.exists():
            return {"status": "script_not_found"}
        try:
            # GC old sessions (>7 days)
            r = await asyncio.to_thread(
                subprocess.run,
                [__import__("sys").executable, str(script), "--gc", "--days", "7"],
                capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
            )
            return {"gc_done": True, "returncode": r.returncode}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def _task_cluster_dispatch() -> dict[str, Any]:
        """Quick cluster health + auto-reroute if nodes offline (every 2min)."""
        import httpx
        probes = {
            "M1": "http://127.0.0.1:1234/api/v1/models",
            "OL1": "http://127.0.0.1:11434/api/tags",
            "WS": "http://127.0.0.1:9742/health",
            "Canvas": "http://127.0.0.1:18800/",
        }
        results: dict[str, str] = {}
        async with httpx.AsyncClient(timeout=10) as client:
            for name, url in probes.items():
                for attempt in range(2):
                    try:
                        r = await client.get(url, timeout=5.0)
                        results[name] = "up" if r.status_code == 200 else f"http_{r.status_code}"
                        break
                    except (httpx.TimeoutException, httpx.ConnectError):
                        if attempt == 0:
                            await asyncio.sleep(0.3)
                            continue
                        results[name] = "down"
                    except Exception:
                        results[name] = "down"
                        break
        offline = [n for n, s in results.items() if s != "up"]
        result: dict[str, Any] = {"nodes": results, "offline_count": len(offline)}
        if offline:
            result["alert"] = f"Nodes offline: {', '.join(offline)}"
            # Broadcast via WS if server is up
            if results.get("WS") == "up":
                try:
                    async with httpx.AsyncClient(timeout=8) as client:
                        await client.post("http://127.0.0.1:9742/api/broadcast", json={
                            "channel": "system", "event": "node_offline",
                            "payload": {"offline": offline}
                        })
                except Exception:
                    pass
        return result

    @staticmethod
    async def _task_system_audit() -> dict[str, Any]:
        """Escalation audit: if VRAM/zombies high, run full system_audit (every 10min)."""
        import subprocess, json as _json
        turbo = __import__("pathlib").Path("/home/turbo/jarvis-m1-ops")
        exe = __import__("sys").executable
        # Quick checks
        try:
            vr = await asyncio.to_thread(
                subprocess.run,
                [exe, str(turbo / "scripts" / "vram_guard.py"), "--once", "--json"],
                capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
            )
            vtext = vr.stdout or ""
            vdata = {}
            if "{" in vtext:
                try:
                    vdata = _json.loads(vtext[vtext.find("{"):])
                except _json.JSONDecodeError:
                    pass
            vram_pct = vdata.get("max_vram_pct", 0)
        except Exception:
            vram_pct = 0

        # Check cowork-paused flag
        paused = (turbo / "data" / ".cowork-paused").exists()

        need_audit = vram_pct >= 85 or paused
        if not need_audit:
            return {"action": "skip", "vram_pct": vram_pct, "paused": paused}

        # Run full targeted audit
        audit_script = turbo / "scripts" / "system_audit.py"
        if not audit_script.exists():
            return {"action": "audit_script_missing"}

        try:
            ar = await asyncio.to_thread(
                subprocess.run,
                [exe, str(audit_script), "--quick", "--save"],
                capture_output=True, text=True, timeout=120,
                encoding="utf-8", errors="replace",
            )
            result: dict[str, Any] = {
                "action": "full_audit",
                "vram_pct": vram_pct,
                "audit_returncode": ar.returncode,
            }
            if vram_pct >= 90:
                result["alert"] = f"Full audit triggered: VRAM {vram_pct:.1f}%"
            return result
        except Exception as e:
            return {"action": "audit_failed", "error": str(e)}

    # ── Status & API ────────────────────────────────────────────────────

    @staticmethod
    def _safe_json(obj: Any) -> Any:
        """Convert non-serializable objects to dicts/strings for JSON output."""
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: AutonomousLoop._safe_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [AutonomousLoop._safe_json(v) for v in obj]
        if hasattr(obj, "__dataclass_fields__"):
            from dataclasses import asdict
            return asdict(obj)
        return str(obj)

    def get_status(self) -> dict[str, Any]:
        """Return full status of the autonomous loop (JSON-safe)."""
        tasks_info = {}
        for name, t in self._tasks.items():
            tasks_info[name] = {
                "enabled": t.enabled,
                "interval_s": t.interval_s,
                "run_count": t.run_count,
                "fail_count": t.fail_count,
                "last_run": t.last_run,
                "last_result": self._safe_json(t.last_result),
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
