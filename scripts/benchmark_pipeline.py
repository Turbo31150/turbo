"""JARVIS Benchmark Pipeline — Massive parallel request simulation.

Flow per request:
  1. Telegram-style message arrives
  2. gpt-oss-20b classifies intent + formats structured prompt
  3. qwen3-8b generates the response
  4. OpenClaw routes to agent + executes tools if needed
  5. Response sent to Telegram + Electron WS

Usage:
    uv run python scripts/benchmark_pipeline.py [--count 20] [--parallel 3]
"""

import asyncio
import json
import time
import sys
import os
import argparse
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Config ──────────────────────────────────────────────────────────────

M1_URL = "http://127.0.0.1:1234"
OL1_URL = "http://127.0.0.1:11434"
WS_URL = "http://127.0.0.1:9742"
OPENCLAW_URL = "http://127.0.0.1:18789"

# Simulated Telegram messages — diverse intent types
TELEGRAM_MESSAGES = [
    # Code
    "Ecris une fonction Python qui trie une liste par fréquence d'éléments",
    "Corrige ce bug: TypeError: 'NoneType' object is not subscriptable dans parser.py",
    "Refactorise cette classe pour utiliser le pattern Strategy",
    "Crée un endpoint FastAPI POST /api/tasks avec validation Pydantic",
    # Trading
    "Analyse BTC/USDT sur les 4 dernières heures, tendance ?",
    "Quel est le score trading actuel pour SOL ?",
    "Scan des paires avec momentum > 70",
    # Système
    "Status du cluster JARVIS",
    "Quelle est la température des GPUs ?",
    "Combien de mémoire RAM disponible ?",
    # Questions
    "Explique les circuit breakers dans les systèmes distribués",
    "Quelle est la différence entre async et threading en Python ?",
    "Comment fonctionne le consensus Raft ?",
    # Créatif
    "Génère un nom de projet pour une app de suivi fitness IA",
    "Rédige un commit message pour: ajout du GPU Guardian avec auto-unload",
    # Architecture
    "Propose une architecture microservices pour un système de trading",
    "Comment optimiser les requêtes SQLite avec WAL mode ?",
    # Debug
    "Mon serveur FastAPI timeout après 30s, comment diagnostiquer ?",
    "Pourquoi asyncio.create_subprocess_exec ouvre des fenêtres sur Windows ?",
    # Rapide
    "Quelle heure est-il ?",
    "Ping",
    "Version de Python installée ?",
    # Actions
    "Envoie un message Telegram: Benchmark en cours",
    "Liste les fichiers dans F:/BUREAU/turbo/src/",
    "Vérifie si le port 9742 est ouvert",
]


async def step1_classify_oss20b(client: httpx.AsyncClient, message: str) -> dict:
    """gpt-oss-20b classifies intent and formats for qwen3-8b."""
    system_prompt = (
        "Tu es un routeur IA. Analyse le message utilisateur et retourne un JSON:\n"
        '{"intent": "code|trading|system|question|creative|architecture|debug|quick|action",'
        ' "complexity": "simple|medium|complex",'
        ' "formatted_prompt": "prompt optimisé pour qwen3-8b",'
        ' "openclaw_agent": "agent OpenClaw recommandé ou null",'
        ' "needs_tools": true/false}\n'
        "Réponds UNIQUEMENT en JSON valide, rien d'autre."
    )
    try:
        resp = await client.post(
            f"{M1_URL}/v1/chat/completions",
            json={
                "model": "gpt-oss-20b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                "max_tokens": 300,
                "temperature": 0.1,
                "stream": False,
            },
            timeout=60,
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        # Extract JSON from response
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
        return {"intent": "question", "complexity": "simple",
                "formatted_prompt": message, "openclaw_agent": None, "needs_tools": False}
    except Exception as e:
        return {"intent": "unknown", "error": str(e), "formatted_prompt": message,
                "openclaw_agent": None, "needs_tools": False}


async def step2_generate_qwen(client: httpx.AsyncClient, classified: dict) -> str:
    """qwen3-8b generates the actual response."""
    prompt = classified.get("formatted_prompt", "")
    try:
        resp = await client.post(
            f"{M1_URL}/v1/chat/completions",
            json={
                "model": "qwen3-8b",
                "messages": [
                    {"role": "system", "content": "/nothink\nTu es JARVIS, assistant IA. Réponds de façon concise et utile."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 512,
                "temperature": 0.3,
                "stream": False,
            },
            timeout=60,
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[ERREUR qwen3-8b] {e}"


async def step3_openclaw_route(client: httpx.AsyncClient, message: str, classified: dict) -> dict:
    """Route through OpenClaw bridge for agent matching."""
    try:
        from src.openclaw_bridge import route_message
        result = route_message(message)
        return {
            "agent": result.get("agent", "unknown"),
            "confidence": result.get("confidence", 0),
            "intent": result.get("intent", "unknown"),
        }
    except Exception as e:
        return {"agent": "fallback", "error": str(e)}


async def step4_send_telegram(client: httpx.AsyncClient, message: str, response: str) -> dict:
    """Send response to Telegram via WS API."""
    try:
        resp = await client.post(
            f"{WS_URL}/api/telegram",
            json={
                "action": "send_message",
                "text": f"[Benchmark]\n\nQ: {message[:80]}\n\nR: {response[:500]}",
            },
            timeout=10,
        )
        return {"sent": resp.status_code == 200, "status": resp.status_code}
    except Exception as e:
        return {"sent": False, "error": str(e)}


async def step5_send_electron(client: httpx.AsyncClient, message: str, response: str, meta: dict) -> dict:
    """Send to Electron via WS event stream."""
    try:
        resp = await client.post(
            f"{WS_URL}/api/chat",
            json={
                "message": message,
                "response": response[:500],
                "metadata": meta,
                "source": "benchmark",
            },
            timeout=10,
        )
        return {"sent": resp.status_code == 200}
    except Exception:
        return {"sent": False}


async def run_single(client: httpx.AsyncClient, idx: int, message: str,
                     send_telegram: bool = True) -> dict:
    """Run full pipeline for one message."""
    t0 = time.time()
    result = {
        "idx": idx,
        "message": message[:60],
        "steps": {},
        "success": True,
    }

    # Step 1: Classify with gpt-oss-20b
    t1 = time.time()
    classified = await step1_classify_oss20b(client, message)
    result["steps"]["1_classify"] = {
        "ms": round((time.time() - t1) * 1000),
        "intent": classified.get("intent", "?"),
        "complexity": classified.get("complexity", "?"),
        "agent": classified.get("openclaw_agent"),
    }

    # Step 2: Generate with qwen3-8b
    t2 = time.time()
    response = await step2_generate_qwen(client, classified)
    result["steps"]["2_generate"] = {
        "ms": round((time.time() - t2) * 1000),
        "length": len(response),
        "preview": response[:100],
    }

    # Step 3: OpenClaw routing
    t3 = time.time()
    ocl = await step3_openclaw_route(client, message, classified)
    result["steps"]["3_openclaw"] = {
        "ms": round((time.time() - t3) * 1000),
        **ocl,
    }

    # Step 4: Telegram
    if send_telegram:
        t4 = time.time()
        tg = await step4_send_telegram(client, message, response)
        result["steps"]["4_telegram"] = {"ms": round((time.time() - t4) * 1000), **tg}
    else:
        result["steps"]["4_telegram"] = {"skipped": True}

    # Step 5: Electron
    t5 = time.time()
    el = await step5_send_electron(client, message, response, {
        "intent": classified.get("intent"),
        "agent": ocl.get("agent"),
    })
    result["steps"]["5_electron"] = {"ms": round((time.time() - t5) * 1000), **el}

    result["total_ms"] = round((time.time() - t0) * 1000)
    result["success"] = "error" not in str(classified) and "[ERREUR" not in response
    return result


async def run_benchmark(count: int = 20, parallel: int = 3,
                        send_telegram: bool = True) -> dict:
    """Run full benchmark with parallel batches."""
    print(f"\n{'='*70}")
    print(f"  JARVIS BENCHMARK — {count} requêtes, {parallel} parallèles")
    print(f"  Pipeline: Telegram -> oss-20b -> qwen3-8b -> OpenClaw -> Telegram+Electron")
    print(f"{'='*70}\n")

    # Select messages (cycle through if count > len)
    messages = [TELEGRAM_MESSAGES[i % len(TELEGRAM_MESSAGES)] for i in range(count)]

    results = []
    t_start = time.time()

    async with httpx.AsyncClient() as client:
        # Process in batches of `parallel`
        for batch_start in range(0, count, parallel):
            batch_end = min(batch_start + parallel, count)
            batch = messages[batch_start:batch_end]
            batch_indices = list(range(batch_start, batch_end))

            tasks = [
                run_single(client, idx, msg, send_telegram)
                for idx, msg in zip(batch_indices, batch)
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in batch_results:
                if isinstance(r, Exception):
                    results.append({"success": False, "error": str(r)})
                    print(f"  FAIL Exception: {r}")
                else:
                    results.append(r)
                    status = "OK" if r["success"] else "FAIL"
                    intent = r["steps"].get("1_classify", {}).get("intent", "?")
                    agent = r["steps"].get("3_openclaw", {}).get("agent", "?")
                    total = r["total_ms"]
                    t1 = r["steps"].get("1_classify", {}).get("ms", 0)
                    t2 = r["steps"].get("2_generate", {}).get("ms", 0)
                    print(f"  {status} [{r['idx']:>2}] {r['message'][:45]:45s} "
                          f"| {intent:10s} | {agent:20s} "
                          f"| oss:{t1:>5}ms qwen:{t2:>5}ms total:{total:>6}ms")

            # Small delay between batches to avoid M1 saturation
            if batch_end < count:
                await asyncio.sleep(0.5)

    total_time = time.time() - t_start

    # Stats
    ok = [r for r in results if r.get("success")]
    fail = [r for r in results if not r.get("success")]
    times = [r["total_ms"] for r in ok if "total_ms" in r]
    classify_times = [r["steps"]["1_classify"]["ms"] for r in ok if "1_classify" in r.get("steps", {})]
    generate_times = [r["steps"]["2_generate"]["ms"] for r in ok if "2_generate" in r.get("steps", {})]

    # Intent distribution
    intents = {}
    agents = {}
    for r in ok:
        i = r.get("steps", {}).get("1_classify", {}).get("intent", "?")
        a = r.get("steps", {}).get("3_openclaw", {}).get("agent", "?")
        intents[i] = intents.get(i, 0) + 1
        agents[a] = agents.get(a, 0) + 1

    report = {
        "total_requests": count,
        "success": len(ok),
        "failed": len(fail),
        "success_rate": f"{len(ok)/max(1,count)*100:.1f}%",
        "total_time_s": round(total_time, 1),
        "throughput_rps": round(count / total_time, 2),
        "latency": {
            "avg_ms": round(sum(times) / max(1, len(times))),
            "min_ms": min(times) if times else 0,
            "max_ms": max(times) if times else 0,
            "p50_ms": sorted(times)[len(times)//2] if times else 0,
            "p95_ms": sorted(times)[int(len(times)*0.95)] if times else 0,
        },
        "classify_oss20b": {
            "avg_ms": round(sum(classify_times) / max(1, len(classify_times))),
            "min_ms": min(classify_times) if classify_times else 0,
            "max_ms": max(classify_times) if classify_times else 0,
        },
        "generate_qwen": {
            "avg_ms": round(sum(generate_times) / max(1, len(generate_times))),
            "min_ms": min(generate_times) if generate_times else 0,
            "max_ms": max(generate_times) if generate_times else 0,
        },
        "intent_distribution": intents,
        "agent_distribution": agents,
    }

    print(f"\n{'='*70}")
    print(f"  RÉSULTATS BENCHMARK")
    print(f"{'='*70}")
    print(f"  Requêtes: {report['success']}/{report['total_requests']} OK ({report['success_rate']})")
    print(f"  Temps total: {report['total_time_s']}s | Débit: {report['throughput_rps']} req/s")
    print(f"\n  Latence totale pipeline:")
    print(f"    avg={report['latency']['avg_ms']}ms  min={report['latency']['min_ms']}ms  "
          f"max={report['latency']['max_ms']}ms  p50={report['latency']['p50_ms']}ms  "
          f"p95={report['latency']['p95_ms']}ms")
    print(f"\n  gpt-oss-20b (classify):")
    print(f"    avg={report['classify_oss20b']['avg_ms']}ms  "
          f"min={report['classify_oss20b']['min_ms']}ms  "
          f"max={report['classify_oss20b']['max_ms']}ms")
    print(f"\n  qwen3-8b (generate):")
    print(f"    avg={report['generate_qwen']['avg_ms']}ms  "
          f"min={report['generate_qwen']['min_ms']}ms  "
          f"max={report['generate_qwen']['max_ms']}ms")
    print(f"\n  Intents: {json.dumps(intents, ensure_ascii=False)}")
    print(f"  Agents:  {json.dumps(agents, ensure_ascii=False)}")
    print(f"{'='*70}\n")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS Benchmark Pipeline")
    parser.add_argument("--count", type=int, default=20, help="Number of requests")
    parser.add_argument("--parallel", type=int, default=3, help="Parallel batch size")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram sending")
    args = parser.parse_args()

    asyncio.run(run_benchmark(
        count=args.count,
        parallel=args.parallel,
        send_telegram=not args.no_telegram,
    ))
