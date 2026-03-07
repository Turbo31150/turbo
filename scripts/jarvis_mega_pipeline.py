#!/usr/bin/env python3
"""
JARVIS Mega Pipeline — 1000 cycles autonomes, jamais d'arret.

Pipeline par cycle:
  1. HEALTH CHECK   — etat cluster (M1/M2/M3/OL1)
  2. DEBUG          — detecte erreurs dans logs + services
  3. CLUSTER QUERY  — dispatch question au cluster, note reponse
  4. WORKFLOW EXEC  — execute un workflow via workflow_engine
  5. AMELIORATION   — analyse patterns, suggere improvements
  6. NOTATION       — score qualite reponse, persiste en SQLite
  7. TELEGRAM       — rapport toutes les 25 cycles

Resilience: retry infini sur erreur, skip domain si timeout, log tout.

Usage:
  python scripts/jarvis_mega_pipeline.py
  python scripts/jarvis_mega_pipeline.py --cycles 500 --focus debug
  python scripts/jarvis_mega_pipeline.py --cycles 1000 --notify
"""

import json
import os
import re
import sys
import time
import sqlite3
import traceback
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Paths ─────────────────────────────────────────────────────────────────────
TURBO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = TURBO_ROOT / "data"
PIPELINE_DB = DATA_DIR / "mega_pipeline.db"
LOG_DIR = TURBO_ROOT / "logs"

# ── Cluster ───────────────────────────────────────────────────────────────────
CLUSTER = [
    {"id": "M1", "url": "http://127.0.0.1:1234/v1/chat/completions", "model": "qwen3-8b", "type": "lmstudio", "weight": 1.8},
    {"id": "M2", "url": "http://192.168.1.26:1234/v1/chat/completions", "model": "deepseek-r1-0528-qwen3-8b", "type": "lmstudio", "weight": 1.5},
    {"id": "OL1", "url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b", "type": "ollama", "weight": 1.3},
    {"id": "M3", "url": "http://192.168.1.113:1234/v1/chat/completions", "model": "deepseek-r1-0528-qwen3-8b", "type": "lmstudio", "weight": 1.2},
]

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_CHAT = "2010747443"

def _get_telegram_token():
    token = os.getenv("TELEGRAM_TOKEN", "")
    if not token:
        env_path = TURBO_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("TELEGRAM_TOKEN="):
                    token = line.split("=", 1)[1].strip()
    return token

def send_telegram(text):
    token = _get_telegram_token()
    if not token:
        return
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        try:
            body = json.dumps({"chat_id": TELEGRAM_CHAT, "text": chunk}).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=body, headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ── Database ──────────────────────────────────────────────────────────────────
def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(PIPELINE_DB))
    db.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            cycle INTEGER,
            domain TEXT,
            phase TEXT,
            node_used TEXT,
            prompt_hash TEXT,
            response_len INTEGER,
            score REAL,
            latency_ms INTEGER,
            success INTEGER DEFAULT 1,
            error TEXT,
            improvements TEXT,
            patterns TEXT
        );
        CREATE TABLE IF NOT EXISTS pipeline_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            cycle INTEGER,
            pattern_type TEXT,
            description TEXT,
            frequency INTEGER DEFAULT 1,
            score_impact REAL
        );
        CREATE TABLE IF NOT EXISTS pipeline_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            cycle INTEGER,
            domain TEXT,
            error_type TEXT,
            message TEXT,
            resolved INTEGER DEFAULT 0,
            fix_applied TEXT
        );
        CREATE TABLE IF NOT EXISTS pipeline_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            total_cycles INTEGER,
            total_queries INTEGER,
            avg_score REAL,
            avg_latency_ms REAL,
            error_rate REAL,
            best_node TEXT,
            patterns_found INTEGER,
            improvements_applied INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_cycles_cycle ON pipeline_cycles(cycle);
        CREATE INDEX IF NOT EXISTS idx_cycles_domain ON pipeline_cycles(domain);
        CREATE INDEX IF NOT EXISTS idx_errors_resolved ON pipeline_errors(resolved);
    """)
    db.close()

def db_insert(table, **kwargs):
    cols = ", ".join(kwargs.keys())
    placeholders = ", ".join("?" * len(kwargs))
    try:
        db = sqlite3.connect(str(PIPELINE_DB))
        db.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(kwargs.values()))
        db.commit()
        db.close()
    except Exception as e:
        log(f"[DB] Insert error: {e}")

# ── Cluster Query ─────────────────────────────────────────────────────────────
def query_node(node, prompt, timeout=60):
    try:
        if node["type"] == "ollama":
            body = json.dumps({
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False
            }).encode()
        else:
            body = json.dumps({
                "model": node["model"],
                "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}],
                "temperature": 0.3, "max_tokens": 2048, "stream": False
            }).encode()

        req = urllib.request.Request(node["url"], data=body, headers={"Content-Type": "application/json"})
        t0 = time.time()
        resp = urllib.request.urlopen(req, timeout=timeout)
        latency = int((time.time() - t0) * 1000)
        data = json.loads(resp.read().decode())

        if node["type"] == "ollama":
            text = data.get("message", {}).get("content", "")
        else:
            choices = data.get("choices", [])
            text = choices[0]["message"]["content"] if choices else ""
        text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
        return {"node": node["id"], "text": text, "latency": latency, "ok": True, "weight": node["weight"]}
    except Exception as e:
        return {"node": node["id"], "text": "", "latency": 0, "ok": False, "error": str(e)[:200], "weight": node["weight"]}

def query_cluster(prompt, timeout=60):
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(query_node, n, prompt, timeout): n for n in CLUSTER}
        for f in as_completed(futs, timeout=timeout + 15):
            try:
                results.append(f.result())
            except Exception:
                pass
    return results

def best_response(results):
    valid = [r for r in results if r.get("ok") and r.get("text")]
    if not valid:
        return None
    return max(valid, key=lambda r: r["weight"])

# ── Scoring ───────────────────────────────────────────────────────────────────
def score_response(text, latency_ms, domain):
    if not text or len(text) < 5:
        return 0.0
    s = 0.0
    # Length (0-25)
    if 50 <= len(text) <= 3000:
        s += 25
    elif len(text) > 3000:
        s += 15
    else:
        s += len(text) / 50 * 25
    # Structure (0-25)
    if re.search(r'\n\s*[-*]\s', text): s += 8
    if re.search(r'\n\s*\d+[\.\)]\s', text): s += 8
    if re.search(r'\*\*[^*]+\*\*', text): s += 5
    if len(text.split('\n')) >= 3: s += 4
    # Speed (0-25)
    if latency_ms < 3000: s += 25
    elif latency_ms < 10000: s += 20
    elif latency_ms < 30000: s += 15
    elif latency_ms < 60000: s += 10
    else: s += 5
    # Coherence (0-25) — basic heuristic
    words = text.split()
    unique_ratio = len(set(w.lower() for w in words)) / max(len(words), 1)
    s += min(25, unique_ratio * 30)
    return round(min(100, s), 1)

# ── Domain: HEALTH CHECK ──────────────────────────────────────────────────────
def phase_health(cycle_num):
    results = []
    for node in CLUSTER:
        t0 = time.time()
        try:
            if node["type"] == "ollama":
                req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
                resp = urllib.request.urlopen(req, timeout=5)
                data = json.loads(resp.read().decode())
                models = len(data.get("models", []))
                results.append({"node": node["id"], "ok": True, "models": models, "latency": int((time.time()-t0)*1000)})
            else:
                url = node["url"].replace("/v1/chat/completions", "/v1/models")
                req = urllib.request.Request(url)
                resp = urllib.request.urlopen(req, timeout=5)
                data = json.loads(resp.read().decode())
                loaded = len([m for m in data.get("data", []) if m.get("loaded_instances")])
                results.append({"node": node["id"], "ok": True, "models": loaded, "latency": int((time.time()-t0)*1000)})
        except Exception as e:
            results.append({"node": node["id"], "ok": False, "error": str(e)[:100], "latency": 0})
    online = sum(1 for r in results if r["ok"])
    return {"nodes": results, "online": online, "total": len(CLUSTER)}

# ── Domain: DEBUG ─────────────────────────────────────────────────────────────
DEBUG_TARGETS = [
    ("telegram-bot.log", ["ERROR", "FATAL", "CRASH", "timeout"]),
    ("telegram-bot-debug.log", ["ERROR", "Conflict", "FATAL"]),
    ("unified_boot.log", ["ERROR", "FAIL", "OFFLINE"]),
    ("cluster_boot.log", ["ERROR", "FAIL"]),
]

def phase_debug(cycle_num):
    errors_found = []
    for logfile, patterns in DEBUG_TARGETS:
        logpath = LOG_DIR / logfile
        if not logpath.exists():
            continue
        try:
            lines = logpath.read_text(encoding="utf-8", errors="replace").splitlines()
            # Check last 50 lines only
            for line in lines[-50:]:
                for pat in patterns:
                    if pat in line:
                        errors_found.append({"file": logfile, "pattern": pat, "line": line.strip()[:200]})
                        break
        except Exception:
            pass
    return {"errors_found": len(errors_found), "details": errors_found[:10]}

# ── Domain: CLUSTER QUERY (test + note) ───────────────────────────────────────
QUERY_BANK = [
    {"domain": "code", "prompt": "Ecris une fonction Python pour {topic}. Sois concis.", "topics": [
        "verifier qu'une chaine est un palindrome", "trier un dictionnaire par valeur",
        "compter les occurrences de mots dans un texte", "generer des nombres premiers jusqu'a N",
        "detecter les cycles dans une liste chainee", "parser un CSV sans pandas",
        "implementer un LRU cache en 20 lignes", "valider une adresse email avec regex",
        "creer un serveur HTTP minimal", "calculer la distance de Levenshtein",
    ]},
    {"domain": "debug", "prompt": "Analyse cette erreur et explique la cause + fix: {topic}", "topics": [
        "ModuleNotFoundError: No module named 'src.brain'",
        "sqlite3.OperationalError: database is locked",
        "ConnectionRefusedError: [Errno 111] Connection refused sur port 18800",
        "asyncio.TimeoutError apres 120s sur cluster query",
        "JSON decode error sur response vide du noeud M2",
        "Telegram Conflict: terminated by other getUpdates request",
        "CUDA out of memory sur RTX 2060 12GB",
        "ImportError: circular import entre event_bus et brain",
    ]},
    {"domain": "archi", "prompt": "Propose une amelioration pour: {topic}", "topics": [
        "le systeme de retry du cluster JARVIS (actuellement 1 retry fixe)",
        "le routing intelligent des requetes vers le bon noeud",
        "la persistence des conversations Telegram (actuellement en memoire max 50)",
        "le scoring des reponses du cluster (actuellement 5 criteres basiques)",
        "le workflow engine qui n'a que 2 actions (bash + cluster_query)",
        "le systeme d'alertes proactives trading (check toutes les 2min seulement)",
    ]},
    {"domain": "trading", "prompt": "Analyse: {topic}", "topics": [
        "quel impact a le RSI divergence sur les signaux LONG vs SHORT",
        "comment optimiser le ratio TP/SL pour du scalping 5min sur MEXC futures",
        "quelle combinaison d'indicateurs detecte le mieux les breakouts volume",
        "comment filtrer les faux signaux pendant les periodes de range",
    ]},
    {"domain": "system", "prompt": "Comment: {topic}", "topics": [
        "monitorer la latence de 6 noeuds GPU en temps reel sous Windows",
        "creer un circuit breaker Python pour les appels cluster",
        "implementer un health check distribue avec consensus",
        "optimiser les requetes SQLite quand 4+ processes ecrivent simultanement",
    ]},
]

def pick_query(cycle_num):
    bank_idx = cycle_num % len(QUERY_BANK)
    bank = QUERY_BANK[bank_idx]
    topic_idx = (cycle_num // len(QUERY_BANK)) % len(bank["topics"])
    topic = bank["topics"][topic_idx]
    prompt = bank["prompt"].replace("{topic}", topic)
    return bank["domain"], prompt, topic

# ── Domain: AMELIORATION ──────────────────────────────────────────────────────
def phase_improve(cycle_num, cycle_data):
    prompt = f"""Expert JARVIS. Analyse ce cycle #{cycle_num} et suggere UNE amelioration:

Health: {cycle_data.get('health', {}).get('online', '?')}/{cycle_data.get('health', {}).get('total', '?')} nodes online
Debug: {cycle_data.get('debug', {}).get('errors_found', 0)} erreurs detectees
Query: domain={cycle_data.get('query_domain', '?')}, score={cycle_data.get('score', 0):.0f}/100, latency={cycle_data.get('latency', 0)}ms
Node: {cycle_data.get('node', '?')}

Reponds en JSON compact:
{{"pattern": "nom du pattern observe",
  "improvement": "description en 1 ligne",
  "priority": "HIGH/MED/LOW",
  "category": "perf|reliability|quality|feature"}}"""

    results = query_cluster(prompt, timeout=45)
    best = best_response(results)
    if best:
        try:
            match = re.search(r'\{[\s\S]*?\}', best["text"])
            if match:
                parsed = json.loads(match.group())
                return {"ok": True, "data": parsed, "node": best["node"]}
        except Exception:
            pass
        return {"ok": True, "data": {"pattern": "raw", "improvement": best["text"][:200]}, "node": best["node"]}
    return {"ok": False, "data": None}

# ── Main Pipeline ─────────────────────────────────────────────────────────────
def run_pipeline(total_cycles=1000, notify=True, focus=None):
    init_db()

    log("=" * 70)
    log(f"  JARVIS MEGA PIPELINE — {total_cycles} cycles")
    log(f"  Cluster: {len(CLUSTER)} nodes | Focus: {focus or 'all'}")
    log(f"  DB: {PIPELINE_DB}")
    log(f"  Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    if notify:
        send_telegram(f"JARVIS Mega Pipeline demarre: {total_cycles} cycles, {len(CLUSTER)} nodes")

    global_start = time.time()
    total_queries = 0
    total_score = 0
    total_errors = 0
    node_scores = {}  # node_id -> [scores]
    patterns_found = []

    cycle = 0
    while cycle < total_cycles:
        cycle += 1
        cycle_start = time.time()
        cycle_data = {"cycle": cycle}

        try:
            # ── Phase 1: Health Check ─────────────────────────────────────
            health = phase_health(cycle)
            cycle_data["health"] = health
            online_nodes = [n["node"] for n in health["nodes"] if n["ok"]]

            if not online_nodes:
                log(f"[Cycle {cycle:4d}] SKIP — 0 nodes online, retry in 30s")
                db_insert("pipeline_errors", cycle=cycle, domain="health",
                          error_type="no_nodes", message="All cluster nodes offline")
                total_errors += 1
                time.sleep(30)
                cycle -= 1  # Retry this cycle
                continue

            # ── Phase 2: Debug Scan ───────────────────────────────────────
            debug = phase_debug(cycle)
            cycle_data["debug"] = debug
            if debug["errors_found"] > 0:
                for err in debug["details"][:3]:
                    db_insert("pipeline_errors", cycle=cycle, domain="debug",
                              error_type="log_error", message=f"{err['file']}: {err['line'][:200]}")

            # ── Phase 3: Cluster Query ────────────────────────────────────
            domain, prompt, topic = pick_query(cycle)
            if focus and domain != focus:
                domain, prompt, topic = focus, f"Question {focus} #{cycle}: {topic}", topic

            cycle_data["query_domain"] = domain
            t0 = time.time()
            results = query_cluster(prompt, timeout=60)
            best = best_response(results)

            if best:
                latency = best["latency"]
                score = score_response(best["text"], latency, domain)
                cycle_data["score"] = score
                cycle_data["latency"] = latency
                cycle_data["node"] = best["node"]
                total_queries += 1
                total_score += score

                if best["node"] not in node_scores:
                    node_scores[best["node"]] = []
                node_scores[best["node"]].append(score)

                db_insert("pipeline_cycles",
                    cycle=cycle, domain=domain, phase="query",
                    node_used=best["node"], prompt_hash=str(hash(prompt))[:8],
                    response_len=len(best["text"]), score=score,
                    latency_ms=latency, success=1
                )
            else:
                cycle_data["score"] = 0
                cycle_data["latency"] = int((time.time()-t0)*1000)
                cycle_data["node"] = "NONE"
                total_errors += 1
                db_insert("pipeline_cycles",
                    cycle=cycle, domain=domain, phase="query",
                    node_used="NONE", response_len=0, score=0,
                    latency_ms=cycle_data["latency"], success=0,
                    error="no_response"
                )

            # ── Phase 4: Improvement Analysis (every 5 cycles) ────────────
            if cycle % 5 == 0:
                improve = phase_improve(cycle, cycle_data)
                if improve["ok"] and improve["data"]:
                    data = improve["data"]
                    pattern = data.get("pattern", "unknown")
                    patterns_found.append(pattern)
                    db_insert("pipeline_patterns",
                        cycle=cycle, pattern_type=data.get("category", "general"),
                        description=data.get("improvement", "")[:500],
                        score_impact=cycle_data.get("score", 0)
                    )
                    cycle_data["improvement"] = data.get("improvement", "")[:100]

            # ── Display ───────────────────────────────────────────────────
            avg = total_score / max(total_queries, 1)
            bar_len = int(cycle_data.get("score", 0) / 100 * 20)
            bar = "#" * bar_len + "." * (20 - bar_len)
            status = "OK" if cycle_data.get("score", 0) >= 50 else "!!"
            node_tag = cycle_data.get("node", "?")[:3]

            extra = ""
            if cycle_data.get("improvement"):
                extra = f" | +{cycle_data['improvement'][:40]}"

            log(f"[{cycle:4d}/{total_cycles}] {status} {domain:<8} [{bar}] "
                f"{cycle_data.get('score',0):5.1f}/100 {cycle_data.get('latency',0):5d}ms "
                f"[{node_tag}] avg={avg:.1f} err={total_errors}{extra}")

            # ── Telegram Report (every 25 cycles) ────────────────────────
            if notify and cycle % 25 == 0:
                elapsed = time.time() - global_start
                err_rate = total_errors / max(cycle, 1) * 100

                # Best node
                best_node = "?"
                best_avg = 0
                for nid, scores in node_scores.items():
                    navg = sum(scores) / len(scores)
                    if navg > best_avg:
                        best_avg = navg
                        best_node = nid

                report = (
                    f"JARVIS Pipeline — Cycle {cycle}/{total_cycles}\n"
                    f"Elapsed: {elapsed/60:.0f}min | Queries: {total_queries}\n"
                    f"Avg Score: {avg:.1f}/100 | Errors: {total_errors} ({err_rate:.1f}%)\n"
                    f"Best Node: {best_node} ({best_avg:.1f})\n"
                    f"Online: {health['online']}/{health['total']}\n"
                    f"Patterns: {len(set(patterns_found))}"
                )
                send_telegram(report)

                # Save periodic stats
                db_insert("pipeline_stats",
                    total_cycles=cycle, total_queries=total_queries,
                    avg_score=round(avg, 1), avg_latency_ms=0,
                    error_rate=round(err_rate, 1), best_node=best_node,
                    patterns_found=len(set(patterns_found)),
                    improvements_applied=0
                )

        except KeyboardInterrupt:
            log(f"\n[INTERRUPT] Pipeline arrete au cycle {cycle}")
            break
        except Exception as e:
            total_errors += 1
            log(f"[{cycle:4d}] CRASH: {e}")
            db_insert("pipeline_errors", cycle=cycle, domain="pipeline",
                      error_type="crash", message=str(e)[:500])
            time.sleep(5)  # Cooldown on crash, then continue

        # Throttle: small delay between cycles
        time.sleep(0.3)

    # ── Final Report ──────────────────────────────────────────────────────────
    total_time = time.time() - global_start
    avg = total_score / max(total_queries, 1)
    err_rate = total_errors / max(cycle, 1) * 100

    log("\n" + "=" * 70)
    log(f"  MEGA PIPELINE COMPLETE — {cycle} cycles")
    log("=" * 70)
    log(f"  Duration: {total_time:.0f}s ({total_time/60:.1f}min)")
    log(f"  Queries: {total_queries} | Avg Score: {avg:.1f}/100")
    log(f"  Errors: {total_errors} ({err_rate:.1f}%)")
    log(f"  Patterns: {len(set(patterns_found))}")

    # Node breakdown
    log(f"\n  {'Node':<6} {'Avg':>6} {'Count':>6} {'Grade'}")
    log(f"  {'─'*30}")
    for nid in sorted(node_scores.keys()):
        scores = node_scores[nid]
        navg = sum(scores) / len(scores)
        grade = "A" if navg >= 80 else ("B" if navg >= 65 else ("C" if navg >= 50 else "D"))
        log(f"  {nid:<6} {navg:6.1f} {len(scores):6d}  {grade}")

    log("=" * 70)

    if notify:
        final = (
            f"JARVIS Mega Pipeline TERMINE\n"
            f"{cycle} cycles en {total_time/60:.1f}min\n"
            f"Score moyen: {avg:.1f}/100\n"
            f"Erreurs: {total_errors} ({err_rate:.1f}%)\n"
            f"Patterns: {len(set(patterns_found))}\n"
            f"DB: {PIPELINE_DB}"
        )
        send_telegram(final)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=1000)
    parser.add_argument("--focus", type=str, default=None, choices=["code", "debug", "archi", "trading", "system"])
    parser.add_argument("--notify", action="store_true", default=True)
    parser.add_argument("--no-notify", action="store_true")
    args = parser.parse_args()

    if args.no_notify:
        args.notify = False

    run_pipeline(total_cycles=args.cycles, notify=args.notify, focus=args.focus)
