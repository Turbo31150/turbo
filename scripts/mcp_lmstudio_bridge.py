#!/usr/bin/env python3
"""MCP Bridge STDIO pour LM Studio cluster (M1/M2/M3).

Protocole MCP JSON-RPC via stdin/stdout.
Permet d'appeler les noeuds LM Studio directement depuis Claude Code.
Lit les URLs depuis .env via _paths.py.

Usage dans .mcp.json:
    {"command": "python", "args": ["scripts/mcp_lmstudio_bridge.py"]}
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

# Load env
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Cluster config from env
NODES = {
    "m1": {
        "name": "M1 Local (qwen3-8b, 6 GPU)",
        "url": os.environ.get("LM_STUDIO_1_URL", "http://127.0.0.1:1234"),
        "key": os.environ.get("LM_STUDIO_1_API_KEY", ""),
    },
    "m2": {
        "name": "M2 Reasoning (deepseek-r1, 3 GPU)",
        "url": os.environ.get("LM_STUDIO_2_URL", "http://192.168.1.26:1234"),
        "key": os.environ.get("LM_STUDIO_2_API_KEY", ""),
    },
    "m3": {
        "name": "M3 Fallback (deepseek-r1, 1 GPU)",
        "url": os.environ.get("LM_STUDIO_3_URL", "http://192.168.1.113:1234"),
        "key": os.environ.get("LM_STUDIO_3_API_KEY", ""),
    },
}


def send_response(response: dict):
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def send_error(req_id: Any, code: int, message: str):
    send_response({
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": code, "message": message},
    })


def send_result(req_id: Any, result: Any):
    send_response({
        "jsonrpc": "2.0", "id": req_id,
        "result": result,
    })


def get_tools() -> list[dict]:
    tools = []
    for node_id, node in NODES.items():
        tools.extend([
            {
                "name": f"{node_id}_chat",
                "description": f"Send prompt to {node['name']} ({node['url']})",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Prompt to send"},
                        "model": {"type": "string", "description": "Model name (optional)"},
                        "temperature": {"type": "number", "default": 0.3},
                        "max_tokens": {"type": "integer", "default": 2048},
                    },
                    "required": ["message"],
                },
            },
            {
                "name": f"{node_id}_models",
                "description": f"List loaded models on {node['name']}",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": f"{node_id}_status",
                "description": f"Health check {node['name']}",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ])

    # Add cluster-wide tools
    tools.append({
        "name": "cluster_health",
        "description": "Check health of all LM Studio nodes (M1/M2/M3)",
        "inputSchema": {"type": "object", "properties": {}},
    })
    tools.append({
        "name": "cluster_chat",
        "description": "Send prompt to best available node (M1 priority)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Prompt to send"},
                "model": {"type": "string", "description": "Model name (optional)"},
                "temperature": {"type": "number", "default": 0.3},
                "max_tokens": {"type": "integer", "default": 2048},
            },
            "required": ["message"],
        },
    })

    return tools


def _http_post(url: str, data: dict, key: str = "", timeout: int = 120) -> dict:
    """HTTP POST with optional auth."""
    import urllib.request
    body = json.dumps(data).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, body, headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _http_get(url: str, key: str = "", timeout: int = 10) -> dict:
    """HTTP GET with optional auth."""
    import urllib.request
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def handle_chat(node_id: str, params: dict) -> dict:
    node = NODES[node_id]
    message = params.get("message", "")
    model = params.get("model", "")
    temp = params.get("temperature", 0.3)
    max_tokens = params.get("max_tokens", 2048)

    # Use new API format
    url = f"{node['url']}/api/v1/chat"
    payload = {
        "model": model,
        "input": f"/nothink\n{message}" if node_id == "m1" else message,
        "temperature": temp,
        "max_output_tokens": max_tokens,
        "stream": False,
        "store": False,
    }

    result = _http_post(url, payload, node["key"])

    # Extract response text
    output = result.get("output", [])
    texts = []
    for block in output:
        if block.get("type") == "message":
            for c in block.get("content", []):
                if c.get("type") == "output_text":
                    texts.append(c.get("text", ""))
    response_text = "\n".join(texts) if texts else json.dumps(result)

    return {"node": node_id, "response": response_text}


def handle_models(node_id: str) -> dict:
    node = NODES[node_id]
    url = f"{node['url']}/api/v1/models"
    try:
        data = _http_get(url, node["key"])
        models = data.get("data", data.get("models", []))
        loaded = [m for m in models if m.get("loaded_instances")]
        return {
            "node": node_id,
            "total": len(models),
            "loaded": len(loaded),
            "models": [m.get("id", "?") for m in loaded],
        }
    except Exception as e:
        return {"node": node_id, "error": str(e)}


def handle_status(node_id: str) -> dict:
    node = NODES[node_id]
    url = f"{node['url']}/api/v1/models"
    try:
        data = _http_get(url, node["key"], timeout=5)
        models = data.get("data", data.get("models", []))
        loaded = len([m for m in models if m.get("loaded_instances")])
        return {"node": node_id, "status": "online", "loaded_models": loaded}
    except Exception as e:
        return {"node": node_id, "status": "offline", "error": str(e)}


def handle_cluster_health() -> dict:
    results = {}
    for node_id in NODES:
        results[node_id] = handle_status(node_id)
    online = sum(1 for r in results.values() if r["status"] == "online")
    return {"nodes": results, "online": online, "total": len(NODES)}


def handle_cluster_chat(params: dict) -> dict:
    """Send to best available node (M1 > M2 > M3)."""
    for node_id in ["m1", "m2", "m3"]:
        try:
            status = handle_status(node_id)
            if status["status"] == "online":
                return handle_chat(node_id, params)
        except Exception:
            continue
    return {"error": "All nodes offline"}


def handle_tool_call(req_id: Any, name: str, arguments: dict):
    try:
        if name == "cluster_health":
            send_result(req_id, {"content": [{"type": "text", "text": json.dumps(handle_cluster_health(), indent=2)}]})
        elif name == "cluster_chat":
            result = handle_cluster_chat(arguments)
            send_result(req_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        elif name.endswith("_chat"):
            node_id = name.replace("_chat", "")
            result = handle_chat(node_id, arguments)
            send_result(req_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        elif name.endswith("_models"):
            node_id = name.replace("_models", "")
            result = handle_models(node_id)
            send_result(req_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        elif name.endswith("_status"):
            node_id = name.replace("_status", "")
            result = handle_status(node_id)
            send_result(req_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        else:
            send_error(req_id, -32601, f"Unknown tool: {name}")
    except Exception as e:
        send_result(req_id, {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True})


def main():
    """MCP stdio loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = msg.get("id")
        method = msg.get("method", "")

        if method == "initialize":
            send_result(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "jarvis-lmstudio-bridge", "version": "2.0.0"},
            })
        elif method == "notifications/initialized":
            pass  # Acknowledge
        elif method == "tools/list":
            send_result(req_id, {"tools": get_tools()})
        elif method == "tools/call":
            params = msg.get("params", {})
            handle_tool_call(req_id, params.get("name", ""), params.get("arguments", {}))
        elif method == "ping":
            send_result(req_id, {})
        else:
            send_error(req_id, -32601, f"Method not found: {method}")


if __name__ == "__main__":
    main()
