#!/usr/bin/env python3
"""JARVIS Cluster Stress Test — Multi-scenario distributed benchmark.

Tests 30+ tasks of increasing complexity across all nodes with different
routing strategies: single, race, round-robin, category-based, consensus.

Usage:
    uv run python scripts/cluster_stress_distributed.py
    uv run python scripts/cluster_stress_distributed.py --strategy race
    uv run python scripts/cluster_stress_distributed.py --quick
"""
import asyncio, httpx, time, json, sys, statistics
from pathlib import Path
from datetime import datetime

# === NODES ===
NODES = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "type": "lmstudio", "model": "qwen3-8b",
        "prefix": "/nothink\n", "max_tokens": 1024, "weight": 1.8,
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "type": "lmstudio", "model": "deepseek-r1-0528-qwen3-8b",
        "prefix": "", "max_tokens": 2048, "weight": 1.5,
    },
    "M3": {
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "type": "lmstudio", "model": "deepseek/deepseek-r1-0528-qwen3-8b",
        "prefix": "", "max_tokens": 2048, "weight": 1.2,
    },
    "OL1-1.7b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama", "model": "qwen3:1.7b", "weight": 1.3,
    },
}

# === 30 TASKS (small → large) ===
TASKS = [
    # --- MICRO (1-10 tokens expected) ---
    {"id": "T01", "cat": "simple", "size": "micro", "prompt": "Capital of France? One word.", "expect": ["Paris"]},
    {"id": "T02", "cat": "simple", "size": "micro", "prompt": "2+2=? Number only.", "expect": ["4"]},
    {"id": "T03", "cat": "simple", "size": "micro", "prompt": "Current year? Number only.", "expect": ["2026"]},
    {"id": "T04", "cat": "simple", "size": "micro", "prompt": "Is Python interpreted? Yes or No.", "expect": ["Yes"]},
    {"id": "T05", "cat": "simple", "size": "micro", "prompt": "HTTP status for Not Found? Number only.", "expect": ["404"]},

    # --- SMALL (10-50 tokens) ---
    {"id": "T06", "cat": "code", "size": "small", "prompt": "Python one-liner to reverse a string s.", "expect": ["[::-1]"]},
    {"id": "T07", "cat": "code", "size": "small", "prompt": "JavaScript arrow function that doubles a number.", "expect": ["=>"]},
    {"id": "T08", "cat": "reasoning", "size": "small", "prompt": "A farmer has 17 sheep. All but 9 die. How many left? Answer only.", "expect": ["9"]},
    {"id": "T09", "cat": "code", "size": "small", "prompt": "SQL query to count rows in users table.", "expect": ["SELECT", "COUNT"]},
    {"id": "T10", "cat": "analysis", "size": "small", "prompt": "3 advantages of TypeScript over JavaScript. Brief list.", "expect": ["type"]},

    # --- MEDIUM (50-150 tokens) ---
    {"id": "T11", "cat": "code", "size": "medium", "prompt": "Python function is_palindrome(s) that checks if string is palindrome. Code only.", "expect": ["def", "return"]},
    {"id": "T12", "cat": "code", "size": "medium", "prompt": "Python function fibonacci(n) returning nth fibonacci number. Code only.", "expect": ["def", "return"]},
    {"id": "T13", "cat": "reasoning", "size": "medium", "prompt": "Explain why 0.1 + 0.2 != 0.3 in floating point. 3 sentences max.", "expect": ["float", "binary"]},
    {"id": "T14", "cat": "analysis", "size": "medium", "prompt": "Compare REST vs GraphQL: 2 pros each, 2 cons each. Structured list.", "expect": ["REST", "GraphQL"]},
    {"id": "T15", "cat": "code", "size": "medium", "prompt": "Python decorator that logs function execution time. Code only.", "expect": ["def", "wrapper", "time"]},
    {"id": "T16", "cat": "system", "size": "medium", "prompt": "Bash one-liner to find the 5 largest files in /tmp recursively.", "expect": ["find", "sort"]},
    {"id": "T17", "cat": "code", "size": "medium", "prompt": "Python function to merge two sorted lists into one sorted list. Code only.", "expect": ["def", "return"]},
    {"id": "T18", "cat": "reasoning", "size": "medium", "prompt": "What is Big O notation? Explain O(1), O(n), O(n^2) with examples. Brief.", "expect": ["O(", "constant", "linear"]},

    # --- LARGE (150-500 tokens) ---
    {"id": "T19", "cat": "code", "size": "large", "prompt": "Python class LRUCache with get(key) and put(key, value) methods using OrderedDict. Include docstrings. Code only.", "expect": ["class", "def get", "def put"]},
    {"id": "T20", "cat": "code", "size": "large", "prompt": "Python async function that fetches 5 URLs in parallel with httpx, retries on failure (max 3), returns dict of url->response. Code only.", "expect": ["async", "httpx", "retry"]},
    {"id": "T21", "cat": "analysis", "size": "large", "prompt": "Compare PostgreSQL vs MongoDB vs Redis for a chat application. Cover: data model, scalability, query patterns, real-time features. Structured analysis.", "expect": ["PostgreSQL", "MongoDB", "Redis"]},
    {"id": "T22", "cat": "code", "size": "large", "prompt": "Python FastAPI endpoint that accepts JSON body with 'text' field, validates length 1-1000 chars, returns word count and character count. Include error handling. Code only.", "expect": ["FastAPI", "def", "return"]},
    {"id": "T23", "cat": "reasoning", "size": "large", "prompt": "Design a rate limiter for an API: explain token bucket algorithm, sliding window, and fixed window approaches. Which is best for a multi-tenant SaaS? Structured answer.", "expect": ["token", "bucket", "window"]},
    {"id": "T24", "cat": "code", "size": "large", "prompt": "Python context manager for database transactions that auto-commits on success and rolls back on exception. Support nested transactions with savepoints. Code only.", "expect": ["class", "__enter__", "__exit__"]},

    # --- XL (500+ tokens) ---
    {"id": "T25", "cat": "code", "size": "xl", "prompt": "Full Python implementation of a thread-safe producer-consumer queue with: Queue class, Producer thread, Consumer thread, graceful shutdown. Include type hints and docstrings. Code only.", "expect": ["class", "Thread", "Queue", "def"]},
    {"id": "T26", "cat": "analysis", "size": "xl", "prompt": "Architecture document for a real-time trading signal system: components (data ingestion, signal engine, risk manager, executor), data flow, technology choices, failure modes, scaling strategy. Structured document.", "expect": ["signal", "risk", "executor"]},
    {"id": "T27", "cat": "code", "size": "xl", "prompt": "Python implementation of a simple HTTP router (like Flask) supporting GET/POST methods, URL parameters (/users/<id>), middleware chain, and 404 handling. Code only.", "expect": ["class", "def route", "GET", "POST"]},
    {"id": "T28", "cat": "reasoning", "size": "xl", "prompt": "Explain CAP theorem with concrete examples for each trade-off pair (CP, AP, CA). Then explain why CA is impossible in distributed systems. Include diagrams in text. Detailed answer.", "expect": ["CAP", "consistency", "availability", "partition"]},
    {"id": "T29", "cat": "code", "size": "xl", "prompt": "Python implementation of a simple event bus with: subscribe(event, callback), unsubscribe, emit(event, data), wildcard patterns (user.*), async support. Include tests. Code only.", "expect": ["class", "subscribe", "emit", "async"]},
    {"id": "T30", "cat": "code", "size": "xl", "prompt": "Python implementation of a DAG task scheduler: Task class with dependencies, topological sort, parallel execution with asyncio, progress tracking, error propagation. Code only.", "expect": ["class", "Task", "async", "topological"]},
]


async def call_node(client, node_name, node_cfg, prompt, timeout=90):
    """Call a single node and return (content, elapsed, tokens_est, error)."""
    t0 = time.perf_counter()
    try:
        if node_cfg["type"] == "lmstudio":
            body = {
                "model": node_cfg["model"],
                "input": node_cfg.get("prefix", "") + prompt,
                "temperature": 0.3,
                "max_output_tokens": node_cfg.get("max_tokens", 1024),
                "stream": False, "store": False,
            }
            r = await client.post(node_cfg["url"], json=body,
                                  headers={"Content-Type": "application/json"}, timeout=timeout)
            d = r.json()
            if "error" in d or d.get("StatusCode", 200) >= 400:
                return "", time.perf_counter() - t0, 0, d.get("error", str(d.get("Status", "error")))
            msgs = [o for o in d.get("output", []) if o.get("type") == "message"]
            content = msgs[-1].get("content", "") if msgs else ""
            if isinstance(content, list):
                content = content[0].get("text", "") if content else ""
        else:  # ollama
            body = {
                "model": node_cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False,
            }
            r = await client.post(node_cfg["url"], json=body, timeout=timeout)
            d = r.json()
            if d.get("StatusCode", 200) >= 400:
                return "", time.perf_counter() - t0, 0, d.get("error", "rate limited")
            content = d.get("message", {}).get("content", "")

        elapsed = time.perf_counter() - t0
        tokens = len(str(content).split())
        return str(content), elapsed, tokens, None
    except Exception as e:
        return "", time.perf_counter() - t0, 0, str(e)[:80]


def score_quality(content, expected_keywords):
    if not content.strip():
        return 0
    score = 20  # non-empty base
    matched = sum(1 for k in expected_keywords if k.lower() in content.lower())
    if expected_keywords:
        score += int(80 * matched / len(expected_keywords))
    return min(100, score)


# === ROUTING STRATEGIES ===

async def strategy_single(client, task, node_name):
    """Send to a single specific node."""
    cfg = NODES[node_name]
    content, elapsed, tokens, err = await call_node(client, node_name, cfg, task["prompt"])
    quality = score_quality(content, task["expect"]) if not err else 0
    return [{"node": node_name, "time": elapsed, "tokens": tokens, "quality": quality, "error": err}]


async def strategy_race(client, task, node_names=None):
    """Send to all nodes, first quality response wins."""
    nodes = node_names or list(NODES.keys())
    coros = [call_node(client, n, NODES[n], task["prompt"]) for n in nodes]
    results = await asyncio.gather(*coros)
    out = []
    for i, (content, elapsed, tokens, err) in enumerate(results):
        quality = score_quality(content, task["expect"]) if not err else 0
        out.append({"node": nodes[i], "time": elapsed, "tokens": tokens, "quality": quality, "error": err})
    return out


async def strategy_round_robin(client, tasks, node_names=None):
    """Distribute tasks round-robin across nodes."""
    nodes = node_names or list(NODES.keys())
    results = []
    coros = []
    assignments = []
    for i, task in enumerate(tasks):
        node_name = nodes[i % len(nodes)]
        assignments.append((task, node_name))
        coros.append(call_node(client, node_name, NODES[node_name], task["prompt"]))

    raw = await asyncio.gather(*coros)
    for i, (content, elapsed, tokens, err) in enumerate(raw):
        task, node_name = assignments[i]
        quality = score_quality(content, task["expect"]) if not err else 0
        results.append({
            "task": task["id"], "cat": task["cat"], "size": task["size"],
            "node": node_name, "time": elapsed, "tokens": tokens,
            "quality": quality, "error": err,
        })
    return results


async def strategy_category(client, task):
    """Route based on task category to best node."""
    routing = {
        "simple": "OL1-1.7b",  # fastest for trivial
        "code": "M1",           # champion code
        "reasoning": "M2",     # deepseek-r1 reasoning
        "analysis": "M1",      # good general
        "system": "M1",        # system knowledge
    }
    node_name = routing.get(task["cat"], "M1")
    cfg = NODES[node_name]
    content, elapsed, tokens, err = await call_node(client, node_name, cfg, task["prompt"])
    quality = score_quality(content, task["expect"]) if not err else 0
    return [{"node": node_name, "time": elapsed, "tokens": tokens, "quality": quality, "error": err}]


async def strategy_consensus(client, task, node_names=None):
    """Send to 2+ nodes, pick weighted best."""
    nodes = node_names or ["M1", "M2", "M3"]
    coros = [call_node(client, n, NODES[n], task["prompt"]) for n in nodes]
    results = await asyncio.gather(*coros)
    out = []
    for i, (content, elapsed, tokens, err) in enumerate(results):
        quality = score_quality(content, task["expect"]) if not err else 0
        weight = NODES[nodes[i]]["weight"]
        out.append({
            "node": nodes[i], "time": elapsed, "tokens": tokens,
            "quality": quality, "weighted_score": quality * weight,
            "error": err,
        })
    return out


# === MAIN BENCHMARK ===

async def run_full_benchmark(quick=False):
    tasks = TASKS[:10] if quick else TASKS
    print(f"\n{'#'*70}")
    print(f"  JARVIS CLUSTER STRESS TEST — {len(tasks)} tasks x 5 strategies")
    print(f"  Nodes: {', '.join(NODES.keys())}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*70}")

    all_results = {}
    async with httpx.AsyncClient() as client:
        # === STRATEGY 1: SINGLE (each node solo) ===
        print(f"\n{'='*60}")
        print(f"  STRATEGY 1: SINGLE NODE (each node individually)")
        print(f"{'='*60}")
        for node_name in NODES:
            results = []
            coros = [strategy_single(client, t, node_name) for t in tasks]
            raw = await asyncio.gather(*coros)
            for i, r_list in enumerate(raw):
                r = r_list[0]
                r["task"] = tasks[i]["id"]
                r["cat"] = tasks[i]["cat"]
                r["size"] = tasks[i]["size"]
                results.append(r)

            ok = [r for r in results if not r.get("error")]
            avg_t = statistics.mean([r["time"] for r in ok]) if ok else 999
            avg_q = statistics.mean([r["quality"] for r in ok]) if ok else 0
            print(f"  {node_name:<12s} {len(ok)}/{len(results)} OK  avg={avg_t:.1f}s  Q={avg_q:.0f}")
            all_results[f"single_{node_name}"] = results

        # === STRATEGY 2: RACE (all nodes, first wins) ===
        print(f"\n{'='*60}")
        print(f"  STRATEGY 2: RACE (all nodes parallel, best wins)")
        print(f"{'='*60}")
        race_results = []
        # Run tasks sequentially to avoid overwhelming
        for t in tasks:
            r_list = await strategy_race(client, t)
            best = max(r_list, key=lambda x: (x["quality"], -x["time"]))
            race_results.append({
                "task": t["id"], "cat": t["cat"], "size": t["size"],
                "winner": best["node"], "time": best["time"],
                "quality": best["quality"],
                "all": [{n["node"]: f"Q={n['quality']} {n['time']:.1f}s"} for n in r_list],
            })
            winner_str = f"  {t['id']} [{t['size']:5s}] winner={best['node']:<10s} Q={best['quality']:>3d} {best['time']:.1f}s"
            print(winner_str)
        all_results["race"] = race_results

        # === STRATEGY 3: ROUND-ROBIN ===
        print(f"\n{'='*60}")
        print(f"  STRATEGY 3: ROUND-ROBIN (distribute evenly)")
        print(f"{'='*60}")
        rr_results = await strategy_round_robin(client, tasks)
        for r in rr_results:
            status = "OK" if not r.get("error") else f"FAIL"
            print(f"  {r['task']} -> {r['node']:<10s} Q={r['quality']:>3d} {r['time']:.1f}s {status}")
        all_results["round_robin"] = rr_results

        # === STRATEGY 4: CATEGORY-BASED ===
        print(f"\n{'='*60}")
        print(f"  STRATEGY 4: CATEGORY-BASED (smart routing)")
        print(f"{'='*60}")
        cat_results = []
        coros = [strategy_category(client, t) for t in tasks]
        raw = await asyncio.gather(*coros)
        for i, r_list in enumerate(raw):
            r = r_list[0]
            r["task"] = tasks[i]["id"]
            r["cat"] = tasks[i]["cat"]
            r["size"] = tasks[i]["size"]
            cat_results.append(r)
            print(f"  {r['task']} [{r['cat']:9s}] -> {r['node']:<10s} Q={r['quality']:>3d} {r['time']:.1f}s")
        all_results["category"] = cat_results

        # === STRATEGY 5: CONSENSUS (M1+M2+M3) ===
        print(f"\n{'='*60}")
        print(f"  STRATEGY 5: CONSENSUS (M1+M2+M3 weighted vote)")
        print(f"{'='*60}")
        cons_results = []
        # Only run on subset to save time
        consensus_tasks = tasks[:8] if not quick else tasks[:4]
        for t in consensus_tasks:
            r_list = await strategy_consensus(client, t)
            best = max(r_list, key=lambda x: x.get("weighted_score", 0))
            cons_results.append({
                "task": t["id"], "winner": best["node"],
                "quality": best["quality"], "weighted": best.get("weighted_score", 0),
                "time": best["time"],
            })
            votes = " | ".join(f"{r['node']}:Q{r['quality']}*{NODES[r['node']]['weight']}" for r in r_list)
            print(f"  {t['id']} winner={best['node']:<6s} Q={best['quality']:>3d} wt={best.get('weighted_score',0):.0f}  [{votes}]")
        all_results["consensus"] = cons_results

    # === FINAL ANALYSIS ===
    print(f"\n{'#'*70}")
    print(f"  FINAL ANALYSIS — STRATEGY COMPARISON")
    print(f"{'#'*70}")

    strategy_scores = {}
    for strat_name, results in all_results.items():
        if strat_name.startswith("single_"):
            node = strat_name.replace("single_", "")
            ok = [r for r in results if r.get("quality", 0) > 0]
            if ok:
                avg_q = statistics.mean([r["quality"] for r in ok])
                avg_t = statistics.mean([r["time"] for r in ok])
                total_t = sum(r["time"] for r in results)
                strategy_scores[f"single/{node}"] = {
                    "avg_quality": avg_q, "avg_time": avg_t, "total_time": total_t,
                    "success_rate": len(ok) / len(results) * 100,
                }
        elif strat_name == "race":
            ok = [r for r in results if r.get("quality", 0) > 0]
            if ok:
                avg_q = statistics.mean([r["quality"] for r in ok])
                avg_t = statistics.mean([r["time"] for r in ok])
                strategy_scores["race"] = {
                    "avg_quality": avg_q, "avg_time": avg_t,
                    "success_rate": len(ok) / len(results) * 100,
                }
        elif strat_name == "round_robin":
            ok = [r for r in results if r.get("quality", 0) > 0]
            if ok:
                avg_q = statistics.mean([r["quality"] for r in ok])
                avg_t = statistics.mean([r["time"] for r in ok])
                total_t = sum(r["time"] for r in results)
                strategy_scores["round_robin"] = {
                    "avg_quality": avg_q, "avg_time": avg_t, "total_time": total_t,
                    "success_rate": len(ok) / len(results) * 100,
                }
        elif strat_name == "category":
            ok = [r for r in results if r.get("quality", 0) > 0]
            if ok:
                avg_q = statistics.mean([r["quality"] for r in ok])
                avg_t = statistics.mean([r["time"] for r in ok])
                total_t = sum(r["time"] for r in results)
                strategy_scores["category"] = {
                    "avg_quality": avg_q, "avg_time": avg_t, "total_time": total_t,
                    "success_rate": len(ok) / len(results) * 100,
                }

    print(f"\n{'Strategy':<20s} {'Avg Q':>6s} {'Avg T':>7s} {'Success':>8s} {'SCORE':>7s}")
    print("-" * 55)
    rankings = []
    for name, s in sorted(strategy_scores.items(), key=lambda x: -(x[1]["avg_quality"] * 0.6 + (100 - min(100, x[1]["avg_time"] * 10)) * 0.3 + x[1]["success_rate"] * 0.1)):
        speed_score = max(0, 100 - x["avg_time"] * 10) if (x := s) else 0
        composite = s["avg_quality"] * 0.6 + speed_score * 0.3 + s["success_rate"] * 0.1
        print(f"{name:<20s} {s['avg_quality']:>5.0f} {s['avg_time']:>6.1f}s {s['success_rate']:>6.0f}% {composite:>6.1f}")
        rankings.append({"strategy": name, "score": composite, **s})

    # Winner
    if rankings:
        best = max(rankings, key=lambda x: x["score"])
        print(f"\n  >>> BEST STRATEGY: {best['strategy']} (score={best['score']:.1f})")

    # Save
    output = {
        "timestamp": datetime.now().isoformat(),
        "nodes": list(NODES.keys()),
        "tasks_count": len(tasks),
        "results": {k: v for k, v in all_results.items() if not k.startswith("single_")},
        "strategy_scores": strategy_scores,
        "rankings": sorted(rankings, key=lambda x: -x["score"]),
        "best_strategy": best["strategy"] if rankings else None,
    }
<<<<<<< Updated upstream
    out_path = Path("/home/turbo/jarvis-m1-ops/data/cluster_stress_results.json")
=======
    out_path = Path("/home/turbo/jarvis/data/cluster_stress_results.json")
>>>>>>> Stashed changes
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Saved: {out_path}")
    return output


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    asyncio.run(run_full_benchmark(quick=quick))
