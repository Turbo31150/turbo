"""JARVIS MEGA Learning Engine v2 — Multi-agent architecture.

Architecture:
- Workers paralleles: un par type de noeud (M1, M2, M3, OL1, OC)
- Chaque worker ecrit ses resultats directement en DB
- Aggregateur periodique calcule les EMA + routing
- DB bien indexee pour des milliers d'entrees
- Sauvegarde incrementale au fur et a mesure
"""

import asyncio
import json
import os
import re
import sqlite3
import sys
import time
import traceback
import threading
from collections import defaultdict
from pathlib import Path

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT", "")

DB_PATH = Path("F:/BUREAU/turbo/data/mega_learning.db")
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")
STATE_FILE = Path("F:/BUREAU/turbo/data/mega_learnings.json")

# ══════════════════════════════════════════════════════════════
# PROMPTS — 54 diversifies par categorie
# ══════════════════════════════════════════════════════════════
PROMPTS = [
    "Ecris une fonction Python quicksort optimisee",
    "Corrige: KeyError dans un dict nested",
    "Cree un decorator retry avec backoff exponentiel",
    "Refactorise avec le pattern Strategy",
    "Test pytest pour une API FastAPI",
    "Ecris un parser JSON minimal en Python",
    "Cree une classe Python LinkedList",
    "Script bash monitor disk usage alerte 90%",
    "Rate limiter token bucket implementation",
    "Cree un context manager pour mesurer le temps",
    "Escargot 3m jour 2m nuit mur 10m combien de jours",
    "Prouve racine(2) irrationnel",
    "Si A implique B et B implique C alors A implique C ?",
    "Monte Carlo Tree Search pour jeux",
    "Backpropagation expliquee simplement",
    "Si tous les A sont B et certains B sont C, peut-on conclure que certains A sont C ?",
    "Analyse technique BTC RSI 65 MACD convergent",
    "Compare DCA vs lump sum ETH 2025",
    "Trading RSI MACD PEPE momentum",
    "Tendances crypto mars 2026",
    "Architecture event-driven notifications",
    "Architecture hexagonale vs clean architecture",
    "Kubernetes vs Docker Swarm pour 50 pods",
    "gRPC vs REST pour microservices internes",
    "Singleton vs dependency injection avantages",
    "SOLID principes avec exemples Python",
    "PostgreSQL vs SQLite 10M rows 50 req/s",
    "Compare Redis vs Memcached",
    "Optimise SELECT * FROM logs WHERE ts > now()-1h",
    "B-tree vs LSM-tree pour une DB",
    "Pattern circuit breaker exemple concret",
    "Consensus Raft distribue explication",
    "GPU offloading comment ca marche",
    "Zero-copy networking explication",
    "Lock-free queue en C++ principe",
    "Bloom filter probabiliste explication",
    "Nom de projet dashboard IA temps reel",
    "Slogan JARVIS 5 mots",
    "Ecris un haiku sur le machine learning",
    "Difference WebSocket vs SSE vs long polling",
    "Explique les goroutines Go vs async Python",
    "Compare transformer vs RNN pour du NLP",
    "CRDT types et cas d'usage",
    "MapReduce vs Spark streaming differences",
    "Nouveautes Python 3.13",
    "FastAPI 422 debug schema Pydantic",
    "asyncio.CancelledError producer-consumer",
    "Corrige: IndexError dans une boucle while sur une liste vide",
    "Integrale x*ln(x) dx",
    "Probabilite 3 as sur 5 cartes tirees de 52",
    "1337 * 42 =",
    "Pi 10 decimales",
    "Capitale du Japon",
    "Combien font 847 x 293 ?",
]

CATEGORIES = {
    "code": re.compile(r"(fonction|class|decorator|refactor|test|pytest|endpoint|parser|script|ecris|cree|implem|linked|rate.limiter|token.bucket|context.manager)", re.I),
    "math": re.compile(r"(integrale|probabilite|calcul|equation|combien|racine|\d+\s*[\*\+\-\/x]\s*\d+|pi\s|monte carlo)", re.I),
    "reasoning": re.compile(r"(prouve|implique|logique|escargot|paradox|si.*alors|pourquoi|conclure|backpropag)", re.I),
    "trading": re.compile(r"(btc|eth|sol|trading|rsi|macd|dca|crypto|momentum|tendance)", re.I),
    "architecture": re.compile(r"(architecture|microservice|pattern|design|hexagonal|kubernetes|grpc|event.driven|singleton|solid|dependency)", re.I),
    "database": re.compile(r"(sql|postgres|sqlite|redis|memcache|b.tree|lsm|query|select|10M)", re.I),
    "system": re.compile(r"(circuit.breaker|consensus|raft|gpu|lock.free|zero.copy|websocket|sse|bloom.filter)", re.I),
    "creative": re.compile(r"(haiku|slogan|nom de projet|genere)", re.I),
    "knowledge": re.compile(r"(explique|difference|compare|comment|capitale|nouveaute|transformer|rnn|crdt|mapreduce|goroutine)", re.I),
    "debug": re.compile(r"(debug|erreur|error|timeout|cancel|bug|422|corrige|indexerror)", re.I),
}


def classify(prompt):
    for cat, regex in CATEGORIES.items():
        if regex.search(prompt):
            return cat
    return "general"


# ══════════════════════════════════════════════════════════════
# DB — Schema bien indexe pour des milliers d'entrees
# ══════════════════════════════════════════════════════════════

def init_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA synchronous=NORMAL")

    # Table principale: chaque requete individuelle
    conn.execute("""CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node TEXT NOT NULL,
        model TEXT,
        category TEXT NOT NULL,
        prompt_idx INT,
        ok INT NOT NULL,
        ms INT NOT NULL,
        response_len INT DEFAULT 0,
        agent TEXT,
        ts REAL NOT NULL
    )""")

    # Agregation incrementale par noeud
    conn.execute("""CREATE TABLE IF NOT EXISTS node_stats (
        node TEXT PRIMARY KEY,
        total_ok INT DEFAULT 0,
        total_fail INT DEFAULT 0,
        total_ms INT DEFAULT 0,
        avg_ms REAL DEFAULT 0,
        avg_len REAL DEFAULT 0,
        sr REAL DEFAULT 0,
        ema_score REAL DEFAULT 0.5,
        last_ok_ts REAL DEFAULT 0,
        last_fail_ts REAL DEFAULT 0,
        circuit_open INT DEFAULT 0,
        circuit_until REAL DEFAULT 0,
        updated_ts REAL
    )""")

    # Routing par categorie → meilleur noeud
    conn.execute("""CREATE TABLE IF NOT EXISTS category_routing (
        category TEXT PRIMARY KEY,
        best_node TEXT,
        score REAL,
        avg_ms INT,
        avg_len INT,
        alternatives TEXT,
        updated_ts REAL
    )""")

    # Log d'activite des agents workers
    conn.execute("""CREATE TABLE IF NOT EXISTS agent_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT NOT NULL,
        event TEXT NOT NULL,
        detail TEXT,
        ts REAL NOT NULL
    )""")

    # Index pour requetes rapides
    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_node ON results(node)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_cat ON results(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_ts ON results(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_ok ON results(ok)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_node_cat ON results(node, category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_log_ts ON agent_log(ts)")

    conn.commit()
    return conn


def get_db():
    """Thread-safe DB connection."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


# ══════════════════════════════════════════════════════════════
# RESULT WRITER — Thread-safe, batch writes
# ══════════════════════════════════════════════════════════════

class ResultWriter:
    """Collect results from async workers, batch-write to DB."""
    def __init__(self):
        self.lock = asyncio.Lock()
        self.buffer = []
        self.total_ok = 0
        self.total_fail = 0
        self.total_ms = 0
        self.conn = get_db()

    def close(self):
        self._flush_sync()
        self.conn.close()

    async def add(self, node, model, category, prompt_idx, ok, ms, response_len, agent_name):
        async with self.lock:
            self.buffer.append((node, model, category, prompt_idx, int(ok), ms, response_len, agent_name, time.time()))
            if ok:
                self.total_ok += 1
                self.total_ms += ms
            else:
                self.total_fail += 1
            # Flush every 10 results
            if len(self.buffer) >= 10:
                self._flush_sync()

    def _flush_sync(self):
        if not self.buffer:
            return
        try:
            self.conn.executemany(
                "INSERT INTO results (node, model, category, prompt_idx, ok, ms, response_len, agent, ts) VALUES (?,?,?,?,?,?,?,?,?)",
                self.buffer
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # DB locked, retry next flush
        self.buffer.clear()

    async def flush(self):
        async with self.lock:
            self._flush_sync()

    @property
    def total(self):
        return self.total_ok + self.total_fail

    @property
    def sr(self):
        t = self.total
        return self.total_ok * 100 // t if t > 0 else 0


# ══════════════════════════════════════════════════════════════
# AGGREGATEUR — Calcule EMA + routing table
# ══════════════════════════════════════════════════════════════

EMA_ALPHA = 0.12

def aggregate(conn):
    """Aggregate results into node_stats + category_routing. Run periodically."""
    # 1. Update node_stats from results
    rows = conn.execute("""
        SELECT node,
               SUM(CASE WHEN ok=1 THEN 1 ELSE 0 END) as ok_count,
               SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END) as fail_count,
               AVG(CASE WHEN ok=1 THEN ms END) as avg_ms,
               AVG(CASE WHEN ok=1 THEN response_len END) as avg_len,
               MAX(CASE WHEN ok=1 THEN ts END) as last_ok,
               MAX(CASE WHEN ok=0 THEN ts END) as last_fail
        FROM results
        GROUP BY node
        HAVING (ok_count + fail_count) > 0
    """).fetchall()

    for node, ok_count, fail_count, avg_ms, avg_len, last_ok, last_fail in rows:
        total = ok_count + fail_count
        sr = ok_count / total if total > 0 else 0
        avg_ms = avg_ms or 0
        avg_len = avg_len or 0
        speed_score = max(0, 1 - avg_ms / 15000)
        quality_score = min(1, avg_len / 300)
        ema_score = sr * 0.4 + speed_score * 0.3 + quality_score * 0.3

        conn.execute("""INSERT OR REPLACE INTO node_stats
            (node, total_ok, total_fail, avg_ms, avg_len, sr, ema_score, last_ok_ts, last_fail_ts, updated_ts)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (node, ok_count, fail_count, avg_ms, avg_len, sr, ema_score, last_ok or 0, last_fail or 0, time.time()))

    # 2. Update category_routing — best node per category
    cat_rows = conn.execute("""
        SELECT category, node,
               SUM(CASE WHEN ok=1 THEN 1 ELSE 0 END) as ok_count,
               COUNT(*) as total,
               AVG(CASE WHEN ok=1 THEN ms END) as avg_ms,
               AVG(CASE WHEN ok=1 THEN response_len END) as avg_len
        FROM results
        GROUP BY category, node
        HAVING total >= 2
    """).fetchall()

    cat_scores = defaultdict(list)
    for cat, node, ok_count, total, avg_ms, avg_len in cat_rows:
        sr = ok_count / total if total > 0 else 0
        avg_ms = avg_ms or 0
        avg_len = avg_len or 0
        speed = max(0, 1 - avg_ms / 15000)
        quality = min(1, avg_len / 300)
        score = sr * 0.4 + speed * 0.3 + quality * 0.3
        cat_scores[cat].append((node, score, int(avg_ms), int(avg_len)))

    for cat, nodes in cat_scores.items():
        nodes.sort(key=lambda x: x[1], reverse=True)
        best = nodes[0]
        alts = json.dumps([(n, round(s, 3)) for n, s, _, _ in nodes[1:4] if s > 0.1])
        conn.execute("""INSERT OR REPLACE INTO category_routing
            (category, best_node, score, avg_ms, avg_len, alternatives, updated_ts)
            VALUES (?,?,?,?,?,?,?)""",
            (cat, best[0], round(best[1], 3), best[2], best[3], alts, time.time()))

    conn.commit()
    return len(rows), len(cat_scores)


def inject_etoile(conn):
    """Inject routing into etoile.db for JARVIS production."""
    try:
        econn = sqlite3.connect(str(ETOILE_DB), timeout=5)
        econn.execute("""CREATE TABLE IF NOT EXISTS deep_learnings (
            id INTEGER PRIMARY KEY, category TEXT, complexity TEXT,
            best_node TEXT, score REAL, ema_latency REAL, ema_quality REAL,
            samples INT, learning_cycle INT, ts REAL
        )""")
        econn.execute("DELETE FROM deep_learnings")
        rows = conn.execute("SELECT category, best_node, score, avg_ms, avg_len FROM category_routing").fetchall()
        total = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
        for cat, node, score, avg_ms, avg_len in rows:
            econn.execute("INSERT INTO deep_learnings VALUES (NULL,?,?,?,?,?,?,?,?,?)",
                (cat, "all", node, score, avg_ms, avg_len, total, 0, time.time()))
        econn.commit()
        econn.close()
        return len(rows)
    except Exception as e:
        return 0


def cleanup_old_results(conn, keep_hours=24):
    """Delete results older than keep_hours. Keep node_stats and routing."""
    cutoff = time.time() - (keep_hours * 3600)
    deleted = conn.execute("DELETE FROM results WHERE ts < ?", (cutoff,)).rowcount
    if deleted > 0:
        conn.execute("VACUUM")
        conn.commit()
    return deleted


# ══════════════════════════════════════════════════════════════
# WORKER AGENTS — Un par type de noeud
# ══════════════════════════════════════════════════════════════

def strip_think(text):
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    text = re.sub(r"<think>[\s\S]*$", "", text).strip()
    return text


class WorkerAgent:
    """Base worker agent — sends prompts to a node and records results."""
    def __init__(self, name, writer):
        self.name = name
        self.writer = writer
        self.consecutive_fails = 0
        self.circuit_until = 0
        self.total_ok = 0
        self.total_fail = 0

    def is_open(self):
        if time.time() > self.circuit_until:
            return False
        return True

    def on_fail(self):
        self.consecutive_fails += 1
        self.total_fail += 1
        if self.consecutive_fails >= 2:
            timeout = 30 if self.total_fail < 10 else 120 if self.total_fail < 30 else 300
            self.circuit_until = time.time() + timeout

    def on_success(self):
        self.consecutive_fails = 0
        self.total_ok += 1

    async def call(self, client, prompt, prompt_idx, cat):
        raise NotImplementedError


class M1Worker(WorkerAgent):
    """M1 local LM Studio — qwen3-8b"""
    def __init__(self, writer):
        super().__init__("M1/qwen3-8b", writer)
        self.url = "http://127.0.0.1:1234/v1/chat/completions"

    async def call(self, client, prompt, prompt_idx, cat):
        if self.is_open(): return
        t0 = time.time()
        try:
            body = {"model": "qwen3-8b", "messages": [
                {"role": "system", "content": "Tu es JARVIS. Reponds en francais, concis."},
                {"role": "user", "content": f"/nothink\n{prompt}"}
            ], "max_tokens": 128, "temperature": 0.3, "stream": False}
            resp = await client.post(self.url, json=body, timeout=20)
            ms = int((time.time() - t0) * 1000)
            if resp.status_code != 200:
                self.on_fail()
                await self.writer.add(self.name, "qwen3-8b", cat, prompt_idx, False, ms, 0, self.name)
                return
            raw = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            text = strip_think(raw)
            rlen = len(text) if text else len(raw)
            ok = rlen > 0
            if ok: self.on_success()
            else: self.on_fail()
            await self.writer.add(self.name, "qwen3-8b", cat, prompt_idx, ok, ms, rlen, self.name)
        except Exception:
            ms = int((time.time() - t0) * 1000)
            self.on_fail()
            await self.writer.add(self.name, "qwen3-8b", cat, prompt_idx, False, ms, 0, self.name)


class LMStudioWorker(WorkerAgent):
    """Remote LM Studio (M2/M3) — deepseek-r1"""
    def __init__(self, name, url, writer):
        super().__init__(name, writer)
        self.url = url
        self.model = "deepseek-r1-0528-qwen3-8b"

    async def call(self, client, prompt, prompt_idx, cat):
        if self.is_open(): return
        t0 = time.time()
        try:
            body = {"model": self.model, "messages": [
                {"role": "system", "content": "Tu es JARVIS. Reponds en francais."},
                {"role": "user", "content": prompt}
            ], "max_tokens": 128, "temperature": 0.3, "stream": False}
            resp = await client.post(self.url, json=body, timeout=25)
            ms = int((time.time() - t0) * 1000)
            if resp.status_code != 200:
                self.on_fail()
                await self.writer.add(self.name, self.model, cat, prompt_idx, False, ms, 0, self.name)
                return
            raw = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            text = strip_think(raw)
            rlen = len(text) if text else len(raw)
            ok = rlen > 0
            if ok: self.on_success()
            else: self.on_fail()
            await self.writer.add(self.name, self.model, cat, prompt_idx, ok, ms, rlen, self.name)
        except Exception:
            ms = int((time.time() - t0) * 1000)
            self.on_fail()
            await self.writer.add(self.name, self.model, cat, prompt_idx, False, ms, 0, self.name)


class OllamaWorker(WorkerAgent):
    """OL1 local Ollama — qwen3:1.7b"""
    def __init__(self, writer):
        super().__init__("OL1/qwen3:1.7b", writer)

    async def call(self, client, prompt, prompt_idx, cat):
        if self.is_open(): return
        t0 = time.time()
        try:
            body = {"model": "qwen3:1.7b", "messages": [
                {"role": "user", "content": f"/no_think\n{prompt}"}
            ], "stream": False, "think": False, "options": {"num_predict": 128}}
            resp = await client.post("http://127.0.0.1:11434/api/chat", json=body, timeout=15)
            ms = int((time.time() - t0) * 1000)
            if resp.status_code != 200:
                self.on_fail()
                await self.writer.add(self.name, "qwen3:1.7b", cat, prompt_idx, False, ms, 0, self.name)
                return
            raw = resp.json().get("message", {}).get("content", "")
            text = strip_think(raw)
            rlen = len(text) if text else len(raw)
            ok = rlen > 0
            if ok: self.on_success()
            else: self.on_fail()
            await self.writer.add(self.name, "qwen3:1.7b", cat, prompt_idx, ok, ms, rlen, self.name)
        except Exception:
            ms = int((time.time() - t0) * 1000)
            self.on_fail()
            await self.writer.add(self.name, "qwen3:1.7b", cat, prompt_idx, False, ms, 0, self.name)


class OpenClawWorker(WorkerAgent):
    """OpenClaw dispatch via WS API 9742"""
    OC_AGENTS = {
        "code": ["coding", "code-champion", "m1-deep"],
        "reasoning": ["deep-reasoning", "deep-work", "m1-reason"],
        "trading": ["trading-scanner", "trading", "data-analyst"],
        "debug": ["debug-detective", "coding"],
        "architecture": ["system-ops", "gemini-pro", "analysis-engine"],
        "database": ["coding", "data-analyst"],
        "system": ["system-ops", "devops-ci"],
        "knowledge": ["recherche-synthese", "ol1-web", "doc-writer"],
        "creative": ["creative-brainstorm", "fast-chat"],
        "math": ["deep-reasoning", "m1-reason"],
        "general": ["fast-chat", "quick-dispatch", "main"],
    }

    def __init__(self, writer):
        super().__init__("OC", writer)
        self.agent_idx = 0

    async def call(self, client, prompt, prompt_idx, cat):
        if self.is_open(): return
        agents = self.OC_AGENTS.get(cat, self.OC_AGENTS["general"])
        agent = agents[self.agent_idx % len(agents)]
        self.agent_idx += 1
        node_id = f"OC/{agent}"
        t0 = time.time()
        try:
            resp = await client.post("http://127.0.0.1:9742/api/dispatch_engine/dispatch",
                json={"prompt": prompt, "pattern": agent}, timeout=12)
            ms = int((time.time() - t0) * 1000)
            if resp.status_code != 200:
                self.on_fail()
                await self.writer.add(node_id, agent, cat, prompt_idx, False, ms, 0, self.name)
                return
            data = resp.json()
            ok = data.get("success", False)
            rlen = len(str(data.get("response", ""))) if ok else 0
            if ok and rlen > 5: self.on_success()
            else: self.on_fail(); ok = False
            await self.writer.add(node_id, agent, cat, prompt_idx, ok, ms, rlen, self.name)
        except Exception:
            ms = int((time.time() - t0) * 1000)
            self.on_fail()
            await self.writer.add(node_id, agent, cat, prompt_idx, False, ms, 0, self.name)


class CollabWorker(WorkerAgent):
    """Collab/Cowork multi-agent collaboration."""
    def __init__(self, writer):
        super().__init__("COLLAB/cowork", writer)

    async def call(self, client, prompt, prompt_idx, cat):
        if self.is_open(): return
        t0 = time.time()
        try:
            resp = await client.post("http://127.0.0.1:9742/api/collab/ask",
                json={"prompt": prompt}, timeout=15)
            ms = int((time.time() - t0) * 1000)
            if resp.status_code != 200:
                self.on_fail()
                await self.writer.add(self.name, "cowork", cat, prompt_idx, False, ms, 0, self.name)
                return
            data = resp.json()
            text = str(data.get("response", data.get("result", "")))
            ok = len(text) > 5
            if ok: self.on_success()
            else: self.on_fail()
            await self.writer.add(self.name, "cowork", cat, prompt_idx, ok, ms, len(text), self.name)
        except Exception:
            ms = int((time.time() - t0) * 1000)
            self.on_fail()
            await self.writer.add(self.name, "cowork", cat, prompt_idx, False, ms, 0, self.name)


# ══════════════════════════════════════════════════════════════
# ORCHESTRATEUR — Lance les agents workers en parallele
# ══════════════════════════════════════════════════════════════

async def warmup_node(client, name, call_fn):
    """Warmup a node and return (name, ok, ms)."""
    t0 = time.time()
    try:
        ok = await call_fn(client)
        ms = int((time.time() - t0) * 1000)
        return name, ok, ms
    except Exception:
        ms = int((time.time() - t0) * 1000)
        return name, False, ms


async def run_mega(target=10000):
    """Main orchestrator — runs all workers in parallel."""
    conn = init_db()
    writer = ResultWriter()

    # Resume
    r = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    start_count = r

    # Create all workers
    m1 = M1Worker(writer)
    m2 = LMStudioWorker("M2/deepseek-r1", "http://192.168.1.26:1234/v1/chat/completions", writer)
    m3 = LMStudioWorker("M3/deepseek-r1", "http://192.168.1.113:1234/v1/chat/completions", writer)
    ol1 = OllamaWorker(writer)
    oc = OpenClawWorker(writer)
    collab = CollabWorker(writer)

    all_workers = [m1, m2, m3, ol1, oc, collab]

    print(f"\n{'='*70}")
    print(f"  JARVIS MEGA LEARNING ENGINE v2")
    print(f"  Target: {target} cycles | 6 worker agents | {len(PROMPTS)} prompts")
    print(f"  Workers: M1 M2 M3 OL1 OpenClaw Collab")
    print(f"  Resume from: {start_count} results")
    print(f"{'='*70}\n")
    sys.stdout.flush()

    async with httpx.AsyncClient() as client:
        # ── WARMUP ──
        print("  [WARMUP] Testing all nodes...")
        warmup_results = await asyncio.gather(
            warmup_node(client, "M1", lambda c: _warmup_m1(c)),
            warmup_node(client, "OL1", lambda c: _warmup_ol1(c)),
            warmup_node(client, "M2", lambda c: _warmup_lm(c, "http://192.168.1.26:1234/v1/chat/completions")),
            warmup_node(client, "M3", lambda c: _warmup_lm(c, "http://192.168.1.113:1234/v1/chat/completions")),
            warmup_node(client, "OC", lambda c: _warmup_oc(c)),
            return_exceptions=True,
        )

        alive = []
        dead = []
        for r in warmup_results:
            if isinstance(r, Exception):
                continue
            name, ok, ms = r
            if ok:
                alive.append(f"{name}({ms}ms)")
            else:
                dead.append(name)

        print(f"  [WARMUP] ALIVE: {alive}")
        print(f"  [WARMUP] DEAD:  {dead}")

        # Disable dead workers
        for w in all_workers:
            wname = w.name.split("/")[0]
            if wname in dead:
                w.circuit_until = time.time() + 120
                w.consecutive_fails = 3
                w.total_fail = 5

        # M1 keep-warm
        if "M1" not in dead:
            print("  [WARMUP] Keep-warm M1...")
            await _warmup_m1(client)
        elif "M1" in dead:
            print("  [WARMUP] M1 dead, retry 60s...")
            ok = await _warmup_m1_retry(client)
            if ok:
                m1.circuit_until = 0
                m1.consecutive_fails = 0
                print("  [WARMUP] M1 RECOVERED!")

        # Log warmup
        conn.execute("INSERT INTO agent_log (agent, event, detail, ts) VALUES (?,?,?,?)",
            ("orchestrator", "warmup", json.dumps({"alive": alive, "dead": dead}), time.time()))
        conn.commit()

        # Telegram
        await _send_telegram(client, f"<b>MEGA LEARNING v2 START</b>\n{target} cycles | 6 agents\nAlive: {', '.join(alive)}")

        sys.stdout.flush()
        t0 = time.time()

        # ── MAIN LOOP ──
        for cycle in range(target):
            prompt_idx = cycle % len(PROMPTS)
            prompt = PROMPTS[prompt_idx]
            cat = classify(prompt)

            # Fire all workers in parallel on same prompt
            try:
                tasks = [w.call(client, prompt, prompt_idx, cat) for w in all_workers]
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                print(f"  [CYCLE {cycle}] GATHER ERROR: {e}", flush=True)
                traceback.print_exc(file=sys.stdout)
                continue

            done = cycle + 1

            # Periodic aggregation + reporting
            try:
                if done % 25 == 0:
                    await writer.flush()
                    n_nodes, n_cats = aggregate(conn)
                    n_etoile = inject_etoile(conn)

                    if done % 50 == 0:
                        _print_report(conn, writer, done, target, t0)

                    # Save state
                    _save_state(conn)

                    # Log
                    conn.execute("INSERT INTO agent_log (agent, event, detail, ts) VALUES (?,?,?,?)",
                        ("aggregator", "aggregate", f"nodes={n_nodes} cats={n_cats} etoile={n_etoile}", time.time()))
                    conn.commit()

                elif done % 10 == 0:
                    await writer.flush()
                    elapsed = int(time.time() - t0)
                    cpm = done * 60 / max(elapsed, 1)
                    # Quick status line
                    routing = conn.execute("SELECT category, best_node, score FROM category_routing ORDER BY score DESC LIMIT 3").fetchall()
                    top = ", ".join(f"{c}={n.split('/')[0]}({s:.2f})" for c, n, s in routing)
                    active = sum(1 for w in all_workers if not w.is_open())
                    print(f"  [{done:5d}/{target}] OK={writer.total_ok} F={writer.total_fail} SR={writer.sr}% "
                          f"{elapsed}s {cpm:.1f}c/m agents={active}/6 | {top}")
                    sys.stdout.flush()
            except Exception as e:
                print(f"  [CYCLE {done}] REPORT ERROR: {e}", flush=True)
                traceback.print_exc(file=sys.stdout)

            # Telegram update every 500
            if done % 500 == 0 and done > 0:
                try:
                    routing = conn.execute("SELECT category, best_node, score FROM category_routing ORDER BY score DESC LIMIT 8").fetchall()
                    lines = "\n".join(f"  {c} -> {n} ({s:.2f})" for c, n, s in routing)
                    await _send_telegram(client,
                        f"<b>MEGA [{done}/{target}]</b>\nOK={writer.total_ok} F={writer.total_fail} SR={writer.sr}%\n<pre>{lines}</pre>")
                except Exception:
                    pass

        # ── FINAL ──
        await writer.flush()
        aggregate(conn)
        inject_etoile(conn)
        _save_state(conn)
        elapsed = int(time.time() - t0)

        print(f"\n{'='*70}")
        print(f"  MEGA LEARNING COMPLETE — {target} cycles in {elapsed}s ({elapsed//60}min)")
        print(f"  OK={writer.total_ok} FAIL={writer.total_fail} SR={writer.sr}%")
        _print_report(conn, writer, target, target, t0)

        await _send_telegram(client,
            f"<b>MEGA LEARNING DONE</b>\n{target} cycles in {elapsed//60}min\nSR={writer.sr}%")

    writer.close()
    conn.close()


# ── Helper functions ──

async def _warmup_m1(client):
    try:
        resp = await client.post("http://127.0.0.1:1234/v1/chat/completions",
            json={"model": "qwen3-8b", "messages": [{"role": "user", "content": "/nothink\ntest"}], "max_tokens": 10},
            timeout=45)
        return resp.status_code == 200
    except Exception:
        return False

async def _warmup_m1_retry(client):
    try:
        resp = await client.post("http://127.0.0.1:1234/v1/chat/completions",
            json={"model": "qwen3-8b", "messages": [{"role": "user", "content": "/nothink\ntest"}], "max_tokens": 10},
            timeout=60)
        return resp.status_code == 200
    except Exception:
        return False

async def _warmup_ol1(client):
    try:
        resp = await client.post("http://127.0.0.1:11434/api/chat",
            json={"model": "qwen3:1.7b", "messages": [{"role": "user", "content": "/no_think\ntest"}],
                  "stream": False, "think": False},
            timeout=15)
        return resp.status_code == 200
    except Exception:
        return False

async def _warmup_lm(client, url):
    try:
        resp = await client.post(url,
            json={"model": "deepseek-r1-0528-qwen3-8b", "messages": [{"role": "user", "content": "test"}], "max_tokens": 10},
            timeout=25)
        return resp.status_code == 200
    except Exception:
        return False

async def _warmup_oc(client):
    try:
        resp = await client.post("http://127.0.0.1:9742/api/dispatch_engine/dispatch",
            json={"prompt": "test", "pattern": "fast-chat"}, timeout=12)
        return resp.status_code == 200 and resp.json().get("success", False)
    except Exception:
        return False

async def _send_telegram(client, text):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        await client.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text[:4000], "parse_mode": "HTML"}, timeout=10)
    except Exception:
        pass

def _print_report(conn, writer, done, target, t0):
    elapsed = int(time.time() - t0)
    cpm = done * 60 / max(elapsed, 1)
    print(f"\n{'='*70}")
    print(f"  LEARNING REPORT | {done}/{target} | {elapsed}s ({cpm:.1f} c/m)")
    print(f"  OK={writer.total_ok} FAIL={writer.total_fail} SR={writer.sr}%")
    print(f"{'='*70}")

    # Routing table
    routing = conn.execute("SELECT category, best_node, score, avg_ms, avg_len FROM category_routing ORDER BY score DESC").fetchall()
    if routing:
        print(f"\n  ROUTING ({len(routing)} categories):")
        for cat, node, score, avg_ms, avg_len in routing:
            bar = "#" * int(score * 20)
            print(f"    {cat:14s} -> {node:25s} s={score:.3f} {int(avg_ms):5d}ms {bar}")

    # Top nodes
    nodes = conn.execute("SELECT node, total_ok, total_fail, sr, avg_ms, ema_score FROM node_stats ORDER BY ema_score DESC LIMIT 10").fetchall()
    if nodes:
        print(f"\n  TOP NODES:")
        for node, ok, fail, sr, avg_ms, ema in nodes:
            print(f"    {node:25s} OK={ok:4d} F={fail:3d} SR={sr:.0%} avg={int(avg_ms):5d}ms ema={ema:.3f}")

    sys.stdout.flush()

def _save_state(conn):
    """Save routing table to JSON for other JARVIS components."""
    routing = conn.execute("SELECT category, best_node, score, avg_ms, avg_len, alternatives FROM category_routing").fetchall()
    data = {
        "routing": {cat: {"node": node, "score": score, "avg_ms": avg_ms, "avg_len": avg_len,
                          "alternatives": json.loads(alts) if alts else []}
                    for cat, node, score, avg_ms, avg_len, alts in routing},
        "total_results": conn.execute("SELECT COUNT(*) FROM results").fetchone()[0],
        "timestamp": time.time(),
    }
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════

async def main():
    try:
        await run_mega(target=10000)
    except Exception as e:
        print(f"\n[FATAL] {type(e).__name__}: {e}", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOPPED] KeyboardInterrupt", flush=True)
    except Exception as e:
        print(f"\n[CRASH] {type(e).__name__}: {e}", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        sys.exit(1)
