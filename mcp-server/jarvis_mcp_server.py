"""
JARVIS MCP Server — Expose cluster tools to Claude Code via MCP protocol.

Runs on port 8901. Claude Code connects via HTTP transport.
Tools: cluster_health, dispatch_query, pipeline_run, pipeline_list, cache_stats, sql_query

Usage:
    python jarvis_mcp_server.py
    claude mcp add --transport http jarvis-mcp -- http://127.0.0.1:8901/mcp
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import sqlite3
import requests
from pathlib import Path

app = Flask(__name__)
CORS(app)

JARVIS_HOME = os.environ.get("TURBO", os.path.expanduser("~/jarvis"))
MCP_KEY = os.environ.get("MCP_API_KEY", "jarvis-mcp-key")
WS_URL = os.environ.get("WS_URL", "http://127.0.0.1:9742")
PIPELINE_DB = Path(JARVIS_HOME) / "data" / "pipeline.db"

# ── MCP Tools Definition ─────────────────────────────────────

TOOLS = [
    {
        "name": "cluster_health",
        "description": "Check health of all JARVIS cluster nodes (M1, M2, M3, OL1, Gemini)",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "dispatch_query",
        "description": "Send a query to the JARVIS cluster for AI processing",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The query to process"},
                "node": {"type": "string", "description": "Target node (M1/M2/M3/OL1/auto)", "default": "auto"},
            },
            "required": ["query"]
        }
    },
    {
        "name": "pipeline_run",
        "description": "Launch a DevOps pipeline that decomposes and distributes a task across the cluster",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Task description for the pipeline"},
                "name": {"type": "string", "description": "Pipeline name (optional)"},
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "pipeline_list",
        "description": "List recent pipelines with status and completion",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10}
            }
        }
    },
    {
        "name": "cache_stats",
        "description": "Get pipeline SQL cache statistics (entries, hits, categories)",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "sql_query",
        "description": "Execute a read-only SQL query on JARVIS databases (pipeline.db, etoile.db)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL SELECT query"},
                "db": {"type": "string", "description": "Database: pipeline or etoile", "default": "pipeline"},
            },
            "required": ["query"]
        }
    },
    {
        "name": "openclaw_agents",
        "description": "List available OpenClaw agents and their capabilities",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "telegram_send",
        "description": "Send a message to Telegram via JARVIS bot",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to send"}
            },
            "required": ["message"]
        }
    },
]

# ── Tool Handlers ─────────────────────────────────────────────

def _api(path, method="GET", data=None):
    """Call JARVIS WS API."""
    try:
        url = f"{WS_URL}{path}"
        if method == "GET":
            r = requests.get(url, timeout=10)
        else:
            r = requests.post(url, json=data, timeout=30)
        return r.json() if r.ok else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def _db_query(query, db="pipeline"):
    """Execute read-only SQL query."""
    if not query.strip().upper().startswith("SELECT"):
        return {"error": "Only SELECT queries allowed"}
    db_path = PIPELINE_DB if db == "pipeline" else Path(JARVIS_HOME) / "data" / "etoile.db"
    if not db_path.exists():
        return {"error": f"Database {db_path} not found"}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query).fetchall()
        result = [dict(r) for r in rows[:100]]
        conn.close()
        return {"rows": result, "count": len(result)}
    except Exception as e:
        return {"error": str(e)}


def handle_tool(name, args):
    if name == "cluster_health":
        return _api("/health")

    elif name == "dispatch_query":
        return _api("/api/chat", "POST", {"text": args["query"], "node": args.get("node", "auto")})

    elif name == "pipeline_run":
        return _api("/api/devops/pipelines/run", "POST", {"prompt": args["prompt"], "name": args.get("name", "")})

    elif name == "pipeline_list":
        return _api(f"/api/devops/pipelines?limit={args.get('limit', 10)}")

    elif name == "cache_stats":
        return _api("/api/devops/cache")

    elif name == "sql_query":
        return _db_query(args["query"], args.get("db", "pipeline"))

    elif name == "openclaw_agents":
        return _api("/api/openclaw/agents")

    elif name == "telegram_send":
        return _api("/api/telegram/send", "POST", {"message": args["message"]})

    return {"error": f"Unknown tool: {name}"}


# ── MCP HTTP Endpoint ─────────────────────────────────────────

@app.route("/mcp", methods=["POST"])
def mcp_handler():
    data = request.json
    if not data or data.get("jsonrpc") != "2.0":
        return jsonify({"error": "Invalid JSON-RPC"}), 400

    method = data.get("method", "")
    params = data.get("params", {})
    req_id = data.get("id", 1)

    if method == "tools/list":
        return jsonify({"jsonrpc": "2.0", "id": req_id, "result": TOOLS})

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        result = handle_tool(tool_name, tool_args)
        return jsonify({"jsonrpc": "2.0", "id": req_id, "result": result})

    elif method == "resources/list":
        return jsonify({"jsonrpc": "2.0", "id": req_id, "result": []})

    elif method == "prompts/list":
        return jsonify({"jsonrpc": "2.0", "id": req_id, "result": []})

    return jsonify({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "tools": len(TOOLS), "server": "jarvis-mcp"})


if __name__ == "__main__":
    port = int(os.environ.get("MCP_SSE_PORT", 8901))
    print(f"JARVIS MCP Server on http://0.0.0.0:{port}")
    print(f"  Tools: {', '.join(t['name'] for t in TOOLS)}")
    print(f"  Add to Claude: claude mcp add --transport http jarvis-mcp -- http://127.0.0.1:{port}/mcp")
    app.run(host="0.0.0.0", port=port)
