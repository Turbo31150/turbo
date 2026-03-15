#!/usr/bin/env python3
"""JARVIS Multi-Scenario Benchmark — 1000 cycles
Tests diverse task sizes across ALL routing paths:
  Direct nodes (M1/M2/M3/OL1), Cloud Ollama, Race, Consensus, Chain, Round-Robin
"""
import asyncio, httpx, json, time, random, sys, os
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional

# ── CONFIG ──────────────────────────────────────────
TOTAL_CYCLES = 1000
MAX_PARALLEL = 12  # respect cluster capacity
TIMEOUT_S = 30
<<<<<<< Updated upstream
RESULTS_PATH = "/home/turbo/jarvis-m1-ops/data/benchmark_1000_results.json"
=======
RESULTS_PATH = "/home/turbo/jarvis/data/benchmark_1000_results.json"
>>>>>>> Stashed changes

# ── NODES ───────────────────────────────────────────
NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b",
            "extract": "lmstudio", "prefix": "/nothink\n"},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "extract": "lmstudio", "prefix": ""},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "extract": "lmstudio", "prefix": ""},
    "OL1-local": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
                   "extract": "ollama", "prefix": ""},
    # DELETED: model removed from Ollama
    # "OL1-gptoss": {"url": "http://127.0.0.1:11434/api/chat", "model": "gpt-oss:120b-cloud",
    #                 "extract": "ollama", "prefix": "", "think": False},
    # DELETED: model removed from Ollama
    # "OL1-devstral": {"url": "http://127.0.0.1:11434/api/chat", "model": "devstral-2:123b-cloud",
    #                   "extract": "ollama", "prefix": "", "think": False},
}

# ── TASK TEMPLATES (small → large) ─────────────────
TASKS_TINY = [  # <1s expected
    "Reponds en 1 mot: 2+2=?",
    "Dis juste OK",
    "Capital de la France?",
    "1+1=?",
    "Vrai ou faux: le soleil est une etoile",
    "Couleur du ciel?",
    "3*7=?",
    "Bonjour en anglais?",
    "Nom d'un fruit rouge",
    "Combien de jours dans une semaine?",
]
TASKS_SMALL = [  # 1-3s
    "Ecris une fonction Python qui retourne le max d'une liste. Code seulement.",
    "Explique en 2 phrases ce qu'est un API REST.",
    "Traduis en anglais: Le chat dort sur le toit.",
    "Liste 5 langages de programmation populaires.",
    "Quelle est la difference entre TCP et UDP? Bref.",
    "Ecris un one-liner Python pour inverser une string.",
    "Qu'est-ce que JSON? 2 phrases max.",
    "Donne un exemple de requete SQL SELECT avec WHERE.",
    "Fibonacci de 10? Juste le nombre.",
    "Difference entre git merge et git rebase? Bref.",
]
TASKS_MEDIUM = [  # 3-10s
    "Ecris une classe Python 'Stack' avec push, pop, peek, is_empty. Code complet.",
    "Explique le pattern Observer en programmation. Donne un exemple court Python.",
    "Ecris un script bash qui monitore l'utilisation CPU toutes les 5 secondes.",
    "Compare les avantages/inconvenients de REST vs GraphQL en 5 points.",
    "Ecris une fonction Python async qui fetch 3 URLs en parallele avec httpx.",
    "Explique comment fonctionne un hash table. Complexite O(1) pourquoi?",
    "Ecris un decorateur Python qui mesure le temps d'execution d'une fonction.",
    "Qu'est-ce que SOLID? Explique chaque lettre en 1 phrase.",
]
TASKS_LARGE = [  # 10-30s
    "Ecris un serveur HTTP minimal en Python (sans framework) qui gere GET/POST sur /api/data avec JSON.",
    "Design une architecture microservices pour un systeme de e-commerce: auth, catalog, orders, payments. Diagramme textuel.",
    "Ecris un parser d'expressions mathematiques en Python (recursive descent) supportant +,-,*,/,().",
    "Explique en detail comment fonctionne le consensus Raft. Etapes, election, log replication.",
    "Ecris un rate limiter token bucket en Python avec asyncio, thread-safe.",
]

# ── ROUTING STRATEGIES ──────────────────────────────
STRATEGIES = [
    "direct-M1", "direct-M2", "direct-M3",
    "direct-OL1-local",
    # DELETED: model removed from Ollama
    # "direct-OL1-gptoss", "direct-OL1-devstral",
    "race-M1-M2", "race-M1-OL1local", "race-all-local",
    "consensus-M1-M2-M3",
    # DELETED: model removed from Ollama
    # "consensus-M1-cloud",
    "chain-M1-then-M2",
    # DELETED: model removed from Ollama
    # "chain-cloud-then-M1",
    "roundrobin",
]

@dataclass
class Result:
    cycle: int
    strategy: str
    task_size: str
    task: str
    node_used: str
    latency_ms: float
    success: bool
    output_len: int = 0
    error: str = ""

# ── NODE CALLERS ────────────────────────────────────
async def call_lmstudio(client: httpx.AsyncClient, url: str, model: str, prompt: str, prefix: str, timeout: float = TIMEOUT_S) -> tuple[str, float]:
    t0 = time.perf_counter()
    body = {"model": model, "input": f"{prefix}{prompt}", "temperature": 0.3, "max_output_tokens": 512, "stream": False, "store": False}
    r = await client.post(url, json=body, timeout=timeout)
    elapsed = (time.perf_counter() - t0) * 1000
    data = r.json()
    # Extract: last message block from output[]
    output = data.get("output", [])
    text = ""
    for block in reversed(output):
        if isinstance(block, dict) and block.get("type") == "message":
            for c in block.get("content", []):
                if isinstance(c, dict) and c.get("type") == "output_text":
                    text = c.get("text", "")
                    break
            if text:
                break
    if not text and output:
        text = str(output[-1])[:200]
    return text, elapsed

async def call_ollama(client: httpx.AsyncClient, url: str, model: str, prompt: str, think: bool = True, timeout: float = TIMEOUT_S) -> tuple[str, float]:
    t0 = time.perf_counter()
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False}
    if not think:
        body["think"] = False
    r = await client.post(url, json=body, timeout=timeout)
    elapsed = (time.perf_counter() - t0) * 1000
    data = r.json()
    text = data.get("message", {}).get("content", "")
    return text, elapsed

async def call_node(client: httpx.AsyncClient, node_name: str, prompt: str) -> tuple[str, float, str]:
    """Returns (text, latency_ms, node_name)"""
    cfg = NODES[node_name]
    if cfg["extract"] == "lmstudio":
        text, ms = await call_lmstudio(client, cfg["url"], cfg["model"], prompt, cfg.get("prefix", ""))
    else:
        text, ms = await call_ollama(client, cfg["url"], cfg["model"], prompt, think=cfg.get("think", True))
    return text, ms, node_name

# ── STRATEGY EXECUTORS ──────────────────────────────
async def strategy_direct(client, node_name, prompt):
    text, ms, node = await call_node(client, node_name, prompt)
    return text, ms, node

async def strategy_race(client, node_names, prompt):
    """First to respond wins"""
    tasks = [asyncio.create_task(call_node(client, n, prompt)) for n in node_names]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    result = done.pop().result()
    return result  # (text, ms, node)

async def strategy_consensus(client, node_names, prompt):
    """All respond, pick longest (most complete)"""
    tasks = [call_node(client, n, prompt) for n in node_names]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid = [(t, ms, n) for t, ms, n in results if isinstance(t, str) and len(t) > 0]
    if not valid:
        raise Exception("No valid responses")
    best = max(valid, key=lambda x: len(x[0]))
    total_ms = max(ms for _, ms, _ in valid)
    return best[0], total_ms, f"consensus({best[2]})"

async def strategy_chain(client, node_a, node_b, prompt):
    """A generates, B verifies/improves"""
    text_a, ms_a, _ = await call_node(client, node_a, prompt)
    verify_prompt = f"Verifie et ameliore cette reponse (corrige si faux, sinon confirme):\nQuestion: {prompt}\nReponse: {text_a[:300]}"
    text_b, ms_b, _ = await call_node(client, node_b, verify_prompt)
    return text_b, ms_a + ms_b, f"chain({node_a}->{node_b})"

RR_NODES = ["M1", "OL1-local", "M2", "M3"]
rr_idx = 0

async def execute_strategy(client, strategy, prompt):
    global rr_idx
    if strategy.startswith("direct-"):
        node = strategy.replace("direct-", "")
        return await strategy_direct(client, node, prompt)
    elif strategy == "race-M1-M2":
        return await strategy_race(client, ["M1", "M2"], prompt)
    elif strategy == "race-M1-OL1local":
        return await strategy_race(client, ["M1", "OL1-local"], prompt)
    elif strategy == "race-all-local":
        return await strategy_race(client, ["M1", "M2", "OL1-local"], prompt)
    elif strategy == "consensus-M1-M2-M3":
        return await strategy_consensus(client, ["M1", "M2", "M3"], prompt)
    # DELETED: cloud strategies removed (gpt-oss/devstral models removed from Ollama)
    # elif strategy == "consensus-M1-cloud":
    #     return await strategy_consensus(client, ["M1", "OL1-gptoss"], prompt)
    elif strategy == "chain-M1-then-M2":
        return await strategy_chain(client, "M1", "M2", prompt)
    # DELETED: cloud strategies removed (gpt-oss/devstral models removed from Ollama)
    # elif strategy == "chain-cloud-then-M1":
    #     return await strategy_chain(client, "OL1-gptoss", "M1", prompt)
    elif strategy == "roundrobin":
        node = RR_NODES[rr_idx % len(RR_NODES)]
        rr_idx += 1
        return await strategy_direct(client, node, prompt)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

# ── CYCLE GENERATOR ─────────────────────────────────
def generate_cycles(n=TOTAL_CYCLES):
    """Generate n task assignments with increasing complexity"""
    cycles = []
    for i in range(n):
        # Progressive difficulty
        progress = i / n
        if progress < 0.25:
            size, pool = "tiny", TASKS_TINY
        elif progress < 0.55:
            size, pool = "small", TASKS_SMALL
        elif progress < 0.82:
            size, pool = "medium", TASKS_MEDIUM
        else:
            size, pool = "large", TASKS_LARGE

        task = pool[i % len(pool)]
        strategy = STRATEGIES[i % len(STRATEGIES)]
        cycles.append((i, size, task, strategy))
    return cycles

# ── MAIN RUNNER ─────────────────────────────────────
async def run_cycle(sem, client, cycle_num, size, task, strategy):
    async with sem:
        try:
            text, ms, node = await execute_strategy(client, strategy, task)
            return Result(cycle=cycle_num, strategy=strategy, task_size=size,
                         task=task[:60], node_used=node, latency_ms=round(ms, 1),
                         success=True, output_len=len(text))
        except Exception as e:
            return Result(cycle=cycle_num, strategy=strategy, task_size=size,
                         task=task[:60], node_used="FAIL", latency_ms=0,
                         success=False, error=str(e)[:100])

async def main():
    print(f"=== JARVIS Multi-Scenario Benchmark — {TOTAL_CYCLES} cycles ===")
    print(f"Strategies: {len(STRATEGIES)} | Nodes: {len(NODES)} | Max parallel: {MAX_PARALLEL}")
    print()

    cycles = generate_cycles(TOTAL_CYCLES)
    sem = asyncio.Semaphore(MAX_PARALLEL)
    results: list[Result] = []

    t_start = time.perf_counter()

    async with httpx.AsyncClient() as client:
        # Run in batches of 50 for progress reporting
        batch_size = 50
        for batch_start in range(0, len(cycles), batch_size):
            batch = cycles[batch_start:batch_start + batch_size]
            tasks = [run_cycle(sem, client, c[0], c[1], c[2], c[3]) for c in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

            done = batch_start + len(batch)
            ok = sum(1 for r in results if r.success)
            fail = len(results) - ok
            avg_ms = sum(r.latency_ms for r in results if r.success) / max(ok, 1)
            elapsed = time.perf_counter() - t_start

            print(f"  [{done:4d}/{TOTAL_CYCLES}] OK={ok} FAIL={fail} avg={avg_ms:.0f}ms elapsed={elapsed:.1f}s")

    total_time = time.perf_counter() - t_start

    # ── ANALYSIS ────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"COMPLETE: {TOTAL_CYCLES} cycles in {total_time:.1f}s")
    print(f"{'='*60}\n")

    ok_results = [r for r in results if r.success]
    fail_results = [r for r in results if not r.success]

    print(f"SUCCESS: {len(ok_results)}/{TOTAL_CYCLES} ({100*len(ok_results)/TOTAL_CYCLES:.1f}%)")
    print(f"FAIL:    {len(fail_results)}")
    if ok_results:
        print(f"AVG latency: {sum(r.latency_ms for r in ok_results)/len(ok_results):.0f}ms")
        print(f"MIN latency: {min(r.latency_ms for r in ok_results):.0f}ms")
        print(f"MAX latency: {max(r.latency_ms for r in ok_results):.0f}ms")

    # By strategy
    print(f"\n--- PAR STRATEGIE ---")
    by_strat = defaultdict(list)
    for r in results:
        by_strat[r.strategy].append(r)

    print(f"{'Strategy':<25} {'OK':>4} {'Fail':>4} {'Avg ms':>8} {'Min ms':>8} {'Max ms':>8} {'Avg len':>8}")
    for strat in STRATEGIES:
        rs = by_strat[strat]
        oks = [r for r in rs if r.success]
        fails = len(rs) - len(oks)
        if oks:
            avg = sum(r.latency_ms for r in oks) / len(oks)
            mn = min(r.latency_ms for r in oks)
            mx = max(r.latency_ms for r in oks)
            avg_len = sum(r.output_len for r in oks) / len(oks)
            print(f"{strat:<25} {len(oks):>4} {fails:>4} {avg:>8.0f} {mn:>8.0f} {mx:>8.0f} {avg_len:>8.0f}")
        else:
            print(f"{strat:<25} {0:>4} {len(rs):>4} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8}")

    # By task size
    print(f"\n--- PAR TAILLE ---")
    by_size = defaultdict(list)
    for r in results:
        by_size[r.task_size].append(r)

    for size in ["tiny", "small", "medium", "large"]:
        rs = by_size[size]
        oks = [r for r in rs if r.success]
        if oks:
            avg = sum(r.latency_ms for r in oks) / len(oks)
            print(f"  {size:<8}: {len(oks):>3} OK / {len(rs):>3} total, avg {avg:.0f}ms")

    # By node used
    print(f"\n--- PAR NOEUD UTILISE ---")
    by_node = defaultdict(list)
    for r in ok_results:
        by_node[r.node_used].append(r)
    for node, rs in sorted(by_node.items(), key=lambda x: -len(x[1])):
        avg = sum(r.latency_ms for r in rs) / len(rs)
        print(f"  {node:<25}: {len(rs):>3} reqs, avg {avg:.0f}ms")

    # Failures detail
    if fail_results:
        print(f"\n--- ECHECS ---")
        err_counts = defaultdict(int)
        for r in fail_results:
            err_counts[f"{r.strategy}: {r.error[:50]}"] += 1
        for err, cnt in sorted(err_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  x{cnt}: {err}")

    # Save JSON
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_cycles": TOTAL_CYCLES,
        "total_time_s": round(total_time, 1),
        "success_rate": round(100 * len(ok_results) / TOTAL_CYCLES, 1),
        "avg_latency_ms": round(sum(r.latency_ms for r in ok_results) / max(len(ok_results), 1)),
        "by_strategy": {},
        "by_size": {},
        "failures": len(fail_results),
        "results": [{"cycle": r.cycle, "strategy": r.strategy, "size": r.task_size,
                      "node": r.node_used, "ms": r.latency_ms, "ok": r.success,
                      "len": r.output_len} for r in results]
    }
    for strat in STRATEGIES:
        oks = [r for r in by_strat[strat] if r.success]
        if oks:
            report["by_strategy"][strat] = {
                "count": len(oks), "avg_ms": round(sum(r.latency_ms for r in oks)/len(oks)),
                "min_ms": round(min(r.latency_ms for r in oks)),
                "max_ms": round(max(r.latency_ms for r in oks))
            }
    for size in ["tiny", "small", "medium", "large"]:
        oks = [r for r in by_size[size] if r.success]
        if oks:
            report["by_size"][size] = {
                "count": len(oks), "avg_ms": round(sum(r.latency_ms for r in oks)/len(oks))
            }

    with open(RESULTS_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nResultats sauvegardes: {RESULTS_PATH}")
    print(f"\nThroughput: {TOTAL_CYCLES/total_time:.1f} cycles/s")

if __name__ == "__main__":
    asyncio.run(main())
