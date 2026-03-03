"""Shared helpers for python_ws routes — avoids duplication across modules."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger("jarvis.helpers")

# ── Agent tag stripping ──────────────────────────────────────────────────

AGENT_TAGS = (
    "[M1] ", "[OL1] ", "[M2] ", "[M3] ", "[GEMINI] ", "[CLAUDE] ",
    "[GPT-OSS] ", "[DEVSTRAL-2] ", "[GLM-4] ", "[MINIMAX-M2] ", "[QWEN3] ",
)


def strip_agent_tag(text: str) -> str:
    """Remove leading agent tag (e.g. '[M1] ') from text."""
    for tag in AGENT_TAGS:
        if text.startswith(tag):
            return text[len(tag):]
    return text


# ── WebSocket push loop ─────────────────────────────────────────────────

async def push_loop(
    send_func: Callable[[dict], Awaitable[None]],
    build_payload: Callable[[], Awaitable[dict]],
    *,
    channel: str,
    event: str,
    interval: float = 5.0,
    backoff: float = 2.0,
) -> None:
    """Generic push loop: periodically builds a payload and sends it.

    Args:
        send_func: async callable to send a JSON message (websocket.send_json or similar)
        build_payload: async callable that returns the payload dict
        channel: WebSocket channel name
        event: event name
        interval: seconds between pushes
        backoff: seconds to wait after a transient error
    """
    while True:
        try:
            payload = await build_payload()
            await send_func({
                "type": "event",
                "channel": channel,
                "event": event,
                "payload": payload,
            })
        except (ConnectionError, OSError, asyncio.CancelledError, WebSocketDisconnect):
            break  # Connection closed — stop push loop
        except (asyncio.TimeoutError, RuntimeError, ValueError):
            logger.debug("push_loop[%s/%s] transient error", channel, event, exc_info=True)
            await asyncio.sleep(backoff)
            continue
        await asyncio.sleep(interval)


# ── LM Studio response extraction ───────────────────────────────────────

def extract_lmstudio_content(data: dict) -> str:
    """Extract text content from LM Studio Responses API output.

    Handles both string content and content-list formats,
    scanning output[] in reverse to skip reasoning blocks.
    """
    for item in reversed(data.get("output", [])):
        if isinstance(item, dict) and item.get("type") == "message":
            c = item.get("content", "")
            if isinstance(c, str) and c.strip():
                return c.strip()
            if isinstance(c, list):
                for part in c:
                    if isinstance(part, dict) and part.get("text", "").strip():
                        return part["text"].strip()
    return ""
