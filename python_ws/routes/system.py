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
