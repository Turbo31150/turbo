"""Chat route — AI conversation via Claude SDK + Commander pipeline + MAO consensus."""
import asyncio
import json
import os
import time
import traceback
from typing import Any

# Try to import src modules
try:
    from src.config import config as jarvis_config
except ImportError:
    jarvis_config = None

try:
    from src.commander import classify_task, decompose_task, build_commander_enrichment
except ImportError:
    classify_task = None
    decompose_task = None
    build_commander_enrichment = None


class ChatSession:
    """Manages a chat conversation."""

    def __init__(self):
        self.messages: list[dict] = []
        self.active = False

    def add_message(self, role: str, content: str, agent: str | None = None,
                    tool_calls: list | None = None) -> dict:
        msg = {
            "id": f"msg_{len(self.messages)}_{int(time.time()*1000)}",
            "role": role,
            "content": content,
            "agent": agent,
            "tool_calls": tool_calls or [],
            "timestamp": time.time(),
        }
        self.messages.append(msg)
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
                import inspect
                if inspect.iscoroutinefunction(classify_task):
                    task_type = await classify_task(text)
                else:
                    task_type = await asyncio.to_thread(classify_task, text)
                if not isinstance(task_type, str):
                    task_type = "simple"
            except Exception:
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
    except Exception as e:
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
    except Exception:
        return None

    cmd = result.get("command")
    confidence = result.get("confidence", 0)
    params = result.get("params", {})

    if not cmd or confidence < 0.75:
        return None

    # Execute the command
    try:
        output = await execute_command(cmd, params)
    except Exception as e:
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
            # Strip [M1]/[OL1] tags from history to avoid confusing the model
            clean = content
            for tag in ("[M1] ", "[OL1] ", "[M2] ", "[M3] ", "[GEMINI] ", "[CLAUDE] ", "[GPT-OSS] ", "[DEVSTRAL-2] ", "[GLM-4] ", "[MINIMAX-M2] ", "[QWEN3] "):
                if clean.startswith(tag):
                    clean = clean[len(tag):]
            history.append({"role": "assistant", "content": clean})
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
            clean = content
            for tag in ("[M1] ", "[OL1] ", "[M2] ", "[M3] ", "[GEMINI] ", "[CLAUDE] ", "[GPT-OSS] ", "[DEVSTRAL-2] ", "[GLM-4] ", "[MINIMAX-M2] ", "[QWEN3] "):
                if clean.startswith(tag):
                    clean = clean[len(tag):]
            parts.append(f"\nJARVIS: {clean}")
    parts.append(f"\nUtilisateur: {current_text}")
    return "\n".join(parts)


## All available models with metadata for the frontend
ALL_MODELS = [
    {"id": "gpt-oss:120b-cloud", "name": "gpt-oss 120B", "group": "cloud", "score": 100, "weight": 1.9,
     "url": "http://127.0.0.1:11434/api/chat", "backend": "ollama", "speed": "51 tok/s"},
    {"id": "qwen3-8b", "name": "M1 / qwen3-8b", "group": "local", "score": 98, "weight": 1.8,
     "url": "http://127.0.0.1:1234/api/v1/chat", "backend": "lmstudio", "speed": "45 tok/s"},
    {"id": "devstral-2:123b-cloud", "name": "devstral-2 123B", "group": "cloud", "score": 94, "weight": 1.5,
     "url": "http://127.0.0.1:11434/api/chat", "backend": "ollama", "speed": "36 tok/s"},
    {"id": "deepseek-coder-v2-lite-instruct", "name": "M2 / deepseek-coder", "group": "local", "score": 85, "weight": 1.4,
     "url": "http://192.168.1.26:1234/api/v1/chat", "backend": "lmstudio",
     "auth": "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4", "speed": "15 tok/s"},
    {"id": "qwen3:1.7b", "name": "OL1 / qwen3 1.7B", "group": "local", "score": 88, "weight": 1.3,
     "url": "http://127.0.0.1:11434/api/chat", "backend": "ollama", "speed": "84 tok/s"},
    {"id": "glm-4.7:cloud", "name": "GLM 4.7", "group": "cloud", "score": 88, "weight": 1.2,
     "url": "http://127.0.0.1:11434/api/chat", "backend": "ollama", "speed": "48 tok/s"},
    {"id": "minimax-m2.5:cloud", "name": "Minimax (web)", "group": "cloud", "score": 80, "weight": 1.0,
     "url": "http://127.0.0.1:11434/api/chat", "backend": "ollama", "speed": "var"},
    {"id": "mistral-7b-instruct-v0.3", "name": "M3 / mistral-7b", "group": "local", "score": 89, "weight": 0.8,
     "url": "http://192.168.1.113:1234/api/v1/chat", "backend": "lmstudio",
     "auth": "Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux", "speed": "10 tok/s"},
    # Proxy backends (subprocess node)
    {"id": "gemini-3-pro", "name": "GEMINI / gemini-3-pro", "group": "proxy", "score": 74, "weight": 1.2,
     "backend": "proxy", "proxy_path": "F:/BUREAU/turbo/gemini-proxy.js", "speed": "var"},
    {"id": "claude-opus", "name": "CLAUDE / opus", "group": "proxy", "score": 85, "weight": 1.2,
     "backend": "proxy", "proxy_path": "F:/BUREAU/turbo/claude-proxy.js", "speed": "var"},
]

# Health cache for models (refreshed every 30s)
_model_health: dict[str, bool] = {}
_health_ts: float = 0


async def _query_proxy(proxy_path: str, prompt: str, timeout: float = 120.0) -> str | None:
    """Query GEMINI or CLAUDE via their Node.js proxy subprocess."""
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
        try:
            proc.kill()
        except Exception:
            pass
    except Exception:
        pass
    return None


async def check_models_health() -> dict:
    """Health check all models, return status dict."""
    import httpx
    global _model_health, _health_ts
    now = time.time()
    if now - _health_ts < 30:
        return _model_health

    results = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for m in ALL_MODELS:
            try:
                if m["backend"] == "proxy":
                    # Proxy health: check if proxy JS file exists
                    results[m["id"]] = os.path.isfile(m.get("proxy_path", ""))
                elif m["backend"] == "ollama":
                    r = await client.get("http://127.0.0.1:11434/api/tags")
                    results[m["id"]] = r.status_code == 200
                else:
                    url = m["url"].replace("/api/v1/chat", "/api/v1/models")
                    headers = {}
                    if m.get("auth"):
                        headers["Authorization"] = m["auth"]
                    r = await client.get(url, headers=headers)
                    results[m["id"]] = r.status_code == 200
            except Exception:
                results[m["id"]] = False
    _model_health = results
    _health_ts = now
    return results


async def get_models_with_status() -> list[dict]:
    """Return all models with online/offline status."""
    health = await check_models_health()
    return [
        {**{k: v for k, v in m.items() if k not in ("url", "auth", "backend", "proxy_path")},
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
    import httpx

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
        if m.get("auth"):
            node["auth"] = m["auth"]
        nodes_priority.append(node)

    # Build conversation history with memory
    chat_messages = _build_chat_history(text)
    lmstudio_input = _build_lmstudio_input(text)

    async with httpx.AsyncClient(timeout=60.0) as client:
        for node in nodes_priority:
            try:
                if node["backend"] == "proxy":
                    # GEMINI / CLAUDE via subprocess proxy
                    result = await _query_proxy(node["proxy_path"], text, timeout=60.0)
                    if result:
                        return f"[{node['name']}] {result}"
                elif node["backend"] == "ollama":
                    # think:false obligatoire pour cloud models
                    ollama_payload = {
                        "model": node["model"],
                        "messages": chat_messages,
                        "stream": False,
                        "think": False,
                    }
                    resp = await client.post(node["url"], json=ollama_payload)
                    data = resp.json()
                    content = data.get("message", {}).get("content", "")
                    if content and content.strip():
                        return f"[{node['name']}] {content.strip()}"
                else:
                    headers = {"Content-Type": "application/json"}
                    if node.get("auth"):
                        headers["Authorization"] = node["auth"]
                    resp = await client.post(node["url"], headers=headers, json={
                        "model": node["model"],
                        "input": lmstudio_input,
                        "temperature": 0.3,
                        "max_output_tokens": 512,
                        "stream": False,
                        "store": False,
                    })
                    data = resp.json()
                    if data.get("error"):
                        continue
                    # LM Studio: output[].content is string or content[].text
                    for item in reversed(data.get("output", [])):
                        if isinstance(item, dict) and item.get("type") == "message":
                            c = item.get("content", "")
                            if isinstance(c, str) and c.strip():
                                return f"[{node['name']}] {c.strip()}"
                            if isinstance(c, list):
                                for part in c:
                                    if isinstance(part, dict) and part.get("text", "").strip():
                                        return f"[{node['name']}] {part['text'].strip()}"
            except Exception:
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
    import httpx
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

        async with httpx.AsyncClient(timeout=60.0) as client:
            if m["backend"] == "ollama":
                resp = await client.post(m["url"], json={
                    "model": model_id, "messages": chat_messages,
                    "stream": False, "think": False,
                })
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                if content and content.strip():
                    return {"model": model_id, "name": name, "content": content.strip(), "latency": round(time.time() - start, 2)}
            else:
                headers = {"Content-Type": "application/json"}
                if m.get("auth"):
                    headers["Authorization"] = m["auth"]
                resp = await client.post(m["url"], headers=headers, json={
                    "model": model_id, "input": lmstudio_input,
                    "temperature": 0.3, "max_output_tokens": 512,
                    "stream": False, "store": False,
                })
                data = resp.json()
                for item in reversed(data.get("output", [])):
                    if isinstance(item, dict) and item.get("type") == "message":
                        c = item.get("content", "")
                        if isinstance(c, str) and c.strip():
                            return {"model": model_id, "name": name, "content": c.strip(), "latency": round(time.time() - start, 2)}
                        if isinstance(c, list):
                            for part in c:
                                if isinstance(part, dict) and part.get("text", "").strip():
                                    return {"model": model_id, "name": name, "content": part["text"].strip(), "latency": round(time.time() - start, 2)}
    except Exception as e:
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
