"""Chat route — AI conversation via Claude SDK + Commander pipeline + MAO consensus."""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any

import httpx

from python_ws.helpers import strip_agent_tag, extract_lmstudio_content

logger = logging.getLogger("jarvis.chat")

# Shared httpx client — avoids TCP reconnect overhead per request
_http: httpx.AsyncClient | None = None


def _get_http() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            timeout=60,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _http

# Turbo root — resolved relative to this file (python_ws/routes/chat.py → turbo/)
_TURBO_ROOT = Path(__file__).resolve().parent.parent.parent

# Try to import src modules
try:
    from src.config import config as jarvis_config, build_lmstudio_payload, build_ollama_payload
except ImportError:
    jarvis_config = None
    build_lmstudio_payload = None
    build_ollama_payload = None

try:
    from src.commander import classify_task, decompose_task, build_commander_enrichment
except ImportError:
    classify_task = None
    decompose_task = None
    build_commander_enrichment = None


MAX_MESSAGE_LENGTH = 10_000  # 10K chars max per message

# Extract cluster URLs from config (falls back to defaults if config unavailable)
_OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"
_M1_CHAT = "http://127.0.0.1:1234/api/v1/chat"
_M2_CHAT = "http://192.168.1.26:1234/api/v1/chat"
_M3_CHAT = "http://192.168.1.113:1234/api/v1/chat"
if jarvis_config:
    for _n in jarvis_config.lm_nodes:
        if _n.name == "M1":
            _M1_CHAT = f"{_n.url}/api/v1/chat"
        elif _n.name == "M2":
            _M2_CHAT = f"{_n.url}/api/v1/chat"
        elif _n.name == "M3":
            _M3_CHAT = f"{_n.url}/api/v1/chat"
    if jarvis_config.ollama_nodes:
        _OLLAMA_CHAT = f"{jarvis_config.ollama_nodes[0].url}/api/chat"
MAX_SESSION_MESSAGES = 200   # Keep last 200 messages in memory


class ChatSession:
    """Manages a chat conversation with bounded history."""

    def __init__(self):
        self.messages: list[dict] = []
        self.active = False

    def add_message(self, role: str, content: str, agent: str | None = None,
                    tool_calls: list | None = None) -> dict:
        msg = {
            "id": f"msg_{len(self.messages)}_{int(time.time()*1000)}",
            "role": role,
            "content": content[:MAX_MESSAGE_LENGTH],
            "agent": agent,
            "tool_calls": tool_calls or [],
            "timestamp": time.time(),
        }
        self.messages.append(msg)
        # Evict oldest messages to prevent unbounded growth
        if len(self.messages) > MAX_SESSION_MESSAGES:
            self.messages = self.messages[-MAX_SESSION_MESSAGES:]
        return msg

    def clear(self):
        self.messages.clear()


_session = ChatSession()


async def handle_chat_request(action: str, payload: dict) -> dict:
    """Handle chat channel requests."""
    if action == "send_message":
        return await _send_message(payload)
    elif action == "clear_conversation":
        _session.clear()
        return {"cleared": True}
    elif action == "get_history":
        return {"messages": _session.messages}
    return {"error": f"Unknown chat action: {action}"}


async def _send_message(payload: dict) -> dict:
    """Process a user message: try command execution first, fallback to IA."""
    text = (payload.get("content") or payload.get("text") or "").strip()
    if not text:
        return {"error": "Empty message"}
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH]

    # Add user message
    user_msg = _session.add_message("user", text)

    start = time.time()

    try:
        # Step 0: Detect /consensus prefix BEFORE command matching
        force_consensus = text.lower().startswith("/consensus ")
        if force_consensus:
            consensus_text = text[len("/consensus "):].strip()
            response_text = await _query_parallel_consensus(consensus_text)
            task_type = "consensus"
            agent_name = _get_agent_for_task(task_type)
            elapsed = time.time() - start
            agent_msg = _session.add_message("assistant", response_text, agent=agent_name)
            agent_msg["task_type"] = task_type
            agent_msg["elapsed"] = round(elapsed, 2)
            return {
                "user_message": user_msg,
                "agent_message": agent_msg,
                "task_type": task_type,
            }

        # Step 1: Try to match a voice command and execute it
        cmd_result = await _try_execute_command(text)
        if cmd_result:
            elapsed = time.time() - start
            agent_msg = _session.add_message("assistant", cmd_result["response"], agent="ia-system")
            agent_msg["task_type"] = "command"
            agent_msg["elapsed"] = round(elapsed, 2)
            agent_msg["command"] = cmd_result.get("command_name")
            return {
                "user_message": user_msg,
                "agent_message": agent_msg,
                "task_type": "command",
                "executed": True,
            }

        # Step 2: No command matched — classify and route to IA
        task_type = "simple"
        if classify_task:
            try:
                if inspect.iscoroutinefunction(classify_task):
                    task_type = await classify_task(text)
                else:
                    task_type = await asyncio.to_thread(classify_task, text)
                if not isinstance(task_type, str):
                    task_type = "simple"
            except (ImportError, asyncio.TimeoutError, ValueError, TypeError) as e:
                logger.warning("classify_task failed: %s", e)
                task_type = "simple"

        # Consensus via classifier (not /consensus prefix)
        if task_type == "consensus":
            response_text = await _query_parallel_consensus(text)
        else:
            response_text = await _query_local_ia(text, task_type)

        agent_name = _get_agent_for_task(task_type)
        elapsed = time.time() - start

        agent_msg = _session.add_message("assistant", response_text, agent=agent_name)
        agent_msg["task_type"] = task_type
        agent_msg["elapsed"] = round(elapsed, 2)

        return {
            "user_message": user_msg,
            "agent_message": agent_msg,
            "task_type": task_type,
        }
    except (asyncio.TimeoutError, KeyError, ValueError, RuntimeError, OSError) as e:
        logger.error("_send_message error: %s\n%s", e, traceback.format_exc())
        error_msg = _session.add_message("system", f"Erreur: {str(e)}")
        return {"error": str(e), "message": error_msg}


async def _try_execute_command(text: str) -> dict | None:
    """Try to match text to a command and execute it. Returns None if no match."""
    try:
        from src.voice_correction import full_correction_pipeline
        from src.executor import execute_command
    except ImportError:
        return None

    try:
        result = await full_correction_pipeline(text)
    except (OSError, ValueError, KeyError) as exc:
        logger.debug("_try_execute_command correction failed: %s", exc)
        return None

    cmd = result.get("command")
    confidence = result.get("confidence", 0)
    params = result.get("params", {})

    if not cmd or confidence < 0.75:
        return None

    # Execute the command
    try:
        output = await execute_command(cmd, params)
    except (asyncio.TimeoutError, RuntimeError, ValueError) as e:
        output = f"Erreur execution: {e}"

    # Skip special sentinel values — those need IA handling
    if isinstance(output, str) and output.startswith("__"):
        return None

    return {
        "command_name": cmd.name,
        "description": cmd.description,
        "action_type": cmd.action_type,
        "confidence": confidence,
        "response": output,
    }


JARVIS_SYSTEM = (
    "Tu es JARVIS, assistant IA vocal francais. "
    "Reponds de facon concise (2-3 phrases max) et naturelle. "
    "Tu controles un cluster de machines IA (M1, M2, M3, OL1) et tu peux "
    "executer des commandes systeme, trading, diagnostic. "
    "Reponds toujours en francais."
)


def _build_chat_history(current_text: str, max_turns: int = 6) -> list[dict]:
    """Build message history from session for context-aware responses."""
    history = [{"role": "system", "content": JARVIS_SYSTEM}]
    # Take last N messages (user + assistant pairs)
    recent = _session.messages[-(max_turns * 2):]
    for msg in recent:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            history.append({"role": "user", "content": content})
        elif role == "assistant":
            history.append({"role": "assistant", "content": strip_agent_tag(content)})
    # Add current user message
    history.append({"role": "user", "content": current_text})
    return history


def _build_lmstudio_input(current_text: str, max_turns: int = 6) -> str:
    """Build conversation input for LM Studio Responses API."""
    parts = [f"/nothink\n{JARVIS_SYSTEM}"]
    recent = _session.messages[-(max_turns * 2):]
    for msg in recent:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            parts.append(f"\nUtilisateur: {content}")
        elif role == "assistant":
            parts.append(f"\nJARVIS: {strip_agent_tag(content)}")
    parts.append(f"\nUtilisateur: {current_text}")
    return "\n".join(parts)


def _get_model_auth(model_entry: dict) -> str:
    """Resolve auth for a model entry: 'auth_node' → config lookup, 'auth' → direct value."""
    if "auth_node" in model_entry and jarvis_config:
        node = jarvis_config.get_node(model_entry["auth_node"])
        if node:
            return node.auth_headers.get("Authorization", "")
    return model_entry.get("auth", "")


## All available models with metadata for the frontend
ALL_MODELS = [
    {"id": "gpt-oss:120b-cloud", "name": "gpt-oss 120B", "group": "cloud", "score": 100, "weight": 1.9,
     "url": _OLLAMA_CHAT, "backend": "ollama", "speed": "51 tok/s"},
    {"id": "qwen3-8b", "name": "M1 / qwen3-8b", "group": "local", "score": 98, "weight": 1.8,
     "url": _M1_CHAT, "backend": "lmstudio", "speed": "45 tok/s"},
    {"id": "devstral-2:123b-cloud", "name": "devstral-2 123B", "group": "cloud", "score": 94, "weight": 1.5,
     "url": _OLLAMA_CHAT, "backend": "ollama", "speed": "36 tok/s"},
    {"id": "deepseek-coder-v2-lite-instruct", "name": "M2 / deepseek-coder", "group": "local", "score": 85, "weight": 1.4,
     "url": _M2_CHAT, "backend": "lmstudio",
     "auth_node": "M2", "speed": "15 tok/s"},
    {"id": "qwen3:1.7b", "name": "OL1 / qwen3 1.7B", "group": "local", "score": 88, "weight": 1.3,
     "url": _OLLAMA_CHAT, "backend": "ollama", "speed": "84 tok/s"},
    {"id": "glm-4.7:cloud", "name": "GLM 4.7", "group": "cloud", "score": 88, "weight": 1.2,
     "url": _OLLAMA_CHAT, "backend": "ollama", "speed": "48 tok/s"},
    {"id": "minimax-m2.5:cloud", "name": "Minimax (web)", "group": "cloud", "score": 80, "weight": 1.0,
     "url": _OLLAMA_CHAT, "backend": "ollama", "speed": "var"},
    {"id": "mistral-7b-instruct-v0.3", "name": "M3 / mistral-7b", "group": "local", "score": 89, "weight": 0.8,
     "url": _M3_CHAT, "backend": "lmstudio",
     "auth_node": "M3", "speed": "10 tok/s"},
    # Proxy backends (subprocess node)
    {"id": "gemini-3-pro", "name": "GEMINI / gemini-3-pro", "group": "proxy", "score": 74, "weight": 1.2,
     "backend": "proxy", "proxy_path": str(_TURBO_ROOT / "gemini-proxy.js"), "speed": "var"},
    {"id": "claude-opus", "name": "CLAUDE / opus", "group": "proxy", "score": 85, "weight": 1.2,
     "backend": "proxy", "proxy_path": str(_TURBO_ROOT / "claude-proxy.js"), "speed": "var"},
]

# Health cache for models (refreshed every 30s)
_model_health: dict[str, bool] = {}
_health_ts: float = 0
_health_lock: asyncio.Lock = asyncio.Lock()


async def _query_proxy(proxy_path: str, prompt: str, timeout: float = 120.0) -> str | None:
    """Query GEMINI or CLAUDE via their Node.js proxy subprocess."""
    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "node", proxy_path, prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode == 0 and stdout:
            text = stdout.decode("utf-8", errors="replace").strip()
            if text:
                return text
    except asyncio.TimeoutError:
        if proc is not None:
            try:
                proc.kill()
                await proc.wait()
            except OSError as exc:
                logger.debug("Failed to kill proxy process: %s", exc)
        logger.debug("_query_proxy timeout after %.0fs: %s", timeout, proxy_path)
    except OSError as exc:
        logger.debug("_query_proxy failed: %s", exc)
    return None


async def check_models_health() -> dict:
    """Health check all models, return status dict.

    Uses asyncio.Lock to prevent thundering herd — only one caller runs
    the actual health check while others wait and get the cached result.
    """
    global _model_health, _health_ts

    # Fast path: cache still valid
    if time.time() - _health_ts < 30:
        return _model_health

    async with _health_lock:
        # Double-check after acquiring lock (another coroutine may have refreshed)
        if time.time() - _health_ts < 30:
            return _model_health

        results = {}
        client = _get_http()
        for m in ALL_MODELS:
            try:
                if m["backend"] == "proxy":
                    results[m["id"]] = os.path.isfile(m.get("proxy_path", ""))
                elif m["backend"] == "ollama":
                    ollama_base = _OLLAMA_CHAT.rsplit("/api/chat", 1)[0]
                    r = await client.get(f"{ollama_base}/api/tags", timeout=5)
                    results[m["id"]] = r.status_code == 200
                else:
                    url = m["url"].replace("/api/v1/chat", "/api/v1/models")
                    headers = {}
                    auth = _get_model_auth(m)
                    if auth:
                        headers["Authorization"] = auth
                    r = await client.get(url, headers=headers, timeout=5)
                    results[m["id"]] = r.status_code == 200
            except (httpx.HTTPError, OSError) as exc:
                logger.debug("health check %s failed: %s", m["id"], exc)
                results[m["id"]] = False
        _model_health = results
        _health_ts = time.time()
        return results


async def get_models_with_status() -> list[dict]:
    """Return all models with online/offline status."""
    health = await check_models_health()
    return [
        {**{k: v for k, v in m.items() if k not in ("url", "auth", "auth_node", "backend", "proxy_path")},
         "online": health.get(m["id"], False)}
        for m in ALL_MODELS
    ]


# Task-type to routing priority mapping (bench-final 2026-02-28)
ROUTING_MATRIX = {
    "code":         ["gpt-oss:120b-cloud", "qwen3-8b", "devstral-2:123b-cloud", "deepseek-coder-v2-lite-instruct"],
    "analyse":      ["gpt-oss:120b-cloud", "qwen3-8b", "devstral-2:123b-cloud", "claude-opus"],
    "architecture": ["gemini-3-pro", "qwen3-8b", "gpt-oss:120b-cloud", "claude-opus"],
    "trading":      ["minimax-m2.5:cloud", "qwen3-8b", "gpt-oss:120b-cloud"],
    "web":          ["minimax-m2.5:cloud", "gpt-oss:120b-cloud", "gemini-3-pro"],
    "systeme":      ["qwen3-8b", "qwen3:1.7b"],
    "consensus":    ["gpt-oss:120b-cloud", "qwen3-8b", "devstral-2:123b-cloud", "gemini-3-pro", "claude-opus"],
    "simple":       ["qwen3:1.7b", "qwen3-8b", "gpt-oss:120b-cloud"],
}


async def _query_local_ia(text: str, task_type: str) -> str:
    """Query IA nodes for a response using full routing matrix."""

    # Build node priority from routing matrix (copy to avoid mutating the original)
    model_ids = list(ROUTING_MATRIX.get(task_type, ROUTING_MATRIX["simple"]))
    # Add fallbacks not in the list
    all_ids = [m["id"] for m in ALL_MODELS]
    for mid in all_ids:
        if mid not in model_ids:
            model_ids.append(mid)

    model_map = {m["id"]: m for m in ALL_MODELS}
    nodes_priority = []
    for mid in model_ids:
        m = model_map.get(mid)
        if not m:
            continue
        node = {"name": mid.split(":")[0].upper() if ":" in mid else m["name"].split("/")[0].strip(),
                "backend": m["backend"], "model": mid}
        if m["backend"] == "proxy":
            node["proxy_path"] = m["proxy_path"]
        else:
            node["url"] = m["url"]
        auth = _get_model_auth(m)
        if auth:
            node["auth"] = auth
        nodes_priority.append(node)

    # Build conversation history with memory
    chat_messages = _build_chat_history(text)
    lmstudio_input = _build_lmstudio_input(text)

    client = _get_http()
    for node in nodes_priority:
        try:
            if node["backend"] == "proxy":
                # GEMINI / CLAUDE via subprocess proxy
                result = await _query_proxy(node["proxy_path"], text, timeout=60.0)
                if result:
                    return f"[{node['name']}] {result}"
            elif node["backend"] == "ollama":
                ol_payload = (build_ollama_payload(node["model"], chat_messages)
                              if build_ollama_payload else
                              {"model": node["model"], "messages": chat_messages,
                               "stream": False, "think": False})
                resp = await client.post(node["url"], json=ol_payload)
                resp.raise_for_status()
                content = resp.json().get("message", {}).get("content", "")
                if content and content.strip():
                    return f"[{node['name']}] {content.strip()}"
            else:
                headers = {"Content-Type": "application/json"}
                if node.get("auth"):
                    headers["Authorization"] = node["auth"]
                lms_payload = (build_lmstudio_payload(node["model"], lmstudio_input,
                                                      temperature=0.3, max_output_tokens=512)
                               if build_lmstudio_payload else
                               {"model": node["model"], "input": lmstudio_input,
                                "temperature": 0.3, "max_output_tokens": 512,
                                "stream": False, "store": False})
                resp = await client.post(node["url"], headers=headers, json=lms_payload)
                resp.raise_for_status()
                data = resp.json()
                if data.get("error"):
                    continue
                extracted = extract_lmstudio_content(data)
                if extracted:
                    return f"[{node['name']}] {extracted}"
        except (httpx.HTTPError, asyncio.TimeoutError, OSError, KeyError) as exc:
            logger.debug("_query_local_ia %s failed: %s", node.get("name", "?"), exc)
            continue

    return "Aucun agent disponible."


# Consensus models: all agents dispatched in parallel for weighted vote
CONSENSUS_MODELS = [
    "gpt-oss:120b-cloud", "qwen3-8b", "devstral-2:123b-cloud",
    "deepseek-coder-v2-lite-instruct", "glm-4.7:cloud",
    "gemini-3-pro", "claude-opus",
]

# Weights for consensus vote (from MAO bench-final 2026-02-28)
CONSENSUS_WEIGHTS = {
    "gpt-oss:120b-cloud": 1.9,
    "qwen3-8b": 1.8,
    "devstral-2:123b-cloud": 1.5,
    "deepseek-coder-v2-lite-instruct": 1.4,
    "qwen3:1.7b": 1.3,
    "glm-4.7:cloud": 1.2,
    "gemini-3-pro": 1.2,
    "claude-opus": 1.2,
    "minimax-m2.5:cloud": 1.0,
    "mistral-7b-instruct-v0.3": 0.8,
}


async def _query_single_node(model_id: str, text: str, chat_messages: list, lmstudio_input: str) -> dict:
    """Query a single node and return {model, content, latency} or {model, error}."""
    model_map = {m["id"]: m for m in ALL_MODELS}
    m = model_map.get(model_id)
    if not m:
        return {"model": model_id, "error": "unknown model"}

    name = model_id.split(":")[0].upper() if ":" in model_id else m["name"].split("/")[0].strip()
    start = time.time()
    try:
        if m["backend"] == "proxy":
            result = await _query_proxy(m["proxy_path"], text, timeout=60.0)
            if result:
                return {"model": model_id, "name": name, "content": result, "latency": round(time.time() - start, 2)}
            return {"model": model_id, "name": name, "error": "proxy timeout"}

        client = _get_http()
        if m["backend"] == "ollama":
            ol_payload = (build_ollama_payload(model_id, chat_messages)
                          if build_ollama_payload else
                          {"model": model_id, "messages": chat_messages,
                           "stream": False, "think": False})
            resp = await client.post(m["url"], json=ol_payload)
            resp.raise_for_status()
            content = resp.json().get("message", {}).get("content", "")
            if content and content.strip():
                return {"model": model_id, "name": name, "content": content.strip(), "latency": round(time.time() - start, 2)}
        else:
            headers = {"Content-Type": "application/json"}
            auth = _get_model_auth(m)
            if auth:
                headers["Authorization"] = auth
            lms_payload = (build_lmstudio_payload(model_id, lmstudio_input,
                                                  temperature=0.3, max_output_tokens=512)
                           if build_lmstudio_payload else
                           {"model": model_id, "input": lmstudio_input,
                            "temperature": 0.3, "max_output_tokens": 512,
                            "stream": False, "store": False})
            resp = await client.post(m["url"], headers=headers, json=lms_payload)
            resp.raise_for_status()
            extracted = extract_lmstudio_content(resp.json())
            if extracted:
                return {"model": model_id, "name": name, "content": extracted, "latency": round(time.time() - start, 2)}
    except (httpx.HTTPError, asyncio.TimeoutError, OSError, KeyError) as e:
        return {"model": model_id, "name": name, "error": str(e)}
    return {"model": model_id, "name": name, "error": "empty response"}


async def _query_parallel_consensus(text: str) -> str:
    """Dispatch to ALL agents in parallel, synthesize with weighted vote."""
    chat_messages = _build_chat_history(text)
    lmstudio_input = _build_lmstudio_input(text)

    # Launch all consensus models in parallel
    tasks = [
        _query_single_node(mid, text, chat_messages, lmstudio_input)
        for mid in CONSENSUS_MODELS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect successful responses
    responses = []
    errors = []
    for r in results:
        if isinstance(r, Exception):
            errors.append(str(r))
        elif isinstance(r, dict) and r.get("content"):
            responses.append(r)
        elif isinstance(r, dict):
            errors.append(f"{r.get('name', '?')}: {r.get('error', '?')}")

    if not responses:
        return "CONSENSUS FAIL — Aucun agent n'a repondu."

    # Build weighted synthesis
    total_weight = sum(CONSENSUS_WEIGHTS.get(r["model"], 1.0) for r in responses)
    parts = [f"**CONSENSUS MAO** — {len(responses)}/{len(CONSENSUS_MODELS)} agents, poids total {total_weight:.1f}\n"]

    for r in sorted(responses, key=lambda x: CONSENSUS_WEIGHTS.get(x["model"], 1.0), reverse=True):
        w = CONSENSUS_WEIGHTS.get(r["model"], 1.0)
        parts.append(f"**[{r['name']}]** (w={w}, {r['latency']}s):\n{r['content']}\n")

    if errors:
        parts.append(f"\n_Timeouts/erreurs: {', '.join(errors)}_")

    return "\n---\n".join(parts)


def _get_agent_for_task(task_type: str) -> str:
    """Map task type to agent name."""
    return {
        "code": "ia-fast",
        "analyse": "ia-deep",
        "trading": "ia-trading",
        "systeme": "ia-system",
        "web": "ia-bridge",
        "simple": "ia-fast",
        "architecture": "ia-bridge",
        "consensus": "ia-consensus",
    }.get(task_type, "ia-fast")
