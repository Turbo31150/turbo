#!/usr/bin/env python3
"""MCP Bridge STDIO pour LM Studio cluster (M1/M2/M3) + Ollama (OL1).

Protocole MCP JSON-RPC via stdin/stdout.
Permet d'appeler les noeuds du cluster directement via MCP.

v4.0 - IPs mises a jour, ajout OL1, Responses API M1
"""
import json
import sys
from typing import Any

import httpx

# ── Cluster nodes configuration ─────────────────────────────────────────────
NODES = {
    "m1": {
        "name": "M1 (qwen3-8b, 6 GPU, 46tok/s)",
        "base_url": "http://127.0.0.1:1234/v1",
        "type": "lmstudio",
        "default_model": "qwen3-8b",
    },
    "m2": {
        "name": "M2 (deepseek-r1, 3 GPU, 192.168.1.26)",
        "base_url": "http://192.168.1.26:1234/v1",
        "type": "lmstudio",
        "default_model": "deepseek-r1-0528-qwen3-8b",
    },
    "m3": {
        "name": "M3 (deepseek-r1, 1 GPU, 192.168.1.113)",
        "base_url": "http://192.168.1.113:1234/v1",
        "type": "lmstudio",
        "default_model": "deepseek-r1-0528-qwen3-8b",
    },
    "ol1": {
        "name": "OL1 (Ollama, qwen3:1.7b, 84tok/s)",
        "base_url": "http://127.0.0.1:11434",
        "type": "ollama",
        "default_model": "qwen3:1.7b",
    },
}


def send_response(response: dict):
    print(json.dumps(response), flush=True)


def send_error(req_id: Any, code: int, message: str):
    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message}
    })


def send_result(req_id: Any, result: Any):
    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result
    })


def get_tools() -> list[dict]:
    tools = []
    for node_id, node in NODES.items():
        tools.extend([
            {
                "name": f"{node_id}_chat",
                "description": f"Envoyer un message a {node['name']}",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Message/prompt a envoyer"},
                        "model": {"type": "string", "description": f"Modele (defaut: {node['default_model']})"},
                        "temperature": {"type": "number", "description": "Temperature 0-2", "default": 0.3},
                        "max_tokens": {"type": "integer", "description": "Max tokens reponse", "default": 2048},
                    },
                    "required": ["message"],
                },
            },
            {
                "name": f"{node_id}_models",
                "description": f"Lister les modeles charges sur {node['name']}",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": f"{node_id}_status",
                "description": f"Verifier le statut de {node['name']}",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ])

    # Add cluster-wide tools
    tools.append({
        "name": "cluster_health",
        "description": "Health check de tous les noeuds du cluster (M1/M2/M3/OL1)",
        "inputSchema": {"type": "object", "properties": {}},
    })
    tools.append({
        "name": "cluster_chat",
        "description": "Envoyer un message au meilleur noeud disponible (auto-selection)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message a envoyer"},
                "temperature": {"type": "number", "default": 0.3},
            },
            "required": ["message"],
        },
    })
    return tools


def _chat_lmstudio(base_url: str, model: str, message: str,
                    temperature: float = 0.3, max_tokens: int = 2048) -> dict:
    """Call LM Studio chat completions API."""
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": message}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            data = resp.json()
            if "choices" in data and data["choices"]:
                content = data["choices"][0]["message"].get("content", "")
                if not content:
                    content = data["choices"][0]["message"].get("reasoning", "")
                return {"response": content, "model": model, "usage": data.get("usage", {})}
            return {"error": "No choices in response", "raw": str(data)[:500]}
    except Exception as e:
        return {"error": str(e)}


def _chat_ollama(model: str, message: str, temperature: float = 0.3) -> dict:
    """Call Ollama chat API."""
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": message}],
                    "stream": False,
                    "options": {"temperature": temperature},
                },
            )
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return {"response": content, "model": model}
    except Exception as e:
        return {"error": str(e)}


def chat_node(node_id: str, message: str, model: str = None,
              temperature: float = 0.3, max_tokens: int = 2048) -> dict:
    node = NODES.get(node_id)
    if not node:
        return {"error": f"Noeud inconnu: {node_id}"}

    model = model or node["default_model"]

    if node["type"] == "ollama":
        result = _chat_ollama(model, message, temperature)
    else:
        result = _chat_lmstudio(node["base_url"], model, message, temperature, max_tokens)

    result["node"] = node["name"]
    return result


def list_models(node_id: str) -> dict:
    node = NODES.get(node_id)
    if not node:
        return {"error": f"Noeud inconnu: {node_id}"}

    try:
        with httpx.Client(timeout=5.0) as client:
            if node["type"] == "ollama":
                resp = client.get("http://127.0.0.1:11434/api/tags")
                models = [m["name"] for m in resp.json().get("models", [])]
            else:
                resp = client.get(f"{node['base_url']}/models")
                models = [m["id"] for m in resp.json().get("data", [])]
        return {"node": node["name"], "models": models, "count": len(models)}
    except Exception as e:
        return {"node": node["name"], "error": str(e)}


def node_status(node_id: str) -> dict:
    node = NODES.get(node_id)
    if not node:
        return {"error": f"Noeud inconnu: {node_id}"}

    try:
        with httpx.Client(timeout=3.0) as client:
            if node["type"] == "ollama":
                resp = client.get("http://127.0.0.1:11434/api/tags")
                count = len(resp.json().get("models", []))
            else:
                resp = client.get(f"{node['base_url']}/models")
                count = len(resp.json().get("data", []))
        return {"node": node["name"], "status": "online", "models_loaded": count}
    except Exception as e:
        return {"node": node["name"], "status": "offline", "error": str(e)}


def cluster_health() -> dict:
    results = {}
    for node_id in NODES:
        results[node_id] = node_status(node_id)
    online = sum(1 for r in results.values() if r.get("status") == "online")
    return {"nodes": results, "online": online, "total": len(NODES)}


def cluster_chat(message: str, temperature: float = 0.3) -> dict:
    """Send to the best available node. Priority: M1 > OL1 > M3 > M2."""
    for node_id in ["m1", "ol1", "m3", "m2"]:
        status = node_status(node_id)
        if status.get("status") == "online":
            return chat_node(node_id, message, temperature=temperature)
    return {"error": "Aucun noeud disponible"}


def handle_tool_call(name: str, arguments: dict) -> dict:
    if name == "cluster_health":
        return cluster_health()
    if name == "cluster_chat":
        return cluster_chat(arguments.get("message", ""), arguments.get("temperature", 0.3))

    # Parse node_id + action from tool name
    for node_id in NODES:
        if name.startswith(f"{node_id}_"):
            action = name[len(node_id) + 1:]
            if action == "chat":
                return chat_node(
                    node_id, arguments.get("message", ""),
                    arguments.get("model"), arguments.get("temperature", 0.3),
                    arguments.get("max_tokens", 2048),
                )
            elif action == "models":
                return list_models(node_id)
            elif action == "status":
                return node_status(node_id)

    return {"error": f"Outil inconnu: {name}"}


def main():
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
        except json.JSONDecodeError:
            continue

        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            send_result(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "jarvis-lmstudio-bridge", "version": "4.0.0"},
            })
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            send_result(req_id, {"tools": get_tools()})
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = handle_tool_call(tool_name, arguments)
            send_result(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}],
            })
        else:
            if req_id is not None:
                send_error(req_id, -32601, f"Methode inconnue: {method}")


if __name__ == "__main__":
    main()
