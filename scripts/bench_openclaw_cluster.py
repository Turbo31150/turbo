#!/usr/bin/env python3
"""Benchmark OpenClaw Cluster — Speed/Quality/Distribution Test
Teste tous les noeuds disponibles en parallele, mesure tok/s, latence, qualite.
Scenarios: code, reasoning, general, web search.
"""
import asyncio, httpx, time, json, sys, os
from datetime import datetime

# === CONFIG ===
M1_URL = "http://127.0.0.1:1234/api/v1/chat"
M2_URL = "http://192.168.1.26:1234/api/v1/chat"
M3_URL = "http://192.168.1.113:1234/api/v1/chat"
OL1_URL = "http://127.0.0.1:11434/api/chat"
GEMINI_PROXY = "http://127.0.0.1:18791/v1beta/openai/chat/completions"
GEMINI_KEY = "GEMINI_KEY_REDACTED"

TIMEOUT = 60
RESULTS = []

# === PROMPTS PAR SCENARIO ===
SCENARIOS = {
    "code": "Ecris une fonction Python qui trouve le plus court chemin dans un graphe pondere avec Dijkstra. Inclus les types et un exemple.",
    "reasoning": "Un fermier a 3 poules. Chaque poule pond 2 oeufs par jour. Combien d'oeufs en 2 semaines? Montre ton raisonnement etape par etape.",
    "general": "Explique la difference entre TCP et UDP en 5 phrases concises.",
    "web_search": "Quels sont les 3 frameworks Python les plus populaires en 2026 et pourquoi?",
    "refactor": "Refactore ce code: def f(l): r=[]; [r.append(x) for x in l if x not in r]; return r. Rends-le idiomatique Python.",
}

async def test_lmstudio(client, name, url, model, prompt, auth_key=None):
    """Test LM Studio node (M1/M2/M3)"""
    headers = {"Content-Type": "application/json"}
    if auth_key:
        headers["Authorization"] = f"Bearer {auth_key}"

    prefix = "/nothink\n" if "qwen" in model and "deepseek" not in model else ""
    body = {
        "model": model,
        "input": f"{prefix}{prompt}",
        "temperature": 0.2,
        "max_output_tokens": 1024,
        "stream": False,
        "store": False,
    }

    t0 = time.perf_counter()
    try:
        resp = await client.post(url, json=body, headers=headers, timeout=TIMEOUT)
        elapsed = time.perf_counter() - t0
        data = resp.json()

        # Extract content from output
        msgs = [o for o in data.get("output", []) if o.get("type") == "message"]
        content = ""
        if msgs:
            c = msgs[-1].get("content", "")
            content = c if isinstance(c, str) else json.dumps(c)

        tokens = data.get("usage", {}).get("output_tokens", len(content.split()))
        tok_s = tokens / elapsed if elapsed > 0 else 0

        return {
            "node": name, "model": model, "status": "OK",
            "latency_s": round(elapsed, 2), "tokens": tokens,
            "tok_s": round(tok_s, 1), "content_len": len(content),
            "content_preview": content[:150],
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "node": name, "model": model, "status": f"FAIL:{type(e).__name__}",
            "latency_s": round(elapsed, 2), "tokens": 0, "tok_s": 0,
            "content_len": 0, "content_preview": str(e)[:100],
        }

async def test_ollama(client, name, model, prompt):
    """Test Ollama node (local or cloud)"""
    is_cloud = "cloud" in model
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if is_cloud:
        body["think"] = False

    t0 = time.perf_counter()
    try:
        resp = await client.post(OL1_URL, json=body, timeout=TIMEOUT)
        elapsed = time.perf_counter() - t0
        data = resp.json()

        if data.get("StatusCode") == 429:
            return {
                "node": name, "model": model, "status": "RATE_LIMITED",
                "latency_s": round(elapsed, 2), "tokens": 0, "tok_s": 0,
                "content_len": 0, "content_preview": data.get("error", "429"),
            }

        content = data.get("message", {}).get("content", "")
        tokens = data.get("eval_count", len(content.split()))
        eval_dur = data.get("eval_duration", 0)
        tok_s = (tokens / (eval_dur / 1e9)) if eval_dur > 0 else (tokens / elapsed if elapsed > 0 else 0)

        return {
            "node": name, "model": model, "status": "OK",
            "latency_s": round(elapsed, 2), "tokens": tokens,
            "tok_s": round(tok_s, 1), "content_len": len(content),
            "content_preview": content[:150],
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "node": name, "model": model, "status": f"FAIL:{type(e).__name__}",
            "latency_s": round(elapsed, 2), "tokens": 0, "tok_s": 0,
            "content_len": 0, "content_preview": str(e)[:100],
        }

async def test_gemini(client, model, prompt):
    """Test Gemini via proxy"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GEMINI_KEY}",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    }

    t0 = time.perf_counter()
    try:
        resp = await client.post(GEMINI_PROXY, json=body, headers=headers, timeout=TIMEOUT)
        elapsed = time.perf_counter() - t0
        data = resp.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        tokens = data.get("usage", {}).get("completion_tokens", len(content.split()))
        tok_s = tokens / elapsed if elapsed > 0 else 0

        return {
            "node": "GEMINI", "model": model, "status": "OK",
            "latency_s": round(elapsed, 2), "tokens": tokens,
            "tok_s": round(tok_s, 1), "content_len": len(content),
            "content_preview": content[:150],
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "node": "GEMINI", "model": model, "status": f"FAIL:{type(e).__name__}",
            "latency_s": round(elapsed, 2), "tokens": 0, "tok_s": 0,
            "content_len": 0, "content_preview": str(e)[:100],
        }

async def run_scenario(scenario_name, prompt):
    """Run one scenario across all available nodes in parallel"""
    print(f"\n{'='*60}")
    print(f"  SCENARIO: {scenario_name.upper()}")
    print(f"{'='*60}")

    async with httpx.AsyncClient() as client:
        tasks = [
            # M1 models
            test_lmstudio(client, "M1", M1_URL, "qwen3-8b", prompt),
            test_lmstudio(client, "M1", M1_URL, "gpt-oss-20b", prompt),
            # M2
            test_lmstudio(client, "M2", M2_URL, "deepseek/deepseek-r1-0528-qwen3-8b", prompt),
            # Ollama local
            test_ollama(client, "OL1-local", "qwen3:1.7b", prompt),
            test_ollama(client, "OL1-local", "qwen3:14b", prompt),
            # Ollama cloud (test a few key ones)
            test_ollama(client, "OL1-cloud", "gpt-oss:120b-cloud", prompt),
            test_ollama(client, "OL1-cloud", "devstral-2:123b-cloud", prompt),
            test_ollama(client, "OL1-cloud", "deepseek-v3.2:cloud", prompt),
            test_ollama(client, "OL1-cloud", "glm-4.7:cloud", prompt),
            test_ollama(client, "OL1-cloud", "qwen3-next:80b-cloud", prompt),
            # Gemini
            test_gemini(client, "models/gemini-2.5-flash", prompt),
            # M3 (likely offline but try)
            test_lmstudio(client, "M3", M3_URL, "deepseek/deepseek-r1-0528-qwen3-8b", prompt),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        scenario_results = []
        for r in results:
            if isinstance(r, Exception):
                r = {"node": "?", "model": "?", "status": f"EXCEPTION:{type(r).__name__}",
                     "latency_s": 0, "tokens": 0, "tok_s": 0, "content_len": 0, "content_preview": str(r)[:100]}
            r["scenario"] = scenario_name
            scenario_results.append(r)

            status_icon = "OK" if r["status"] == "OK" else ("LIM" if "RATE" in r["status"] else "FAIL")
            print(f"  [{status_icon:4}] {r['node']:10} {r['model']:35} | {r['latency_s']:5.1f}s | {r['tok_s']:6.1f} tok/s | {r['content_len']:5} chars")

        RESULTS.extend(scenario_results)
        return scenario_results

def compute_rankings(results):
    """Compute overall rankings by node/model"""
    scores = {}
    for r in results:
        if r["status"] != "OK":
            continue
        key = f"{r['node']}/{r['model']}"
        if key not in scores:
            scores[key] = {"ok": 0, "total_latency": 0, "total_toks": 0, "total_content": 0, "scenarios": []}
        scores[key]["ok"] += 1
        scores[key]["total_latency"] += r["latency_s"]
        scores[key]["total_toks"] += r["tok_s"]
        scores[key]["total_content"] += r["content_len"]
        scores[key]["scenarios"].append(r["scenario"])

    ranked = []
    for key, s in scores.items():
        avg_latency = s["total_latency"] / s["ok"]
        avg_toks = s["total_toks"] / s["ok"]
        avg_content = s["total_content"] / s["ok"]
        # Score: speed * quality proxy (content richness)
        speed_score = min(100, avg_toks * 2)
        quality_score = min(100, avg_content / 5)
        combined = speed_score * 0.4 + quality_score * 0.6
        ranked.append({
            "model": key, "ok": s["ok"], "avg_latency": round(avg_latency, 2),
            "avg_toks": round(avg_toks, 1), "avg_content": round(avg_content),
            "speed_score": round(speed_score, 1), "quality_score": round(quality_score, 1),
            "combined_score": round(combined, 1), "scenarios": s["scenarios"],
        })

    ranked.sort(key=lambda x: x["combined_score"], reverse=True)
    return ranked

async def main():
    print(f"{'#'*60}")
    print(f"  BENCHMARK OPENCLAW CLUSTER — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Scenarios: {len(SCENARIOS)} | Nodes: M1+M2+M3+OL1+Gemini")
    print(f"  Models: ~12 par scenario | Total: ~{len(SCENARIOS)*12} requests")
    print(f"{'#'*60}")

    t_start = time.perf_counter()

    for name, prompt in SCENARIOS.items():
        await run_scenario(name, prompt)

    total_time = time.perf_counter() - t_start

    # Rankings
    ranked = compute_rankings(RESULTS)

    print(f"\n{'='*60}")
    print(f"  CLASSEMENT FINAL (Score = 40% vitesse + 60% qualite)")
    print(f"{'='*60}")
    print(f"  {'#':3} {'Model':40} {'OK':3} {'Lat':5} {'Tok/s':6} {'Chars':5} {'Score':5}")
    print(f"  {'-'*70}")
    for i, r in enumerate(ranked[:15], 1):
        print(f"  {i:3} {r['model']:40} {r['ok']:3} {r['avg_latency']:5.1f} {r['avg_toks']:6.1f} {r['avg_content']:5} {r['combined_score']:5.1f}")

    # Summary
    ok_count = sum(1 for r in RESULTS if r["status"] == "OK")
    fail_count = sum(1 for r in RESULTS if "FAIL" in r["status"])
    rate_limited = sum(1 for r in RESULTS if "RATE" in r["status"])

    print(f"\n  Total: {len(RESULTS)} requests | OK: {ok_count} | FAIL: {fail_count} | RATE_LIMITED: {rate_limited}")
    print(f"  Duree totale: {total_time:.1f}s")

    # Save results
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_time_s": round(total_time, 1),
        "total_requests": len(RESULTS),
        "ok": ok_count, "fail": fail_count, "rate_limited": rate_limited,
        "rankings": ranked,
        "details": RESULTS,
    }

    outpath = "F:/BUREAU/turbo/data/bench_openclaw_cluster.json"
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Rapport sauvegarde: {outpath}")

    return report

if __name__ == "__main__":
    report = asyncio.run(main())
