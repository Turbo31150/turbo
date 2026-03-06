#!/usr/bin/env python3
"""JARVIS Cluster Benchmark Distributed - Test speed/quality across all nodes."""
import asyncio, httpx, time, json, sys, statistics

NODES = {
    "M1/qwen3-8b": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "qwen3-8b",
        "headers": {"Content-Type": "application/json"},
        "prefix": "/nothink\n",
        "max_tokens": 1024,
    },
    "M2/deepseek-r1": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "deepseek-r1-0528-qwen3-8b",
        "headers": {"Content-Type": "application/json"},
        "prefix": "",
        "max_tokens": 2048,
    },
    "OL1/gpt-oss-120b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "gpt-oss:120b-cloud",
        "think": False,
    },
    "OL1/devstral-123b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "devstral-2:123b-cloud",
        "think": False,
    },
    "OL1/qwen3-1.7b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "qwen3:1.7b",
        "think": False,
    },
    "OL1/qwen3-14b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "qwen3:14b",
        "think": False,
    },
    "OL1/glm-4.7": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "glm-4.7:cloud",
        "think": False,
    },
    "OL1/qwen3-coder-480b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "qwen3-coder:480b-cloud",
        "think": False,
    },
    "OL1/deepseek-v3.2": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "deepseek-v3.2:cloud",
        "think": False,
    },
    "OL1/kimi-k2.5": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "kimi-k2.5:cloud",
        "think": False,
    },
    "OL1/cogito-671b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "cogito-2.1:671b-cloud",
        "think": False,
    },
    "OL1/qwen3-next-80b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "qwen3-next:80b-cloud",
        "think": False,
    },
}

SCENARIOS = {
    "code_simple": {
        "prompt": "Write a Python function that checks if a string is a palindrome. Return only the function, no explanation.",
        "category": "code",
        "expected_keywords": ["def", "return", "palindrome"],
    },
    "code_complex": {
        "prompt": "Write a Python async function that fetches URLs in parallel using httpx, with retry logic (max 3 retries, exponential backoff). Include type hints. Return only the code.",
        "category": "code",
        "expected_keywords": ["async", "httpx", "retry", "await"],
    },
    "reasoning": {
        "prompt": "A farmer has 17 sheep. All but 9 die. How many sheep does the farmer have left? Explain your reasoning step by step, then give the final answer.",
        "category": "reasoning",
        "expected_keywords": ["9"],
    },
    "question_simple": {
        "prompt": "What is the capital of France? Answer in one word.",
        "category": "simple",
        "expected_keywords": ["Paris"],
    },
    "analysis": {
        "prompt": "Compare REST vs GraphQL APIs. Give 3 pros and 3 cons of each in a structured format.",
        "category": "analysis",
        "expected_keywords": ["REST", "GraphQL", "pro", "con"],
    },
}


async def call_lmstudio(client, node_cfg, prompt, timeout=60):
    body = {
        "model": node_cfg["model"],
        "input": node_cfg.get("prefix", "") + prompt,
        "temperature": 0.3,
        "max_output_tokens": node_cfg.get("max_tokens", 1024),
        "stream": False,
        "store": False,
    }
    r = await client.post(node_cfg["url"], json=body, headers=node_cfg.get("headers", {}), timeout=timeout)
    d = r.json()
    msgs = [o for o in d.get("output", []) if o.get("type") == "message"]
    if not msgs:
        return ""
    content = msgs[-1].get("content", "")
    if isinstance(content, list):
        return content[0].get("text", "") if content else ""
    return str(content)


async def call_ollama(client, node_cfg, prompt, timeout=120):
    body = {
        "model": node_cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": node_cfg.get("think", False),
    }
    r = await client.post(node_cfg["url"], json=body, timeout=timeout)
    d = r.json()
    return d.get("message", {}).get("content", "")


async def benchmark_node(client, node_name, node_cfg, scenario_name, scenario):
    prompt = scenario["prompt"]
    t0 = time.perf_counter()
    try:
        if node_cfg["type"] == "lmstudio":
            response = await call_lmstudio(client, node_cfg, prompt)
        else:
            response = await call_ollama(client, node_cfg, prompt)
        elapsed = time.perf_counter() - t0
        tokens_est = len(response.split())
        tok_per_sec = tokens_est / elapsed if elapsed > 0 else 0

        # Quality scoring
        quality = 0
        kw = scenario.get("expected_keywords", [])
        if response.strip():
            quality += 30  # non-empty
            matched = sum(1 for k in kw if k.lower() in response.lower())
            quality += int(70 * matched / len(kw)) if kw else 70

        return {
            "node": node_name,
            "scenario": scenario_name,
            "category": scenario["category"],
            "time_s": round(elapsed, 2),
            "tokens_est": tokens_est,
            "tok_per_sec": round(tok_per_sec, 1),
            "quality": quality,
            "response_len": len(response),
            "ok": True,
            "response_preview": response[:150].replace("\n", " "),
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "node": node_name,
            "scenario": scenario_name,
            "category": scenario["category"],
            "time_s": round(elapsed, 2),
            "tokens_est": 0,
            "tok_per_sec": 0,
            "quality": 0,
            "response_len": 0,
            "ok": False,
            "error": str(e)[:100],
        }


async def run_benchmark(nodes_filter=None, scenarios_filter=None):
    nodes = NODES
    scenarios = SCENARIOS

    if nodes_filter:
        nodes = {k: v for k, v in nodes.items() if any(f.lower() in k.lower() for f in nodes_filter)}
    if scenarios_filter:
        scenarios = {k: v for k, v in scenarios.items() if k in scenarios_filter}

    print(f"\n{'='*80}")
    print(f"  JARVIS CLUSTER BENCHMARK DISTRIBUTED")
    print(f"  Nodes: {len(nodes)} | Scenarios: {len(scenarios)} | Total tests: {len(nodes)*len(scenarios)}")
    print(f"{'='*80}\n")

    results = []
    async with httpx.AsyncClient() as client:
        # Run ALL nodes x ALL scenarios in parallel (max concurrency)
        tasks = []
        for node_name, node_cfg in nodes.items():
            for sc_name, sc in scenarios.items():
                tasks.append(benchmark_node(client, node_name, node_cfg, sc_name, sc))

        print(f"  Launching {len(tasks)} parallel requests...")
        t_global = time.perf_counter()
        results = await asyncio.gather(*tasks)
        t_total = time.perf_counter() - t_global
        print(f"  All done in {t_total:.1f}s\n")

    # Results table
    print(f"{'Node':<25s} {'Scenario':<18s} {'Time':>6s} {'Tok/s':>6s} {'Q':>4s} {'Len':>5s} {'Status'}")
    print("-" * 80)
    for r in sorted(results, key=lambda x: (x["scenario"], x["time_s"])):
        status = "OK" if r["ok"] else f"FAIL: {r.get('error','')[:30]}"
        print(f"{r['node']:<25s} {r['scenario']:<18s} {r['time_s']:>5.1f}s {r['tok_per_sec']:>5.1f} {r['quality']:>4d} {r['response_len']:>5d} {status}")

    # Aggregated scores per node
    print(f"\n{'='*80}")
    print(f"  AGGREGATED SCORES PER NODE")
    print(f"{'='*80}")
    node_stats = {}
    for r in results:
        if not r["ok"]:
            continue
        n = r["node"]
        if n not in node_stats:
            node_stats[n] = {"times": [], "qualities": [], "tok_per_sec": [], "ok": 0, "fail": 0}
        node_stats[n]["times"].append(r["time_s"])
        node_stats[n]["qualities"].append(r["quality"])
        node_stats[n]["tok_per_sec"].append(r["tok_per_sec"])
        node_stats[n]["ok"] += 1

    for r in results:
        if r["ok"]:
            continue
        n = r["node"]
        if n not in node_stats:
            node_stats[n] = {"times": [], "qualities": [], "tok_per_sec": [], "ok": 0, "fail": 0}
        node_stats[n]["fail"] += 1

    print(f"\n{'Node':<25s} {'Avg Time':>8s} {'Avg Q':>6s} {'Avg Tok/s':>10s} {'OK/Total':>9s} {'SCORE':>7s}")
    print("-" * 70)
    rankings = []
    for n, s in sorted(node_stats.items()):
        avg_t = statistics.mean(s["times"]) if s["times"] else 999
        avg_q = statistics.mean(s["qualities"]) if s["qualities"] else 0
        avg_tok = statistics.mean(s["tok_per_sec"]) if s["tok_per_sec"] else 0
        total = s["ok"] + s["fail"]
        # Composite score: quality * 0.5 + speed_normalized * 0.3 + reliability * 0.2
        speed_score = min(100, avg_tok * 2)  # 50 tok/s = 100
        reliability = (s["ok"] / total * 100) if total > 0 else 0
        composite = avg_q * 0.5 + speed_score * 0.3 + reliability * 0.2
        rankings.append((n, avg_t, avg_q, avg_tok, s["ok"], total, composite))
        print(f"{n:<25s} {avg_t:>7.1f}s {avg_q:>5.0f} {avg_tok:>9.1f} {s['ok']:>3d}/{total:<3d}   {composite:>6.1f}")

    # Best per category
    print(f"\n{'='*80}")
    print(f"  BEST NODE PER CATEGORY")
    print(f"{'='*80}")
    categories = set(r["category"] for r in results)
    routing_table = {}
    for cat in sorted(categories):
        cat_results = [r for r in results if r["category"] == cat and r["ok"]]
        if not cat_results:
            print(f"\n  {cat}: NO RESULTS")
            continue
        # Sort by quality desc, then speed
        best = sorted(cat_results, key=lambda x: (-x["quality"], x["time_s"]))
        print(f"\n  {cat.upper()}:")
        for i, b in enumerate(best[:3]):
            marker = " <<< BEST" if i == 0 else ""
            print(f"    {i+1}. {b['node']:<25s} Q={b['quality']:>3d}  {b['time_s']:>5.1f}s  {b['tok_per_sec']:>5.1f} tok/s{marker}")
        routing_table[cat] = best[0]["node"]

    # Optimal routing
    print(f"\n{'='*80}")
    print(f"  OPTIMAL ROUTING TABLE")
    print(f"{'='*80}")
    for cat, node in routing_table.items():
        print(f"  {cat:<15s} -> {node}")

    # Save results
    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_time_s": round(t_total, 1),
        "total_tests": len(results),
        "results": results,
        "rankings": [{"node": r[0], "avg_time": r[1], "avg_quality": r[2], "avg_tok_s": r[3], "ok": r[4], "total": r[5], "score": r[6]} for r in sorted(rankings, key=lambda x: -x[6])],
        "routing_table": routing_table,
    }
    out_path = "F:/BUREAU/turbo/data/cluster_benchmark_distributed.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Results saved to {out_path}")

    return output


if __name__ == "__main__":
    nodes_filter = None
    if "--nodes" in sys.argv:
        idx = sys.argv.index("--nodes")
        nodes_filter = sys.argv[idx + 1].split(",") if idx + 1 < len(sys.argv) else None
    asyncio.run(run_benchmark(nodes_filter=nodes_filter))
