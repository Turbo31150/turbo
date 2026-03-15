"""JARVIS IA Tool Executor — bridges AI tool calls to JARVIS HTTP endpoints.

Supports both OpenAI function-calling format and MCP callTool format.
Each tool maps to a real JARVIS REST endpoint on port 9742.

Usage:
    from src.ia_tool_executor import execute_tool_call, execute_mcp_call

    # OpenAI format (from M1/OL1 response):
    result = await execute_tool_call("jarvis_run_task", {"task_name": "zombie_gc"})

    # MCP format (from Claude MCP client):
    result = await execute_mcp_call("jarvis.runAutonomousTask", {"task_name": "zombie_gc"})
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

from src.ia_tools import TOOLS_BY_NAME, get_tool_meta, _MCP_ANNOTATIONS


__all__ = [
    "get_mcp_tools_manifest",
    "get_tool_metrics",
    "get_tool_metrics_history",
]

logger = logging.getLogger("jarvis.tool_executor")

JARVIS_BASE = "http://127.0.0.1:9742"
TIMEOUT = 30.0

# ── In-memory tool usage metrics ─────────────────────────────────────────────
_metrics: dict[str, dict[str, Any]] = defaultdict(lambda: {
    "calls": 0, "ok": 0, "errors": 0, "total_ms": 0.0,
    "by_caller": defaultdict(int), "last_called": 0.0,
})


def get_tool_metrics() -> dict[str, Any]:
    """Return tool usage metrics summary (in-memory + SQLite history)."""
    summary = {}
    for name, m in sorted(_metrics.items(), key=lambda x: -x[1]["calls"]):
        summary[name] = {
            "calls": m["calls"],
            "ok": m["ok"],
            "errors": m["errors"],
            "success_rate": round(m["ok"] / m["calls"], 2) if m["calls"] else 0,
            "avg_ms": round(m["total_ms"] / m["calls"], 1) if m["calls"] else 0,
            "by_caller": dict(m["by_caller"]),
        }
    return {"tools": summary, "total_calls": sum(m["calls"] for m in _metrics.values())}


# ── SQLite persistence (non-blocking, fire-and-forget) ───────────────────────
_ETOILE_DB = Path(__file__).resolve().parent.parent / "data" / "etoile.db"
_db_lock = threading.Lock()
_db_initialized = False


def _ensure_db():
    """Create tool_metrics table if not exists. Thread-safe, runs once."""
    global _db_initialized
    if _db_initialized:
        return
    with _db_lock:
        if _db_initialized:
            return
        try:
            with sqlite3.connect(str(_ETOILE_DB), timeout=5) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tool_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts REAL NOT NULL,
                        tool_name TEXT NOT NULL,
                        caller TEXT NOT NULL DEFAULT 'unknown',
                        success INTEGER NOT NULL DEFAULT 1,
                        latency_ms REAL NOT NULL DEFAULT 0,
                        error TEXT,
                        http_status INTEGER
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tool_metrics_ts ON tool_metrics(ts)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tool_metrics_tool ON tool_metrics(tool_name)
                """)
                conn.commit()
            _db_initialized = True
        except (sqlite3.Error, OSError) as e:
            logger.warning("tool_metrics DB init failed: %s", e)


def _persist_metric(tool_name: str, caller: str, success: bool,
                    latency_ms: float, error: str | None = None,
                    http_status: int | None = None):
    """Write one metric row to SQLite. Runs in background thread."""
    def _write():
        try:
            _ensure_db()
            with sqlite3.connect(str(_ETOILE_DB), timeout=5) as conn:
                conn.execute(
                    "INSERT INTO tool_metrics (ts, tool_name, caller, success, latency_ms, error, http_status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (time.time(), tool_name, caller, int(success), latency_ms, error, http_status),
                )
                conn.commit()
        except (sqlite3.Error, OSError) as e:
            logger.debug("tool_metrics write failed: %s", e)
    threading.Thread(target=_write, daemon=True).start()


def get_tool_metrics_history(hours: int = 24, limit: int = 500) -> list[dict]:
    """Read recent tool metrics from SQLite."""
    try:
        _ensure_db()
        since = time.time() - hours * 3600
        with sqlite3.connect(str(_ETOILE_DB), timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tool_metrics WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
                (since, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except (sqlite3.Error, OSError) as e:
        logger.warning("tool_metrics read failed: %s", e)
        return []

# ── MCP name mapping (dot-notation → underscore) ────────────────────────────
_MCP_TO_OPENAI: dict[str, str] = {
    "jarvis.autonomousStatus": "jarvis_autonomous_status",
    "jarvis.autonomousEvents": "jarvis_autonomous_events",
    "jarvis.runAutonomousTask": "jarvis_run_task",
    "jarvis.toggleTask": "jarvis_toggle_task",
    "jarvis.clusterHealth": "jarvis_cluster_health",
    "jarvis.orchestratorHealth": "jarvis_orchestrator_health",
    "jarvis.bestNode": "jarvis_best_node",
    "jarvis.diagnosticsQuick": "jarvis_diagnostics_quick",
    "jarvis.diagnosticsFull": "jarvis_diagnostics_full",
    "jarvis.remember": "jarvis_remember",
    "jarvis.recall": "jarvis_recall",
    "jarvis.dbHealth": "jarvis_db_health",
    "jarvis.dbMaintenance": "jarvis_db_maintenance",
    "jarvis.alertsActive": "jarvis_alerts_active",
    "jarvis.alertAcknowledge": "jarvis_alert_acknowledge",
    "jarvis.coworkExecute": "jarvis_cowork_execute",
    "jarvis.coworkSearch": "jarvis_cowork_search",
    "jarvis.pipelineExecute": "jarvis_pipeline_execute",
    "jarvis.sendMessage": "jarvis_send_message",
    "jarvis.classifyIntent": "jarvis_classify_intent",
    "jarvis.bootStatus": "jarvis_boot_status",
    "jarvis.bootPhase": "jarvis_boot_phase",
    "jarvis.gpuStatus": "jarvis_gpu_status",
}

# Reverse mapping
_OPENAI_TO_MCP: dict[str, str] = {v: k for k, v in _MCP_TO_OPENAI.items()}

# ── Guard-rails: tools that require extra caution ────────────────────────────
_DESTRUCTIVE_TOOLS = {
    "jarvis_cowork_execute",   # can run arbitrary scripts
    "jarvis_db_maintenance",   # modifies databases
    "jarvis_pipeline_execute", # runs multi-step pipelines
}

_READ_ONLY_TOOLS = {
    "jarvis_autonomous_status", "jarvis_autonomous_events",
    "jarvis_cluster_health", "jarvis_orchestrator_health",
    "jarvis_best_node", "jarvis_diagnostics_quick",
    "jarvis_db_health", "jarvis_alerts_active",
    "jarvis_recall", "jarvis_cowork_search",
    "jarvis_classify_intent",
}


async def execute_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    caller: str = "unknown",
    allow_destructive: bool = False,
) -> dict[str, Any]:
    """Execute a tool call and return the result.

    Args:
        tool_name: OpenAI-format tool name (e.g. "jarvis_run_task")
        arguments: Parsed arguments dict
        caller: Who is calling (for audit trail, e.g. "M1", "OL1", "claude")
        allow_destructive: If False, destructive tools are blocked

    Returns:
        {"ok": True, "result": ...} or {"ok": False, "error": ...}
    """
    if tool_name not in TOOLS_BY_NAME:
        return {"ok": False, "error": f"Unknown tool: {tool_name}",
                "available": list(TOOLS_BY_NAME.keys())}

    # Guard-rail: block destructive tools unless explicitly allowed
    if tool_name in _DESTRUCTIVE_TOOLS and not allow_destructive:
        logger.warning("Blocked destructive tool %s from caller %s", tool_name, caller)
        return {"ok": False, "error": f"Tool '{tool_name}' is destructive and requires allow_destructive=True",
                "hint": "Set allow_destructive=True or use a privileged caller scope"}

    meta = get_tool_meta(tool_name)
    method = meta.get("method", "GET")
    path_template = meta.get("path", "")

    # Resolve path parameters (e.g. {task_name})
    path = path_template
    for key, val in arguments.items():
        placeholder = "{" + key + "}"
        if placeholder in path:
            path = path.replace(placeholder, str(val))

    url = f"{JARVIS_BASE}{path}"

    logger.info("Tool %s called by %s -> %s %s", tool_name, caller, method, url)

    t0 = time.monotonic()
    m = _metrics[tool_name]
    m["calls"] += 1
    m["by_caller"][caller] += 1
    m["last_called"] = time.time()

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            if method == "GET":
                params = {k: v for k, v in arguments.items()
                          if "{" + k + "}" not in path_template}
                resp = await client.get(url, params=params or None)
            elif method == "POST":
                body = {k: v for k, v in arguments.items()
                        if "{" + k + "}" not in path_template}
                resp = await client.post(url, json=body or None)
            elif method == "DELETE":
                resp = await client.delete(url)
            else:
                m["errors"] += 1
                return {"ok": False, "error": f"Unsupported method: {method}"}

            elapsed_ms = (time.monotonic() - t0) * 1000
            m["total_ms"] += elapsed_ms

            if resp.status_code >= 400:
                m["errors"] += 1
                elapsed_ms = (time.monotonic() - t0) * 1000
                m["total_ms"] += elapsed_ms
                _persist_metric(tool_name, caller, False, elapsed_ms,
                                error=f"HTTP {resp.status_code}", http_status=resp.status_code)
                return {"ok": False, "error": f"HTTP {resp.status_code}", "body": resp.text[:500]}

            try:
                data = resp.json()
            except (json.JSONDecodeError, ValueError):
                data = {"raw": resp.text[:1000]}

            m["ok"] += 1
            _persist_metric(tool_name, caller, True, elapsed_ms, http_status=resp.status_code)
            return {"ok": True, "result": data}

    except httpx.TimeoutException:
        elapsed_err = (time.monotonic() - t0) * 1000
        m["errors"] += 1
        m["total_ms"] += elapsed_err
        logger.error("Tool %s timed out (%.0fs)", tool_name, TIMEOUT)
        _persist_metric(tool_name, caller, False, elapsed_err, error="timeout")
        return {"ok": False, "error": f"Timeout after {TIMEOUT}s"}
    except httpx.ConnectError:
        elapsed_err = (time.monotonic() - t0) * 1000
        m["errors"] += 1
        m["total_ms"] += elapsed_err
        logger.error("Tool %s: JARVIS WS unreachable at %s", tool_name, JARVIS_BASE)
        _persist_metric(tool_name, caller, False, elapsed_err, error="connect_error")
        return {"ok": False, "error": "JARVIS WS unreachable (port 9742)"}
    except Exception as e:
        elapsed_err = (time.monotonic() - t0) * 1000
        m["errors"] += 1
        m["total_ms"] += elapsed_err
        logger.exception("Tool %s failed", tool_name)
        _persist_metric(tool_name, caller, False, elapsed_err, error=str(e)[:200])
        return {"ok": False, "error": str(e)}


async def execute_mcp_call(
    mcp_tool_name: str,
    arguments: dict[str, Any],
    *,
    caller: str = "mcp",
) -> dict[str, Any]:
    """Execute a tool call using MCP dot-notation name.

    Translates MCP name to OpenAI name and delegates to execute_tool_call.
    """
    openai_name = _MCP_TO_OPENAI.get(mcp_tool_name)
    if not openai_name:
        return {"ok": False, "error": f"Unknown MCP tool: {mcp_tool_name}"}
    return await execute_tool_call(openai_name, arguments, caller=caller)


def get_mcp_tools_manifest() -> list[dict[str, Any]]:
    """Return tools in MCP listTools format.

    Each tool has: name (dot-notation), title, description, inputSchema, annotations.
    Annotations follow the MCP spec: readOnlyHint, destructiveHint, openWorldHint.
    """
    manifest = []
    for tool in TOOLS_BY_NAME.values():
        fn = tool["function"]
        openai_name = fn["name"]
        mcp_name = _OPENAI_TO_MCP.get(openai_name, openai_name)
        entry = {
            "name": mcp_name,
            "title": fn["description"][:80],
            "description": fn["description"],
            "inputSchema": fn["parameters"],
        }
        annotations = _MCP_ANNOTATIONS.get(openai_name)
        if annotations:
            entry["annotations"] = annotations
        manifest.append(entry)
    return manifest


async def process_model_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    caller: str = "M1",
    allow_destructive: bool = False,
) -> list[dict[str, Any]]:
    """Process a batch of tool_calls from a model response.

    Expects OpenAI format: [{"id": "...", "function": {"name": "...", "arguments": "..."}}]
    Returns results ready to be sent back as tool_call_output messages.
    """
    results = []
    for tc in tool_calls:
        tc_id = tc.get("id", "")
        fn = tc.get("function", {})
        name = fn.get("name", "")
        try:
            args = json.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else fn.get("arguments", {})
        except json.JSONDecodeError:
            args = {}

        result = await execute_tool_call(
            name, args, caller=caller, allow_destructive=allow_destructive,
        )
        results.append({
            "tool_call_id": tc_id,
            "role": "tool",
            "content": json.dumps(result, ensure_ascii=False, default=str),
        })
    return results
