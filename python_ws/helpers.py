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


import re as _re

_THINK_RE = _re.compile(r"<think>[\s\S]*?</think>", _re.IGNORECASE)
_THINK_OPEN_RE = _re.compile(r"<think>[\s\S]*$", _re.IGNORECASE)  # unclosed <think> (truncated output)
_NOTHINK_RE = _re.compile(r"^/no_?think\s*", _re.IGNORECASE)


def strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks and /nothink prefix from model output."""
    text = _THINK_RE.sub("", text)       # closed <think>...</think>
    text = _THINK_OPEN_RE.sub("", text)  # unclosed <think>... (truncated by max_tokens)
    text = _NOTHINK_RE.sub("", text)
    return text.strip()


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

    Handles both string content and content-list formats.
    Priority: message block first, then reasoning block fallback
    (deepseek-r1 may exhaust token budget on reasoning without producing message).
    """
    reasoning_text = ""
    for item in reversed(data.get("output", [])):
        if not isinstance(item, dict):
            continue
        block_type = item.get("type", "")
        c = item.get("content", "")
        if block_type == "message":
            if isinstance(c, str) and c.strip():
                return strip_think_tags(c)
            if isinstance(c, list):
                for part in c:
                    if isinstance(part, dict) and part.get("text", "").strip():
                        return strip_think_tags(part["text"])
        elif block_type == "reasoning" and not reasoning_text:
            if isinstance(c, str) and c.strip():
                reasoning_text = c.strip()
    # Fallback: extract conclusion from reasoning block
    if reasoning_text:
        return _extract_conclusion_from_reasoning(reasoning_text)
    return ""


def _extract_conclusion_from_reasoning(text: str) -> str:
    """Extract the final conclusion from a reasoning block.

    Looks for conclusion markers in French/English, returns last meaningful paragraph.
    """
    import re
    # Look for explicit conclusion markers
    markers = [
        r"(?:donc|ainsi|en conclusion|la reponse|le resultat|il faut|reponse finale)[^.]*[.!]",
        r"(?:therefore|the answer|result is|it takes)[^.]*[.!]",
    ]
    last_match = ""
    for pattern in markers:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            last_match = m.group(0).strip()
    if last_match:
        return last_match
    # Fallback: last 2 non-empty lines (likely the conclusion)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        return " ".join(lines[-2:])[:500]
    return text[:500]
