"""JARVIS Debug Pipeline — 1000 cycles continus sans arret.

Cycle: health_check -> dispatch_cluster -> verify_response -> collect_notes -> detect_patterns -> improve
Resilient: chaque cycle dans try/except, jamais d'arret. SQLite persistance.
Utilise M1 + OL1 (nodes disponibles).

Usage:
    python scripts/debug_pipeline_1000.py [--cycles 1000] [--interval 10]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
import time
import traceback
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).resolve().parent
TURBO_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(TURBO_DIR))
os.chdir(str(TURBO_DIR))

DB_PATH = TURBO_DIR / "data" / "debug_pipeline.db"
LOG_PATH = TURBO_DIR / "logs" / "debug_pipeline.log"

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
log = logging.getLogger("debug_pipeline")

# --- Cluster Nodes ---
NODES = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "model": "qwen3-8b",
        "format": "lmstudio",  # output[].content
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b",
        "format": "ollama",  # message.content
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "model": "deepseek-r1-0528-qwen3-8b",
        "format": "lmstudio",
    },
    "M3": {
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "model": "deepseek-r1-0528-qwen3-8b",
        "format": "lmstudio",
    },
}

# Health endpoints
HEALTH_CHECKS = {
    "M1": "http://127.0.0.1:1234/api/v1/models",
    "OL1": "http://127.0.0.1:11434/api/tags",
    "M2": "http://192.168.1.26:1234/api/v1/models",
    "M3": "http://192.168.1.113:1234/api/v1/models",
    "proxy": "http://127.0.0.1:18800/health",
    "ws": "http://127.0.0.1:9742/health",
    "openclaw": "http://127.0.0.1:18789/api/health",
}

# Telegram bot token (for interface tests)
_TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
_TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT", "")

# Test prompts (varied to detect different failure modes)
TEST_PROMPTS = [
    {"prompt": "Reponds OK si tu fonctionnes.", "expected": "OK", "type": "alive"},
    {"prompt": "2+2=?", "expected": "4", "type": "math"},
    {"prompt": "def add(a,b): return a+b\n# Test:", "expected": "add", "type": "code"},
    {"prompt": "Quelle est la capitale de la France?", "expected": "Paris", "type": "knowledge"},
    {"prompt": "Resumer en 1 mot: Le chat dort sur le tapis.", "expected": "chat", "type": "comprehension"},
    {"prompt": "JSON: {\"status\": \"ok\"} — Extrais le status.", "expected": "ok", "type": "parsing"},
    {"prompt": "Traduis en anglais: Bonjour le monde.", "expected": "Hello", "type": "translation"},
    {"prompt": "Liste 3 couleurs primaires separees par virgule.", "expected": "rouge", "type": "list"},
]

# Pattern categories for auto-detection
ERROR_PATTERNS = {
    "empty_response": "Reponse vide du noeud",
    "timeout": "Timeout depassé",
    "connection_refused": "Connexion refusee",
    "wrong_answer": "Reponse incorrecte",
    "slow_response": "Reponse lente (>5s)",
    "model_not_loaded": "Modele non charge",
    "conflict": "Conflit instance",
    "json_parse": "Erreur parsing JSON",
}


# --- Database ---
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
                created_at REAL
            );
        """)


# --- Node Communication ---
def query_node(node_name: str, prompt: str, timeout: int = 30) -> dict:
    """Query a cluster node. Returns {ok, text, latency_ms, error}."""
    node = NODES.get(node_name)
    if not node:
        return {"ok": False, "text": "", "latency_ms": 0, "error": f"Unknown node: {node_name}"}

    t0 = time.time()
    try:
        if node["format"] == "ollama":
            body = json.dumps({
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False,
            }).encode()
        else:
            body = json.dumps({
                "model": node["model"],
                "input": f"/nothink\n{prompt}",
                "temperature": 0.2, "max_output_tokens": 1024,
                "stream": False, "store": False,
            }).encode()

        req = urllib.request.Request(
            node["url"], data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())

        latency = int((time.time() - t0) * 1000)

        # Extract text based on format
        if node["format"] == "ollama":
            text = data.get("message", {}).get("content", "")
        else:
            # LM Studio /api/v1/chat format: output[].content
            text = ""
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    text = item.get("content", "")
                    break
            # Fallback: OpenAI format
            if not text:
                choices = data.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "")

        # Clean thinking tokens
        import re
        text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()

        if not text:
            return {"ok": False, "text": "", "latency_ms": latency, "error": "empty_response"}

        return {"ok": True, "text": text, "latency_ms": latency, "error": ""}

    except urllib.error.URLError as e:
        latency = int((time.time() - t0) * 1000)
        err = str(e.reason) if hasattr(e, 'reason') else str(e)
        if "ETIMEDOUT" in err or "timed out" in err:
            return {"ok": False, "text": "", "latency_ms": latency, "error": "timeout"}
        if "Connection refused" in err:
            return {"ok": False, "text": "", "latency_ms": latency, "error": "connection_refused"}
        return {"ok": False, "text": "", "latency_ms": latency, "error": f"network:{err[:180]}"}
    except TimeoutError:
        latency = int((time.time() - t0) * 1000)
        return {"ok": False, "text": "", "latency_ms": latency, "error": "timeout"}
    except Exception as e:
        latency = int((time.time() - t0) * 1000)
        etype = type(e).__name__
        return {"ok": False, "text": "", "latency_ms": latency, "error": f"{etype}:{str(e)[:180]}"}


def health_check(name: str, url: str, timeout: int = 3) -> dict:
    """Check if a service is alive. Returns {ok, latency_ms, detail}."""
    t0 = time.time()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode()[:500]
        latency = int((time.time() - t0) * 1000)
        return {"ok": True, "latency_ms": latency, "detail": data[:100]}
    except Exception as e:
        latency = int((time.time() - t0) * 1000)
        return {"ok": False, "latency_ms": latency, "detail": str(e)[:100]}


# --- Pattern Detection ---
def detect_patterns(cycle_errors: list[dict], db_conn: sqlite3.Connection) -> list[dict]:
    """Analyze errors and detect recurring patterns."""
    patterns_found = []
    now = time.time()

    error_counts = Counter()
    for err in cycle_errors:
        key = f"{err.get('node', '?')}:{err.get('error', 'unknown')}"
        error_counts[key] += 1

    for key, count in error_counts.items():
        node, error_type = key.split(":", 1)
        # Map to pattern type
        ptype = "unknown"
        for pt, desc in ERROR_PATTERNS.items():
            if pt in error_type.lower():
                ptype = pt
                break

        # Check if pattern already exists
        row = db_conn.execute(
            "SELECT id, count FROM patterns WHERE pattern_type=? AND node=? AND resolved=0",
            (ptype, node)
        ).fetchone()

        if row:
            db_conn.execute(
                "UPDATE patterns SET count=count+?, last_seen=? WHERE id=?",
                (count, now, row[0])
            )
            total = row[1] + count
        else:
            db_conn.execute(
                "INSERT INTO patterns (pattern_type, description, count, first_seen, last_seen, node) VALUES (?,?,?,?,?,?)",
                (ptype, f"{ERROR_PATTERNS.get(ptype, error_type)} on {node}", count, now, now, node)
            )
            total = count

        patterns_found.append({"type": ptype, "node": node, "count": total})

    return patterns_found


def propose_improvements(patterns: list[dict], cycle_num: int, db_conn: sqlite3.Connection) -> list[dict]:
    """Generate improvement suggestions based on detected patterns."""
    improvements = []
    now = time.time()

    for p in patterns:
        if p["count"] >= 5 and p["type"] == "empty_response":
            imp = {
                "category": "reliability",
                "description": f"Node {p['node']} returns empty responses frequently ({p['count']}x). Consider warmup or model reload.",
                "priority": "P1",
            }
            improvements.append(imp)
            db_conn.execute(
                "INSERT INTO improvements (cycle_num, category, description, priority, created_at) VALUES (?,?,?,?,?)",
                (cycle_num, imp["category"], imp["description"], imp["priority"], now)
            )

        elif p["count"] >= 10 and p["type"] == "timeout":
            imp = {
                "category": "performance",
                "description": f"Node {p['node']} timeouts ({p['count']}x). Check network or reduce load.",
                "priority": "P1",
            }
            improvements.append(imp)
            db_conn.execute(
                "INSERT INTO improvements (cycle_num, category, description, priority, created_at) VALUES (?,?,?,?,?)",
                (cycle_num, imp["category"], imp["description"], imp["priority"], now)
            )

        elif p["count"] >= 3 and p["type"] == "connection_refused":
            imp = {
                "category": "infrastructure",
                "description": f"Node {p['node']} connection refused ({p['count']}x). Node likely offline.",
                "priority": "P2",
            }
            improvements.append(imp)
            db_conn.execute(
                "INSERT INTO improvements (cycle_num, category, description, priority, created_at) VALUES (?,?,?,?,?)",
                (cycle_num, imp["category"], imp["description"], imp["priority"], now)
            )

        elif p["count"] >= 5 and p["type"] == "slow_response":
            imp = {
                "category": "performance",
                "description": f"Node {p['node']} consistently slow ({p['count']}x). Check GPU load or model size.",
                "priority": "P2",
            }
            improvements.append(imp)
            db_conn.execute(
                "INSERT INTO improvements (cycle_num, category, description, priority, created_at) VALUES (?,?,?,?,?)",
                (cycle_num, imp["category"], imp["description"], imp["priority"], now)
            )

    return improvements


# --- Main Cycle ---
def run_cycle(cycle_num: int, total_cycles: int) -> dict:
    """Execute one complete debug cycle."""
    cycle_start = time.time()
    ts = datetime.now().strftime("%H:%M:%S")

    log.info(f"=== CYCLE {cycle_num}/{total_cycles} [{ts}] ===")

    # Step 1: Health Check
    log.info("  [1/6] Health check...")
    nodes_online = []
    nodes_offline = []
    for name, url in HEALTH_CHECKS.items():
        h = health_check(name, url)
        if h["ok"]:
            nodes_online.append(name)
        else:
            nodes_offline.append(name)

    log.info(f"        Online: {nodes_online} | Offline: {nodes_offline}")

    # Step 2: Dispatch cluster queries
    log.info("  [2/6] Dispatch cluster queries...")
    prompt_data = TEST_PROMPTS[cycle_num % len(TEST_PROMPTS)]
    prompt = prompt_data["prompt"]
    expected = prompt_data["expected"]
    prompt_type = prompt_data["type"]

    queries = []
    available_nodes = [n for n in ["M1", "OL1"] if n in nodes_online]
    if not available_nodes:
        available_nodes = ["M1", "OL1"]  # Try anyway

    for node_name in available_nodes:
        timeout = 15 if node_name == "M1" else 20  # M1 fast, reduce timeout
        result = query_node(node_name, prompt, timeout=timeout)
        result["node"] = node_name
        result["prompt_type"] = prompt_type
        result["prompt"] = prompt[:100]
        result["expected"] = expected
        result["correct"] = 1 if expected.lower() in result.get("text", "").lower() else 0
        queries.append(result)
        status = "OK" if result["ok"] else "FAIL"
        log.info(f"        [{node_name}] {status} {result['latency_ms']}ms — {result.get('text', result.get('error', ''))[:60]}")

    # Step 3: Verify responses
    log.info("  [3/6] Verify responses...")
    total_q = len(queries)
    success_q = sum(1 for q in queries if q["ok"])
    correct_q = sum(1 for q in queries if q.get("correct"))
    failed_q = total_q - success_q
    avg_lat = sum(q["latency_ms"] for q in queries) / max(total_q, 1)
    log.info(f"        {success_q}/{total_q} OK | {correct_q}/{total_q} correct | avg {avg_lat:.0f}ms")

    # Step 4: Collect errors
    cycle_errors = [{"node": q["node"], "error": q["error"]} for q in queries if not q["ok"]]
    slow_queries = [q for q in queries if q["ok"] and q["latency_ms"] > 5000]
    for sq in slow_queries:
        cycle_errors.append({"node": sq["node"], "error": "slow_response"})

    # Step 5: Detect patterns & propose improvements
    log.info("  [4/6] Pattern detection...")
    with sqlite3.connect(str(DB_PATH)) as conn:
        # Insert cycle record
        conn.execute(
            "INSERT INTO cycles (cycle_num, started_at, status, nodes_online, nodes_offline, "
            "total_queries, successful_queries, failed_queries, avg_latency_ms, errors) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (cycle_num, cycle_start, "running",
             json.dumps(nodes_online), json.dumps(nodes_offline),
             total_q, success_q, failed_q, avg_lat, json.dumps(cycle_errors)),
        )
        cycle_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert query records
        for q in queries:
            conn.execute(
                "INSERT INTO queries (cycle_id, node, prompt_type, prompt, response, expected, "
                "correct, latency_ms, error, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (cycle_id, q["node"], q["prompt_type"], q["prompt"],
                 q.get("text", "")[:500], q["expected"], q.get("correct", 0),
                 q["latency_ms"], q.get("error", ""), time.time()),
            )

        patterns = detect_patterns(cycle_errors, conn)
        improvements = propose_improvements(patterns, cycle_num, conn)

        if patterns:
            log.info(f"        Patterns: {[f'{p['type']}({p['node']})x{p['count']}' for p in patterns]}")
        if improvements:
            log.info(f"  [5/6] Improvements: {[f'{i['priority']}:{i['category']}' for i in improvements]}")
        else:
            log.info("  [5/6] No new improvements.")

        # Step 5b: Interface tests (every 10 cycles)
        if cycle_num % 10 == 0:
            log.info("  [5b/6] Interface tests (proxy, telegram, openclaw)...")
            try:
                proxy_body = json.dumps({"agent": "telegram", "text": "ping"}).encode()
                proxy_req = urllib.request.Request(
                    "http://127.0.0.1:18800/chat", data=proxy_body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(proxy_req, timeout=15) as resp:
                    proxy_data = json.loads(resp.read().decode())
                proxy_ok = bool(proxy_data.get("ok") or proxy_data.get("data", {}).get("text"))
                log.info(f"        [PROXY /chat] {'OK' if proxy_ok else 'FAIL'}")
            except Exception as e:
                log.info(f"        [PROXY /chat] FAIL: {str(e)[:80]}")
                cycle_errors.append({"node": "proxy", "error": f"proxy_chat:{str(e)[:100]}"})
            try:
                oc_req = urllib.request.Request("http://127.0.0.1:18789/api/health")
                with urllib.request.urlopen(oc_req, timeout=5) as resp:
                    log.info("        [OPENCLAW] OK")
            except Exception as e:
                log.info(f"        [OPENCLAW] FAIL: {str(e)[:60]}")
            try:
                import subprocess as _sp
                tg_check = _sp.run(
                    ["wmic", "process", "where", "name='node.exe'", "get", "CommandLine"],
                    capture_output=True, text=True, timeout=5,
                )
                tg_running = "telegram-bot" in tg_check.stdout
                log.info(f"        [TELEGRAM BOT] {'RUNNING' if tg_running else 'NOT RUNNING'}")
                if not tg_running:
                    cycle_errors.append({"node": "telegram", "error": "telegram_bot_not_running"})
            except Exception as e:
                log.info(f"        [TELEGRAM BOT] check failed: {str(e)[:60]}")

        # Step 6: Auto-improve — ask M1 for analysis every 50 cycles
        notes = ""
        if cycle_num % 50 == 0 and cycle_num > 0 and "M1" in nodes_online:
            log.info("  [6/6] Auto-analysis via M1...")
            stats = conn.execute(
                "SELECT COUNT(*), AVG(avg_latency_ms), SUM(failed_queries), SUM(successful_queries) "
                "FROM cycles WHERE cycle_num > ?", (max(0, cycle_num - 50),)
            ).fetchone()
            top_patterns = conn.execute(
                "SELECT pattern_type, node, count FROM patterns WHERE resolved=0 ORDER BY count DESC LIMIT 5"
            ).fetchall()

            analysis_prompt = (
                f"Analyse ces metriques JARVIS des 50 derniers cycles:\n"
                f"- Cycles: {stats[0]}, Latence moy: {stats[1]:.0f}ms\n"
                f"- Succes: {stats[3]}, Echecs: {stats[2]}\n"
                f"- Top patterns: {[(p[0], p[1], p[2]) for p in top_patterns]}\n"
                f"Propose 3 ameliorations concretes en 1 phrase chacune."
            )
            analysis = query_node("M1", analysis_prompt, timeout=15)
            if analysis["ok"]:
                notes = analysis["text"][:500]
                log.info(f"        M1 analysis: {notes[:100]}...")
            else:
                log.info(f"        M1 analysis failed: {analysis.get('error', '')}")
        else:
            log.info("  [6/6] Skip auto-analysis (not milestone cycle).")

        # Finalize cycle
        cycle_end = time.time()
        conn.execute(
            "UPDATE cycles SET finished_at=?, status=?, patterns=?, improvements=?, notes=? WHERE id=?",
            (cycle_end, "completed", json.dumps([p["type"] for p in patterns]),
             json.dumps([i["description"][:200] for i in improvements]),
             notes, cycle_id),
        )

    cycle_ms = int((cycle_end - cycle_start) * 1000)
    log.info(f"  CYCLE {cycle_num} DONE — {cycle_ms}ms | {success_q}/{total_q} OK | patterns:{len(patterns)}")
    return {
        "cycle": cycle_num, "ms": cycle_ms, "ok": success_q, "fail": failed_q,
        "patterns": len(patterns), "improvements": len(improvements),
    }


def print_summary():
    """Print final summary from DB."""
    with sqlite3.connect(str(DB_PATH)) as conn:
        total = conn.execute("SELECT COUNT(*) FROM cycles").fetchone()[0]
        completed = conn.execute("SELECT COUNT(*) FROM cycles WHERE status='completed'").fetchone()[0]
        avg_lat = conn.execute("SELECT AVG(avg_latency_ms) FROM cycles").fetchone()[0] or 0
        total_q = conn.execute("SELECT SUM(total_queries) FROM cycles").fetchone()[0] or 0
        success_q = conn.execute("SELECT SUM(successful_queries) FROM cycles").fetchone()[0] or 0
        top_patterns = conn.execute(
            "SELECT pattern_type, node, count FROM patterns ORDER BY count DESC LIMIT 10"
        ).fetchall()
        improvements = conn.execute(
            "SELECT priority, category, description FROM improvements ORDER BY created_at DESC LIMIT 10"
        ).fetchall()

    log.info("\n" + "=" * 60)
    log.info("PIPELINE SUMMARY")
    log.info("=" * 60)
    log.info(f"Cycles: {completed}/{total} completed")
    log.info(f"Queries: {success_q}/{total_q} successful ({success_q/max(total_q,1)*100:.1f}%)")
    log.info(f"Avg latency: {avg_lat:.0f}ms")
    log.info(f"\nTop Patterns:")
    for p in top_patterns:
        log.info(f"  [{p[1]}] {p[0]}: {p[2]}x")
    log.info(f"\nRecent Improvements:")
    for i in improvements:
        log.info(f"  [{i[0]}] {i[1]}: {i[2][:80]}")
    log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Debug Pipeline — 1000 cycles continus")
    parser.add_argument("--cycles", type=int, default=1000, help="Nombre de cycles (default: 1000)")
    parser.add_argument("--interval", type=float, default=10, help="Secondes entre cycles (default: 10)")
    parser.add_argument("--summary", action="store_true", help="Afficher le resume et quitter")
    args = parser.parse_args()

    init_db()

    if args.summary:
        print_summary()
        return

    log.info(f"JARVIS Debug Pipeline — {args.cycles} cycles, interval {args.interval}s")
    log.info(f"DB: {DB_PATH}")
    log.info(f"Log: {LOG_PATH}")

    cycle = 1
    consecutive_errors = 0
    max_consecutive = 10  # pause after 10 consecutive full failures

    try:
        while cycle <= args.cycles:
            try:
                result = run_cycle(cycle, args.cycles)
                if result["ok"] > 0:
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1

                # Adaptive interval: slow down if all nodes failing
                if consecutive_errors >= max_consecutive:
                    log.warning(f"  {consecutive_errors} cycles echoues consecutifs — pause 60s...")
                    time.sleep(60)
                    consecutive_errors = 0
                else:
                    time.sleep(args.interval)

                cycle += 1

            except KeyboardInterrupt:
                log.info("\nInterruption utilisateur — arret propre.")
                break
            except Exception as e:
                log.error(f"  CYCLE {cycle} ERREUR: {e}")
                log.error(traceback.format_exc()[-300:])
                consecutive_errors += 1
                time.sleep(max(args.interval, 5))
                cycle += 1

    finally:
        print_summary()
        log.info("Pipeline termine.")


if __name__ == "__main__":
    main()
