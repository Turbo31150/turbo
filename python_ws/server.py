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
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
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
from python_ws.routes.telegram import handle_telegram_request
from python_ws.routes.sql import sql_router
from python_ws.routes.terminal import router as terminal_router
from python_ws.routes.collab import collab_router

# ── Logging ──────────────────────────────────────────────────────────────────
try:
    from src.logging_config import setup_logging
    setup_logging(level="INFO", json_file=True, console=True)
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
logger = logging.getLogger("jarvis.ws")

# ── Valid channels ───────────────────────────────────────────────────────────
CHANNELS = {"cluster", "trading", "voice", "chat", "files", "system", "dictionary", "telegram"}

# ── Connected WebSocket clients ──────────────────────────────────────────────
_connected_clients: set = set()

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(title="JARVIS Desktop WS", version="1.0.0")

_CORS_ORIGINS = os.getenv(
    "JARVIS_CORS_ORIGINS",
    "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:9742",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ── REST API routes ─────────────────────────────────────────────────────────
app.include_router(sql_router, prefix="/sql")
app.include_router(terminal_router)
app.include_router(collab_router)

# ── HTTP endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "service": "jarvis-ws", "port": 9742})


@app.post("/api/tts")
async def api_tts(request: Request):
    """HTTP TTS endpoint — returns MP3 audio bytes for Canvas UI speak()."""
    from fastapi.responses import Response
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "Empty text"}, status_code=400)
    if len(text) > 5000:
        return JSONResponse({"error": "Text too long"}, status_code=400)
    _ALLOWED_VOICES = {"fr-FR-HenriNeural", "fr-FR-DeniseNeural", "en-US-GuyNeural", "en-US-JennyNeural"}
    voice = body.get("voice", "fr-FR-DeniseNeural")
    if voice not in _ALLOWED_VOICES:
        voice = "fr-FR-DeniseNeural"
    try:
        import edge_tts
        import io
        comm = edge_tts.Communicate(text, voice)
        buf = io.BytesIO()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        audio_bytes = buf.getvalue()
        if not audio_bytes:
            return JSONResponse({"error": "TTS produced no audio"}, status_code=500)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except ImportError:
        return JSONResponse({"error": "edge_tts not installed"}, status_code=500)
    except Exception as exc:
        logger.exception("TTS failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Phase 4 REST API v2 ──────────────────────────────────────────────────

@app.get("/api/chat/history")
async def api_chat_history(session_id: str = "", limit: int = 50):
    """Return chat history from SQLite."""
    try:
        import sqlite3
        db_path = Path(_turbo_root) / "data" / "jarvis.db"
        if not db_path.exists():
            return JSONResponse({"history": []})
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        if session_id:
            rows = conn.execute(
                "SELECT * FROM chat_history WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, min(limit, 200)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM chat_history ORDER BY timestamp DESC LIMIT ?",
                (min(limit, 200),),
            ).fetchall()
        conn.close()
        return JSONResponse({"history": [dict(r) for r in rows]})
    except Exception as exc:
        logger.exception("GET /api/chat/history failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/tools/metrics")
async def api_tool_metrics():
    """Return ToolMetrics report."""
    try:
        from src.tools import ToolMetrics
        return JSONResponse({"metrics": ToolMetrics().get_report()})
    except Exception as exc:
        logger.exception("GET /api/tools/metrics failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/cluster/observability")
async def api_observability():
    """Return ObservabilityMatrix report."""
    try:
        from src.observability import observability_matrix
        return JSONResponse({"observability": observability_matrix.get_report()})
    except Exception as exc:
        logger.exception("GET /api/cluster/observability failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/cluster/drift")
async def api_drift():
    """Return DriftDetector report."""
    try:
        from src.drift_detector import drift_detector
        return JSONResponse({"drift": drift_detector.get_report()})
    except Exception as exc:
        logger.exception("GET /api/cluster/drift failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/cluster/autotune")
async def api_autotune():
    """Return AutoTuneScheduler status."""
    try:
        from src.auto_tune import auto_tune
        return JSONResponse({"auto_tune": auto_tune.get_status()})
    except Exception as exc:
        logger.exception("GET /api/cluster/autotune failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/cluster/dashboard")
async def api_cluster_dashboard():
    """Combined dashboard: observability + drift + auto_tune."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        return JSONResponse(orchestrator_v2.get_dashboard())
    except Exception as exc:
        logger.exception("GET /api/cluster/dashboard failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Orchestrator V2 REST API — Phase 4 ──────────────────────────────────────

@app.get("/api/orchestrator/status")
async def api_orch_status():
    """Full orchestrator_v2 dashboard."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        return JSONResponse(orchestrator_v2.get_dashboard())
    except Exception as exc:
        logger.exception("GET /api/orchestrator/status failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/orchestrator/nodes")
async def api_orch_nodes():
    """Per-node stats (calls, latency, success rate, tokens)."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        return JSONResponse(orchestrator_v2.get_node_stats())
    except Exception as exc:
        logger.exception("GET /api/orchestrator/nodes failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/orchestrator/budget")
async def api_orch_budget():
    """Token budget report for current session."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        return JSONResponse(orchestrator_v2.get_budget_report())
    except Exception as exc:
        logger.exception("GET /api/orchestrator/budget failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/orchestrator/budget/reset")
async def api_orch_budget_reset():
    """Reset session budget counters."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        orchestrator_v2.reset_budget()
        return JSONResponse({"ok": True, "message": "Budget reset"})
    except Exception as exc:
        logger.exception("POST /api/orchestrator/budget/reset failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/orchestrator/fallback/{task_type}")
async def api_orch_fallback(task_type: str):
    """Drift-aware fallback chain for a task type."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        chain = orchestrator_v2.fallback_chain(task_type)
        return JSONResponse({"task_type": task_type, "chain": chain})
    except Exception as exc:
        logger.exception("GET /api/orchestrator/fallback failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/orchestrator/best/{task_type}")
async def api_orch_best_node(task_type: str):
    """Best node for a task type (weighted score + drift filter)."""
    try:
        from src.orchestrator_v2 import orchestrator_v2, ROUTING_MATRIX
        matrix_entry = ROUTING_MATRIX.get(task_type, ROUTING_MATRIX.get("simple", []))
        candidates = [n for n, _ in matrix_entry]
        best = orchestrator_v2.get_best_node(candidates, task_type)
        scores = {n: orchestrator_v2.weighted_score(n, task_type) for n in candidates}
        return JSONResponse({"task_type": task_type, "best": best, "scores": scores})
    except Exception as exc:
        logger.exception("GET /api/orchestrator/best failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/orchestrator/health")
async def api_orch_health():
    """Cluster health score 0-100 + active alerts."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        score = orchestrator_v2.health_check()
        alerts = orchestrator_v2.get_alerts()
        return JSONResponse({"health_score": score, "alerts": alerts})
    except Exception as exc:
        logger.exception("GET /api/orchestrator/health failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/orchestrator/routing")
async def api_orch_routing():
    """Full routing matrix."""
    try:
        from src.orchestrator_v2 import ROUTING_MATRIX
        matrix = {k: [{"node": n, "weight": w} for n, w in v] for k, v in ROUTING_MATRIX.items()}
        return JSONResponse(matrix)
    except Exception as exc:
        logger.exception("GET /api/orchestrator/routing failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Autonomous Loop REST API — Phase 4 ──────────────────────────────────────

@app.get("/api/autonomous/status")
async def api_autonomous_status():
    """Autonomous loop status (tasks, events, running state)."""
    try:
        from src.autonomous_loop import autonomous_loop
        return JSONResponse(autonomous_loop.get_status())
    except Exception as exc:
        logger.exception("GET /api/autonomous/status failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/autonomous/events")
async def api_autonomous_events(limit: int = 50):
    """Recent autonomous loop events (alerts, errors)."""
    try:
        from src.autonomous_loop import autonomous_loop
        return JSONResponse({"events": autonomous_loop.get_events(limit)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/autonomous/toggle/{task_name}")
async def api_autonomous_toggle(task_name: str, enabled: bool = True):
    """Enable/disable an autonomous task."""
    try:
        from src.autonomous_loop import autonomous_loop
        autonomous_loop.enable(task_name, enabled)
        return JSONResponse({"ok": True, "task": task_name, "enabled": enabled})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/db/health")
async def api_db_health():
    """Return database health status."""
    try:
        from src.database import get_db_health
        return JSONResponse({"db_health": get_db_health()})
    except Exception as exc:
        logger.exception("GET /api/db/health failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/db/maintenance")
async def api_db_maintenance():
    """Force database maintenance (VACUUM + ANALYZE)."""
    try:
        from src.database import auto_maintenance
        auto_maintenance(force=True)
        return JSONResponse({"ok": True, "message": "Maintenance completed"})
    except Exception as exc:
        logger.exception("POST /api/db/maintenance failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/db/backup")
async def api_db_backup():
    """Create database backup."""
    try:
        from src.database import backup_database
        path = backup_database()
        return JSONResponse({"ok": True, "backup_path": str(path)})
    except Exception as exc:
        logger.exception("POST /api/db/backup failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/intent/classify")
async def api_intent_classify(text: str = ""):
    """Classify text intent."""
    try:
        from src.intent_classifier import intent_classifier
        if not text:
            return JSONResponse({"error": "missing 'text' parameter"}, status_code=400)
        results = intent_classifier.classify(text)
        return JSONResponse({"results": [
            {"intent": r.intent, "confidence": r.confidence, "entities": r.entities}
            for r in results
        ]})
    except Exception as exc:
        logger.exception("GET /api/intent/classify failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/trading/rankings")
async def api_trading_rankings():
    """Return strategy rankings."""
    try:
        from src.trading_engine import strategy_scorer
        return JSONResponse({"rankings": strategy_scorer.get_strategy_rankings()})
    except Exception as exc:
        logger.exception("GET /api/trading/rankings failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Pipeline Composer REST API — Phase 4 Vague 3 ────────────────────────────

@app.post("/api/pipelines/compose")
async def api_pipeline_compose(request: Request):
    """Create a new pipeline from step definitions."""
    try:
        body = await request.json()
        name = body.get("name", "")
        steps = body.get("steps", [])
        if not name or not steps:
            return JSONResponse({"error": "name and steps required"}, status_code=400)

        # Validate steps
        validated = []
        for i, step in enumerate(steps):
            validated.append({
                "node": step.get("node", "M1"),
                "prompt": step.get("prompt", ""),
                "condition": step.get("condition", ""),
                "on_fail": step.get("on_fail", "skip"),
                "timeout_s": step.get("timeout_s", 30),
            })

        # Save to database
        from src.database import get_db_connection
        import json as _json
        conn = get_db_connection("etoile")
        conn.execute(
            "INSERT OR REPLACE INTO pipeline_dictionary (command, category, action_type, steps_json) VALUES (?, 'composed', 'pipeline', ?)",
            (name, _json.dumps(validated)),
        )
        conn.commit()
        conn.close()

        return JSONResponse({"ok": True, "name": name, "steps_count": len(validated)})
    except Exception as exc:
        logger.exception("POST /api/pipelines/compose failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/pipelines/execute")
async def api_pipeline_execute_composed(request: Request):
    """Execute a composed pipeline by name."""
    try:
        body = await request.json()
        name = body.get("name", "")
        if not name:
            return JSONResponse({"error": "name required"}, status_code=400)

        # Load from DB
        from src.database import get_db_connection
        import json as _json
        conn = get_db_connection("etoile")
        row = conn.execute(
            "SELECT steps_json FROM pipeline_dictionary WHERE command = ? AND category = 'composed'",
            (name,),
        ).fetchone()
        conn.close()

        if not row:
            return JSONResponse({"error": f"Pipeline '{name}' not found"}, status_code=404)

        steps = _json.loads(row[0])

        # Execute via domino executor
        from src.domino_executor import DominoExecutor, DominoStep
        executor = DominoExecutor()
        domino_steps = []
        for s in steps:
            domino_steps.append(DominoStep(
                action_type="ia_query",
                action=s["prompt"],
                node=s["node"],
                condition=s.get("condition", ""),
                on_fail=s.get("on_fail", "skip"),
                timeout_s=s.get("timeout_s", 30),
            ))

        result = await asyncio.to_thread(executor.run, domino_steps)
        return JSONResponse({"ok": True, "name": name, "result": result})
    except Exception as exc:
        logger.exception("POST /api/pipelines/execute failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Agent Memory REST API — Phase 4 Vague 3 ────────────────────────────────

@app.post("/api/memory/remember")
async def api_memory_remember(request: Request):
    """Store a memory."""
    try:
        body = await request.json()
        content = body.get("content", "")
        if not content:
            return JSONResponse({"error": "content required"}, status_code=400)
        from src.agent_memory import agent_memory
        mem_id = agent_memory.remember(
            content,
            category=body.get("category", "general"),
            importance=body.get("importance", 1.0),
        )
        return JSONResponse({"ok": True, "id": mem_id})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/memory/recall")
async def api_memory_recall(q: str = "", limit: int = 5, category: str = ""):
    """Search memories by similarity."""
    try:
        from src.agent_memory import agent_memory
        results = agent_memory.recall(q, limit=limit, category=category or None)
        return JSONResponse({"results": results})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/memory/list")
async def api_memory_list(category: str = "", limit: int = 50):
    """List all memories."""
    try:
        from src.agent_memory import agent_memory
        return JSONResponse({"memories": agent_memory.list_all(category or None, limit)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/memory/stats")
async def api_memory_stats():
    """Memory stats."""
    try:
        from src.agent_memory import agent_memory
        return JSONResponse(agent_memory.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.delete("/api/memory/{memory_id}")
async def api_memory_forget(memory_id: int):
    """Delete a memory."""
    try:
        from src.agent_memory import agent_memory
        ok = agent_memory.forget(memory_id)
        return JSONResponse({"ok": ok})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Conversation + LB + Proactive REST API — Phase 4 Vague 4 ────────────────

@app.get("/api/conversations")
async def api_conversations(limit: int = 20, source: str = ""):
    """List recent conversations."""
    try:
        from src.conversation_store import conversation_store
        return JSONResponse({"conversations": conversation_store.list_conversations(limit, source or None)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/conversations/{conv_id}")
async def api_conversation_detail(conv_id: str):
    """Get a conversation with all turns."""
    try:
        from src.conversation_store import conversation_store
        conv = conversation_store.get_conversation(conv_id)
        if not conv:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse(conv)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/conversations/stats/summary")
async def api_conversations_stats():
    """Conversation stats."""
    try:
        from src.conversation_store import conversation_store
        return JSONResponse(conversation_store.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/lb/status")
async def api_lb_status():
    """Load balancer status."""
    try:
        from src.load_balancer import load_balancer
        return JSONResponse(load_balancer.get_status())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/lb/pick/{task_type}")
async def api_lb_pick(task_type: str):
    """Pick best node via LB."""
    try:
        from src.load_balancer import load_balancer
        node = load_balancer.pick(task_type)
        load_balancer.release(node)
        return JSONResponse({"task_type": task_type, "node": node})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/proactive/suggestions")
async def api_proactive_suggestions():
    """Get proactive suggestions."""
    try:
        from src.proactive_agent import proactive_agent
        suggestions = await proactive_agent.analyze()
        return JSONResponse({"suggestions": suggestions})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ═══════════════════════════════════════════════════════════════
# Phase 5: Auto-Optimizer + Event Bus + Metrics
# ═══════════════════════════════════════════════════════════════

@app.post("/api/optimizer/optimize")
async def api_optimizer_optimize():
    """Run auto-optimization cycle."""
    try:
        from src.auto_optimizer import auto_optimizer
        adjustments = auto_optimizer.force_optimize()
        return JSONResponse({"adjustments": adjustments})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/optimizer/history")
async def api_optimizer_history(limit: int = 50):
    """Get optimization history."""
    try:
        from src.auto_optimizer import auto_optimizer
        return JSONResponse({"history": auto_optimizer.get_history(limit)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/optimizer/stats")
async def api_optimizer_stats():
    """Get optimizer stats."""
    try:
        from src.auto_optimizer import auto_optimizer
        return JSONResponse(auto_optimizer.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/eventbus/stats")
async def api_eventbus_stats():
    """Event bus stats."""
    try:
        from src.event_bus import event_bus
        return JSONResponse(event_bus.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/eventbus/events")
async def api_eventbus_events(limit: int = 50):
    """Recent events from bus."""
    try:
        from src.event_bus import event_bus
        return JSONResponse({"events": event_bus.get_events(limit)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/metrics/snapshot")
async def api_metrics_snapshot():
    """Real-time metrics snapshot."""
    try:
        from src.metrics_aggregator import metrics_aggregator
        return JSONResponse(metrics_aggregator.snapshot())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/metrics/history")
async def api_metrics_history(minutes: int = 60):
    """Metrics history."""
    try:
        from src.metrics_aggregator import metrics_aggregator
        return JSONResponse({"history": metrics_aggregator.get_history(minutes)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/metrics/summary")
async def api_metrics_summary():
    """Metrics aggregator summary."""
    try:
        from src.metrics_aggregator import metrics_aggregator
        return JSONResponse(metrics_aggregator.get_summary())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ═══════════════════════════════════════════════════════════════
# Phase 6: Workflow Engine + Session Manager + Alert Manager
# ═══════════════════════════════════════════════════════════════

@app.get("/api/workflows")
async def api_workflow_list(limit: int = 20):
    try:
        from src.workflow_engine import workflow_engine
        return JSONResponse({"workflows": workflow_engine.list_workflows(limit)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/workflows/stats")
async def api_workflow_stats():
    try:
        from src.workflow_engine import workflow_engine
        return JSONResponse(workflow_engine.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/sessions")
async def api_session_list(limit: int = 20):
    try:
        from src.session_manager import session_manager
        return JSONResponse({"sessions": session_manager.list_sessions(limit)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/sessions/stats")
async def api_session_stats():
    try:
        from src.session_manager import session_manager
        return JSONResponse(session_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/alerts/active")
async def api_alerts_active(level: str = None):
    try:
        from src.alert_manager import alert_manager
        return JSONResponse({"alerts": alert_manager.get_active(level)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/alerts/stats")
async def api_alerts_stats():
    try:
        from src.alert_manager import alert_manager
        return JSONResponse(alert_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ═══════════════════════════════════════════════════════════════
# Phase 7: Config + Audit + Diagnostics
# ═══════════════════════════════════════════════════════════════

@app.get("/api/config")
async def api_config_all():
    try:
        from src.config_manager import config_manager
        return JSONResponse(config_manager.get_all())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/config/{section}")
async def api_config_section(section: str):
    try:
        from src.config_manager import config_manager
        return JSONResponse(config_manager.get_section(section))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/config/history")
async def api_config_history():
    try:
        from src.config_manager import config_manager
        return JSONResponse({"history": config_manager.get_history()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/audit/search")
async def api_audit_search(action_type: str = None, source: str = None, query: str = None, limit: int = 20):
    try:
        from src.audit_trail import audit_trail
        return JSONResponse({"entries": audit_trail.search(action_type=action_type, source=source, query=query, limit=limit)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/audit/stats")
async def api_audit_stats(hours: int = 24):
    try:
        from src.audit_trail import audit_trail
        return JSONResponse(audit_trail.get_stats(hours))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/diagnostics/run")
async def api_diagnostics_run():
    try:
        from src.cluster_diagnostics import cluster_diagnostics
        return JSONResponse(cluster_diagnostics.run_diagnostic())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/diagnostics/quick")
async def api_diagnostics_quick():
    try:
        from src.cluster_diagnostics import cluster_diagnostics
        return JSONResponse(cluster_diagnostics.get_quick_status())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/alerts/acknowledge")
async def api_alerts_acknowledge(body: dict = None):
    try:
        from src.alert_manager import alert_manager
        key = (body or {}).get("key", "")
        ok = alert_manager.acknowledge(key)
        return JSONResponse({"acknowledged": ok})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/alerts/resolve")
async def api_alerts_resolve(body: dict = None):
    try:
        from src.alert_manager import alert_manager
        key = (body or {}).get("key", "")
        ok = alert_manager.resolve(key)
        return JSONResponse({"resolved": ok})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Rate Limiter — Phase 8 ──────────────────────────────────────────────

@app.get("/api/ratelimit/stats")
async def api_ratelimit_stats():
    try:
        from src.rate_limiter import rate_limiter
        return JSONResponse(rate_limiter.get_all_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/ratelimit/check")
async def api_ratelimit_check(body: dict = None):
    try:
        from src.rate_limiter import rate_limiter
        node = (body or {}).get("node", "M1")
        allowed = rate_limiter.allow(node)
        return JSONResponse({"node": node, "allowed": allowed})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/ratelimit/configure")
async def api_ratelimit_configure(body: dict = None):
    try:
        from src.rate_limiter import rate_limiter
        b = body or {}
        rate_limiter.configure_node(b.get("node", "M1"), float(b.get("rps", 10)), float(b.get("burst", 20)))
        return JSONResponse({"ok": True})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Task Scheduler — Phase 8 ──────────────────────────────────────────

@app.get("/api/scheduler/jobs")
async def api_scheduler_jobs():
    try:
        from src.task_scheduler import task_scheduler
        return JSONResponse(task_scheduler.list_jobs())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/scheduler/stats")
async def api_scheduler_stats():
    try:
        from src.task_scheduler import task_scheduler
        return JSONResponse(task_scheduler.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/scheduler/add")
async def api_scheduler_add(body: dict = None):
    try:
        from src.task_scheduler import task_scheduler
        b = body or {}
        job_id = task_scheduler.add_job(
            name=b.get("name", "unnamed"), action=b.get("action", "noop"),
            interval_s=float(b.get("interval_s", 60)), params=b.get("params", {}),
            one_shot=bool(b.get("one_shot", False)),
        )
        return JSONResponse({"job_id": job_id})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.delete("/api/scheduler/jobs/{job_id}")
async def api_scheduler_remove(job_id: str):
    try:
        from src.task_scheduler import task_scheduler
        ok = task_scheduler.remove_job(job_id)
        return JSONResponse({"removed": ok})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Health Dashboard — Phase 8 ────────────────────────────────────────

@app.get("/api/health/full")
async def api_health_full():
    try:
        from src.health_dashboard import health_dashboard
        return JSONResponse(health_dashboard.collect())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/health/summary")
async def api_health_summary():
    try:
        from src.health_dashboard import health_dashboard
        return JSONResponse(health_dashboard.get_summary())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/health/history")
async def api_health_history():
    try:
        from src.health_dashboard import health_dashboard
        return JSONResponse(health_dashboard.get_history())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Workflow Execute — Phase 8 ────────────────────────────────────────

@app.post("/api/workflows/execute")
async def api_workflow_execute(body: dict = None):
    try:
        from src.workflow_engine import workflow_engine
        wf_id = (body or {}).get("wf_id", "")
        run_id = await workflow_engine.execute(wf_id)
        run = workflow_engine.get_run(run_id)
        return JSONResponse(run or {"run_id": run_id})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Plugin Manager — Phase 9 ──────────────────────────────────────────

@app.get("/api/plugins")
async def api_plugins():
    try:
        from src.plugin_manager import plugin_manager
        return JSONResponse(plugin_manager.list_plugins())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/plugins/discover")
async def api_plugins_discover():
    try:
        from src.plugin_manager import plugin_manager
        return JSONResponse(plugin_manager.discover())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/plugins/stats")
async def api_plugins_stats():
    try:
        from src.plugin_manager import plugin_manager
        return JSONResponse(plugin_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Command Router — Phase 9 ─────────────────────────────────────────

@app.post("/api/commands/route")
async def api_cmd_route(body: dict = None):
    try:
        from src.command_router import command_router
        text = (body or {}).get("text", "")
        result = command_router.route(text)
        if result:
            return JSONResponse({"route": result.route.name, "score": round(result.score, 3)})
        return JSONResponse({"route": None})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/commands/routes")
async def api_cmd_routes():
    try:
        from src.command_router import command_router
        return JSONResponse(command_router.get_routes())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Resource Monitor — Phase 9 ───────────────────────────────────────

@app.get("/api/resources/sample")
async def api_resource_sample():
    try:
        from src.resource_monitor import resource_monitor
        return JSONResponse(resource_monitor.sample())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/resources/latest")
async def api_resource_latest():
    try:
        from src.resource_monitor import resource_monitor
        return JSONResponse(resource_monitor.get_latest())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/resources/stats")
async def api_resource_stats():
    try:
        from src.resource_monitor import resource_monitor
        return JSONResponse(resource_monitor.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Cache Manager — Phase 11 ──────────────────────────────────────────

@app.get("/api/cache/stats")
async def api_cache_stats():
    try:
        from src.cache_manager import cache_manager
        return JSONResponse(cache_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Secret Vault — Phase 11 ──────────────────────────────────────────

@app.get("/api/vault/list")
async def api_vault_list():
    try:
        from src.secret_vault import secret_vault
        return JSONResponse(secret_vault.list_entries())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/vault/stats")
async def api_vault_stats():
    try:
        from src.secret_vault import secret_vault
        return JSONResponse(secret_vault.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Dependency Graph — Phase 11 ──────────────────────────────────────

@app.get("/api/depgraph")
async def api_depgraph():
    try:
        from src.dependency_graph import dep_graph
        return JSONResponse(dep_graph.get_graph())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/depgraph/order")
async def api_depgraph_order():
    try:
        from src.dependency_graph import dep_graph
        return JSONResponse(dep_graph.topological_sort())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/depgraph/stats")
async def api_depgraph_stats():
    try:
        from src.dependency_graph import dep_graph
        return JSONResponse(dep_graph.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Retry Manager — Phase 10 ──────────────────────────────────────────

@app.get("/api/retry/stats")
async def api_retry_stats():
    try:
        from src.retry_manager import retry_manager
        return JSONResponse(retry_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Data Pipeline — Phase 10 ─────────────────────────────────────────

@app.get("/api/pipelines/list")
async def api_pipeline_list():
    try:
        from src.data_pipeline import data_pipeline
        return JSONResponse(data_pipeline.list_pipelines())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/pipelines/stats")
async def api_pipeline_stats():
    try:
        from src.data_pipeline import data_pipeline
        return JSONResponse(data_pipeline.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Service Registry — Phase 10 ──────────────────────────────────────

@app.get("/api/services")
async def api_service_list():
    try:
        from src.service_registry import service_registry
        return JSONResponse(service_registry.list_services())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/services/register")
async def api_service_register(body: dict = None):
    try:
        from src.service_registry import service_registry
        b = body or {}
        service_registry.register(b.get("name", ""), b.get("url", ""), b.get("service_type", "generic"))
        return JSONResponse({"ok": True})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/services/heartbeat")
async def api_service_heartbeat(body: dict = None):
    try:
        from src.service_registry import service_registry
        ok = service_registry.heartbeat((body or {}).get("name", ""))
        return JSONResponse({"ok": ok})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/services/stats")
async def api_service_stats():
    try:
        from src.service_registry import service_registry
        return JSONResponse(service_registry.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Telegram Bot REST API ──────────────────────────────────────────────

@app.get("/api/telegram/status")
async def api_telegram_status():
    """Telegram bot status (bot identity + proxy health)."""
    try:
        from python_ws.routes.telegram import handle_telegram_request
        return JSONResponse(await handle_telegram_request("bot_status", {}))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/telegram/send")
async def api_telegram_send(request: Request):
    """Send a message via Telegram bot."""
    try:
        from python_ws.routes.telegram import handle_telegram_request
        body = await request.json()
        return JSONResponse(await handle_telegram_request("send_message", body))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/telegram/history")
async def api_telegram_history(limit: int = 20):
    """Recent Telegram messages."""
    try:
        from python_ws.routes.telegram import handle_telegram_request
        return JSONResponse(await handle_telegram_request("get_history", {"limit": limit}))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/telegram/chat")
async def api_telegram_chat(request: Request):
    """Send a query through the cluster via Telegram proxy."""
    try:
        from python_ws.routes.telegram import handle_telegram_request
        body = await request.json()
        return JSONResponse(await handle_telegram_request("proxy_chat", body))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Notification Hub — Phase 12 ────────────────────────────────────────

@app.post("/api/notifications/send")
async def api_notif_send(request: Request):
    try:
        from src.notification_hub import notification_hub
        body = await request.json()
        sent = notification_hub.send(
            body.get("message", ""), level=body.get("level", "info"),
            source=body.get("source", "api"),
        )
        return JSONResponse({"sent_channels": sent})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/notifications/history")
async def api_notif_history():
    try:
        from src.notification_hub import notification_hub
        return JSONResponse(notification_hub.get_history())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/notifications/channels")
async def api_notif_channels():
    try:
        from src.notification_hub import notification_hub
        return JSONResponse(notification_hub.get_channels())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/notifications/stats")
async def api_notif_stats():
    try:
        from src.notification_hub import notification_hub
        return JSONResponse(notification_hub.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Feature Flags — Phase 12 ──────────────────────────────────────────

@app.get("/api/flags")
async def api_flag_list():
    try:
        from src.feature_flags import feature_flags
        return JSONResponse(feature_flags.list_flags())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/flags/check")
async def api_flag_check(name: str = "", context: str = ""):
    try:
        from src.feature_flags import feature_flags
        enabled = feature_flags.is_enabled(name, context or None)
        return JSONResponse({"flag": name, "enabled": enabled})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/flags/toggle")
async def api_flag_toggle(request: Request):
    try:
        from src.feature_flags import feature_flags
        body = await request.json()
        ok = feature_flags.toggle(body.get("name", ""), body.get("enabled"))
        return JSONResponse({"toggled": ok})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/flags/stats")
async def api_flag_stats():
    try:
        from src.feature_flags import feature_flags
        return JSONResponse(feature_flags.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Backup Manager — Phase 12 ─────────────────────────────────────────

@app.get("/api/backups")
async def api_backup_list():
    try:
        from src.backup_manager import backup_manager
        return JSONResponse(backup_manager.list_backups())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/backups/create")
async def api_backup_create(request: Request):
    try:
        from src.backup_manager import backup_manager
        from pathlib import Path
        body = await request.json()
        entry = backup_manager.backup_file(Path(body.get("source", "")), tag=body.get("tag", ""))
        if entry:
            return JSONResponse({"backup_id": entry.backup_id, "status": entry.status})
        return JSONResponse({"error": "Source not found"}, status_code=404)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/backups/stats")
async def api_backup_stats():
    try:
        from src.backup_manager import backup_manager
        return JSONResponse(backup_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Session Manager V2 — Phase 13 ──────────────────────────────────────

@app.get("/api/sessions_v2")
async def api_session_v2_list():
    try:
        from src.session_manager_v2 import session_manager_v2
        return JSONResponse(session_manager_v2.list_sessions())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/sessions_v2/create")
async def api_session_v2_create(request: Request):
    try:
        from src.session_manager_v2 import session_manager_v2
        body = await request.json()
        s = session_manager_v2.create(body.get("owner", "api"))
        return JSONResponse({"session_id": s.session_id, "owner": s.owner})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/sessions_v2/stats")
async def api_session_v2_stats():
    try:
        from src.session_manager_v2 import session_manager_v2
        return JSONResponse(session_manager_v2.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Queue Manager — Phase 13 ──────────────────────────────────────────

@app.get("/api/queue")
async def api_queue_list():
    try:
        from src.queue_manager import queue_manager
        return JSONResponse(queue_manager.list_tasks())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/queue/stats")
async def api_queue_stats():
    try:
        from src.queue_manager import queue_manager
        return JSONResponse(queue_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── API Gateway — Phase 13 ────────────────────────────────────────────

@app.get("/api/gateway/routes")
async def api_gw_routes():
    try:
        from src.api_gateway import api_gateway
        return JSONResponse(api_gateway.get_routes())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/gateway/clients")
async def api_gw_clients():
    try:
        from src.api_gateway import api_gateway
        return JSONResponse(api_gateway.get_clients())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/gateway/stats")
async def api_gw_stats():
    try:
        from src.api_gateway import api_gateway
        return JSONResponse(api_gateway.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Template Engine — Phase 14 ─────────────────────────────────────────

@app.get("/api/templates")
async def api_template_list():
    try:
        from src.template_engine import template_engine
        return JSONResponse(template_engine.list_templates())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/templates/stats")
async def api_template_stats():
    try:
        from src.template_engine import template_engine
        return JSONResponse(template_engine.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── State Machine — Phase 14 ──────────────────────────────────────────

@app.get("/api/fsm")
async def api_fsm_list():
    try:
        from src.state_machine import state_machine_mgr
        return JSONResponse(state_machine_mgr.list_machines())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/fsm/stats")
async def api_fsm_stats():
    try:
        from src.state_machine import state_machine_mgr
        return JSONResponse(state_machine_mgr.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Log Aggregator — Phase 14 ─────────────────────────────────────────

@app.get("/api/logagg")
async def api_logagg_query():
    try:
        from src.log_aggregator import log_aggregator
        return JSONResponse(log_aggregator.query(limit=100))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/logagg/sources")
async def api_logagg_sources():
    try:
        from src.log_aggregator import log_aggregator
        return JSONResponse(log_aggregator.get_sources())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/logagg/stats")
async def api_logagg_stats():
    try:
        from src.log_aggregator import log_aggregator
        return JSONResponse(log_aggregator.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Permission Manager — Phase 15 ──────────────────────────────────────

@app.get("/api/permissions/roles")
async def api_perm_roles():
    try:
        from src.permission_manager import permission_manager
        return JSONResponse(permission_manager.list_roles())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/permissions/users")
async def api_perm_users():
    try:
        from src.permission_manager import permission_manager
        return JSONResponse(permission_manager.list_users())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/permissions/stats")
async def api_perm_stats():
    try:
        from src.permission_manager import permission_manager
        return JSONResponse(permission_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Environment Manager — Phase 15 ────────────────────────────────────

@app.get("/api/env/profiles")
async def api_env_profiles():
    try:
        from src.env_manager import env_manager
        return JSONResponse(env_manager.list_profiles())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/env/stats")
async def api_env_stats():
    try:
        from src.env_manager import env_manager
        return JSONResponse(env_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Telemetry — Phase 15 ──────────────────────────────────────────────

@app.get("/api/telemetry/counters")
async def api_telemetry_counters():
    try:
        from src.telemetry_collector import telemetry
        return JSONResponse(telemetry.get_counters())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/telemetry/gauges")
async def api_telemetry_gauges():
    try:
        from src.telemetry_collector import telemetry
        return JSONResponse(telemetry.get_gauges())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/telemetry/stats")
async def api_telemetry_stats():
    try:
        from src.telemetry_collector import telemetry
        return JSONResponse(telemetry.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Event Store — Phase 16 ───────────────────────────────────────────────

@app.get("/api/evstore/streams")
async def api_evstore_streams():
    try:
        from src.event_store import event_store
        return JSONResponse({"streams": event_store.streams()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/evstore/events")
async def api_evstore_events(stream: str = "", limit: int = 50):
    try:
        from src.event_store import event_store
        if stream:
            events = event_store.get_stream(stream)[-limit:]
        else:
            events = event_store.get_all(limit=limit)
        return JSONResponse([
            {"id": e.event_id, "stream": e.stream, "type": e.event_type,
             "version": e.version, "data": e.data, "timestamp": e.timestamp}
            for e in events
        ])
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/evstore/stats")
async def api_evstore_stats():
    try:
        from src.event_store import event_store
        return JSONResponse(event_store.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Webhook Manager — Phase 16 ──────────────────────────────────────────

@app.get("/api/webhooks/list")
async def api_webhook_list():
    try:
        from src.webhook_manager import webhook_manager
        return JSONResponse(webhook_manager.list_endpoints())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/webhooks/history")
async def api_webhook_history(name: str = ""):
    try:
        from src.webhook_manager import webhook_manager
        return JSONResponse(webhook_manager.get_history(webhook_name=name or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/webhooks/stats")
async def api_webhook_stats():
    try:
        from src.webhook_manager import webhook_manager
        return JSONResponse(webhook_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Health Probe — Phase 16 ─────────────────────────────────────────────

@app.get("/api/healthprobe/list")
async def api_hprobe_list():
    try:
        from src.health_probe import health_probe
        return JSONResponse(health_probe.list_probes())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/healthprobe/run")
async def api_hprobe_run(name: str = ""):
    try:
        from src.health_probe import health_probe
        if name:
            r = health_probe.run_check(name)
            if not r:
                return JSONResponse({"error": "probe not found"}, status_code=404)
            return JSONResponse({"name": r.name, "status": r.status.value,
                                  "latency_ms": r.latency_ms, "message": r.message})
        results = health_probe.run_all()
        return JSONResponse([
            {"name": r.name, "status": r.status.value,
             "latency_ms": r.latency_ms, "message": r.message}
            for r in results
        ])
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/healthprobe/stats")
async def api_hprobe_stats():
    try:
        from src.health_probe import health_probe
        return JSONResponse(health_probe.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Service Mesh — Phase 17 ──────────────────────────────────────────────

@app.get("/api/mesh/services")
async def api_mesh_services():
    try:
        from src.service_mesh import service_mesh
        return JSONResponse(service_mesh.list_services())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/mesh/names")
async def api_mesh_names():
    try:
        from src.service_mesh import service_mesh
        return JSONResponse({"services": service_mesh.list_service_names()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/mesh/stats")
async def api_mesh_stats():
    try:
        from src.service_mesh import service_mesh
        return JSONResponse(service_mesh.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Config Vault — Phase 17 ─────────────────────────────────────────────

@app.get("/api/vault/namespaces")
async def api_vault_namespaces():
    try:
        from src.config_vault import config_vault
        return JSONResponse({"namespaces": config_vault.list_namespaces()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/vault/keys")
async def api_vault_keys(namespace: str = "default"):
    try:
        from src.config_vault import config_vault
        return JSONResponse({"namespace": namespace, "keys": config_vault.list_keys(namespace)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/vault/stats")
async def api_vault_stats():
    try:
        from src.config_vault import config_vault
        return JSONResponse(config_vault.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Rule Engine — Phase 17 ──────────────────────────────────────────────

@app.get("/api/rules/list")
async def api_rules_list(group: str = ""):
    try:
        from src.rule_engine import rule_engine
        return JSONResponse(rule_engine.list_rules(group=group or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/rules/groups")
async def api_rules_groups():
    try:
        from src.rule_engine import rule_engine
        return JSONResponse({"groups": rule_engine.list_groups()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/rules/stats")
async def api_rules_stats():
    try:
        from src.rule_engine import rule_engine
        return JSONResponse(rule_engine.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Retry Policy — Phase 18 ──────────────────────────────────────────────

@app.get("/api/retry/policies")
async def api_retry_policies():
    try:
        from src.retry_policy import retry_manager
        return JSONResponse(retry_manager.list_policies())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/retry/stats")
async def api_retry_stats():
    try:
        from src.retry_policy import retry_manager
        return JSONResponse(retry_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Message Broker — Phase 18 ───────────────────────────────────────────

@app.get("/api/broker/topics")
async def api_broker_topics():
    try:
        from src.message_broker import message_broker
        return JSONResponse({"topics": message_broker.list_topics()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/broker/stats")
async def api_broker_stats():
    try:
        from src.message_broker import message_broker
        return JSONResponse(message_broker.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Command Registry — Phase 18 ─────────────────────────────────────────

@app.get("/api/commands/list")
async def api_cmdreg_list(category: str = ""):
    try:
        from src.command_registry import command_registry
        return JSONResponse(command_registry.list_commands(category=category or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/commands/stats")
async def api_cmdreg_stats():
    try:
        from src.command_registry import command_registry
        return JSONResponse(command_registry.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Process Manager — Phase 19 ───────────────────────────────────────────

@app.get("/api/processes/list")
async def api_procmgr_list(group: str = ""):
    try:
        from src.process_manager import process_manager
        return JSONResponse(process_manager.list_processes(group=group or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/processes/events")
async def api_procmgr_events(name: str = ""):
    try:
        from src.process_manager import process_manager
        return JSONResponse(process_manager.get_events(name=name or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/processes/stats")
async def api_procmgr_stats():
    try:
        from src.process_manager import process_manager
        return JSONResponse(process_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Data Validator — Phase 19 ────────────────────────────────────────────

@app.get("/api/validator/schemas")
async def api_dataval_schemas():
    try:
        from src.data_validator import data_validator
        return JSONResponse(data_validator.list_schemas())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/validator/history")
async def api_dataval_history():
    try:
        from src.data_validator import data_validator
        return JSONResponse(data_validator.get_history())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/validator/stats")
async def api_dataval_stats():
    try:
        from src.data_validator import data_validator
        return JSONResponse(data_validator.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── File Watcher — Phase 19 ─────────────────────────────────────────────

@app.get("/api/filewatcher/list")
async def api_fwatch_list(group: str = ""):
    try:
        from src.file_watcher import file_watcher
        return JSONResponse(file_watcher.list_watches(group=group or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/filewatcher/events")
async def api_fwatch_events(watch_name: str = ""):
    try:
        from src.file_watcher import file_watcher
        return JSONResponse(file_watcher.get_events(watch_name=watch_name or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/filewatcher/stats")
async def api_fwatch_stats():
    try:
        from src.file_watcher import file_watcher
        return JSONResponse(file_watcher.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Clipboard Manager — Phase 20 ─────────────────────────────────────────

@app.get("/api/clipboard/history")
async def api_clipmgr_history(category: str = ""):
    try:
        from src.clipboard_manager import clipboard_manager
        return JSONResponse(clipboard_manager.get_history(category=category or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/clipboard/search")
async def api_clipmgr_search(query: str = ""):
    try:
        from src.clipboard_manager import clipboard_manager
        return JSONResponse(clipboard_manager.search(query))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/clipboard/stats")
async def api_clipmgr_stats():
    try:
        from src.clipboard_manager import clipboard_manager
        return JSONResponse(clipboard_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Shortcut Manager — Phase 20 ─────────────────────────────────────────

@app.get("/api/hotkeys/list")
async def api_hotkey_list(group: str = ""):
    try:
        from src.shortcut_manager import shortcut_manager
        return JSONResponse(shortcut_manager.list_shortcuts(group=group or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/hotkeys/activations")
async def api_hotkey_activations(name: str = ""):
    try:
        from src.shortcut_manager import shortcut_manager
        return JSONResponse(shortcut_manager.get_activations(name=name or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/hotkeys/stats")
async def api_hotkey_stats():
    try:
        from src.shortcut_manager import shortcut_manager
        return JSONResponse(shortcut_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Snapshot Manager — Phase 20 ──────────────────────────────────────────

@app.get("/api/snapshots/list")
async def api_snapmgr_list(tag: str = ""):
    try:
        from src.snapshot_manager import snapshot_manager
        return JSONResponse(snapshot_manager.list_snapshots(tag=tag or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/snapshots/restores")
async def api_snapmgr_restores():
    try:
        from src.snapshot_manager import snapshot_manager
        return JSONResponse(snapshot_manager.get_restore_history())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/snapshots/stats")
async def api_snapmgr_stats():
    try:
        from src.snapshot_manager import snapshot_manager
        return JSONResponse(snapshot_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Network Scanner — Phase 21 ───────────────────────────────────────────

@app.get("/api/netscan/profiles")
async def api_netscan_profiles():
    try:
        from src.network_scanner import network_scanner
        return JSONResponse(network_scanner.list_profiles())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/netscan/history")
async def api_netscan_history():
    try:
        from src.network_scanner import network_scanner
        return JSONResponse(network_scanner.get_history())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/netscan/stats")
async def api_netscan_stats():
    try:
        from src.network_scanner import network_scanner
        return JSONResponse(network_scanner.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Cron Manager — Phase 21 ─────────────────────────────────────────────

@app.get("/api/cron/list")
async def api_cron_list(group: str = ""):
    try:
        from src.cron_manager import cron_manager
        return JSONResponse(cron_manager.list_jobs(group=group or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/cron/executions")
async def api_cron_executions(name: str = ""):
    try:
        from src.cron_manager import cron_manager
        return JSONResponse(cron_manager.get_executions(name=name or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/cron/stats")
async def api_cron_stats():
    try:
        from src.cron_manager import cron_manager
        return JSONResponse(cron_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── App Launcher — Phase 21 ─────────────────────────────────────────────

@app.get("/api/apps/list")
async def api_applnch_list(group: str = ""):
    try:
        from src.app_launcher import app_launcher
        return JSONResponse(app_launcher.list_apps(group=group or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/apps/history")
async def api_applnch_history(app_name: str = ""):
    try:
        from src.app_launcher import app_launcher
        return JSONResponse(app_launcher.get_history(app_name=app_name or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/apps/stats")
async def api_applnch_stats():
    try:
        from src.app_launcher import app_launcher
        return JSONResponse(app_launcher.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Email Sender — Phase 22 ──────────────────────────────────────────────

@app.get("/api/email/list")
async def api_emailsend_list(status: str = ""):
    try:
        from src.email_sender import email_sender
        return JSONResponse(email_sender.list_messages(status=status or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/email/templates")
async def api_emailsend_templates():
    try:
        from src.email_sender import email_sender
        return JSONResponse(email_sender.list_templates())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/email/stats")
async def api_emailsend_stats():
    try:
        from src.email_sender import email_sender
        return JSONResponse(email_sender.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── System Profiler — Phase 22 ──────────────────────────────────────────

@app.get("/api/profiler/profiles")
async def api_sysprof_profiles(tag: str = ""):
    try:
        from src.system_profiler import system_profiler
        return JSONResponse(system_profiler.list_profiles(tag=tag or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/profiler/benchmarks")
async def api_sysprof_benchmarks():
    try:
        from src.system_profiler import system_profiler
        return JSONResponse(system_profiler.list_benchmarks())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/profiler/stats")
async def api_sysprof_stats():
    try:
        from src.system_profiler import system_profiler
        return JSONResponse(system_profiler.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Context Manager — Phase 22 ──────────────────────────────────────────

@app.get("/api/contexts/list")
async def api_ctxmgr_list(tag: str = ""):
    try:
        from src.context_manager import context_manager
        return JSONResponse(context_manager.list_contexts(tag=tag or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/contexts/events")
async def api_ctxmgr_events(context_id: str = ""):
    try:
        from src.context_manager import context_manager
        return JSONResponse(context_manager.get_events(context_id=context_id or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/contexts/stats")
async def api_ctxmgr_stats():
    try:
        from src.context_manager import context_manager
        return JSONResponse(context_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Window Manager — Phase 23 ────────────────────────────────────────────

@app.get("/api/windows/list")
async def api_winmgr_list(visible_only: bool = True):
    try:
        from src.window_manager import window_manager
        return JSONResponse(window_manager.list_windows(visible_only=visible_only))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/windows/events")
async def api_winmgr_events(limit: int = 50):
    try:
        from src.window_manager import window_manager
        return JSONResponse(window_manager.get_events(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/windows/stats")
async def api_winmgr_stats():
    try:
        from src.window_manager import window_manager
        return JSONResponse(window_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Power Manager — Phase 23 ─────────────────────────────────────────────

@app.get("/api/power/battery")
async def api_pwrmgr_battery():
    try:
        from src.power_manager import power_manager
        return JSONResponse(power_manager.get_battery_status())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/power/events")
async def api_pwrmgr_events(limit: int = 50):
    try:
        from src.power_manager import power_manager
        return JSONResponse(power_manager.get_events(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/power/stats")
async def api_pwrmgr_stats():
    try:
        from src.power_manager import power_manager
        return JSONResponse(power_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Download Manager — Phase 23 ──────────────────────────────────────────

@app.get("/api/downloads/list")
async def api_dlmgr_list(status: str = ""):
    try:
        from src.download_manager import download_manager
        return JSONResponse(download_manager.list_downloads(status=status or None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/downloads/history")
async def api_dlmgr_history():
    try:
        from src.download_manager import download_manager
        return JSONResponse(download_manager.list_downloads(limit=100))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/downloads/stats")
async def api_dlmgr_stats():
    try:
        from src.download_manager import download_manager
        return JSONResponse(download_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Registry Manager — Phase 24 ───────────────────────────────────────────

@app.get("/api/registry/favorites")
async def api_regmgr_favorites():
    try:
        from src.registry_manager import registry_manager
        return JSONResponse(registry_manager.list_favorites())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/registry/events")
async def api_regmgr_events(limit: int = 50):
    try:
        from src.registry_manager import registry_manager
        return JSONResponse(registry_manager.get_events(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/registry/stats")
async def api_regmgr_stats():
    try:
        from src.registry_manager import registry_manager
        return JSONResponse(registry_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Service Controller — Phase 24 ────────────────────────────────────────

@app.get("/api/winsvc/list")
async def api_svcctl_list_p24(state: str = "all"):
    try:
        from src.service_controller import service_controller
        return JSONResponse(service_controller.list_services(state=state))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/winsvc/events")
async def api_svcctl_events(limit: int = 50):
    try:
        from src.service_controller import service_controller
        return JSONResponse(service_controller.get_events(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/winsvc/stats")
async def api_svcctl_stats_p24():
    try:
        from src.service_controller import service_controller
        return JSONResponse(service_controller.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Disk Monitor — Phase 24 ──────────────────────────────────────────────

@app.get("/api/disks/drives")
async def api_diskmon_drives():
    try:
        from src.disk_monitor import disk_monitor
        return JSONResponse(disk_monitor.list_drives())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/disks/alerts")
async def api_diskmon_alerts(limit: int = 50):
    try:
        from src.disk_monitor import disk_monitor
        return JSONResponse(disk_monitor.get_alerts(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/disks/stats")
async def api_diskmon_stats():
    try:
        from src.disk_monitor import disk_monitor
        return JSONResponse(disk_monitor.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Audio Controller — Phase 25 ───────────────────────────────────────────

@app.get("/api/audio/presets")
async def api_audictl_presets():
    try:
        from src.audio_controller import audio_controller
        return JSONResponse(audio_controller.list_presets())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/audio/events")
async def api_audictl_events(limit: int = 50):
    try:
        from src.audio_controller import audio_controller
        return JSONResponse(audio_controller.get_events(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/audio/stats")
async def api_audictl_stats():
    try:
        from src.audio_controller import audio_controller
        return JSONResponse(audio_controller.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Startup Manager — Phase 25 ───────────────────────────────────────────

@app.get("/api/startup/list")
async def api_startup_list(scope: str = "user"):
    try:
        from src.startup_manager import startup_manager
        return JSONResponse(startup_manager.list_entries(scope=scope))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/startup/events")
async def api_startup_events(limit: int = 50):
    try:
        from src.startup_manager import startup_manager
        return JSONResponse(startup_manager.get_events(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/startup/stats")
async def api_startup_stats():
    try:
        from src.startup_manager import startup_manager
        return JSONResponse(startup_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Screen Capture — Phase 25 ────────────────────────────────────────────

@app.get("/api/captures/list")
async def api_scrcap_list(limit: int = 50):
    try:
        from src.screen_capture import screen_capture
        return JSONResponse(screen_capture.list_captures(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/captures/events")
async def api_scrcap_events(limit: int = 50):
    try:
        from src.screen_capture import screen_capture
        return JSONResponse(screen_capture.get_events(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/captures/stats")
async def api_scrcap_stats():
    try:
        from src.screen_capture import screen_capture
        return JSONResponse(screen_capture.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── WiFi Manager — Phase 26 ───────────────────────────────────────────────

@app.get("/api/wifi/profiles")
async def api_wifimgr_profiles():
    try:
        from src.wifi_manager import wifi_manager
        return JSONResponse(wifi_manager.list_profiles())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/wifi/events")
async def api_wifimgr_events(limit: int = 50):
    try:
        from src.wifi_manager import wifi_manager
        return JSONResponse(wifi_manager.get_events(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/wifi/stats")
async def api_wifimgr_stats():
    try:
        from src.wifi_manager import wifi_manager
        return JSONResponse(wifi_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Display Manager — Phase 26 ───────────────────────────────────────────

@app.get("/api/displays/list")
async def api_dispmgr_list():
    try:
        from src.display_manager import display_manager
        return JSONResponse(display_manager.list_displays())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/displays/events")
async def api_dispmgr_events(limit: int = 50):
    try:
        from src.display_manager import display_manager
        return JSONResponse(display_manager.get_events(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/displays/stats")
async def api_dispmgr_stats():
    try:
        from src.display_manager import display_manager
        return JSONResponse(display_manager.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── USB Monitor — Phase 26 ───────────────────────────────────────────────

@app.get("/api/usb/events")
async def api_usbmon_events(limit: int = 50):
    try:
        from src.usb_monitor import usb_monitor
        return JSONResponse(usb_monitor.get_events(limit=limit))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/usb/changes")
async def api_usbmon_changes():
    try:
        from src.usb_monitor import usb_monitor
        return JSONResponse(usb_monitor.detect_changes())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/usb/stats")
async def api_usbmon_stats():
    try:
        from src.usb_monitor import usb_monitor
        return JSONResponse(usb_monitor.get_stats())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/models")
async def api_models():
    """Return all available models with online/offline status."""
    try:
        from python_ws.routes.chat import get_models_with_status
        models = await get_models_with_status()
        return JSONResponse({"models": models})
    except (ImportError, OSError, KeyError, ValueError) as exc:
        logger.exception("GET /api/models failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/dictionary")
async def api_dictionary():
    """REST endpoint for full dictionary data (too large for WS)."""
    try:
        result = await handle_dictionary_request("get_all", {})
        return JSONResponse(result)
    except (OSError, KeyError, ValueError) as exc:
        logger.exception("GET /api/dictionary failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


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


async def _parse_json(request: Request) -> dict:
    """Parse JSON body with proper error handling."""
    try:
        return await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")


@app.post("/api/dictionary/command")
async def api_add_command(request: Request):
    """Add a new command to pipeline_dictionary."""
    body = await _parse_json(request)
    result = await handle_dictionary_request("add_command", body)
    return JSONResponse(result, status_code=201 if result.get("ok") else 400)


@app.put("/api/dictionary/command/{record_id}")
async def api_edit_command(record_id: int, request: Request):
    """Edit an existing command."""
    body = await _parse_json(request)
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
    body = await _parse_json(request)
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
    body = await _parse_json(request)
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
    try:
        result = await handle_system_request("list_dominos", {"category": category})
        return JSONResponse(result)
    except (OSError, KeyError, ValueError) as exc:
        logger.exception("GET /api/dominos failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/dominos/chains")
async def api_list_chains(q: str = "", limit: int = 50):
    """Search DB chains."""
    result = await handle_system_request("list_chains", {"query": q, "limit": limit})
    return JSONResponse(result)


@app.get("/api/dominos/resolve/{trigger}")
async def api_resolve_chain(trigger: str):
    """Resolve a trigger into its full chain."""
    try:
        result = await handle_system_request("resolve_chain", {"trigger": trigger})
        return JSONResponse(result)
    except (OSError, KeyError, ValueError) as exc:
        logger.exception("GET /api/dominos/resolve failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/dominos/execute")
async def api_execute_domino(request: Request):
    """Execute a domino by ID or voice text."""
    body = await _parse_json(request)
    result = await handle_system_request("execute_domino", body)
    return JSONResponse(result)


@app.post("/api/dominos/execute-chain")
async def api_execute_chain(request: Request):
    """Execute a DB chain by trigger."""
    body = await _parse_json(request)
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
    index = _whisperflow_dir / "index.html"
    if not index.exists():
        return JSONResponse({"error": "WhisperFlow UI not found"}, status_code=404)
    return FileResponse(index)

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

    if channel == "telegram":
        return await handle_telegram_request(action, payload or {})

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
    bg_tasks.append(asyncio.create_task(_orchestrator_push_loop(websocket)))

    try:
        while True:
            raw = await websocket.receive_text()
            # Limit message size to prevent DoS (100KB)
            if len(raw) > 100_000:
                await websocket.send_json({
                    "id": None, "type": "response", "channel": None,
                    "action": None, "payload": None,
                    "error": "message too large (max 100KB)",
                })
                continue
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
                except (WebSocketDisconnect, RuntimeError, OSError):
                    raise WebSocketDisconnect(code=1006)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as exc:
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
        await asyncio.wait_for(websocket.send_json({
            "type": "event",
            "channel": "chat",
            "event": "agent_message",
            "payload": agent_msg,
        }), timeout=5.0)
        await asyncio.wait_for(websocket.send_json({
            "type": "event",
            "channel": "chat",
            "event": "agent_complete",
            "payload": {"task_type": result.get("task_type")},
        }), timeout=5.0)


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
    except (OSError, asyncio.TimeoutError, KeyError, WebSocketDisconnect) as exc:
        logger.debug("domino_steps push error: %s", exc)


# ── Background push loops ───────────────────────────────────────────────────

async def _cluster_push_loop(websocket: WebSocket) -> None:
    """Push cluster status every 5 seconds."""
    await push_cluster_events(websocket)


async def _trading_push_loop(websocket: WebSocket) -> None:
    """Push trading updates every 30 seconds."""
    async def send_func(msg: dict):
        await websocket.send_json(msg)
    await push_trading_events(send_func)


async def _orchestrator_push_loop(websocket: WebSocket) -> None:
    """Push orchestrator_v2 alerts + health every 10 seconds."""
    from python_ws.helpers import push_loop as _push

    async def build_orch_payload() -> dict:
        try:
            from src.orchestrator_v2 import orchestrator_v2
            alerts = orchestrator_v2.get_alerts()
            health = orchestrator_v2.health_check()
            return {"health_score": health, "alerts": alerts, "alert_count": len(alerts)}
        except Exception as exc:
            return {"health_score": -1, "alerts": [], "error": str(exc)}

    await _push(
        websocket.send_json, build_orch_payload,
        channel="cluster", event="orchestrator_update",
        interval=10.0, backoff=3.0,
    )


# ── Global Push-to-Talk (CTRL key) ────────────────────────────────────────────

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


async def _broadcast_event(channel: str, event: str, payload: dict[str, Any]) -> None:
    """Broadcast an event to all connected WebSocket clients with timeout."""
    msg = {"type": "event", "channel": channel, "event": event, "payload": payload}
    dead: list[WebSocket] = []
    for client in list(_connected_clients):
        try:
            await asyncio.wait_for(client.send_json(msg), timeout=2.0)
        except (ConnectionError, OSError, asyncio.TimeoutError, RuntimeError, WebSocketDisconnect):
            dead.append(client)
    for d in dead:
        _connected_clients.discard(d)


async def _broadcast_ptt(event_name: str) -> None:
    """Broadcast PTT event to all connected WebSocket clients."""
    await _broadcast_event("voice", event_name, {"key": "ctrl_right", "source": "global_hook"})


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
    await _broadcast_event("voice", "wake_detected", {"word": "jarvis", "source": "openwakeword"})


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
    # Phase 4: initialize orchestrator_v2 + initial health check
    await _startup_orchestrator()
    # Phase 4: start autonomous loop
    try:
        from src.autonomous_loop import autonomous_loop
        await autonomous_loop.start()
        logger.info("Autonomous loop started")
    except Exception as exc:
        logger.warning("Autonomous loop startup failed (non-fatal): %s", exc)


async def _startup_orchestrator():
    """Phase 4 startup: initialize orchestrator_v2, run initial health check."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        health = orchestrator_v2.health_check()
        logger.info("Orchestrator v2 initialized — health: %d/100", health)
        alerts = orchestrator_v2.get_alerts()
        if alerts:
            logger.warning("Startup alerts: %d active", len(alerts))
            for a in alerts[:3]:
                logger.warning("  Alert: %s", a.get("message", a))
    except Exception as exc:
        logger.warning("Orchestrator v2 startup failed (non-fatal): %s", exc)

    # Record initial node probes into orchestrator
    try:
        import httpx
        probes = [
            ("M1", "http://127.0.0.1:1234/api/v1/models"),
            ("OL1", "http://127.0.0.1:11434/api/tags"),
        ]
        async with httpx.AsyncClient(timeout=3) as client:
            for node, url in probes:
                try:
                    import time as _t
                    t0 = _t.perf_counter()
                    r = await client.get(url)
                    lat = (_t.perf_counter() - t0) * 1000
                    ok = r.status_code == 200
                    orchestrator_v2.record_call(node, latency_ms=lat, success=ok)
                    logger.info("Startup probe %s: %s (%.0fms)", node, "OK" if ok else "FAIL", lat)
                except Exception:
                    orchestrator_v2.record_call(node, latency_ms=0, success=False)
                    logger.info("Startup probe %s: OFFLINE", node)
    except Exception:
        pass


@app.on_event("shutdown")
async def _graceful_shutdown():
    """Phase 4 production hardening: graceful shutdown."""
    logger.info("JARVIS WS shutting down — flushing metrics...")

    # Close all WebSocket connections gracefully
    for client in list(_connected_clients):
        try:
            await asyncio.wait_for(client.close(1001, "Server shutting down"), timeout=2.0)
        except Exception:
            pass
    _connected_clients.clear()

    # Stop wake word detector
    global _wake_detector
    if _wake_detector:
        try:
            _wake_detector.stop()
        except Exception:
            pass
        _wake_detector = None

    # Stop autonomous loop
    try:
        from src.autonomous_loop import autonomous_loop
        autonomous_loop.stop()
    except Exception:
        pass

    logger.info("JARVIS WS shutdown complete")


# ── Printer Manager — Phase 27 ──────────────────────────────────────────────

@app.get("/api/printers/list")
async def api_printers_list():
    from src.printer_manager import printer_manager
    return printer_manager.list_printers()


@app.get("/api/printers/events")
async def api_printers_events():
    from src.printer_manager import printer_manager
    return printer_manager.get_events()


@app.get("/api/printers/stats")
async def api_printers_stats():
    from src.printer_manager import printer_manager
    return printer_manager.get_stats()


# ── Firewall Controller — Phase 27 ──────────────────────────────────────────

@app.get("/api/firewall/rules")
async def api_firewall_rules(direction: str = ""):
    from src.firewall_controller import firewall_controller
    rules = firewall_controller.list_rules(direction=direction)
    return rules[:100]


@app.get("/api/firewall/events")
async def api_firewall_events():
    from src.firewall_controller import firewall_controller
    return firewall_controller.get_events()


@app.get("/api/firewall/stats")
async def api_firewall_stats():
    from src.firewall_controller import firewall_controller
    return firewall_controller.get_stats()


# ── Scheduler Manager — Phase 27 ────────────────────────────────────────────

@app.get("/api/scheduler/list")
async def api_scheduler_list(folder: str = "\\"):
    from src.scheduler_manager import scheduler_manager
    return scheduler_manager.list_tasks(folder=folder)


@app.get("/api/scheduler/events")
async def api_scheduler_events():
    from src.scheduler_manager import scheduler_manager
    return scheduler_manager.get_events()


@app.get("/api/scheduler/stats")
async def api_scheduler_stats():
    from src.scheduler_manager import scheduler_manager
    return scheduler_manager.get_stats()


# ── Bluetooth Manager — Phase 28 ────────────────────────────────────────────

@app.get("/api/bluetooth/list")
async def api_bluetooth_list():
    from src.bluetooth_manager import bluetooth_manager
    return bluetooth_manager.list_devices()


@app.get("/api/bluetooth/events")
async def api_bluetooth_events():
    from src.bluetooth_manager import bluetooth_manager
    return bluetooth_manager.get_events()


@app.get("/api/bluetooth/stats")
async def api_bluetooth_stats():
    from src.bluetooth_manager import bluetooth_manager
    return bluetooth_manager.get_stats()


# ── Event Log Reader — Phase 28 ─────────────────────────────────────────────

@app.get("/api/eventlog/read")
async def api_eventlog_read(log_name: str = "System", max_events: int = 50, level: str = ""):
    from src.eventlog_reader import eventlog_reader
    return eventlog_reader.read_log(log_name=log_name, max_events=max_events, level=level)


@app.get("/api/eventlog/events")
async def api_eventlog_events():
    from src.eventlog_reader import eventlog_reader
    return eventlog_reader.get_events()


@app.get("/api/eventlog/stats")
async def api_eventlog_stats():
    from src.eventlog_reader import eventlog_reader
    return eventlog_reader.get_stats()


# ── Font Manager — Phase 28 ─────────────────────────────────────────────────

@app.get("/api/fonts/list")
async def api_fonts_list():
    from src.font_manager import font_manager
    return font_manager.list_fonts()


@app.get("/api/fonts/events")
async def api_fonts_events():
    from src.font_manager import font_manager
    return font_manager.get_events()


@app.get("/api/fonts/stats")
async def api_fonts_stats():
    from src.font_manager import font_manager
    return font_manager.get_stats()


# ── Network Monitor — Phase 29 ──────────────────────────────────────────────

@app.get("/api/network/adapters")
async def api_network_adapters():
    from src.network_monitor import network_monitor
    return network_monitor.list_adapters()


@app.get("/api/network/events")
async def api_network_events():
    from src.network_monitor import network_monitor
    return network_monitor.get_events()


@app.get("/api/network/stats")
async def api_network_stats():
    from src.network_monitor import network_monitor
    return network_monitor.get_stats()


# ── Hosts Manager — Phase 29 ────────────────────────────────────────────────

@app.get("/api/hosts/list")
async def api_hosts_list():
    from src.hosts_manager import hosts_manager
    return hosts_manager.read_entries()


@app.get("/api/hosts/events")
async def api_hosts_events():
    from src.hosts_manager import hosts_manager
    return hosts_manager.get_events()


@app.get("/api/hosts/stats")
async def api_hosts_stats():
    from src.hosts_manager import hosts_manager
    return hosts_manager.get_stats()


# ── Theme Controller — Phase 29 ─────────────────────────────────────────────

@app.get("/api/theme/get")
async def api_theme_get():
    from src.theme_controller import theme_controller
    return theme_controller.get_theme()


@app.get("/api/theme/events")
async def api_theme_events():
    from src.theme_controller import theme_controller
    return theme_controller.get_events()


@app.get("/api/theme/stats")
async def api_theme_stats():
    from src.theme_controller import theme_controller
    return theme_controller.get_stats()


# ── Certificate Manager — Phase 30 ──────────────────────────────────────────

@app.get("/api/certs/list")
async def api_certs_list(store: str = "Cert:\\LocalMachine\\My"):
    from src.certificate_manager import certificate_manager
    return certificate_manager.list_certs(store=store)


@app.get("/api/certs/events")
async def api_certs_events():
    from src.certificate_manager import certificate_manager
    return certificate_manager.get_events()


@app.get("/api/certs/stats")
async def api_certs_stats():
    from src.certificate_manager import certificate_manager
    return certificate_manager.get_stats()


# ── Virtual Desktop — Phase 30 ──────────────────────────────────────────────

@app.get("/api/vdesktops/list")
async def api_vdesktops_list():
    from src.virtual_desktop import virtual_desktop
    return virtual_desktop.list_desktops()


@app.get("/api/vdesktops/events")
async def api_vdesktops_events():
    from src.virtual_desktop import virtual_desktop
    return virtual_desktop.get_events()


@app.get("/api/vdesktops/stats")
async def api_vdesktops_stats():
    from src.virtual_desktop import virtual_desktop
    return virtual_desktop.get_stats()


# ── Notification Manager — Phase 30 ─────────────────────────────────────────

@app.get("/api/notifications/history")
async def api_notifications_history():
    from src.notification_manager import notification_manager
    return notification_manager.get_history()


@app.get("/api/notifications/events")
async def api_notifications_events():
    from src.notification_manager import notification_manager
    return notification_manager.get_events()


@app.get("/api/notifications/stats")
async def api_notifications_stats():
    from src.notification_manager import notification_manager
    return notification_manager.get_stats()


# ── System Restore — Phase 31 ───────────────────────────────────────────────

@app.get("/api/restore/list")
async def api_restore_list():
    from src.sysrestore_manager import sysrestore_manager
    return sysrestore_manager.list_points()


@app.get("/api/restore/events")
async def api_restore_events():
    from src.sysrestore_manager import sysrestore_manager
    return sysrestore_manager.get_events()


@app.get("/api/restore/stats")
async def api_restore_stats():
    from src.sysrestore_manager import sysrestore_manager
    return sysrestore_manager.get_stats()


# ── Performance Counter — Phase 31 ──────────────────────────────────────────

@app.get("/api/perfcounter/counters")
async def api_perfcounter_counters():
    from src.perfcounter import perfcounter
    return perfcounter.list_counters()


@app.get("/api/perfcounter/events")
async def api_perfcounter_events():
    from src.perfcounter import perfcounter
    return perfcounter.get_events()


@app.get("/api/perfcounter/stats")
async def api_perfcounter_stats():
    from src.perfcounter import perfcounter
    return perfcounter.get_stats()


# ── Credential Vault — Phase 31 ─────────────────────────────────────────────

@app.get("/api/credentials/list")
async def api_credentials_list():
    from src.credential_vault import credential_vault
    return credential_vault.list_credentials()


@app.get("/api/credentials/events")
async def api_credentials_events():
    from src.credential_vault import credential_vault
    return credential_vault.get_events()


@app.get("/api/credentials/stats")
async def api_credentials_stats():
    from src.credential_vault import credential_vault
    return credential_vault.get_stats()


# ── Locale Manager — Phase 32 ────────────────────────────────────────────────

@app.get("/api/locale/info")
async def api_locale_info():
    from src.locale_manager import locale_manager
    return {
        "system_locale": locale_manager.get_system_locale(),
        "languages": locale_manager.get_user_language(),
        "timezone": locale_manager.get_timezone(),
        "keyboards": locale_manager.get_keyboard_layouts(),
        "date_format": locale_manager.get_date_format(),
    }


@app.get("/api/locale/events")
async def api_locale_events():
    from src.locale_manager import locale_manager
    return locale_manager.get_events()


@app.get("/api/locale/stats")
async def api_locale_stats():
    from src.locale_manager import locale_manager
    return locale_manager.get_stats()


# ── GPU Monitor — Phase 32 ───────────────────────────────────────────────────

@app.get("/api/gpu/snapshot")
async def api_gpu_snapshot():
    from src.gpu_monitor import gpu_monitor
    return gpu_monitor.snapshot()


@app.get("/api/gpu/events")
async def api_gpu_events():
    from src.gpu_monitor import gpu_monitor
    return gpu_monitor.get_events()


@app.get("/api/gpu/stats")
async def api_gpu_stats():
    from src.gpu_monitor import gpu_monitor
    return gpu_monitor.get_stats()


# ── Share Manager — Phase 32 ─────────────────────────────────────────────────

@app.get("/api/shares/list")
async def api_shares_list():
    from src.share_manager import share_manager
    return share_manager.list_shares()


@app.get("/api/shares/events")
async def api_shares_events():
    from src.share_manager import share_manager
    return share_manager.get_events()


@app.get("/api/shares/stats")
async def api_shares_stats():
    from src.share_manager import share_manager
    return share_manager.get_stats()


# ── Driver Manager — Phase 33 ────────────────────────────────────────────────

@app.get("/api/drivers/list")
async def api_drivers_list():
    from src.driver_manager import driver_manager
    return driver_manager.list_drivers()


@app.get("/api/drivers/events")
async def api_drivers_events():
    from src.driver_manager import driver_manager
    return driver_manager.get_events()


@app.get("/api/drivers/stats")
async def api_drivers_stats():
    from src.driver_manager import driver_manager
    return driver_manager.get_stats()


# ── WMI Explorer — Phase 33 ──────────────────────────────────────────────────

@app.get("/api/wmi/classes")
async def api_wmi_classes():
    from src.wmi_explorer import wmi_explorer
    return wmi_explorer.list_common_classes()


@app.get("/api/wmi/events")
async def api_wmi_events():
    from src.wmi_explorer import wmi_explorer
    return wmi_explorer.get_events()


@app.get("/api/wmi/stats")
async def api_wmi_stats():
    from src.wmi_explorer import wmi_explorer
    return wmi_explorer.get_stats()


# ── Env Variable Manager — Phase 33 ──────────────────────────────────────────

@app.get("/api/envvars/list")
async def api_envvars_list():
    from src.env_variable_manager import env_variable_manager
    return env_variable_manager.list_all()


@app.get("/api/envvars/events")
async def api_envvars_events():
    from src.env_variable_manager import env_variable_manager
    return env_variable_manager.get_events()


@app.get("/api/envvars/stats")
async def api_envvars_stats():
    from src.env_variable_manager import env_variable_manager
    return env_variable_manager.get_stats()


# ── Pagefile Manager — Phase 34 ──────────────────────────────────────────────

@app.get("/api/pagefile/usage")
async def api_pagefile_usage():
    from src.pagefile_manager import pagefile_manager
    return pagefile_manager.get_usage()


@app.get("/api/pagefile/events")
async def api_pagefile_events():
    from src.pagefile_manager import pagefile_manager
    return pagefile_manager.get_events()


@app.get("/api/pagefile/stats")
async def api_pagefile_stats():
    from src.pagefile_manager import pagefile_manager
    return pagefile_manager.get_stats()


# ── Time Sync Manager — Phase 34 ─────────────────────────────────────────────

@app.get("/api/timesync/status")
async def api_timesync_status():
    from src.time_sync_manager import time_sync_manager
    return time_sync_manager.get_status()


@app.get("/api/timesync/events")
async def api_timesync_events():
    from src.time_sync_manager import time_sync_manager
    return time_sync_manager.get_events()


@app.get("/api/timesync/stats")
async def api_timesync_stats():
    from src.time_sync_manager import time_sync_manager
    return time_sync_manager.get_stats()


# ── Disk Health — Phase 34 ───────────────────────────────────────────────────

@app.get("/api/diskhealth/list")
async def api_diskhealth_list():
    from src.disk_health import disk_health
    return disk_health.list_disks()


@app.get("/api/diskhealth/events")
async def api_diskhealth_events():
    from src.disk_health import disk_health
    return disk_health.get_events()


@app.get("/api/diskhealth/stats")
async def api_diskhealth_stats():
    from src.disk_health import disk_health
    return disk_health.get_stats()


# ── User Account Manager — Phase 35 ──────────────────────────────────────────

@app.get("/api/users/list")
async def api_users_list():
    from src.user_account_manager import user_account_manager
    return user_account_manager.list_users()


@app.get("/api/users/events")
async def api_users_events():
    from src.user_account_manager import user_account_manager
    return user_account_manager.get_events()


@app.get("/api/users/stats")
async def api_users_stats():
    from src.user_account_manager import user_account_manager
    return user_account_manager.get_stats()


# ── Group Policy Reader — Phase 35 ───────────────────────────────────────────

@app.get("/api/gpo/rsop")
async def api_gpo_rsop():
    from src.group_policy_reader import group_policy_reader
    return group_policy_reader.get_rsop()


@app.get("/api/gpo/events")
async def api_gpo_events():
    from src.group_policy_reader import group_policy_reader
    return group_policy_reader.get_events()


@app.get("/api/gpo/stats")
async def api_gpo_stats():
    from src.group_policy_reader import group_policy_reader
    return group_policy_reader.get_stats()


# ── Windows Feature Manager — Phase 35 ───────────────────────────────────────

@app.get("/api/features/list")
async def api_features_list():
    from src.windows_feature_manager import windows_feature_manager
    return windows_feature_manager.list_features()


@app.get("/api/features/events")
async def api_features_events():
    from src.windows_feature_manager import windows_feature_manager
    return windows_feature_manager.get_events()


@app.get("/api/features/stats")
async def api_features_stats():
    from src.windows_feature_manager import windows_feature_manager
    return windows_feature_manager.get_stats()


# ── Memory Diagnostics — Phase 36 ────────────────────────────────────────────

@app.get("/api/memory/modules")
async def api_memory_modules():
    from src.memory_diagnostics import memory_diagnostics
    return memory_diagnostics.list_modules()


@app.get("/api/memory/events")
async def api_memory_events():
    from src.memory_diagnostics import memory_diagnostics
    return memory_diagnostics.get_events()


@app.get("/api/memory/stats")
async def api_memory_stats():
    from src.memory_diagnostics import memory_diagnostics
    return memory_diagnostics.get_stats()


# ── System Info Collector — Phase 36 ─────────────────────────────────────────

@app.get("/api/sysinfo/profile")
async def api_sysinfo_profile():
    from src.system_info_collector import system_info_collector
    return system_info_collector.get_full_profile()


@app.get("/api/sysinfo/events")
async def api_sysinfo_events():
    from src.system_info_collector import system_info_collector
    return system_info_collector.get_events()


@app.get("/api/sysinfo/stats")
async def api_sysinfo_stats():
    from src.system_info_collector import system_info_collector
    return system_info_collector.get_stats()


# ── Crash Dump Reader — Phase 36 ─────────────────────────────────────────────

@app.get("/api/crashdumps/summary")
async def api_crashdumps_summary():
    from src.crash_dump_reader import crash_dump_reader
    return crash_dump_reader.get_crash_summary()


@app.get("/api/crashdumps/events")
async def api_crashdumps_events():
    from src.crash_dump_reader import crash_dump_reader
    return crash_dump_reader.get_events()


@app.get("/api/crashdumps/stats")
async def api_crashdumps_stats():
    from src.crash_dump_reader import crash_dump_reader
    return crash_dump_reader.get_stats()


# ── Hotfix Manager — Phase 37 ────────────────────────────────────────────────

@app.get("/api/hotfixes/list")
async def api_hotfixes_list():
    from src.hotfix_manager import hotfix_manager
    return hotfix_manager.list_hotfixes()

@app.get("/api/hotfixes/events")
async def api_hotfixes_events():
    from src.hotfix_manager import hotfix_manager
    return hotfix_manager.get_events()

@app.get("/api/hotfixes/stats")
async def api_hotfixes_stats():
    from src.hotfix_manager import hotfix_manager
    return hotfix_manager.get_stats()


# ── Volume Manager — Phase 37 ────────────────────────────────────────────────

@app.get("/api/volumes/list")
async def api_volumes_list():
    from src.volume_manager import volume_manager
    return volume_manager.list_volumes()

@app.get("/api/volumes/events")
async def api_volumes_events():
    from src.volume_manager import volume_manager
    return volume_manager.get_events()

@app.get("/api/volumes/stats")
async def api_volumes_stats():
    from src.volume_manager import volume_manager
    return volume_manager.get_stats()


# ── Defender Status — Phase 37 ───────────────────────────────────────────────

@app.get("/api/defender/status")
async def api_defender_status():
    from src.defender_status import defender_status
    return defender_status.get_status()

@app.get("/api/defender/events")
async def api_defender_events():
    from src.defender_status import defender_status
    return defender_status.get_events()

@app.get("/api/defender/stats")
async def api_defender_stats():
    from src.defender_status import defender_status
    return defender_status.get_stats()


# ── IP Config — Phase 38 ─────────────────────────────────────────────────────

@app.get("/api/ipconfig/all")
async def api_ipconfig_all():
    from src.ip_config_manager import ip_config_manager
    return ip_config_manager.get_all()

@app.get("/api/ipconfig/events")
async def api_ipconfig_events():
    from src.ip_config_manager import ip_config_manager
    return ip_config_manager.get_events()

@app.get("/api/ipconfig/stats")
async def api_ipconfig_stats():
    from src.ip_config_manager import ip_config_manager
    return ip_config_manager.get_stats()


# ── Recycle Bin — Phase 38 ───────────────────────────────────────────────────

@app.get("/api/recyclebin/info")
async def api_recyclebin_info():
    from src.recycle_bin_manager import recycle_bin_manager
    return recycle_bin_manager.get_info()

@app.get("/api/recyclebin/events")
async def api_recyclebin_events():
    from src.recycle_bin_manager import recycle_bin_manager
    return recycle_bin_manager.get_events()

@app.get("/api/recyclebin/stats")
async def api_recyclebin_stats():
    from src.recycle_bin_manager import recycle_bin_manager
    return recycle_bin_manager.get_stats()


# ── Installed Apps — Phase 38 ────────────────────────────────────────────────

@app.get("/api/apps/list")
async def api_apps_list():
    from src.installed_apps_manager import installed_apps_manager
    return installed_apps_manager.list_win32_apps()

@app.get("/api/apps/events")
async def api_apps_events():
    from src.installed_apps_manager import installed_apps_manager
    return installed_apps_manager.get_events()

@app.get("/api/apps/stats")
async def api_apps_stats():
    from src.installed_apps_manager import installed_apps_manager
    return installed_apps_manager.get_stats()


# ── Phase 39 — Scheduled Tasks, Audio Devices, USB Devices ──────────────────

@app.get("/api/schtasks/list")
async def api_schtasks_list():
    from src.scheduled_task_manager import scheduled_task_manager
    return scheduled_task_manager.list_tasks()

@app.get("/api/schtasks/events")
async def api_schtasks_events():
    from src.scheduled_task_manager import scheduled_task_manager
    return scheduled_task_manager.get_events()

@app.get("/api/schtasks/stats")
async def api_schtasks_stats():
    from src.scheduled_task_manager import scheduled_task_manager
    return scheduled_task_manager.get_stats()


@app.get("/api/audio/list")
async def api_audio_list():
    from src.audio_device_manager import audio_device_manager
    return audio_device_manager.list_devices()

@app.get("/api/audio/events")
async def api_audio_events():
    from src.audio_device_manager import audio_device_manager
    return audio_device_manager.get_events()

@app.get("/api/audio/stats")
async def api_audio_stats():
    from src.audio_device_manager import audio_device_manager
    return audio_device_manager.get_stats()


@app.get("/api/usb/list")
async def api_usb_list():
    from src.usb_device_manager import usb_device_manager
    return usb_device_manager.list_devices()

@app.get("/api/usb/events")
async def api_usb_events():
    from src.usb_device_manager import usb_device_manager
    return usb_device_manager.get_events()

@app.get("/api/usb/stats")
async def api_usb_stats():
    from src.usb_device_manager import usb_device_manager
    return usb_device_manager.get_stats()


# ── Phase 43 — Network Adapter, Windows Update, Local Security Policy ───────

@app.get("/api/netadapter/list")
async def api_netadapter_list():
    from src.network_adapter_manager import network_adapter_manager
    return network_adapter_manager.list_adapters()

@app.get("/api/netadapter/events")
async def api_netadapter_events():
    from src.network_adapter_manager import network_adapter_manager
    return network_adapter_manager.get_events()

@app.get("/api/netadapter/stats")
async def api_netadapter_stats():
    from src.network_adapter_manager import network_adapter_manager
    return network_adapter_manager.get_stats()


@app.get("/api/winupdate/history")
async def api_winupdate_history(limit: int = 30):
    from src.windows_update_manager import windows_update_manager
    return windows_update_manager.get_update_history(limit)

@app.get("/api/winupdate/events")
async def api_winupdate_events():
    from src.windows_update_manager import windows_update_manager
    return windows_update_manager.get_events()

@app.get("/api/winupdate/stats")
async def api_winupdate_stats():
    from src.windows_update_manager import windows_update_manager
    return windows_update_manager.get_stats()


@app.get("/api/secpol/export")
async def api_secpol_export():
    from src.local_security_policy import local_security_policy
    return local_security_policy.export_policy()

@app.get("/api/secpol/events")
async def api_secpol_events():
    from src.local_security_policy import local_security_policy
    return local_security_policy.get_events()

@app.get("/api/secpol/stats")
async def api_secpol_stats():
    from src.local_security_policy import local_security_policy
    return local_security_policy.get_stats()


# ── Phase 42 — DNS Client, Storage Pool, Power Plan ─────────────────────────

@app.get("/api/dns/servers")
async def api_dns_servers():
    from src.dns_client_manager import dns_client_manager
    return dns_client_manager.get_server_addresses()

@app.get("/api/dns/events")
async def api_dns_events():
    from src.dns_client_manager import dns_client_manager
    return dns_client_manager.get_events()

@app.get("/api/dns/stats")
async def api_dns_stats():
    from src.dns_client_manager import dns_client_manager
    return dns_client_manager.get_stats()


@app.get("/api/storagepool/list")
async def api_storagepool_list():
    from src.storage_pool_manager import storage_pool_manager
    return storage_pool_manager.list_pools()

@app.get("/api/storagepool/events")
async def api_storagepool_events():
    from src.storage_pool_manager import storage_pool_manager
    return storage_pool_manager.get_events()

@app.get("/api/storagepool/stats")
async def api_storagepool_stats():
    from src.storage_pool_manager import storage_pool_manager
    return storage_pool_manager.get_stats()


@app.get("/api/powerplan/list")
async def api_powerplan_list():
    from src.power_plan_manager import power_plan_manager
    return power_plan_manager.list_plans()

@app.get("/api/powerplan/events")
async def api_powerplan_events():
    from src.power_plan_manager import power_plan_manager
    return power_plan_manager.get_events()

@app.get("/api/powerplan/stats")
async def api_powerplan_stats():
    from src.power_plan_manager import power_plan_manager
    return power_plan_manager.get_stats()


# ── Phase 41 — Virtual Memory, Event Log Reader, Shadow Copy ────────────────

@app.get("/api/virtmem/status")
async def api_virtmem_status():
    from src.virtual_memory_manager import virtual_memory_manager
    return virtual_memory_manager.get_status()

@app.get("/api/virtmem/events")
async def api_virtmem_events():
    from src.virtual_memory_manager import virtual_memory_manager
    return virtual_memory_manager.get_events()

@app.get("/api/virtmem/stats")
async def api_virtmem_stats():
    from src.virtual_memory_manager import virtual_memory_manager
    return virtual_memory_manager.get_stats()


@app.get("/api/winevt/recent")
async def api_winevt_recent(log_name: str = "System", max_events: int = 20):
    from src.windows_event_log_reader import windows_event_log_reader
    return windows_event_log_reader.get_recent(log_name, max_events)

@app.get("/api/winevt/events")
async def api_winevt_events():
    from src.windows_event_log_reader import windows_event_log_reader
    return windows_event_log_reader.get_events()

@app.get("/api/winevt/stats")
async def api_winevt_stats():
    from src.windows_event_log_reader import windows_event_log_reader
    return windows_event_log_reader.get_stats()


@app.get("/api/shadowcopy/list")
async def api_shadowcopy_list():
    from src.shadow_copy_manager import shadow_copy_manager
    return shadow_copy_manager.list_copies()

@app.get("/api/shadowcopy/events")
async def api_shadowcopy_events():
    from src.shadow_copy_manager import shadow_copy_manager
    return shadow_copy_manager.get_events()

@app.get("/api/shadowcopy/stats")
async def api_shadowcopy_stats():
    from src.shadow_copy_manager import shadow_copy_manager
    return shadow_copy_manager.get_stats()


# ── Phase 40 — Screen Resolution, BIOS Settings, Performance Counters ───────

@app.get("/api/screen/list")
async def api_screen_list():
    from src.screen_resolution_manager import screen_resolution_manager
    return screen_resolution_manager.list_displays()

@app.get("/api/screen/events")
async def api_screen_events():
    from src.screen_resolution_manager import screen_resolution_manager
    return screen_resolution_manager.get_events()

@app.get("/api/screen/stats")
async def api_screen_stats():
    from src.screen_resolution_manager import screen_resolution_manager
    return screen_resolution_manager.get_stats()


@app.get("/api/bios/info")
async def api_bios_info():
    from src.bios_settings import bios_settings
    return bios_settings.get_info()

@app.get("/api/bios/events")
async def api_bios_events():
    from src.bios_settings import bios_settings
    return bios_settings.get_events()

@app.get("/api/bios/stats")
async def api_bios_stats():
    from src.bios_settings import bios_settings
    return bios_settings.get_stats()


@app.get("/api/perfcounters/snapshot")
async def api_perfcounters_snapshot():
    from src.performance_counter import performance_counter
    return performance_counter.snapshot()

@app.get("/api/perfcounters/events")
async def api_perfcounters_events():
    from src.performance_counter import performance_counter
    return performance_counter.get_events()

@app.get("/api/perfcounters/stats")
async def api_perfcounters_stats():
    from src.performance_counter import performance_counter
    return performance_counter.get_stats()


# ── Prediction Engine (v2.0) ─────────────────────────────────────────────────

@app.post("/api/record_action")
async def api_record_action(request: Request):
    """Record a user action for the prediction engine."""
    body = await request.json()
    action = body.get("action", "")
    context = body.get("context", {})
    if not action:
        return {"error": "action required"}
    try:
        from src.prediction_engine import prediction_engine
        prediction_engine.record_action(action, context)
        return {"recorded": True, "action": action}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/predictions")
async def api_predictions(n: int = 5):
    """Get predicted next user actions."""
    from src.prediction_engine import prediction_engine
    return prediction_engine.predict_next(n=n)


@app.get("/api/predictions/profile")
async def api_predictions_profile():
    """Get user activity profile."""
    from src.prediction_engine import prediction_engine
    return prediction_engine.get_user_profile()


@app.get("/api/predictions/stats")
async def api_predictions_stats():
    """Prediction engine stats."""
    from src.prediction_engine import prediction_engine
    return prediction_engine.get_stats()


@app.get("/api/autodev/stats")
async def api_autodev_stats():
    """Auto-developer stats."""
    from src.auto_developer import auto_developer
    return auto_developer.get_stats()


@app.get("/api/browser/status")
async def api_browser_status():
    """Browser navigator status."""
    from src.browser_navigator import browser_nav
    return browser_nav.get_status()


# ── Pattern Agents API ──────────────────────────────────────────────────────

@app.get("/api/agents/list")
async def api_agents_list():
    """List all 14 pattern agents."""
    from src.pattern_agents import PatternAgentRegistry
    reg = PatternAgentRegistry()
    return {"agents": reg.list_agents()}


@app.post("/api/agents/dispatch")
async def api_agents_dispatch(request: Request):
    """Dispatch a prompt to the right agent. Body: {prompt, pattern?}"""
    from src.smart_dispatcher import SmartDispatcher
    body = await request.json()
    prompt = body.get("prompt", "")
    pattern = body.get("pattern")
    if not prompt:
        raise HTTPException(400, "prompt required")
    d = SmartDispatcher()
    if pattern:
        r = await d.dispatch_typed(pattern, prompt)
    else:
        r = await d.dispatch(prompt)
    await d.close()
    return {
        "ok": r.ok, "content": r.content, "pattern": r.pattern,
        "node": r.node, "model": r.model, "latency_ms": round(r.latency_ms),
        "tokens": r.tokens, "quality": r.quality_score, "strategy": r.strategy,
    }


@app.post("/api/agents/classify")
async def api_agents_classify(request: Request):
    """Classify a prompt with confidence scoring. Body: {prompt}"""
    from src.pattern_agents import PatternAgentRegistry
    body = await request.json()
    prompt = body.get("prompt", "")
    if not prompt:
        raise HTTPException(400, "prompt required")
    reg = PatternAgentRegistry()
    classification = reg.classify_with_confidence(prompt)
    pattern = classification["pattern"]
    agent = reg.agents.get(pattern)
    return {
        "pattern": pattern,
        "confidence": classification["confidence"],
        "candidates": classification["candidates"],
        "agent": agent.agent_id if agent else "unknown",
        "node": agent.primary_node if agent else "M1",
        "strategy": agent.strategy if agent else "single",
    }


@app.get("/api/agents/routing")
async def api_agents_routing():
    """Get smart routing report based on dispatch history."""
    from src.smart_dispatcher import SmartDispatcher
    d = SmartDispatcher()
    report = d.get_routing_report()
    await d.close()
    return report


@app.post("/api/agents/evolve")
async def api_agents_evolve():
    """Run agent factory evolution: discover new patterns, tune nodes/strategies."""
    from src.agent_factory import AgentFactory
    f = AgentFactory()
    evolutions = f.analyze_and_evolve()
    return {
        "evolutions": [
            {"pattern": e.pattern_type, "action": e.action,
             "old": e.old_value, "new": e.new_value,
             "reason": e.reason, "confidence": e.confidence}
            for e in evolutions
        ]
    }


@app.get("/api/agents/stats")
async def api_agents_stats():
    """Get agent performance stats from dispatch_log."""
    from src.agent_factory import AgentFactory
    f = AgentFactory()
    report = f.generate_report()
    return report


# ── Pipeline API ────────────────────────────────────────────────────────────

@app.get("/api/pipelines/list-patterns")
async def api_pipelines_list_patterns():
    """List available pre-built pipelines."""
    from src.pipeline_composer import PIPELINES
    return {"pipelines": list(PIPELINES.keys())}


@app.post("/api/pipelines/run-pattern")
async def api_pipelines_run_pattern(request: Request):
    """Run a named pipeline. Body: {pipeline, prompt}"""
    from src.pipeline_composer import run_pipeline
    body = await request.json()
    name = body.get("pipeline", "")
    prompt = body.get("prompt", "")
    if not name or not prompt:
        raise HTTPException(400, "pipeline and prompt required")
    result = await run_pipeline(name, prompt)
    return {
        "ok": result.ok, "pipeline": result.pipeline_name,
        "total_ms": round(result.total_ms),
        "steps": result.steps, "output": result.final_output[:3000],
    }


# ── Agent Monitor API ──────────────────────────────────────────────────────

@app.get("/api/agents/dashboard")
async def api_agents_dashboard():
    """Real-time agent monitoring dashboard."""
    from src.agent_monitor import get_monitor
    return get_monitor().get_dashboard()


@app.get("/api/agents/monitor/{pattern}")
async def api_agents_monitor_detail(pattern: str):
    """Detailed metrics for one pattern agent."""
    from src.agent_monitor import get_monitor
    return get_monitor().get_agent_detail(pattern)


@app.get("/api/agents/routing-optimizer")
async def api_agents_routing_optimizer():
    """Routing optimization report with recommendations."""
    from src.routing_optimizer import RoutingOptimizer
    opt = RoutingOptimizer()
    return opt.report()


# ── Adaptive Router API ────────────────────────────────────────────────────

@app.get("/api/router/status")
async def api_router_status():
    """Adaptive router status: circuits, health, affinities."""
    from src.adaptive_router import get_router
    return get_router().get_status()


@app.get("/api/router/recommendations")
async def api_router_recommendations():
    """Auto-generated routing recommendations."""
    from src.adaptive_router import get_router
    return {"recommendations": get_router().get_recommendations()}


@app.post("/api/router/pick")
async def api_router_pick(request: Request):
    """Pick optimal node for a pattern. Body: {pattern, prompt?, count?}"""
    from src.adaptive_router import get_router
    body = await request.json()
    pattern = body.get("pattern", "code")
    prompt = body.get("prompt", "")
    count = body.get("count", 1)
    router = get_router()
    if count > 1:
        return {"nodes": router.pick_nodes(pattern, count=count)}
    return {"node": router.pick_node(pattern, prompt)}


# ── Pattern Discovery API ─────────────────────────────────────────────────

@app.get("/api/discovery/report")
async def api_discovery_report():
    """Full pattern discovery + behavior report."""
    from src.pattern_discovery import PatternDiscovery
    return PatternDiscovery().full_report()


@app.post("/api/discovery/register")
async def api_discovery_register():
    """Discover and register new patterns in the database."""
    from src.pattern_discovery import PatternDiscovery
    d = PatternDiscovery()
    patterns = d.discover()
    count = d.register_patterns(patterns)
    return {"discovered": len(patterns), "registered": count}


# ── Orchestrator v3 API ──────────────────────────────────────────────────

@app.post("/api/orchestrate")
async def api_orchestrate(request: Request):
    """Execute an orchestrated workflow. Body: {prompt, workflow?, budget_s?}"""
    from src.agent_orchestrator_v3 import Orchestrator
    body = await request.json()
    prompt = body.get("prompt", "")
    workflow = body.get("workflow", "auto")
    budget_s = body.get("budget_s", 60)
    if not prompt:
        raise HTTPException(400, "prompt required")
    o = Orchestrator()
    r = await o.execute(prompt, workflow=workflow, budget_s=budget_s)
    await o.close()
    return {
        "ok": r.ok, "workflow": r.strategy_used,
        "content": r.final_content[:3000],
        "total_ms": round(r.total_latency_ms),
        "steps": [{"name": s.step_name, "pattern": s.pattern, "node": s.node,
                    "ok": s.ok, "ms": round(s.latency_ms), "quality": round(s.quality, 3)}
                   for s in r.steps],
        "patterns": r.patterns_used,
        "nodes": r.nodes_used,
        "summary": r.summary,
    }


@app.post("/api/orchestrate/consensus")
async def api_orchestrate_consensus(request: Request):
    """Run consensus across N nodes. Body: {prompt, nodes?, min_agree?}"""
    from src.agent_orchestrator_v3 import Orchestrator
    body = await request.json()
    prompt = body.get("prompt", "")
    nodes = body.get("nodes")
    min_agree = body.get("min_agree", 2)
    if not prompt:
        raise HTTPException(400, "prompt required")
    o = Orchestrator()
    r = await o.execute_consensus(prompt, nodes=nodes, min_agree=min_agree)
    await o.close()
    return {
        "ok": r.ok, "content": r.final_content[:3000],
        "total_ms": round(r.total_latency_ms),
        "nodes": r.nodes_used, "agreed": r.metadata.get("agreed", 0),
    }


@app.post("/api/orchestrate/race")
async def api_orchestrate_race(request: Request):
    """Race N nodes for fastest response. Body: {prompt, pattern?, count?}"""
    from src.agent_orchestrator_v3 import Orchestrator
    body = await request.json()
    prompt = body.get("prompt", "")
    pattern = body.get("pattern", "code")
    count = body.get("count", 3)
    if not prompt:
        raise HTTPException(400, "prompt required")
    o = Orchestrator()
    r = await o.execute_race(prompt, pattern=pattern, count=count)
    await o.close()
    return {
        "ok": r.ok, "content": r.final_content[:3000],
        "total_ms": round(r.total_latency_ms),
        "winner": r.metadata.get("winner"),
        "raced_nodes": r.metadata.get("raced_nodes", []),
    }


@app.get("/api/orchestrate/workflows")
async def api_orchestrate_workflows():
    """List available orchestration workflows."""
    from src.agent_orchestrator_v3 import Orchestrator
    return Orchestrator().list_workflows()


# ── Episodic Memory API ──────────────────────────────────────────────────

@app.get("/api/memory/session")
async def api_memory_session():
    """Current session memory summary."""
    from src.agent_episodic_memory import get_episodic_memory
    return get_episodic_memory().get_session_summary()


@app.post("/api/memory/recall")
async def api_memory_recall(request: Request):
    """Recall relevant episodes. Body: {query, top_k?, pattern?}"""
    from src.agent_episodic_memory import get_episodic_memory
    body = await request.json()
    query = body.get("query", "")
    top_k = body.get("top_k", 5)
    pattern = body.get("pattern")
    if not query:
        raise HTTPException(400, "query required")
    mem = get_episodic_memory()
    episodes = mem.recall(query, top_k=top_k, pattern_filter=pattern)
    return {"episodes": [
        {"pattern": e.pattern, "node": e.node, "preview": e.prompt_preview,
         "success": e.success, "quality": e.quality, "relevance": round(e.relevance, 2)}
        for e in episodes
    ]}


@app.get("/api/memory/node/{node}")
async def api_memory_node(node: str):
    """Memory about a specific node."""
    from src.agent_episodic_memory import get_episodic_memory
    return get_episodic_memory().get_node_memory(node)


@app.get("/api/memory/pattern/{pattern}")
async def api_memory_pattern(pattern: str):
    """Memory about a specific pattern."""
    from src.agent_episodic_memory import get_episodic_memory
    return get_episodic_memory().get_pattern_memory(pattern)


@app.post("/api/memory/learn")
async def api_memory_learn():
    """Analyze history and generate semantic facts."""
    from src.agent_episodic_memory import get_episodic_memory
    mem = get_episodic_memory()
    learned = mem.learn_from_history()
    return {"learned": learned, "total_facts": len(mem._facts)}


# ── Self-Improve API ─────────────────────────────────────────────────────

@app.post("/api/improve/cycle")
async def api_improve_cycle():
    """Run a self-improvement cycle."""
    from src.agent_self_improve import SelfImprover
    imp = SelfImprover()
    report = await imp.run_cycle()
    return {
        "cycle_id": report.cycle_id,
        "duration_ms": round(report.duration_ms),
        "actions": [
            {"type": a.action_type, "target": a.target,
             "description": a.description, "confidence": round(a.confidence, 2)}
            for a in report.actions
        ],
        "recommendations": report.recommendations,
        "success_rate": round(report.metrics_before.get("success_rate", 0) * 100, 1),
        "summary": report.summary,
    }


@app.get("/api/improve/history")
async def api_improve_history():
    """Get self-improvement cycle history."""
    from src.agent_self_improve import SelfImprover
    return {"history": SelfImprover().get_history(limit=20)}


# ── Agent Collaboration API ──────────────────────────────────────────────

@app.post("/api/collab/ask")
async def api_collab_ask(request: Request):
    """Ask a specific agent. Body: {pattern, prompt, context?}"""
    from src.agent_collaboration import get_bus
    body = await request.json()
    pattern = body.get("pattern", "simple")
    prompt = body.get("prompt", "")
    context = body.get("context", {})
    if not prompt:
        raise HTTPException(400, "prompt required")
    bus = get_bus()
    msg = await bus.ask(pattern, prompt, context=context)
    return {"ok": msg.ok, "response": (msg.response or "")[:3000],
            "pattern": msg.to_agent, "latency_ms": round(msg.latency_ms)}


@app.post("/api/collab/chain")
async def api_collab_chain(request: Request):
    """Execute agent chain. Body: {agents: ["code","security"], prompt}"""
    from src.agent_collaboration import get_bus
    body = await request.json()
    agents = body.get("agents", ["simple"])
    prompt = body.get("prompt", "")
    if not prompt:
        raise HTTPException(400, "prompt required")
    bus = get_bus()
    r = await bus.chain(agents, prompt)
    return {"ok": r.ok, "content": r.final_content[:3000],
            "chain": r.chain, "steps_ok": r.steps_ok,
            "total_ms": round(r.total_latency_ms), "summary": r.summary}


@app.post("/api/collab/debate")
async def api_collab_debate(request: Request):
    """Multi-agent debate. Body: {agents, question, rounds?}"""
    from src.agent_collaboration import get_bus
    body = await request.json()
    agents = body.get("agents", ["code", "reasoning"])
    question = body.get("question", "")
    rounds = body.get("rounds", 2)
    if not question:
        raise HTTPException(400, "question required")
    bus = get_bus()
    r = await bus.debate(agents, question, rounds=rounds)
    return {"ok": r.ok, "content": r.final_content[:3000],
            "steps_ok": r.steps_ok, "total_ms": round(r.total_latency_ms)}


@app.get("/api/collab/stats")
async def api_collab_stats():
    """Collaboration statistics."""
    from src.agent_collaboration import get_bus
    return get_bus().get_stats()


# ── Health Guardian API ──────────────────────────────────────────────────

@app.get("/api/health/check")
async def api_health_check():
    """Run full health check on all nodes."""
    from src.agent_health_guardian import HealthGuardian
    g = HealthGuardian()
    report = await g.check_all()
    return {
        "status": report.overall_status,
        "healthy": report.healthy_nodes, "total": report.total_nodes,
        "alerts": [{"severity": a.severity, "target": a.target,
                     "type": a.alert_type, "message": a.message}
                    for a in report.alerts],
        "nodes": [{"node": n.node, "status": n.status, "latency_ms": round(n.latency_ms),
                    "models_loaded": n.models_loaded, "error": n.error}
                   for n in report.node_checks],
        "duration_ms": round(report.duration_ms),
        "summary": report.summary,
    }


@app.post("/api/health/heal")
async def api_health_heal():
    """Run auto-healing."""
    from src.agent_health_guardian import HealthGuardian
    g = HealthGuardian()
    healed = await g.auto_heal()
    return {"actions": healed}


# ── Benchmark API ────────────────────────────────────────────────────────

@app.post("/api/benchmark/quick")
async def api_benchmark_quick():
    """Run quick benchmark (~2min)."""
    from src.pattern_benchmark_runner import BenchmarkRunner
    r = BenchmarkRunner()
    report = await r.run_quick()
    await r.close()
    return {
        "name": report.name, "success_rate": round(report.success_rate * 100, 1),
        "total": report.total_tests, "ok": report.success_count,
        "duration_ms": round(report.duration_ms),
        "per_pattern": report.per_pattern,
        "recommendations": report.recommendations,
        "summary": report.summary,
    }


@app.get("/api/benchmark/history")
async def api_benchmark_history():
    """Benchmark history."""
    from src.pattern_benchmark_runner import BenchmarkRunner
    return {"history": BenchmarkRunner().get_history()}


# ── Task Planner API ────────────────────────────────────────────────────

@app.post("/api/planner/plan")
async def api_planner_plan(request: Request):
    """Plan a complex task. Body: {prompt}"""
    from src.agent_task_planner import TaskPlanner
    body = await request.json()
    prompt = body.get("prompt", "")
    if not prompt:
        raise HTTPException(400, "prompt required")
    p = TaskPlanner()
    plan = p.plan(prompt)
    return p.plan_to_dict(plan)


@app.post("/api/planner/execute")
async def api_planner_execute(request: Request):
    """Plan and execute a complex task. Body: {prompt}"""
    from src.agent_task_planner import TaskPlanner
    body = await request.json()
    prompt = body.get("prompt", "")
    if not prompt:
        raise HTTPException(400, "prompt required")
    p = TaskPlanner()
    plan = p.plan(prompt)
    result = await p.execute_plan(plan)
    await p.close()
    return {
        "ok": result.ok, "complexity": plan.complexity,
        "steps_ok": result.steps_ok, "steps_total": result.steps_total,
        "total_ms": round(result.total_ms),
        "output": result.final_output[:3000],
        "plan": p.plan_to_dict(plan),
        "summary": result.summary,
    }


# ── Feedback Loop API ────────────────────────────────────────────────────

@app.get("/api/feedback/quality")
async def api_feedback_quality():
    """Quality report from feedback loop."""
    from src.agent_feedback_loop import get_feedback
    return get_feedback().get_quality_report()


@app.get("/api/feedback/trends")
async def api_feedback_trends():
    """Pattern quality trends."""
    from src.agent_feedback_loop import get_feedback
    fb = get_feedback()
    return {"trends": [
        {"pattern": t.pattern, "direction": t.direction,
         "recent": t.recent_quality, "older": t.older_quality,
         "change": t.change_pct, "best_node": t.best_node}
        for t in fb.get_trends()
    ]}


@app.get("/api/feedback/adjustments")
async def api_feedback_adjustments():
    """Suggested routing adjustments."""
    from src.agent_feedback_loop import get_feedback
    fb = get_feedback()
    return {"adjustments": [
        {"pattern": a.pattern, "action": a.action,
         "current": a.current, "suggested": a.suggested,
         "reason": a.reason, "confidence": round(a.confidence, 2)}
        for a in fb.suggest_adjustments()
    ]}


@app.get("/api/feedback/ab")
async def api_feedback_ab():
    """A/B test results per pattern."""
    from src.agent_feedback_loop import get_feedback
    return get_feedback().get_ab_results()


@app.post("/api/feedback/rate")
async def api_feedback_rate(request: Request):
    """Submit user rating. Body: {pattern, node, rating (1-5)}"""
    from src.agent_feedback_loop import get_feedback
    body = await request.json()
    fb = get_feedback()
    fb.record_feedback(
        pattern=body.get("pattern", ""),
        node=body.get("node", "M1"),
        user_rating=int(body.get("rating", 0)),
        quality=float(body.get("quality", 0.5)),
        success=True,
    )
    return {"ok": True}


# ── Entry point ──────────────────────────────────────────────────────────────

# ── Phase 13: Dispatch Engine ────────────────────────────────────────────────

@app.get("/api/dispatch_engine/stats")
async def dispatch_engine_stats():
    from src.dispatch_engine import get_engine
    return get_engine().get_stats()

@app.get("/api/dispatch_engine/report")
async def dispatch_engine_report():
    from src.dispatch_engine import get_engine
    return get_engine().get_pipeline_report()

@app.post("/api/dispatch_engine/dispatch")
async def dispatch_engine_dispatch(req: Request):
    body = await req.json()
    from src.dispatch_engine import get_engine
    engine = get_engine()
    result = await engine.dispatch(
        pattern=body.get("pattern", "simple"),
        prompt=body.get("prompt", ""),
        node_override=body.get("node"),
        strategy_override=body.get("strategy"),
    )
    return {"pattern": result.pattern, "node": result.node, "content": result.content,
            "quality": result.quality, "latency_ms": result.latency_ms,
            "success": result.success, "pipeline_ms": result.pipeline_ms,
            "enriched": result.enriched, "fallback_used": result.fallback_used}

@app.post("/api/dispatch_engine/batch")
async def dispatch_engine_batch(req: Request):
    body = await req.json()
    from src.dispatch_engine import get_engine
    engine = get_engine()
    results = await engine.batch_dispatch(
        tasks=body.get("tasks", []),
        concurrency=body.get("concurrency", 3),
    )
    return [{"pattern": r.pattern, "node": r.node, "quality": r.quality,
             "success": r.success, "latency_ms": r.latency_ms} for r in results]

@app.get("/api/dispatch_engine/analytics")
async def dispatch_engine_analytics():
    from src.dispatch_engine import get_engine
    return get_engine().get_full_analytics()

@app.post("/api/dispatch_engine/auto_optimize")
async def dispatch_engine_auto_optimize():
    from src.pattern_agents import PatternAgentRegistry
    reg = PatternAgentRegistry()
    return reg.auto_optimize_strategies()

# ── Phase 13: Prompt Optimizer ───────────────────────────────────────────────

@app.post("/api/prompt_optimizer/optimize")
async def prompt_optimizer_optimize(req: Request):
    body = await req.json()
    from src.agent_prompt_optimizer import get_optimizer
    return get_optimizer().optimize(body.get("pattern", "simple"), body.get("prompt", ""))

@app.get("/api/prompt_optimizer/insights")
async def prompt_optimizer_insights(pattern: str = ""):
    from src.agent_prompt_optimizer import get_optimizer
    return get_optimizer().get_insights(pattern or None)

@app.get("/api/prompt_optimizer/templates")
async def prompt_optimizer_templates():
    from src.agent_prompt_optimizer import get_optimizer
    return get_optimizer().get_templates()

@app.post("/api/prompt_optimizer/analyze")
async def prompt_optimizer_analyze(req: Request):
    body = await req.json()
    from src.agent_prompt_optimizer import get_optimizer
    return get_optimizer().analyze_prompt(body.get("pattern", "simple"), body.get("prompt", ""))

# ── Phase 13: Auto Scaler ───────────────────────────────────────────────────

@app.get("/api/auto_scaler/metrics")
async def auto_scaler_metrics():
    from src.agent_auto_scaler import get_scaler
    metrics = get_scaler().get_load_metrics()
    return {n: {"avg_latency_ms": m.avg_latency_ms, "p95_latency_ms": m.p95_latency_ms,
                "error_rate": m.error_rate, "requests_5min": m.requests_last_5min,
                "requests_1h": m.requests_last_1h} for n, m in metrics.items()}

@app.get("/api/auto_scaler/evaluate")
async def auto_scaler_evaluate():
    from src.agent_auto_scaler import get_scaler
    actions = get_scaler().evaluate()
    return [{"action_type": a.action_type, "target_node": a.target_node,
             "description": a.description, "priority": a.priority} for a in actions]

@app.get("/api/auto_scaler/capacity")
async def auto_scaler_capacity():
    from src.agent_auto_scaler import get_scaler
    return get_scaler().get_capacity_report()

@app.get("/api/auto_scaler/history")
async def auto_scaler_history():
    from src.agent_auto_scaler import get_scaler
    return get_scaler().get_scaling_history()

@app.post("/api/auto_scaler/execute")
async def auto_scaler_execute(req: Request):
    from src.agent_auto_scaler import get_scaler
    scaler = get_scaler()
    actions = scaler.evaluate()
    results = await scaler.execute_actions(actions)
    return results

# ── Phase 13: Event Stream ──────────────────────────────────────────────────

@app.get("/api/event_stream/events")
async def event_stream_events(topic: str = "", since_id: int = 0, limit: int = 100):
    from src.event_stream import get_stream
    return get_stream().get_events(topic or None, since_id, limit)

@app.get("/api/event_stream/latest")
async def event_stream_latest(topic: str = "", n: int = 10):
    from src.event_stream import get_stream
    return get_stream().get_latest(topic or None, n)

@app.get("/api/event_stream/stats")
async def event_stream_stats():
    from src.event_stream import get_stream
    return get_stream().get_stats()

@app.get("/api/event_stream/topics")
async def event_stream_topics():
    from src.event_stream import get_stream
    return get_stream().get_topics()

@app.post("/api/event_stream/emit")
async def event_stream_emit(req: Request):
    body = await req.json()
    from src.event_stream import get_stream
    eid = get_stream().emit(body.get("topic", "system"), body.get("data", {}), body.get("source", "api"))
    return {"event_id": eid}

from fastapi.responses import StreamingResponse

@app.get("/api/event_stream/sse/{topic}")
async def event_stream_sse(topic: str):
    from src.event_stream import get_stream
    return StreamingResponse(get_stream().sse_generator(topic), media_type="text/event-stream")

# ── Phase 13: Agent Ensemble ────────────────────────────────────────────────

@app.post("/api/ensemble/execute")
async def ensemble_execute(req: Request):
    body = await req.json()
    from src.agent_ensemble import get_ensemble
    ens = get_ensemble()
    result = await ens.execute(
        pattern=body.get("pattern", "simple"),
        prompt=body.get("prompt", ""),
        nodes=body.get("nodes"),
        strategy=body.get("strategy", "best_of_n"),
    )
    return {
        "best_node": result.best_output.node,
        "best_content": result.best_output.content,
        "best_score": result.best_output.total_score,
        "agreement": result.agreement_score,
        "ensemble_size": result.ensemble_size,
        "total_latency_ms": result.total_latency_ms,
        "all_scores": [{
            "node": o.node, "score": o.total_score,
            "latency_ms": o.latency_ms, "success": o.success,
        } for o in result.all_outputs],
    }

@app.get("/api/ensemble/stats")
async def ensemble_stats():
    from src.agent_ensemble import get_ensemble
    return get_ensemble().get_ensemble_stats()

@app.get("/api/ensemble/best_config")
async def ensemble_best_config(pattern: str = "code"):
    from src.agent_ensemble import get_ensemble
    return get_ensemble().get_best_ensemble_config(pattern)


# ── Phase 14: Quality Gate ───────────────────────────────────────────────────

@app.post("/api/quality_gate/evaluate")
async def quality_gate_evaluate(req: Request):
    body = await req.json()
    from src.quality_gate import get_gate
    result = get_gate().evaluate(
        body.get("pattern", "simple"), body.get("prompt", ""),
        body.get("content", ""), latency_ms=body.get("latency_ms", 0),
        node=body.get("node", ""),
    )
    return {"passed": result.passed, "overall_score": result.overall_score,
            "gates": result.gates, "failed_gates": result.failed_gates,
            "suggestions": result.suggestions, "retry_recommended": result.retry_recommended}

@app.get("/api/quality_gate/stats")
async def quality_gate_stats():
    from src.quality_gate import get_gate
    return get_gate().get_stats()

@app.get("/api/quality_gate/report")
async def quality_gate_report():
    from src.quality_gate import get_gate
    return get_gate().get_gate_report()

# ── Phase 14: Pattern Lifecycle ──────────────────────────────────────────────

@app.get("/api/lifecycle/patterns")
async def lifecycle_patterns():
    from src.pattern_lifecycle import get_lifecycle
    patterns = get_lifecycle().get_all_patterns()
    return [{"pattern": p.pattern_type, "agent": p.agent_id, "model": p.model_primary,
             "strategy": p.strategy, "status": p.status, "calls": p.total_calls,
             "success_rate": p.success_rate, "quality": p.avg_quality} for p in patterns]

@app.get("/api/lifecycle/health")
async def lifecycle_health():
    from src.pattern_lifecycle import get_lifecycle
    return get_lifecycle().health_report()

@app.get("/api/lifecycle/actions")
async def lifecycle_actions():
    from src.pattern_lifecycle import get_lifecycle
    return get_lifecycle().suggest_actions()

@app.post("/api/lifecycle/create")
async def lifecycle_create(req: Request):
    body = await req.json()
    from src.pattern_lifecycle import get_lifecycle
    ok = get_lifecycle().create_pattern(
        body.get("pattern", ""), body.get("agent_id", ""),
        body.get("model", "qwen3-8b"), body.get("strategy", "single"),
    )
    return {"created": ok}

@app.post("/api/lifecycle/evolve")
async def lifecycle_evolve(req: Request):
    body = await req.json()
    from src.pattern_lifecycle import get_lifecycle
    ok = get_lifecycle().evolve_pattern(
        body.get("pattern", ""), model=body.get("model"),
        strategy=body.get("strategy"),
    )
    return {"evolved": ok}

@app.post("/api/lifecycle/deprecate")
async def lifecycle_deprecate(req: Request):
    body = await req.json()
    from src.pattern_lifecycle import get_lifecycle
    ok = get_lifecycle().deprecate_pattern(body.get("pattern", ""))
    return {"deprecated": ok}

@app.get("/api/lifecycle/history")
async def lifecycle_history(pattern: str = ""):
    from src.pattern_lifecycle import get_lifecycle
    return get_lifecycle().get_lifecycle_history(pattern or None)

# ── Phase 14: Cluster Intelligence ──────────────────────────────────────────

@app.get("/api/intelligence/report")
async def intelligence_report():
    from src.cluster_intelligence import get_intelligence
    return get_intelligence().full_report()

@app.get("/api/intelligence/status")
async def intelligence_status():
    from src.cluster_intelligence import get_intelligence
    return get_intelligence().quick_status()

@app.get("/api/intelligence/actions")
async def intelligence_actions():
    from src.cluster_intelligence import get_intelligence
    actions = get_intelligence().priority_actions()
    return [a.__dict__ for a in actions]


# ── Cowork Bridge ────────────────────────────────────────────────────────────

@app.get("/api/cowork/scripts")
async def cowork_scripts(category: str = ""):
    from src.cowork_bridge import get_bridge
    return get_bridge().list_scripts(category or None)

@app.get("/api/cowork/search")
async def cowork_search(q: str = "", limit: int = 20):
    from src.cowork_bridge import get_bridge
    return get_bridge().search(q, limit)

@app.post("/api/cowork/execute")
async def cowork_execute(req: Request):
    body = await req.json()
    from src.cowork_bridge import get_bridge
    result = get_bridge().execute(
        body.get("script", ""),
        args=body.get("args", ["--once"]),
        timeout_s=body.get("timeout", 60),
    )
    return {"script": result.script, "exit_code": result.exit_code,
            "stdout": result.stdout[:3000], "stderr": result.stderr[:1000],
            "duration_ms": result.duration_ms, "success": result.success}

@app.get("/api/cowork/stats")
async def cowork_stats():
    from src.cowork_bridge import get_bridge
    return get_bridge().get_stats()

@app.get("/api/cowork/history")
async def cowork_history(script: str = "", limit: int = 50):
    from src.cowork_bridge import get_bridge
    return get_bridge().get_execution_history(script or None, limit)


# ── Phase 15: Self-Improvement Loop ──────────────────────────────────────────

@app.get("/api/self_improvement/analyze")
async def self_improvement_analyze():
    from src.self_improvement import get_improver
    return get_improver().analyze()

@app.get("/api/self_improvement/suggest")
async def self_improvement_suggest():
    from src.self_improvement import get_improver
    actions = get_improver().suggest_improvements()
    return [{"type": a.action_type, "target": a.target, "description": a.description,
             "priority": a.priority, "params": a.params} for a in actions]

@app.post("/api/self_improvement/apply")
async def self_improvement_apply(req: Request):
    body = await req.json()
    from src.self_improvement import get_improver
    return get_improver().apply_improvements(
        auto=body.get("auto", False),
        max_actions=body.get("max_actions", 5),
    )

@app.get("/api/self_improvement/history")
async def self_improvement_history(limit: int = 50):
    from src.self_improvement import get_improver
    return get_improver().get_history(limit)

@app.get("/api/self_improvement/stats")
async def self_improvement_stats():
    from src.self_improvement import get_improver
    return get_improver().get_stats()


# ── Phase 15: Dynamic Agents ────────────────────────────────────────────────

@app.get("/api/dynamic_agents/list")
async def dynamic_agents_list():
    from src.dynamic_agents import get_spawner
    return get_spawner().list_agents()

@app.get("/api/dynamic_agents/stats")
async def dynamic_agents_stats():
    from src.dynamic_agents import get_spawner
    return get_spawner().get_stats()

@app.post("/api/dynamic_agents/dispatch")
async def dynamic_agents_dispatch(req: Request):
    body = await req.json()
    from src.dynamic_agents import get_spawner
    return await get_spawner().dispatch(
        body.get("pattern", ""),
        body.get("prompt", ""),
    )

@app.post("/api/dynamic_agents/dispatch_cowork")
async def dynamic_agents_dispatch_cowork(req: Request):
    body = await req.json()
    from src.dynamic_agents import get_spawner
    return await get_spawner().dispatch_with_cowork(
        body.get("pattern", ""),
        body.get("prompt", ""),
    )

@app.post("/api/dynamic_agents/register")
async def dynamic_agents_register():
    from src.dynamic_agents import get_spawner
    count = get_spawner().register_to_registry()
    return {"registered": count}


# ── Phase 15: Cowork Proactive Engine ────────────────────────────────────────

@app.get("/api/cowork_proactive/needs")
async def cowork_proactive_needs():
    from src.cowork_proactive import get_proactive
    needs = get_proactive().detect_needs()
    return [{"category": n.category, "urgency": n.urgency,
             "description": n.description, "source": n.source} for n in needs]

@app.post("/api/cowork_proactive/run")
async def cowork_proactive_run(req: Request):
    body = await req.json()
    from src.cowork_proactive import get_proactive
    return get_proactive().run_proactive(
        max_scripts=body.get("max_scripts", 5),
        dry_run=body.get("dry_run", True),
    )

@app.get("/api/cowork_proactive/anticipate")
async def cowork_proactive_anticipate():
    from src.cowork_proactive import get_proactive
    return get_proactive().anticipate()

@app.get("/api/cowork_proactive/stats")
async def cowork_proactive_stats():
    from src.cowork_proactive import get_proactive
    return get_proactive().get_stats()


# ── Phase 15: Reflection Engine ──────────────────────────────────────────────

@app.get("/api/reflection/insights")
async def reflection_insights():
    from src.reflection_engine import get_reflection
    insights = get_reflection().reflect()
    return [{"category": i.category, "severity": i.severity, "title": i.title,
             "description": i.description, "metric_value": i.metric_value,
             "recommendation": i.recommendation} for i in insights]

@app.get("/api/reflection/timeline")
async def reflection_timeline(hours: int = 24):
    from src.reflection_engine import get_reflection
    return get_reflection().timeline_analysis(hours)

@app.get("/api/reflection/summary")
async def reflection_summary():
    from src.reflection_engine import get_reflection
    return get_reflection().get_summary()

@app.get("/api/reflection/stats")
async def reflection_stats():
    from src.reflection_engine import get_reflection
    return get_reflection().get_stats()


# ── Phase 16: Pattern Evolution ──────────────────────────────────────────────

@app.get("/api/evolution/gaps")
async def evolution_gaps():
    from src.pattern_evolution import get_evolution
    suggestions = get_evolution().analyze_gaps()
    return [{"action": s.action, "pattern": s.pattern_type, "description": s.description,
             "confidence": s.confidence, "model": s.model_suggestion} for s in suggestions]

@app.post("/api/evolution/create")
async def evolution_create(req: Request):
    body = await req.json()
    from src.pattern_evolution import get_evolution
    return get_evolution().auto_create_patterns(
        min_confidence=body.get("min_confidence", 0.5),
    )

@app.post("/api/evolution/evolve")
async def evolution_evolve():
    from src.pattern_evolution import get_evolution
    return get_evolution().evolve_patterns()

@app.get("/api/evolution/history")
async def evolution_history(limit: int = 50):
    from src.pattern_evolution import get_evolution
    return get_evolution().get_evolution_history(limit)

@app.get("/api/evolution/stats")
async def evolution_stats():
    from src.pattern_evolution import get_evolution
    return get_evolution().get_stats()


def main():
    import uvicorn
    host = os.getenv("JARVIS_WS_HOST", "127.0.0.1")
    try:
        port = int(os.getenv("JARVIS_WS_PORT", "9742"))
    except ValueError:
        port = 9742
    logger.info("Starting JARVIS WebSocket server on %s:%d", host, port)
    uvicorn.run(
        "python_ws.server:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
