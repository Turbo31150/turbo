"""Bridge adapter — connects WebSocket server to existing src/ modules."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import httpx

# Ensure src/ is importable
_turbo_root = str(Path(__file__).resolve().parent.parent)
if _turbo_root not in sys.path:
    sys.path.insert(0, _turbo_root)


# ── Safe imports from src ────────────────────────────────────────────────────

def _try_import_config():
    """Safely import JarvisConfig and config instance from src.config."""
    try:
        from src.config import JarvisConfig, config as _cfg
        return JarvisConfig, _cfg
    except ImportError:
        return None, None


_JarvisConfig, _config = _try_import_config()


def get_config():
    """Return the JarvisConfig singleton (or None if src.config unavailable)."""
    return _config


def get_config_class():
    """Return the JarvisConfig class (or None)."""
    return _JarvisConfig


# ── Cluster status via HTTP probes ───────────────────────────────────────────

async def _probe_lmstudio(client: httpx.AsyncClient, node) -> dict[str, Any]:
    """Probe a single LM Studio node (M1, M2, M3)."""
    result: dict[str, Any] = {
        "name": node.name,
        "url": node.url,
        "role": node.role,
        "gpus": node.gpus,
        "vram_gb": node.vram_gb,
        "default_model": node.default_model,
        "weight": node.weight,
        "online": False,
        "models_loaded": [],
        "latency_ms": -1,
    }
    try:
        t0 = time.perf_counter()
        resp = await client.get(
            f"{node.url}/api/v1/models",
            headers=node.auth_headers,
            timeout=5.0,
        )
        latency = round((time.perf_counter() - t0) * 1000)
        resp.raise_for_status()
        data = resp.json()
        loaded = [
            m.get("id", m.get("name", "unknown"))
            for m in data.get("models", data.get("data", []))
            if m.get("loaded_instances") or m.get("active")
        ]
        result["online"] = True
        result["models_loaded"] = loaded
        result["latency_ms"] = latency
    except Exception as exc:
        result["error"] = str(exc)
    return result


async def _probe_ollama(client: httpx.AsyncClient, node) -> dict[str, Any]:
    """Probe the Ollama node (OL1)."""
    result: dict[str, Any] = {
        "name": node.name,
        "url": node.url,
        "role": node.role,
        "default_model": node.default_model,
        "weight": node.weight,
        "online": False,
        "models_loaded": [],
        "latency_ms": -1,
    }
    try:
        t0 = time.perf_counter()
        resp = await client.get(f"{node.url}/api/tags", timeout=5.0)
        latency = round((time.perf_counter() - t0) * 1000)
        resp.raise_for_status()
        data = resp.json()
        models = [m.get("name", "unknown") for m in data.get("models", [])]
        result["online"] = True
        result["models_loaded"] = models
        result["latency_ms"] = latency
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _gemini_info(node) -> dict[str, Any]:
    """Return static info for the Gemini node (no HTTP probe)."""
    return {
        "name": node.name,
        "proxy_path": node.proxy_path,
        "role": node.role,
        "default_model": node.default_model,
        "models": node.models,
        "weight": node.weight,
        "online": True,  # assume available; actual check requires subprocess
        "latency_ms": -1,
    }


async def get_cluster_status() -> dict[str, Any]:
    """Probe every node in the cluster and return unified status dict."""
    cfg = get_config()
    if cfg is None:
        return {"error": "src.config not available", "nodes": {}}

    nodes: dict[str, Any] = {}

    async with httpx.AsyncClient() as client:
        # LM Studio nodes
        for node in cfg.lm_nodes:
            nodes[node.name] = await _probe_lmstudio(client, node)

        # Ollama nodes
        for node in cfg.ollama_nodes:
            nodes[node.name] = await _probe_ollama(client, node)

    # Gemini (static)
    nodes[cfg.gemini_node.name] = _gemini_info(cfg.gemini_node)

    online_count = sum(1 for n in nodes.values() if n.get("online"))
    return {
        "total_nodes": len(nodes),
        "online": online_count,
        "offline": len(nodes) - online_count,
        "nodes": nodes,
    }
