"""Chat route — AI conversation via Claude SDK + Commander pipeline + MAO consensus.

v2: Message persistence, request tracing, session recovery.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import sqlite3
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import httpx

from python_ws.helpers import strip_agent_tag, extract_lmstudio_content

logger = logging.getLogger("jarvis.chat")

# Shared httpx client — avoids TCP reconnect overhead per request
_http: httpx.AsyncClient | None = None
_http_lock = asyncio.Lock()


async def _get_http() -> httpx.AsyncClient:
    global _http
    if _http is not None and not _http.is_closed:
        return _http
    async with _http_lock:
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
    """Manages a chat conversation with bounded history + SQLite persistence."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        self.messages: list[dict] = []
        self.active = False
        self._db_path = _TURBO_ROOT / "data" / "jarvis.db"
        self._ensure_table()
        self._restore_from_db()

    def _ensure_table(self):
        """Create chat_history table if it doesn't exist."""
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("""CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                agent TEXT,
                model TEXT,
                latency_ms REAL DEFAULT 0,
                tokens INTEGER DEFAULT 0,
                timestamp REAL NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_ts ON chat_history(timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id)")
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.debug("chat_history table creation failed: %s", e)

    def _restore_from_db(self):
        """Restore last session messages from SQLite on startup."""
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, content, agent, model, latency_ms, timestamp FROM chat_history "
                "ORDER BY timestamp DESC LIMIT ?", (MAX_SESSION_MESSAGES,)
            ).fetchall()
            conn.close()
            if rows:
                self.messages = [
                    {"id": f"msg_restored_{i}", "role": r["role"],
                     "content": r["content"], "agent": r["agent"],
                     "tool_calls": [], "timestamp": r["timestamp"]}
                    for i, r in enumerate(reversed(rows))
                ]
                logger.info("Restored %d messages from DB", len(self.messages))
        except (sqlite3.Error, OSError) as e:
            logger.debug("Chat history restore failed (table may not exist yet): %s", e)

    def _persist(self, msg: dict, model: str | None = None, latency_ms: float = 0, tokens: int = 0):
        """Persist message to SQLite + conversation checkpoint (non-blocking best-effort)."""
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute(
                "INSERT INTO chat_history (session_id, role, content, agent, model, latency_ms, tokens, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (self.session_id, msg["role"], msg["content"], msg.get("agent"),
                 model, latency_ms, tokens, msg["timestamp"]),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.debug("Chat persist failed: %s", e)
        # Also checkpoint for cross-restart continuity
        try:
            _cp_db_path = _TURBO_ROOT / "data" / "conversation_checkpoints.db"
            cp = sqlite3.connect(str(_cp_db_path), timeout=5)
            cp.execute("PRAGMA journal_mode=WAL")
            cp.execute("""CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL, turn_index INTEGER NOT NULL,
                timestamp TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
                token_estimate INTEGER DEFAULT 0, source TEXT DEFAULT 'ws', metadata TEXT)""")
            cp.execute("""CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                last_active TEXT NOT NULL, turn_count INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0, source TEXT DEFAULT 'ws', metadata TEXT)""")
            now = datetime.now().isoformat()
            row = cp.execute("SELECT MAX(turn_index) FROM checkpoints WHERE session_id=?",
                             (self.session_id,)).fetchone()
            turn_idx = (row[0] or 0) + 1
            token_est = len(msg["content"]) // 4
            cp.execute("INSERT INTO checkpoints (session_id, turn_index, timestamp, role, content, token_estimate, source) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (self.session_id, turn_idx, now, msg["role"], msg["content"][:10000], token_est, "ws"))
            cp.execute("""INSERT INTO sessions (session_id, created_at, last_active, turn_count, total_tokens, source)
                VALUES (?, ?, ?, 1, ?, 'ws') ON CONFLICT(session_id) DO UPDATE SET
                last_active=excluded.last_active, turn_count=turn_count+1,
                total_tokens=total_tokens+excluded.total_tokens""",
                       (self.session_id, now, now, token_est))
            cp.commit()
            cp.close()
        except Exception:
            pass  # Best-effort, never block chat

    def add_message(self, role: str, content: str, agent: str | None = None,
                    tool_calls: list | None = None, model: str | None = None,
                    latency_ms: float = 0, tokens: int = 0) -> dict:
        msg = {
            "id": f"msg_{len(self.messages)}_{int(time.time()*1000)}",
            "role": role,
            "content": content[:MAX_MESSAGE_LENGTH],
            "agent": agent,
            "tool_calls": tool_calls or [],
            "timestamp": time.time(),
        }
        self.messages.append(msg)
        if len(self.messages) > MAX_SESSION_MESSAGES:
            self.messages = self.messages[-MAX_SESSION_MESSAGES:]
        self._persist(msg, model=model, latency_ms=latency_ms, tokens=tokens)
        return msg

    def clear(self):
        self.messages.clear()

    def get_session_stats(self) -> dict:
        user_msgs = sum(1 for m in self.messages if m["role"] == "user")
        return {
            "session_id": self.session_id,
            "total_messages": len(self.messages),
            "user_messages": user_msgs,
            "assistant_messages": len(self.messages) - user_msgs,
        }


_session = ChatSession()


def new_request_id() -> str:
    """Generate a correlation ID for request tracing."""
    return f"req_{uuid.uuid4().hex[:8]}"


async def handle_chat_request(action: str, payload: dict) -> dict:
    """Handle chat channel requests."""
    if action == "send_message":
        return await _send_message(payload)
    elif action == "clear_conversation":
        _session.clear()
        return {"cleared": True}
    elif action == "get_history":
        return {"messages": _session.messages}
    elif action == "get_session_stats":
        return _session.get_session_stats()
    elif action == "search_history":
        return _search_chat_history(payload.get("query", ""), payload.get("limit", 50))
    return {"error": f"Unknown chat action: {action}"}


async def _send_message(payload: dict) -> dict:
    """Process a user message: try command execution first, fallback to IA."""
    text = (payload.get("content") or payload.get("text") or "").strip()
    if not text:
        return {"error": "Empty message"}
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH]

    request_id = new_request_id()

    # Add user message
    user_msg = _session.add_message("user", text)
    user_msg["request_id"] = request_id

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
        # Skip command matching for natural questions (interrogative sentences)
        _is_question = any(text.lower().startswith(w) for w in (
            "quel", "quels", "quelle", "quelles", "comment", "pourquoi",
            "est-ce", "y a-t-il", "peux-tu", "pourrais-tu", "donne-moi",
            "dis-moi", "explique", "decris", "combien", "ou ", "quand",
            "qui ", "que ", "?",
        ))
        cmd_result = None if _is_question else await _try_execute_command(text)
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
    "Si tu as des tools disponibles, utilise-les pour obtenir des donnees reelles "
    "avant de repondre (ex: statut cluster, diagnostics, alertes). "
    "Reponds toujours en francais."
)

# Task types that benefit from IA tools (system interaction)
# "simple" included because even simple queries may need system data;
# tools are only injected for LM Studio backends (not Ollama)
_TOOL_TASK_TYPES = {"systeme", "architecture", "analyse", "consensus", "code", "simple"}


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
    {"id": "qwen3-8b", "name": "M1 / qwen3-8b", "group": "local", "score": 98, "weight": 1.8,
     "url": _M1_CHAT, "backend": "lmstudio", "speed": "45 tok/s"},
    {"id": "deepseek-r1-0528-qwen3-8b", "name": "M2 / deepseek-r1", "group": "local", "score": 85, "weight": 1.5,
     "url": _M2_CHAT, "backend": "lmstudio",
     "auth_node": "M2", "speed": "44 tok/s"},
    {"id": "qwen3:1.7b", "name": "OL1 / qwen3 1.7B", "group": "local", "score": 88, "weight": 1.3,
     "url": _OLLAMA_CHAT, "backend": "ollama", "speed": "84 tok/s"},
    {"id": "deepseek-r1-0528-qwen3-8b-m3", "name": "M3 / deepseek-r1", "group": "local", "score": 80, "weight": 1.2,
     "url": _M3_CHAT, "backend": "lmstudio",
     "auth_node": "M3", "speed": "33 tok/s"},
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
        client = await _get_http()
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
    "code":         ["qwen3-8b", "deepseek-r1-0528-qwen3-8b", "qwen3:1.7b"],
    "analyse":      ["qwen3-8b", "deepseek-r1-0528-qwen3-8b", "qwen3:1.7b"],
    "architecture": ["qwen3-8b", "qwen3:1.7b", "deepseek-r1-0528-qwen3-8b"],
    "trading":      ["qwen3:1.7b", "qwen3-8b", "deepseek-r1-0528-qwen3-8b"],
    "web":          ["qwen3:1.7b", "qwen3-8b"],
    "systeme":      ["qwen3-8b", "qwen3:1.7b"],
    "consensus":    ["qwen3-8b", "deepseek-r1-0528-qwen3-8b", "qwen3:1.7b"],
    "simple":       ["qwen3:1.7b", "qwen3-8b"],
}


async def _query_local_ia(text: str, task_type: str) -> str:
    """Query IA nodes for a response using full routing matrix.

    v4: Injects IA tools for system-related queries so models can call
    JARVIS endpoints (diagnostics, cluster health, etc.) before responding.
    """

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

    # Load tools for system-related queries
    # M1 (qwen3-8b): full system scope (18 tools) — capable model
    # OL1 (qwen3:1.7b): minimal scope (4 tools) — smaller model
    ia_tools = None
    ia_tools_minimal = None
    if task_type in _TOOL_TASK_TYPES:
        try:
            from src.ia_tools import get_tools_for_scope
            ia_tools = get_tools_for_scope("system")       # 18 tools for M1
            ia_tools_minimal = get_tools_for_scope("minimal")  # 4 tools for OL1
        except ImportError:
            ia_tools = None
            ia_tools_minimal = None

    client = await _get_http()
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
                # Inject minimal tools for Ollama (smaller model = fewer tools)
                if ia_tools_minimal:
                    ol_payload["tools"] = ia_tools_minimal
                resp = await client.post(node["url"], json=ol_payload)
                resp.raise_for_status()
                ol_data = resp.json()
                ol_msg = ol_data.get("message", {})
                # Check for tool_calls
                if ol_msg.get("tool_calls"):
                    tool_result = await _handle_ollama_tool_calls(
                        ol_msg["tool_calls"], node, chat_messages, ol_payload, client,
                    )
                    if tool_result:
                        return f"[{node['name']}] {tool_result}"
                content = (ol_msg.get("content") or "").strip()
                if content:
                    return f"[{node['name']}] {content}"
            else:
                headers = {"Content-Type": "application/json"}
                if node.get("auth"):
                    headers["Authorization"] = node["auth"]
                # Use Chat Completions API when tools are available (Responses API doesn't support tools)
                if ia_tools and node["backend"] == "lmstudio":
                    cc_url = node["url"].replace("/api/v1/chat", "/v1/chat/completions")
                    cc_payload = {
                        "model": node["model"],
                        "messages": chat_messages,
                        "temperature": 0.3,
                        "max_tokens": 512,
                        "stream": False,
                        "tools": ia_tools,
                    }
                    resp = await client.post(cc_url, headers=headers, json=cc_payload)
                    resp.raise_for_status()
                    data = resp.json()
                    choice = (data.get("choices") or [{}])[0]
                    msg = choice.get("message", {})
                    # Check for tool_calls
                    if msg.get("tool_calls"):
                        tool_result = await _handle_tool_calls_cc(
                            msg["tool_calls"], node, headers, cc_url, chat_messages, client,
                        )
                        if tool_result:
                            return f"[{node['name']}] {tool_result}"
                    # Normal text response
                    content = (msg.get("content") or "").strip()
                    if content:
                        return f"[{node['name']}] {content}"
                else:
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


async def _handle_tool_calls_cc(
    tool_calls: list[dict],
    node: dict,
    headers: dict,
    cc_url: str,
    chat_messages: list[dict],
    client: httpx.AsyncClient,
) -> str | None:
    """Process tool_calls from Chat Completions response and loop back for final answer.

    Uses the standard OpenAI tool_calls flow:
    1. Execute each tool call via ia_tool_executor
    2. Append assistant message (with tool_calls) + tool results to conversation
    3. Re-query model WITHOUT tools to get final text response
    """
    logger.info("Tool calls from %s: %s", node.get("name", "?"),
                [tc.get("function", {}).get("name", "?") for tc in tool_calls])

    try:
        from src.ia_tool_executor import process_model_tool_calls
    except ImportError:
        logger.warning("ia_tool_executor not available, skipping tool calls")
        return None

    caller = node.get("name", "unknown")
    results = await process_model_tool_calls(tool_calls, caller=caller)

    # Build follow-up conversation with tool results (standard OpenAI format)
    follow_up_messages = list(chat_messages)
    # Add assistant message with tool_calls
    follow_up_messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": tool_calls,
    })
    # Add tool results
    for r in results:
        follow_up_messages.append({
            "role": "tool",
            "tool_call_id": r["tool_call_id"],
            "content": r["content"][:2000],
        })

    # Re-query WITHOUT tools to get final text response (prevents infinite loop)
    follow_up_payload = {
        "model": node.get("model", "qwen3-8b"),
        "messages": follow_up_messages,
        "temperature": 0.3,
        "max_tokens": 512,
        "stream": False,
    }

    try:
        resp = await client.post(cc_url, headers=headers, json=follow_up_payload)
        resp.raise_for_status()
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message", {}).get("content") or "").strip()
        if content:
            return content
    except (httpx.HTTPError, asyncio.TimeoutError, OSError) as exc:
        logger.debug("Tool follow-up failed for %s: %s", caller, exc)

    # Fallback: summarize tool results directly
    summary = "; ".join(r["content"][:200] for r in results)
    return f"[tools] {summary[:500]}"


async def _handle_ollama_tool_calls(
    tool_calls: list[dict],
    node: dict,
    chat_messages: list[dict],
    original_payload: dict,
    client: httpx.AsyncClient,
) -> str | None:
    """Process tool_calls from Ollama response and loop back for final answer.

    Ollama tool_calls format: [{"id": "...", "function": {"name": "...", "arguments": {...}}}]
    """
    # Normalize Ollama tool_calls to OpenAI format for process_model_tool_calls
    normalized = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        args = fn.get("arguments", {})
        # Ollama returns arguments as dict, process_model_tool_calls expects str or dict
        normalized.append({
            "id": tc.get("id", ""),
            "function": {
                "name": fn.get("name", ""),
                "arguments": args if isinstance(args, str) else json.dumps(args, ensure_ascii=False),
            },
        })

    logger.info("Ollama tool calls from %s: %s", node.get("name", "?"),
                [tc["function"]["name"] for tc in normalized])

    try:
        from src.ia_tool_executor import process_model_tool_calls
    except ImportError:
        return None

    caller = node.get("name", "unknown")
    results = await process_model_tool_calls(normalized, caller=caller)

    # Build follow-up with tool results for Ollama
    follow_up_messages = list(chat_messages)
    follow_up_messages.append({
        "role": "assistant",
        "content": "",
        "tool_calls": tool_calls,  # Ollama native format
    })
    for r in results:
        follow_up_messages.append({
            "role": "tool",
            "content": r["content"][:2000],
        })

    # Re-query WITHOUT tools
    follow_up_payload = {
        "model": original_payload.get("model", node.get("model", "qwen3:1.7b")),
        "messages": follow_up_messages,
        "stream": False,
        "think": False,
    }

    try:
        resp = await client.post(node["url"], json=follow_up_payload)
        resp.raise_for_status()
        content = (resp.json().get("message", {}).get("content") or "").strip()
        if content:
            return content
    except (httpx.HTTPError, asyncio.TimeoutError, OSError) as exc:
        logger.debug("Ollama tool follow-up failed for %s: %s", caller, exc)

    summary = "; ".join(r["content"][:200] for r in results)
    return f"[tools] {summary[:500]}"


# Consensus models: all agents dispatched in parallel for weighted vote
CONSENSUS_MODELS = [
    "qwen3-8b", "deepseek-r1-0528-qwen3-8b", "qwen3:1.7b",
    "deepseek-r1-0528-qwen3-8b-m3",
]

# Weights for consensus vote (MaJ 2026-03-06)
CONSENSUS_WEIGHTS = {
    "qwen3-8b": 1.8,
    "deepseek-r1-0528-qwen3-8b": 1.5,
    "qwen3:1.7b": 1.3,
    "deepseek-r1-0528-qwen3-8b-m3": 1.2,
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

        client = await _get_http()
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
    """Dispatch to agents in parallel, synthesize with weighted vote.

    v2: Uses orchestrator_v2 to dynamically select best nodes and record metrics.
    Falls back to CONSENSUS_MODELS if orchestrator unavailable.
    """
    import time as _time
    chat_messages = _build_chat_history(text)
    lmstudio_input = _build_lmstudio_input(text)

    # v2: dynamically filter models via orchestrator_v2
    active_models = list(CONSENSUS_MODELS)
    try:
        from src.orchestrator_v2 import orchestrator_v2
        chain = orchestrator_v2.fallback_chain("code")
        # Map node names to model IDs for filtering
        node_to_model = {
            "M1": "qwen3-8b",
            "M2": "deepseek-r1-0528-qwen3-8b",
            "OL1": "qwen3:1.7b",
            "M3": "deepseek-r1-0528-qwen3-8b-m3",
        }
        # Prioritize models from fallback chain (degraded nodes moved to end)
        prioritized = [node_to_model[n] for n in chain if n in node_to_model]
        # Add any consensus models not in the chain
        remaining = [m for m in CONSENSUS_MODELS if m not in prioritized]
        active_models = prioritized + remaining
    except Exception:
        pass

    # Launch all consensus models in parallel
    tasks = [
        _query_single_node(mid, text, chat_messages, lmstudio_input)
        for mid in active_models
    ]
    t0 = _time.perf_counter()
    results = await asyncio.wait_for(
        asyncio.gather(*tasks, return_exceptions=True),
        timeout=60.0,
    )
    total_elapsed = (_time.perf_counter() - t0) * 1000

    # Collect successful responses
    responses = []
    errors = []
    for r in results:
        if isinstance(r, Exception):
            errors.append(str(r))
        elif isinstance(r, dict) and r.get("content"):
            responses.append(r)
            # v2: record success in orchestrator
            try:
                from src.orchestrator_v2 import orchestrator_v2
                lat = float(r.get("latency", 0)) * 1000
                orchestrator_v2.record_call(
                    r.get("name", "unknown"),
                    latency_ms=lat, success=True,
                    tokens=len(r.get("content", "")) // 4,
                )
            except Exception:
                pass
        elif isinstance(r, dict):
            errors.append(f"{r.get('name', '?')}: {r.get('error', '?')}")

    if not responses:
        return "CONSENSUS FAIL — Aucun agent n'a repondu."

    # Build weighted synthesis
    total_weight = sum(CONSENSUS_WEIGHTS.get(r["model"], 1.0) for r in responses)
    parts = [f"**CONSENSUS MAO v2** — {len(responses)}/{len(active_models)} agents, poids {total_weight:.1f}, {total_elapsed:.0f}ms\n"]

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


# ═══════════════════════════════════════════════════════════════════════════
# CHAT HISTORY SEARCH — Query persisted messages
# ═══════════════════════════════════════════════════════════════════════════

def _search_chat_history(query: str, limit: int = 50) -> dict:
    """Search persisted chat history by content (LIKE match)."""
    db_path = _TURBO_ROOT / "data" / "jarvis.db"
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT session_id, role, content, agent, model, latency_ms, timestamp "
            "FROM chat_history WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"%{query}%", min(limit, 200)),
        ).fetchall()
        conn.close()
        return {"results": [dict(r) for r in rows], "count": len(rows), "query": query}
    except sqlite3.Error as e:
        return {"error": str(e), "results": [], "count": 0}


def get_chat_export(session_id: str | None = None, limit: int = 500) -> list[dict]:
    """Export chat history as list of dicts (for backup/analysis)."""
    db_path = _TURBO_ROOT / "data" / "jarvis.db"
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        if session_id:
            rows = conn.execute(
                "SELECT * FROM chat_history WHERE session_id = ? ORDER BY timestamp LIMIT ?",
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM chat_history ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []
