#!/usr/bin/env python3
"""JARVIS Pattern Agents Benchmark — 1000 cycles via PatternAgentRegistry.

Tests all 14 agents with escalating complexity, multiple strategies.
Saves to etoile.db + JSON report + Telegram summary.
"""
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

# Add project root to path
<<<<<<< Updated upstream
PROJECT_ROOT = Path("/home/turbo/jarvis-m1-ops")
=======
PROJECT_ROOT = Path("/home/turbo/jarvis")
>>>>>>> Stashed changes
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.pattern_agents import PatternAgentRegistry, AgentResult

# ── Task Pool ───────────────────────────────────────────────────────────────
TASK_POOL = {
    "simple": [
        "bonjour", "merci", "oui", "1+1", "date", "ok", "salut",
        "Capitale de la France?", "2+3*4=?", "Couleur du ciel?",
    ],
    "code": [
        "Ecris une fonction Python qui retourne le max d'une liste",
        "Ecris un decorator Python pour mesurer le temps d'execution",
        "Ecris une classe Python Stack avec push, pop, peek",
        "Ecris un parser CSV en Python sans lib externe",
        "Ecris un rate limiter token bucket en Python",
        "Ecris un serveur HTTP minimal en Python avec GET/POST",
        "Ecris une fonction async Python qui fetch 3 URLs en parallele",
        "Ecris un circuit breaker Python",
    ],
    "reasoning": [
        "Si A>B et B>C, est-ce que A>C? Justifie.",
        "Un train part a 8h a 120km/h, un autre a 9h a 150km/h. Quand le second rattrape le premier?",
        "Analyse le dilemme du prisonnier itere. Quelle strategie domine?",
        "Probabilite de tirer 2 as consecutifs d'un jeu de 52 cartes?",
    ],
    "analysis": [
        "Compare Python vs JavaScript en 5 points",
        "Compare REST vs GraphQL vs gRPC: tableau 5 criteres",
        "Analyse monolithe vs microservices: pro/con",
        "Compare 3 bases de donnees (SQLite, Postgres, MongoDB)",
    ],
    "system": [
        "Quelle commande PowerShell liste les processus?",
        "Comment verifier l'espace disque sur Windows?",
        "Ecris un script de health check pour 5 services en bash",
        "Ecris un script PowerShell qui monitore la VRAM GPU",
    ],
    "classifier": [
        "Classifie cette demande: 'ecris une fonction de tri'",
        "Classifie et route: 'compare React vs Vue pour un dashboard'",
        "Multi-classification: route ces demandes vers les bons agents",
    ],
    "creative": [
        "Ecris un poeme sur la programmation",
        "Invente une histoire de 5 lignes sur un robot",
        "Cree un dialogue entre Python et JavaScript",
        "Ecris un article de blog sur l'IA en 2026",
    ],
    "math": [
        "Calcule la derivee de x^3 + 2x^2 - 5x + 3",
        "Resous l'equation 3x + 7 = 22",
        "Somme des 100 premiers entiers?",
        "Matrice 2x2 [[1,2],[3,4]] - calcule le determinant",
    ],
    "trading": [
        "Analyse technique BTC/USDT: RSI + MACD signals",
        "Compare DCA vs Lump Sum pour crypto sur 1 an",
        "Calcule le risk/reward ratio pour TP 0.4% SL 0.25%",
        "Strategies de risk management pour futures 10x",
    ],
    "security": [
        "Quels sont les 3 risques OWASP les plus critiques?",
        "Audit: cursor.execute(f'SELECT * FROM users WHERE id={user_id}')",
        "Comment implementer JWT refresh tokens de facon securisee?",
        "Ecris un middleware de validation d'input Python anti-injection",
    ],
    "architecture": [
        "Design un systeme de file d'attente distribue",
        "Compare event sourcing vs CRUD classique",
        "Architecture d'un rate limiter distribue pour API gateway",
        "Strategie de migration monolithe vers microservices en 5 etapes",
    ],
    "data": [
        "Ecris une requete SQL pour trouver les doublons dans une table",
        "Compare SQLite WAL vs DELETE journal mode",
        "Ecris un script Python d'ETL: CSV -> nettoyage -> SQLite",
        "Optimise: SELECT * FROM orders WHERE date > '2025-01-01' ORDER BY amount DESC",
    ],
    "devops": [
        "Ecris un Dockerfile multi-stage pour Python FastAPI",
        "Script GitHub Actions pour CI: lint + test + build",
        "Explique GitFlow en 4 points",
        "Compare Docker Compose vs Kubernetes pour un petit cluster",
    ],
    "web": [
        "Recherche les dernieres tendances IA 2026",
        "Quel est le cours du Bitcoin aujourd'hui?",
        "Actualites tech de cette semaine",
    ],
}

# Weight distribution for 1000 cycles
SIZE_WEIGHTS = {
    "simple": 100, "code": 120, "reasoning": 60, "analysis": 80,
    "system": 60, "classifier": 40, "creative": 60, "math": 60,
    "trading": 60, "security": 60, "architecture": 60, "data": 60,
    "devops": 40, "web": 40,
}

def generate_1000_tasks() -> list[tuple[str, str]]:
    pool = []
    for ptype, weight in SIZE_WEIGHTS.items():
        for _ in range(weight):
            pool.append(ptype)
    random.shuffle(pool)
    tasks = []
    for i in range(1000):
        ptype = pool[i % len(pool)]
        prompt = random.choice(TASK_POOL.get(ptype, TASK_POOL["simple"]))
        tasks.append((ptype, prompt))
    return tasks

async def run_benchmark():
    print(f"\n{'='*72}")
    print(f"  JARVIS PATTERN AGENTS BENCHMARK — 1000 CYCLES")
    print(f"  14 Agents | Multi-Strategy | Auto-Dispatch")
    print(f"{'='*72}\n")

    registry = PatternAgentRegistry()
    tasks = generate_1000_tasks()

    results: list[AgentResult] = []
    t_start = time.perf_counter()

    # Run in batches of 40 with semaphore of 8
    batch_size = 40
    sem = asyncio.Semaphore(8)

    async def run_one(ptype, prompt):
        async with sem:
            return await registry.dispatch(ptype, prompt)

    for batch_start in range(0, 1000, batch_size):
        batch = tasks[batch_start:batch_start + batch_size]
        coros = [run_one(pt, p) for pt, p in batch]
        batch_results = await asyncio.gather(*coros)
        results.extend(batch_results)

        done = batch_start + len(batch)
        ok = sum(1 for r in results if r.ok)
        avg_ms = sum(r.latency_ms for r in results if r.ok) / max(ok, 1)
        elapsed = time.perf_counter() - t_start
        rate = done / elapsed
        eta = (1000 - done) / max(0.01, rate)

        # Print every result in batch
        for i, r in enumerate(batch_results):
            idx = batch_start + i + 1
            status = "OK" if r.ok else "FAIL"
            print(f"  [{idx:4d}/1000] {r.pattern:14s} {r.strategy:24s} {r.node:12s} {r.latency_ms:7.0f}ms {r.tokens:4d}tok Q={r.quality_score:.2f} {status}")

        print(f"  --- batch {done}/1000 | {ok} OK | avg {avg_ms:.0f}ms | {rate:.1f} req/s | ETA {eta:.0f}s ---")

    total_time = time.perf_counter() - t_start
    ok_results = [r for r in results if r.ok]

    # ── Analysis ────────────────────────────────────
    print(f"\n{'='*72}")
    print(f"  RESULTATS: {len(ok_results)}/1000 OK ({100*len(ok_results)/1000:.1f}%)")
    print(f"  Duree: {total_time:.1f}s | Throughput: {1000/total_time:.1f} req/s")
    print(f"{'='*72}")

    # By pattern
    print(f"\n--- Par Pattern Agent ---")
    from collections import defaultdict
    by_pat = defaultdict(list)
    for r in results:
        by_pat[r.pattern].append(r)

    print(f"{'Pattern':<16} {'OK':>4} {'Total':>5} {'Rate':>6} {'Avg ms':>8} {'Avg Q':>6} {'Avg tok':>8}")
    pat_stats = {}
    for pat in sorted(by_pat.keys()):
        rs = by_pat[pat]
        oks = [r for r in rs if r.ok]
        rate = len(oks) / max(1, len(rs))
        avg_ms = sum(r.latency_ms for r in oks) / max(1, len(oks))
        avg_q = sum(r.quality_score for r in oks) / max(1, len(oks))
        avg_tok = sum(r.tokens for r in oks) / max(1, len(oks))
        print(f"{pat:<16} {len(oks):>4} {len(rs):>5} {100*rate:>5.1f}% {avg_ms:>8.0f} {avg_q:>6.2f} {avg_tok:>8.0f}")
        pat_stats[pat] = {"ok": len(oks), "total": len(rs), "rate": rate, "avg_ms": avg_ms, "avg_q": avg_q}

    # By strategy
    print(f"\n--- Par Strategie ---")
    by_strat = defaultdict(list)
    for r in results:
        base_strat = r.strategy.split(":")[0]
        by_strat[base_strat].append(r)

    for strat in sorted(by_strat.keys()):
        rs = by_strat[strat]
        oks = [r for r in rs if r.ok]
        avg_ms = sum(r.latency_ms for r in oks) / max(1, len(oks))
        print(f"  {strat:<24} {len(oks):>4}/{len(rs):>4} ({100*len(oks)/max(1,len(rs)):>5.1f}%) avg={avg_ms:>7.0f}ms")

    # By node
    print(f"\n--- Par Noeud ---")
    by_node = defaultdict(list)
    for r in ok_results:
        by_node[r.node].append(r)
    for node in sorted(by_node.keys(), key=lambda n: -len(by_node[n])):
        rs = by_node[node]
        avg_ms = sum(r.latency_ms for r in rs) / len(rs)
        avg_q = sum(r.quality_score for r in rs) / len(rs)
        print(f"  {node:<16} {len(rs):>4} reqs  avg={avg_ms:>7.0f}ms  Q={avg_q:.2f}")

    # Best node per pattern
    print(f"\n--- Meilleur Noeud par Pattern ---")
    for pat in sorted(by_pat.keys()):
        pat_by_node = defaultdict(list)
        for r in by_pat[pat]:
            if r.ok:
                pat_by_node[r.node].append(r)
        if pat_by_node:
            best_node = min(pat_by_node.keys(), key=lambda n: sum(r.latency_ms for r in pat_by_node[n]) / len(pat_by_node[n]))
            avg = sum(r.latency_ms for r in pat_by_node[best_node]) / len(pat_by_node[best_node])
            print(f"  {pat:<16} -> {best_node:<12} ({avg:.0f}ms, {len(pat_by_node[best_node])} reqs)")

    # Save report
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": 1000,
        "ok": len(ok_results),
        "rate": f"{100*len(ok_results)/1000:.1f}%",
        "duration_s": round(total_time, 1),
        "throughput_rps": round(1000 / total_time, 2),
        "by_pattern": pat_stats,
        "results": [
            {"pattern": r.pattern, "node": r.node, "strategy": r.strategy,
             "ms": round(r.latency_ms), "tokens": r.tokens, "quality": r.quality_score, "ok": r.ok}
            for r in results
        ],
    }
    report_path = PROJECT_ROOT / "data" / "benchmark_pattern_agents_1000.json"
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nRapport: {report_path}")

    await registry.close()
    return report

if __name__ == "__main__":
    asyncio.run(run_benchmark())
