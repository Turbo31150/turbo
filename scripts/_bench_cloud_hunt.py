"""Benchmark massif: trouver le meilleur modele cloud Ollama pour le code."""
import sys, io, json, time, asyncio, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import httpx

# UN prompt exigeant qui teste tout: structure, logique, error handling, types
PROMPT = """Ecris en Python une classe ThreadSafeRateLimiter qui:
1. Accepte max_requests et window_seconds dans __init__
2. Methode acquire() qui retourne True si la requete est autorisee, False sinon
3. Utilise threading.Lock pour la thread-safety
4. Sliding window algorithm (pas fixed window)
5. Methode get_stats() qui retourne un dict avec requests_count, window_start, remaining
Code complet uniquement, pas d'explication."""

CHECKS = {
    "has_class": r"class\s+\w*RateLimiter",
    "has_init": r"def\s+__init__\s*\(self",
    "has_acquire": r"def\s+acquire\s*\(",
    "has_get_stats": r"def\s+get_stats\s*\(",
    "has_lock": r"(threading\.Lock|Lock\(\))",
    "has_max_requests": r"(max_requests|max_req|limit)",
    "has_window": r"(window|interval|period|seconds)",
    "has_time": r"(time\.|monotonic|perf_counter|time_ns)",
    "has_return_bool": r"return\s+(True|False)",
    "has_sliding": r"(filter|list comp|remove|pop|deque|timestamps|window)",
    "has_threading_import": r"import\s+threading|from\s+threading",
    "has_dict_return": r"(return\s*\{|dict\()",
}

CLOUD_MODELS = [
    "qwen3-coder:480b-cloud",
    "qwen3-coder-next:cloud",
    "qwen3.5:cloud",
    "qwen3-next:80b-cloud",
    "deepseek-v3.2:cloud",
    "devstral-2:123b-cloud",
    "gpt-oss:120b-cloud",
    "cogito-2.1:671b-cloud",
    "gemini-3-flash-preview:cloud",
    "glm-4.7:cloud",
]

async def test_model(client, model):
    t0 = time.perf_counter()
    try:
        resp = await client.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": PROMPT}],
                "stream": False, "think": False,
                "options": {"num_predict": 1024, "temperature": 0.1},
            },
            timeout=180.0,
        )
        elapsed = time.perf_counter() - t0
        data = resp.json()
        content = data.get("message", {}).get("content", "")

        if not content or len(content.strip()) < 20:
            return {"model": model, "ok": False, "time": round(elapsed, 1), "reason": "VIDE", "quality": 0}

        # Quality checks
        passed = 0
        missed = []
        for name, pat in CHECKS.items():
            if re.search(pat, content, re.IGNORECASE | re.DOTALL):
                passed += 1
            else:
                missed.append(name.replace("has_", ""))
        quality = round(passed / len(CHECKS) * 100)
        tokens = len(content.split()) * 1.3
        tps = round(tokens / elapsed, 1) if elapsed > 0 else 0

        return {
            "model": model, "ok": True, "time": round(elapsed, 1),
            "quality": quality, "passed": passed, "total": len(CHECKS),
            "missed": missed, "tokens": int(tokens), "tps": tps,
            "content_len": len(content),
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {"model": model, "ok": False, "time": round(elapsed, 1), "reason": str(e)[:60], "quality": 0}

async def main():
    print("=" * 75)
    print("  CHASSE AU MEILLEUR MODELE CLOUD — 10 candidats, 1 prompt exigeant")
    print(f"  {len(CHECKS)} criteres qualite | ThreadSafeRateLimiter sliding window")
    print("=" * 75)

    results = []
    async with httpx.AsyncClient() as client:
        # Run 3 at a time to avoid overloading
        for batch_start in range(0, len(CLOUD_MODELS), 3):
            batch = CLOUD_MODELS[batch_start:batch_start+3]
            print(f"\n  Batch {batch_start//3+1}: {', '.join(m.split(':')[0] for m in batch)}")
            batch_results = await asyncio.gather(*[test_model(client, m) for m in batch])
            for r in batch_results:
                results.append(r)
                name = r["model"].split(":")[0] if ":" in r["model"] else r["model"]
                if r["ok"]:
                    missed_str = ", ".join(r["missed"][:4]) if r["missed"] else "TOUS OK"
                    print(f"    {name:25s} | {r['time']:5.1f}s | {r['tps']:5.1f}tok/s | Q:{r['quality']:3d}% ({r['passed']}/{r['total']}) | {r['content_len']:4d}ch | miss: {missed_str}")
                else:
                    print(f"    {name:25s} | {r['time']:5.1f}s | FAIL: {r.get('reason','?')}")

    # Ranking
    print(f"\n{'='*75}")
    print(f"  CLASSEMENT (qualite*0.6 + vitesse*0.2 + richesse*0.2)")
    print(f"{'='*75}")

    scored = []
    for r in results:
        if not r["ok"]:
            scored.append((r["model"], 0, 0, 0, 0, r["time"], 0, False))
            continue
        q = r["quality"]
        speed = min(100, r["tps"] / 50 * 100)
        rich = min(100, r["content_len"] / 2000 * 100)
        composite = q * 0.6 + speed * 0.2 + rich * 0.2
        scored.append((r["model"], composite, q, speed, rich, r["time"], r["tps"], True))

    scored.sort(key=lambda x: x[1], reverse=True)

    print(f"  {'#':>2s} {'Modele':30s} | {'SCORE':>6s} | {'Q%':>4s} | {'V%':>4s} | {'R%':>4s} | {'Time':>5s} | {'tok/s':>5s}")
    print(f"  {'':2s} {'-'*30}-+-{'-'*6}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*5}-+-{'-'*5}")

    for i, (model, comp, q, v, r, t, tps, ok) in enumerate(scored):
        name = model.split(":")[0] if ":" in model else model
        tag = model.split(":")[-1] if ":" in model else ""
        display = f"{name}:{tag}" if tag else name
        if ok:
            medal = [">>>", "  >", "   "][min(i, 2)] if i < 3 else "   "
            print(f"  {medal} {display:30s} | {comp:5.1f} | {q:3.0f}% | {v:3.0f}% | {r:3.0f}% | {t:4.1f}s | {tps:4.1f}")
        else:
            print(f"     {display:30s} | FAIL  |     |     |     | {t:4.1f}s |")

    # Compare with M1
    print(f"\n  REFERENCE M1 qwen3-8b: SCORE 98.1 | Q:100% | V:91% | R:100% | 7.6s | 45.3tok/s")
    winner = scored[0]
    if winner[1] > 0:
        diff = winner[1] - 98.1
        print(f"  MEILLEUR CLOUD: {winner[0]} — {winner[1]:.1f}/100 ({'+'if diff>0 else ''}{diff:.1f} vs M1)")
    print(f"\n{'='*75}")

asyncio.run(main())
