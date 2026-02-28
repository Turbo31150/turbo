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


# ── Domino/Cascade REST API ────────────────────────────────────────────────

@app.get("/api/dominos")
async def api_list_dominos(category: str = ""):
    """List all domino pipelines and DB chains."""
    result = await handle_system_request("list_dominos", {"category": category})
    return JSONResponse(result)


@app.get("/api/dominos/chains")
async def api_list_chains(q: str = "", limit: int = 50):
    """Search DB chains."""
    result = await handle_system_request("list_chains", {"query": q, "limit": limit})
    return JSONResponse(result)


@app.get("/api/dominos/resolve/{trigger}")
async def api_resolve_chain(trigger: str):
    """Resolve a trigger into its full chain."""
    result = await handle_system_request("resolve_chain", {"trigger": trigger})
    return JSONResponse(result)


@app.post("/api/dominos/execute")
async def api_execute_domino(request: Request):
    """Execute a domino by ID or voice text."""
    body = await request.json()
    result = await handle_system_request("execute_domino", body)
    return JSONResponse(result)


@app.post("/api/dominos/execute-chain")
async def api_execute_chain(request: Request):
    """Execute a DB chain by trigger."""
    body = await request.json()
    result = await handle_system_request("execute_chain", body)
    return JSONResponse(result)


@app.get("/api/dominos/logs")
async def api_domino_logs(run_id: str = "", limit: int = 20):
    """Get domino execution logs."""
    result = await handle_system_request("domino_logs", {"run_id": run_id, "limit": limit})
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
    _connected_clients.add(websocket)
    logger.info("WebSocket client connected (%d total)", len(_connected_clients))

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
                elif channel == "system" and action in ("execute_domino", "execute_chain") and not error:
                    await _push_domino_events(websocket, result)
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
        _connected_clients.discard(websocket)
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


async def _push_domino_events(websocket: WebSocket, result: dict) -> None:
    """Push domino cascade execution events."""
    domino = result.get("domino")
    if not domino:
        return

    # Push cascade result
    await websocket.send_json({
        "type": "event",
        "channel": "system",
        "event": "domino_complete",
        "payload": {
            "domino_id": domino.get("domino_id", ""),
            "category": domino.get("category", ""),
            "passed": domino.get("passed", 0),
            "failed": domino.get("failed", 0),
            "skipped": domino.get("skipped", 0),
            "total_ms": domino.get("total_ms", 0),
            "total_steps": domino.get("total_steps", 0),
            "run_id": domino.get("run_id", ""),
            "source": result.get("source", "hardcoded"),
        },
    })

    # Fetch and push detailed step logs
    try:
        run_id = domino.get("run_id", "")
        if run_id:
            from python_ws.routes.system import handle_system_request
            logs = await handle_system_request("domino_logs", {"run_id": run_id})
            if logs.get("logs"):
                await websocket.send_json({
                    "type": "event",
                    "channel": "system",
                    "event": "domino_steps",
                    "payload": {
                        "run_id": run_id,
                        "domino_id": domino.get("domino_id", ""),
                        "steps": logs["logs"],
                    },
                })
    except Exception:
        pass


# ── Background push loops ───────────────────────────────────────────────────

async def _cluster_push_loop(websocket: WebSocket) -> None:
    """Push cluster status every 5 seconds."""
    await push_cluster_events(websocket)


async def _trading_push_loop(websocket: WebSocket) -> None:
    """Push trading updates every 30 seconds."""
    async def send_func(msg: dict):
        await websocket.send_json(msg)
    await push_trading_events(send_func)


# ── Global Push-to-Talk (CTRL key) ────────────────────────────────────────────

_connected_clients: set[WebSocket] = set()

_ptt_hook_started = False
_ptt_active = False


def _start_global_ptt_hook(loop: asyncio.AbstractEventLoop) -> None:
    """Start a global keyboard hook for CTRL push-to-talk.

    When Right-CTRL is pressed/released, broadcast ptt_start/ptt_stop events
    to all connected WebSocket clients so WhisperFlow can start/stop recording
    even when the browser window is not focused.
    """
    global _ptt_hook_started
    if _ptt_hook_started:
        return
    try:
        import keyboard as kb
    except ImportError:
        logger.warning("keyboard library not available — global PTT disabled")
        return

    _ptt_hook_started = True

    def on_ptt_press(e):
        global _ptt_active
        if e.name == "ctrl droit" or e.name == "right ctrl" or e.scan_code == 285:
            if _ptt_active:
                return  # debounce
            _ptt_active = True
            asyncio.run_coroutine_threadsafe(_broadcast_ptt("ptt_start"), loop)

    def on_ptt_release(e):
        global _ptt_active
        if e.name == "ctrl droit" or e.name == "right ctrl" or e.scan_code == 285:
            if not _ptt_active:
                return
            _ptt_active = False
            asyncio.run_coroutine_threadsafe(_broadcast_ptt("ptt_stop"), loop)

    kb.on_press(on_ptt_press)
    kb.on_release(on_ptt_release)
    logger.info("Global PTT hook started (Right-CTRL)")


async def _broadcast_ptt(event_name: str) -> None:
    """Broadcast PTT event to all connected WebSocket clients."""
    msg = {
        "type": "event",
        "channel": "voice",
        "event": event_name,
        "payload": {"key": "ctrl_right", "source": "global_hook"},
    }
    dead: list[WebSocket] = []
    for client in _connected_clients:
        try:
            await client.send_json(msg)
        except Exception:
            dead.append(client)
    for d in dead:
        _connected_clients.discard(d)


# ── Wake Word Detector (OpenWakeWord "jarvis") ───────────────────────────────

_wake_detector = None


def _start_wake_word(loop: asyncio.AbstractEventLoop) -> None:
    """Start OpenWakeWord background listener.

    When 'jarvis' is detected, broadcast wake_detected event to all clients
    so WhisperFlow auto-starts recording (hands-free mode).
    """
    global _wake_detector
    try:
        from src.wake_word import WakeWordDetector
    except ImportError:
        logger.warning("OpenWakeWord not available — wake word disabled")
        return

    def on_wake():
        logger.info("Wake word 'jarvis' detected!")
        asyncio.run_coroutine_threadsafe(_broadcast_wake(), loop)

    _wake_detector = WakeWordDetector(callback=on_wake, threshold=0.7)
    ok = _wake_detector.start()
    if ok:
        logger.info("Wake word detector started (threshold=0.7)")
    else:
        logger.warning("Wake word detector failed to start")
        _wake_detector = None


async def _broadcast_wake() -> None:
    """Broadcast wake word detection to all connected clients."""
    msg = {
        "type": "event",
        "channel": "voice",
        "event": "wake_detected",
        "payload": {"word": "jarvis", "source": "openwakeword"},
    }
    dead: list[WebSocket] = []
    for client in _connected_clients:
        try:
            await client.send_json(msg)
        except Exception:
            dead.append(client)
    for d in dead:
        _connected_clients.discard(d)


# ── REST endpoint for wake word control ──
@app.post("/api/wake/{action}")
async def api_wake_control(action: str):
    """Start/stop/status for wake word detector."""
    global _wake_detector
    if action == "status":
        return JSONResponse({"active": _wake_detector is not None and _wake_detector.is_running})
    if action == "start":
        if _wake_detector and _wake_detector.is_running:
            return JSONResponse({"ok": True, "message": "Already running"})
        loop = asyncio.get_running_loop()
        _start_wake_word(loop)
        running = _wake_detector is not None and _wake_detector.is_running
        return JSONResponse({"ok": running})
    if action == "stop":
        if _wake_detector:
            _wake_detector.stop()
            _wake_detector = None
        return JSONResponse({"ok": True, "message": "Stopped"})
    return JSONResponse({"error": f"Unknown action: {action}"}, status_code=400)


@app.on_event("startup")
async def _setup_ptt_and_wake():
    loop = asyncio.get_running_loop()
    _start_global_ptt_hook(loop)
    _start_wake_word(loop)


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
