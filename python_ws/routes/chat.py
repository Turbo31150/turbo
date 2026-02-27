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
    """Process a user message: try command execution first, fallback to IA."""
    text = (payload.get("content") or payload.get("text") or "").strip()
    if not text:
        return {"error": "Empty message"}

    # Add user message
    user_msg = _session.add_message("user", text)

    start = time.time()

    try:
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
            for tag in ("[M1] ", "[OL1] ", "[M2] ", "[M3] ", "[GEMINI] "):
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
            for tag in ("[M1] ", "[OL1] ", "[M2] ", "[M3] ", "[GEMINI] "):
                if clean.startswith(tag):
                    clean = clean[len(tag):]
            parts.append(f"\nJARVIS: {clean}")
    parts.append(f"\nUtilisateur: {current_text}")
    return "\n".join(parts)


async def _query_local_ia(text: str, task_type: str) -> str:
    """Query local IA nodes for a response."""
    import httpx

    # Route: M1 priority, fallback OL1, then M2
    nodes_priority = [
        {
            "name": "M1", "url": "http://10.5.0.2:1234/api/v1/chat",
            "backend": "lmstudio", "model": "qwen3-8b",
            "auth": "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
        },
        {
            "name": "OL1", "url": "http://127.0.0.1:11434/api/chat",
            "backend": "ollama", "model": "qwen3:1.7b",
        },
        {
            "name": "M2", "url": "http://192.168.1.26:1234/api/v1/chat",
            "backend": "lmstudio", "model": "deepseek-coder-v2-lite-instruct",
            "auth": "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4",
        },
    ]

    if task_type == "web":
        nodes_priority.insert(0, {
            "name": "OL1-cloud", "url": "http://127.0.0.1:11434/api/chat",
            "backend": "ollama", "model": "minimax-m2.5:cloud",
        })

    # Build conversation history with memory
    chat_messages = _build_chat_history(text)
    lmstudio_input = _build_lmstudio_input(text)

    async with httpx.AsyncClient(timeout=30.0) as client:
        for node in nodes_priority:
            try:
                if node["backend"] == "ollama":
                    resp = await client.post(node["url"], json={
                        "model": node["model"],
                        "messages": chat_messages,
                        "stream": False,
                        "think": False,
                    })
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
