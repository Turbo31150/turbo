#!/usr/bin/env python3
"""JARVIS DevOps Orchestrator — Full cluster + OpenClaw + HF + Gemini + Claude routing.

Dispatches tasks to ALL available providers through OpenClaw's 40 agents.
Timeout-aware, circuit-breaker, results → Telegram.

Providers:
  - M2 (deepseek-r1, reasoning, 60s timeout)
  - M3 (deepseek-r1, reasoning fallback, 90s timeout)
  - HF/Qwen3.5-27B (fast cloud, 20s)
  - HF/DeepSeek-R1 (reasoning cloud, 30s)
  - HF/Llama-3.3-70B (general cloud, 20s)
  - HF/gpt-oss-120b (big tasks, 45s)
  - Gemini (archi/web/vision via CLI proxy, 30s)
  - Claude (complex reasoning via CLI proxy, 60s)
  - M1 (qwen3-8b, IF loaded, 15s)
  - OL1 (qwen3:1.7b, IF loaded, 10s)

Usage:
    python scripts/devops_orchestrator.py --health          # Health check all
    python scripts/devops_orchestrator.py --dispatch "msg"  # Smart dispatch
    python scripts/devops_orchestrator.py --broadcast "msg" # All agents parallel
    python scripts/devops_orchestrator.py --consensus "msg" # Weighted vote
    python scripts/devops_orchestrator.py --daemon          # Continuous mode
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
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import sqlite3
import threading
from collections import defaultdict

TURBO = Path("F:/BUREAU/turbo")
sys.path.insert(0, str(TURBO))
METRICS_DB = str(TURBO / "data" / "devops_metrics.db")

# ── Logging ────────────────────────────────────────────────────────────────
LOG_PATH = TURBO / "data" / "devops_orchestrator.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(LOG_PATH), encoding="utf-8"),
    ],
)
log = logging.getLogger("devops_orch")

# ── Load .env ──────────────────────────────────────────────────────────────
def _load_env():
    env = {}
    env_file = TURBO / ".env"
    if env_file.exists():
        for line in env_file.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

ENV = _load_env()
HF_TOKEN = ENV.get("HF_TOKEN", "")
TELEGRAM_TOKEN = ENV.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = ENV.get("TELEGRAM_CHAT", "")

# ── Think tag stripping (deepseek-r1) ─────────────────────────────────────
_THINK_CLOSED = re.compile(r"<think>[\s\S]*?</think>")
_THINK_OPEN = re.compile(r"<think>[\s\S]*$")

def strip_think(text: str) -> str:
    text = _THINK_CLOSED.sub("", text)
    text = _THINK_OPEN.sub("", text)
    return text.strip()

# ── Provider Definitions ──────────────────────────────────────────────────
@dataclass
class Provider:
    id: str
    name: str
    api_type: str  # "openai", "ollama", "lmstudio_resp", "gemini_cli", "claude_cli"
    url: str
    model: str
    timeout: int  # seconds
    max_tokens: int
    weight: float
    is_reasoning: bool = False
    is_cloud: bool = False
    needs_think_strip: bool = False
    needs_nothink: bool = False
    auth_header: str = ""
    circuit_open: bool = False
    fail_count: int = 0
    last_fail: float = 0.0
    cooldown: float = 120.0

    def is_available(self) -> bool:
        if not self.circuit_open:
            return True
        if time.time() - self.last_fail > self.cooldown:
            self.circuit_open = False
            self.fail_count = 0
            return True
        return False

    def record_fail(self):
        self.fail_count += 1
        self.last_fail = time.time()
        if self.fail_count >= 3:  # 3 fails before circuit opens (was 2)
            self.circuit_open = True
            self.cooldown = min(300, 60 * (2 ** min(self.fail_count - 3, 3)))  # exponential: 60→120→240→300 cap
            log.warning("Circuit OPEN: %s (fails=%d, cooldown=%.0fs)", self.id, self.fail_count, self.cooldown)

    def record_success(self):
        self.fail_count = 0
        self.circuit_open = False
        self.cooldown = 120.0


# All providers
PROVIDERS: dict[str, Provider] = {
    # ── Local LM Studio ──
    "M1": Provider("M1", "M1/qwen3-8b", "openai",
                   "http://127.0.0.1:1234/v1/chat/completions", "qwen3-8b",
                   timeout=45, max_tokens=64, weight=1.2, needs_nothink=True),  # slow ~1tok/s GPU1 lost
    "M2": Provider("M2", "M2/deepseek-r1", "openai",
                   "http://192.168.1.26:1234/v1/chat/completions", "deepseek-r1-0528-qwen3-8b",
                   timeout=120, max_tokens=4096, weight=1.5, is_reasoning=True, needs_think_strip=True),
    "M3": Provider("M3", "M3/deepseek-r1", "openai",
                   "http://192.168.1.113:1234/v1/chat/completions", "deepseek-r1-0528-qwen3-8b",
                   timeout=90, max_tokens=1024, weight=1.1, is_reasoning=True, needs_think_strip=True),
    # ── Local Ollama ──
    "OL1": Provider("OL1", "OL1/qwen3", "ollama",
                    "http://127.0.0.1:11434/api/chat", "qwen3:1.7b",
                    timeout=25, max_tokens=256, weight=0.8, needs_nothink=True),  # unstable, low weight
    # ── HuggingFace Cloud (CREDITS DEPLETED 2026-03-11 — circuit forced open) ──
    # 30 models available but monthly quota exhausted. Will auto-recover when credits refill.
    "HF_QWEN27": Provider("HF_QWEN27", "HF/Qwen3.5-27B", "openai",
                          "https://router.huggingface.co/v1/chat/completions", "Qwen/Qwen3.5-27B",
                          timeout=20, max_tokens=512, weight=0.1, is_cloud=True,
                          auth_header=f"Bearer {HF_TOKEN}"),
    "HF_DEEPSEEK": Provider("HF_DEEPSEEK", "HF/DeepSeek-R1", "openai",
                            "https://router.huggingface.co/v1/chat/completions", "deepseek-ai/DeepSeek-R1-0528",
                            timeout=30, max_tokens=512, weight=0.1, is_cloud=True, is_reasoning=True,
                            needs_think_strip=True, auth_header=f"Bearer {HF_TOKEN}"),
    "HF_LLAMA70": Provider("HF_LLAMA70", "HF/Llama-3.3-70B", "openai",
                           "https://router.huggingface.co/v1/chat/completions", "meta-llama/Llama-3.3-70B-Instruct",
                           timeout=20, max_tokens=512, weight=0.1, is_cloud=True,
                           auth_header=f"Bearer {HF_TOKEN}"),
    "HF_GPT120": Provider("HF_GPT120", "HF/gpt-oss-120b", "openai",
                          "https://router.huggingface.co/v1/chat/completions", "openai/gpt-oss-120b",
                          timeout=45, max_tokens=1024, weight=0.1, is_cloud=True,
                          auth_header=f"Bearer {HF_TOKEN}"),
    "HF_QWEN35B": Provider("HF_QWEN35B", "HF/Qwen3.5-35B-MoE", "openai",
                           "https://router.huggingface.co/v1/chat/completions", "Qwen/Qwen3.5-35B-A3B",
                           timeout=20, max_tokens=512, weight=0.1, is_cloud=True,
                           auth_header=f"Bearer {HF_TOKEN}"),
    # ── CLI Proxies ──
    "GEMINI": Provider("GEMINI", "Gemini/flash", "gemini_rest",
                       f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={ENV.get('GEMINI_API_KEY','')}",
                       "gemini-2.5-flash",
                       timeout=20, max_tokens=512, weight=1.5, is_cloud=True),
    "CLAUDE": Provider("CLAUDE", "Claude/sonnet", "claude_cli",
                       "", "claude-sonnet",
                       timeout=60, max_tokens=1024, weight=1.2, is_cloud=True),
}

# Auto-disable HF providers if credits depleted (check at import time)
def _probe_hf_credits():
    """Quick check if HF credits are available. Force circuits open if depleted."""
    if not HF_TOKEN:
        return
    try:
        cmd = ["curl", "-s", "--max-time", "5",
               "https://router.huggingface.co/v1/chat/completions",
               "-H", "Content-Type: application/json",
               "-H", f"Authorization: Bearer {HF_TOKEN}",
               "-d", '{"model":"Qwen/Qwen3-8B","messages":[{"role":"user","content":"ok"}],"max_tokens":1,"stream":false}']
        result = subprocess.run(cmd, capture_output=True, timeout=8)
        text = result.stdout.decode("utf-8", errors="replace")
        if "depleted" in text.lower():
            log.warning("HF credits DEPLETED — disabling all HF providers")
            for pid, p in PROVIDERS.items():
                if pid.startswith("HF_"):
                    p.circuit_open = True
                    p.cooldown = 3600  # 1h cooldown
                    p.fail_count = 10  # keep circuit open
    except Exception:
        pass

_probe_hf_credits()


# ── Metrics Tracker ───────────────────────────────────────────────────────

class MetricsTracker:
    """Track per-provider performance metrics. Thread-safe, SQLite-backed."""

    def __init__(self, db_path: str = METRICS_DB):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS dispatch_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT DEFAULT (datetime('now')),
                provider TEXT NOT NULL,
                agent TEXT,
                success INTEGER,
                latency_ms REAL,
                response_len INTEGER DEFAULT 0
            )""")
            db.execute("""CREATE INDEX IF NOT EXISTS idx_metrics_provider
                ON dispatch_metrics(provider, ts)""")

    def record(self, provider_id: str, agent: str, success: bool, latency_ms: float, response_len: int = 0):
        with self._lock:
            try:
                with sqlite3.connect(self._db_path) as db:
                    db.execute(
                        "INSERT INTO dispatch_metrics(provider, agent, success, latency_ms, response_len) VALUES(?,?,?,?,?)",
                        (provider_id, agent, int(success), latency_ms, response_len))
            except Exception as e:
                log.debug("Metrics record error: %s", e)

    def get_stats(self, hours: int = 1) -> dict[str, dict]:
        """Get per-provider stats for the last N hours."""
        with sqlite3.connect(self._db_path) as db:
            rows = db.execute("""
                SELECT provider,
                    COUNT(*) as total,
                    SUM(success) as ok,
                    AVG(latency_ms) as avg_ms,
                    MAX(latency_ms) as max_ms
                FROM dispatch_metrics
                WHERE ts > datetime('now', ? || ' hours')
                GROUP BY provider
            """, (f"-{hours}",)).fetchall()
        stats = {}
        for r in rows:
            pid, total, ok, avg_ms, max_ms = r
            stats[pid] = {
                "total": total, "ok": ok, "fail": total - ok,
                "sr": round(ok / total * 100, 1) if total else 0,
                "avg_ms": round(avg_ms or 0), "max_ms": round(max_ms or 0),
            }
        return stats

    def adjust_weights(self):
        """Dynamically adjust provider weights based on recent performance."""
        stats = self.get_stats(hours=1)
        for pid, s in stats.items():
            provider = PROVIDERS.get(pid)
            if not provider or s["total"] < 3:
                continue
            # Base weight stays, adjust by SR and speed
            sr = s["sr"] / 100.0
            speed_factor = min(1.0, 10000 / max(1, s["avg_ms"]))  # faster = higher
            adjustment = sr * 0.7 + speed_factor * 0.3  # 70% reliability, 30% speed
            # Clamp between 0.5 and 2.0
            new_weight = max(0.5, min(2.0, provider.weight * (0.5 + adjustment * 0.5)))
            if abs(new_weight - provider.weight) > 0.05:
                log.info("Weight adjust: %s %.2f → %.2f (sr=%.0f%% avg=%dms)",
                         pid, provider.weight, new_weight, s["sr"], s["avg_ms"])
                provider.weight = round(new_weight, 2)


# Global metrics instance
METRICS = MetricsTracker()

# ── OpenClaw Agent → Provider routing ─────────────────────────────────────
# Maps each of the 40 OpenClaw agents to preferred providers (ordered)
AGENT_ROUTING: dict[str, list[str]] = {
    # Code agents → M1 (local fast for code) + Gemini + M2 (review)
    "coding":            ["M1", "OL1", "GEMINI", "M2", "HF_QWEN27"],
    "code-champion":     ["M1", "M2", "GEMINI", "HF_GPT120"],
    "debug-detective":   ["M2", "OL1", "M1", "GEMINI"],
    "devops-ci":         ["GEMINI", "OL1", "M1", "M2"],
    # Reasoning agents → M2 (deepseek-r1) + Claude + M3 (fallback)
    "deep-work":         ["M2", "CLAUDE", "M3", "GEMINI"],
    "deep-reasoning":    ["M2", "CLAUDE", "M3", "HF_DEEPSEEK"],
    "analysis-engine":   ["M2", "GEMINI", "CLAUDE", "M3"],
    "claude-reasoning":  ["CLAUDE", "M2", "M3"],
    "consensus-master":  ["M2", "GEMINI", "CLAUDE", "OL1", "M3"],
    # Fast agents → OL1 (fastest local) + Gemini + M1
    "fast-chat":         ["M1", "OL1", "GEMINI", "HF_QWEN27"],
    "quick-dispatch":    ["M1", "OL1", "GEMINI"],
    "main":              ["M1", "OL1", "GEMINI", "M2"],
    "task-router":       ["M1", "OL1", "GEMINI"],
    # Trading agents → OL1 (web) + M2 (analysis)
    "trading":           ["OL1", "M2", "GEMINI", "HF_QWEN27"],
    "trading-scanner":   ["GEMINI", "OL1", "M2"],
    # System/Infra agents → OL1 + M1
    "system-ops":        ["OL1", "M1", "GEMINI", "M2"],
    "windows":           ["OL1", "M1", "GEMINI"],
    "voice-assistant":   ["OL1", "M1"],
    # Pipeline agents → OL1 fast
    "pipeline-monitor":  ["OL1", "GEMINI", "M1"],
    "pipeline-trading":  ["OL1", "M2", "GEMINI"],
    "pipeline-maintenance": ["OL1", "M1", "GEMINI"],
    "pipeline-comet":    ["OL1", "GEMINI"],
    "pipeline-routines": ["OL1", "M1"],
    "pipeline-modes":    ["OL1", "GEMINI"],
    # Specialized agents
    "data-analyst":      ["M2", "GEMINI", "CLAUDE", "M3"],
    "creative-brainstorm": ["GEMINI", "CLAUDE", "M2"],
    "doc-writer":        ["GEMINI", "OL1", "M1"],
    "translator":        ["OL1", "GEMINI", "M1"],
    "recherche-synthese": ["GEMINI", "OL1", "CLAUDE"],
    "securite-audit":    ["M2", "GEMINI", "CLAUDE"],
    # Node-specific agents → their actual nodes
    "m1-deep":           ["M1", "OL1", "M2"],
    "m1-reason":         ["M1", "M2", "M3"],
    "m2-code":           ["M2", "OL1", "M1"],
    "m2-review":         ["M2", "GEMINI", "CLAUDE"],
    "m3-general":        ["M3", "M2", "OL1"],
    "ol1-fast":          ["OL1", "M1", "GEMINI"],
    "ol1-reasoning":     ["OL1", "M2", "M3"],
    "ol1-web":           ["GEMINI", "OL1"],
    "gemini-flash":      ["GEMINI", "OL1", "M1"],
    "gemini-pro":        ["GEMINI", "CLAUDE", "M2"],
}

# ── Intent classification (from openclaw_bridge) ─────────────────────────
INTENT_PATTERNS = [
    (re.compile(r"(?:code|programme|fonction|script|bug|debug|refactor|implemente)", re.I), "coding"),
    (re.compile(r"(?:securite|audit|vulnerabilite|owasp|faille)", re.I), "securite-audit"),
    (re.compile(r"(?:trade|trading|btc|eth|sol|crypto|mexc|signal)", re.I), "trading"),
    (re.compile(r"(?:cluster|gpu|vram|health|diagnostic|temperature)", re.I), "system-ops"),
    (re.compile(r"(?:architecture|design.pattern|microservice)", re.I), "deep-work"),
    (re.compile(r"(?:raisonnement|logique|mathematique|preuve)", re.I), "deep-reasoning"),
    (re.compile(r"(?:analyse|compare|rapport|statistique|donnees)", re.I), "data-analyst"),
    (re.compile(r"(?:cherche|recherche|web|internet|actualite)", re.I), "recherche-synthese"),
    (re.compile(r"(?:traduis|traduction|translate)", re.I), "translator"),
    (re.compile(r"(?:consensus|vote|arbitrage)", re.I), "consensus-master"),
    (re.compile(r"(?:pipeline|domino|routine|workflow)", re.I), "pipeline-monitor"),
    (re.compile(r"(?:creatif|brainstorm|invente|imagine)", re.I), "creative-brainstorm"),
    (re.compile(r"(?:documente|readme|changelog)", re.I), "doc-writer"),
    (re.compile(r"(?:deploy|ci|cd|docker|git|commit)", re.I), "devops-ci"),
]

def classify_intent(text: str) -> str:
    for pattern, agent in INTENT_PATTERNS:
        if pattern.search(text):
            return agent
    return "fast-chat"

# ── Query Functions ───────────────────────────────────────────────────────

def _query_openai(provider: Provider, prompt: str) -> str:
    """Query OpenAI-compatible endpoint (M2, M3, HF models)."""
    headers = ["Content-Type: application/json"]
    if provider.auth_header:
        headers.append(f"Authorization: {provider.auth_header}")

    user_content = f"/nothink\n{prompt}" if provider.needs_nothink else prompt
    # For reasoning models (deepseek-r1): ensure enough tokens for think+answer
    # deepseek-r1 uses ~1000-3000 tokens just for <think>, needs 4096+ total
    max_tok = provider.max_tokens
    if provider.is_reasoning and max_tok < 4096:
        max_tok = 4096  # reasoning models need room for <think>+answer
    body = json.dumps({
        "model": provider.model,
        "messages": [{"role": "user", "content": user_content}],
        "max_tokens": max_tok,
        "temperature": 0.3,
        "stream": False,
    })

    cmd = ["curl", "-s", "--max-time", str(provider.timeout), provider.url]
    for h in headers:
        cmd.extend(["-H", h])
    cmd.extend(["-d", body])

    result = subprocess.run(cmd, capture_output=True, timeout=provider.timeout + 5)
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr[:200]}")

    data = json.loads(result.stdout.decode("utf-8", errors="replace"))
    if "choices" in data and data["choices"]:
        content = data["choices"][0].get("message", {}).get("content", "")
        if provider.needs_think_strip:
            content = strip_think(content)
        return content.strip()
    if "error" in data:
        raise RuntimeError(f"API error: {data['error']}")
    return ""


def _query_lmstudio_resp(provider: Provider, prompt: str) -> str:
    """Query LM Studio Responses API (M1)."""
    input_text = f"/nothink\n{prompt}" if provider.needs_nothink else prompt
    body = json.dumps({
        "model": provider.model,
        "input": input_text,
        "temperature": 0.2,
        "max_output_tokens": provider.max_tokens,
        "stream": False,
        "store": False,
    })

    cmd = ["curl", "-s", "--max-time", str(provider.timeout),
           provider.url, "-H", "Content-Type: application/json", "-d", body]
    result = subprocess.run(cmd, capture_output=True, timeout=provider.timeout + 5)
    data = json.loads(result.stdout.decode("utf-8", errors="replace"))

    for item in reversed(data.get("output", [])):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    return c["text"].strip()
    return ""


def _query_ollama(provider: Provider, prompt: str) -> str:
    """Query Ollama endpoint (OL1). Robust JSON parsing."""
    msg = f"/no_think\n{prompt}" if provider.needs_nothink else prompt
    body = json.dumps({
        "model": provider.model,
        "messages": [{"role": "user", "content": msg}],
        "stream": False,
        "options": {"num_predict": provider.max_tokens},
    })

    cmd = ["curl", "-s", "--max-time", str(provider.timeout),
           provider.url, "-d", body]
    result = subprocess.run(cmd, capture_output=True, timeout=provider.timeout + 5)
    raw = result.stdout.decode("utf-8", errors="replace").strip()
    if not raw:
        raise RuntimeError("OL1 returned empty response")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Sometimes Ollama returns partial JSON or error text
        if "error" in raw.lower():
            raise RuntimeError(f"OL1 error: {raw[:200]}")
        raise RuntimeError(f"OL1 invalid JSON: {raw[:100]}")
    if "error" in data:
        raise RuntimeError(f"OL1: {data['error'][:200]}")
    content = data.get("message", {}).get("content", "")
    return strip_think(content).strip()


def _query_gemini_rest(provider: Provider, prompt: str) -> str:
    """Query Gemini via REST API direct."""
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": provider.max_tokens, "temperature": 0.3},
    })
    cmd = ["curl", "-s", "--max-time", str(provider.timeout), provider.url,
           "-H", "Content-Type: application/json", "-d", body]
    result = subprocess.run(cmd, capture_output=True, timeout=provider.timeout + 5)
    data = json.loads(result.stdout.decode("utf-8", errors="replace"))
    if "candidates" in data and data["candidates"]:
        parts = data["candidates"][0].get("content", {}).get("parts", [])
        if parts:
            return parts[0].get("text", "").strip()
    if "error" in data:
        msg = data["error"].get("message", str(data["error"]))
        if "429" in str(data["error"].get("code", "")) or "rate" in msg.lower():
            raise RuntimeError(f"Rate limited: {msg[:100]}")
        raise RuntimeError(f"Gemini error: {msg[:100]}")
    return ""


def _query_gemini_cli(provider: Provider, prompt: str) -> str:
    """Query Gemini via CLI proxy (fallback)."""
    cmd = ["node", "F:/BUREAU/turbo/gemini-proxy.js", prompt]
    result = subprocess.run(cmd, capture_output=True, timeout=provider.timeout + 5)
    return result.stdout.decode("utf-8", errors="replace").strip()


def _query_claude_cli(provider: Provider, prompt: str) -> str:
    """Query Claude via CLI proxy."""
    cmd = ["node", "F:/BUREAU/turbo/claude-proxy.js", prompt]
    result = subprocess.run(cmd, capture_output=True, timeout=provider.timeout + 5)
    out = result.stdout.decode("utf-8", errors="replace").strip()
    if not out:
        raise RuntimeError("Claude proxy returned empty")
    return out


# Simple response cache (prompt hash → response, TTL 120s)
_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 120.0

def query_provider(provider: Provider, prompt: str, use_cache: bool = True) -> str:
    """Route to the correct query function based on API type. With cache + retry."""
    cache_key = f"{provider.id}:{hash(prompt[:200])}"
    if use_cache and cache_key in _CACHE:
        cached, ts = _CACHE[cache_key]
        if time.time() - ts < _CACHE_TTL:
            log.debug("Cache hit: %s", cache_key)
            return cached

    dispatch = {
        "openai": _query_openai,
        "lmstudio_resp": _query_lmstudio_resp,
        "ollama": _query_ollama,
        "gemini_rest": _query_gemini_rest,
        "gemini_cli": _query_gemini_cli,
        "claude_cli": _query_claude_cli,
    }
    fn = dispatch.get(provider.api_type)
    if not fn:
        raise ValueError(f"Unknown API type: {provider.api_type}")

    # Retry once on failure
    last_err = None
    for attempt in range(2):
        try:
            result = fn(provider, prompt)
            if result:
                _CACHE[cache_key] = (result, time.time())
                return result
        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(1)  # brief backoff before retry
    if last_err:
        raise last_err
    return ""


# ── Dispatch Logic ────────────────────────────────────────────────────────

@dataclass
class DispatchResult:
    provider_id: str
    provider_name: str
    agent: str
    response: str
    latency_ms: float
    success: bool
    error: str = ""


# Universal fallback chain — tried after agent-specific providers fail
_FALLBACK_CHAIN = ["M1", "M2", "OL1", "M3", "CLAUDE"]


def dispatch_to_agent(agent: str, prompt: str) -> DispatchResult:
    """Dispatch a prompt to an OpenClaw agent's preferred providers (fallback chain)."""
    agent_providers = AGENT_ROUTING.get(agent, [])
    # Combine agent-specific + universal fallback (deduplicated)
    seen = set()
    providers_chain = []
    for pid in agent_providers + _FALLBACK_CHAIN:
        if pid not in seen:
            seen.add(pid)
            providers_chain.append(pid)

    for pid in providers_chain:
        provider = PROVIDERS.get(pid)
        if not provider or not provider.is_available():
            continue

        start = time.time()
        try:
            response = query_provider(provider, prompt)
            elapsed = (time.time() - start) * 1000
            if response:
                provider.record_success()
                METRICS.record(pid, agent, True, elapsed, len(response))
                log.info("[%s→%s] OK %.0fms (%d chars)", agent, pid, elapsed, len(response))
                return DispatchResult(pid, provider.name, agent, response, elapsed, True)
            else:
                provider.record_fail()
                METRICS.record(pid, agent, False, elapsed)
                log.warning("[%s→%s] Empty response", agent, pid)
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            provider.record_fail()
            METRICS.record(pid, agent, False, elapsed)
            log.warning("[%s→%s] FAIL %.0fms: %s", agent, pid, elapsed, str(e)[:100])

    return DispatchResult("NONE", "none", agent, "", 0, False, "All providers failed")


def is_long_task(prompt: str) -> bool:
    """Detect if a prompt is a long/complex task that should use the pipeline."""
    # Long prompts (>300 chars) or multi-step indicators
    if len(prompt) > 300:
        return True
    long_indicators = [
        "step by step", "etape par etape", "analyse complete", "full analysis",
        "build", "construis", "implemente", "create a", "write a complete",
        "refactor", "audit", "plan", "design", "architecture",
    ]
    prompt_lower = prompt.lower()
    return sum(1 for kw in long_indicators if kw in prompt_lower) >= 2


def smart_dispatch(prompt: str, force_pipeline: bool = False) -> DispatchResult:
    """Classify intent → select agent → dispatch to best provider.
    Auto-routes long tasks to the pipeline engine."""
    if force_pipeline or is_long_task(prompt):
        try:
            from pipeline_engine import run_pipeline
            log.info("Long task detected — routing to pipeline engine")
            pipeline = run_pipeline(prompt, telegram=False)
            if pipeline.result:
                return DispatchResult("PIPELINE", "pipeline", "auto",
                                      pipeline.result, 0, True)
        except Exception as e:
            log.warning("Pipeline fallback: %s", e)

    agent = classify_intent(prompt)
    log.info("Intent: '%s' → agent: %s", prompt[:50], agent)
    return dispatch_to_agent(agent, prompt)


def broadcast_dispatch(prompt: str, max_workers: int = 12) -> list[DispatchResult]:
    """Send prompt to ALL available providers in parallel."""
    results = []
    available = [(pid, p) for pid, p in PROVIDERS.items() if p.is_available()]
    log.info("Broadcasting to %d providers...", len(available))

    def _query(pid_provider):
        pid, provider = pid_provider
        start = time.time()
        try:
            response = query_provider(provider, prompt)
            elapsed = (time.time() - start) * 1000
            if response:
                provider.record_success()
                return DispatchResult(pid, provider.name, "broadcast", response, elapsed, True)
            provider.record_fail()
            return DispatchResult(pid, provider.name, "broadcast", "", elapsed, False, "Empty")
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            provider.record_fail()
            return DispatchResult(pid, provider.name, "broadcast", "", elapsed, False, str(e)[:100])

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_query, item): item[0] for item in available}
        try:
            for future in as_completed(futures, timeout=180):
                try:
                    results.append(future.result())
                except Exception as e:
                    pid = futures[future]
                    results.append(DispatchResult(pid, pid, "broadcast", "", 0, False, str(e)[:100]))
        except TimeoutError:
            # Gracefully handle partial results — mark unfinished providers as timeout
            timed_out = [pid for f, pid in futures.items() if not f.done()]
            log.warning("Broadcast timeout: %d providers unfinished: %s", len(timed_out), timed_out)
            for f, pid in futures.items():
                if not f.done():
                    results.append(DispatchResult(pid, pid, "broadcast", "", 180000, False, "Timeout"))
                    f.cancel()

    return results


def _similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity (Jaccard)."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def consensus_dispatch(prompt: str) -> dict[str, Any]:
    """Weighted consensus with semantic grouping."""
    results = broadcast_dispatch(prompt)
    successful = [r for r in results if r.success and r.response]

    if not successful:
        return {"consensus": "FAILED", "votes": 0, "results": []}

    # Build weighted responses
    weighted = []
    for r in successful:
        provider = PROVIDERS.get(r.provider_id)
        w = provider.weight if provider else 1.0
        weighted.append({"provider": r.provider_name, "weight": w,
                         "response": r.response[:500], "latency_ms": r.latency_ms,
                         "group": -1})

    # Group similar responses (Jaccard > 0.3 = same cluster)
    groups: list[list[int]] = []
    for i, item in enumerate(weighted):
        placed = False
        for g in groups:
            rep = weighted[g[0]]
            if _similarity(item["response"], rep["response"]) > 0.3:
                g.append(i)
                placed = True
                break
        if not placed:
            groups.append([i])

    # Pick group with highest combined weight
    best_group = max(groups, key=lambda g: sum(weighted[i]["weight"] for i in g))
    group_weight = sum(weighted[i]["weight"] for i in best_group)
    total_weight = sum(x["weight"] for x in weighted)

    # Within best group, pick highest-weight response
    best_idx = max(best_group, key=lambda i: weighted[i]["weight"])
    best = weighted[best_idx]

    for i, item in enumerate(weighted):
        item["group"] = next((gi for gi, g in enumerate(groups) if i in g), -1)

    return {
        "consensus": best["response"],
        "best_provider": best["provider"],
        "votes": len(successful),
        "groups": len(groups),
        "group_size": len(best_group),
        "total_weight": round(total_weight, 2),
        "quorum": round(group_weight / total_weight, 2) if total_weight else 0,
        "details": weighted,
    }


# ── Cowork Integration (395 scripts in jarvis-cowork/dev/) ────────────────

COWORK_PATH = Path("F:/BUREAU/jarvis-cowork")
COWORK_DEV = COWORK_PATH / "dev"

# Cowork categories → script patterns
COWORK_CATEGORIES: dict[str, list[str]] = {
    "health":    ["health_checker", "cluster_health_watchdog", "autonomous_health_guard", "cowork_health_summary"],
    "trading":   ["auto_trader", "crypto_price_alert", "trading_signal_aggregator"],
    "system":    ["gpu_optimizer", "gpu_thermal_guard", "driver_checker", "display_manager"],
    "code":      ["code_generator", "code_reviewer", "ia_autonomous_coder", "continuous_coder"],
    "deploy":    ["auto_deployer", "deployment_manager"],
    "monitor":   ["auto_monitor", "event_bus_monitor", "api_monitor", "dispatch_realtime_monitor"],
    "cluster":   ["cluster_autotuner", "cluster_benchmark_auto", "cluster_failover_manager",
                  "cluster_model_rotator", "cluster_sync", "cluster_warmup"],
    "email":     ["email_reader"],
    "report":    ["auto_reporter", "daily_cowork_report", "cowork_health_summary"],
    "browser":   ["browser_pilot", "browser_automation"],
    "scheduler": ["cowork_scheduler", "auto_scheduler"],
    "security":  ["dependency_vulnerability_scanner", "security_auditor"],
}


def run_cowork_script(script_name: str, args: list[str] = None, timeout: int = 60) -> dict:
    """Execute a cowork script from jarvis-cowork/dev/."""
    script = COWORK_DEV / f"{script_name}.py"
    if not script.exists():
        return {"success": False, "error": f"Script not found: {script}"}

    cmd = [sys.executable, str(script)]
    if args:
        cmd.extend(args)
    else:
        cmd.append("--once")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(COWORK_PATH))
        return {
            "success": result.returncode == 0,
            "output": result.stdout[:2000],
            "error": result.stderr[:500] if result.returncode != 0 else "",
            "script": script_name,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout {timeout}s", "script": script_name}
    except Exception as e:
        return {"success": False, "error": str(e)[:200], "script": script_name}


def dispatch_cowork(category: str) -> list[dict]:
    """Run all cowork scripts for a category."""
    scripts = COWORK_CATEGORIES.get(category, [])
    if not scripts:
        return [{"error": f"Unknown category: {category}"}]

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(run_cowork_script, s): s for s in scripts}
        for f in as_completed(futures, timeout=120):
            try:
                results.append(f.result())
            except Exception as e:
                results.append({"success": False, "error": str(e)[:100], "script": futures[f]})
    return results


def list_cowork_scripts() -> list[str]:
    """List all available cowork scripts."""
    if not COWORK_DEV.exists():
        return []
    return sorted([f.stem for f in COWORK_DEV.glob("*.py")])


# ── Telegram Notification ─────────────────────────────────────────────────

def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        log.warning("Telegram not configured (TELEGRAM_TOKEN or TELEGRAM_CHAT missing)")
        return False
    try:
        # Truncate to Telegram limit
        msg = message[:4000]
        cmd = [
            "curl", "-s", "--max-time", "10",
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            "-d", f"chat_id={TELEGRAM_CHAT}",
            "-d", f"text={msg}",
            "-d", f"parse_mode={parse_mode}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        data = json.loads(result.stdout)
        if data.get("ok"):
            log.info("Telegram: sent (%d chars)", len(msg))
            return True
        log.warning("Telegram error: %s", data.get("description", "unknown"))
        return False
    except Exception as e:
        log.error("Telegram failed: %s", e)
        return False


def _escape_html(text: str) -> str:
    """Escape HTML special chars for Telegram. Strip code blocks."""
    text = re.sub(r"```\w*\n?", "", text)  # remove code fences
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_dispatch_result(result: DispatchResult) -> str:
    """Format a dispatch result for Telegram."""
    status = "OK" if result.success else "FAIL"
    resp = _escape_html(result.response[:800])
    return (
        f"[{status}] <b>{result.agent}</b> via {result.provider_name}\n"
        f"{result.latency_ms:.0f}ms\n"
        f"{resp}"
    )


def format_consensus(data: dict) -> str:
    """Format consensus result for Telegram."""
    lines = [
        f"🗳 <b>CONSENSUS</b> — {data['votes']} votes, weight={data['total_weight']}",
        f"🏆 Best: {data.get('best_provider', '?')}",
        "",
        data.get("consensus", "NO CONSENSUS")[:1500],
        "",
        "📊 Détails:",
    ]
    for d in data.get("details", []):
        lines.append(f"  • {d['provider']} (w={d['weight']}) {d['latency_ms']:.0f}ms")
    return "\n".join(lines)


# ── Health Check ──────────────────────────────────────────────────────────

def warm_up_local_nodes():
    """Pre-warm M1 and OL1 to trigger model loading."""
    log.info("Warming up local nodes...")
    def _warm(pid):
        p = PROVIDERS.get(pid)
        if not p:
            return
        try:
            query_provider(p, "OK", use_cache=False)
            log.info("  %s warmed up", pid)
        except Exception as e:
            log.warning("  %s warm-up failed: %s", pid, str(e)[:80])

    with ThreadPoolExecutor(max_workers=3) as pool:
        pool.map(_warm, ["M1", "OL1"])


def health_check() -> dict[str, dict]:
    """Check all providers health in parallel."""
    results = {}

    def _check(pid, provider):
        start = time.time()
        try:
            response = query_provider(provider, "say OK in one word")
            elapsed = (time.time() - start) * 1000
            ok = bool(response and len(response) < 200)
            return pid, {"status": "OK" if ok else "EMPTY", "latency_ms": round(elapsed),
                         "response": response[:50], "circuit": provider.circuit_open}
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return pid, {"status": "FAIL", "latency_ms": round(elapsed),
                         "error": str(e)[:100], "circuit": provider.circuit_open}

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_check, pid, p) for pid, p in PROVIDERS.items()]
        for f in as_completed(futures, timeout=120):
            try:
                pid, data = f.result()
                results[pid] = data
            except Exception:
                pass

    return results


# ── OpenClaw Integration ──────────────────────────────────────────────────

def dispatch_via_openclaw(text: str, agent: str = None) -> dict:
    """Dispatch through OpenClaw WS API at :9742, then route to providers."""
    if not agent:
        agent = classify_intent(text)

    # First try OpenClaw gateway
    try:
        cmd = [
            "curl", "-s", "--max-time", "30",
            "http://127.0.0.1:9742/api/openclaw/route",
            "-X", "POST", "-H", "Content-Type: application/json",
            "-d", json.dumps({"text": text, "agent": agent}),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        data = json.loads(result.stdout)
        if data.get("response"):
            return {"source": "openclaw", "agent": agent, "response": data["response"]}
    except Exception as e:
        log.debug("OpenClaw gateway failed: %s", e)

    # Fallback: direct dispatch to providers
    dispatch_result = dispatch_to_agent(agent, text)
    return {
        "source": "direct",
        "agent": agent,
        "provider": dispatch_result.provider_name,
        "response": dispatch_result.response,
        "latency_ms": dispatch_result.latency_ms,
        "success": dispatch_result.success,
    }


# ── CLI Entry Point ──────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS DevOps Orchestrator")
    parser.add_argument("--health", action="store_true", help="Health check all providers")
    parser.add_argument("--dispatch", type=str, help="Smart dispatch a message")
    parser.add_argument("--broadcast", type=str, help="Broadcast to all providers")
    parser.add_argument("--consensus", type=str, help="Weighted consensus vote")
    parser.add_argument("--agent", type=str, help="Force specific OpenClaw agent")
    parser.add_argument("--telegram", action="store_true", help="Send results to Telegram")
    parser.add_argument("--openclaw", action="store_true", help="Route via OpenClaw gateway")
    parser.add_argument("--cowork", type=str, help="Run cowork scripts by category")
    parser.add_argument("--cowork-list", action="store_true", help="List cowork categories")
    parser.add_argument("--full-test", action="store_true", help="Full integration test all providers + Telegram")
    parser.add_argument("--metrics", action="store_true", help="Show per-provider metrics")
    parser.add_argument("--pipeline", type=str, help="Run a long task through the circulating pipeline")
    parser.add_argument("--pipeline-list", action="store_true", help="List recent pipelines")
    parser.add_argument("--pipeline-resume", type=str, help="Resume an incomplete pipeline by ID")
    parser.add_argument("--daemon", action="store_true", help="Continuous loop: health → dispatch → audit → repeat")
    parser.add_argument("--interval", type=int, default=300, help="Daemon loop interval in seconds (default 300)")
    args = parser.parse_args()

    if args.metrics:
        stats = METRICS.get_stats(hours=24)
        if not stats:
            print("No metrics yet. Run some dispatches first.")
            return
        print("=== PROVIDER METRICS (last 24h) ===")
        lines = ["METRICS (24h)"]
        for pid in sorted(stats.keys()):
            s = stats[pid]
            prov = PROVIDERS.get(pid)
            name = prov.name if prov else pid
            line = f"{pid:15s} | {s['total']:3d} req | SR={s['sr']:5.1f}% | avg={s['avg_ms']:5d}ms | w={prov.weight if prov else '?'}"
            print(line)
            lines.append(line)
        if args.telegram:
            send_telegram("\n".join(lines))

        # Auto-adjust weights
        METRICS.adjust_weights()
        return

    if args.health:
        print("🔍 Health check all providers...")
        results = health_check()
        lines = ["🏥 <b>DEVOPS ORCHESTRATOR — HEALTH CHECK</b>", ""]
        for pid, data in sorted(results.items()):
            icon = "🟢" if data["status"] == "OK" else "🔴"
            prov = PROVIDERS[pid]
            line = f"{icon} <b>{pid}</b> ({prov.name}) — {data['status']} {data.get('latency_ms',0)}ms"
            if data.get("circuit"):
                line += " ⚡CIRCUIT OPEN"
            lines.append(line)
        msg = "\n".join(lines)
        print(msg.replace("<b>", "").replace("</b>", ""))
        if args.telegram:
            send_telegram(msg)
        return

    if args.dispatch:
        if args.openclaw:
            result = dispatch_via_openclaw(args.dispatch, args.agent)
            print(f"[{result['agent']}→{result.get('provider','openclaw')}] {result.get('response','')[:500]}")
            if args.telegram and result.get("response"):
                send_telegram(f"🤖 <b>[{result['agent']}]</b>\n{result.get('response','')[:2000]}")
        else:
            result = smart_dispatch(args.dispatch)
            print(format_dispatch_result(result).replace("<b>", "").replace("</b>", ""))
            if args.telegram:
                send_telegram(format_dispatch_result(result))
        return

    if args.broadcast:
        results = broadcast_dispatch(args.broadcast)
        for r in sorted(results, key=lambda x: -x.latency_ms):
            status = "✅" if r.success else "❌"
            print(f"{status} [{r.provider_name}] {r.latency_ms:.0f}ms: {r.response[:100]}")
        if args.telegram:
            lines = ["📡 <b>BROADCAST RESULTS</b>", ""]
            for r in results:
                s = "✅" if r.success else "❌"
                lines.append(f"{s} {r.provider_name} ({r.latency_ms:.0f}ms): {r.response[:200]}")
            send_telegram("\n".join(lines))
        return

    if args.consensus:
        data = consensus_dispatch(args.consensus)
        msg = format_consensus(data)
        print(msg.replace("<b>", "").replace("</b>", ""))
        if args.telegram:
            send_telegram(msg)
        return

    if args.cowork_list:
        print("COWORK CATEGORIES:")
        for cat, scripts in sorted(COWORK_CATEGORIES.items()):
            print(f"  {cat}: {', '.join(scripts)}")
        print(f"\nTotal scripts available: {len(list_cowork_scripts())}")
        return

    if args.cowork:
        print(f"Running cowork category: {args.cowork}")
        results = dispatch_cowork(args.cowork)
        lines = [f"COWORK [{args.cowork}]", ""]
        for r in results:
            s = "OK" if r.get("success") else "FAIL"
            script = r.get("script", "?")
            output = r.get("output", r.get("error", ""))[:300]
            lines.append(f"[{s}] {script}: {output}")
            print(f"[{s}] {script}: {output[:200]}")
        if args.telegram:
            send_telegram("\n".join(lines))
        return

    if args.full_test:
        print("=== FULL INTEGRATION TEST ===")
        test_prompts = {
            "coding":          "ecris une fonction Python qui calcule fibonacci",
            "deep-reasoning":  "explique pourquoi 0.1 + 0.2 != 0.3 en informatique",
            "trading":         "analyse la tendance BTC/USDT",
            "system-ops":      "quel est le statut du cluster GPU",
            "recherche-synthese": "cherche les dernieres news sur Claude AI",
        }
        all_results = []
        lines = ["FULL INTEGRATION TEST", ""]
        for agent, prompt in test_prompts.items():
            print(f"\nTesting [{agent}]: {prompt[:40]}...")
            result = dispatch_to_agent(agent, prompt)
            all_results.append(result)
            s = "OK" if result.success else "FAIL"
            print(f"  [{s}] {result.provider_name} {result.latency_ms:.0f}ms: {result.response[:100]}")
            lines.append(f"[{s}] {agent} -> {result.provider_name} ({result.latency_ms:.0f}ms)")
            if result.response:
                lines.append(f"  {result.response[:200]}")
            lines.append("")

        ok = sum(1 for r in all_results if r.success)
        summary = f"\nResult: {ok}/{len(all_results)} SUCCESS"
        print(summary)
        lines.append(summary)

        if args.telegram:
            send_telegram("\n".join(lines))
        return

    if args.pipeline:
        from pipeline_engine import run_pipeline
        print(f"=== PIPELINE MODE ===")
        pipeline = run_pipeline(args.pipeline, telegram=args.telegram)
        print(f"\nPipeline {pipeline.id} — {pipeline.status}")
        ok = sum(1 for s in pipeline.sections if s.status in ('completed', 'cached'))
        print(f"Sections: {ok}/{len(pipeline.sections)}")
        if pipeline.result:
            print(f"\n{'='*60}\n{pipeline.result[:2000]}\n{'='*60}")
        return

    if args.pipeline_list:
        from pipeline_engine import list_pipelines, _init_db
        conn = _init_db()
        pipelines = list_pipelines(conn)
        if not pipelines:
            print("No pipelines found.")
        else:
            for p in pipelines:
                print(f"  {p['id']}  {p['status']:10s}  {p['completed_sections']}/{p['total_sections']}  {p['name']}")
        conn.close()
        return

    if args.pipeline_resume:
        from pipeline_engine import resume_pipeline, _init_db
        conn = _init_db()
        pipeline = resume_pipeline(conn, args.pipeline_resume)
        if pipeline:
            print(f"Pipeline {pipeline.id} — {pipeline.status}")
        conn.close()
        return

    if args.daemon:
        print(f"=== DAEMON MODE (interval={args.interval}s) ===")
        warm_up_local_nodes()
        cycle = 0
        while True:
            cycle += 1
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"\n[Cycle {cycle} @ {ts}]")

            # Phase 1: Health check
            health = health_check()
            alive = sum(1 for v in health.values() if v["status"] == "OK")
            total = len(health)
            print(f"  Health: {alive}/{total} providers alive")

            # Phase 2: Audit cowork
            cowork_results = dispatch_cowork("health")
            cw_ok = sum(1 for r in cowork_results if r.get("success"))
            print(f"  Cowork health: {cw_ok}/{len(cowork_results)} scripts OK")

            # Phase 3: Test dispatch
            test_result = dispatch_to_agent("fast-chat", "status report bref du systeme")
            print(f"  Dispatch test: {'OK' if test_result.success else 'FAIL'} via {test_result.provider_name}")

            # Phase 4: Report to Telegram
            # Phase 4: Dynamic weight adjustment
            METRICS.adjust_weights()

            report = (
                f"[Cycle {cycle}] {ts}\n"
                f"Cluster: {alive}/{total} alive\n"
                f"Cowork: {cw_ok}/{len(cowork_results)} OK\n"
                f"Dispatch: {'OK' if test_result.success else 'FAIL'} ({test_result.provider_name})"
            )
            if test_result.response:
                report += f"\n{test_result.response[:500]}"
            send_telegram(report)

            print(f"  Sleeping {args.interval}s...")
            time.sleep(args.interval)
        return

    parser.print_help()


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    main()
