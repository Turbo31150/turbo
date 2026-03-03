"""Cluster channel — monitoring, node health, push events."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from starlette.websockets import WebSocket

from python_ws.helpers import push_loop

logger = logging.getLogger("jarvis.cluster")

from python_ws.bridge import (
    get_cluster_status,
    get_config,
    _probe_lmstudio,
    _probe_ollama,
)


async def handle_cluster_request(action: str, payload: dict | None) -> dict[str, Any]:
    """Handle a cluster channel request. Returns the response payload or error."""
    payload = payload or {}

    if action in ("cluster_status", "get_status"):
        return await get_cluster_status()

    if action == "node_health":
        node_name = payload.get("node")
        if not node_name:
            return {"error": "missing 'node' in payload"}
        return await _ping_node(node_name)

    if action == "gpu_stats":
        # Returns whatever cluster_status gives us (gpu info is embedded)
        status = await get_cluster_status()
        gpu_summary = {}
        for name, info in status.get("nodes", {}).items():
            gpu_summary[name] = {
                "gpus": info.get("gpus", 0),
                "vram_gb": info.get("vram_gb", 0),
                "online": info.get("online", False),
                "latency_ms": info.get("latency_ms", -1),
            }
        return {"gpu_nodes": gpu_summary}

    return {"error": f"unknown cluster action: {action}"}


async def _ping_node(node_name: str) -> dict[str, Any]:
    """Ping a specific node by name, reusing shared probe helpers."""
    import httpx

    cfg = get_config()
    if cfg is None:
        return {"error": "config unavailable"}

    for node in cfg.lm_nodes:
        if node.name == node_name:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                return await _probe_lmstudio(client, node)

    for node in cfg.ollama_nodes:
        if node.name == node_name:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                return await _probe_ollama(client, node)

    if node_name == "GEMINI":
        return {"node": "GEMINI", "online": True, "note": "static — no HTTP probe"}

    return {"error": f"unknown node: {node_name}"}


async def push_cluster_events(websocket: WebSocket) -> None:
    """Background loop: push cluster status every 5 seconds."""
    await push_loop(
        websocket.send_json, get_cluster_status,
        channel="cluster", event="node_status_changed",
        interval=5.0, backoff=2.0,
    )
