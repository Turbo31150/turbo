"""Cluster channel — monitoring, node health, push events."""

from __future__ import annotations

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

    if action == "model_swap":
        return await _model_swap(payload)

    if action == "gpu_cleanup":
        return await _gpu_cleanup()

    if action == "orchestrator_status":
        return await _orchestrator_status()

    if action == "fallback_chain":
        return await _get_fallback_chain(payload)

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


async def _model_swap(payload: dict) -> dict[str, Any]:
    """Load or unload a model on a node via LM Studio CLI or Ollama API."""
    import subprocess
    action = payload.get("action", "load")  # "load" or "unload"
    model = payload.get("model", "")
    node = payload.get("node", "M1")

    if not model:
        return {"error": "missing 'model' in payload"}

    if node in ("M1", "M2", "M3"):
        # LM Studio CLI
        lms_path = r"/home/turbo\.lmstudio\bin\lms.exe"
        try:
            cmd = [lms_path, action, model] if action == "load" else [lms_path, "unload", model]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {
                "ok": result.returncode == 0,
                "node": node, "model": model, "action": action,
                "output": result.stdout.strip(),
                "error": result.stderr.strip() if result.returncode != 0 else None,
            }
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return {"error": f"LMS CLI failed: {e}"}
    elif node == "OL1":
        # Ollama pull/delete
        import httpx
        try:
            if action == "load":
                async with httpx.AsyncClient(timeout=120) as client:
                    r = await client.post(
                        "http://127.0.0.1:11434/api/pull",
                        json={"name": model, "stream": False},
                    )
                    return {"ok": r.status_code == 200, "node": "OL1", "model": model, "action": "pull"}
            else:
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.delete(
                        "http://127.0.0.1:11434/api/delete",
                        json={"name": model},
                    )
                    return {"ok": r.status_code == 200, "node": "OL1", "model": model, "action": "delete"}
        except (httpx.HTTPError, OSError) as e:
            return {"error": f"Ollama API failed: {e}"}

    return {"error": f"Unknown node for model_swap: {node}"}


async def _gpu_cleanup() -> dict[str, Any]:
    """Run GPU memory cleanup — clear CUDA cache and report VRAM."""
    import subprocess
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.used,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return {"error": "nvidia-smi failed"}
        gpus = []
        for line in r.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                gpus.append({
                    "index": int(parts[0]),
                    "used_mb": int(parts[1]),
                    "total_mb": int(parts[2]),
                    "free_mb": int(parts[3]),
                })
        return {"gpus": gpus, "message": "GPU status retrieved"}
    except FileNotFoundError:
        return {"error": "nvidia-smi not found"}
    except Exception as e:
        return {"error": f"GPU cleanup failed: {e}"}


async def _orchestrator_status() -> dict[str, Any]:
    """Get orchestrator v2 full status."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        return orchestrator_v2.get_dashboard()
    except Exception as e:
        return {"error": f"Orchestrator unavailable: {e}"}


async def _get_fallback_chain(payload: dict) -> dict[str, Any]:
    """Get fallback chain for a task type."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        task_type = payload.get("task_type", "code")
        exclude = set(payload.get("exclude", []))
        chain = orchestrator_v2.fallback_chain(task_type, exclude=exclude)
        return {"task_type": task_type, "chain": chain}
    except Exception as e:
        return {"error": f"Fallback chain failed: {e}"}


async def push_cluster_events(websocket: WebSocket) -> None:
    """Background loop: push cluster status every 5 seconds."""
    await push_loop(
        websocket.send_json, get_cluster_status,
        channel="cluster", event="node_status_changed",
        interval=5.0, backoff=2.0,
    )
