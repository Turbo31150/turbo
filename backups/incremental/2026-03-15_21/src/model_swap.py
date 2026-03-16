"""JARVIS Model Swap — On-demand model loading for heavy tasks.

Manages transparent model swapping on M1 LM Studio:
- qwen3-8b (default, fast, 46 tok/s) for 90% of tasks
- gpt-oss-20b (heavy, 15 tok/s, 131K ctx) for architecture/deep analysis
- Auto-swap back to qwen3-8b after heavy task completes

Usage:
    from src.model_swap import ensure_model, swap_to_heavy, swap_to_fast
    await ensure_model("gpt-oss-20b")  # loads if not loaded, swaps if needed
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx

logger = logging.getLogger("jarvis.model_swap")

M1_URL = "http://127.0.0.1:1234"
FAST_MODEL = "qwen3-8b"
HEAVY_MODEL = "gpt-oss-20b"

_swap_lock = asyncio.Lock()
_last_swap_ts: float = 0.0
_current_model: str | None = None


async def get_loaded_model() -> str | None:
    """Check which model is currently loaded on M1."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{M1_URL}/api/v1/models")
            data = resp.json()
            for m in data.get("data", data.get("models", [])):
                if m.get("loaded_instances"):
                    return m.get("key", "")
    except (httpx.HTTPError, OSError, ValueError):
        pass
    return None


async def unload_model(model_id: str) -> bool:
    """Unload a model from M1 LM Studio."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{M1_URL}/api/v1/models/unload",
                json={"model": model_id},
            )
            if resp.status_code in (200, 204):
                logger.info("Unloaded model: %s", model_id)
                return True
            # Try alternative endpoint
            resp = await client.delete(f"{M1_URL}/api/v1/models/{model_id}")
            return resp.status_code in (200, 204)
    except (httpx.HTTPError, OSError) as e:
        logger.warning("Unload failed for %s: %s", model_id, e)
    return False


async def load_model(model_id: str, timeout: float = 60.0) -> bool:
    """Load a model on M1 by sending a minimal request (triggers auto-load)."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{M1_URL}/api/v1/chat",
                json={
                    "model": model_id,
                    "input": "/nothink\ntest",
                    "temperature": 0.1,
                    "max_output_tokens": 10,
                    "stream": False,
                    "store": False,
                },
            )
            data = resp.json()
            if data.get("output"):
                logger.info("Loaded model: %s", model_id)
                return True
            if data.get("error"):
                logger.warning("Load failed for %s: %s", model_id, data["error"])
                return False
    except (httpx.HTTPError, OSError, asyncio.TimeoutError) as e:
        logger.warning("Load timeout/error for %s: %s", model_id, e)
    return False


async def ensure_model(model_id: str) -> bool:
    """Ensure a specific model is loaded. Swap if necessary."""
    global _current_model, _last_swap_ts

    async with _swap_lock:
        current = await get_loaded_model()
        _current_model = current

        if current and model_id in current:
            return True  # Already loaded

        # Need to swap
        logger.info("Model swap: %s -> %s", current, model_id)
        t0 = time.monotonic()

        # Unload current model
        if current:
            await unload_model(current)
            await asyncio.sleep(1)  # Brief pause for GPU memory release

        # Load requested model
        ok = await load_model(model_id)
        elapsed = (time.monotonic() - t0) * 1000

        if ok:
            _current_model = model_id
            _last_swap_ts = time.time()
            logger.info("Model swap complete: %s in %.0fms", model_id, elapsed)
        else:
            # Fallback: reload the fast model
            logger.warning("Swap to %s failed, reloading %s", model_id, FAST_MODEL)
            await load_model(FAST_MODEL)
            _current_model = FAST_MODEL

        return ok


async def swap_to_heavy() -> bool:
    """Swap to heavy model (gpt-oss-20b) for complex tasks."""
    return await ensure_model(HEAVY_MODEL)


async def swap_to_fast() -> bool:
    """Swap back to fast model (qwen3-8b) for normal operation."""
    return await ensure_model(FAST_MODEL)


def get_swap_status() -> dict:
    """Return current model swap status."""
    return {
        "current_model": _current_model,
        "last_swap_ts": _last_swap_ts,
        "fast_model": FAST_MODEL,
        "heavy_model": HEAVY_MODEL,
    }
