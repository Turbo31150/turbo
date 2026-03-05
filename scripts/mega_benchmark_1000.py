#!/usr/bin/env python3
"""JARVIS Mega-Benchmark — 1000 cycles multi-chemin multi-strategie.

Chemins testes:
  1. Direct nodes (M1/M2/M3/OL1) via curl-like
  2. Proxy direct-proxy:18800 /chat (OpenClaw routing)
  3. Ollama cloud (gpt-oss, devstral)
  4. Race (tous noeuds parallele, premier gagne)
  5. Consensus (2+ noeuds, vote pondere)
  6. Round-robin

Resultats: etoile.db + data/mega_benchmark_1000.json
Progress + vocal summary → Telegram
"""

import asyncio
import httpx
import json
import os
import random
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("F:/BUREAU/turbo")
os.chdir(PROJECT_ROOT)

# ── Telegram config ──────────────────────────────────────────────────────────
TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT = "2010747443"
TTS_SCRIPT = "C:/Users/franc/.openclaw/workspace/dev/win_tts.py"

# ── Nodes ────────────────────────────────────────────────────────────────────
NODES = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "qwen3-8b",
        "prefix": "/nothink\n",
        "max_tokens": 1024,
        "weight": 1.8,
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "deepseek-r1-0528-qwen3-8b",
        "prefix": "",
        "max_tokens": 2048,
        "weight": 1.5,
    },
    "M3": {
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "deepseek/deepseek-r1-0528-qwen3-8b",
        "prefix": "",
        "max_tokens": 2048,
        "weight": 1.2,
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "qwen3:1.7b",
        "weight": 1.3,
    },
    "gpt-oss": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "gpt-oss:120b-cloud",
        "weight": 1.9,
    },
    "devstral": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "devstral-2:123b-cloud",
        "weight": 1.5,
    },
}

PROXY_URL = "http://127.0.0.1:18800"

# ── Task pool (escalating complexity) ────────────────────────────────────────
TASKS = {
    "nano": [
        "bonjour", "merci", "oui", "non", "salut",
        "ok", "1+1", "date", "heure", "test",
    ],
    "micro": [
        "Capitale de la France?",
        "2+3*4=?",
        "Couleur du ciel?",
        "Qui a invente Internet?",
        "def hello(): ...",
        "Combien de continents?",
        "Pi arrondi a 2 decimales?",
        "Bonjour en japonais?",
        "Racine carree de 144?",
        "HTTP status 404 signifie?",
    ],
    "small": [
        "Compare TCP vs UDP en 3 points",
        "Ecris une fonction Python qui inverse une string",
        "Difference entre stack et heap?",
        "Explique le pattern singleton en 2 phrases",
        "Liste 5 commandes git essentielles",
        "Avantages de TypeScript vs JavaScript?",
        "Ecris un one-liner Python pour lire un fichier JSON",
        "Comment fonctionne un hash table?",
        "Difference entre REST et GraphQL?",
        "Qu'est-ce qu'un mutex?",
    ],
    "medium": [
        "Ecris une classe Python AsyncRetryClient avec backoff exponentiel",
        "Compare REST vs GraphQL vs gRPC: tableau 5 criteres",
        "Explique le CAP theorem avec des exemples concrets",
        "Ecris un decorator Python pour le caching avec TTL",
        "Analyse les trade-offs monolithe vs microservices",
        "Un train part a 8h a 120km/h, un autre a 9h a 150km/h. Quand se croisent-ils?",
        "Ecris un parser de CSV en Python sans lib externe",
        "Compare 3 strategies de load balancing",
        "Ecris un rate limiter token bucket en Python",
        "Explique la difference entre concurrence et parallelisme avec code",
    ],
    "large": [
        "Ecris un parser JSON streaming Python pour fichiers >1GB sans tout charger en memoire",
        "Cree un mini ORM Python avec SQLite: Model, Field, Query builder",
        "Architecture complete d'un systeme de notification push: diagramme + composants + flow",
        "Ecris un pipeline ETL async Python: extract HTTP, transform, load SQLite avec retry",
        "Compare 5 bases de donnees (SQLite, Postgres, MongoDB, Redis, DynamoDB) sur 8 criteres",
        "Ecris un serveur WebSocket Python avec rooms, broadcast, et heartbeat",
        "Analyse le dilemme du prisonnier itere: strategies, Nash equilibrium, code simulation",
        "Ecris un task scheduler Python avec cron expressions, priorites, et persistence SQLite",
        "Design pattern event sourcing: explique + implementation Python complete",
        "Ecris un circuit breaker Python avec etats open/half-open/closed et metriques",
    ],
    "xl": [
        "Ecris un mini framework de test unitaire Python: assertions, fixtures, setup/teardown, rapport HTML",
        "Architecture microservices complete pour un e-commerce: 6 services, API gateway, events, saga pattern",
        "Ecris un compilateur d'expressions arithmetiques: lexer, parser AST, evaluateur, avec gestion erreurs",
        "Compare en detail React vs Vue vs Svelte vs Angular vs Solid: 10 criteres, benchmarks, recommandations",
        "Ecris un systeme de cache distribue Python: L1 mem + L2 disk, invalidation, replication, consistent hashing",
    ],
    # ── New patterns (agents crees dans etoile.db) ──
    "creative": [
        "Ecris un poeme sur la programmation",
        "Invente une histoire courte de 5 lignes sur un robot",
        "Redige un article de blog sur l'IA en 2026",
        "Ecris un scenario de film en 1 paragraphe",
        "Cree un dialogue entre Python et JavaScript",
    ],
    "math": [
        "Calcule la derivee de x^3 + 2x^2 - 5x + 3",
        "Resous l'equation 3x + 7 = 22",
        "Probabilite de tirer 2 as d'un jeu de 52 cartes?",
        "Calcule la somme des 100 premiers entiers naturels",
        "Matrice 2x2 [[1,2],[3,4]] - calcule l'inverse",
    ],
    "trading": [
        "Analyse technique BTC/USDT: RSI + MACD signals",
        "Compare DCA vs Lump Sum pour crypto sur 1 an",
        "Explique le pattern double bottom en trading",
        "Strategies de risk management pour futures 10x",
        "Calcule le risk/reward ratio pour TP 0.4% SL 0.25%",
    ],
    "security": [
        "Quels sont les 3 risques OWASP les plus critiques?",
        "Ecris un middleware de validation d'input Python anti-injection",
        "Comment implementer JWT refresh tokens de facon securisee?",
        "Audit ce code: `cursor.execute(f'SELECT * FROM users WHERE id={user_id}')`",
        "Explique la difference entre chiffrement symetrique et asymetrique",
    ],
    "architecture": [
        "Design un systeme de file d'attente distribue avec garantie at-least-once",
        "Compare event sourcing vs CRUD classique: quand utiliser quoi?",
        "Architecture d'un rate limiter distribue pour API gateway",
        "Design pattern CQRS: explique + schema + quand l'utiliser",
        "Strategie de migration monolithe vers microservices en 5 etapes",
    ],
    "data": [
        "Ecris une requete SQL pour trouver les doublons dans une table",
        "Compare SQLite WAL vs DELETE journal mode: performance",
        "Ecris un script Python d'ETL: CSV -> nettoyage -> SQLite",
        "Schema de base pour un systeme de logs structure",
        "Optimise cette requete: SELECT * FROM orders WHERE date > '2025-01-01' ORDER BY amount DESC",
    ],
    "devops": [
        "Ecris un Dockerfile multi-stage pour une app Python FastAPI",
        "Script GitHub Actions pour CI: lint + test + build",
        "Explique la strategie de branching GitFlow en 4 points",
        "Ecris un script de health check pour 5 services en bash",
        "Compare Docker Compose vs Kubernetes pour un petit cluster",
    ],
}

# Pre-compute weighted task selection for 1000 cycles
# 14 patterns total — mix all sizes including new pattern types
SIZE_WEIGHTS = {
    "nano": 80, "micro": 100, "small": 100,
    "medium": 100, "large": 80, "xl": 60,
    "creative": 80, "math": 80, "trading": 60,
    "security": 60, "architecture": 60, "data": 60, "devops": 40,
}

# ── Strategies ───────────────────────────────────────────────────────────────
PATTERN_NODE_MAP = {
    "nano": "OL1", "micro": "OL1", "small": "M1",
    "medium": "M1", "large": "M1", "xl": "M1",
    "creative": "M1", "math": "M2", "trading": "M1",
    "security": "M1", "architecture": "M1", "data": "M1", "devops": "M1",
}

ROUND_ROBIN_IDX = 0
DIRECT_NODES = ["M1", "M2", "M3", "OL1"]  # local nodes for race/robin


async def call_node(client: httpx.AsyncClient, node_name: str, prompt: str, timeout: float = 60) -> dict:
    """Call a single node, return standardized result dict."""
    node = NODES[node_name]
    t0 = time.time()
    try:
        if node["type"] == "lmstudio":
            body = {
                "model": node["model"],
                "input": f"{node.get('prefix', '')}{prompt}",
                "temperature": 0.3,
                "max_output_tokens": node.get("max_tokens", 1024),
                "stream": False,
                "store": False,
            }
            r = await client.post(node["url"], json=body, timeout=timeout)
            data = r.json()
            content = ""
            for o in data.get("output", []):
                if o.get("type") == "message":
                    c = o.get("content", "")
                    if isinstance(c, list):
                        content = c[0].get("text", "") if c else ""
                    else:
                        content = str(c)
        else:  # ollama
            body = {
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
            }
            r = await client.post(node["url"], json=body, timeout=timeout)
            data = r.json()
            content = data.get("message", {}).get("content", "")

        latency = (time.time() - t0) * 1000
        tokens = len(content.split())
        return {"node": node_name, "content": content, "latency_ms": latency, "tokens": tokens, "ok": bool(content)}
    except Exception as e:
        return {"node": node_name, "content": "", "latency_ms": (time.time() - t0) * 1000, "tokens": 0, "ok": False, "error": str(e)[:200]}


async def call_proxy(client: httpx.AsyncClient, prompt: str, timeout: float = 60) -> dict:
    """Send through direct-proxy:18800 /chat (OpenClaw routing)."""
    t0 = time.time()
    try:
        r = await client.post(f"{PROXY_URL}/chat", json={"text": prompt}, timeout=timeout)
        data = r.json()
        content = data.get("data", {}).get("text", "") if data.get("ok") else ""
        model = data.get("data", {}).get("model", "proxy")
        latency = (time.time() - t0) * 1000
        tokens = len(content.split())
        return {"node": f"proxy:{model}", "content": content, "latency_ms": latency, "tokens": tokens, "ok": bool(content)}
    except Exception as e:
        return {"node": "proxy", "content": "", "latency_ms": (time.time() - t0) * 1000, "tokens": 0, "ok": False, "error": str(e)[:200]}


async def strat_single(client, size, prompt):
    """Best node for this task size."""
    node = PATTERN_NODE_MAP.get(size, "M1")
    return await call_node(client, node, prompt), "single"


async def strat_race(client, size, prompt):
    """All local nodes in parallel, fastest wins."""
    tasks = [call_node(client, n, prompt) for n in DIRECT_NODES]
    results = await asyncio.gather(*tasks)
    ok = [r for r in results if r["ok"] and r["content"]]
    if ok:
        best = min(ok, key=lambda x: x["latency_ms"])
        return best, f"race:winner={best['node']}"
    return results[0] if results else {"ok": False}, "race:all_fail"


async def strat_round_robin(client, size, prompt):
    """Rotate through local nodes."""
    global ROUND_ROBIN_IDX
    nodes = DIRECT_NODES
    node = nodes[ROUND_ROBIN_IDX % len(nodes)]
    ROUND_ROBIN_IDX += 1
    return await call_node(client, node, prompt), f"robin:{node}"


async def strat_consensus(client, size, prompt):
    """2 nodes, weighted vote."""
    primary = PATTERN_NODE_MAP.get(size, "M1")
    secondary = "M2" if primary != "M2" else "M1"
    r1, r2 = await asyncio.gather(
        call_node(client, primary, prompt),
        call_node(client, secondary, prompt),
    )
    w1 = NODES[primary]["weight"]
    w2 = NODES[secondary]["weight"]
    if r1["ok"] and r2["ok"]:
        winner = r1 if w1 >= w2 else r2
        return winner, f"consensus:{primary}({w1})>{secondary}({w2})"
    return (r1 if r1["ok"] else r2), "consensus:fallback"


async def strat_proxy(client, size, prompt):
    """Through OpenClaw direct-proxy."""
    return await call_proxy(client, prompt), "proxy"


async def strat_cloud(client, size, prompt):
    """Cloud model (gpt-oss or devstral) for complex tasks."""
    node = "gpt-oss" if size in ("large", "xl") else "devstral"
    return await call_node(client, node, prompt, timeout=120), f"cloud:{node}"


async def strat_fallback_chain(client, size, prompt):
    """M1 -> M2 -> M3 -> OL1 until one succeeds."""
    for n in ["M1", "M2", "M3", "OL1"]:
        r = await call_node(client, n, prompt)
        if r["ok"] and r["content"]:
            return r, f"chain:hit={n}"
    return r, "chain:all_fail"


STRATEGIES = {
    "single": strat_single,
    "race": strat_race,
    "round_robin": strat_round_robin,
    "consensus": strat_consensus,
    "fallback_chain": strat_fallback_chain,
}

# Strategy distribution per size (what % of cycles use each strategy)
# Proxy offline → replaced with more single/race/consensus
_FAST = ["single"] * 40 + ["round_robin"] * 30 + ["race"] * 20 + ["fallback_chain"] * 10
_BALANCED = ["single"] * 25 + ["race"] * 25 + ["consensus"] * 20 + ["round_robin"] * 15 + ["fallback_chain"] * 15
_HEAVY = ["single"] * 20 + ["consensus"] * 30 + ["race"] * 25 + ["fallback_chain"] * 15 + ["round_robin"] * 10

STRAT_DISTRIBUTION = {
    "nano": _FAST, "micro": _FAST,
    "small": _BALANCED, "medium": _BALANCED,
    "large": _HEAVY, "xl": _HEAVY,
    "creative": _BALANCED, "math": _HEAVY, "trading": _HEAVY,
    "security": _HEAVY, "architecture": _HEAVY,
    "data": _BALANCED, "devops": _BALANCED,
}


# ── Telegram helpers ─────────────────────────────────────────────────────────

async def telegram_send(client: httpx.AsyncClient, text: str):
    """Send text message to Telegram."""
    try:
        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": text[:4096], "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception:
        pass


def telegram_voice(text: str):
    """Send vocal message to Telegram via TTS pipeline."""
    try:
        clean = text.replace("\r\n", " ").replace("\n", " ")[:2000]
        subprocess.run(
            ["python", TTS_SCRIPT, "--telegram"],
            input=clean, capture_output=True, text=True, timeout=30,
        )
    except Exception:
        pass


# ── Generate task list ───────────────────────────────────────────────────────

def generate_task_list(n: int = 1000) -> list[dict]:
    """Generate N tasks with size distribution and strategy assignment."""
    tasks = []
    pool = []
    for size, count in SIZE_WEIGHTS.items():
        for _ in range(count):
            pool.append(size)
    random.shuffle(pool)

    for i in range(n):
        size = pool[i % len(pool)]
        prompt = random.choice(TASKS[size])
        strat = random.choice(STRAT_DISTRIBUTION[size])
        tasks.append({"id": i + 1, "size": size, "prompt": prompt, "strategy": strat})
    return tasks


# ── Main benchmark ───────────────────────────────────────────────────────────

async def run_benchmark(total_cycles: int = 1000, concurrency: int = 5):
    ts_start = time.time()
    tasks = generate_task_list(total_cycles)

    # DB
    db = sqlite3.connect(str(PROJECT_ROOT / "etoile.db"))
    cur = db.cursor()

    results = []
    ok_count = 0
    batch_size = 50  # telegram progress every N

    print(f"\n{'=' * 72}")
    print(f"  JARVIS MEGA-BENCHMARK — {total_cycles} CYCLES")
    print(f"  Noeuds: {len(NODES)} | Strategies: {len(STRATEGIES)} | Concurrency: {concurrency}")
    print(f"  Sizes: {dict(SIZE_WEIGHTS)}")
    print(f"{'=' * 72}\n")

    async with httpx.AsyncClient() as client:
        # Send start notification to Telegram
        await telegram_send(client, f"*JARVIS Mega-Benchmark lance*\n{total_cycles} cycles | {len(NODES)} noeuds | {len(STRATEGIES)} strategies")

        sem = asyncio.Semaphore(concurrency)

        async def run_one(task: dict) -> dict:
            async with sem:
                strat_fn = STRATEGIES[task["strategy"]]
                result, detail = await strat_fn(client, task["size"], task["prompt"])
                return {
                    "id": task["id"],
                    "size": task["size"],
                    "prompt": task["prompt"][:100],
                    "strategy": task["strategy"],
                    "detail": detail,
                    "node": result.get("node", "?"),
                    "latency_ms": result.get("latency_ms", 0),
                    "tokens": result.get("tokens", 0),
                    "ok": result.get("ok", False),
                    "error": result.get("error", ""),
                }

        # Run in batches for progress tracking
        for batch_start in range(0, total_cycles, batch_size):
            batch_end = min(batch_start + batch_size, total_cycles)
            batch_tasks = tasks[batch_start:batch_end]

            batch_coros = [run_one(t) for t in batch_tasks]
            batch_results = await asyncio.gather(*batch_coros)

            for r in batch_results:
                results.append(r)
                if r["ok"]:
                    ok_count += 1

                # Print progress line
                status = "OK" if r["ok"] else "FAIL"
                preview = r.get("prompt", "")[:40]
                print(f"  [{r['id']:4d}/{total_cycles}] {r['size']:6s} {r['strategy']:14s} {r['node']:16s} {r['latency_ms']:7.0f}ms {r['tokens']:4d}tok {status}")

                # Save to SQLite
                cur.execute("""INSERT INTO agent_dispatch_log
                    (request_text, classified_type, agent_id, model_used, node, strategy,
                     latency_ms, tokens_in, tokens_out, success, error_msg, quality_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (r["prompt"], r["size"], "mega-bench",
                     r["node"], r["node"], r["strategy"],
                     r["latency_ms"], len(r["prompt"].split()), r["tokens"],
                     1 if r["ok"] else 0,
                     r["error"][:200] if r["error"] else None,
                     min(1.0, r["tokens"] / max(1, len(r["prompt"].split()) * 3))
                    ))

            db.commit()

            # Telegram progress update
            elapsed = time.time() - ts_start
            rate = batch_end / max(1, elapsed)
            eta = (total_cycles - batch_end) / max(0.01, rate)
            batch_ok = sum(1 for r in batch_results if r["ok"])
            avg_lat = sum(r["latency_ms"] for r in batch_results) / max(1, len(batch_results))
            await telegram_send(client,
                f"*[{batch_end}/{total_cycles}]* {ok_count}/{batch_end} OK ({100*ok_count/max(1,batch_end):.0f}%) "
                f"| batch {batch_ok}/{len(batch_results)} | avg {avg_lat:.0f}ms | ETA {eta:.0f}s"
            )

        # ── Analysis ─────────────────────────────────────────────────────────
        total_time = time.time() - ts_start

        print(f"\n{'=' * 72}")
        print(f"  RESULTATS: {ok_count}/{total_cycles} OK ({100 * ok_count / max(1, total_cycles):.1f}%)")
        print(f"  Duree totale: {total_time:.1f}s | Throughput: {total_cycles / total_time:.1f} req/s")
        print(f"{'=' * 72}")

        # By strategy
        print(f"\n--- Par Strategie ---")
        strat_stats = {}
        for s in STRATEGIES:
            sr = [r for r in results if r["strategy"] == s]
            if sr:
                ok = sum(1 for r in sr if r["ok"])
                avg_lat = sum(r["latency_ms"] for r in sr) / len(sr)
                avg_tok = sum(r["tokens"] for r in sr) / len(sr)
                strat_stats[s] = {"count": len(sr), "ok": ok, "rate": ok / len(sr), "avg_ms": avg_lat, "avg_tok": avg_tok}
                print(f"  {s:16s} {ok:4d}/{len(sr):4d} ({100 * ok / len(sr):5.1f}%)  avg={avg_lat:7.0f}ms  tok={avg_tok:.0f}")

        # By size
        print(f"\n--- Par Taille ---")
        size_stats = {}
        for sz in TASKS:
            sr = [r for r in results if r["size"] == sz]
            if sr:
                ok = sum(1 for r in sr if r["ok"])
                avg_lat = sum(r["latency_ms"] for r in sr) / len(sr)
                size_stats[sz] = {"count": len(sr), "ok": ok, "rate": ok / len(sr), "avg_ms": avg_lat}
                print(f"  {sz:8s} {ok:4d}/{len(sr):4d} ({100 * ok / len(sr):5.1f}%)  avg={avg_lat:7.0f}ms")

        # By node
        print(f"\n--- Par Noeud ---")
        node_stats = {}
        for r in results:
            n = r["node"].split(":")[0] if ":" in r["node"] else r["node"]
            if n not in node_stats:
                node_stats[n] = {"count": 0, "ok": 0, "total_ms": 0, "total_tok": 0}
            node_stats[n]["count"] += 1
            node_stats[n]["ok"] += 1 if r["ok"] else 0
            node_stats[n]["total_ms"] += r["latency_ms"]
            node_stats[n]["total_tok"] += r["tokens"]
        for n, s in sorted(node_stats.items(), key=lambda x: -x[1]["count"]):
            avg = s["total_ms"] / max(1, s["count"])
            print(f"  {n:16s} {s['ok']:4d}/{s['count']:4d} ({100 * s['ok'] / max(1, s['count']):5.1f}%)  avg={avg:7.0f}ms")

        # Best strategy per size
        print(f"\n--- Meilleure Strategie par Taille ---")
        best_map = {}
        for sz in TASKS:
            best_s, best_lat = None, float("inf")
            for s in STRATEGIES:
                sr = [r for r in results if r["size"] == sz and r["strategy"] == s and r["ok"]]
                if sr:
                    avg = sum(r["latency_ms"] for r in sr) / len(sr)
                    if avg < best_lat:
                        best_lat = avg
                        best_s = s
            if best_s:
                best_map[sz] = {"strategy": best_s, "avg_ms": best_lat}
                print(f"  {sz:8s} -> {best_s:16s} ({best_lat:.0f}ms)")

        # ── Save report ──────────────────────────────────────────────────────
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_cycles": total_cycles,
            "ok": ok_count,
            "fail": total_cycles - ok_count,
            "rate": f"{100 * ok_count / max(1, total_cycles):.1f}%",
            "duration_s": round(total_time, 1),
            "throughput_rps": round(total_cycles / total_time, 2),
            "by_strategy": strat_stats,
            "by_size": size_stats,
            "by_node": {k: {**v, "avg_ms": v["total_ms"] / max(1, v["count"])} for k, v in node_stats.items()},
            "best_per_size": best_map,
            "results": results,
        }
        report_path = PROJECT_ROOT / "data" / "mega_benchmark_1000.json"
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"\nRapport: {report_path}")
        print(f"SQL: {total_cycles} entrees dans agent_dispatch_log")

        # ── Telegram final report ────────────────────────────────────────────
        summary_lines = [
            f"*MEGA-BENCHMARK TERMINE*",
            f"*{ok_count}/{total_cycles}* OK ({100 * ok_count / max(1, total_cycles):.1f}%)",
            f"Duree: {total_time:.0f}s | {total_cycles / total_time:.1f} req/s",
            "",
            "*Par strategie:*",
        ]
        for s, d in sorted(strat_stats.items(), key=lambda x: -x[1]["rate"]):
            summary_lines.append(f"  {s}: {d['ok']}/{d['count']} ({100*d['rate']:.0f}%) avg {d['avg_ms']:.0f}ms")
        summary_lines.append("\n*Par taille:*")
        for sz in ["nano", "micro", "small", "medium", "large", "xl"]:
            if sz in size_stats:
                d = size_stats[sz]
                summary_lines.append(f"  {sz}: {d['ok']}/{d['count']} ({100*d['rate']:.0f}%) avg {d['avg_ms']:.0f}ms")
        summary_lines.append("\n*Meilleur routing:*")
        for sz, d in best_map.items():
            summary_lines.append(f"  {sz} -> {d['strategy']} ({d['avg_ms']:.0f}ms)")

        summary_text = "\n".join(summary_lines)
        await telegram_send(client, summary_text)

        # ── Vocal summary ────────────────────────────────────────────────────
        vocal = (
            f"Mega benchmark termine. {ok_count} sur {total_cycles} cycles reussis, "
            f"soit {100 * ok_count / max(1, total_cycles):.0f} pourcent. "
            f"Duree totale {total_time:.0f} secondes, "
            f"debit {total_cycles / total_time:.1f} requetes par seconde. "
        )
        # Add best strategies per size
        for sz, d in best_map.items():
            vocal += f"Taille {sz}: meilleure strategie {d['strategy']}, {d['avg_ms']:.0f} millisecondes. "

        print(f"\nEnvoi vocal Telegram...")
        telegram_voice(vocal)
        print("Vocal envoye.")

    db.close()
    return report


if __name__ == "__main__":
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    conc = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    asyncio.run(run_benchmark(cycles, conc))
