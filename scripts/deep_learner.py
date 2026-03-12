"""JARVIS Deep Learner — Analyse ultra_stress_v2.db en temps reel.

Apprend:
1. Categorie de prompt → meilleur noeud (affinite)
2. Qualite des reponses (scoring longueur+coherence)
3. Patterns temporels (latence par heure, degradation)
4. Export learnings vers etoile.db (routing JARVIS principal)

Tourne en parallele du stress test, lit la DB en read-only.
"""

import sqlite3
import json
import re
import time
import sys
import os
from pathlib import Path
from collections import defaultdict

# Fix Windows encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STRESS_DB = Path("/home/turbo/jarvis-m1-ops/data/ultra_stress_v2.db")
ETOILE_DB = Path("/home/turbo/jarvis-m1-ops/data/etoile.db")
LEARNINGS_FILE = Path("/home/turbo/jarvis-m1-ops/data/cluster_learnings.json")

# ── Prompt categories (regex-based) ──
CATEGORIES = {
    "code": re.compile(r"(fonction|class|decorator|refactor|test|pytest|endpoint|parser|script|ecris|cree|implem)", re.I),
    "math": re.compile(r"(integrale|probabilite|calcul|equation|combien|racine|\d+\s*[\*\+\-\/]\s*\d+|pi\s)", re.I),
    "reasoning": re.compile(r"(prouve|implique|logique|escargot|paradox|si.*alors|pourquoi)", re.I),
    "trading": re.compile(r"(btc|eth|sol|trading|rsi|macd|dca|crypto|momentum|tendance)", re.I),
    "architecture": re.compile(r"(architecture|microservice|pattern|design|hexagonal|kubernetes|grpc|event.driven)", re.I),
    "database": re.compile(r"(sql|postgres|sqlite|redis|memcache|b.tree|lsm|query|select)", re.I),
    "system": re.compile(r"(circuit.breaker|consensus|raft|gpu|lock.free|zero.copy|websocket|sse)", re.I),
    "creative": re.compile(r"(haiku|slogan|nom de projet|genere)", re.I),
    "knowledge": re.compile(r"(explique|difference|compare|comment|capitale|nouveaute|backpropag|transformer|rnn|crdt|mapreduce|solid)", re.I),
    "debug": re.compile(r"(debug|erreur|error|timeout|cancel|bug|422|corrige)", re.I),
}


def classify_prompt(prompt):
    """Classify a prompt into a category."""
    for cat, regex in CATEGORIES.items():
        if regex.search(prompt):
            return cat
    return "general"


# Map cycle → prompt (from the PROMPTS list in the stress test)
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


def get_prompt_for_cycle(cycle):
    return PROMPTS[cycle % len(PROMPTS)]


def analyze():
    """Analyze stress DB and extract deep learnings."""
    conn = sqlite3.connect(str(STRESS_DB), timeout=10)
    conn.row_factory = sqlite3.Row

    # ── 1. Success rate per category per node ──
    affinity = defaultdict(lambda: defaultdict(lambda: {"ok": 0, "fail": 0, "total_ms": 0}))

    rows = conn.execute("SELECT cycle, node, ok, ms, response_len FROM cycles WHERE ok IS NOT NULL").fetchall()
    for r in rows:
        prompt = get_prompt_for_cycle(r["cycle"])
        cat = classify_prompt(prompt)
        node = r["node"]
        if r["ok"]:
            affinity[cat][node]["ok"] += 1
            affinity[cat][node]["total_ms"] += r["ms"]
        else:
            affinity[cat][node]["fail"] += 1

    # ── 2. Best node per category ──
    best_per_category = {}
    print("=" * 70)
    print("  DEEP LEARNING — AFFINITE CATEGORIE → NOEUD")
    print("=" * 70)

    for cat in sorted(affinity.keys()):
        nodes = affinity[cat]
        # Score = success_rate * (1 / avg_ms_normalized)
        scored = []
        for node, stats in nodes.items():
            total = stats["ok"] + stats["fail"]
            if total < 3:
                continue
            sr = stats["ok"] / total
            avg_ms = stats["total_ms"] / max(stats["ok"], 1)
            # Score: high success + low latency
            speed_bonus = max(0, 1 - avg_ms / 20000)  # 0-1, 1=fast
            score = sr * 0.7 + speed_bonus * 0.3
            scored.append((node, sr, avg_ms, score, stats["ok"], total))

        scored.sort(key=lambda x: x[3], reverse=True)

        if scored:
            best = scored[0]
            best_per_category[cat] = {
                "best_node": best[0],
                "score": round(best[3], 3),
                "success_rate": round(best[1], 3),
                "avg_ms": int(best[2]),
                "samples": best[5],
            }
            print(f"\n  [{cat.upper()}]")
            for node, sr, avg, score, ok_count, total in scored[:5]:
                bar = "█" * int(score * 20)
                print(f"    {node:25s} score={score:.2f} sr={sr:.0%} avg={int(avg)}ms ({ok_count}/{total}) {bar}")

    # ── 3. Response quality analysis ──
    print(f"\n{'=' * 70}")
    print("  QUALITE DES REPONSES PAR NOEUD")
    print("=" * 70)

    quality = conn.execute("""
        SELECT node,
               AVG(CASE WHEN ok=1 THEN response_len END) as avg_len,
               MAX(CASE WHEN ok=1 THEN response_len END) as max_len,
               MIN(CASE WHEN ok=1 THEN response_len END) as min_len,
               COUNT(CASE WHEN ok=1 AND response_len > 100 THEN 1 END) as rich_responses,
               COUNT(CASE WHEN ok=1 THEN 1 END) as total_ok
        FROM cycles
        GROUP BY node
        HAVING total_ok > 5
        ORDER BY avg_len DESC
    """).fetchall()

    quality_scores = {}
    for r in quality:
        node = r[0]
        avg_len = int(r[1] or 0)
        rich = r[4] or 0
        total_ok = r[5] or 0
        rich_pct = rich * 100 // max(total_ok, 1)
        quality_scores[node] = {"avg_len": avg_len, "rich_pct": rich_pct, "total_ok": total_ok}
        print(f"  {node:25s} avg_len={avg_len:5d} chars  rich={rich_pct:3d}% ({rich}/{total_ok})")

    # ── 4. Latency trends (degradation detection) ──
    print(f"\n{'=' * 70}")
    print("  TENDANCES LATENCE (premier 1/3 vs dernier 1/3)")
    print("=" * 70)

    max_cycle = conn.execute("SELECT MAX(cycle) FROM cycles").fetchone()[0] or 0
    third = max_cycle // 3

    trends = conn.execute("""
        SELECT node,
               AVG(CASE WHEN cycle < ? AND ok=1 THEN ms END) as early_ms,
               AVG(CASE WHEN cycle > ? AND ok=1 THEN ms END) as late_ms
        FROM cycles
        GROUP BY node
        HAVING early_ms IS NOT NULL AND late_ms IS NOT NULL
    """, (third, max_cycle - third)).fetchall()

    trend_data = {}
    for r in trends:
        node, early, late = r[0], int(r[1] or 0), int(r[2] or 0)
        if early == 0:
            continue
        change = (late - early) * 100 // early
        direction = "↗ DEGRADATION" if change > 20 else "↘ AMELIORATION" if change < -20 else "→ STABLE"
        trend_data[node] = {"early_ms": early, "late_ms": late, "change_pct": change}
        print(f"  {node:25s} {early:5d}ms → {late:5d}ms  ({change:+d}%) {direction}")

    # ── 5. Export learnings ──
    learnings = {
        "timestamp": time.time(),
        "total_cycles": max_cycle + 1,
        "best_per_category": best_per_category,
        "quality_scores": quality_scores,
        "latency_trends": trend_data,
        "routing_recommendations": {},
    }

    # Build routing recommendations
    for cat, data in best_per_category.items():
        if data["score"] > 0.5:
            learnings["routing_recommendations"][cat] = {
                "primary": data["best_node"],
                "confidence": data["score"],
                "avg_ms": data["avg_ms"],
            }

    # Save to JSON
    with open(LEARNINGS_FILE, "w") as f:
        json.dump(learnings, f, indent=2)
    print(f"\n  Learnings saved to {LEARNINGS_FILE}")

    # ── 6. Inject into etoile.db ──
    try:
        econn = sqlite3.connect(str(ETOILE_DB), timeout=5)
        econn.execute("""CREATE TABLE IF NOT EXISTS cluster_learnings (
            id INTEGER PRIMARY KEY, category TEXT, best_node TEXT,
            score REAL, success_rate REAL, avg_ms INT, samples INT, ts REAL
        )""")
        econn.execute("DELETE FROM cluster_learnings")  # fresh snapshot
        for cat, data in best_per_category.items():
            econn.execute(
                "INSERT INTO cluster_learnings (category, best_node, score, success_rate, avg_ms, samples, ts) VALUES (?,?,?,?,?,?,?)",
                (cat, data["best_node"], data["score"], data["success_rate"], data["avg_ms"], data["samples"], time.time())
            )
        econn.commit()
        econn.close()
        print(f"  Learnings injected into etoile.db ({len(best_per_category)} categories)")
    except Exception as e:
        print(f"  WARNING: Could not inject into etoile.db: {e}")

    conn.close()

    # ── Summary ──
    print(f"\n{'=' * 70}")
    print(f"  RESUME APPRENTISSAGE")
    print(f"{'=' * 70}")
    print(f"  Categories apprises: {len(best_per_category)}")
    print(f"  Noeuds evalues:      {len(quality_scores)}")
    print(f"  Tendances latence:   {len(trend_data)}")
    print(f"  Recommandations:     {len(learnings['routing_recommendations'])}")
    for cat, rec in learnings["routing_recommendations"].items():
        print(f"    {cat:15s} → {rec['primary']:25s} (conf={rec['confidence']:.2f}, {rec['avg_ms']}ms)")


if __name__ == "__main__":
    analyze()
