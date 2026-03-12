"""JARVIS Telegram Production Pipeline v3 — Full Stack Integration.

Architecture:
  1. Keyword shortcuts (0.1ms) — bypass IA pour dominos/cowork/commandes directes
  2. intent_classifier (0.1ms) — 11 categories regex
  3. Smart Model Router — route vers le meilleur modele selon intent+complexite
  4. OpenClaw bridge — route vers agent specialise
  5. Telegram + Electron — reponse avec inline keyboards + actions

Models branches:
  - qwen3:1.7b (Ollama) — classify + reponses simples (200ms, 125 tok/s)
  - qwen3-8b (LM Studio) — code, debug (1s, 65 tok/s)
  - gpt-oss-20b (LM Studio) — analyse profonde (7s)
  - deepseek-r1 (LM Studio) — reasoning (5-15s)
  - qwq-32b (LM Studio) — math/logique (5-15s)
  - minimax-m2.5:cloud (Ollama) — web search (2s)
  - glm-5:cloud (Ollama) — generaliste cloud
  - kimi-k2.5:cloud (Ollama) — raisonnement cloud

Usage: uv run python scripts/telegram_live_pipeline.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# ── Setup ──
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(Path(_ROOT) / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("jarvis.pipeline")

# ── Import JARVIS modules ──
try:
    from src.intent_classifier import IntentClassifier
    _classifier = IntentClassifier()
    log.info("IntentClassifier loaded (11 categories)")
except Exception as e:
    log.warning(f"IntentClassifier unavailable: {e}")
    _classifier = None

try:
    from src.openclaw_bridge import OpenClawBridge
    _bridge = OpenClawBridge()
    log.info(f"OpenClaw bridge loaded ({len(_bridge.get_routing_table())} routes)")
except Exception as e:
    log.warning(f"OpenClaw bridge unavailable: {e}")
    _bridge = None

try:
    from src.domino_pipelines import DOMINO_PIPELINES, find_domino
    _dominos = DOMINO_PIPELINES
    log.info(f"Domino pipelines loaded ({len(_dominos)} pipelines)")
except Exception as e:
    log.warning(f"Domino pipelines unavailable: {e}")
    _dominos = []
    def find_domino(text): return None

# ── Config ──
TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT", "")
TG_API = f"https://api.telegram.org/bot{TG_TOKEN}"
OLLAMA = "http://127.0.0.1:11434"
LMSTUDIO = "http://127.0.0.1:1234"
WS = "http://127.0.0.1:9742"
ADMIN_USERS = {int(TG_CHAT)} if TG_CHAT else set()

# ── Model Registry ──
MODELS = {
    # Ollama local
    "qwen3:1.7b":       {"server": "ollama",   "speed": "fast",   "tok_s": 125, "ctx": 4096,  "for": ["classify", "simple", "quick"]},
    # Ollama cloud
    "minimax-m2.5:cloud":{"server": "ollama",   "speed": "medium", "tok_s": 40,  "ctx": 4096,  "for": ["web", "search", "news"]},
    "glm-5:cloud":       {"server": "ollama",   "speed": "medium", "tok_s": 30,  "ctx": 4096,  "for": ["general", "creative"]},
    "kimi-k2.5:cloud":   {"server": "ollama",   "speed": "medium", "tok_s": 30,  "ctx": 4096,  "for": ["reasoning", "analysis"]},
    # LM Studio
    "qwen3-8b":          {"server": "lmstudio", "speed": "fast",   "tok_s": 65,  "ctx": 32768, "for": ["code", "debug", "general"]},
    "gpt-oss-20b":       {"server": "lmstudio", "speed": "slow",   "tok_s": 20,  "ctx": 51899, "for": ["deep", "architecture", "complex"]},
    "deepseek-r1-0528-qwen3-8b": {"server": "lmstudio", "speed": "slow", "tok_s": 10, "ctx": 27000, "for": ["reasoning", "math", "logic"]},
    "qwq-32b":           {"server": "lmstudio", "speed": "slow",   "tok_s": 8,   "ctx": 32768, "for": ["math", "reasoning", "logic"]},
    "qwen3-coder-30b-a3b-instruct": {"server": "lmstudio", "speed": "slow", "tok_s": 9, "ctx": 32768, "for": ["code", "refactor", "architecture"]},
}

# ── Intent → Model routing ──
INTENT_MODEL_MAP = {
    "code_dev":        "qwen3-8b",
    "code":            "qwen3-8b",
    "debug":           "qwen3-8b",
    "trading":         "minimax-m2.5:cloud",
    "trading_scan":    "minimax-m2.5:cloud",
    "cluster_ops":     "qwen3:1.7b",
    "system_control":  "qwen3:1.7b",
    "voice_control":   "qwen3:1.7b",
    "navigation":      "qwen3:1.7b",
    "app_launch":      "qwen3:1.7b",
    "file_ops":        "qwen3:1.7b",
    "query":           "qwen3:1.7b",
    "pipeline":        "qwen3:1.7b",
    "web":             "minimax-m2.5:cloud",
    "search":          "minimax-m2.5:cloud",
    "research":        "minimax-m2.5:cloud",
    "architecture":    "gpt-oss-20b",
    "reasoning":       "deepseek-r1-0528-qwen3-8b",
    "math":            "qwq-32b",
    "consensus":       "gpt-oss-20b",
    "creative":        "glm-5:cloud",
}

# ── Complexity escalation keywords ──
ESCALATION_KEYWORDS = {
    "gpt-oss-20b": ["explique en detail", "architecture", "analyse approfondie", "compare en profondeur",
                     "audit complet", "strategie globale", "consensus", "refactoring majeur"],
    "deepseek-r1-0528-qwen3-8b": ["raisonne", "prouve", "demontre", "logiquement", "mathematiquement",
                                    "step by step", "etape par etape"],
    "qwq-32b": ["calcule", "equation", "probabilite", "statistique", "formule", "algorithme complexe"],
}

# ── Keyword shortcuts (bypass model — direct action) ──
KEYWORD_SHORTCUTS = {
    # System
    r"^(gpu|temperature|temp gpu)$": {"action": "powershell", "cmd": "nvidia-smi --query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader", "label": "GPU Status"},
    r"^(disk|espace disque|df)$": {"action": "powershell", "cmd": "Get-PSDrive -PSProvider FileSystem | Format-Table Name,@{n='Used(GB)';e={[math]::Round($_.Used/1GB,1)}},@{n='Free(GB)';e={[math]::Round($_.Free/1GB,1)}} -AutoSize", "label": "Espace disque"},
    r"^(ram|memoire|memory)$": {"action": "powershell", "cmd": "Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name,@{n='MB';e={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table -AutoSize", "label": "Top 10 RAM"},
    r"^(process|processus|ps)$": {"action": "powershell", "cmd": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name,CPU,@{n='MB';e={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table -AutoSize", "label": "Top 10 CPU"},
    r"^(ip|network|reseau)$": {"action": "powershell", "cmd": "Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne '127.0.0.1'} | Format-Table InterfaceAlias,IPAddress -AutoSize", "label": "IPs reseau"},
    r"^(uptime)$": {"action": "powershell", "cmd": "(Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime | Format-Table Days,Hours,Minutes -AutoSize", "label": "Uptime"},
    # Cluster
    r"^(cluster|status|health)$": {"action": "cluster_health", "label": "Cluster Health"},
    r"^(models|modeles)$": {"action": "list_models", "label": "Modeles charges"},
    # Cowork
    r"^cowork\s+(.+)$": {"action": "cowork", "label": "Cowork script"},
}

# ── Intent prompts per model ──
SYSTEM_PROMPTS = {
    "code":     "Expert code Python/JS/TS. Reponds avec code concis commente. Max 20 lignes. Francais.",
    "trading":  "Analyste crypto MEXC Futures. Signal: direction, entree, TP 0.4%, SL 0.25%. Donnees temps reel si possible.",
    "system":   "Admin systeme JARVIS/Windows. Commande exacte en ```block```. Bref.",
    "debug":    "Expert debug. Cause probable + solution en 3 etapes. Concis.",
    "question": "Assistant JARVIS. Reponse claire 3-5 lignes. Francais.",
    "web":      "Recherche web. Cite les sources. Resume les resultats cles.",
    "reasoning":"Raisonnement logique. Decompose etape par etape. Montre ton raisonnement.",
    "creative": "Brainstorming creatif. Propose 3 idees originales avec avantages.",
    "architecture": "Architecte logiciel. Diagramme + composants + flux de donnees. Concis.",
}

# ── Telegram action buttons per intent ──
INTENT_ACTIONS = {
    "code_dev": [[{"text": "Executer", "cb": "exec"}, {"text": "Expliquer", "cb": "explain"}, {"text": "Optimiser", "cb": "optimize"}]],
    "trading":  [[{"text": "Scanner", "cb": "scan"}, {"text": "Alerter", "cb": "alert"}], [{"text": "Backtest", "cb": "backtest"}, {"text": "Position", "cb": "possize"}]],
    "system_control": [[{"text": "Executer", "cb": "exec"}, {"text": "Monitor", "cb": "monitor"}], [{"text": "Logs", "cb": "logs"}, {"text": "Restart", "cb": "restart"}]],
    "debug":    [[{"text": "Diagnostiquer", "cb": "diag"}, {"text": "Auto-fix", "cb": "fix"}], [{"text": "Logs", "cb": "logs"}, {"text": "Escalader", "cb": "escalate"}]],
    "query":    [[{"text": "Approfondir", "cb": "deep"}, {"text": "Web search", "cb": "websearch"}]],
    "pipeline": [[{"text": "Executer pipeline", "cb": "run_pipeline"}, {"text": "Etapes", "cb": "show_steps"}]],
}

# ── State ──
_last_update_id = 0
_stats = {"received": 0, "processed": 0, "errors": 0, "start_time": 0,
          "models_used": {}, "intents_seen": {}, "shortcuts_used": 0,
          "dominos_triggered": 0, "total_classify_ms": 0, "total_generate_ms": 0}
_last_context: dict[int, dict] = {}
_last_alerts: set = set()


# ══════════════════════════════════════════════════════════════════
# TELEGRAM API
# ══════════════════════════════════════════════════════════════════

async def tg_call(client: httpx.AsyncClient, method: str, params: dict | None = None) -> dict:
    try:
        r = await client.post(f"{TG_API}/{method}", json=params or {}, timeout=30)
        return r.json()
    except Exception as e:
        log.error(f"TG API {method}: {e}")
        return {"ok": False, "error": str(e)}

async def tg_send(client: httpx.AsyncClient, chat_id: int | str, text: str,
                  keyboard: list | None = None, parse_mode: str = "Markdown") -> dict:
    params: dict = {"chat_id": chat_id, "text": text[:4096]}
    if parse_mode:
        params["parse_mode"] = parse_mode
    if keyboard:
        # Convert shorthand cb → callback_data
        converted = []
        for row in keyboard:
            converted_row = []
            for btn in row:
                b = dict(btn)
                if "cb" in b:
                    b["callback_data"] = b.pop("cb")
                converted_row.append(b)
            converted.append(converted_row)
        params["reply_markup"] = {"inline_keyboard": converted}
    return await tg_call(client, "sendMessage", params)

async def tg_answer_callback(client: httpx.AsyncClient, cb_id: str, text: str = ""):
    return await tg_call(client, "answerCallbackQuery",
                         {"callback_query_id": cb_id, "text": (text or "OK")[:200]})


# ══════════════════════════════════════════════════════════════════
# MODEL INFERENCE — ALL MODELS
# ══════════════════════════════════════════════════════════════════

async def call_ollama(client: httpx.AsyncClient, model: str, prompt: str,
                      system: str = "", max_tokens: int = 512) -> tuple[str, float]:
    """Call any Ollama model (local or cloud)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    # /nothink for local qwen, think:false for cloud
    is_cloud = "cloud" in model
    prefix = "" if is_cloud else "/nothink\n"
    messages.append({"role": "user", "content": f"{prefix}{prompt}"})

    t0 = time.perf_counter()
    resp = await client.post(f"{OLLAMA}/api/chat", json={
        "model": model, "messages": messages, "stream": False,
        "think": False, "options": {"num_predict": max_tokens, "num_ctx": 4096},
    }, timeout=60)
    ms = (time.perf_counter() - t0) * 1000
    return resp.json().get("message", {}).get("content", ""), ms

async def call_lmstudio(client: httpx.AsyncClient, model: str, prompt: str,
                        system: str = "", max_tokens: int = 512) -> tuple[str, float]:
    """Call any LM Studio model."""
    full_input = f"{system}\n\n{prompt}" if system else prompt
    # /nothink for qwen models only
    if "qwen" in model.lower() and "deepseek" not in model.lower():
        full_input = f"/nothink\n{full_input}"

    t0 = time.perf_counter()
    resp = await client.post(f"{LMSTUDIO}/api/v1/chat", json={
        "model": model, "input": full_input,
        "temperature": 0.3, "max_output_tokens": max_tokens,
        "stream": False, "store": False,
    }, timeout=90)
    ms = (time.perf_counter() - t0) * 1000
    data = resp.json()
    content = ""
    for o in reversed(data.get("output", [])):
        if o.get("type") == "message":
            content = o.get("content", "")
            break
    return content, ms

async def call_model(client: httpx.AsyncClient, model: str, prompt: str,
                     system: str = "", max_tokens: int = 512) -> tuple[str, float]:
    """Unified model call — routes to correct server."""
    info = MODELS.get(model, {})
    server = info.get("server", "ollama")
    try:
        if server == "lmstudio":
            return await call_lmstudio(client, model, prompt, system, max_tokens)
        else:
            return await call_ollama(client, model, prompt, system, max_tokens)
    except Exception as e:
        log.warning(f"Model {model} failed: {e}, falling back to qwen3:1.7b")
        return await call_ollama(client, "qwen3:1.7b", prompt, system, min(max_tokens, 256))


# ══════════════════════════════════════════════════════════════════
# SMART ROUTER
# ══════════════════════════════════════════════════════════════════

def select_model(text: str, intent: str) -> str:
    """Select best model based on intent + complexity keywords."""
    # Check escalation keywords
    text_lower = text.lower()
    for model, keywords in ESCALATION_KEYWORDS.items():
        if any(k in text_lower for k in keywords):
            log.info(f"  Escalation → {model}")
            return model

    # Long prompts → deeper model
    if len(text) > 300:
        return "gpt-oss-20b"

    # Intent-based routing
    return INTENT_MODEL_MAP.get(intent, "qwen3:1.7b")


def classify_intent(text: str) -> tuple[str, float]:
    """Classify using JARVIS intent_classifier or fallback."""
    if _classifier:
        result = _classifier.classify(text)
        return result.intent, result.confidence

    # Fallback: simple regex
    text_lower = text.lower()
    if any(k in text_lower for k in ["code", "fonction", "python", "debug", "bug", "erreur"]):
        return "code_dev", 0.8
    if any(k in text_lower for k in ["btc", "eth", "trading", "crypto", "signal", "scan"]):
        return "trading", 0.8
    if any(k in text_lower for k in ["gpu", "disk", "ram", "process", "service", "restart"]):
        return "system_control", 0.8
    if any(k in text_lower for k in ["pipeline", "domino", "sequence", "routine"]):
        return "pipeline", 0.8
    return "query", 0.5


# ══════════════════════════════════════════════════════════════════
# KEYWORD SHORTCUTS (BYPASS MODEL)
# ══════════════════════════════════════════════════════════════════

async def try_shortcut(client: httpx.AsyncClient, chat_id: int, text: str) -> bool:
    """Try keyword shortcuts. Returns True if handled."""
    text_clean = text.strip().lower()

    for pattern, config in KEYWORD_SHORTCUTS.items():
        m = re.match(pattern, text_clean, re.IGNORECASE)
        if not m:
            continue

        _stats["shortcuts_used"] += 1
        label = config.get("label", "Action")
        action = config["action"]
        log.info(f"  SHORTCUT [{label}]: {action}")

        if action == "powershell":
            try:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", config["cmd"]],
                    capture_output=True, text=True, timeout=15,
                )
                output = (result.stdout or result.stderr or "Pas de sortie").strip()
                await tg_send(client, chat_id, f"*{label}*\n```\n{output[:3500]}\n```")
            except Exception as e:
                await tg_send(client, chat_id, f"*{label}* Erreur: {e}", parse_mode=None)
            return True

        if action == "cluster_health":
            lines = ["*Cluster Health*\n"]
            checks = [
                ("M1 LM Studio", f"{LMSTUDIO}/v1/models"),
                ("OL1 Ollama", f"{OLLAMA}/api/tags"),
                ("WS 9742", f"{WS}/health"),
                ("OpenClaw", "http://127.0.0.1:18789/"),
                ("Canvas", "http://127.0.0.1:18800/"),
            ]
            for name, url in checks:
                try:
                    r = await client.get(url, timeout=3)
                    lines.append(f"`{name:15s}` UP ({r.status_code})")
                except Exception:
                    lines.append(f"`{name:15s}` DOWN")
            await tg_send(client, chat_id, "\n".join(lines))
            return True

        if action == "list_models":
            lines = ["*Modeles charges*\n", "*Ollama:*"]
            try:
                r = await client.get(f"{OLLAMA}/api/ps", timeout=3)
                for m in r.json().get("models", []):
                    lines.append(f"  `{m.get('name')}` ({m.get('size',0)/1e9:.1f}GB)")
            except Exception:
                lines.append("  Indisponible")
            lines.append("\n*LM Studio:*")
            try:
                r = await client.get(f"{LMSTUDIO}/v1/models", timeout=3)
                for m in r.json().get("data", [])[:10]:
                    lines.append(f"  `{m['id']}`")
                total = len(r.json().get("data", []))
                if total > 10:
                    lines.append(f"  _...et {total-10} autres_")
            except Exception:
                lines.append("  Indisponible")
            await tg_send(client, chat_id, "\n".join(lines))
            return True

        if action == "cowork":
            script_name = m.group(1) if m.lastindex else ""
            if script_name:
                await run_cowork(client, chat_id, script_name)
            return True

    # Check domino pipelines
    domino = find_domino(text_clean)
    if domino:
        _stats["dominos_triggered"] += 1
        log.info(f"  DOMINO: {domino.id} ({len(domino.steps)} steps)")
        steps_text = "\n".join(f"  {i+1}. `{s.action}` {s.description or ''}" for i, s in enumerate(domino.steps[:8]))
        await tg_send(client, chat_id,
            f"*Pipeline: {domino.id}*\n{domino.description}\n\n{steps_text}",
            keyboard=[[{"text": "Executer", "cb": f"domino_{domino.id}"},
                       {"text": "Annuler", "cb": "cancel"}]],
        )
        return True

    return False


async def run_cowork(client: httpx.AsyncClient, chat_id: int, script: str):
    """Execute a cowork script."""
    cowork_dir = Path(_ROOT) / "cowork" / "dev"
    # Find script
    matches = list(cowork_dir.glob(f"*{script}*.py"))
    if not matches:
        await tg_send(client, chat_id, f"Script cowork `{script}` non trouve.", parse_mode="Markdown")
        return
    script_path = matches[0]
    log.info(f"  COWORK: {script_path.name}")
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--once"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(_ROOT)),
        )
        output = (result.stdout or result.stderr or "Termine sans sortie").strip()
        await tg_send(client, chat_id, f"*Cowork: {script_path.name}*\n```\n{output[:3000]}\n```")
    except subprocess.TimeoutExpired:
        await tg_send(client, chat_id, f"*Cowork: {script_path.name}* — Timeout 30s")
    except Exception as e:
        await tg_send(client, chat_id, f"*Cowork error:* {e}", parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════
# MAIN MESSAGE HANDLER
# ══════════════════════════════════════════════════════════════════

async def handle_message(client: httpx.AsyncClient, message: dict):
    """Full JARVIS pipeline for one Telegram message."""
    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    user = message.get("from", {})
    username = user.get("username") or user.get("first_name", "?")

    if not text or not chat_id:
        return

    # ── Bot commands ──
    if text.startswith("/"):
        await handle_command(client, chat_id, text)
        return

    _stats["received"] += 1
    log.info(f"[{username}] {text[:80]}")

    # ── Step 1: Keyword shortcuts (0.1ms, bypass model) ──
    if await try_shortcut(client, chat_id, text):
        return

    # ── Step 2: Classify intent ──
    t0 = time.perf_counter()
    intent, confidence = classify_intent(text)
    classify_ms = (time.perf_counter() - t0) * 1000
    _stats["total_classify_ms"] += classify_ms
    _stats["intents_seen"][intent] = _stats["intents_seen"].get(intent, 0) + 1

    # ── Step 3: Select model ──
    model = select_model(text, intent)
    log.info(f"  [{intent}] conf:{confidence:.0%} → {model}")

    # ── Step 4: Generate response ──
    system_prompt = SYSTEM_PROMPTS.get(intent.split("_")[0], SYSTEM_PROMPTS.get(intent, SYSTEM_PROMPTS["question"]))

    # OpenClaw agent info
    agent_name = ""
    if _bridge:
        route = _bridge.route(text)
        agent_name = route.agent if route else ""

    try:
        response, generate_ms = await call_model(client, model, text, system_prompt, max_tokens=512)
        _stats["total_generate_ms"] += generate_ms
        _stats["processed"] += 1
        _stats["models_used"][model] = _stats["models_used"].get(model, 0) + 1

        total_ms = classify_ms + generate_ms
        log.info(f"  {model} classify:{classify_ms:.0f}ms gen:{generate_ms:.0f}ms total:{total_ms:.0f}ms len:{len(response)}")

        # Save context
        _last_context[chat_id] = {
            "intent": intent, "model": model, "agent": agent_name,
            "prompt": text, "response": response, "timestamp": time.time(),
        }

        # ── Step 5: Send response with actions ──
        model_short = model.split(":")[0].split("-")[0] if model != "qwen3:1.7b" else "qwen3"
        agent_tag = f" | {agent_name}" if agent_name else ""
        header = f"*[{intent.upper()}]* `{model_short}` _{total_ms:.0f}ms{agent_tag}_\n\n"

        actions = INTENT_ACTIONS.get(intent, INTENT_ACTIONS.get("query", []))
        status_row = [{"text": f"{total_ms:.0f}ms | {model_short}", "cb": "stats"}]
        all_actions = actions + [status_row]

        await tg_send(client, chat_id, header + response, keyboard=all_actions)

    except Exception as e:
        _stats["errors"] += 1
        log.error(f"Pipeline error: {e}")
        await tg_send(client, chat_id, f"Erreur pipeline ({model}): {e}", parse_mode=None)


# ══════════════════════════════════════════════════════════════════
# BOT COMMANDS
# ══════════════════════════════════════════════════════════════════

async def handle_command(client: httpx.AsyncClient, chat_id: int, text: str):
    cmd = text.split()[0].lower()

    if cmd in ("/start", "/help"):
        models_list = "\n".join(f"  `{m}` ({v['speed']}, {v['tok_s']}tok/s)" for m, v in list(MODELS.items())[:6])
        await tg_send(client, chat_id,
            f"*JARVIS Pipeline Production v3*\n\n"
            f"*{len(MODELS)} modeles* branches, routing intelligent.\n"
            f"*{len(_dominos)} pipelines* domino pre-encodes.\n"
            f"*438 scripts* cowork disponibles.\n\n"
            f"*Modeles:*\n{models_list}\n\n"
            f"*Shortcuts:* gpu, disk, ram, process, cluster, models\n"
            f"*Cowork:* `cowork <nom_script>`\n"
            f"*Pipelines:* routine matin, trading scan, debug cluster...\n"
            f"*Commandes:* /status /health /models /agents /pipelines",
        )
        return

    if cmd in ("/status", "/stats"):
        uptime = time.time() - _stats["start_time"]
        n = max(_stats["processed"], 1)
        top_models = sorted(_stats["models_used"].items(), key=lambda x: -x[1])[:5]
        top_intents = sorted(_stats["intents_seen"].items(), key=lambda x: -x[1])[:5]
        models_str = "\n".join(f"  `{m}`: {c}" for m, c in top_models) or "  Aucun"
        intents_str = "\n".join(f"  `{i}`: {c}" for i, c in top_intents) or "  Aucun"
        await tg_send(client, chat_id,
            f"*JARVIS Stats*\n\n"
            f"Uptime: {uptime/60:.0f}min\n"
            f"Messages: {_stats['received']} | Traites: {_stats['processed']} | Erreurs: {_stats['errors']}\n"
            f"Shortcuts: {_stats['shortcuts_used']} | Dominos: {_stats['dominos_triggered']}\n"
            f"Classify: {_stats['total_classify_ms']/n:.0f}ms avg\n"
            f"Generate: {_stats['total_generate_ms']/n:.0f}ms avg\n\n"
            f"*Top modeles:*\n{models_str}\n\n*Top intents:*\n{intents_str}",
        )
        return

    if cmd == "/health":
        await try_shortcut(client, chat_id, "cluster")
        return

    if cmd == "/models":
        await try_shortcut(client, chat_id, "models")
        return

    if cmd == "/pipelines":
        if _dominos:
            lines = ["*Domino Pipelines*\n"]
            for d in _dominos[:15]:
                triggers = ", ".join(d.trigger_vocal[:2]) if d.trigger_vocal else "?"
                lines.append(f"  `{d.id}` — _{triggers}_ ({len(d.steps)} steps)")
            await tg_send(client, chat_id, "\n".join(lines))
        else:
            await tg_send(client, chat_id, "Pipelines non chargees.")
        return

    if cmd == "/agents":
        if _bridge:
            table = _bridge.get_routing_table()
            lines = ["*OpenClaw Agents*\n"]
            for intent, agent in sorted(table.items()):
                lines.append(f"  `{intent:15s}` → {agent}")
            await tg_send(client, chat_id, "\n".join(lines[:30]))
        else:
            await tg_send(client, chat_id, "OpenClaw bridge non chargee.")
        return


# ══════════════════════════════════════════════════════════════════
# CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════════

async def handle_callback(client: httpx.AsyncClient, callback: dict):
    cb_id = callback.get("id", "")
    data = callback.get("data", "")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    ctx = _last_context.get(chat_id, {})

    if not data or not chat_id:
        await tg_answer_callback(client, cb_id)
        return

    log.info(f"  Callback: {data}")

    if data == "exec":
        await tg_answer_callback(client, cb_id, "Execution...")
        code_blocks = re.findall(r'```(?:\w+)?\n?(.*?)```', ctx.get("response", ""), re.DOTALL)
        if code_blocks:
            cmd = code_blocks[0].strip()
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15, cwd=_ROOT)
                output = (result.stdout or result.stderr or "OK").strip()
                await tg_send(client, chat_id, f"*Resultat:*\n```\n{output[:3000]}\n```")
            except Exception as e:
                await tg_send(client, chat_id, f"Erreur: {e}", parse_mode=None)
        else:
            await tg_send(client, chat_id, "Pas de code executable.")

    elif data == "explain":
        await tg_answer_callback(client, cb_id, "Explication...")
        resp, ms = await call_model(client, "qwen3-8b", f"Explique ligne par ligne:\n{ctx.get('response', '')[:800]}", "Pedagogie code. Francais.", 512)
        await tg_send(client, chat_id, f"*Explication ({ms:.0f}ms):*\n\n{resp}")

    elif data == "optimize":
        await tg_answer_callback(client, cb_id, "Optimisation...")
        resp, ms = await call_model(client, "qwen3-8b", f"Optimise:\n{ctx.get('response', '')[:800]}", "Expert optimisation.", 512)
        await tg_send(client, chat_id, f"*Optimise ({ms:.0f}ms):*\n\n{resp}")

    elif data == "deep" or data == "websearch":
        await tg_answer_callback(client, cb_id, "Approfondissement...")
        model = "minimax-m2.5:cloud" if data == "websearch" else "gpt-oss-20b"
        resp, ms = await call_model(client, model, ctx.get("prompt", ""), "Approfondi avec details et exemples.", 768)
        await tg_send(client, chat_id, f"*[{model}] {ms:.0f}ms:*\n\n{resp}")

    elif data == "escalate":
        await tg_answer_callback(client, cb_id, "Escalade gpt-oss-20b...")
        resp, ms = await call_model(client, "gpt-oss-20b",
            f"Analyse approfondie:\n{ctx.get('prompt','')}\n\nContexte:\n{ctx.get('response','')[:500]}", "", 1024)
        await tg_send(client, chat_id, f"*[gpt-oss-20b] {ms:.0f}ms:*\n\n{resp}")

    elif data == "scan":
        await tg_answer_callback(client, cb_id, "Scan trading...")
        resp, ms = await call_model(client, "minimax-m2.5:cloud",
            "Scan crypto: BTC ETH SOL prix actuels, tendance 24h, RSI. Format tableau.", SYSTEM_PROMPTS["trading"], 384)
        await tg_send(client, chat_id, f"*Scan Trading ({ms:.0f}ms):*\n\n{resp}")

    elif data.startswith("domino_"):
        pipeline_id = data[7:]
        await tg_answer_callback(client, cb_id, f"Pipeline {pipeline_id}...")
        await tg_send(client, chat_id, f"*Execution pipeline `{pipeline_id}`...*\n_Implementation domino executor en cours._")

    elif data == "stats":
        await tg_answer_callback(client, cb_id, "Stats")

    elif data == "cancel":
        await tg_answer_callback(client, cb_id, "Annule.")

    else:
        await tg_answer_callback(client, cb_id, f"Action: {data}")
        await tg_send(client, chat_id, f"Action `{data}` — en cours.", parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════
# HEALTH MONITOR
# ══════════════════════════════════════════════════════════════════

async def health_monitor(client: httpx.AsyncClient):
    global _last_alerts
    while True:
        await asyncio.sleep(300)  # Every 5 min (reduced from 2)
        try:
            alerts = set()
            for name, url in [("ollama", f"{OLLAMA}/api/tags"), ("ws", f"{WS}/health")]:
                try:
                    await client.get(url, timeout=3)
                except Exception:
                    alerts.add(f"{name} DOWN")
            # GPU check
            try:
                r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu",
                                    "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
                for i, line in enumerate(r.stdout.strip().split("\n")):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) == 3:
                        pct = int(parts[0]) / int(parts[1]) * 100
                        if int(parts[2]) > 85: alerts.add(f"GPU {i} temp: {parts[2]}C")
                        if pct > 95: alerts.add(f"GPU {i} VRAM: {pct:.0f}%")
            except Exception:
                pass
            new = alerts - _last_alerts
            resolved = _last_alerts - alerts
            if new and TG_CHAT:
                await tg_send(client, TG_CHAT, "*JARVIS Alert*\n" + "\n".join(f"- {a}" for a in new))
            if resolved and TG_CHAT:
                await tg_send(client, TG_CHAT, "*Resolved*\n" + "\n".join(f"- {a}" for a in resolved))
            _last_alerts = alerts
        except Exception as e:
            log.error(f"Health error: {e}")


# ══════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════

async def main():
    global _last_update_id

    log.info("=" * 60)
    log.info("  JARVIS Telegram Production Pipeline v3")
    log.info(f"  {len(MODELS)} modeles | {len(_dominos)} dominos | 438 cowork scripts")
    log.info(f"  IntentClassifier: {'OK' if _classifier else 'FALLBACK'}")
    log.info(f"  OpenClaw bridge: {'OK' if _bridge else 'FALLBACK'}")
    log.info("=" * 60)

    _stats["start_time"] = time.time()

    async with httpx.AsyncClient() as client:
        # Verify services
        for name, url in [("Ollama", f"{OLLAMA}/api/tags"), ("WS", f"{WS}/health")]:
            try:
                await client.get(url, timeout=5)
                log.info(f"  {name}: OK")
            except Exception as e:
                log.warning(f"  {name}: {e}")

        # Verify bot
        me = await tg_call(client, "getMe")
        if not me.get("ok"):
            log.error(f"Bot error: {me}")
            return
        log.info(f"  Bot: @{me['result'].get('username')}")

        # Boot notification
        await tg_send(client, TG_CHAT,
            f"*JARVIS v3 LIVE*\n\n"
            f"{len(MODELS)} modeles | {len(_dominos)} dominos | 438 cowork\n"
            f"Smart routing actif. Envoyez un message.\n"
            f"/help pour les commandes",
        )

        # Start health monitor
        asyncio.create_task(health_monitor(client))

        log.info("Listening...")
        while True:
            try:
                r = await client.post(f"{TG_API}/getUpdates", json={
                    "offset": _last_update_id + 1, "timeout": 30,
                    "allowed_updates": ["message", "callback_query"],
                }, timeout=35)
                for update in r.json().get("result", []):
                    _last_update_id = update["update_id"]
                    if "message" in update:
                        asyncio.create_task(handle_message(client, update["message"]))
                    elif "callback_query" in update:
                        asyncio.create_task(handle_callback(client, update["callback_query"]))
            except httpx.TimeoutException:
                continue
            except Exception as e:
                log.error(f"Poll error: {e}")
                await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown.")
