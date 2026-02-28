"""JARVIS Desktop — FastAPI + WebSocket server on port 9742.

Envelope protocol
-----------------
Client -> Server:
    { "id": "<uuid>", "type": "request", "channel": "<ch>", "action": "<act>", "payload": {...} }

Server -> Client (response):
    { "id": "<uuid>", "type": "response", "channel": "<ch>", "action": "<act>", "payload": {...}, "error": null }

Server -> Client (push event):
    { "type": "event", "channel": "<ch>", "event": "<name>", "payload": {...} }

Channels: cluster, trading, voice, chat, files, system
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ── Ensure turbo root is on sys.path ────────────────────────────────────────
_turbo_root = str(Path(__file__).resolve().parent.parent)
if _turbo_root not in sys.path:
    sys.path.insert(0, _turbo_root)

from python_ws.routes.cluster import handle_cluster_request, push_cluster_events
from python_ws.routes.system import handle_system_request
from python_ws.routes.chat import handle_chat_request
from python_ws.routes.trading import handle_trading_request, push_trading_events
from python_ws.routes.voice import handle_voice_request
from python_ws.routes.files import handle_files_request
from python_ws.routes.dictionary import handle_dictionary_request
from python_ws.routes.sql import sql_router

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jarvis.ws")

# ── Valid channels ───────────────────────────────────────────────────────────
CHANNELS = {"cluster", "trading", "voice", "chat", "files", "system", "dictionary"}

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(title="JARVIS Desktop WS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST API routes ─────────────────────────────────────────────────────────
app.include_router(sql_router, prefix="/sql")

# ── HTTP endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "service": "jarvis-ws", "port": 9742})


@app.get("/api/dictionary")
async def api_dictionary():
    """REST endpoint for full dictionary data (too large for WS)."""
    result = await handle_dictionary_request("get_all", {})
    return JSONResponse(result)


@app.get("/api/dictionary/search")
async def api_dictionary_search(q: str = "", limit: int = 50):
    """Search commands, pipelines, and DB entries."""
    result = await handle_dictionary_request("search", {"query": q, "limit": limit})
    return JSONResponse(result)


@app.get("/api/dictionary/stats")
async def api_dictionary_stats():
    """Dictionary statistics."""
    result = await handle_dictionary_request("get_stats", {})
    return JSONResponse(result)


from fastapi import Request

@app.post("/api/dictionary/command")
async def api_add_command(request: Request):
    """Add a new command to pipeline_dictionary."""
    body = await request.json()
    result = await handle_dictionary_request("add_command", body)
    return JSONResponse(result, status_code=201 if result.get("ok") else 400)


@app.put("/api/dictionary/command/{record_id}")
async def api_edit_command(record_id: int, request: Request):
    """Edit an existing command."""
    body = await request.json()
    body["id"] = record_id
    result = await handle_dictionary_request("edit_command", body)
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


@app.delete("/api/dictionary/command/{record_id}")
async def api_delete_command(record_id: int):
    """Delete a command."""
    result = await handle_dictionary_request("delete_command", {"id": record_id})
    return JSONResponse(result, status_code=200 if result.get("ok") else 404)


@app.post("/api/dictionary/chain")
async def api_add_chain(request: Request):
    """Add a new domino chain."""
    body = await request.json()
    result = await handle_dictionary_request("add_chain", body)
    return JSONResponse(result, status_code=201 if result.get("ok") else 400)


@app.delete("/api/dictionary/chain/{chain_id}")
async def api_delete_chain(chain_id: int):
    """Delete a domino chain."""
    result = await handle_dictionary_request("delete_chain", {"id": chain_id})
    return JSONResponse(result, status_code=200 if result.get("ok") else 404)


@app.post("/api/dictionary/correction")
async def api_add_correction(request: Request):
    """Add or update a voice correction."""
    body = await request.json()
    result = await handle_dictionary_request("add_correction", body)
    return JSONResponse(result, status_code=201 if result.get("ok") else 400)


@app.post("/api/dictionary/reload")
async def api_reload_dict():
    """Force reload the dictionary cache."""
    result = await handle_dictionary_request("reload_dict", {})
    return JSONResponse(result)


# ── WhisperFlow static serving ─────────────────────────────────────────────
_whisperflow_dir = Path(__file__).resolve().parent.parent / "whisperflow"

@app.get("/whisperflow")
@app.get("/whisperflow/")
async def whisperflow_index():
    """Serve WhisperFlow UI at http://127.0.0.1:9742/whisperflow/"""
    return FileResponse(_whisperflow_dir / "index.html")

if _whisperflow_dir.exists():
    app.mount("/whisperflow/static", StaticFiles(directory=str(_whisperflow_dir)), name="whisperflow")


# ── Channel router ──────────────────────────────────────────────────────────

async def _route_request(channel: str, action: str, payload: dict | None) -> dict[str, Any]:
    """Dispatch a request to the appropriate channel handler."""
    if channel == "cluster":
        return await handle_cluster_request(action, payload)

    if channel == "system":
        return await handle_system_request(action, payload)

    if channel == "chat":
        return await handle_chat_request(action, payload or {})

    if channel == "trading":
        return await handle_trading_request(action, payload or {})

    if channel == "voice":
        return await handle_voice_request(action, payload or {})

    if channel == "files":
        return await handle_files_request(action, payload or {})

    if channel == "dictionary":
        return await handle_dictionary_request(action, payload)

    return {"error": f"unknown channel: {channel}"}


# ── WebSocket endpoint ──────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected")

    # Start background push tasks
    bg_tasks: list[asyncio.Task] = []
    bg_tasks.append(asyncio.create_task(_cluster_push_loop(websocket)))
    bg_tasks.append(asyncio.create_task(_trading_push_loop(websocket)))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "id": None,
                    "type": "response",
                    "channel": None,
                    "action": None,
                    "payload": None,
                    "error": "invalid JSON",
                })
                continue

            msg_id = msg.get("id", str(uuid.uuid4()))
            msg_type = msg.get("type")
            channel = msg.get("channel")
            action = msg.get("action")
            payload = msg.get("payload")

            if msg_type != "request":
                await websocket.send_json({
                    "id": msg_id,
                    "type": "response",
                    "channel": channel,
                    "action": action,
                    "payload": None,
                    "error": f"unsupported message type: {msg_type}",
                })
                continue

            if channel not in CHANNELS:
                await websocket.send_json({
                    "id": msg_id,
                    "type": "response",
                    "channel": channel,
                    "action": action,
                    "payload": None,
                    "error": f"unknown channel: {channel}. Valid: {', '.join(sorted(CHANNELS))}",
                })
                continue

            # Route to handler
            try:
                result = await _route_request(channel, action, payload)
                error = result.pop("error", None) if isinstance(result, dict) else None
                await websocket.send_json({
                    "id": msg_id,
                    "type": "response",
                    "channel": channel,
                    "action": action,
                    "payload": result,
                    "error": error,
                })

                # Push follow-up events for channels that need them
                if channel == "chat" and action == "send_message" and not error:
                    await _push_chat_events(websocket, result)
                elif channel == "voice" and action == "stop_recording" and not error:
                    await _push_voice_events(websocket, result)
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                logger.warning("Handler error: %s/%s: %s", channel, action, exc)
                try:
                    await websocket.send_json({
                        "id": msg_id,
                        "type": "response",
                        "channel": channel,
                        "action": action,
                        "payload": None,
                        "error": str(exc),
                    })
                except (WebSocketDisconnect, Exception):
                    raise WebSocketDisconnect(code=1006)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
    finally:
        # Cancel all background tasks
        for task in bg_tasks:
            task.cancel()
        for task in bg_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass


# ── Chat & Voice event pushers ─────────────────────────────────────────────

async def _push_chat_events(websocket: WebSocket, result: dict) -> None:
    """Push agent_message event after chat response."""
    agent_msg = result.get("agent_message")
    if agent_msg:
        await websocket.send_json({
            "type": "event",
            "channel": "chat",
            "event": "agent_message",
            "payload": agent_msg,
        })
        await websocket.send_json({
            "type": "event",
            "channel": "chat",
            "event": "agent_complete",
            "payload": {"task_type": result.get("task_type")},
        })


async def _push_voice_events(websocket: WebSocket, result: dict) -> None:
    """Push transcription_result event after voice transcription."""
    entry = result.get("transcription")
    if entry:
        await websocket.send_json({
            "type": "event",
            "channel": "voice",
            "event": "transcription_result",
            "payload": {
                "text": entry.get("corrected") or entry.get("original", ""),
                "original": entry.get("original", ""),
                "timestamp": entry.get("timestamp"),
            },
        })


# ── Background push loops ───────────────────────────────────────────────────

async def _cluster_push_loop(websocket: WebSocket) -> None:
    """Push cluster status every 5 seconds."""
    await push_cluster_events(websocket)


async def _trading_push_loop(websocket: WebSocket) -> None:
    """Push trading updates every 30 seconds."""
    async def send_func(msg: dict):
        await websocket.send_json(msg)
    await push_trading_events(send_func)


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    import uvicorn
    logger.info("Starting JARVIS WebSocket server on 127.0.0.1:9742")
    uvicorn.run(
        "python_ws.server:app",
        host="127.0.0.1",
        port=9742,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
