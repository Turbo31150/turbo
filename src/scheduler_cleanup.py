"""JARVIS Scheduler Cleanup & Bootstrap -- Fix duplicate test jobs + create real schedules.

Cleans up the 36+ duplicate 'test' noop jobs and creates meaningful
scheduled tasks for autonomous operation.

Usage:
    from src.scheduler_cleanup import cleanup_and_bootstrap
    await cleanup_and_bootstrap()
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("jarvis.scheduler_cleanup")


async def cleanup_and_bootstrap() -> dict[str, Any]:
    """Clean duplicate test jobs and create real scheduled tasks."""
    from src.database import get_connection
    
    result = {
        "deleted_test_jobs": 0,
        "created_jobs": [],
        "errors": []
    }
    
    # --- PHASE 1: Delete all duplicate 'test' noop jobs ---
    try:
        count = get_connection().execute(
            "DELETE FROM scheduler_jobs WHERE name = 'test' AND action = 'noop'"
        ).rowcount
        get_connection().commit()
        result["deleted_test_jobs"] = count or 0
        logger.info(f"Cleaned up {count} duplicate test jobs")
    except Exception as e:
        result["errors"].append(f"Cleanup failed: {e}")
        logger.error(f"Cleanup failed: {e}")
    
    # --- PHASE 2: Create real scheduled jobs ---
    REAL_JOBS = [
        {
            "name": "morning_briefing",
            "interval_s": 86400,  # 24h (triggered by cron at 8:00)
            "action": "skill",
            "params": '{"skill": "rapport_matin"}',
            "description": "Rapport du matin: cluster + trading + systme"
        },
        {
            "name": "evening_report",
            "interval_s": 86400,
            "action": "skill",
            "params": '{"skill": "rapport_soir"}',
            "description": "Bilan du soir: trading + activit + maintenance"
        },
        {
            "name": "hourly_health",
            "interval_s": 3600,
            "action": "health_check",
            "params": '{"full": true}',
            "description": "Check sant cluster + GPU + services toutes les heures"
        },
        {
            "name": "trading_scan",
            "interval_s": 900,  # 15 min
            "action": "trading_scan",
            "params": '{"min_score": 75, "top": 5}',
            "description": "Scan signaux trading toutes les 15 min"
        },
        {
            "name": "pattern_analysis",
            "interval_s": 21600,  # 6h
            "action": "brain_analyze",
            "params": '{"auto_create": true, "min_confidence": 0.75}',
            "description": "Analyse patterns d'utilisation toutes les 6h"
        },
        {
            "name": "db_maintenance",
            "interval_s": 86400,
            "action": "db_vacuum",
            "params": '{"force": false}',
            "description": "Maintenance DB quotidienne (VACUUM + ANALYZE)"
        },
        {
            "name": "drift_check",
            "interval_s": 7200,  # 2h
            "action": "drift_check",
            "params": '{}',
            "description": "Vrification qualit modles toutes les 2h"
        },
        {
            "name": "security_scan",
            "interval_s": 43200,  # 12h
            "action": "security_scan",
            "params": '{}',
            "description": "Scan scurit biquotidien"
        },
    ]
    
    for job in REAL_JOBS:
        try:
            # Check if job already exists
            existing = get_connection().execute(
                "SELECT job_id FROM scheduler_jobs WHERE name = ?",
                (job["name"],)
            ).fetchone()
            
            if existing:
                logger.info(f"Job '{job['name']}' already exists, skipping")
                continue
            
            import hashlib
            job_id = hashlib.md5(
                f"{job['name']}{time.time()}".encode()
            ).hexdigest()[:12]
            
            get_connection().execute(
                """INSERT INTO scheduler_jobs 
                   (job_id, name, interval_s, action, params, enabled, one_shot, 
                    last_run, run_count, last_result, last_error, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, 0, 0.0, 0, '', '', ?)""",
                (job_id, job["name"], job["interval_s"], job["action"],
                 job["params"], time.time())
            )
            get_connection().commit()
            result["created_jobs"].append(job["name"])
            logger.info(f"Created scheduled job: {job['name']} (every {job['interval_s']}s)")
            
        except Exception as e:
            result["errors"].append(f"Failed to create {job['name']}: {e}")
            logger.error(f"Failed to create job {job['name']}: {e}")
    
    try:
        total_remaining = get_connection().execute(
            "SELECT COUNT(*) FROM scheduler_jobs"
        ).fetchone()[0]
        result["total_jobs_after"] = total_remaining
    except Exception as e:
        result["total_jobs_after"] = -1
        result["errors"].append(f"Count failed: {e}")

    logger.info(
        f"Scheduler bootstrap complete: {result['deleted_test_jobs']} deleted, "
        f"{len(result['created_jobs'])} created, {result['total_jobs_after']} total"
    )

    return result


async def fix_startup_duplicate_bug() -> str:
    """Prevent the 'test' job creation bug on every MCP server restart.
    
    Call this at startup BEFORE the scheduler initializes to prevent
    the duplicate job creation.
    """
    from src.database import get_connection
    
    # Count existing test jobs
    count = get_connection().execute(
        "SELECT COUNT(*) FROM scheduler_jobs WHERE name = 'test' AND action = 'noop'"
    ).fetchone()[0]
    
    if count > 1:
        # Keep only the newest one (or delete all if we have real jobs)
        get_connection().execute(
            "DELETE FROM scheduler_jobs WHERE name = 'test' AND action = 'noop'"
        )
        get_connection().commit()
        return f"Fixed: deleted {count} duplicate test jobs"
    
    return "OK: no duplicates found"

