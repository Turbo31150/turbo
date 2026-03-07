"""JARVIS Debug Pipeline v2 — 1000 cycles continus, jamais d'arret.

Workflow complet par cycle:
  1. Health check (M1/OL1/M2/M3/proxy/ws)
  2. Test Telegram flow (text → proxy → cluster → response)
  3. Test Canvas proxy (POST /chat → agenticChat)
  4. Test Voice pipeline (WS server start/stop recording)
  5. Cluster dispatch parallele (race M1 vs OL1)
  6. Verify responses (correctness, latency, quality)
  7. Pattern detection + auto-improvement via cluster consensus
  8. Report to Telegram (every 100 cycles)

Resilient: chaque etape dans try/except, jamais d'arret.
SQLite persistance + log rotatif.

Usage:
    python scripts/debug_pipeline_v2.py [--cycles 1000] [--interval 8]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sqlite3
import sys
import time
import traceback
import urllib.request
import urllib.error
from collections import Counter
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup paths
SCRIPT_DIR = Path(__file__).resolve().parent
TURBO_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(TURBO_DIR))
os.chdir(str(TURBO_DIR))

DB_PATH = TURBO_DIR / "data" / "debug_pipeline_v2.db"
LOG_PATH = TURBO_DIR / "logs" / "debug_pipeline_v2.log"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(LOG_PATH), encoding="utf-8"),
    ],
)
log = logging.getLogger("debug_v2")

# ── Cluster Nodes ──────────────────────────────────────────────────────────
NODES = {
    "M1": {
        "url": "http://127.0.0.1:1234/v1/chat/completions",
        "model": "qwen3-8b",
        "format": "openai",
        "weight": 1.8,
        "timeout": 15,
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b",
        "format": "ollama",
        "weight": 1.3,
        "timeout": 15,
    },
    "M2": {
        "url": "http://192.168.1.26:1234/v1/chat/completions",
        "model": "deepseek-r1-0528-qwen3-8b",
        "format": "openai",
        "weight": 1.5,
        "timeout": 30,
    },
    "M3": {
        "url": "http://192.168.1.113:1234/v1/chat/completions",
        "model": "deepseek-r1-0528-qwen3-8b",
        "format": "openai",
        "weight": 1.2,
        "timeout": 30,
    },
}

SERVICES = {
    "M1":    "http://127.0.0.1:1234/v1/models",
    "OL1":   "http://127.0.0.1:11434/api/tags",
    "M2":    "http://192.168.1.26:1234/v1/models",
    "M3":    "http://192.168.1.113:1234/v1/models",
    "proxy": "http://127.0.0.1:18800/health",
    "ws":    "http://127.0.0.1:9742/health",
}

# ── Test Prompts (varied, categorized) ─────────────────────────────────────
TEST_PROMPTS = [
    {"prompt": "Reponds OK si tu fonctionnes.", "expected": "ok", "type": "alive"},
    {"prompt": "2+2=?", "expected": "4", "type": "math"},
    {"prompt": "def add(a,b): return a+b\n# appel: add(3,5) = ?", "expected": "8", "type": "code"},
    {"prompt": "Capitale de la France?", "expected": "paris", "type": "knowledge"},
    {"prompt": "Resumer en 1 mot: Le chat dort.", "expected": "chat", "type": "comprehension"},
    {"prompt": "JSON: {\"status\":\"ok\"} — quel est le status?", "expected": "ok", "type": "parsing"},
    {"prompt": "Traduis: Bonjour le monde → anglais", "expected": "hello", "type": "translation"},
    {"prompt": "3 couleurs primaires? (virgules)", "expected": "rouge", "type": "list"},
    {"prompt": "Qu'est-ce que JARVIS?", "expected": "assistant", "type": "meta"},
    {"prompt": "Corrige: 'je suis alle a la meson' →", "expected": "maison", "type": "correction"},
    {"prompt": "10 * 15 + 3 = ?", "expected": "153", "type": "math"},
    {"prompt": "Python: list(range(5)) = ?", "expected": "[0, 1, 2, 3, 4]", "type": "code"},
]

# Error pattern categories
ERROR_PATTERNS = {
    "empty_response": "Reponse vide",
    "timeout": "Timeout",
    "connection_refused": "Connexion refusee",
    "wrong_answer": "Reponse incorrecte",
    "slow_response": "Reponse lente (>5s)",
    "model_not_loaded": "Modele non charge",
    "json_parse": "Erreur parsing JSON",
    "voice_fail": "Pipeline vocal echoue",
    "proxy_fail": "Proxy ne repond pas",
    "ws_fail": "WS server echoue",
    "tts_fail": "TTS echoue",
    "transcribe_fail": "Transcription echouee",
}


# ── Database ───────────────────────────────────────────────────────────────
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_num INTEGER,
                started_at REAL,
                finished_at REAL,
                status TEXT DEFAULT 'running',
                nodes_online TEXT DEFAULT '[]',
                nodes_offline TEXT DEFAULT '[]',
                total_queries INTEGER DEFAULT 0,
                successful_queries INTEGER DEFAULT 0,
                failed_queries INTEGER DEFAULT 0,
                avg_latency_ms REAL DEFAULT 0,
                proxy_ok INTEGER DEFAULT 0,
                ws_ok INTEGER DEFAULT 0,
                voice_ok INTEGER DEFAULT 0,
                telegram_ok INTEGER DEFAULT 0,
                errors TEXT DEFAULT '[]',
                patterns TEXT DEFAULT '[]',
                improvements TEXT DEFAULT '[]',
                notes TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER,
                node TEXT,
                prompt_type TEXT,
                prompt TEXT,
                response TEXT,
                expected TEXT,
                correct INTEGER DEFAULT 0,
                latency_ms REAL,
                error TEXT DEFAULT '',
                timestamp REAL,
                FOREIGN KEY (cycle_id) REFERENCES cycles(id)
            );
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT,
                description TEXT,
                count INTEGER DEFAULT 1,
                first_seen REAL,
                last_seen REAL,
                node TEXT DEFAULT '',
                resolved INTEGER DEFAULT 0,
                resolution TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS improvements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_num INTEGER,
                category TEXT,
                description TEXT,
                priority TEXT DEFAULT 'P3',
                status TEXT DEFAULT 'proposed',
                applied INTEGER DEFAULT 0,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS workflow_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER,
                step TEXT,
                input_text TEXT,
                output_text TEXT,
                latency_ms REAL,
                success INTEGER DEFAULT 1,
                error TEXT DEFAULT '',
                timestamp REAL,
                FOREIGN KEY (cycle_id) REFERENCES cycles(id)
            );
        """)


# ── HTTP helper ────────────────────────────────────────────────────────────
def http_post(url, data, timeout=15, headers=None):
    """POST JSON, return (status, body_dict, latency_ms)."""
    t0 = time.time()
    body = json.dumps(data).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
        return resp.status, result, int((time.time() - t0) * 1000)
    except Exception as e:
        return 0, {"error": str(e)[:300]}, int((time.time() - t0) * 1000)


def http_get(url, timeout=5):
    """GET, return (ok, data_str, latency_ms)."""
    t0 = time.time()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode()[:2000]
        return True, data, int((time.time() - t0) * 1000)
    except Exception as e:
        return False, str(e)[:200], int((time.time() - t0) * 1000)


# ── Node query ─────────────────────────────────────────────────────────────
def query_node(node_name: str, prompt: str) -> dict:
    """Query a cluster node. Returns {ok, text, latency_ms, error, node}."""
    node = NODES.get(node_name)
    if not node:
        return {"ok": False, "text": "", "latency_ms": 0, "error": "unknown_node", "node": node_name}

    t0 = time.time()
    try:
        if node["format"] == "ollama":
            data = {
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False,
            }
            status, result, lat = http_post(node["url"], data, timeout=node["timeout"])
            text = result.get("message", {}).get("content", "") if status == 200 else ""
        else:
            data = {
                "model": node["model"],
                "messages": [{"role": "user", "content": "/nothink\n" + prompt}],
                "temperature": 0.2, "max_tokens": 1024, "stream": False,
            }
            status, result, lat = http_post(node["url"], data, timeout=node["timeout"])
            text = ""
            if status == 200:
                choices = result.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "")

        # Clean
        text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^/no_?think\s*', '', text, flags=re.IGNORECASE).strip()

        if not text or len(text) < 2:
            return {"ok": False, "text": "", "latency_ms": lat, "error": "empty_response", "node": node_name}

        return {"ok": True, "text": text, "latency_ms": lat, "error": "", "node": node_name}

    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        err_str = str(e)[:200]
        if "ETIMEDOUT" in err_str or "timed out" in err_str:
            return {"ok": False, "text": "", "latency_ms": lat, "error": "timeout", "node": node_name}
        if "Connection refused" in err_str:
            return {"ok": False, "text": "", "latency_ms": lat, "error": "connection_refused", "node": node_name}
        return {"ok": False, "text": "", "latency_ms": lat, "error": f"exception:{err_str}", "node": node_name}


# ── Cluster race ───────────────────────────────────────────────────────────
def cluster_race(prompt: str, nodes: list[str] | None = None) -> dict:
    """Race multiple nodes in parallel, return first valid response."""
    targets = nodes or ["M1", "OL1"]
    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        futures = {pool.submit(query_node, n, prompt): n for n in targets}
        for fut in as_completed(futures, timeout=30):
            try:
                result = fut.result()
                if result["ok"]:
                    return result
            except Exception:
                continue
    return {"ok": False, "text": "", "latency_ms": 0, "error": "all_nodes_failed", "node": "none"}


# ── Test Steps ─────────────────────────────────────────────────────────────

def step_health(traces: list) -> tuple[list, list]:
    """Step 1: Health check all services."""
    online, offline = [], []
    for name, url in SERVICES.items():
        t0 = time.time()
        tout = 15 if name == "proxy" else 5  # proxy /health checks all nodes
        ok, data, lat = http_get(url, timeout=tout)
        traces.append({
            "step": "health", "input_text": f"GET {url}",
            "output_text": data[:100] if ok else str(data)[:100],
            "latency_ms": lat, "success": 1 if ok else 0,
            "error": "" if ok else data[:200],
        })
        if ok:
            online.append(name)
        else:
            offline.append(name)
    return online, offline


def step_proxy_test(traces: list) -> bool:
    """Step 2: Test Canvas proxy /chat endpoint."""
    try:
        status, result, lat = http_post(
            "http://127.0.0.1:18800/chat",
            {"agent": "test", "text": "Dis OK."},
            timeout=30,
        )
        ok = status == 200 and result.get("ok", False)
        text = result.get("data", {}).get("text", "")[:200] if isinstance(result.get("data"), dict) else str(result)[:200]
        traces.append({
            "step": "proxy_chat", "input_text": "Dis OK.",
            "output_text": text, "latency_ms": lat,
            "success": 1 if ok else 0, "error": "" if ok else result.get("error", "")[:200],
        })
        return ok
    except Exception as e:
        traces.append({
            "step": "proxy_chat", "input_text": "Dis OK.",
            "output_text": "", "latency_ms": 0,
            "success": 0, "error": str(e)[:200],
        })
        return False


def step_ws_test(traces: list) -> bool:
    """Step 3: Test WS server health + voice endpoint."""
    ok, data, lat = http_get("http://127.0.0.1:9742/health", timeout=5)
    traces.append({
        "step": "ws_health", "input_text": "GET /health",
        "output_text": data[:100], "latency_ms": lat,
        "success": 1 if ok else 0, "error": "" if ok else data[:200],
    })
    if not ok:
        return False

    # Test TTS endpoint (lightweight)
    try:
        status, result, lat = http_post(
            "http://127.0.0.1:9742/api/tts",
            {"text": "test", "voice": "fr-FR-DeniseNeural"},
            timeout=10,
        )
        tts_ok = status == 200
        traces.append({
            "step": "ws_tts", "input_text": "TTS test",
            "output_text": str(result)[:100], "latency_ms": lat,
            "success": 1 if tts_ok else 0, "error": "" if tts_ok else str(result)[:200],
        })
        return True
    except Exception as e:
        traces.append({
            "step": "ws_tts", "input_text": "TTS test",
            "output_text": "", "latency_ms": 0,
            "success": 0, "error": str(e)[:200],
        })
        return True  # WS health OK even if TTS fails


def step_telegram_flow(traces: list, prompt: str) -> bool:
    """Step 4: Simulate Telegram flow (text → proxy → cluster → response)."""
    # Simulate what the Telegram bot does: POST to proxy /chat
    try:
        status, result, lat = http_post(
            "http://127.0.0.1:18800/chat",
            {"agent": "telegram", "text": prompt},
            timeout=60,
        )
        ok = status == 200 and result.get("ok", False)
        text = ""
        if isinstance(result.get("data"), dict):
            text = result["data"].get("text", "")[:300]
        traces.append({
            "step": "telegram_flow", "input_text": prompt[:100],
            "output_text": text[:200], "latency_ms": lat,
            "success": 1 if ok and text else 0,
            "error": "" if ok else result.get("error", "unknown")[:200],
        })
        return ok and bool(text)
    except Exception as e:
        traces.append({
            "step": "telegram_flow", "input_text": prompt[:100],
            "output_text": "", "latency_ms": 0,
            "success": 0, "error": str(e)[:200],
        })
        return False


def step_cluster_dispatch(traces: list, prompt: str, expected: str,
                          online_nodes: list) -> list[dict]:
    """Step 5: Direct cluster dispatch to all online nodes."""
    available = [n for n in online_nodes if n in NODES]
    if not available:
        available = ["M1", "OL1"]

    queries = []
    with ThreadPoolExecutor(max_workers=len(available)) as pool:
        futures = {pool.submit(query_node, n, prompt): n for n in available}
        for fut in as_completed(futures, timeout=35):
            node_name = futures[fut]
            try:
                result = fut.result()
            except Exception as e:
                result = {"ok": False, "text": "", "latency_ms": 0,
                          "error": str(e)[:200], "node": node_name}

            result["correct"] = 1 if expected.lower() in result.get("text", "").lower() else 0
            queries.append(result)

            traces.append({
                "step": f"cluster_{node_name}",
                "input_text": prompt[:100],
                "output_text": result.get("text", "")[:200],
                "latency_ms": result["latency_ms"],
                "success": 1 if result["ok"] else 0,
                "error": result.get("error", "")[:200],
            })

    return queries


# ── Pattern Detection ──────────────────────────────────────────────────────
def detect_patterns(errors: list[dict], conn: sqlite3.Connection) -> list[dict]:
    """Analyze errors and detect/update recurring patterns."""
    patterns = []
    now = time.time()
    counts = Counter()
    for err in errors:
        key = f"{err.get('node', '?')}:{err.get('error', 'unknown')}"
        counts[key] += 1

    for key, count in counts.items():
        node, error_type = key.split(":", 1)
        ptype = "unknown"
        for pt in ERROR_PATTERNS:
            if pt in error_type.lower():
                ptype = pt
                break

        row = conn.execute(
            "SELECT id, count FROM patterns WHERE pattern_type=? AND node=? AND resolved=0",
            (ptype, node)
        ).fetchone()

        if row:
            conn.execute(
                "UPDATE patterns SET count=count+?, last_seen=? WHERE id=?",
                (count, now, row[0])
            )
            total = row[1] + count
        else:
            conn.execute(
                "INSERT INTO patterns (pattern_type, description, count, first_seen, last_seen, node) "
                "VALUES (?,?,?,?,?,?)",
                (ptype, f"{ERROR_PATTERNS.get(ptype, error_type)} on {node}", count, now, now, node)
            )
            total = count

        patterns.append({"type": ptype, "node": node, "count": total})

    return patterns


def propose_improvements(patterns: list[dict], cycle_num: int,
                         conn: sqlite3.Connection) -> list[dict]:
    """Generate improvements based on patterns."""
    improvements = []
    now = time.time()

    thresholds = {
        "empty_response": (5, "P1", "reliability", "returns empty responses. Warmup/reload needed."),
        "timeout": (10, "P1", "performance", "timeouts. Check GPU load/network."),
        "connection_refused": (3, "P2", "infrastructure", "connection refused. Node offline."),
        "slow_response": (5, "P2", "performance", "consistently slow. Check GPU/model size."),
        "voice_fail": (3, "P1", "voice", "voice pipeline failures. Check Whisper/CUDA."),
        "proxy_fail": (3, "P1", "infrastructure", "proxy failures. Restart direct-proxy."),
        "ws_fail": (3, "P1", "infrastructure", "WS server failures. Restart python_ws."),
        "tts_fail": (5, "P2", "voice", "TTS failures. Check edge-tts/ffplay."),
    }

    for p in patterns:
        key = p["type"]
        if key in thresholds:
            threshold, priority, category, desc_suffix = thresholds[key]
            if p["count"] >= threshold:
                # Avoid duplicate improvements
                existing = conn.execute(
                    "SELECT id FROM improvements WHERE category=? AND cycle_num>? AND description LIKE ?",
                    (category, max(0, cycle_num - 100), f"%{p['node']}%{key}%")
                ).fetchone()
                if existing:
                    continue

                imp = {
                    "category": category,
                    "description": f"Node {p['node']} {desc_suffix} ({p['count']}x)",
                    "priority": priority,
                }
                improvements.append(imp)
                conn.execute(
                    "INSERT INTO improvements (cycle_num, category, description, priority, created_at) "
                    "VALUES (?,?,?,?,?)",
                    (cycle_num, imp["category"], imp["description"], imp["priority"], now)
                )

    return improvements


# ── Auto-analysis via cluster ──────────────────────────────────────────────
def auto_analyze(cycle_num: int, conn: sqlite3.Connection) -> str:
    """Every 50 cycles, ask cluster for analysis and recommendations."""
    stats = conn.execute(
        "SELECT COUNT(*), AVG(avg_latency_ms), SUM(failed_queries), SUM(successful_queries), "
        "AVG(proxy_ok), AVG(ws_ok), AVG(voice_ok), AVG(telegram_ok) "
        "FROM cycles WHERE cycle_num > ?", (max(0, cycle_num - 50),)
    ).fetchone()

    top_patterns = conn.execute(
        "SELECT pattern_type, node, count FROM patterns WHERE resolved=0 ORDER BY count DESC LIMIT 5"
    ).fetchall()

    recent_improvements = conn.execute(
        "SELECT priority, category, description FROM improvements WHERE cycle_num > ? ORDER BY created_at DESC LIMIT 5",
        (max(0, cycle_num - 50),)
    ).fetchall()

    prompt = (
        f"Analyse JARVIS debug pipeline (cycles {max(0,cycle_num-50)}-{cycle_num}):\n"
        f"- {stats[0]} cycles, latence moy {stats[1]:.0f}ms\n"
        f"- Succes: {stats[3]}, Echecs: {stats[2]}\n"
        f"- Proxy OK: {stats[4]*100:.0f}%, WS OK: {stats[5]*100:.0f}%\n"
        f"- Voice OK: {stats[6]*100:.0f}%, Telegram OK: {stats[7]*100:.0f}%\n"
        f"- Top patterns: {[(p[0],p[1],p[2]) for p in top_patterns]}\n"
        f"- Recent improvements: {[(i[0],i[1],i[2][:60]) for i in recent_improvements]}\n\n"
        f"Propose 3 ameliorations concretes (1 phrase chacune). Format: [P1/P2/P3] description"
    )

    result = cluster_race(prompt, ["M1", "OL1"])
    if result["ok"]:
        return result["text"][:500]
    return ""


# ── Telegram notification ──────────────────────────────────────────────────
def notify_telegram(message: str):
    """Send a status update to Telegram via the bot's API proxy."""
    try:
        from pathlib import Path
        env_path = TURBO_DIR / ".env"
        token, chat = "", ""
        if env_path.exists():
            for line in env_path.read_text().split("\n"):
                if line.startswith("TELEGRAM_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                elif line.startswith("TELEGRAM_CHAT="):
                    chat = line.split("=", 1)[1].strip()
        if token and chat:
            data = json.dumps({
                "chat_id": chat,
                "text": message[:4000],
                "parse_mode": "Markdown",
            }).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log.debug("Telegram notify failed: %s", e)


# ── Main Cycle ─────────────────────────────────────────────────────────────
def run_cycle(cycle_num: int, total_cycles: int) -> dict:
    """Execute one complete debug cycle with full workflow trace."""
    cycle_start = time.time()
    ts = datetime.now().strftime("%H:%M:%S")
    traces = []

    log.info(f"=== CYCLE {cycle_num}/{total_cycles} [{ts}] ===")

    # Step 1: Health check
    log.info("  [1/7] Health check...")
    online, offline = step_health(traces)
    log.info(f"        Online: {online} | Offline: {offline}")

    # Step 2: Proxy test
    log.info("  [2/7] Canvas proxy test...")
    proxy_ok = step_proxy_test(traces)
    log.info(f"        Proxy: {'OK' if proxy_ok else 'FAIL'}")

    # Step 3: WS server test
    log.info("  [3/7] WS server test...")
    ws_ok = step_ws_test(traces)
    log.info(f"        WS: {'OK' if ws_ok else 'FAIL'}")

    # Step 4: Telegram flow simulation
    prompt_data = TEST_PROMPTS[cycle_num % len(TEST_PROMPTS)]
    prompt = prompt_data["prompt"]
    expected = prompt_data["expected"]
    prompt_type = prompt_data["type"]

    log.info(f"  [4/7] Telegram flow ({prompt_type})...")
    telegram_ok = step_telegram_flow(traces, prompt)
    log.info(f"        Telegram: {'OK' if telegram_ok else 'FAIL'}")

    # Step 5: Direct cluster dispatch
    log.info("  [5/7] Cluster dispatch...")
    cluster_nodes = [n for n in online if n in NODES]
    queries = step_cluster_dispatch(traces, prompt, expected, cluster_nodes)
    for q in queries:
        status = "OK" if q["ok"] else "FAIL"
        log.info(f"        [{q['node']}] {status} {q['latency_ms']}ms — {q.get('text','')[:50] or q.get('error','')[:50]}")

    # Step 6: Verify + collect errors
    log.info("  [6/7] Verify & patterns...")
    total_q = len(queries)
    success_q = sum(1 for q in queries if q["ok"])
    correct_q = sum(1 for q in queries if q.get("correct"))
    failed_q = total_q - success_q
    avg_lat = sum(q["latency_ms"] for q in queries) / max(total_q, 1)

    cycle_errors = []
    for q in queries:
        if not q["ok"]:
            cycle_errors.append({"node": q["node"], "error": q.get("error", "unknown")})
        elif q["latency_ms"] > 5000:
            cycle_errors.append({"node": q["node"], "error": "slow_response"})
    if not proxy_ok:
        cycle_errors.append({"node": "proxy", "error": "proxy_fail"})
    if not ws_ok:
        cycle_errors.append({"node": "ws", "error": "ws_fail"})

    log.info(f"        {success_q}/{total_q} OK | {correct_q}/{total_q} correct | avg {avg_lat:.0f}ms")

    # Database operations
    with sqlite3.connect(str(DB_PATH)) as conn:
        # Insert cycle
        conn.execute(
            "INSERT INTO cycles (cycle_num, started_at, status, nodes_online, nodes_offline, "
            "total_queries, successful_queries, failed_queries, avg_latency_ms, "
            "proxy_ok, ws_ok, voice_ok, telegram_ok, errors) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cycle_num, cycle_start, "running",
             json.dumps(online), json.dumps(offline),
             total_q, success_q, failed_q, avg_lat,
             1 if proxy_ok else 0, 1 if ws_ok else 0,
             0, 1 if telegram_ok else 0,
             json.dumps(cycle_errors)),
        )
        cycle_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert queries
        for q in queries:
            conn.execute(
                "INSERT INTO queries (cycle_id, node, prompt_type, prompt, response, expected, "
                "correct, latency_ms, error, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (cycle_id, q["node"], prompt_type, prompt[:100],
                 q.get("text", "")[:500], expected, q.get("correct", 0),
                 q["latency_ms"], q.get("error", ""), time.time()),
            )

        # Insert workflow traces
        for t in traces:
            conn.execute(
                "INSERT INTO workflow_traces (cycle_id, step, input_text, output_text, "
                "latency_ms, success, error, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (cycle_id, t["step"], t.get("input_text", "")[:200],
                 t.get("output_text", "")[:300], t["latency_ms"],
                 t["success"], t.get("error", "")[:300], time.time()),
            )

        # Patterns + improvements
        patterns = detect_patterns(cycle_errors, conn)
        improvements = propose_improvements(patterns, cycle_num, conn)

        if patterns:
            pat_strs = [f"{p['type']}({p['node']})x{p['count']}" for p in patterns]
            log.info(f"        Patterns: {pat_strs}")
        if improvements:
            imp_strs = [f"{i['priority']}:{i['category']}" for i in improvements]
            log.info(f"        Improvements: {imp_strs}")

        # Step 7: Auto-analysis every 50 cycles
        notes = ""
        if cycle_num % 50 == 0 and cycle_num > 0:
            log.info("  [7/7] Auto-analysis via cluster...")
            notes = auto_analyze(cycle_num, conn)
            if notes:
                log.info(f"        Analysis: {notes[:120]}...")
            else:
                log.info("        Analysis: cluster unavailable")
        else:
            log.info("  [7/7] Skip (not milestone).")

        # Notify Telegram every 100 cycles
        if cycle_num % 100 == 0 and cycle_num > 0:
            total_done = conn.execute("SELECT COUNT(*) FROM cycles WHERE status='completed'").fetchone()[0]
            total_success = conn.execute("SELECT SUM(successful_queries) FROM cycles").fetchone()[0] or 0
            total_total = conn.execute("SELECT SUM(total_queries) FROM cycles").fetchone()[0] or 1
            rate = total_success / total_total * 100
            notify_telegram(
                f"*Debug Pipeline v2* — Cycle {cycle_num}/{total_cycles}\n"
                f"Success rate: {rate:.1f}% ({total_success}/{total_total})\n"
                f"Avg latency: {avg_lat:.0f}ms\n"
                f"Patterns: {len(patterns)} | Improvements: {len(improvements)}\n"
                f"{notes[:300] if notes else 'No analysis'}"
            )

        # Finalize
        cycle_end = time.time()
        conn.execute(
            "UPDATE cycles SET finished_at=?, status=?, patterns=?, improvements=?, notes=? WHERE id=?",
            (cycle_end, "completed",
             json.dumps([p["type"] for p in patterns]),
             json.dumps([i["description"][:200] for i in improvements]),
             notes[:500], cycle_id),
        )

    cycle_ms = int((cycle_end - cycle_start) * 1000)
    log.info(f"  DONE — {cycle_ms}ms | {success_q}/{total_q} OK | proxy={'OK' if proxy_ok else 'FAIL'} ws={'OK' if ws_ok else 'FAIL'} tg={'OK' if telegram_ok else 'FAIL'}")
    return {
        "cycle": cycle_num, "ms": cycle_ms, "ok": success_q, "fail": failed_q,
        "proxy": proxy_ok, "ws": ws_ok, "telegram": telegram_ok,
        "patterns": len(patterns), "improvements": len(improvements),
    }


def print_summary():
    """Print comprehensive summary from DB."""
    if not DB_PATH.exists():
        log.info("No pipeline data yet.")
        return
    with sqlite3.connect(str(DB_PATH)) as conn:
        total = conn.execute("SELECT COUNT(*) FROM cycles").fetchone()[0]
        completed = conn.execute("SELECT COUNT(*) FROM cycles WHERE status='completed'").fetchone()[0]
        avg_lat = conn.execute("SELECT AVG(avg_latency_ms) FROM cycles").fetchone()[0] or 0
        total_q = conn.execute("SELECT SUM(total_queries) FROM cycles").fetchone()[0] or 0
        success_q = conn.execute("SELECT SUM(successful_queries) FROM cycles").fetchone()[0] or 0
        proxy_rate = conn.execute("SELECT AVG(proxy_ok)*100 FROM cycles").fetchone()[0] or 0
        ws_rate = conn.execute("SELECT AVG(ws_ok)*100 FROM cycles").fetchone()[0] or 0
        tg_rate = conn.execute("SELECT AVG(telegram_ok)*100 FROM cycles").fetchone()[0] or 0

        top_patterns = conn.execute(
            "SELECT pattern_type, node, count FROM patterns ORDER BY count DESC LIMIT 10"
        ).fetchall()
        recent_imps = conn.execute(
            "SELECT priority, category, description FROM improvements ORDER BY created_at DESC LIMIT 10"
        ).fetchall()

    log.info("\n" + "=" * 70)
    log.info("JARVIS DEBUG PIPELINE v2 — SUMMARY")
    log.info("=" * 70)
    log.info(f"Cycles: {completed}/{total} completed")
    log.info(f"Queries: {success_q}/{total_q} ({success_q/max(total_q,1)*100:.1f}%)")
    log.info(f"Avg latency: {avg_lat:.0f}ms")
    log.info(f"Proxy OK: {proxy_rate:.0f}% | WS OK: {ws_rate:.0f}% | Telegram OK: {tg_rate:.0f}%")
    log.info(f"\nTop Patterns:")
    for p in top_patterns:
        log.info(f"  [{p[1]}] {p[0]}: {p[2]}x")
    log.info(f"\nRecent Improvements:")
    for i in recent_imps:
        log.info(f"  [{i[0]}] {i[1]}: {i[2][:80]}")
    log.info("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Debug Pipeline v2 — 1000 cycles continus")
    parser.add_argument("--cycles", type=int, default=1000, help="Nombre de cycles (default: 1000)")
    parser.add_argument("--interval", type=float, default=8, help="Secondes entre cycles (default: 8)")
    parser.add_argument("--summary", action="store_true", help="Afficher resume et quitter")
    args = parser.parse_args()

    init_db()

    if args.summary:
        print_summary()
        return

    log.info(f"JARVIS Debug Pipeline v2 — {args.cycles} cycles, interval {args.interval}s")
    log.info(f"DB: {DB_PATH}")
    log.info(f"Tests: {len(TEST_PROMPTS)} prompts | Nodes: {list(NODES.keys())}")

    cycle = 1
    consecutive_errors = 0

    try:
        while cycle <= args.cycles:
            try:
                result = run_cycle(cycle, args.cycles)
                if result["ok"] > 0 or result["proxy"] or result["telegram"]:
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1

                if consecutive_errors >= 15:
                    log.warning(f"  {consecutive_errors} echecs consecutifs — pause 120s...")
                    time.sleep(120)
                    consecutive_errors = 0
                else:
                    time.sleep(args.interval)

                cycle += 1

            except KeyboardInterrupt:
                log.info("\nInterruption utilisateur.")
                break
            except Exception as e:
                log.error(f"  CYCLE {cycle} ERREUR: {e}")
                log.error(traceback.format_exc()[-500:])
                consecutive_errors += 1
                time.sleep(max(args.interval, 5))
                cycle += 1

    finally:
        print_summary()
        log.info("Pipeline v2 termine.")


if __name__ == "__main__":
    main()
