#!/usr/bin/env python3
"""JARVIS Multi-Path Dispatch Benchmark v1.0
=============================================
Benchmark exhaustif: 6 chemins x N noeuds x 60 taches (nano->xl).
+ Agent Factory: genere des agents optimaux par pattern decouvert.

Usage:
    uv run python scripts/multi_path_benchmark.py
    uv run python scripts/multi_path_benchmark.py --phase 1      # cartographie seule
    uv run python scripts/multi_path_benchmark.py --factory-only  # genere agents depuis dernier JSON
"""
import asyncio
import httpx
import json
import sqlite3
import subprocess
import sys
import io
import os
import time
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════

TURBO_ROOT = Path("/home/turbo/jarvis-m1-ops")
DATA_DIR = TURBO_ROOT / "data"
AGENTS_DIR = TURBO_ROOT / "plugins" / "jarvis-turbo" / "agents"
ETOILE_DB = TURBO_ROOT / "data" / "etoile.db"
TIMEOUT = 120  # seconds per request
PARALLEL_LIMIT = 5  # max concurrent requests per phase

# ── NODES ────────────────────────────────────────────────────────────────

NODES = {
    "M1/qwen3-8b": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "qwen3-8b",
        "prefix": "/nothink\n",
        "max_tokens": 1024,
        "weight": 1.8,
    },
    "M2/deepseek-r1": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "deepseek-r1-0528-qwen3-8b",
        "prefix": "",
        "max_tokens": 2048,
        "weight": 1.5,
    },
    "M3/deepseek-r1": {
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "deepseek-r1-0528-qwen3-8b",
        "prefix": "",
        "max_tokens": 2048,
        "weight": 1.2,
    },
    "OL1/qwen3-1.7b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "qwen3:1.7b",
        "weight": 1.3,
    },
    "OL1/qwen3-14b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "qwen3:14b",
        "weight": 1.4,
    },
    # DELETED: model removed from Ollama
    # "OL1/gpt-oss-120b": {
    #     "url": "http://127.0.0.1:11434/api/chat",
    #     "type": "ollama",
    #     "model": "gpt-oss:120b-cloud",
    #     "weight": 1.9,
    # },
    # DELETED: model removed from Ollama
    # "OL1/devstral-123b": {
    #     "url": "http://127.0.0.1:11434/api/chat",
    #     "type": "ollama",
    #     "model": "devstral-2:123b-cloud",
    #     "weight": 1.5,
    # },
}

# ── 6 PATHS ──────────────────────────────────────────────────────────────

PATHS = {
    "P1_DIRECT": "Direct HTTP curl → LM Studio / Ollama",
    "P2_MCP": "MCP bridge_query via mcp_server.py",
    "P3_PROXY": "Canvas direct-proxy.js :18800 (query enhancement)",
    "P4_EXTERNAL": "External proxy (gemini-proxy.js / claude-proxy.js)",
    "P5_CONSENSUS": "Consensus mesh (N noeuds parallele, vote pondere)",
    "P6_COMMANDER": "Commander pipeline (classify→decompose→dispatch→verify)",
}

# ── TASKS (60 taches, 6 tailles x 6 categories + extras) ────────────────

TASK_BANK = {
    "nano": [
        {"id": "N01", "cat": "simple",    "prompt": "2+2?"},
        {"id": "N02", "cat": "simple",    "prompt": "Bonjour JARVIS"},
        {"id": "N03", "cat": "simple",    "prompt": "Oui ou non: le ciel est bleu?"},
        {"id": "N04", "cat": "code",      "prompt": "print('hello') en Python"},
        {"id": "N05", "cat": "simple",    "prompt": "Capitale de la France?"},
        {"id": "N06", "cat": "simple",    "prompt": "Combien font 10*10?"},
        {"id": "N07", "cat": "code",      "prompt": "len([1,2,3]) retourne quoi?"},
        {"id": "N08", "cat": "reasoning", "prompt": "Si A>B et B>C, A>C?"},
        {"id": "N09", "cat": "system",    "prompt": "Quel OS utilise JARVIS?"},
        {"id": "N10", "cat": "simple",    "prompt": "Dis OK"},
    ],
    "micro": [
        {"id": "U01", "cat": "code",      "prompt": "Ecris une fonction Python max_of_list(lst) qui retourne le maximum"},
        {"id": "U02", "cat": "code",      "prompt": "Ecris un one-liner Python pour inverser une chaine"},
        {"id": "U03", "cat": "reasoning", "prompt": "Un train part a 8h a 120km/h, un autre a 9h a 150km/h. Quand le 2e rattrape?"},
        {"id": "U04", "cat": "simple",    "prompt": "Donne les capitales de France, Allemagne, Japon en une ligne"},
        {"id": "U05", "cat": "analysis",  "prompt": "Compare TCP vs UDP en 3 points cles"},
        {"id": "U06", "cat": "code",      "prompt": "Ecris une list comprehension Python qui filtre les nombres pairs de 1 a 20"},
        {"id": "U07", "cat": "system",    "prompt": "Comment verifier l'espace disque en Python?"},
        {"id": "U08", "cat": "reasoning", "prompt": "Pourquoi le tri rapide est O(n log n) en moyenne?"},
        {"id": "U09", "cat": "analysis",  "prompt": "3 differences entre REST et GraphQL"},
        {"id": "U10", "cat": "simple",    "prompt": "Liste 5 langages de programmation populaires"},
    ],
    "small": [
        {"id": "S01", "cat": "code",      "prompt": "Ecris un decorator Python @timer qui mesure le temps d'execution d'une fonction et l'affiche"},
        {"id": "S02", "cat": "code",      "prompt": "Ecris une fonction async Python qui fait 3 requetes HTTP en parallele avec asyncio.gather"},
        {"id": "S03", "cat": "reasoning", "prompt": "Compare DCA vs lump sum investing. Lequel est optimal pour un horizon 5 ans? Justifie avec des arguments quantitatifs"},
        {"id": "S04", "cat": "analysis",  "prompt": "Analyse les avantages et inconvenients de SQLite vs PostgreSQL pour une app avec 1000 users simultanes"},
        {"id": "S05", "cat": "system",    "prompt": "Ecris un script Python qui monitore l'utilisation CPU et RAM toutes les 5 secondes et alerte si >80%"},
        {"id": "S06", "cat": "code",      "prompt": "Ecris une classe Python LRUCache avec get/put en O(1) utilisant OrderedDict"},
        {"id": "S07", "cat": "analysis",  "prompt": "Compare Docker vs Podman vs LXC: securite, performance, facilite d'usage"},
        {"id": "S08", "cat": "reasoning", "prompt": "Un algorithme a une complexite T(n) = 2T(n/2) + n. Resous la recurrence et donne la complexite Big-O"},
        {"id": "S09", "cat": "code",      "prompt": "Ecris un context manager Python pour mesurer le temps d'un bloc de code avec __enter__/__exit__"},
        {"id": "S10", "cat": "system",    "prompt": "Ecris une fonction Python qui liste tous les processus Windows consommant plus de 100MB de RAM"},
    ],
    "medium": [
        {"id": "M01", "cat": "code",      "prompt": "Ecris une classe Python AsyncHTTPClient avec retry exponentiel, timeout configurable, circuit breaker, et logging structure"},
        {"id": "M02", "cat": "code",      "prompt": "Ecris un rate limiter token bucket en Python avec support multi-thread et fenetre glissante"},
        {"id": "M03", "cat": "analysis",  "prompt": "Architecture complete d'un systeme de trading automatise: composants, flux de donnees, gestion des risques, latence, haute disponibilite. Schema et justifications"},
        {"id": "M04", "cat": "reasoning", "prompt": "Demontre mathematiquement pourquoi le probleme du voyageur de commerce est NP-dur. Explique la reduction depuis le probleme de Hamilton"},
        {"id": "M05", "cat": "code",      "prompt": "Ecris un parser d'expressions mathematiques en Python avec tokenizer, AST, et evaluateur supportant +,-,*,/,^,parentheses"},
        {"id": "M06", "cat": "system",    "prompt": "Ecris un health checker Python complet qui verifie: CPU, RAM, disque, GPU (nvidia-smi), reseau, et services systemd/Windows. Retourne un JSON structure"},
        {"id": "M07", "cat": "analysis",  "prompt": "Compare 5 strategies de deploiement: blue-green, canary, rolling, recreate, shadow. Pour chacune: quand l'utiliser, risques, rollback, cout infra"},
        {"id": "M08", "cat": "code",      "prompt": "Ecris un mini ORM Python avec SQLite: Model base class, champs types, create_table, insert, select avec where, update, delete"},
        {"id": "M09", "cat": "reasoning", "prompt": "Analyse game-theorique du dilemme du prisonnier itere. Compare tit-for-tat, always defect, pavlov. Quelle strategie domine et pourquoi?"},
        {"id": "M10", "cat": "system",    "prompt": "Ecris un load balancer Python async qui distribue les requetes entre N workers avec weighted round-robin, health checks, et circuit breaker"},
    ],
    "large": [
        {"id": "L01", "cat": "code",      "prompt": "Ecris un parser JSON streaming en Python qui traite des fichiers >1GB sans charger en memoire. Supporte objets imbriques, arrays, et retourne un iterateur"},
        {"id": "L02", "cat": "code",      "prompt": "Ecris un framework de test unitaire complet en Python: TestCase, assertions (assertEqual, assertRaises, assertIn), fixtures (setUp/tearDown), test discovery, et rapport console colore"},
        {"id": "L03", "cat": "analysis",  "prompt": "Architecture complete d'un moteur de recherche: crawling, indexation inversee, ranking (TF-IDF + PageRank), serving, cache, sharding. Avec schemas, estimations de capacite, et choix technologiques"},
        {"id": "L04", "cat": "reasoning", "prompt": "Analyse complete des algorithmes de consensus distribue: Paxos, Raft, PBFT, Tendermint. Pour chacun: garanties (safety/liveness), tolerance aux fautes, performance, cas d'usage. Comparaison tabulaire + recommandation"},
        {"id": "L05", "cat": "code",      "prompt": "Ecris un serveur HTTP minimal en Python (socket raw, pas de framework): parse requete, routing, middleware, static files, JSON response, error handling, logging, keep-alive"},
        {"id": "L06", "cat": "system",    "prompt": "Ecris un monitoring agent Python complet: collecte metriques (CPU/RAM/GPU/disque/reseau) toutes les 10s, stockage SQLite, alerting configurable par seuil, API REST pour consulter, et export Prometheus"},
        {"id": "L07", "cat": "analysis",  "prompt": "Compare les architectures microservices vs monolithe vs serverless pour un SaaS B2B avec 10k users: cout, latence, scalabilite, DX, observabilite, securite. Matrice de decision + recommandation argumentee"},
        {"id": "L08", "cat": "code",      "prompt": "Ecris un task scheduler cron-like en Python: parse expressions cron (*/5 * * * *), execution async, persistence SQLite, retry avec backoff, logging, et API pour CRUD des jobs"},
        {"id": "L09", "cat": "reasoning", "prompt": "Analyse mathematique des strategies de market making: spread optimal (Avellaneda-Stoikov), gestion du risque d'inventaire, impact du HFT, conditions de marche favorables. Formules + simulation numerique"},
        {"id": "L10", "cat": "system",    "prompt": "Ecris un reverse proxy Python async avec: load balancing, SSL termination, rate limiting, circuit breaker, health checks, sticky sessions, WebSocket support, et access logging"},
    ],
    "xl": [
        {"id": "X01", "cat": "code",      "prompt": "Ecris un compilateur complet pour un mini-langage: lexer, parser (recursive descent), AST, semantic analysis, code generation (Python bytecode ou stack machine). Supporte: variables, if/else, while, fonctions, types int/str/bool"},
        {"id": "X02", "cat": "code",      "prompt": "Ecris un database engine complet en Python: B-tree index, page storage, WAL journal, query parser (SELECT/INSERT/UPDATE/DELETE avec WHERE), transaction support (BEGIN/COMMIT/ROLLBACK), et REPL interactif"},
        {"id": "X03", "cat": "analysis",  "prompt": "Design complet d'une plateforme de trading haute frequence: architecture (FPGA vs software), order management, risk engine, market data handler, matching engine, colocation, compliance. Avec latences, estimations de cout, et plan de deploiement phase par phase"},
        {"id": "X04", "cat": "reasoning", "prompt": "Analyse exhaustive: peut-on creer une AGI avec l'architecture Transformer actuelle? Arguments pour/contre, limitations theoriques (Godel, complexite computationnelle), alternatives (neuro-symbolique, liquid networks), timeline estimee, risques existentiels. Synthese structuree 2000+ mots"},
        {"id": "X05", "cat": "code",      "prompt": "Ecris un framework web complet en Python (sans dependances externes): HTTP server async, router avec params, middleware chain, template engine (variables, loops, conditions), static file serving, session management, CSRF protection, et exemple d'application CRUD"},
    ],
}

ALL_TASKS = []
for size, tasks in TASK_BANK.items():
    for t in tasks:
        ALL_TASKS.append({**t, "size": size})


# ══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class BenchResult:
    task_id: str
    task_size: str
    task_cat: str
    prompt: str
    path_id: str
    node_id: str
    latency_ms: float
    tokens_out: int
    tok_per_sec: float
    success: bool
    quality_score: float
    output_preview: str  # first 200 chars
    error: str = ""
    overhead_ms: float = 0.0
    timestamp: str = ""


# ══════════════════════════════════════════════════════════════════════════
# PATH IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════

async def _call_lmstudio(client: httpx.AsyncClient, node: dict, prompt: str) -> tuple[str, int, float]:
    """Direct LM Studio Responses API call. Returns (output, tokens, elapsed_ms)."""
    t0 = time.perf_counter()
    body = {
        "model": node["model"],
        "input": node.get("prefix", "") + prompt,
        "temperature": 0.3,
        "max_output_tokens": node.get("max_tokens", 1024),
        "stream": False,
        "store": False,
    }
    r = await client.post(node["url"], json=body, timeout=TIMEOUT)
    elapsed = (time.perf_counter() - t0) * 1000
    data = r.json()
    # Extract from output[] — take last message type block
    text = ""
    tokens = 0
    for block in reversed(data.get("output", [])):
        if block.get("type") == "message":
            for c in block.get("content", []):
                if c.get("type") == "output_text":
                    text = c.get("text", "")
                    break
            break
    if not text and data.get("output"):
        # fallback: first content
        for block in data.get("output", []):
            if block.get("type") == "message":
                for c in block.get("content", []):
                    text = c.get("text", "")
                    if text:
                        break
            if text:
                break
    tokens = data.get("usage", {}).get("output_tokens", len(text.split()))
    return text, tokens, elapsed


async def _call_ollama(client: httpx.AsyncClient, node: dict, prompt: str) -> tuple[str, int, float]:
    """Direct Ollama API call."""
    t0 = time.perf_counter()
    body = {
        "model": node["model"],
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
    }
    r = await client.post(node["url"], json=body, timeout=TIMEOUT)
    elapsed = (time.perf_counter() - t0) * 1000
    data = r.json()
    text = data.get("message", {}).get("content", "")
    tokens = data.get("eval_count", len(text.split()))
    return text, tokens, elapsed


async def path_p1_direct(client: httpx.AsyncClient, node_id: str, prompt: str) -> tuple[str, int, float]:
    """P1: Direct HTTP to node."""
    node = NODES[node_id]
    if node["type"] == "lmstudio":
        return await _call_lmstudio(client, node, prompt)
    else:
        return await _call_ollama(client, node, prompt)


async def path_p3_proxy(client: httpx.AsyncClient, node_id: str, prompt: str) -> tuple[str, int, float]:
    """P3: Via Canvas direct-proxy.js :18800."""
    t0 = time.perf_counter()
    # Map node_id to model name for proxy
    node = NODES[node_id]
    model = node["model"]
    body = {"message": prompt, "model": model}
    r = await client.post("http://127.0.0.1:18800/chat", json=body, timeout=TIMEOUT)
    elapsed = (time.perf_counter() - t0) * 1000
    data = r.json()
    text = data.get("response", data.get("content", ""))
    tokens = len(text.split())
    return text, tokens, elapsed


async def path_p4_external(client: httpx.AsyncClient, node_id: str, prompt: str) -> tuple[str, int, float]:
    """P4: Via gemini-proxy.js or claude-proxy.js."""
    t0 = time.perf_counter()
    if "gemini" in node_id.lower():
        cmd = ["node", "/home/turbo/jarvis-m1-ops/gemini-proxy.js", "--json", prompt]
    else:
        cmd = ["node", "/home/turbo/jarvis-m1-ops/claude-proxy.js", "--json", "--budget", "0.30", prompt]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
    elapsed = (time.perf_counter() - t0) * 1000
    try:
        data = json.loads(stdout.decode("utf-8", errors="replace"))
        text = data.get("response", data.get("content", stdout.decode("utf-8", errors="replace")[:2000]))
    except json.JSONDecodeError:
        text = stdout.decode("utf-8", errors="replace")[:2000]
    tokens = len(text.split())
    return text, tokens, elapsed


async def path_p5_consensus(client: httpx.AsyncClient, node_id: str, prompt: str) -> tuple[str, int, float]:
    """P5: Consensus — query 3 nodes in parallel, weighted vote."""
    # Pick 3 nodes: the requested one + 2 others
    all_ids = list(NODES.keys())
    consensus_nodes = [node_id]
    for nid in all_ids:
        if nid != node_id and len(consensus_nodes) < 3:
            consensus_nodes.append(nid)

    t0 = time.perf_counter()
    tasks = [path_p1_direct(client, nid, prompt) for nid in consensus_nodes]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = (time.perf_counter() - t0) * 1000

    # Weighted vote: pick longest non-error response weighted by node weight
    best_text, best_tokens, best_score = "", 0, 0.0
    for nid, res in zip(consensus_nodes, results):
        if isinstance(res, Exception):
            continue
        text, tokens, _ = res
        weight = NODES[nid].get("weight", 1.0)
        score = len(text) * weight
        if score > best_score:
            best_text, best_tokens, best_score = text, tokens, score

    return best_text, best_tokens, elapsed


async def path_p6_commander(client: httpx.AsyncClient, node_id: str, prompt: str) -> tuple[str, int, float]:
    """P6: Commander pipeline — classify + dispatch + verify."""
    t0 = time.perf_counter()

    # Step 1: Classify (quick M1 call)
    classify_prompt = f"/nothink\nClassifie cette tache en un seul mot (code/analyse/reasoning/system/simple): {prompt[:100]}"
    try:
        cls_text, _, _ = await _call_lmstudio(client, NODES["M1/qwen3-8b"], classify_prompt)
        task_type = cls_text.strip().lower().split()[0] if cls_text.strip() else "simple"
    except Exception:
        task_type = "simple"

    # Step 2: Route to best node for task type
    ROUTING = {
        "code": "M1/qwen3-8b",  # was OL1/gpt-oss-120b, DELETED: model removed from Ollama
        "analyse": "M1/qwen3-8b",
        "analysis": "M1/qwen3-8b",
        "reasoning": "M2/deepseek-r1",
        "system": "M1/qwen3-8b",
        "simple": "OL1/qwen3-1.7b",
    }
    target = ROUTING.get(task_type, node_id)
    if target not in NODES:
        target = node_id

    # Step 3: Dispatch
    text, tokens, _ = await path_p1_direct(client, target, prompt)

    elapsed = (time.perf_counter() - t0) * 1000
    return text, tokens, elapsed


PATH_FUNCTIONS = {
    "P1_DIRECT": path_p1_direct,
    "P3_PROXY": path_p3_proxy,
    "P4_EXTERNAL": path_p4_external,
    "P5_CONSENSUS": path_p5_consensus,
    "P6_COMMANDER": path_p6_commander,
}

# P4 special nodes (external proxies)
EXTERNAL_NODES = {
    "GEMINI": {"type": "external", "weight": 1.2},
    "CLAUDE": {"type": "external", "weight": 1.2},
}


# ══════════════════════════════════════════════════════════════════════════
# QUALITY SCORING
# ══════════════════════════════════════════════════════════════════════════

def score_quality(task: dict, output: str) -> float:
    """Score output quality 0.0-1.0 based on heuristics."""
    if not output or len(output.strip()) < 3:
        return 0.0

    score = 0.0
    text = output.lower()
    cat = task["cat"]
    size = task["size"]

    # Length adequacy (scaled by expected size)
    size_expectations = {"nano": 5, "micro": 30, "small": 80, "medium": 200, "large": 500, "xl": 1000}
    expected = size_expectations.get(size, 50)
    words = len(output.split())
    length_ratio = min(words / expected, 2.0) / 2.0  # 0-1, caps at 2x expected
    score += length_ratio * 0.3

    # Non-empty meaningful content
    if words > 3:
        score += 0.2

    # Category-specific checks
    if cat == "code" and ("def " in text or "function" in text or "class " in text or "import " in text or "print" in text or "return" in text):
        score += 0.3
    elif cat == "reasoning" and any(w in text for w in ["donc", "parce", "car", "because", "thus", "so ", "conclusion"]):
        score += 0.3
    elif cat == "analysis" and any(w in text for w in ["avantage", "inconvenient", "compare", "vs", "difference", "advantage"]):
        score += 0.3
    elif cat == "system" and any(w in text for w in ["cpu", "ram", "gpu", "disk", "process", "memory", "import os", "import psutil"]):
        score += 0.3
    elif cat == "simple":
        score += 0.3  # simple tasks: any response is good

    # Coherence bonus: no repetition artifacts
    lines = output.strip().split("\n")
    if len(lines) > 1 and len(set(lines)) / len(lines) > 0.5:
        score += 0.2

    return min(score, 1.0)


# ══════════════════════════════════════════════════════════════════════════
# BENCHMARK ENGINE
# ══════════════════════════════════════════════════════════════════════════

async def run_single_test(
    client: httpx.AsyncClient,
    path_id: str,
    node_id: str,
    task: dict,
    semaphore: asyncio.Semaphore,
) -> BenchResult:
    """Run a single benchmark test."""
    async with semaphore:
        ts = datetime.now().isoformat()
        try:
            fn = PATH_FUNCTIONS[path_id]
            text, tokens, latency = await fn(client, node_id, task["prompt"])
            success = bool(text and len(text.strip()) > 2)
            quality = score_quality(task, text)
            tok_s = tokens / (latency / 1000) if latency > 0 else 0
            return BenchResult(
                task_id=task["id"], task_size=task["size"], task_cat=task["cat"],
                prompt=task["prompt"][:100], path_id=path_id, node_id=node_id,
                latency_ms=round(latency, 1), tokens_out=tokens,
                tok_per_sec=round(tok_s, 1), success=success,
                quality_score=round(quality, 3),
                output_preview=text[:200] if text else "",
                timestamp=ts,
            )
        except Exception as e:
            return BenchResult(
                task_id=task["id"], task_size=task["size"], task_cat=task["cat"],
                prompt=task["prompt"][:100], path_id=path_id, node_id=node_id,
                latency_ms=0, tokens_out=0, tok_per_sec=0, success=False,
                quality_score=0, output_preview="", error=str(e)[:200],
                timestamp=ts,
            )


async def phase1_cartography(client: httpx.AsyncClient) -> list[BenchResult]:
    """Phase 1: Map all paths x nodes with nano tasks."""
    print("\n" + "=" * 70)
    print("PHASE 1 — CARTOGRAPHIE (6 chemins x N noeuds x nano)")
    print("=" * 70)
    results = []
    sem = asyncio.Semaphore(3)  # conservative for mapping
    nano_tasks = [t for t in ALL_TASKS if t["size"] == "nano"][:3]  # 3 nano tasks for mapping

    # P1 DIRECT: all nodes
    tasks = []
    for node_id in NODES:
        for task in nano_tasks:
            tasks.append(run_single_test(client, "P1_DIRECT", node_id, task, sem))
    print(f"  P1_DIRECT: {len(tasks)} tests ({len(NODES)} noeuds x {len(nano_tasks)} tasks)...")
    batch = await asyncio.gather(*tasks)
    ok = sum(1 for r in batch if r.success)
    print(f"  P1_DIRECT: {ok}/{len(batch)} OK")
    results.extend(batch)

    # P3 PROXY: via canvas
    tasks = []
    for task in nano_tasks:
        tasks.append(run_single_test(client, "P3_PROXY", "M1/qwen3-8b", task, sem))
    print(f"  P3_PROXY: {len(tasks)} tests...")
    batch = await asyncio.gather(*tasks)
    ok = sum(1 for r in batch if r.success)
    print(f"  P3_PROXY: {ok}/{len(batch)} OK")
    results.extend(batch)

    # P4 EXTERNAL: gemini + claude
    tasks = []
    for ext_node in ["GEMINI", "CLAUDE"]:
        for task in nano_tasks[:1]:  # 1 task per external (slow + costly)
            tasks.append(run_single_test(client, "P4_EXTERNAL", ext_node, task, sem))
    print(f"  P4_EXTERNAL: {len(tasks)} tests...")
    batch = await asyncio.gather(*tasks)
    ok = sum(1 for r in batch if r.success)
    print(f"  P4_EXTERNAL: {ok}/{len(batch)} OK")
    results.extend(batch)

    # P5 CONSENSUS: 3 combos
    tasks = []
    for node_id in ["M1/qwen3-8b", "OL1/qwen3-14b"]:  # was OL1/gpt-oss-120b, DELETED: model removed from Ollama
        for task in nano_tasks[:2]:
            tasks.append(run_single_test(client, "P5_CONSENSUS", node_id, task, sem))
    print(f"  P5_CONSENSUS: {len(tasks)} tests...")
    batch = await asyncio.gather(*tasks)
    ok = sum(1 for r in batch if r.success)
    print(f"  P5_CONSENSUS: {ok}/{len(batch)} OK")
    results.extend(batch)

    # P6 COMMANDER: pipeline
    tasks = []
    for task in nano_tasks:
        tasks.append(run_single_test(client, "P6_COMMANDER", "M1/qwen3-8b", task, sem))
    print(f"  P6_COMMANDER: {len(tasks)} tests...")
    batch = await asyncio.gather(*tasks)
    ok = sum(1 for r in batch if r.success)
    print(f"  P6_COMMANDER: {ok}/{len(batch)} OK")
    results.extend(batch)

    return results


async def phase2_micro_burst(client: httpx.AsyncClient) -> list[BenchResult]:
    """Phase 2: Burst 50 nano+micro tasks on best P1 nodes."""
    print("\n" + "=" * 70)
    print("PHASE 2 — MICRO BURST (50 taches nano+micro, parallele)")
    print("=" * 70)
    sem = asyncio.Semaphore(PARALLEL_LIMIT)
    tasks_to_run = [t for t in ALL_TASKS if t["size"] in ("nano", "micro")]
    fast_nodes = ["M1/qwen3-8b", "OL1/qwen3-1.7b"]

    bench_tasks = []
    for task in tasks_to_run:
        node = fast_nodes[hash(task["id"]) % len(fast_nodes)]
        bench_tasks.append(run_single_test(client, "P1_DIRECT", node, task, sem))

    print(f"  Lancement de {len(bench_tasks)} taches en parallele (sem={PARALLEL_LIMIT})...")
    results = await asyncio.gather(*bench_tasks)
    ok = sum(1 for r in results if r.success)
    avg_lat = statistics.mean(r.latency_ms for r in results if r.success) if ok else 0
    print(f"  Resultat: {ok}/{len(results)} OK | Latence moyenne: {avg_lat:.0f}ms")
    return results


async def phase3_escalade(client: httpx.AsyncClient) -> list[BenchResult]:
    """Phase 3: Escalating task sizes — all paths x all sizes."""
    print("\n" + "=" * 70)
    print("PHASE 3 — ESCALADE (tailles croissantes, multi-chemins)")
    print("=" * 70)
    sem = asyncio.Semaphore(PARALLEL_LIMIT)
    results = []

    # For each size, test 2 best paths (P1 direct + P6 commander)
    for size in ["nano", "micro", "small", "medium", "large", "xl"]:
        size_tasks = [t for t in ALL_TASKS if t["size"] == size]
        bench_tasks = []

        for task in size_tasks[:5]:  # 5 tasks per size
            # P1 on M1 (fast local)
            bench_tasks.append(run_single_test(client, "P1_DIRECT", "M1/qwen3-8b", task, sem))
            # P1 on OL1-14b (was gpt-oss cloud, DELETED: model removed from Ollama)
            bench_tasks.append(run_single_test(client, "P1_DIRECT", "OL1/qwen3-14b", task, sem))
            # P5 consensus
            bench_tasks.append(run_single_test(client, "P5_CONSENSUS", "M1/qwen3-8b", task, sem))
            # P6 commander
            bench_tasks.append(run_single_test(client, "P6_COMMANDER", "M1/qwen3-8b", task, sem))

        print(f"  [{size.upper():6s}] {len(bench_tasks)} tests...", end=" ", flush=True)
        batch = await asyncio.gather(*bench_tasks)
        ok = sum(1 for r in batch if r.success)
        avg_q = statistics.mean(r.quality_score for r in batch if r.success) if ok else 0
        print(f"{ok}/{len(batch)} OK | Qualite moy: {avg_q:.2f}")
        results.extend(batch)

    return results


async def phase4_stress(client: httpx.AsyncClient) -> list[BenchResult]:
    """Phase 4: Stress test — high parallelism on each path."""
    print("\n" + "=" * 70)
    print("PHASE 4 — STRESS (parallelisme max par chemin)")
    print("=" * 70)
    results = []

    # Stress P1 with 10 parallel requests
    sem10 = asyncio.Semaphore(10)
    micro_tasks = [t for t in ALL_TASKS if t["size"] == "micro"]
    bench_tasks = []
    for task in micro_tasks:
        bench_tasks.append(run_single_test(client, "P1_DIRECT", "M1/qwen3-8b", task, sem10))
    print(f"  P1_DIRECT stress x{len(bench_tasks)} (sem=10)...", end=" ", flush=True)
    batch = await asyncio.gather(*bench_tasks)
    ok = sum(1 for r in batch if r.success)
    throughput = sum(r.tok_per_sec for r in batch if r.success)
    print(f"{ok}/{len(batch)} OK | Throughput total: {throughput:.0f} tok/s")
    results.extend(batch)

    # Stress P5 consensus with 5 parallel
    sem5 = asyncio.Semaphore(5)
    bench_tasks = []
    for task in micro_tasks[:5]:
        bench_tasks.append(run_single_test(client, "P5_CONSENSUS", "M1/qwen3-8b", task, sem5))
    print(f"  P5_CONSENSUS stress x{len(bench_tasks)} (sem=5)...", end=" ", flush=True)
    batch = await asyncio.gather(*bench_tasks)
    ok = sum(1 for r in batch if r.success)
    print(f"{ok}/{len(batch)} OK")
    results.extend(batch)

    # Stress P6 commander with 5 parallel
    bench_tasks = []
    for task in micro_tasks[:5]:
        bench_tasks.append(run_single_test(client, "P6_COMMANDER", "M1/qwen3-8b", task, sem5))
    print(f"  P6_COMMANDER stress x{len(bench_tasks)} (sem=5)...", end=" ", flush=True)
    batch = await asyncio.gather(*bench_tasks)
    ok = sum(1 for r in batch if r.success)
    print(f"{ok}/{len(batch)} OK")
    results.extend(batch)

    return results


# ══════════════════════════════════════════════════════════════════════════
# ANALYSIS & AGENT FACTORY
# ══════════════════════════════════════════════════════════════════════════

def analyze_results(all_results: list[BenchResult]) -> dict:
    """Analyze benchmark results and find optimal patterns."""
    analysis = {
        "total_tests": len(all_results),
        "total_success": sum(1 for r in all_results if r.success),
        "by_path": {},
        "by_node": {},
        "by_size": {},
        "by_category": {},
        "optimal_patterns": [],
    }

    # Group by path
    for r in all_results:
        if r.success:
            key = r.path_id
            if key not in analysis["by_path"]:
                analysis["by_path"][key] = {"ok": 0, "total": 0, "latencies": [], "qualities": [], "tok_rates": []}
            analysis["by_path"][key]["ok"] += 1
            analysis["by_path"][key]["latencies"].append(r.latency_ms)
            analysis["by_path"][key]["qualities"].append(r.quality_score)
            analysis["by_path"][key]["tok_rates"].append(r.tok_per_sec)
        for key_field, key_val in [("by_path", r.path_id), ("by_node", r.node_id), ("by_size", r.task_size), ("by_category", r.task_cat)]:
            bucket = analysis[key_field]
            if key_val not in bucket:
                bucket[key_val] = {"ok": 0, "total": 0, "latencies": [], "qualities": [], "tok_rates": []}
            bucket[key_val]["total"] += 1
            if r.success:
                bucket[key_val]["ok"] += 1
                bucket[key_val]["latencies"].append(r.latency_ms)
                bucket[key_val]["qualities"].append(r.quality_score)
                bucket[key_val]["tok_rates"].append(r.tok_per_sec)

    # Compute stats
    for group in [analysis["by_path"], analysis["by_node"], analysis["by_size"], analysis["by_category"]]:
        for key, stats in group.items():
            stats["success_rate"] = stats["ok"] / stats["total"] if stats["total"] else 0
            stats["avg_latency_ms"] = round(statistics.mean(stats["latencies"]), 1) if stats["latencies"] else 0
            stats["avg_quality"] = round(statistics.mean(stats["qualities"]), 3) if stats["qualities"] else 0
            stats["avg_tok_s"] = round(statistics.mean(stats["tok_rates"]), 1) if stats["tok_rates"] else 0
            stats["p95_latency_ms"] = round(sorted(stats["latencies"])[int(len(stats["latencies"]) * 0.95)] if stats["latencies"] else 0, 1)
            # Remove raw lists for JSON serialization
            del stats["latencies"]
            del stats["qualities"]
            del stats["tok_rates"]

    # Find optimal pattern per (category x priority: speed vs quality)
    cat_path_combos = {}
    for r in all_results:
        if not r.success:
            continue
        key = (r.task_cat, r.path_id, r.node_id)
        if key not in cat_path_combos:
            cat_path_combos[key] = {"latencies": [], "qualities": [], "count": 0}
        cat_path_combos[key]["latencies"].append(r.latency_ms)
        cat_path_combos[key]["qualities"].append(r.quality_score)
        cat_path_combos[key]["count"] += 1

    # For each category, find: fastest combo + highest quality combo
    categories = set(r.task_cat for r in all_results)
    for cat in categories:
        combos = {k: v for k, v in cat_path_combos.items() if k[0] == cat and v["count"] >= 2}
        if not combos:
            continue

        # Speed champion
        speed_best = min(combos.items(), key=lambda x: statistics.mean(x[1]["latencies"]))
        analysis["optimal_patterns"].append({
            "category": cat,
            "priority": "speed",
            "path": speed_best[0][1],
            "node": speed_best[0][2],
            "avg_latency_ms": round(statistics.mean(speed_best[1]["latencies"]), 1),
            "avg_quality": round(statistics.mean(speed_best[1]["qualities"]), 3),
            "samples": speed_best[1]["count"],
        })

        # Quality champion
        quality_best = max(combos.items(), key=lambda x: statistics.mean(x[1]["qualities"]))
        if quality_best[0] != speed_best[0]:  # avoid duplicates
            analysis["optimal_patterns"].append({
                "category": cat,
                "priority": "quality",
                "path": quality_best[0][1],
                "node": quality_best[0][2],
                "avg_latency_ms": round(statistics.mean(quality_best[1]["latencies"]), 1),
                "avg_quality": round(statistics.mean(quality_best[1]["qualities"]), 3),
                "samples": quality_best[1]["count"],
            })

    return analysis


def generate_agents(analysis: dict) -> list[str]:
    """Generate agent .md files from optimal patterns."""
    agents_created = []
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    # Agent color palette
    colors = ["cyan", "green", "blue", "yellow", "magenta", "red", "purple", "orange"]
    color_idx = 0

    for pattern in analysis.get("optimal_patterns", []):
        cat = pattern["category"]
        prio = pattern["priority"]
        path = pattern["path"]
        node = pattern["node"]
        lat = pattern["avg_latency_ms"]
        qual = pattern["avg_quality"]

        agent_name = f"path-{cat}-{prio}"
        filename = f"{agent_name}.md"
        filepath = AGENTS_DIR / filename
        color = colors[color_idx % len(colors)]
        color_idx += 1

        # Build routing instruction based on path
        if path == "P1_DIRECT":
            routing = f"Route DIRECTEMENT vers {node} via HTTP (curl/httpx). Pas de proxy, pas de middleware."
        elif path == "P3_PROXY":
            routing = f"Route via Canvas proxy (127.0.0.1:18800/chat) avec query enhancement. Modele: {node}."
        elif path == "P5_CONSENSUS":
            routing = f"Lance un consensus mesh: {node} + 2 autres noeuds en parallele. Vote pondere pour la meilleure reponse."
        elif path == "P6_COMMANDER":
            routing = f"Utilise le pipeline Commander: classify -> decompose -> dispatch adaptatif -> verify. Noeud principal: {node}."
        elif path == "P4_EXTERNAL":
            routing = f"Route via proxy externe ({node}). Usage pour taches necessitant reasoning cloud profond."
        else:
            routing = f"Route vers {node} via {path}."

        content = f"""---
name: {agent_name}
description: "Agent optimise pour les taches '{cat}' avec priorite {prio}. Benchmark: {lat:.0f}ms avg, qualite {qual:.2f}. Chemin: {path} -> {node}"
color: {color}
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - WebFetch
---

# Agent {agent_name.replace('-', ' ').title()}

Tu es un agent specialise pour les taches de type **{cat}** avec priorite **{prio}**.

## Routing

{routing}

## Benchmark

- Latence moyenne: {lat:.0f}ms
- Score qualite: {qual:.2f}/1.0
- Chemin optimal: {path}
- Noeud cible: {node}
- Decouvert par: multi_path_benchmark.py ({datetime.now().strftime('%Y-%m-%d')})

## Instructions

1. Analyse la requete utilisateur
2. {routing}
3. Verifie la qualite de la reponse (coherence, completude)
4. Retourne la reponse avec attribution [{node}]
"""
        filepath.write_text(content, encoding="utf-8")
        agents_created.append(agent_name)
        print(f"  Agent cree: {filename} ({cat}/{prio} -> {path} {node})")

    return agents_created


# ══════════════════════════════════════════════════════════════════════════
# DATABASE PERSISTENCE
# ══════════════════════════════════════════════════════════════════════════

def save_to_db(results: list[BenchResult]):
    """Save results to etoile.db."""
    db = sqlite3.connect(str(ETOILE_DB))
    db.execute("""CREATE TABLE IF NOT EXISTS multi_path_benchmark (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT, task_size TEXT, task_cat TEXT, prompt TEXT,
        path_id TEXT, node_id TEXT,
        latency_ms REAL, tokens_out INTEGER, tok_per_sec REAL,
        success INTEGER, quality_score REAL,
        output_preview TEXT, error TEXT, timestamp TEXT,
        run_id TEXT
    )""")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    for r in results:
        db.execute(
            "INSERT INTO multi_path_benchmark (task_id, task_size, task_cat, prompt, path_id, node_id, latency_ms, tokens_out, tok_per_sec, success, quality_score, output_preview, error, timestamp, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r.task_id, r.task_size, r.task_cat, r.prompt, r.path_id, r.node_id,
             r.latency_ms, r.tokens_out, r.tok_per_sec, int(r.success), r.quality_score,
             r.output_preview, r.error, r.timestamp, run_id),
        )
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM multi_path_benchmark WHERE run_id=?", (run_id,)).fetchone()[0]
    db.close()
    print(f"\n  Sauvegarde DB: {count} lignes dans etoile.db (multi_path_benchmark, run={run_id})")
    return run_id


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

async def main():
    print("=" * 70)
    print(f"  JARVIS Multi-Path Dispatch Benchmark v1.0")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Noeuds: {len(NODES)} | Chemins: {len(PATHS)} | Taches: {len(ALL_TASKS)}")
    print("=" * 70)

    factory_only = "--factory-only" in sys.argv
    phase_only = None
    for arg in sys.argv:
        if arg.startswith("--phase"):
            try:
                phase_only = int(sys.argv[sys.argv.index(arg) + 1])
            except (ValueError, IndexError):
                pass

    all_results: list[BenchResult] = []
    t_start = time.perf_counter()

    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=40),
    ) as client:

        if factory_only:
            # Load latest results from JSON
            json_files = sorted(DATA_DIR.glob("multi_path_benchmark_*.json"), reverse=True)
            if json_files:
                data = json.loads(json_files[0].read_text(encoding="utf-8"))
                print(f"\n  Chargement: {json_files[0].name} ({len(data.get('results', []))} resultats)")
                # Reconstruct BenchResult objects
                for r in data.get("results", []):
                    all_results.append(BenchResult(**{k: r[k] for k in BenchResult.__dataclass_fields__ if k in r}))
            else:
                print("  ERREUR: Aucun fichier benchmark trouve. Lancez d'abord le benchmark complet.")
                return
        else:
            # Run phases
            phases = {
                1: ("CARTOGRAPHIE", phase1_cartography),
                2: ("MICRO BURST", phase2_micro_burst),
                3: ("ESCALADE", phase3_escalade),
                4: ("STRESS", phase4_stress),
            }

            for num, (name, fn) in phases.items():
                if phase_only and num != phase_only:
                    continue
                try:
                    results = await fn(client)
                    all_results.extend(results)
                except Exception as e:
                    print(f"\n  ERREUR Phase {num} ({name}): {e}")

    total_time = (time.perf_counter() - t_start)

    # ── Analysis ──
    print("\n" + "=" * 70)
    print("PHASE 5 — ANALYSE & AGENT FACTORY")
    print("=" * 70)

    analysis = analyze_results(all_results)
    analysis["total_time_s"] = round(total_time, 1)
    analysis["timestamp"] = datetime.now().isoformat()
    analysis["run_args"] = sys.argv[1:]

    # Print summary
    print(f"\n  Total: {analysis['total_success']}/{analysis['total_tests']} OK ({total_time:.1f}s)")
    print(f"\n  Par chemin:")
    for path, stats in sorted(analysis["by_path"].items()):
        print(f"    {path:15s} | {stats['ok']:3d}/{stats['total']:3d} | lat={stats['avg_latency_ms']:7.0f}ms | qual={stats['avg_quality']:.3f} | {stats['avg_tok_s']:.0f} tok/s")
    print(f"\n  Par noeud:")
    for node, stats in sorted(analysis["by_node"].items()):
        print(f"    {node:20s} | {stats['ok']:3d}/{stats['total']:3d} | lat={stats['avg_latency_ms']:7.0f}ms | qual={stats['avg_quality']:.3f} | {stats['avg_tok_s']:.0f} tok/s")
    print(f"\n  Par taille:")
    for size in ["nano", "micro", "small", "medium", "large", "xl"]:
        stats = analysis["by_size"].get(size, {})
        if stats:
            print(f"    {size:8s} | {stats.get('ok',0):3d}/{stats.get('total',0):3d} | lat={stats.get('avg_latency_ms',0):7.0f}ms | qual={stats.get('avg_quality',0):.3f}")
    print(f"\n  Patterns optimaux decouverts: {len(analysis['optimal_patterns'])}")
    for p in analysis["optimal_patterns"]:
        print(f"    {p['category']:10s} [{p['priority']:7s}] -> {p['path']} @ {p['node']} ({p['avg_latency_ms']:.0f}ms, q={p['avg_quality']:.3f})")

    # ── Generate agents ──
    print(f"\n  Generation des agents...")
    agents = generate_agents(analysis)
    analysis["agents_created"] = agents
    print(f"  {len(agents)} agents generes dans {AGENTS_DIR}")

    # ── Save JSON ──
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = DATA_DIR / f"multi_path_benchmark_{ts}.json"
    report = {
        "analysis": analysis,
        "results": [asdict(r) for r in all_results],
    }
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Rapport JSON: {json_path.name}")

    # ── Save to DB ──
    if not factory_only:
        save_to_db(all_results)

    print("\n" + "=" * 70)
    print(f"  BENCHMARK TERMINE — {analysis['total_success']}/{analysis['total_tests']} OK")
    print(f"  {len(agents)} agents crees | {total_time:.1f}s total")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
