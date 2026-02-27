"""
MEGA BENCHMARK JARVIS HEXA_CORE — 2026-02-26
==============================================
Benchmark methodologique complet de tous les noeuds IA.
10 phases, scores ponderes, rapport detaille.

Usage: python scripts/mega_benchmark.py
"""
import asyncio
import httpx
import json
import time
import sys
import io
import subprocess
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

NODES = {
    "M1": {
        "url": "http://10.5.0.2:1234/api/v1/chat",
        "model": "qwen3-8b",
        "auth": "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
        "type": "lmstudio",
        "prefix": "/nothink\n",
        "weight": 1.8,
        "max_tokens": 1024,
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "model": "deepseek-coder-v2-lite-instruct",
        "auth": "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4",
        "type": "lmstudio",
        "prefix": "",
        "weight": 1.4,
        "max_tokens": 512,
    },
    "M3": {
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "model": "mistral-7b-instruct-v0.3",
        "auth": "Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux",
        "type": "lmstudio",
        "prefix": "",
        "weight": 1.0,
        "max_tokens": 512,
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b",
        "type": "ollama",
        "prefix": "/nothink\n",
        "weight": 1.3,
        "max_tokens": 512,
    },
}

TIMEOUT = 30  # seconds per query
KEYWORDS_PARTIAL = 0.5  # partial keyword match score


@dataclass
class TestResult:
    node: str
    phase: str
    task: str
    success: bool
    latency_ms: int
    output: str = ""
    score: float = 0.0
    keywords_found: list = field(default_factory=list)
    keywords_missed: list = field(default_factory=list)
    error: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

async def query_lmstudio(client: httpx.AsyncClient, node: str, prompt: str) -> tuple[str, int]:
    """Query LM Studio node, return (response_text, latency_ms)."""
    cfg = NODES[node]
    body = {
        "model": cfg["model"],
        "input": cfg["prefix"] + prompt,
        "temperature": 0.2,
        "max_output_tokens": cfg["max_tokens"],
        "stream": False,
        "store": False,
    }
    headers = {"Content-Type": "application/json", "Authorization": cfg["auth"]}

    t0 = time.perf_counter()
    resp = await client.post(cfg["url"], json=body, headers=headers, timeout=TIMEOUT)
    latency = int((time.perf_counter() - t0) * 1000)

    data = resp.json()
    if "error" in data:
        raise Exception(data["error"].get("message", str(data["error"])))

    # Extract text from output array
    output = data.get("output", [])
    for item in reversed(output):
        if item.get("type") == "message":
            content = item.get("content", "")
            if isinstance(content, list):
                return content[0].get("text", ""), latency
            elif isinstance(content, str):
                return content, latency
    return str(output)[:500], latency


async def query_ollama(client: httpx.AsyncClient, node: str, prompt: str) -> tuple[str, int]:
    """Query Ollama node, return (response_text, latency_ms)."""
    cfg = NODES[node]
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": cfg["prefix"] + prompt}],
        "stream": False,
    }

    t0 = time.perf_counter()
    resp = await client.post(cfg["url"], json=body, timeout=TIMEOUT)
    latency = int((time.perf_counter() - t0) * 1000)

    data = resp.json()
    content = data.get("message", {}).get("content", "")
    # Remove thinking tags
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
    return content, latency


async def query_node(client: httpx.AsyncClient, node: str, prompt: str) -> tuple[str, int]:
    """Route to correct query function."""
    cfg = NODES[node]
    if cfg["type"] == "ollama":
        return await query_ollama(client, node, prompt)
    else:
        return await query_lmstudio(client, node, prompt)


async def test_node(client: httpx.AsyncClient, node: str, phase: str, task: str,
                    prompt: str, keywords: list[str]) -> TestResult:
    """Run a single test on a node."""
    try:
        text, latency = await query_node(client, node, prompt)
        text_lower = text.lower()

        found = [k for k in keywords if k.lower() in text_lower]
        missed = [k for k in keywords if k.lower() not in text_lower]

        if len(keywords) > 0:
            score = len(found) / len(keywords)
        else:
            score = 1.0 if len(text) > 10 else 0.0

        return TestResult(
            node=node, phase=phase, task=task, success=True,
            latency_ms=latency, output=text[:500], score=score,
            keywords_found=found, keywords_missed=missed,
        )
    except Exception as e:
        return TestResult(
            node=node, phase=phase, task=task, success=False,
            latency_ms=0, error=str(e)[:200], score=0.0,
        )


# ══════════════════════════════════════════════════════════════════════════════
# BENCHMARK PHASES
# ══════════════════════════════════════════════════════════════════════════════

PHASES = [
    # Phase 1: LATENCE — Reponse minimale
    {
        "name": "1. Latence Pure",
        "description": "Temps de reponse minimal (ping IA)",
        "tasks": [
            {"task": "ping", "prompt": "Reponds juste: OK", "keywords": ["ok"]},
            {"task": "echo", "prompt": "Repete exactement: JARVIS ONLINE", "keywords": ["jarvis", "online"]},
        ],
    },
    # Phase 2: CODE PYTHON — Generation
    {
        "name": "2. Code Python",
        "description": "Generation de code Python fonctionnel",
        "tasks": [
            {
                "task": "fibonacci",
                "prompt": "Ecris une fonction Python fibonacci(n) qui retourne le n-ieme nombre de Fibonacci. Code seulement, pas d'explication.",
                "keywords": ["def", "fibonacci", "return"],
            },
            {
                "task": "tri_rapide",
                "prompt": "Ecris une fonction Python quicksort(arr) qui trie une liste. Code seulement.",
                "keywords": ["def", "quicksort", "pivot", "return"],
            },
            {
                "task": "api_async",
                "prompt": "Ecris une fonction Python async fetch_urls(urls) qui telecharge plusieurs URLs en parallele avec httpx. Code seulement.",
                "keywords": ["async", "httpx", "await", "gather"],
            },
        ],
    },
    # Phase 3: CODE JAVASCRIPT
    {
        "name": "3. Code JavaScript",
        "description": "Generation de code JS/TS",
        "tasks": [
            {
                "task": "debounce",
                "prompt": "Ecris une fonction JavaScript debounce(fn, delay) qui retourne une version debounced. Code seulement.",
                "keywords": ["function", "timeout", "clearTimeout", "setTimeout"],
            },
            {
                "task": "fetch_api",
                "prompt": "Ecris une fonction JavaScript async fetchWithRetry(url, maxRetries) qui fetch une URL avec retry. Code seulement.",
                "keywords": ["async", "fetch", "retry", "await", "catch"],
            },
        ],
    },
    # Phase 4: RAISONNEMENT LOGIQUE
    {
        "name": "4. Raisonnement Logique",
        "description": "Problemes de logique et deduction",
        "tasks": [
            {
                "task": "logique_1",
                "prompt": "Si tous les chats sont des animaux, et certains animaux sont noirs, peut-on conclure que certains chats sont noirs ? Reponds Oui ou Non et explique en 1 phrase.",
                "keywords": ["non"],
            },
            {
                "task": "logique_2",
                "prompt": "Un escargot monte un mur de 10m. Chaque jour il monte 3m et chaque nuit il glisse de 2m. Combien de jours pour atteindre le sommet? Reponds avec le nombre.",
                "keywords": ["8"],
            },
            {
                "task": "logique_3",
                "prompt": "Dans une course, tu depasses le 2eme. Quelle est ta position maintenant? Reponds avec un chiffre.",
                "keywords": ["2"],
            },
        ],
    },
    # Phase 5: MATHEMATIQUES
    {
        "name": "5. Mathematiques",
        "description": "Calculs et raisonnement mathematique",
        "tasks": [
            {
                "task": "calcul_1",
                "prompt": "Calcule: 17 * 23 + 45 - 12 * 3. Donne juste le resultat numerique.",
                "keywords": ["400"],
            },
            {
                "task": "calcul_2",
                "prompt": "Quelle est la derivee de f(x) = 3x^2 + 2x - 5 ? Reponds sous forme mathematique.",
                "keywords": ["6x", "2"],
            },
            {
                "task": "stats",
                "prompt": "Calcule la moyenne et la mediane de: 12, 7, 3, 14, 9, 6, 11. Donne les deux valeurs.",
                "keywords": ["8", "9"],
            },
        ],
    },
    # Phase 6: ANALYSE TRADING
    {
        "name": "6. Analyse Trading",
        "description": "Interpretation de signaux trading",
        "tasks": [
            {
                "task": "signal_rsi",
                "prompt": "RSI a 78, MACD bearish crossover, prix au-dessus de la BB superieure. Quel signal donnes-tu ? Reponds: LONG, SHORT ou NEUTRE, et explique en 1 phrase.",
                "keywords": ["short"],
            },
            {
                "task": "risk_calc",
                "prompt": "Position 100 USDT, levier 10x, entry 50000$, stop-loss 49500$. Quel est le pourcentage de perte sur le capital? Reponds avec le pourcentage.",
                "keywords": ["10"],
            },
        ],
    },
    # Phase 7: COMPREHENSION SYSTEME
    {
        "name": "7. Comprehension Systeme",
        "description": "Questions sur Windows, reseau, GPU",
        "tasks": [
            {
                "task": "powershell",
                "prompt": "Ecris la commande PowerShell pour lister tous les processus qui utilisent plus de 500MB de RAM, triés par memoire decroissante.",
                "keywords": ["get-process", "sort", "memory", "descending"],
            },
            {
                "task": "reseau",
                "prompt": "Quelle commande Windows permet de voir toutes les connexions TCP actives avec le PID du processus? Donne la commande exacte.",
                "keywords": ["netstat", "-ano"],
            },
            {
                "task": "gpu_cuda",
                "prompt": "Explique en 2 phrases la difference entre CUDA cores et Tensor cores sur un GPU NVIDIA.",
                "keywords": ["cuda", "tensor", "matrix", "parallel"],
            },
        ],
    },
    # Phase 8: ARCHITECTURE IA
    {
        "name": "8. Architecture IA",
        "description": "Questions sur l'architecture de systemes IA",
        "tasks": [
            {
                "task": "mcp_protocol",
                "prompt": "Explique en 3 phrases ce qu'est le Model Context Protocol (MCP) d'Anthropic et son utilite.",
                "keywords": ["tool", "server", "client", "protocol"],
            },
            {
                "task": "consensus",
                "prompt": "Dans un systeme multi-agents IA, comment implementer un consensus pondere? Decris l'algorithme en 3 etapes.",
                "keywords": ["poids", "vote", "score", "agr"],
            },
        ],
    },
    # Phase 9: GENERATION LONGUE
    {
        "name": "9. Generation Longue",
        "description": "Capacite a generer du contenu structure",
        "tasks": [
            {
                "task": "plan_projet",
                "prompt": "Cree un plan de projet en 5 etapes pour deployer un orchestrateur IA distribue sur 3 machines. Format: 1. Titre - Description (1 ligne par etape).",
                "keywords": ["1.", "2.", "3.", "4.", "5."],
            },
        ],
    },
    # Phase 10: MULTILINGUAL + EDGE CASES
    {
        "name": "10. Multilingual & Edge Cases",
        "description": "Francais, anglais, edge cases",
        "tasks": [
            {
                "task": "francais",
                "prompt": "Traduis en anglais: 'L'orchestrateur distribue les taches sur le cluster GPU'",
                "keywords": ["orchestrator", "distribut", "task", "gpu", "cluster"],
            },
            {
                "task": "json_output",
                "prompt": 'Genere un JSON valide avec les champs: name, score (number), status (string). Exemple pour un noeud IA nomme M1 avec score 95.',
                "keywords": ['"name"', '"score"', '"status"', "m1", "95"],
            },
            {
                "task": "refusal",
                "prompt": "Reponds a cette question impossible: Quelle est la couleur du nombre 7? Dis que c'est impossible a determiner.",
                "keywords": ["impossible", "pas", "couleur"],
            },
        ],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# BENCHMARK RUNNER
# ══════════════════════════════════════════════════════════════════════════════

async def run_benchmark():
    print("=" * 80)
    print(f"  MEGA BENCHMARK JARVIS HEXA_CORE — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Noeuds: {', '.join(NODES.keys())} | Phases: {len(PHASES)} | Timeout: {TIMEOUT}s")
    print("=" * 80)

    all_results: list[TestResult] = []
    node_scores: dict[str, list[float]] = {n: [] for n in NODES}
    node_latencies: dict[str, list[int]] = {n: [] for n in NODES}
    phase_scores: dict[str, dict[str, float]] = {}

    async with httpx.AsyncClient() as client:
        for phase_idx, phase in enumerate(PHASES):
            phase_name = phase["name"]
            print(f"\n{'─' * 80}")
            print(f"  PHASE {phase_name}")
            print(f"  {phase['description']}")
            print(f"{'─' * 80}")

            phase_results = {n: [] for n in NODES}

            for task_def in phase["tasks"]:
                task_name = task_def["task"]
                prompt = task_def["prompt"]
                keywords = task_def["keywords"]

                print(f"\n  [{task_name}] {prompt[:70]}...")
                print(f"  Keywords: {keywords}")

                # Run all nodes in parallel
                tasks = {
                    node: test_node(client, node, phase_name, task_name, prompt, keywords)
                    for node in NODES
                }
                results = await asyncio.gather(*tasks.values(), return_exceptions=True)

                for node, result in zip(tasks.keys(), results):
                    if isinstance(result, Exception):
                        result = TestResult(
                            node=node, phase=phase_name, task=task_name,
                            success=False, latency_ms=0, error=str(result)[:200],
                        )

                    all_results.append(result)
                    phase_results[node].append(result)

                    if result.success:
                        node_scores[node].append(result.score)
                        node_latencies[node].append(result.latency_ms)

                    status = "OK" if result.success else "FAIL"
                    score_str = f"{result.score:.0%}" if result.success else "ERR"
                    latency_str = f"{result.latency_ms}ms" if result.success else "---"
                    found_str = f"[{len(result.keywords_found)}/{len(result.keywords_found)+len(result.keywords_missed)}]"

                    output_preview = result.output[:80].replace("\n", " ") if result.output else result.error[:80]
                    print(f"    {node:4s} | {status} | {score_str:>4s} | {latency_str:>7s} | {found_str} | {output_preview}")

            # Phase summary
            phase_scores[phase_name] = {}
            for node in NODES:
                results_list = phase_results[node]
                if results_list:
                    successes = [r for r in results_list if r.success]
                    if successes:
                        avg_score = sum(r.score for r in successes) / len(successes)
                        avg_lat = sum(r.latency_ms for r in successes) / len(successes)
                        phase_scores[phase_name][node] = avg_score
                        print(f"  >> {node}: {avg_score:.0%} avg score, {avg_lat:.0f}ms avg latency ({len(successes)}/{len(results_list)} success)")
                    else:
                        phase_scores[phase_name][node] = 0.0
                        print(f"  >> {node}: FAIL (0/{len(results_list)} success)")

    # ══════════════════════════════════════════════════════════════════════════
    # FINAL REPORT
    # ══════════════════════════════════════════════════════════════════════════

    print("\n" + "=" * 80)
    print("  RAPPORT FINAL — MEGA BENCHMARK")
    print("=" * 80)

    # Per-node summary
    print("\n┌─────────┬────────┬──────────┬──────────┬──────────┬──────────┐")
    print("│ Noeud   │ Score  │ Latence  │ Success  │ Poids    │ Grade    │")
    print("├─────────┼────────┼──────────┼──────────┼──────────┼──────────┤")

    node_final = {}
    for node in NODES:
        scores = node_scores[node]
        lats = node_latencies[node]
        if scores:
            avg_score = sum(scores) / len(scores)
            avg_lat = sum(lats) / len(lats)
            success_rate = len(scores) / sum(1 for r in all_results if r.node == node)
            grade = "A+" if avg_score >= 0.9 else "A" if avg_score >= 0.8 else "B" if avg_score >= 0.65 else "C" if avg_score >= 0.5 else "D" if avg_score >= 0.3 else "F"
            node_final[node] = {"score": avg_score, "latency": avg_lat, "success": success_rate, "grade": grade}
            print(f"│ {node:7s} │ {avg_score:5.1%} │ {avg_lat:6.0f}ms │ {success_rate:7.1%} │ {NODES[node]['weight']:8.1f} │ {grade:8s} │")
        else:
            node_final[node] = {"score": 0, "latency": 0, "success": 0, "grade": "F"}
            print(f"│ {node:7s} │   0.0% │     ---  │    0.0%  │ {NODES[node]['weight']:8.1f} │ F        │")

    print("└─────────┴────────┴──────────┴──────────┴──────────┴──────────┘")

    # Phase breakdown
    print("\n  SCORES PAR PHASE:")
    print("  " + "─" * 76)
    header = f"  {'Phase':<30s}"
    for node in NODES:
        header += f" │ {node:>5s}"
    print(header)
    print("  " + "─" * 76)

    for phase_name in [p["name"] for p in PHASES]:
        row = f"  {phase_name:<30s}"
        for node in NODES:
            s = phase_scores.get(phase_name, {}).get(node, 0)
            row += f" │ {s:4.0%} "
        print(row)

    # Best node per phase
    print("\n  MEILLEUR NOEUD PAR PHASE:")
    for phase_name in [p["name"] for p in PHASES]:
        scores = phase_scores.get(phase_name, {})
        if scores:
            best = max(scores, key=scores.get)
            print(f"    {phase_name:<30s} → {best} ({scores[best]:.0%})")

    # Weighted final score
    print("\n  SCORE FINAL PONDERE (score * poids_consensus):")
    weighted = []
    for node in NODES:
        nf = node_final[node]
        ws = nf["score"] * NODES[node]["weight"]
        weighted.append((node, ws, nf["score"], NODES[node]["weight"]))
        print(f"    {node}: {nf['score']:.1%} * {NODES[node]['weight']} = {ws:.2f}")

    weighted.sort(key=lambda x: -x[1])
    print(f"\n  CLASSEMENT FINAL:")
    for i, (node, ws, score, weight) in enumerate(weighted, 1):
        medal = ["🥇", "🥈", "🥉", "  "][min(i-1, 3)]
        grade = node_final[node]["grade"]
        lat = node_final[node]["latency"]
        print(f"    {medal} #{i} {node} — Grade {grade}, Score {score:.1%}, Latence {lat:.0f}ms, Pondere {ws:.2f}")

    # Total stats
    total_tests = len(all_results)
    total_success = sum(1 for r in all_results if r.success)
    total_fail = total_tests - total_success
    avg_latency = sum(r.latency_ms for r in all_results if r.success) / max(total_success, 1)

    print(f"\n  STATISTIQUES GLOBALES:")
    print(f"    Tests: {total_tests} | Succes: {total_success} | Echecs: {total_fail}")
    print(f"    Taux de succes: {total_success/total_tests:.1%}")
    print(f"    Latence moyenne: {avg_latency:.0f}ms")
    print(f"    Duree totale: {sum(r.latency_ms for r in all_results)/1000:.1f}s")

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "nodes": {n: node_final[n] for n in NODES},
        "phases": {p: {n: s for n, s in scores.items()} for p, scores in phase_scores.items()},
        "ranking": [{"rank": i+1, "node": n, "weighted_score": ws, "score": s, "weight": w} for i, (n, ws, s, w) in enumerate(weighted)],
        "stats": {"total": total_tests, "success": total_success, "fail": total_fail, "avg_latency_ms": int(avg_latency)},
    }

    report_path = f"data/mega_benchmark_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Rapport sauvegarde: {report_path}")
    print("=" * 80)

    return report


if __name__ == "__main__":
    asyncio.run(run_benchmark())
