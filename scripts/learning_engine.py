"""JARVIS Learning Engine — Stress + Deep Learning integre.

UN SEUL script qui fait TOUT:
1. Envoie des requetes au cluster (stress)
2. Analyse les resultats en temps reel (deep learning)
3. Ajuste le routing dynamiquement (autolearn)
4. Detecte anomalies et patterns
5. Injecte learnings dans etoile.db
6. Telegram reports

10 000 cycles. Chaque cycle:
- Envoie 1 prompt a 4-5 noeuds en parallele
- Analyse immediate (EMA incremental)
- Toutes les 50 cycles: full analysis + routing update
- Toutes les 500 cycles: Telegram report
"""

import asyncio
import json
import math
import os
import re
import sqlite3
import sys
import time
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

HF_TOKEN = os.getenv("HF_TOKEN", "")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT", "")

DB_PATH = Path("F:/BUREAU/turbo/data/learning_engine.db")
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")
LEARNINGS_FILE = Path("F:/BUREAU/turbo/data/deep_learnings.json")

# ── NODES (only proven + active ones) ──
NODES = {
    # LOCAL — M1 principal (46 tok/s, qwen3-8b, 6 GPU)
    "M1/qwen3-8b": {
        "url": "http://127.0.0.1:1234/v1/chat/completions",
        "model": "qwen3-8b", "type": "openai", "timeout": 15,
        "system": "/nothink\nTu es JARVIS. Reponds en francais, concis.",
    },
    # LOCAL — OL1 rapide (84 tok/s, qwen3:1.7b)
    "OL1/qwen3:1.7b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b", "type": "ollama", "timeout": 8,
    },
    # DISTANT — M2 reasoning (si en ligne, bonus)
    "M2/deepseek-r1": {
        "url": "http://192.168.1.26:1234/v1/chat/completions",
        "model": "deepseek-r1-0528-qwen3-8b", "type": "openai", "timeout": 12,
        "system": "Tu es JARVIS. Reponds en francais.",
    },
    # DISTANT — M3 fallback
    "M3/deepseek-r1": {
        "url": "http://192.168.1.113:1234/v1/chat/completions",
        "model": "deepseek-r1-0528-qwen3-8b", "type": "openai", "timeout": 12,
        "system": "Tu es JARVIS. Reponds en francais.",
    },
}

# ── PROMPTS (50 diversifies) ──
PROMPTS = [
    "Ecris une fonction Python quicksort optimisee",
    "Corrige: KeyError dans un dict nested",
    "Cree un decorator retry avec backoff exponentiel",
    "Refactorise avec le pattern Strategy",
    "Test pytest pour une API FastAPI",
    "Escargot 3m jour 2m nuit mur 10m combien de jours",
    "Prouve racine(2) irrationnel",
    "Si A implique B et B implique C alors A implique C ?",
    "Analyse technique BTC RSI 65 MACD convergent",
    "Compare DCA vs lump sum ETH 2025",
    "Architecture event-driven notifications",
    "PostgreSQL vs SQLite 10M rows 50 req/s",
    "Pattern circuit breaker exemple concret",
    "Consensus Raft distribue explication",
    "Nom de projet dashboard IA temps reel",
    "Slogan JARVIS 5 mots",
    "FastAPI 422 debug schema Pydantic",
    "asyncio.CancelledError producer-consumer",
    "Integrale x*ln(x) dx",
    "Probabilite 3 as sur 5 cartes tirees de 52",
    "Nouveautes Python 3.13",
    "Tendances crypto mars 2026",
    "1337 * 42 =",
    "Capitale du Japon",
    "Pi 10 decimales",
    "Ecris un haiku sur le machine learning",
    "Compare Redis vs Memcached",
    "Optimise SELECT * FROM logs WHERE ts > now()-1h",
    "Difference WebSocket vs SSE vs long polling",
    "Script bash monitor disk usage alerte 90%",
    "Trading RSI MACD PEPE momentum",
    "Singleton vs dependency injection avantages",
    "GPU offloading comment ca marche",
    "Cree une classe Python LinkedList",
    "Explique les goroutines Go vs async Python",
    "Architecture hexagonale vs clean architecture",
    "Kubernetes vs Docker Swarm pour 50 pods",
    "SOLID principes avec exemples Python",
    "Rate limiter token bucket implementation",
    "Bloom filter probabiliste explication",
    "B-tree vs LSM-tree pour une DB",
    "Zero-copy networking explication",
    "Lock-free queue en C++ principe",
    "MapReduce vs Spark streaming differences",
    "gRPC vs REST pour microservices internes",
    "CRDT types et cas d'usage",
    "Ecris un parser JSON minimal en Python",
    "Compare transformer vs RNN pour du NLP",
    "Backpropagation expliquee simplement",
    "Monte Carlo Tree Search pour jeux",
]

# ── CATEGORIES ──
CATEGORIES = {
    "code": re.compile(r"(fonction|class|decorator|refactor|test|pytest|endpoint|parser|script|ecris|cree|implem|fibonacci|context manager|dataclass|tri\b|linked)", re.I),
    "math": re.compile(r"(integrale|probabilite|calcul|equation|combien|racine|\d+\s*[\*\+\-\/]\s*\d+|pi\s|monte carlo)", re.I),
    "reasoning": re.compile(r"(prouve|implique|logique|escargot|paradox|si.*alors|pourquoi|conclure)", re.I),
    "trading": re.compile(r"(btc|eth|sol|trading|rsi|macd|dca|crypto|momentum|tendance|support|resistance)", re.I),
    "architecture": re.compile(r"(architecture|microservice|pattern|design|hexagonal|kubernetes|grpc|event.driven|clean.arch)", re.I),
    "database": re.compile(r"(sql|postgres|sqlite|redis|memcache|b.tree|lsm|query|select|10M rows)", re.I),
    "system": re.compile(r"(circuit.breaker|consensus|raft|gpu|lock.free|zero.copy|websocket|sse|rate.limit|bloom.filter|token.bucket)", re.I),
    "creative": re.compile(r"(haiku|slogan|nom de projet|genere)", re.I),
    "knowledge": re.compile(r"(explique|difference|compare|comment|capitale|nouveaute|backpropag|transformer|rnn|crdt|mapreduce|solid|goroutine)", re.I),
    "debug": re.compile(r"(debug|erreur|error|timeout|cancel|bug|422|corrige|indexerror)", re.I),
}


def classify(prompt):
    for cat, regex in CATEGORIES.items():
        if regex.search(prompt):
            return cat
    return "general"


def complexity(prompt):
    score = 1
    if len(prompt) > 80: score += 1
    if any(w in prompt.lower() for w in ["architecture", "compare", "explique", "prouve", "optimise"]): score += 1
    if any(w in prompt.lower() for w in ["integrale", "probabilite", "consensus", "backpropag", "monte carlo"]): score += 2
    if any(w in prompt.lower() for w in ["refactor", "pattern", "kubernetes", "grpc", "crdt"]): score += 1
    return min(score, 5)


class LearningEngine:
    def __init__(self):
        self.ema_alpha = 0.12
        # Per-category per-node EMA scores
        self.cat_node_ema = defaultdict(lambda: defaultdict(float))
        # Per-node global EMAs
        self.node_latency_ema = {}
        self.node_quality_ema = {}
        self.node_sr_ema = {}
        # Complexity routing
        self.complexity_routing = {}
        # Anomalies
        self.anomalies = []
        # Circuit breakers: node → {"fails": int, "open_until": float}
        self.circuits = {}
        # Stats
        self.total_ok = 0
        self.total_fail = 0
        self.total_ms = 0
        self.cycle = 0
        self.learning_cycle = 0
        self.node_stats = {n: {"ok": 0, "fail": 0, "ms": 0} for n in NODES}

        self._init_db()
        self._load_state()

    def _init_db(self):
        self.conn = sqlite3.connect(str(DB_PATH), timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle INT, node TEXT, ok INT, ms INT, response_len INT,
            category TEXT, complexity INT, prompt TEXT, ts REAL
        )""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS learnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            learning_cycle INT, category TEXT, best_node TEXT,
            score REAL, latency_ms INT, quality INT,
            alternatives TEXT, ts REAL
        )""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle INT, type TEXT, node TEXT,
            detail TEXT, ts REAL
        )""")
        self.conn.commit()

        # Resume from last cycle
        r = self.conn.execute("SELECT MAX(cycle) FROM cycles").fetchone()
        if r[0] is not None:
            self.cycle = r[0] + 1

    def _load_state(self):
        if LEARNINGS_FILE.exists():
            try:
                data = json.loads(LEARNINGS_FILE.read_text(encoding="utf-8"))
                if "cat_node_ema" in data:
                    for cat, nodes in data["cat_node_ema"].items():
                        for node, score in nodes.items():
                            self.cat_node_ema[cat][node] = score
                self.node_latency_ema = data.get("node_latency_ema", {})
                self.node_quality_ema = data.get("node_quality_ema", {})
                self.node_sr_ema = data.get("node_sr_ema", {})
                self.learning_cycle = data.get("learning_cycle", 0)
                self.complexity_routing = data.get("complexity_routing", {})
                print(f"  [RESUME] LC#{self.learning_cycle}, cycle={self.cycle}")
            except Exception:
                pass

    def _save_state(self):
        # Convert defaultdicts
        cat_ema = {cat: dict(nodes) for cat, nodes in self.cat_node_ema.items()}
        data = {
            "cat_node_ema": cat_ema,
            "node_latency_ema": self.node_latency_ema,
            "node_quality_ema": self.node_quality_ema,
            "node_sr_ema": self.node_sr_ema,
            "learning_cycle": self.learning_cycle,
            "complexity_routing": self.complexity_routing,
            "routing_table": self._routing_table(),
            "cycle": self.cycle,
            "timestamp": time.time(),
        }
        LEARNINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _ema(self, old, new):
        if old is None or old == 0:
            return new
        return self.ema_alpha * new + (1 - self.ema_alpha) * old

    def is_circuit_open(self, node):
        cb = self.circuits.get(node)
        if not cb:
            return False
        if time.time() > cb["open_until"]:
            # Half-open: allow 1 attempt
            cb["fails"] = 0
            return False
        return True

    def record_fail(self, node):
        cb = self.circuits.setdefault(node, {"fails": 0, "open_until": 0, "total_fails": 0})
        cb["fails"] += 1
        cb["total_fails"] = cb.get("total_fails", 0) + 1
        if cb["fails"] >= 5:
            # Escalating timeout: 30s, 2min, 10min, 30min based on total fails
            tf = cb["total_fails"]
            timeout = 30 if tf < 10 else 120 if tf < 30 else 600 if tf < 100 else 1800
            cb["open_until"] = time.time() + timeout
            self.anomalies.append({
                "type": "circuit_open", "node": node,
                "cycle": self.cycle, "detail": f"{cb['fails']} consecutive fails"
            })

    def record_success(self, node):
        cb = self.circuits.get(node)
        if cb:
            cb["fails"] = max(0, cb["fails"] - 1)

    def _routing_table(self):
        table = {}
        for cat, nodes in self.cat_node_ema.items():
            if not nodes:
                continue
            sorted_nodes = sorted(nodes.items(), key=lambda x: x[1], reverse=True)
            best = sorted_nodes[0]
            table[cat] = {
                "node": best[0], "score": round(best[1], 3),
                "latency_ms": int(self.node_latency_ema.get(best[0], 0)),
                "quality": int(self.node_quality_ema.get(best[0], 0)),
                "alternatives": [(n, round(s, 3)) for n, s in sorted_nodes[1:4] if s > 0.2],
            }
        return table

    async def call_node(self, client, node_id, prompt):
        cfg = NODES[node_id]
        t0 = time.time()
        try:
            headers = {"Content-Type": "application/json"}
            if "auth" in cfg:
                headers["Authorization"] = cfg["auth"]

            if cfg["type"] == "ollama":
                body = {
                    "model": cfg["model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False, "think": False,
                }
            else:
                messages = [{"role": "user", "content": prompt}]
                if "system" in cfg:
                    messages.insert(0, {"role": "system", "content": cfg["system"]})
                body = {
                    "model": cfg["model"], "messages": messages,
                    "max_tokens": 512, "temperature": 0.3, "stream": False,
                }

            resp = await client.post(cfg["url"], json=body, headers=headers, timeout=cfg["timeout"])
            ms = int((time.time() - t0) * 1000)

            if resp.status_code != 200:
                return {"node": node_id, "ok": False, "ms": ms, "len": 0}

            data = resp.json()
            if cfg["type"] == "ollama":
                text = data.get("message", {}).get("content", "")
            else:
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Strip think tags
            text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
            text = re.sub(r"<think>[\s\S]*$", "", text).strip()

            return {"node": node_id, "ok": True, "ms": ms, "len": len(text)}

        except Exception:
            ms = int((time.time() - t0) * 1000)
            return {"node": node_id, "ok": False, "ms": ms, "len": 0}

    def learn_from_result(self, node, ok, ms, resp_len, cat, cplx):
        """Incremental EMA learning from a single result."""
        if ok:
            sr = 1.0
            speed_score = max(0, 1 - ms / 15000)
            quality_score = min(1, resp_len / 400)
            composite = sr * 0.45 + speed_score * 0.25 + quality_score * 0.30

            old = self.cat_node_ema[cat].get(node, 0)
            self.cat_node_ema[cat][node] = self._ema(old, composite)

            self.node_latency_ema[node] = self._ema(self.node_latency_ema.get(node), ms)
            self.node_quality_ema[node] = self._ema(self.node_quality_ema.get(node), resp_len)
            self.node_sr_ema[node] = self._ema(self.node_sr_ema.get(node, 0.5), 1.0)

            self.record_success(node)

            # Complexity routing
            key = str(cplx)
            if key not in self.complexity_routing:
                self.complexity_routing[key] = {}
            old_c = self.complexity_routing[key].get(cat, {}).get("score", 0)
            if composite > old_c:
                self.complexity_routing[key][cat] = {"node": node, "score": round(composite, 3)}
        else:
            # Penalize
            old = self.cat_node_ema[cat].get(node, 0.5)
            self.cat_node_ema[cat][node] = self._ema(old, 0.05)
            self.node_sr_ema[node] = self._ema(self.node_sr_ema.get(node, 0.5), 0.0)
            self.record_fail(node)

    async def inject_etoile(self):
        """Inject learnings into etoile.db."""
        rt = self._routing_table()
        try:
            econn = sqlite3.connect(str(ETOILE_DB), timeout=5)
            econn.execute("""CREATE TABLE IF NOT EXISTS deep_learnings (
                id INTEGER PRIMARY KEY, category TEXT, complexity TEXT,
                best_node TEXT, score REAL, ema_latency REAL, ema_quality REAL,
                samples INT, learning_cycle INT, ts REAL
            )""")
            econn.execute("DELETE FROM deep_learnings")
            for cat, rec in rt.items():
                econn.execute(
                    "INSERT INTO deep_learnings VALUES (NULL,?,?,?,?,?,?,?,?,?)",
                    (cat, "all", rec["node"], rec["score"],
                     rec["latency_ms"], rec["quality"], 0,
                     self.learning_cycle, time.time())
                )
            for cplx, cats in self.complexity_routing.items():
                for cat, rec in cats.items():
                    econn.execute(
                        "INSERT INTO deep_learnings VALUES (NULL,?,?,?,?,?,?,?,?,?)",
                        (cat, f"cplx_{cplx}", rec["node"], rec["score"],
                         0, 0, 0, self.learning_cycle, time.time())
                    )
            econn.commit()
            econn.close()
        except Exception as e:
            print(f"  [WARN] etoile: {e}")

    async def send_telegram(self, client, text):
        if not TG_TOKEN or not TG_CHAT:
            return
        try:
            await client.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT, "text": text[:4000], "parse_mode": "HTML"},
                timeout=10,
            )
        except Exception:
            pass

    def print_learning_report(self):
        rt = self._routing_table()
        print(f"\n{'='*70}")
        print(f"  LEARNING #{self.learning_cycle} | Cycle {self.cycle} | OK={self.total_ok} FAIL={self.total_fail} SR={self.total_ok*100//max(self.total_ok+self.total_fail,1)}%")
        print(f"{'='*70}")

        print(f"\n  ROUTING ({len(rt)} categories):")
        for cat in sorted(rt.keys()):
            rec = rt[cat]
            alts = " | ".join(f"{n}({s})" for n, s in rec["alternatives"][:2])
            bar = "#" * int(rec["score"] * 20)
            print(f"    {cat:14s} -> {rec['node']:22s} s={rec['score']:.3f} lat={rec['latency_ms']:5d}ms q={rec['quality']:4d} {bar}")
            if alts:
                print(f"    {'':14s}    alt: {alts}")

        if self.complexity_routing:
            print(f"\n  COMPLEXITY:")
            for cplx in sorted(self.complexity_routing.keys()):
                cats = self.complexity_routing[cplx]
                items = " ".join(f"{c}={r['node'].split('/')[0]}" for c, r in sorted(cats.items())[:5])
                print(f"    L{cplx}: {items}")

        # Node health
        print(f"\n  NODE HEALTH:")
        for node in sorted(self.node_latency_ema.keys(), key=lambda n: self.node_sr_ema.get(n, 0), reverse=True):
            sr = self.node_sr_ema.get(node, 0)
            lat = self.node_latency_ema.get(node, 0)
            qual = self.node_quality_ema.get(node, 0)
            cb = self.circuits.get(node, {})
            status = "OPEN" if self.is_circuit_open(node) else "OK"
            print(f"    {node:22s} SR={sr:.0%} lat={int(lat):5d}ms qual={int(qual):4d}c [{status}]")

        # Anomalies recentes
        recent = [a for a in self.anomalies if a.get("cycle", 0) > self.cycle - 200]
        if recent:
            print(f"\n  ANOMALIES ({len(recent)} recent):")
            for a in recent[-5:]:
                print(f"    [{a['type']}] {a['node']} @{a['cycle']}: {a.get('detail','')}")

        sys.stdout.flush()

    async def run(self, target=10000):
        t0 = time.time()
        start_cycle = self.cycle
        node_ids = list(NODES.keys())

        print(f"\n{'='*70}")
        print(f"  JARVIS LEARNING ENGINE — {target} cycles")
        print(f"  Resume cycle={self.cycle} | {len(NODES)} nodes | {len(PROMPTS)} prompts")
        print(f"  EMA alpha={self.ema_alpha} | Circuit breaker: 5 fails = 2min open")
        print(f"{'='*70}\n")
        sys.stdout.flush()

        async with httpx.AsyncClient() as client:
            # ── WARMUP: precharge les modeles ──
            print("  [WARMUP] Precharge des modeles...")
            sys.stdout.flush()
            warmup_tasks = []
            for nid, cfg in NODES.items():
                warmup_tasks.append(self.call_node(client, nid, "test"))
            warmup_results = await asyncio.gather(*warmup_tasks, return_exceptions=True)
            alive = [r["node"] for r in warmup_results if not isinstance(r, Exception) and r["ok"]]
            dead = [r["node"] for r in warmup_results if not isinstance(r, Exception) and not r["ok"]]
            print(f"  [WARMUP] OK: {alive}")
            print(f"  [WARMUP] DEAD: {dead}")
            # Pre-open circuits for dead nodes
            for nid in dead:
                cb = self.circuits.setdefault(nid, {"fails": 0, "open_until": 0, "total_fails": 0})
                cb["fails"] = 5
                cb["total_fails"] = cb.get("total_fails", 0) + 5
                cb["open_until"] = time.time() + 300  # 5 min
            sys.stdout.flush()

            # Wait 5s for models to stabilize
            await asyncio.sleep(5)

            # Telegram start
            await self.send_telegram(client,
                f"<b>LEARNING ENGINE START</b>\n"
                f"{target} cycles | {len(NODES)} nodes | Resume @{self.cycle}\n"
                f"Alive: {', '.join(alive)}\nDead: {', '.join(dead)}"
            )

            for _ in range(target):
              try:
                prompt = PROMPTS[self.cycle % len(PROMPTS)]
                cat = classify(prompt)
                cplx = complexity(prompt)

                # Select active nodes (skip circuit-open ones)
                active = [n for n in node_ids if not self.is_circuit_open(n)]
                if not active:
                    # All circuits open — force half-open all
                    for n in node_ids:
                        cb = self.circuits.get(n)
                        if cb:
                            cb["open_until"] = 0
                    active = node_ids

                # Call all active nodes in parallel
                tasks = [self.call_node(client, n, prompt) for n in active]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for r in results:
                    if isinstance(r, Exception):
                        self.total_fail += 1
                        continue

                    node = r["node"]
                    ok = r["ok"]
                    ms = r["ms"]
                    resp_len = r["len"]

                    # Store in DB
                    self.conn.execute(
                        "INSERT INTO cycles VALUES (NULL,?,?,?,?,?,?,?,?,?)",
                        (self.cycle, node, int(ok), ms, resp_len, cat, cplx, prompt[:100], time.time())
                    )

                    # Stats
                    if ok:
                        self.total_ok += 1
                        self.total_ms += ms
                        self.node_stats.setdefault(node, {"ok": 0, "fail": 0, "ms": 0})
                        self.node_stats[node]["ok"] += 1
                        self.node_stats[node]["ms"] += ms
                    else:
                        self.total_fail += 1
                        self.node_stats.setdefault(node, {"ok": 0, "fail": 0, "ms": 0})
                        self.node_stats[node]["fail"] += 1

                    # LEARN immediately
                    self.learn_from_result(node, ok, ms, resp_len, cat, cplx)

                # Anomaly: check for latency spike on best nodes
                for node in active:
                    if node in self.node_latency_ema and self.node_sr_ema.get(node, 0) > 0.5:
                        recent_results = [r for r in results if not isinstance(r, Exception) and r["node"] == node and r["ok"]]
                        if recent_results:
                            current_ms = recent_results[0]["ms"]
                            ema_ms = self.node_latency_ema[node]
                            if current_ms > ema_ms * 3 and current_ms > 5000:
                                self.anomalies.append({
                                    "type": "latency_spike", "node": node,
                                    "cycle": self.cycle,
                                    "detail": f"{current_ms}ms vs EMA {int(ema_ms)}ms"
                                })
                                if len(self.anomalies) > 100:
                                    self.anomalies = self.anomalies[-100:]

                self.conn.commit()
                self.cycle += 1

                # ── Periodic reports ──
                done = self.cycle - start_cycle

                # Full learning report every 50 cycles
                if done % 50 == 0:
                    self.learning_cycle += 1
                    await self.inject_etoile()
                    self._save_state()
                    self.print_learning_report()

                    # Store learning snapshot in DB
                    rt = self._routing_table()
                    for cat, rec in rt.items():
                        self.conn.execute(
                            "INSERT INTO learnings VALUES (NULL,?,?,?,?,?,?,?,?)",
                            (self.learning_cycle, cat, rec["node"], rec["score"],
                             rec["latency_ms"], rec["quality"],
                             json.dumps(rec["alternatives"]), time.time())
                        )
                    self.conn.commit()

                # Short progress every 10 cycles
                elif done % 10 == 0:
                    elapsed = int(time.time() - t0)
                    avg = self.total_ms // max(self.total_ok, 1)
                    sr = self.total_ok * 100 // max(self.total_ok + self.total_fail, 1)
                    rt = self._routing_table()
                    top3 = ", ".join(f"{c}={r['node'].split('/')[0]}" for c, r in sorted(rt.items(), key=lambda x: x[1]["score"], reverse=True)[:3])
                    print(f"  [{done:5d}/{target}] OK={self.total_ok} FAIL={self.total_fail} SR={sr}% avg={avg}ms {elapsed}s | {top3}")
                    sys.stdout.flush()

                # Telegram every 500
                if done % 500 == 0 and done > 0:
                    elapsed = int(time.time() - t0)
                    rt = self._routing_table()
                    routing_lines = "\n".join(
                        f"  {cat} -> {rec['node']} ({rec['score']:.2f})"
                        for cat, rec in sorted(rt.items(), key=lambda x: x[1]["score"], reverse=True)[:8]
                    )
                    node_lines = "\n".join(
                        f"  {n}: SR={self.node_sr_ema.get(n,0):.0%} lat={int(self.node_latency_ema.get(n,0))}ms"
                        for n in sorted(self.node_latency_ema.keys(), key=lambda x: self.node_sr_ema.get(x,0), reverse=True)[:6]
                    )
                    await self.send_telegram(client, (
                        f"<b>LEARNING [{done}/{target}]</b>\n"
                        f"OK={self.total_ok} FAIL={self.total_fail} SR={self.total_ok*100//max(self.total_ok+self.total_fail,1)}%\n"
                        f"Elapsed: {elapsed}s | LC#{self.learning_cycle}\n\n"
                        f"<b>Routing:</b>\n<pre>{routing_lines}</pre>\n\n"
                        f"<b>Nodes:</b>\n<pre>{node_lines}</pre>"
                    ))

              except Exception as cycle_err:
                print(f"  [ERR cycle {self.cycle}] {cycle_err}")
                sys.stdout.flush()
                self.cycle += 1
                continue

            # ── FINAL ──
            elapsed = int(time.time() - t0)
            self.learning_cycle += 1
            await self.inject_etoile()
            self._save_state()

            print(f"\n{'='*70}")
            print(f"  LEARNING ENGINE COMPLETE")
            print(f"{'='*70}")
            print(f"  Cycles: {target} | Time: {elapsed}s ({elapsed//60}min)")
            print(f"  OK: {self.total_ok} | FAIL: {self.total_fail} | SR: {self.total_ok*100//max(self.total_ok+self.total_fail,1)}%")
            print(f"  Learning cycles: {self.learning_cycle}")
            print(f"  Anomalies: {len(self.anomalies)}")

            rt = self._routing_table()
            print(f"\n  FINAL ROUTING TABLE:")
            for cat in sorted(rt.keys()):
                rec = rt[cat]
                print(f"    {cat:14s} -> {rec['node']:22s} score={rec['score']:.3f}")

            sys.stdout.flush()

            # Final telegram
            rt_text = "\n".join(f"  {c} -> {r['node']} ({r['score']:.2f})" for c, r in sorted(rt.items(), key=lambda x: x[1]["score"], reverse=True))
            await self.send_telegram(client, (
                f"<b>LEARNING COMPLETE</b>\n"
                f"{target} cycles in {elapsed}s\n"
                f"OK={self.total_ok} FAIL={self.total_fail}\n"
                f"LC={self.learning_cycle}\n\n"
                f"<b>Final Routing:</b>\n<pre>{rt_text}</pre>"
            ))

        self.conn.close()


async def main():
    engine = LearningEngine()
    await engine.run(target=10000)


if __name__ == "__main__":
    asyncio.run(main())
