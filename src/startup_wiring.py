"""JARVIS Startup Wiring v2  Master bootstrap that connects EVERYTHING.

Call this once at startup to:
1. Fix scheduler duplicate bug
2. Clean + bootstrap scheduler with real jobs  
3. Wire all event bus subscribers
4. Register all health probes
5. Start GPU Guardian
6. Wire cluster self-healer to event bus
7. Start Trading Sentinel
8. Start autonomous loop
9. Emit startup event

Usage:
    from src.startup_wiring import bootstrap_jarvis, shutdown_jarvis
    await bootstrap_jarvis()    # in FastAPI lifespan or main.py
    await shutdown_jarvis()     # graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("jarvis.startup")

_BOOTSTRAP_DONE = False


async def bootstrap_jarvis(
    start_autonomous: bool = True,
    start_gpu_guardian: bool = True,
    start_trading_sentinel: bool = True,
    timeout_s: float = 120,
) -> dict[str, Any]:
    """Master bootstrap  wire everything and start autonomous operation.

    Args:
        start_autonomous: Start the autonomous background loop
        start_gpu_guardian: Start GPU temperature/VRAM monitoring
        start_trading_sentinel: Start trading position monitoring
        timeout_s: Global timeout in seconds (default 120s)

    Returns:
        Status dict with results from each bootstrap step.
    """
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return {"status": "already_bootstrapped", "ts": time.time()}

    try:
        return await asyncio.wait_for(
            _bootstrap_internal(start_autonomous, start_gpu_guardian, start_trading_sentinel),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        logger.error(f"JARVIS Bootstrap TIMEOUT after {timeout_s}s")
        _BOOTSTRAP_DONE = True
        return {"success": False, "error": f"Bootstrap timeout ({timeout_s}s)", "ts": time.time()}


async def _bootstrap_internal(
    start_autonomous: bool,
    start_gpu_guardian: bool,
    start_trading_sentinel: bool,
) -> dict[str, Any]:
    global _BOOTSTRAP_DONE
    
    results: dict[str, Any] = {
        "ts": time.time(),
        "steps": {},
        "errors": [],
        "success": True
    }
    
    logger.info("=" * 60)
    logger.info("JARVIS Bootstrap v2  Wiring ALL systems...")
    logger.info("=" * 60)
    
    # --- Step 1: Fix scheduler duplicate bug ---
    results["steps"]["1_scheduler_fix"] = await _safe_step(
        "Scheduler fix", 1, 9, results,
        _step_scheduler_fix
    )
    
    # --- Step 2: Clean + bootstrap scheduler ---
    results["steps"]["2_scheduler_bootstrap"] = await _safe_step(
        "Scheduler bootstrap", 2, 9, results,
        _step_scheduler_bootstrap
    )
    
    # --- Step 3: Wire event bus ---
    results["steps"]["3_event_bus"] = await _safe_step(
        "Event bus wiring", 3, 9, results,
        _step_event_bus
    )
    
    # --- Step 4: Register health probes ---
    results["steps"]["4_health_probes"] = await _safe_step(
        "Health probes", 4, 9, results,
        _step_health_probes
    )
    
    # --- Step 5: Start GPU Guardian ---
    if start_gpu_guardian:
        results["steps"]["5_gpu_guardian"] = await _safe_step(
            "GPU Guardian", 5, 9, results,
            _step_gpu_guardian
        )
    else:
        results["steps"]["5_gpu_guardian"] = {"skipped": True}
        logger.info("[5/9] GPU Guardian: skipped")
    
    # --- Step 6: Wire cluster self-healer ---
    results["steps"]["6_self_healer"] = await _safe_step(
        "Cluster self-healer", 6, 9, results,
        _step_self_healer
    )
    
    # --- Step 7: Start Trading Sentinel ---
    if start_trading_sentinel:
        results["steps"]["7_trading_sentinel"] = await _safe_step(
            "Trading Sentinel", 7, 9, results,
            _step_trading_sentinel
        )
    else:
        results["steps"]["7_trading_sentinel"] = {"skipped": True}
        logger.info("[7/9] Trading Sentinel: skipped")
    
    # --- Step 8: Start autonomous loop ---
    if start_autonomous:
        results["steps"]["8_autonomous_loop"] = await _safe_step(
            "Autonomous loop", 8, 9, results,
            _step_autonomous_loop
        )
    else:
        results["steps"]["8_autonomous_loop"] = {"skipped": True}
        logger.info("[8/9] Autonomous loop: skipped")
    
    # --- Step 9: Emit startup complete event ---
    results["steps"]["9_startup_event"] = await _safe_step(
        "Startup event", 9, 11, results,
        lambda: _step_startup_event(results)
    )

    # --- Step 10: Collab bridge (Claude Code <-> Perplexity) ---
    results["steps"]["10_collab_bridge"] = await _safe_step(
        "Collab bridge", 10, 11, results,
        _step_collab_bridge
    )

    # --- Step 11: Post-startup validation ---
    results["steps"]["11_post_validation"] = await _safe_step(
        "Post-startup validation", 11, 11, results,
        _step_post_startup_validation
    )

    # --- Final status ---
    _TOTAL_STEPS = 11
    results["success"] = len(results["errors"]) == 0
    results["duration_ms"] = round((time.time() - results["ts"]) * 1000, 1)
    results["steps_ok"] = sum(
        1 for v in results["steps"].values()
        if isinstance(v, dict) and not v.get("error") and not v.get("skipped")
    )
    results["steps_total"] = _TOTAL_STEPS

    _BOOTSTRAP_DONE = True

    if results["success"]:
        logger.info(
            f"\n{'='*60}\n"
            f"JARVIS Bootstrap COMPLETE in {results['duration_ms']}ms\n"
            f"  {results['steps_ok']}/{_TOTAL_STEPS} steps OK  ALL SYSTEMS GO\n"
            f"{'='*60}"
        )
    else:
        logger.warning(
            f"\n{'='*60}\n"
            f"JARVIS Bootstrap PARTIAL in {results['duration_ms']}ms\n"
            f"  {results['steps_ok']}/{_TOTAL_STEPS} steps OK  {len(results['errors'])} errors\n"
            f"  Errors: {results['errors']}\n"
            f"{'='*60}"
        )
    
    return results


async def shutdown_jarvis() -> dict[str, Any]:
    """Graceful shutdown  stop all background services."""
    global _BOOTSTRAP_DONE
    results: dict[str, Any] = {"ts": time.time()}
    
    logger.info("JARVIS Shutdown initiated...")
    
    # Stop Task Scheduler
    try:
        from src.task_scheduler import task_scheduler
        await task_scheduler.stop()
        results["task_scheduler"] = "stopped"
    except Exception as e:
        results["task_scheduler"] = f"error: {e}"

    # Stop Trading Sentinel
    try:
        from src.trading_sentinel import trading_sentinel
        trading_sentinel.stop()
        results["trading_sentinel"] = "stopped"
    except Exception as e:
        results["trading_sentinel"] = f"error: {e}"
    
    # Stop GPU Guardian
    try:
        from src.gpu_guardian import gpu_guardian
        gpu_guardian.stop()
        results["gpu_guardian"] = "stopped"
    except Exception as e:
        results["gpu_guardian"] = f"error: {e}"
    
    # Stop Autonomous Loop
    try:
        from src.autonomous_loop import autonomous_loop
        autonomous_loop.stop()
        results["autonomous_loop"] = "stopped"
    except Exception as e:
        results["autonomous_loop"] = f"error: {e}"
    
    # Emit shutdown event
    try:
        from src.event_bus import event_bus
        await event_bus.emit("system.shutdown", {"ts": time.time()})
        results["shutdown_event"] = "emitted"
    except Exception:
        pass
    
    _BOOTSTRAP_DONE = False
    results["duration_ms"] = round((time.time() - results["ts"]) * 1000, 1)
    logger.info(f"JARVIS Shutdown complete in {results['duration_ms']}ms")
    
    return results


# ----------------------------------------------------------------
# Individual bootstrap steps
# ----------------------------------------------------------------

async def _step_scheduler_fix() -> dict[str, Any]:
    from src.scheduler_cleanup import fix_startup_duplicate_bug
    result = await fix_startup_duplicate_bug()
    return {"result": result}


async def _step_scheduler_bootstrap() -> dict[str, Any]:
    from src.task_scheduler import task_scheduler

    # Clean up garbage noop jobs from scheduler.db
    import sqlite3
    try:
        with sqlite3.connect(str(task_scheduler._db_path)) as conn:
            deleted = conn.execute("DELETE FROM jobs WHERE action = 'noop'").rowcount
            conn.commit()
            logger.info(f"Cleaned {deleted} noop jobs from scheduler.db")
    except Exception:
        deleted = 0

    # Bootstrap real jobs (idempotent — skips if already exists)
    REAL_JOBS = [
        ("morning_briefing", "skill", 86400, {"skill": "rapport_matin"}),
        ("evening_report", "skill", 86400, {"skill": "rapport_soir"}),
        ("hourly_health", "health_check", 3600, {"full": True}),
        ("trading_scan", "trading_scan", 900, {"min_score": 75, "top": 5}),
        ("pattern_analysis", "brain_analyze", 21600, {"auto_create": True}),
        ("db_maintenance", "db_vacuum", 86400, {"force": False}),
        ("drift_check", "drift_check", 7200, {}),
        ("security_scan", "security_scan", 43200, {}),
    ]
    created = []
    existing_jobs = {j["name"] for j in task_scheduler.list_jobs()}
    for name, action, interval, params in REAL_JOBS:
        if name not in existing_jobs:
            task_scheduler.add_job(name, action, interval, params)
            created.append(name)
    result = {"deleted_noop": deleted, "created_jobs": created, "total_after": len(task_scheduler.list_jobs())}

    # Register handlers for each job action type
    async def _health_check(params: dict) -> str:
        from src.health_dashboard import health_dashboard
        report = health_dashboard.get_report()
        return f"health_score={report.get('overall_score', '?')}"

    async def _trading_scan(params: dict) -> str:
        from src.event_bus import event_bus
        await event_bus.emit("trading.scan_requested", params)
        return "scan_triggered"

    async def _brain_analyze(params: dict) -> str:
        from src.brain import brain
        result = await brain.analyze_patterns()
        return f"patterns={len(result) if isinstance(result, list) else result}"

    async def _db_vacuum(params: dict) -> str:
        from src.database import get_connection
        get_connection().execute("PRAGMA optimize")
        return "optimized"

    async def _drift_check(params: dict) -> str:
        from src.event_bus import event_bus
        await event_bus.emit("quality.drift_check", params)
        return "drift_check_triggered"

    async def _security_scan(params: dict) -> str:
        from src.event_bus import event_bus
        await event_bus.emit("security.scan_requested", params)
        return "security_scan_triggered"

    async def _skill_handler(params: dict) -> str:
        skill_name = params.get("skill", "unknown")
        from src.event_bus import event_bus
        await event_bus.emit(f"skill.execute", {"skill": skill_name})
        return f"skill={skill_name}"

    task_scheduler.register_handler("health_check", _health_check)
    task_scheduler.register_handler("trading_scan", _trading_scan)
    task_scheduler.register_handler("brain_analyze", _brain_analyze)
    task_scheduler.register_handler("db_vacuum", _db_vacuum)
    task_scheduler.register_handler("drift_check", _drift_check)
    task_scheduler.register_handler("security_scan", _security_scan)
    task_scheduler.register_handler("skill", _skill_handler)

    # Start the scheduler loop so cron jobs actually execute
    await task_scheduler.start(check_interval=10.0)
    return {
        "deleted": result.get("deleted_test_jobs", 0),
        "created": result.get("created_jobs", []),
        "total_after": result.get("total_jobs_after", 0),
        "scheduler_running": task_scheduler.running,
        "handlers_registered": len(task_scheduler._handlers),
    }


async def _step_event_bus() -> dict[str, Any]:
    from src.event_bus_wiring import wire_all
    counts = await wire_all()
    return {"subscribers": sum(counts.values()), "categories": counts}


async def _step_health_probes() -> dict[str, Any]:
    from src.health_probe_registry import register_all_probes
    registered = register_all_probes()
    ok = sum(1 for v in registered.values() if v)
    return {"registered": ok, "total": len(registered), "detail": registered}


async def _step_gpu_guardian() -> dict[str, Any]:
    from src.gpu_guardian import gpu_guardian
    await gpu_guardian.start()
    await asyncio.sleep(0.5)
    return {"running": getattr(gpu_guardian, "running", False)}


async def _step_self_healer() -> dict[str, Any]:
    from src.cluster_self_healer import cluster_healer
    from src.event_bus import event_bus
    
    async def on_heal_request(data: dict[str, Any]) -> None:
        node = data.get("node", "unknown")
        await cluster_healer.handle_node_failure(node)
    
    event_bus.subscribe("cluster.heal_requested", on_heal_request, priority=10)
    event_bus.subscribe("cluster.node_offline", 
        lambda d: cluster_healer.handle_node_failure(d.get("node", "?")),
        priority=9
    )
    
    return {"wired": True, "known_nodes": list(cluster_healer.status()["known_nodes"])}


async def _step_trading_sentinel() -> dict[str, Any]:
    from src.trading_sentinel import trading_sentinel
    await trading_sentinel.start()
    await asyncio.sleep(0.3)
    return {"running": getattr(trading_sentinel, "running", False)}


async def _step_autonomous_loop() -> dict[str, Any]:
    from src.autonomous_loop import autonomous_loop
    if not hasattr(autonomous_loop, "running") or not autonomous_loop.running:
        asyncio.create_task(autonomous_loop.start())
        await asyncio.sleep(0.5)
    return {
        "running": getattr(autonomous_loop, "running", False),
        "tasks": len(autonomous_loop.tasks) if hasattr(autonomous_loop, 'tasks') else 0
    }


async def _step_collab_bridge() -> dict[str, Any]:
    from src.collab_bridge import stats, list_tasks
    s = stats()
    pending = list_tasks(status="pending")
    return {"queue_stats": s, "pending_count": len(pending), "ready": True}


async def _step_post_startup_validation() -> dict[str, Any]:
    import subprocess
    checks = {}
    for name, url in [
        ("M1", "http://127.0.0.1:1234/api/v1/models"),
        ("OL1", "http://127.0.0.1:11434/api/tags"),
    ]:
        try:
            r = subprocess.run(
                ["curl", "-s", "--max-time", "3", url],
                capture_output=True, text=True, timeout=5,
            )
            checks[name] = "healthy" if r.returncode == 0 and r.stdout.strip() else "degraded"
        except Exception:
            checks[name] = "offline"
    healthy = sum(1 for v in checks.values() if v == "healthy")
    return {"checks": checks, "healthy": healthy, "total": len(checks)}


async def _step_startup_event(results: dict) -> dict[str, Any]:
    from src.event_bus import event_bus
    error_count = len(results.get("errors", []))
    await event_bus.emit("system.startup_complete", {
        "ts": time.time(),
        "success": error_count == 0,
        "error_count": error_count,
        "components": [
            "scheduler", "event_bus", "health_probes", "gpu_guardian",
            "self_healer", "trading_sentinel", "autonomous_loop",
            "collab_bridge", "post_validation"
        ]
    })
    return {"emitted": True}


async def _safe_step(
    name: str, step_num: int, total: int,
    results: dict, fn
) -> dict[str, Any]:
    """Execute a bootstrap step with error handling."""
    try:
        result = await fn()
        logger.info(f"[{step_num}/{total}] {name}: OK")
        return result
    except Exception as e:
        results["errors"].append(f"{name}: {e}")
        logger.error(f"[{step_num}/{total}] {name}: FAILED - {e}")
        return {"error": str(e)}


def is_bootstrapped() -> bool:
    """Check if JARVIS has been bootstrapped."""
    return _BOOTSTRAP_DONE

