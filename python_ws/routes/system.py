"""System channel — OS info, disk space, sanitized config, command execution."""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
import subprocess
import time
from typing import Any

from python_ws.bridge import get_config

logger = logging.getLogger("jarvis.system")

# Lazy-loaded executor
_executor = None


def _get_executor():
    """Lazily load DominoExecutor."""
    global _executor
    if _executor is not None:
        return _executor
    try:
        from src.domino_executor import DominoExecutor
        _executor = DominoExecutor()
        logger.info("DominoExecutor loaded")
    except Exception as e:
        logger.warning("DominoExecutor unavailable: %s", e)
    return _executor


async def handle_system_request(action: str, payload: dict | None) -> dict[str, Any]:
    """Handle a system channel request."""
    payload = payload or {}

    if action == "system_info":
        return _system_info()

    if action == "config":
        return _sanitized_config()

    if action == "execute_command":
        return await _execute_command(payload)

    if action == "execute_domino":
        return await _execute_domino(payload)

    if action == "list_dominos":
        return await _list_dominos(payload)

    if action == "list_chains":
        return await _list_chains(payload)

    if action == "resolve_chain":
        return await _resolve_chain(payload)

    if action == "execute_chain":
        return await _execute_chain(payload)

    if action == "domino_logs":
        return await _domino_logs(payload)

    return {"error": f"unknown system action: {action}"}


def _system_info() -> dict[str, Any]:
    """Gather OS, CPU, memory, and disk information."""
    import psutil

    mem = psutil.virtual_memory()

    # Disk space for C:\ and F:\
    disks = {}
    for drive in ["C:\\", "F:\\"]:
        try:
            usage = shutil.disk_usage(drive)
            disks[drive] = {
                "total_gb": round(usage.total / (1024 ** 3), 1),
                "used_gb": round(usage.used / (1024 ** 3), 1),
                "free_gb": round(usage.free / (1024 ** 3), 1),
                "percent_used": round(usage.used / usage.total * 100, 1),
            }
        except OSError:
            disks[drive] = {"error": "unavailable"}

    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory": {
            "total_gb": round(mem.total / (1024 ** 3), 1),
            "available_gb": round(mem.available / (1024 ** 3), 1),
            "used_gb": round(mem.used / (1024 ** 3), 1),
            "percent": mem.percent,
        },
        "disks": disks,
    }


def _sanitized_config() -> dict[str, Any]:
    """Return config data with API keys redacted."""
    cfg = get_config()
    if cfg is None:
        return {"error": "src.config not available"}

    nodes = []
    for n in cfg.lm_nodes:
        nodes.append({
            "name": n.name,
            "url": n.url,
            "role": n.role,
            "gpus": n.gpus,
            "vram_gb": n.vram_gb,
            "default_model": n.default_model,
            "weight": n.weight,
            "use_cases": n.use_cases,
            "context_length": n.context_length,
            # API key redacted
        })

    ollama = []
    for n in cfg.ollama_nodes:
        ollama.append({
            "name": n.name,
            "url": n.url,
            "role": n.role,
            "default_model": n.default_model,
            "weight": n.weight,
            "use_cases": n.use_cases,
        })

    gemini = {
        "name": cfg.gemini_node.name,
        "role": cfg.gemini_node.role,
        "default_model": cfg.gemini_node.default_model,
        "models": cfg.gemini_node.models,
        "weight": cfg.gemini_node.weight,
        "use_cases": cfg.gemini_node.use_cases,
    }

    return {
        "version": cfg.version,
        "mode": cfg.mode,
        "lm_nodes": nodes,
        "ollama_nodes": ollama,
        "gemini_node": gemini,
        "routing": cfg.routing,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }


# ── Command execution ─────────────────────────────────────────────────────

async def _execute_command(payload: dict) -> dict[str, Any]:
    """Execute a matched JarvisCommand by name or action details.

    Uses src.executor.execute_command which handles all 11 action types:
    powershell, app_open, browser, ms_settings, hotkey, script, pipeline, etc.
    """
    cmd_name = payload.get("command_name", "")
    params = payload.get("params", {})

    if not cmd_name:
        return {"error": "No command_name provided"}

    try:
        from src.commands import COMMANDS
        from src.executor import execute_command
    except ImportError as e:
        return {"error": f"Modules not available: {e}"}

    # Find command by name
    cmd = next((c for c in COMMANDS if c.name == cmd_name), None)
    if not cmd:
        return {"error": f"Command '{cmd_name}' not found"}

    t0 = time.time()
    try:
        result = await execute_command(cmd, params)
        elapsed = round(time.time() - t0, 2)
        logger.info("Executed %s (%s) in %ss", cmd_name, cmd.action_type, elapsed)

        # Handle special return values
        if result.startswith("__"):
            return {
                "executed": True,
                "command_name": cmd_name,
                "action_type": cmd.action_type,
                "output": result,
                "special": True,
                "elapsed": elapsed,
            }

        return {
            "executed": True,
            "command_name": cmd_name,
            "action_type": cmd.action_type,
            "description": cmd.description,
            "output": result[:500],
            "elapsed": elapsed,
        }
    except Exception as e:
        logger.error("Command execution error: %s", e)
        return {"error": str(e), "command_name": cmd_name}


async def _execute_domino(payload: dict) -> dict[str, Any]:
    """Execute a domino cascade by ID or voice text."""
    domino_id = payload.get("domino_id", "")
    voice_text = payload.get("voice_text", "")

    executor = _get_executor()
    if not executor:
        return {"error": "DominoExecutor not available"}

    try:
        if domino_id:
            from src.domino_pipelines import DOMINO_PIPELINES
            domino = next((d for d in DOMINO_PIPELINES if d.id == domino_id), None)
            if not domino:
                return {"error": f"Domino '{domino_id}' not found"}
            result = await asyncio.to_thread(executor.run, domino)
        elif voice_text:
            result = await asyncio.to_thread(executor.run_by_voice, voice_text)
            if not result:
                return {"error": f"No domino matched for: {voice_text}"}
        else:
            return {"error": "Need domino_id or voice_text"}

        return {"executed": True, "domino": result}
    except Exception as e:
        logger.error("Domino execution error: %s", e)
        return {"error": str(e)}


async def _list_dominos(payload: dict) -> dict[str, Any]:
    """List all available domino pipelines (hardcoded + DB chains)."""
    category_filter = payload.get("category", "")

    # Hardcoded pipelines
    try:
        from src.domino_pipelines import DOMINO_PIPELINES
        pipelines = [
            {
                "id": dp.id,
                "triggers": dp.trigger_vocal[:3],
                "category": dp.category,
                "description": dp.description,
                "steps": len(dp.steps),
                "priority": dp.priority,
                "source": "hardcoded",
            }
            for dp in DOMINO_PIPELINES
            if not category_filter or dp.category == category_filter
        ]
    except Exception:
        pipelines = []

    # DB chain triggers
    try:
        from src.chain_resolver import list_all_triggers
        triggers = list_all_triggers()
        chains = [
            {
                "id": f"chain_{t['trigger']}",
                "triggers": [t["trigger"]],
                "category": "db_chain",
                "description": f"{t['trigger']} ({t['chain_count']} chains, conditions: {t['conditions']})",
                "steps": t["chain_count"],
                "priority": "normal",
                "source": "etoile_db",
                "auto_count": t["auto_count"],
            }
            for t in triggers
            if not category_filter or category_filter == "db_chain"
        ]
    except Exception as e:
        logger.warning("Chain resolver error: %s", e)
        chains = []

    # Distinct categories
    cats = sorted(set(p["category"] for p in pipelines + chains))

    return {
        "pipelines": pipelines,
        "chains": chains,
        "categories": cats,
        "total_pipelines": len(pipelines),
        "total_chains": len(chains),
    }


async def _list_chains(payload: dict) -> dict[str, Any]:
    """Search or list DB chains."""
    query = payload.get("query", "")
    limit = payload.get("limit", 50)

    try:
        from src.chain_resolver import search_chains, list_all_triggers
        if query:
            results = search_chains(query, limit=limit)
        else:
            results = search_chains("", limit=limit)
        triggers = list_all_triggers()
        return {"chains": results, "triggers": triggers, "total": len(results)}
    except Exception as e:
        return {"error": str(e)}


async def _resolve_chain(payload: dict) -> dict[str, Any]:
    """Resolve a trigger_cmd into its full chain."""
    trigger = payload.get("trigger", "")
    if not trigger:
        return {"error": "Need trigger parameter"}

    try:
        from src.chain_resolver import resolve_chain
        chain = resolve_chain(trigger)
        if not chain:
            return {"error": f"No chain found for trigger: {trigger}"}
        return {
            "trigger": chain.trigger,
            "steps": [
                {
                    "trigger": s.trigger,
                    "condition": s.condition,
                    "next_cmd": s.next_cmd,
                    "delay_ms": s.delay_ms,
                    "auto": s.auto,
                    "description": s.description,
                    "chain_id": s.chain_id,
                }
                for s in chain.steps
            ],
            "total_delay_ms": chain.total_delay_ms,
            "is_cyclic": chain.is_cyclic,
            "step_count": chain.step_count,
        }
    except Exception as e:
        return {"error": str(e)}


async def _execute_chain(payload: dict) -> dict[str, Any]:
    """Execute a DB chain by trigger_cmd — resolve + execute steps sequentially."""
    trigger = payload.get("trigger", "")
    if not trigger:
        return {"error": "Need trigger parameter"}

    try:
        from src.chain_resolver import resolve_chain
        chain = resolve_chain(trigger)
        if not chain:
            return {"error": f"No chain found for: {trigger}"}

        # Convert resolved chain to DominoPipeline for executor
        from src.domino_pipelines import DominoPipeline, DominoStep
        steps = []
        for s in chain.steps:
            # Determine action_type from the next_cmd content
            action_type = "pipeline"
            action = s.next_cmd
            if s.next_cmd.startswith("powershell:"):
                action_type = "powershell"
            elif s.next_cmd.startswith("curl:"):
                action_type = "curl"
            elif s.next_cmd.startswith("python:"):
                action_type = "python"

            steps.append(DominoStep(
                name=f"{s.trigger}_to_{s.next_cmd}",
                action=action,
                action_type=action_type,
                condition=s.condition if s.condition != "always" else None,
                on_fail="skip",
                timeout_s=30,
            ))

        domino = DominoPipeline(
            id=f"chain_{trigger}",
            trigger_vocal=[trigger],
            steps=steps,
            category="db_chain",
            description=chain.description or f"DB chain: {trigger}",
            learning_context=f"Resolved from etoile.db domino_chains (trigger={trigger})",
        )

        executor = _get_executor()
        if not executor:
            return {"error": "DominoExecutor not available"}

        result = await asyncio.to_thread(executor.run, domino)
        return {"executed": True, "domino": result, "source": "db_chain"}
    except Exception as e:
        logger.error("Chain execution error: %s", e)
        return {"error": str(e)}


async def _domino_logs(payload: dict) -> dict[str, Any]:
    """Get recent domino execution logs."""
    limit = payload.get("limit", 20)
    run_id = payload.get("run_id", "")

    try:
        import sqlite3
        db_path = "F:/BUREAU/turbo/data/etoile.db"
        conn = sqlite3.connect(db_path)

        if run_id:
            rows = conn.execute(
                "SELECT run_id, domino_id, step_name, step_idx, status, duration_ms, node, output_preview, ts "
                "FROM domino_logs WHERE run_id=? ORDER BY step_idx",
                (run_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT run_id, domino_id, step_name, step_idx, status, duration_ms, node, output_preview, ts "
                "FROM domino_logs ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        conn.close()

        return {
            "logs": [
                {
                    "run_id": r[0], "domino_id": r[1], "step_name": r[2],
                    "step_idx": r[3], "status": r[4], "duration_ms": r[5],
                    "node": r[6], "output_preview": r[7], "ts": r[8],
                }
                for r in rows
            ],
            "total": len(rows),
        }
    except Exception as e:
        return {"error": str(e)}
