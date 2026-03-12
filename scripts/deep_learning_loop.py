"""JARVIS Deep Learning Loop — 10 000 cycles d'apprentissage continu.

Tourne en parallele du stress test. A chaque iteration:
1. Analyse les nouvelles donnees de ultra_stress_v2.db
2. Calcule affinite categorie→noeud (ponderation success + vitesse + qualite)
3. Detecte patterns temporels (degradation, amelioration)
4. Apprend les correlations prompt_complexity → best_node
5. Injecte learnings dans etoile.db (routing JARVIS)
6. Genere des recommendations de routing dynamique
7. Telegram report toutes les 500 iterations

Vrai apprentissage — pas juste enable/disable, mais:
- Scoring multi-criteres (success, latence, qualite reponse, stabilite)
- Apprentissage incrementale (EMA — exponential moving average)
- Detection d'anomalies (sudden drops, latency spikes)
- Routing adaptatif par categorie + complexite
"""

import sqlite3
import json
import re
import time
import sys
import os
import math
from pathlib import Path
from collections import defaultdict

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STRESS_DB = Path("/home/turbo/jarvis-m1-ops/data/ultra_stress_v2.db")
ETOILE_DB = Path("/home/turbo/jarvis-m1-ops/data/etoile.db")
LEARNINGS_FILE = Path("/home/turbo/jarvis-m1-ops/data/deep_learnings.json")
HISTORY_FILE = Path("/home/turbo/jarvis-m1-ops/data/learning_history.json")

TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT", "")

# ── Prompt categories ──
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

# Map known prompts (from stress test)
PROMPTS_STRESS = [
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


def classify_prompt(prompt):
    for cat, regex in CATEGORIES.items():
        if regex.search(prompt):
            return cat
    return "general"


def get_prompt_for_cycle(cycle):
    return PROMPTS_STRESS[cycle % len(PROMPTS_STRESS)]


def estimate_complexity(prompt):
    """Estimate prompt complexity 1-5."""
    score = 1
    if len(prompt) > 80:
        score += 1
    if any(w in prompt.lower() for w in ["architecture", "compare", "explique", "prouve", "optimise"]):
        score += 1
    if any(w in prompt.lower() for w in ["integrale", "probabilite", "consensus", "backpropag", "monte carlo"]):
        score += 2
    if any(w in prompt.lower() for w in ["refactor", "pattern", "kubernetes", "grpc", "crdt"]):
        score += 1
    return min(score, 5)


class DeepLearner:
    def __init__(self):
        self.ema_alpha = 0.15  # EMA decay — recent data weighted more
        self.node_scores = {}  # node → {cat → EMA score}
        self.quality_ema = {}  # node → EMA quality
        self.latency_ema = {}  # node → EMA latency
        self.anomalies = []
        self.last_cycle_seen = 0
        self.learning_cycle = 0
        self.history = []
        self.complexity_routing = {}  # complexity_level → {cat → best_node}
        self._load_state()

    def _load_state(self):
        if LEARNINGS_FILE.exists():
            try:
                data = json.loads(LEARNINGS_FILE.read_text(encoding="utf-8"))
                self.node_scores = data.get("node_scores", {})
                self.quality_ema = data.get("quality_ema", {})
                self.latency_ema = data.get("latency_ema", {})
                self.last_cycle_seen = data.get("last_cycle_seen", 0)
                self.learning_cycle = data.get("learning_cycle", 0)
                self.complexity_routing = data.get("complexity_routing", {})
                print(f"  [LOAD] Reprise cycle #{self.learning_cycle}, dernier stress cycle={self.last_cycle_seen}")
            except Exception:
                pass

    def _save_state(self):
        data = {
            "node_scores": self.node_scores,
            "quality_ema": self.quality_ema,
            "latency_ema": self.latency_ema,
            "last_cycle_seen": self.last_cycle_seen,
            "learning_cycle": self.learning_cycle,
            "complexity_routing": self.complexity_routing,
            "timestamp": time.time(),
            "routing_table": self._build_routing_table(),
        }
        LEARNINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _save_history(self, snapshot):
        if HISTORY_FILE.exists():
            try:
                self.history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.history = []
        self.history.append(snapshot)
        # Keep last 500 snapshots
        if len(self.history) > 500:
            self.history = self.history[-500:]
        HISTORY_FILE.write_text(json.dumps(self.history, indent=2, ensure_ascii=False), encoding="utf-8")

    def _ema_update(self, old_val, new_val):
        if old_val is None:
            return new_val
        return self.ema_alpha * new_val + (1 - self.ema_alpha) * old_val

    def learn_iteration(self):
        """One learning iteration — analyze new data since last cycle."""
        if not STRESS_DB.exists():
            print("  [WAIT] DB pas encore creee...")
            return False

        conn = sqlite3.connect(str(STRESS_DB), timeout=10)
        conn.row_factory = sqlite3.Row

        max_cycle = conn.execute("SELECT MAX(cycle) FROM cycles").fetchone()[0]
        if max_cycle is None or max_cycle <= self.last_cycle_seen:
            conn.close()
            return False  # No new data

        new_rows = conn.execute(
            "SELECT cycle, node, ok, ms, response_len FROM cycles WHERE cycle > ? AND ok IS NOT NULL",
            (self.last_cycle_seen,)
        ).fetchall()

        if not new_rows:
            conn.close()
            return False

        # ── 1. Incremental EMA learning per category per node ──
        cat_node_batch = defaultdict(lambda: defaultdict(lambda: {"ok": 0, "fail": 0, "ms_sum": 0, "len_sum": 0}))

        for r in new_rows:
            prompt = get_prompt_for_cycle(r["cycle"])
            cat = classify_prompt(prompt)
            node = r["node"]
            if r["ok"]:
                cat_node_batch[cat][node]["ok"] += 1
                cat_node_batch[cat][node]["ms_sum"] += r["ms"]
                cat_node_batch[cat][node]["len_sum"] += (r["response_len"] or 0)
            else:
                cat_node_batch[cat][node]["fail"] += 1

        # Update EMA scores
        for cat, nodes in cat_node_batch.items():
            if cat not in self.node_scores:
                self.node_scores[cat] = {}
            for node, stats in nodes.items():
                total = stats["ok"] + stats["fail"]
                sr = stats["ok"] / total if total > 0 else 0
                avg_ms = stats["ms_sum"] / max(stats["ok"], 1)
                avg_len = stats["len_sum"] / max(stats["ok"], 1)

                speed_score = max(0, 1 - avg_ms / 20000)
                quality_score = min(1, avg_len / 500)  # 500 chars = quality threshold
                composite = sr * 0.5 + speed_score * 0.2 + quality_score * 0.3

                old = self.node_scores[cat].get(node)
                self.node_scores[cat][node] = self._ema_update(old, composite)

                # Global latency EMA
                if stats["ok"] > 0:
                    old_lat = self.latency_ema.get(node)
                    self.latency_ema[node] = self._ema_update(old_lat, avg_ms)
                    old_qual = self.quality_ema.get(node)
                    self.quality_ema[node] = self._ema_update(old_qual, avg_len)

        # ── 2. Complexity-aware routing ──
        complexity_batch = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"ok": 0, "fail": 0, "ms": 0})))
        for r in new_rows:
            prompt = get_prompt_for_cycle(r["cycle"])
            cat = classify_prompt(prompt)
            cplx = str(estimate_complexity(prompt))
            node = r["node"]
            if r["ok"]:
                complexity_batch[cplx][cat][node]["ok"] += 1
                complexity_batch[cplx][cat][node]["ms"] += r["ms"]
            else:
                complexity_batch[cplx][cat][node]["fail"] += 1

        for cplx, cats in complexity_batch.items():
            if cplx not in self.complexity_routing:
                self.complexity_routing[cplx] = {}
            for cat, nodes in cats.items():
                best_node = None
                best_score = -1
                for node, stats in nodes.items():
                    total = stats["ok"] + stats["fail"]
                    if total < 2:
                        continue
                    sr = stats["ok"] / total
                    spd = max(0, 1 - stats["ms"] / max(stats["ok"], 1) / 20000)
                    sc = sr * 0.6 + spd * 0.4
                    if sc > best_score:
                        best_score = sc
                        best_node = node
                if best_node:
                    self.complexity_routing[cplx][cat] = {"node": best_node, "score": round(best_score, 3)}

        # ── 3. Anomaly detection ──
        for node, lat in self.latency_ema.items():
            # Check for sudden spikes vs historical
            recent_rows = conn.execute(
                "SELECT AVG(ms) FROM cycles WHERE node=? AND ok=1 AND cycle > ? ORDER BY cycle DESC LIMIT 20",
                (node, max(0, max_cycle - 50))
            ).fetchone()
            if recent_rows[0] and lat:
                recent_avg = recent_rows[0]
                if recent_avg > lat * 2:  # 2x spike
                    self.anomalies.append({
                        "type": "latency_spike",
                        "node": node,
                        "expected_ms": int(lat),
                        "actual_ms": int(recent_avg),
                        "cycle": max_cycle,
                    })
                    if len(self.anomalies) > 50:
                        self.anomalies = self.anomalies[-50:]

        # ── 4. Inject into etoile.db ──
        routing_table = self._build_routing_table()
        try:
            econn = sqlite3.connect(str(ETOILE_DB), timeout=5)
            econn.execute("""CREATE TABLE IF NOT EXISTS deep_learnings (
                id INTEGER PRIMARY KEY, category TEXT, complexity TEXT,
                best_node TEXT, score REAL, ema_latency REAL, ema_quality REAL,
                samples INT, learning_cycle INT, ts REAL
            )""")
            econn.execute("""CREATE TABLE IF NOT EXISTS learning_anomalies (
                id INTEGER PRIMARY KEY, type TEXT, node TEXT,
                expected_val REAL, actual_val REAL, cycle INT, ts REAL
            )""")

            # Fresh routing snapshot
            econn.execute("DELETE FROM deep_learnings")
            for cat, rec in routing_table.items():
                econn.execute(
                    "INSERT INTO deep_learnings (category, complexity, best_node, score, ema_latency, ema_quality, samples, learning_cycle, ts) VALUES (?,?,?,?,?,?,?,?,?)",
                    (cat, "all", rec["node"], rec["score"],
                     self.latency_ema.get(rec["node"], 0),
                     self.quality_ema.get(rec["node"], 0),
                     rec.get("samples", 0), self.learning_cycle, time.time())
                )

            # Complexity routing
            for cplx, cats in self.complexity_routing.items():
                for cat, rec in cats.items():
                    econn.execute(
                        "INSERT INTO deep_learnings (category, complexity, best_node, score, ema_latency, ema_quality, samples, learning_cycle, ts) VALUES (?,?,?,?,?,?,?,?,?)",
                        (cat, f"complexity_{cplx}", rec["node"], rec["score"], 0, 0, 0, self.learning_cycle, time.time())
                    )

            # Anomalies
            for a in self.anomalies[-10:]:
                econn.execute(
                    "INSERT OR IGNORE INTO learning_anomalies (type, node, expected_val, actual_val, cycle, ts) VALUES (?,?,?,?,?,?)",
                    (a["type"], a["node"], a.get("expected_ms", 0), a.get("actual_ms", 0), a["cycle"], time.time())
                )

            econn.commit()
            econn.close()
        except Exception as e:
            print(f"  [WARN] etoile.db inject: {e}")

        # Update state
        self.last_cycle_seen = max_cycle
        self.learning_cycle += 1

        # ── 5. Save state + history snapshot ──
        self._save_state()

        total_rows = conn.execute("SELECT COUNT(*) FROM cycles").fetchone()[0]
        total_ok = conn.execute("SELECT SUM(CASE WHEN ok=1 THEN 1 ELSE 0 END) FROM cycles").fetchone()[0] or 0
        conn.close()

        snapshot = {
            "learning_cycle": self.learning_cycle,
            "stress_cycle": max_cycle,
            "new_rows": len(new_rows),
            "total_rows": total_rows,
            "global_sr": round(total_ok / max(total_rows, 1), 3),
            "categories_learned": len(routing_table),
            "anomalies": len(self.anomalies),
            "ts": time.time(),
            "top_routing": {cat: rec["node"] for cat, rec in list(routing_table.items())[:5]},
        }
        self._save_history(snapshot)

        return snapshot

    def _build_routing_table(self):
        table = {}
        for cat, nodes in self.node_scores.items():
            if not nodes:
                continue
            best_node = max(nodes, key=nodes.get)
            table[cat] = {
                "node": best_node,
                "score": round(nodes[best_node], 3),
                "latency_ms": int(self.latency_ema.get(best_node, 0)),
                "quality": int(self.quality_ema.get(best_node, 0)),
                "alternatives": sorted(
                    [(n, round(s, 3)) for n, s in nodes.items() if n != best_node and s > 0.3],
                    key=lambda x: x[1], reverse=True
                )[:3],
            }
        return table

    def print_status(self, snapshot):
        lc = snapshot["learning_cycle"]
        sc = snapshot["stress_cycle"]
        nr = snapshot["new_rows"]
        sr = snapshot["global_sr"]
        nc = snapshot["categories_learned"]

        rt = self._build_routing_table()

        print(f"\n{'='*70}")
        print(f"  LEARNING CYCLE #{lc} | Stress cycle {sc} | +{nr} rows | SR={sr:.0%}")
        print(f"{'='*70}")

        # Routing table
        print(f"\n  ROUTING TABLE ({nc} categories):")
        for cat in sorted(rt.keys()):
            rec = rt[cat]
            alts = ", ".join(f"{n}({s})" for n, s in rec["alternatives"][:2])
            bar = "#" * int(rec["score"] * 20)
            print(f"    {cat:15s} -> {rec['node']:25s} score={rec['score']:.3f} lat={rec['latency_ms']}ms qual={rec['quality']} {bar}")
            if alts:
                print(f"    {'':15s}    alt: {alts}")

        # Complexity routing
        if self.complexity_routing:
            print(f"\n  COMPLEXITY ROUTING:")
            for cplx in sorted(self.complexity_routing.keys()):
                cats = self.complexity_routing[cplx]
                items = ", ".join(f"{c}->{r['node'].split('/')[0]}" for c, r in sorted(cats.items())[:4])
                print(f"    complexity={cplx}: {items}")

        # Anomalies
        if self.anomalies:
            recent = [a for a in self.anomalies if a["cycle"] > sc - 100]
            if recent:
                print(f"\n  ANOMALIES RECENTES ({len(recent)}):")
                for a in recent[-5:]:
                    print(f"    [{a['type']}] {a['node']} expected={a.get('expected_ms',0)}ms actual={a.get('actual_ms',0)}ms @cycle={a['cycle']}")

        # EMA latencies
        print(f"\n  EMA LATENCES (lissees):")
        for node in sorted(self.latency_ema.keys(), key=lambda n: self.latency_ema[n]):
            lat = self.latency_ema[node]
            qual = self.quality_ema.get(node, 0)
            print(f"    {node:25s} {int(lat):5d}ms  qual={int(qual)} chars")

        sys.stdout.flush()

    def send_telegram(self, snapshot):
        if not TG_TOKEN or not TG_CHAT:
            return
        rt = self._build_routing_table()
        routing_lines = "\n".join(
            f"  {cat} -> {rec['node']} ({rec['score']:.2f})"
            for cat, rec in sorted(rt.items(), key=lambda x: x[1]["score"], reverse=True)[:8]
        )
        text = (
            f"<b>DEEP LEARNING #{snapshot['learning_cycle']}</b>\n"
            f"Stress cycle: {snapshot['stress_cycle']} | SR: {snapshot['global_sr']:.0%}\n"
            f"+{snapshot['new_rows']} new rows | {snapshot['categories_learned']} categories\n\n"
            f"<b>Routing:</b>\n<pre>{routing_lines}</pre>\n"
            f"Anomalies: {snapshot['anomalies']}"
        )
        try:
            import urllib.request
            data = json.dumps({"chat_id": TG_CHAT, "text": text[:4000], "parse_mode": "HTML"}).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                data=data, headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass


def main():
    target_cycles = 10_000
    poll_interval = 8  # seconds between learning iterations

    print(f"\n{'='*70}")
    print(f"  JARVIS DEEP LEARNING LOOP — {target_cycles} cycles")
    print(f"  Poll: {poll_interval}s | EMA alpha: 0.15 | Multi-criteres")
    print(f"  DB: {STRESS_DB}")
    print(f"  Output: {LEARNINGS_FILE}")
    print(f"{'='*70}")
    sys.stdout.flush()

    learner = DeepLearner()
    start_lc = learner.learning_cycle
    t0 = time.time()
    no_data_count = 0

    while learner.learning_cycle < start_lc + target_cycles:
        try:
            snapshot = learner.learn_iteration()

            if not snapshot:
                no_data_count += 1
                if no_data_count % 30 == 0:  # Every ~4 min of no data
                    elapsed = int(time.time() - t0)
                    print(f"  [WAIT] Pas de nouvelles donnees... (cycle #{learner.learning_cycle}, {elapsed}s elapsed)")
                    sys.stdout.flush()
                time.sleep(poll_interval)
                continue

            no_data_count = 0
            lc = snapshot["learning_cycle"]

            # Print status every 25 learning cycles
            if lc % 25 == 0 or lc <= 5:
                learner.print_status(snapshot)

            # Short summary otherwise
            elif lc % 5 == 0:
                rt = learner._build_routing_table()
                best_cats = ", ".join(f"{c}={r['score']:.2f}" for c, r in sorted(rt.items(), key=lambda x: x[1]["score"], reverse=True)[:3])
                print(f"  [LC#{lc}] stress={snapshot['stress_cycle']} +{snapshot['new_rows']}rows SR={snapshot['global_sr']:.0%} top: {best_cats}")
                sys.stdout.flush()

            # Telegram every 500
            if lc % 500 == 0:
                learner.send_telegram(snapshot)

            # Brief pause between iterations
            time.sleep(max(1, poll_interval - 2))

        except KeyboardInterrupt:
            print(f"\n  [STOP] Arrete au cycle #{learner.learning_cycle}")
            learner._save_state()
            break
        except Exception as e:
            print(f"  [ERROR] {e}")
            time.sleep(poll_interval)

    # Final report
    elapsed = int(time.time() - t0)
    total_lc = learner.learning_cycle - start_lc
    rt = learner._build_routing_table()

    print(f"\n{'='*70}")
    print(f"  DEEP LEARNING COMPLETE")
    print(f"{'='*70}")
    print(f"  Cycles: {total_lc} | Time: {elapsed}s | Rate: {total_lc/max(elapsed,1)*60:.1f} LC/min")
    print(f"  Categories: {len(rt)} | Anomalies: {len(learner.anomalies)}")
    print(f"\n  FINAL ROUTING TABLE:")
    for cat in sorted(rt.keys()):
        rec = rt[cat]
        print(f"    {cat:15s} -> {rec['node']:25s} score={rec['score']:.3f} lat={rec['latency_ms']}ms")
    print(f"\n  Fichiers:")
    print(f"    {LEARNINGS_FILE}")
    print(f"    {HISTORY_FILE}")
    print(f"    etoile.db (deep_learnings + learning_anomalies)")
    sys.stdout.flush()

    # Final telegram
    if total_lc > 0:
        learner.send_telegram({
            "learning_cycle": learner.learning_cycle,
            "stress_cycle": learner.last_cycle_seen,
            "new_rows": 0,
            "global_sr": 0,
            "categories_learned": len(rt),
            "anomalies": len(learner.anomalies),
        })


if __name__ == "__main__":
    main()
