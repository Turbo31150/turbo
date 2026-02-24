"""System channel — OS info, disk space, sanitized config."""

from __future__ import annotations

import os
import platform
import shutil
from typing import Any

from python_ws.bridge import get_config


async def handle_system_request(action: str, payload: dict | None) -> dict[str, Any]:
    """Handle a system channel request."""
    payload = payload or {}

    if action == "system_info":
        return _system_info()

    if action == "config":
        return _sanitized_config()

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
