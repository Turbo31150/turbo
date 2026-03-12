#!/usr/bin/env python3
"""JARVIS Pattern Dispatch Benchmark — Multi-scenario distribution testing.

Tests 6 agent patterns x 4 nodes x 5 strategies with escalating task complexity.
Saves every result to etoile.db (agent_dispatch_log table).
"""
import asyncio
import httpx
import json
import sqlite3
import time
import sys
from datetime import datetime

# ============================================================
# NODES
# ============================================================
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
}

# ============================================================
# PATTERNS & TASKS (6 patterns x 5 sizes = 30 tasks)
# ============================================================
PATTERNS = {
    "simple": {
        "agent": "quick-dispatch",
        "tasks": [
            ("S1", "micro", "Bonjour JARVIS"),
            ("S2", "micro", "Quelle heure est-il?"),
            ("S3", "small", "Donne moi la capitale de la France, de l'Allemagne et du Japon"),
            ("S4", "medium", "Explique en 3 phrases la difference entre TCP et UDP"),
            ("S5", "large", "Liste les 10 langages de programmation les plus populaires en 2025 avec un mot sur chacun"),
        ],
    },
    "code": {
        "agent": "code-champion",
        "tasks": [
            ("C1", "micro", "Ecris une fonction Python qui retourne le max d'une liste"),
            ("C2", "small", "Ecris un decorator Python qui mesure le temps d'execution d'une fonction"),
            ("C3", "medium", "Ecris une classe Python AsyncHTTPClient avec retry exponentiel et timeout configurable"),
            ("C4", "large", "Ecris un parser JSON streaming en Python qui traite des fichiers de plus de 1GB sans charger tout en memoire"),
            ("C5", "xl", "Ecris un mini framework de test unitaire en Python avec assertions, fixtures, et rapport HTML"),
        ],
    },
    "reasoning": {
        "agent": "deep-reasoning",
        "tasks": [
            ("R1", "micro", "Si A>B et B>C, est-ce que A>C? Justifie."),
            ("R2", "small", "Un train part a 8h a 120km/h, un autre a 9h a 150km/h. Quand le second rattrape le premier?"),
            ("R3", "medium", "Compare 3 strategies d'investissement: DCA, lump sum, et value averaging. Laquelle est optimale pour un horizon 5 ans?"),
            ("R4", "large", "Analyse le dilemme du prisonnier itere. Quelle strategie domine a long terme et pourquoi?"),
            ("R5", "xl", "Decompose le probleme des 8 reines en etapes logiques. Montre l'arbre de decision pour les 3 premieres colonnes."),
        ],
    },
    "analysis": {
        "agent": "analysis-engine",
        "tasks": [
            ("A1", "micro", "Compare Python vs JavaScript en 3 points"),
            ("A2", "small", "Analyse les avantages et inconvenients de SQLite vs PostgreSQL pour un projet local"),
            ("A3", "medium", "Compare REST vs GraphQL vs gRPC: performance, complexite, cas d'usage. Tableau structure."),
            ("A4", "large", "Audit d'architecture: monolithe vs microservices vs serverless. Pro/con, metriques, recommandation pour une startup."),
            ("A5", "xl", "Analyse comparative complete de 5 frameworks frontend (React, Vue, Svelte, Angular, Solid) avec scores sur 10 criteres."),
        ],
    },
    "system": {
        "agent": "system-ops",
        "tasks": [
            ("Y1", "micro", "Quelle commande PowerShell liste les processus?"),
            ("Y2", "small", "Comment verifier l'espace disque disponible sur Windows avec PowerShell?"),
            ("Y3", "medium", "Ecris un script PowerShell qui monitore la VRAM GPU toutes les 5 secondes et alerte si >90%"),
            ("Y4", "large", "Ecris un script complet de backup incremental avec rotation 7 jours, compression, et log"),
            ("Y5", "xl", "Ecris un healthcheck complet du cluster JARVIS: ping 4 noeuds, GPU temp, VRAM, services, DB integrity, rapport JSON"),
        ],
    },
    "classifier": {
        "agent": "task-router",
        "tasks": [
            ("T1", "micro", "Classifie cette demande: 'ecris une fonction de tri'"),
            ("T2", "small", "Classifie et route: 'compare React vs Vue pour un dashboard'"),
            ("T3", "medium", "Classifie cette demande complexe: 'analyse le code du fichier main.py, trouve les bugs, et propose une architecture microservices'"),
            ("T4", "large", "Multi-classification: route ces 5 demandes vers les bons agents: 1)bonjour 2)ecris un sort 3)compare A vs B 4)check GPU 5)calcul probabilite"),
            ("T5", "xl", "Cree un plan de routing pour 10 types de taches differentes avec fallbacks, poids, et strategies optimales"),
        ],
    },
}

# ============================================================
# STRATEGIES
# ============================================================

async def call_node(client: httpx.AsyncClient, node_name: str, prompt: str) -> dict:
    """Call a single node and return result dict."""
    node = NODES[node_name]
    t0 = time.time()
    try:
        if node["type"] == "lmstudio":
            body = {
                "model": node["model"],
                "input": f"{node.get('prefix','')}{prompt}",
                "temperature": 0.3,
                "max_output_tokens": node.get("max_tokens", 1024),
                "stream": False,
                "store": False,
            }
            r = await client.post(node["url"], json=body, timeout=60)
            data = r.json()
            content = ""
            for o in data.get("output", []):
                if o.get("type") == "message":
                    c = o.get("content", "")
                    if isinstance(c, list):
                        content = c[0].get("text", "") if c else ""
                    else:
                        content = str(c)
            latency = (time.time() - t0) * 1000
            tokens = len(content.split())
            return {"node": node_name, "content": content, "latency_ms": latency, "tokens": tokens, "ok": True}
        else:  # ollama
            body = {
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
            }
            r = await client.post(node["url"], json=body, timeout=60)
            data = r.json()
            content = data.get("message", {}).get("content", "")
            latency = (time.time() - t0) * 1000
            tokens = len(content.split())
            return {"node": node_name, "content": content, "latency_ms": latency, "tokens": tokens, "ok": True}
    except Exception as e:
        return {"node": node_name, "content": "", "latency_ms": (time.time() - t0) * 1000, "tokens": 0, "ok": False, "error": str(e)[:200]}


# Pattern -> best node mapping
PATTERN_NODE_MAP = {
    "simple": "OL1",
    "code": "M1",
    "reasoning": "M2",
    "analysis": "M1",
    "system": "M1",
    "classifier": "M1",
}

ROUND_ROBIN_STATE = {"idx": 0}
NODE_LIST = list(NODES.keys())


async def strategy_single(client, pattern_type, prompt):
    """Route to the best node for this pattern."""
    node = PATTERN_NODE_MAP.get(pattern_type, "M1")
    return await call_node(client, node, prompt)


async def strategy_race(client, pattern_type, prompt):
    """Send to ALL nodes in parallel, take the fastest successful response."""
    tasks = [call_node(client, n, prompt) for n in NODES]
    results = await asyncio.gather(*tasks)
    ok_results = [r for r in results if r["ok"] and r["content"]]
    if ok_results:
        best = min(ok_results, key=lambda x: x["latency_ms"])
        best["strategy_detail"] = f"race_winner={best['node']}"
        return best
    return results[0] if results else {"ok": False, "error": "all_failed"}


async def strategy_round_robin(client, pattern_type, prompt):
    """Rotate through nodes sequentially."""
    idx = ROUND_ROBIN_STATE["idx"] % len(NODE_LIST)
    ROUND_ROBIN_STATE["idx"] += 1
    node = NODE_LIST[idx]
    return await call_node(client, node, prompt)


async def strategy_category(client, pattern_type, prompt):
    """Use pattern-specific routing with quality fallback."""
    node = PATTERN_NODE_MAP.get(pattern_type, "M1")
    result = await call_node(client, node, prompt)
    if result["ok"] and result["content"]:
        return result
    # Fallback
    for fb in ["M1", "M2", "M3", "OL1"]:
        if fb != node:
            result = await call_node(client, fb, prompt)
            if result["ok"] and result["content"]:
                result["strategy_detail"] = f"fallback_from={node}_to={fb}"
                return result
    return result


async def strategy_consensus(client, pattern_type, prompt):
    """Send to top 2 nodes, weighted vote."""
    primary = PATTERN_NODE_MAP.get(pattern_type, "M1")
    secondary = "M2" if primary != "M2" else "M1"
    r1, r2 = await asyncio.gather(
        call_node(client, primary, prompt),
        call_node(client, secondary, prompt),
    )
    w1 = NODES[primary]["weight"]
    w2 = NODES[secondary]["weight"]
    if r1["ok"] and r2["ok"]:
        winner = r1 if w1 >= w2 else r2
        winner["strategy_detail"] = f"consensus_{primary}({w1})_vs_{secondary}({w2})"
        return winner
    return r1 if r1["ok"] else r2


STRATEGIES = {
    "single": strategy_single,
    "race": strategy_race,
    "round_robin": strategy_round_robin,
    "category": strategy_category,
    "consensus": strategy_consensus,
}

# ============================================================
# MAIN BENCHMARK
# ============================================================

async def run_benchmark(quick=False):
    db = sqlite3.connect("/home/turbo/jarvis-m1-ops/etoile.db")
    cursor = db.cursor()

    results = []
    total = 0
    ok_count = 0

    strat_list = ["single", "category"] if quick else list(STRATEGIES.keys())
    pattern_list = list(PATTERNS.keys())

    print(f"\n{'='*70}")
    print(f"JARVIS PATTERN DISPATCH BENCHMARK")
    print(f"Patterns: {len(pattern_list)} | Strategies: {len(strat_list)} | Nodes: {len(NODES)}")
    print(f"{'='*70}\n")

    async with httpx.AsyncClient() as client:
        for strat_name in strat_list:
            strat_fn = STRATEGIES[strat_name]
            print(f"\n--- Strategy: {strat_name.upper()} ---")

            for pat_type, pat_data in PATTERNS.items():
                agent_id = pat_data["agent"]
                tasks = pat_data["tasks"][:3] if quick else pat_data["tasks"]

                for task_id, size, prompt in tasks:
                    total += 1
                    print(f"  [{task_id}] {pat_type:12s} {size:6s} -> {strat_name:12s} ... ", end="", flush=True)

                    result = await strat_fn(client, pat_type, prompt)

                    if result.get("ok") and result.get("content"):
                        ok_count += 1
                        status = "OK"
                        preview = result["content"][:60].replace("\n", " ")
                        print(f"{result['latency_ms']:7.0f}ms {result['node']:4s} {result.get('tokens',0):4d}tok | {preview}")
                    else:
                        status = "FAIL"
                        err = result.get("error", "empty")[:40]
                        print(f"FAIL | {err}")

                    # Save to SQLite
                    cursor.execute("""INSERT INTO agent_dispatch_log
                        (request_text, classified_type, agent_id, model_used, node, strategy,
                         latency_ms, tokens_in, tokens_out, success, error_msg, quality_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (prompt[:500], pat_type, agent_id,
                         NODES.get(result.get("node","M1"),{}).get("model","?"),
                         result.get("node","?"), strat_name,
                         result.get("latency_ms",0),
                         len(prompt.split()), result.get("tokens",0),
                         1 if result.get("ok") else 0,
                         result.get("error","")[:200] if not result.get("ok") else None,
                         min(1.0, result.get("tokens",0) / max(1, len(prompt.split()) * 3))
                        ))

                    results.append({
                        "task": task_id, "pattern": pat_type, "agent": agent_id,
                        "strategy": strat_name, "node": result.get("node","?"),
                        "latency_ms": result.get("latency_ms",0),
                        "tokens": result.get("tokens",0),
                        "ok": result.get("ok", False),
                    })

            db.commit()

    # ============================================================
    # ANALYSIS
    # ============================================================
    print(f"\n{'='*70}")
    print(f"RESULTATS: {ok_count}/{total} OK ({100*ok_count/max(1,total):.0f}%)")
    print(f"{'='*70}")

    # By strategy
    print(f"\n--- Par Strategie ---")
    for s in strat_list:
        sr = [r for r in results if r["strategy"] == s]
        ok = sum(1 for r in sr if r["ok"])
        avg_lat = sum(r["latency_ms"] for r in sr) / max(1, len(sr))
        avg_tok = sum(r["tokens"] for r in sr) / max(1, len(sr))
        print(f"  {s:15s} {ok}/{len(sr)} OK  avg={avg_lat:7.0f}ms  avg_tok={avg_tok:.0f}")

    # By pattern
    print(f"\n--- Par Pattern ---")
    for p in pattern_list:
        pr = [r for r in results if r["pattern"] == p]
        ok = sum(1 for r in pr if r["ok"])
        avg_lat = sum(r["latency_ms"] for r in pr) / max(1, len(pr))
        print(f"  {p:15s} {ok}/{len(pr)} OK  avg={avg_lat:7.0f}ms  agent={PATTERNS[p]['agent']}")

    # By node
    print(f"\n--- Par Noeud ---")
    for n in NODES:
        nr = [r for r in results if r["node"] == n]
        if nr:
            ok = sum(1 for r in nr if r["ok"])
            avg_lat = sum(r["latency_ms"] for r in nr) / max(1, len(nr))
            print(f"  {n:5s} {ok}/{len(nr)} OK  avg={avg_lat:7.0f}ms")

    # Best strategy per pattern
    print(f"\n--- Meilleure Strategie par Pattern ---")
    for p in pattern_list:
        best_strat = None
        best_lat = float("inf")
        for s in strat_list:
            sr = [r for r in results if r["pattern"] == p and r["strategy"] == s and r["ok"]]
            if sr:
                avg = sum(r["latency_ms"] for r in sr) / len(sr)
                if avg < best_lat:
                    best_lat = avg
                    best_strat = s
        if best_strat:
            print(f"  {p:15s} -> {best_strat:12s} ({best_lat:.0f}ms)")

    # Update pattern stats in agent_patterns
    for p in pattern_list:
        pr = [r for r in results if r["pattern"] == p and r["ok"]]
        if pr:
            avg_lat = sum(r["latency_ms"] for r in pr) / len(pr)
            success_rate = len(pr) / max(1, len([r for r in results if r["pattern"] == p]))
            cursor.execute("""UPDATE agent_patterns SET
                avg_latency_ms=?, success_rate=?, total_calls=total_calls+?, updated_at=?
                WHERE pattern_type=?""",
                (avg_lat, success_rate, len(pr), datetime.now().isoformat(), p))
    db.commit()

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": total, "ok": ok_count, "rate": f"{100*ok_count/max(1,total):.0f}%",
        "results": results,
    }
    with open("/home/turbo/jarvis-m1-ops/data/pattern_dispatch_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nRapport sauve: data/pattern_dispatch_report.json")
    print(f"Logs SQL: {total} entrees dans agent_dispatch_log")

    db.close()
    return results


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    asyncio.run(run_benchmark(quick=quick))
