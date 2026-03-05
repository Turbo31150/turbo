"""JARVIS MCP Server — Remote transport for Perplexity / external clients.

Exposes JARVIS MCP tools via HTTP with 3 tiers:
  --light  : 25 tools  (default, fast discovery)
  --full   : ~100 tools (comprehensive, all categories)
  --all    : 380+ tools (everything, may overwhelm LLMs)

Supports BOTH transports:
  - Streamable HTTP at /mcp  (recommended, tunnel-friendly)
  - Legacy SSE at /sse + /messages/

Usage:
    python -m src.mcp_server_sse [--port 8901] [--full] [--all] [--sse]

Then connect Perplexity custom connector to:
    https://<your-tunnel>/mcp/
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import uvicorn
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.mcp_server import TOOL_DEFINITIONS, HANDLERS, _build_input_schema, _text, _error  # noqa: E402

logger = logging.getLogger("jarvis.mcp_remote")

DEFAULT_PORT = 8901

# ═══════════════════════════════════════════════════════════════════════════
# CURATED TOOL LIST — Tools useful for Perplexity / external clients
# ═══════════════════════════════════════════════════════════════════════════
PERPLEXITY_TOOLS = {
    # Cluster IA — query the AI cluster
    "lm_query",              # Query LM Studio (M1/M2/M3)
    "lm_cluster_status",     # Cluster health check
    "lm_models",             # List loaded models
    "consensus",             # Multi-AI consensus vote
    "bridge_mesh",           # Parallel multi-node query
    "ollama_query",          # Query Ollama (local + cloud)
    "gemini_query",          # Query Gemini

    # System info
    "system_info",           # CPU/RAM/OS info
    "gpu_info",              # GPU stats (nvidia-smi)
    "powershell_run",        # Run PowerShell command

    # Brain & Memory
    "brain_status",          # Brain learning patterns
    "brain_analyze",         # Analyze a topic
    "memory_recall",         # Recall stored memory

    # Trading
    "trading_pipeline_v2",   # Full trading scan
    "trading_pending_signals", # View pending signals

    # Orchestrator
    "orch_dashboard",        # Orchestrator overview
    "orch_node_stats",       # Per-node statistics

    # Skills & Pipelines
    "list_skills",           # List available skills
    "execute_domino",        # Run a domino pipeline
    "list_dominos",          # List domino pipelines

    # Database
    "sql_query",             # Query SQLite databases
    "sql_export",            # Export SQL data

    # Utilities
    "screenshot",            # Take screenshot
    "list_processes",        # Running processes
    "network_info",          # Network status
}

# ═══════════════════════════════════════════════════════════════════════════
# FULL TOOL LIST — Complete access to ALL JARVIS capabilities (~100 tools)
# ═══════════════════════════════════════════════════════════════════════════
FULL_TOOLS = {
    # ── Cluster IA (8) ─────────────────────────────────────────────────────
    "lm_query",              # Query LM Studio (M1/M2/M3)
    "lm_cluster_status",     # Cluster health check
    "lm_models",             # List loaded models
    "lm_mcp_query",          # Query LM Studio with MCP servers
    "lm_load_model",         # Load a model on M1
    "lm_unload_model",       # Unload a model from M1
    "lm_gpu_stats",          # Detailed GPU stats
    "lm_benchmark",          # Inference latency benchmark

    # ── Intelligence & Reasoning (6) ───────────────────────────────────────
    "consensus",             # Multi-AI consensus vote
    "gemini_query",          # Query Gemini via proxy
    "bridge_query",          # Smart routing to best node
    "bridge_mesh",           # Parallel multi-node query
    "system_audit",          # Full cluster audit (10 sections, scores)
    "intent_classify",       # Classify intent from text/voice

    # ── Ollama (6) ─────────────────────────────────────────────────────────
    "ollama_query",          # Query Ollama (local + cloud)
    "ollama_models",         # List Ollama models
    "ollama_pull",           # Download an Ollama model
    "ollama_status",         # Ollama backend health
    "ollama_web_search",     # Web search via Ollama cloud
    "ollama_subagents",      # 3 parallel Ollama cloud sub-agents

    # ── Brain & Learning (6) ───────────────────────────────────────────────
    "brain_status",          # Brain learning patterns
    "brain_analyze",         # Analyze usage patterns
    "brain_suggest",         # AI-suggested new skill
    "brain_learn",           # Auto-learn: detect patterns, create skills
    "list_skills",           # List learned skills/pipelines
    "create_skill",          # Create a new skill

    # ── Domino Pipelines (3) ───────────────────────────────────────────────
    "execute_domino",        # Run a domino pipeline
    "list_dominos",          # List domino pipelines
    "domino_stats",          # Domino execution history

    # ── Trading (8) ────────────────────────────────────────────────────────
    "trading_pipeline_v2",   # Full trading scan (100 strategies + 5 AI)
    "trading_pending_signals", # Pending signals (score >= threshold)
    "trading_execute_signal", # Execute a signal (dry_run default)
    "trading_positions",     # Open positions on MEXC Futures
    "trading_status",        # Global trading pipeline status
    "trading_close_position", # Close an open position
    "trading_backtest_list", # Backtest results
    "trading_strategy_rankings", # Strategy rankings by performance

    # ── Memory & Conversations (6) ─────────────────────────────────────────
    "memory_remember",       # Store a persistent memory
    "memory_recall",         # Search memory by similarity
    "memory_list",           # List all memories
    "conv_create",           # Create a new conversation
    "conv_add_turn",         # Add an exchange to a conversation
    "conv_list",             # List recent conversations

    # ── Orchestrator (8) ───────────────────────────────────────────────────
    "orch_dashboard",        # Full orchestrator dashboard
    "orch_node_stats",       # Per-node statistics
    "orch_budget",           # Token budget report
    "orch_fallback",         # Drift-aware fallback chain
    "orch_best_node",        # Best node for a task type
    "orch_health",           # Cluster health score 0-100
    "orch_routing_matrix",   # Full routing matrix
    "orch_record_call",      # Record a call manually (calibration)

    # ── Observability & Analytics (6) ──────────────────────────────────────
    "cluster_analytics",     # Cluster performance metrics
    "voice_analytics",       # Voice pipeline statistics
    "observability_report",  # Full observability report
    "observability_alerts",  # Active anomaly alerts
    "drift_check",           # Model quality drift check
    "drift_model_health",    # Specific model health

    # ── System Info (5) ────────────────────────────────────────────────────
    "system_info",           # CPU/RAM/OS info
    "gpu_info",              # GPU stats (nvidia-smi)
    "network_info",          # Network info
    "resource_sample",       # System resource snapshot
    "health_summary",        # Quick cluster health summary

    # ── System Control (6) ─────────────────────────────────────────────────
    "powershell_run",        # Run PowerShell command
    "screenshot",            # Take screenshot
    "list_processes",        # List processes
    "kill_process",          # Kill a process
    "run_script",            # Run an indexed script
    "list_scripts",          # List all indexed scripts

    # ── File Operations (5) ────────────────────────────────────────────────
    "read_text_file",        # Read a text file
    "write_text_file",       # Write a text file
    "list_folder",           # List folder contents
    "search_files",          # Search files
    "open_folder",           # Open folder in Explorer

    # ── Database (4) ───────────────────────────────────────────────────────
    "sql_query",             # Query SQLite databases
    "sql_export",            # Export SQL data
    "db_health",             # Database health (integrity, size)
    "db_maintenance",        # Run maintenance (VACUUM + ANALYZE)

    # ── Security & Audit (5) ───────────────────────────────────────────────
    "security_score",        # System security score
    "security_scan",         # Scan for vulnerabilities
    "audit_search",          # Search audit trail
    "diagnostics_run",       # Full cluster diagnostics
    "diagnostics_quick",     # Quick cluster status

    # ── Task Queue & Workflows (5) ─────────────────────────────────────────
    "task_enqueue",          # Add task to smart queue
    "task_list",             # List pending tasks
    "workflow_list",         # List workflows
    "workflow_execute",      # Execute a workflow
    "autonomous_status",     # Autonomous loop status

    # ── Notifications & Alerts (4) ─────────────────────────────────────────
    "notif_send",            # Send notification (info/warning/critical)
    "notif_history",         # Notification history
    "alert_active",          # List active alerts
    "alert_fire",            # Fire an alert

    # ── Cache & Optimization (4) ───────────────────────────────────────────
    "cache_stats",           # Response cache statistics
    "cache_clear",           # Clear response cache
    "optimizer_optimize",    # Run auto-optimization cycle
    "optimizer_stats",       # Auto-optimizer stats

    # ── Applications & Windows (4) ─────────────────────────────────────────
    "open_app",              # Open an application
    "close_app",             # Close an application
    "open_url",              # Open URL in browser
    "list_windows",          # List open windows

    # ── Email & Communication (2) ──────────────────────────────────────────
    "emailsend_list",        # List emails
    "speak",                 # Text-to-speech TTS

    # ── Load Balancer & Services (3) ───────────────────────────────────────
    "lb_status",             # Load balancer status
    "service_list",          # List registered services
    "scheduler_list",        # List scheduled jobs

    # ── Ollama Trading Analysis (1) ────────────────────────────────────────
    "ollama_trading_analysis", # Trading analysis via 3 cloud agents

    # ── Metrics & Telemetry (3) ────────────────────────────────────────────
    "metrics_snapshot",      # Real-time metrics snapshot
    "metrics_summary",       # Metrics aggregator summary
    "tool_metrics_report",   # MCP tool performance metrics
}


def build_light_app(tool_whitelist: set[str] | None = None) -> Server:
    """Build a new MCP Server with only whitelisted tools."""
    light = Server("jarvis-perplexity")

    if tool_whitelist:
        filtered = [(n, d, s, h) for n, d, s, h in TOOL_DEFINITIONS if n in tool_whitelist]
    else:
        filtered = TOOL_DEFINITIONS

    tool_map = {n: h for n, _, _, h in filtered}

    @light.list_tools()
    async def list_tools() -> list[Tool]:
        tools = []
        for name, desc, schema, _ in filtered:
            tools.append(Tool(
                name=name,
                description=desc,
                inputSchema=_build_input_schema(schema),
            ))
        return tools

    @light.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        handler = tool_map.get(name)
        if not handler:
            return _error(f"Outil inconnu: {name}")
        try:
            result = await handler(arguments)
            if isinstance(result, list):
                return result
            return _text(str(result))
        except Exception as e:
            logger.error("Tool %s error: %s", name, e, exc_info=True)
            return _error(f"{name}: {e}")

    return light


def create_starlette_app(mcp_app: Server, use_sse: bool = False) -> Starlette:
    """Create Starlette app with Streamable HTTP (or legacy SSE) transport."""

    if use_sse:
        # Legacy SSE transport (kept for backward compat)
        from mcp.server.sse import SseServerTransport
        from starlette.responses import Response

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            logger.info("SSE client connected from %s", request.client.host if request.client else "unknown")
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as (read_stream, write_stream):
                await mcp_app.run(
                    read_stream, write_stream, mcp_app.create_initialization_options()
                )
            return Response(status_code=200)

        return Starlette(
            debug=False,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
            middleware=[
                Middleware(
                    CORSMiddleware,
                    allow_origins=["*"],
                    allow_methods=["GET", "POST", "OPTIONS"],
                    allow_headers=["*"],
                ),
            ],
        )

    # ── Streamable HTTP transport (default, tunnel-friendly) ──
    session_manager = StreamableHTTPSessionManager(
        app=mcp_app,
        json_response=False,   # SSE-style streaming responses
        stateless=True,        # No session tracking needed
    )

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            logger.info("StreamableHTTP session manager started")
            yield

    return Starlette(
        debug=False,
        lifespan=lifespan,
        routes=[
            Mount("/mcp", app=session_manager.handle_request),
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                allow_headers=["*"],
                expose_headers=["mcp-session-id"],
            ),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="JARVIS MCP Remote Server (Perplexity)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="0.0.0.0")
    tier = parser.add_mutually_exclusive_group()
    tier.add_argument("--light", action="store_true", help="25 curated tools (default)")
    tier.add_argument("--full", action="store_true", help="~100 tools covering all categories")
    tier.add_argument("--all", action="store_true", help="Expose all 380+ tools (may overwhelm LLMs)")
    parser.add_argument("--sse", action="store_true", help="Use legacy SSE transport instead of Streamable HTTP")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if args.all:
        mcp_app = build_light_app(tool_whitelist=None)
        mode = f"ALL ({len(TOOL_DEFINITIONS)} tools)"
    elif args.full:
        mcp_app = build_light_app(tool_whitelist=FULL_TOOLS)
        mode = f"FULL ({len(FULL_TOOLS)} tools — all categories)"
    else:
        mcp_app = build_light_app(tool_whitelist=PERPLEXITY_TOOLS)
        mode = f"LIGHT ({len(PERPLEXITY_TOOLS)} tools)"

    transport = "SSE (/sse)" if args.sse else "Streamable HTTP (/mcp)"
    starlette_app = create_starlette_app(mcp_app, use_sse=args.sse)

    logger.info("JARVIS MCP on http://%s:%d — %s — %s", args.host, args.port, mode, transport)
    uvicorn.run(starlette_app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
