"""Chat route — AI conversation via Claude SDK + Commander pipeline."""
import asyncio
import json
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
    """Process a user message through the commander pipeline."""
    text = (payload.get("content") or payload.get("text") or "").strip()
    if not text:
        return {"error": "Empty message"}

    # Add user message
    user_msg = _session.add_message("user", text)

    start = time.time()

    try:
        # Step 1: Classify task (if commander available)
        task_type = "simple"
        if classify_task:
            try:
                import inspect
                if inspect.iscoroutinefunction(classify_task):
                    task_type = await classify_task(text)
                else:
                    task_type = await asyncio.to_thread(classify_task, text)
                # Ensure task_type is a string
                if not isinstance(task_type, str):
                    task_type = "simple"
            except Exception:
                task_type = "simple"

        # Step 2: For now, use a simple local IA query as response
        # In production this would use Claude SDK streaming
        response_text = await _query_local_ia(text, task_type)

        agent_name = _get_agent_for_task(task_type)
        elapsed = time.time() - start

        # Add agent response
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


async def _query_local_ia(text: str, task_type: str) -> str:
    """Query local IA nodes for a response."""
    import httpx

    # Route to best node based on task type
    nodes_config = {
        "simple": ("http://127.0.0.1:11434/api/chat", "ollama", "qwen3:1.7b"),
        "code": ("http://192.168.1.26:1234/api/v1/chat", "lmstudio", "deepseek-coder-v2-lite-instruct"),
        "analyse": ("http://192.168.1.26:1234/api/v1/chat", "lmstudio", "deepseek-coder-v2-lite-instruct"),
        "trading": ("http://127.0.0.1:11434/api/chat", "ollama", "qwen3:1.7b"),
        "web": ("http://127.0.0.1:11434/api/chat", "ollama", "minimax-m2.5:cloud"),
    }

    url, backend, model = nodes_config.get(task_type, nodes_config["simple"])

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            if backend == "ollama":
                resp = await client.post(url, json={
                    "model": model,
                    "messages": [{"role": "user", "content": text}],
                    "stream": False,
                    "think": False,
                })
                data = resp.json()
                return data.get("message", {}).get("content", "Pas de reponse")
            else:
                headers = {"Content-Type": "application/json"}
                if "192.168.1.26" in url:
                    headers["Authorization"] = "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4"
                resp = await client.post(url, headers=headers, json={
                    "model": model,
                    "input": text,
                    "temperature": 0.3,
                    "max_output_tokens": 4096,
                    "stream": False,
                    "store": False,
                })
                data = resp.json()
                # Extract from LM Studio response
                output = data.get("output", [])
                if isinstance(output, list):
                    for item in output:
                        if isinstance(item, dict) and item.get("content"):
                            return item["content"]
                return str(output) if output else "Pas de reponse"
        except Exception as e:
            return f"[Erreur IA] {e}"


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
