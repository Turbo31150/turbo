"""Telegram channel — bot control, message sending, history."""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any

logger = logging.getLogger("jarvis.telegram")

_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
_CHAT = os.environ.get("TELEGRAM_CHAT", "")
_PROXY = "http://127.0.0.1:18800"


def _tg_api(method: str, params: dict | None = None, timeout: int = 10) -> dict:
    """Call Telegram Bot API."""
    if not _TOKEN:
        return {"error": "TELEGRAM_TOKEN not configured"}
    url = f"https://api.telegram.org/bot{_TOKEN}/{method}"
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode())


def _proxy_get(endpoint: str, timeout: int = 5) -> dict:
    """GET on canvas proxy."""
    req = urllib.request.Request(f"{_PROXY}{endpoint}")
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode())


def _proxy_post(endpoint: str, data: dict, timeout: int = 120) -> dict:
    """POST on canvas proxy."""
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{_PROXY}{endpoint}", data=body,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode())


async def handle_telegram_request(action: str, payload: dict | None) -> dict[str, Any]:
    """Handle a telegram channel request."""
    payload = payload or {}

    if action == "send_message":
        message = payload.get("message", "")
        chat_id = payload.get("chat_id", _CHAT)
        if not message:
            return {"error": "missing 'message'"}
        try:
            result = _tg_api("sendMessage", {"chat_id": chat_id, "text": message})
            msg_id = result.get("result", {}).get("message_id")
            return {"ok": True, "message_id": msg_id}
        except Exception as e:
            return {"error": f"sendMessage failed: {e}"}

    if action == "bot_status":
        info = {}
        try:
            me = _tg_api("getMe")
            r = me.get("result", {})
            info["bot"] = f"@{r.get('username', '?')} ({r.get('first_name', '?')})"
        except Exception as e:
            info["bot"] = f"OFFLINE ({e})"
        try:
            h = _proxy_get("/health")
            nodes = h.get("nodes", [])
            online = sum(1 for n in nodes if n.get("status") == "online")
            info["proxy"] = f"OK ({online}/{len(nodes)} nodes)"
        except Exception:
            info["proxy"] = "OFFLINE"
        info["chat_id"] = _CHAT
        return info

    if action == "get_history":
        limit = min(int(payload.get("limit", 20)), 100)
        try:
            data = _tg_api("getUpdates", {"limit": limit, "timeout": 0})
            updates = data.get("result", [])
            messages = []
            for u in updates:
                msg = u.get("message", {})
                frm = msg.get("from", {})
                messages.append({
                    "from": frm.get("username") or frm.get("first_name", "?"),
                    "text": msg.get("text", ""),
                    "date": msg.get("date", 0),
                })
            return {"messages": messages[-limit:], "count": len(messages)}
        except Exception as e:
            return {"error": f"getUpdates: {e}"}

    if action == "proxy_chat":
        text = payload.get("text", "")
        agent = payload.get("agent", "telegram")
        if not text:
            return {"error": "missing 'text'"}
        try:
            result = _proxy_post("/chat", {"agent": agent, "text": text})
            return result
        except Exception as e:
            return {"error": f"proxy /chat: {e}"}

    if action == "proxy_health":
        try:
            return _proxy_get("/health")
        except Exception as e:
            return {"error": f"proxy /health: {e}"}

    return {"error": f"unknown telegram action: {action}"}
