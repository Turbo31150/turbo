"""Cluster channel — monitoring, node health, push events."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from starlette.websockets import WebSocket

from python_ws.bridge import get_cluster_status, get_config


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
    """Ping a specific node by name and return its status."""
    cfg = get_config()
    if cfg is None:
        return {"error": "config unavailable"}

    # Find the node
    for node in cfg.lm_nodes:
        if node.name == node_name:
            async with httpx.AsyncClient() as client:
                try:
                    t0 = time.perf_counter()
                    resp = await client.get(
                        f"{node.url}/api/v1/models",
                        headers=node.auth_headers,
                        timeout=5.0,
                    )
                    latency = round((time.perf_counter() - t0) * 1000)
                    resp.raise_for_status()
                    return {"node": node_name, "online": True, "latency_ms": latency}
                except Exception as exc:
                    return {"node": node_name, "online": False, "error": str(exc)}

    for node in cfg.ollama_nodes:
        if node.name == node_name:
            async with httpx.AsyncClient() as client:
                try:
                    t0 = time.perf_counter()
                    resp = await client.get(f"{node.url}/api/tags", timeout=5.0)
                    latency = round((time.perf_counter() - t0) * 1000)
                    resp.raise_for_status()
                    return {"node": node_name, "online": True, "latency_ms": latency}
                except Exception as exc:
                    return {"node": node_name, "online": False, "error": str(exc)}

    if node_name == "GEMINI":
        return {"node": "GEMINI", "online": True, "note": "static — no HTTP probe"}

    return {"error": f"unknown node: {node_name}"}


async def push_cluster_events(websocket: WebSocket) -> None:
    """Background loop: push cluster status every 5 seconds."""
    while True:
        try:
            status = await get_cluster_status()
            await websocket.send_json({
                "type": "event",
                "channel": "cluster",
                "event": "node_status_changed",
                "payload": status,
            })
        except Exception:
            # Connection closed or send failed — stop loop
            break
        await asyncio.sleep(5)
