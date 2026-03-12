"""JARVIS Bootstrap v2 - Avec Cowork Agent intégré.

Ajoute le démarrage de l'agent cowork dans la séquence bootstrap.

Remplace src/startup_wiring.py après validation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("jarvis.startup")


async def bootstrap_jarvis(
    start_autonomous: bool = True,
    start_gpu_guardian: bool = True,
    start_trading_sentinel: bool = True,
    start_cowork: bool = True  # NOUVEAU
) -> dict[str, Any]:
    """Bootstrap complet JARVIS en 10 étapes (+ cowork).
    
    Returns:
        {
            "success": bool,
            "steps_total": int,
            "steps_ok": int,
            "duration_ms": int,
            "errors": list[str]
        }
    """
    start_time = time.time()
    steps = []
    errors = []
    
    # Étape 1: Fix scheduler bug
    try:
        logger.info("[1/10] Fixing scheduler bug...")
        from src.scheduler_cleanup import fix_scheduler_bug
        await fix_scheduler_bug()
        steps.append(("scheduler_fix", True))
        logger.info("[1/10] Scheduler fix: OK")
    except Exception as e:
        errors.append(f"scheduler_fix: {e}")
        steps.append(("scheduler_fix", False))
        logger.warning(f"[1/10] Scheduler fix: SKIP ({e})")
    
    # Étape 2: Scheduler bootstrap (cleanup + jobs)
    try:
        logger.info("[2/10] Bootstrapping scheduler...")
        from src.scheduler_cleanup import cleanup_and_bootstrap
        await cleanup_and_bootstrap()
        steps.append(("scheduler_bootstrap", True))
        logger.info("[2/10] Scheduler bootstrap: OK")
    except Exception as e:
        errors.append(f"scheduler_bootstrap: {e}")
        steps.append(("scheduler_bootstrap", False))
        logger.warning(f"[2/10] Scheduler bootstrap: SKIP ({e})")
    
    # Étape 3: Event bus wiring
    try:
        logger.info("[3/10] Wiring event bus (16 subscribers)...")
        from src.event_bus_wiring import wire_all
        await wire_all()
        steps.append(("event_bus", True))
        logger.info("[3/10] Event bus wiring: OK")
    except Exception as e:
        errors.append(f"event_bus: {e}")
        steps.append(("event_bus", False))
        logger.warning(f"[3/10] Event bus: SKIP ({e})")
    
    # Étape 4: Health probes registration
    try:
        logger.info("[4/10] Registering health probes (10)...")
        from src.health_probe_registry import register_all_probes
        register_all_probes()
        steps.append(("health_probes", True))
        logger.info("[4/10] Health probes: OK")
    except Exception as e:
        errors.append(f"health_probes: {e}")
        steps.append(("health_probes", False))
        logger.warning(f"[4/10] Health probes: SKIP ({e})")
    
    # Étape 5: GPU Guardian
    if start_gpu_guardian:
        try:
            logger.info("[5/10] Starting GPU Guardian...")
            from src.gpu_guardian import gpu_guardian
            asyncio.create_task(gpu_guardian.start())
            steps.append(("gpu_guardian", True))
            logger.info("[5/10] GPU Guardian: STARTED")
        except Exception as e:
            errors.append(f"gpu_guardian: {e}")
            steps.append(("gpu_guardian", False))
            logger.warning(f"[5/10] GPU Guardian: SKIP ({e})")
    else:
        steps.append(("gpu_guardian", False))
    
    # Étape 6: Cluster Self-Healer
    try:
        logger.info("[6/10] Wiring cluster self-healer...")
        from src.cluster_self_healer import wire_self_healer
        await wire_self_healer()
        steps.append(("self_healer", True))
        logger.info("[6/10] Cluster self-healer: OK")
    except Exception as e:
        errors.append(f"self_healer: {e}")
        steps.append(("self_healer", False))
        logger.warning(f"[6/10] Self-healer: SKIP ({e})")
    
    # Étape 7: Trading Sentinel
    if start_trading_sentinel:
        try:
            logger.info("[7/10] Starting Trading Sentinel...")
            from src.trading_sentinel import trading_sentinel
            asyncio.create_task(trading_sentinel.start())
            steps.append(("trading_sentinel", True))
            logger.info("[7/10] Trading Sentinel: STARTED")
        except Exception as e:
            errors.append(f"trading_sentinel: {e}")
            steps.append(("trading_sentinel", False))
            logger.warning(f"[7/10] Trading Sentinel: SKIP ({e})")
    else:
        steps.append(("trading_sentinel", False))
    
    # Étape 8: Autonomous Loop
    if start_autonomous:
        try:
            logger.info("[8/10] Starting autonomous loop...")
            from src.autonomous_loop import autonomous_loop
            asyncio.create_task(autonomous_loop.start())
            steps.append(("autonomous_loop", True))
            logger.info("[8/10] Autonomous loop: STARTED")
        except Exception as e:
            errors.append(f"autonomous_loop: {e}")
            steps.append(("autonomous_loop", False))
            logger.warning(f"[8/10] Autonomous loop: SKIP ({e})")
    else:
        steps.append(("autonomous_loop", False))
    
    # Étape 9: Cowork Agent (NOUVEAU)
    if start_cowork:
        try:
            logger.info("[9/10] Starting Cowork Agent...")
            from src.cowork_agent_config import cowork_agent
            asyncio.create_task(cowork_agent.start())
            steps.append(("cowork_agent", True))
            logger.info("[9/10] Cowork Agent: STARTED")
        except Exception as e:
            errors.append(f"cowork_agent: {e}")
            steps.append(("cowork_agent", False))
            logger.warning(f"[9/10] Cowork Agent: SKIP ({e})")
    else:
        steps.append(("cowork_agent", False))
    
    # Étape 10: Emit startup_complete event
    try:
        logger.info("[10/10] Emitting startup_complete event...")
        from src.event_bus import event_bus
        await event_bus.emit("system.startup_complete", {
            "steps": steps,
            "errors": errors,
            "duration_ms": int((time.time() - start_time) * 1000),
            "ts": time.time()
        })
        steps.append(("startup_event", True))
        logger.info("[10/10] Startup event: OK")
    except Exception as e:
        errors.append(f"startup_event: {e}")
        steps.append(("startup_event", False))
        logger.warning(f"[10/10] Startup event: SKIP ({e})")
    
    # Résumé
    duration_ms = int((time.time() - start_time) * 1000)
    steps_ok = sum(1 for _, ok in steps if ok)
    steps_total = len(steps)
    success = steps_ok == steps_total
    
    logger.info("\n" + "="*70)
    if success:
        logger.info(f"JARVIS Bootstrap COMPLETE in {duration_ms}ms")
        logger.info(f"  {steps_ok}/{steps_total} steps OK -- ALL SYSTEMS GO")
    else:
        logger.warning(f"JARVIS Bootstrap PARTIAL in {duration_ms}ms")
        logger.warning(f"  {steps_ok}/{steps_total} steps OK")
        logger.warning(f"  Errors: {errors}")
    logger.info("="*70 + "\n")
    
    return {
        "success": success,
        "steps_total": steps_total,
        "steps_ok": steps_ok,
        "duration_ms": duration_ms,
        "errors": errors,
        "steps": steps
    }


async def shutdown_jarvis() -> dict[str, Any]:
    """Shutdown gracieux de tous les services."""
    start_time = time.time()
    logger.info("Starting JARVIS shutdown sequence...")
    
    # Arrêter tous les services en parallèle
    tasks = []
    
    try:
        from src.gpu_guardian import gpu_guardian
        tasks.append(("gpu_guardian", gpu_guardian.stop()))
    except Exception:
        pass
    
    try:
        from src.trading_sentinel import trading_sentinel
        tasks.append(("trading_sentinel", trading_sentinel.stop()))
    except Exception:
        pass
    
    try:
        from src.autonomous_loop import autonomous_loop
        tasks.append(("autonomous_loop", autonomous_loop.stop()))
    except Exception:
        pass
    
    try:
        from src.cowork_agent_config import cowork_agent
        tasks.append(("cowork_agent", cowork_agent.stop()))
    except Exception:
        pass
    
    # Attendre arrêt de tous (max 5s)
    if tasks:
        names, coros = zip(*tasks)
        try:
            await asyncio.wait_for(
                asyncio.gather(*coros, return_exceptions=True),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning("Shutdown timeout (5s) - forcing")
    
    # Emit shutdown event
    try:
        from src.event_bus import event_bus
        await event_bus.emit("system.shutdown_complete", {
            "ts": time.time()
        })
    except Exception:
        pass
    
    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(f"JARVIS Shutdown complete in {duration_ms}ms")
    
    return {
        "success": True,
        "duration_ms": duration_ms
    }


if __name__ == "__main__":
    # Test bootstrap
    asyncio.run(bootstrap_jarvis())

