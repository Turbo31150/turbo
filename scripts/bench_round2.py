#!/usr/bin/env python3
"""Benchmark Round 2 — Corrections: Gemini direct, M2 extraction, sequential heavy models"""
import asyncio, httpx, time, json, os
from datetime import datetime

M1 = "http://127.0.0.1:1234/api/v1/chat"
M2 = "http://192.168.1.26:1234/api/v1/chat"
OL1 = "http://127.0.0.1:11434/api/chat"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GEMINI_KEY = "GEMINI_KEY_REDACTED"
TIMEOUT = 90
RESULTS = []

SCENARIOS = {
    "code": "Ecris une fonction Python Dijkstra pour graphe pondere. Types + exemple.",
    "reasoning": "3 poules, 2 oeufs/jour chacune, combien en 2 semaines? Raisonne etape par etape.",
    "general": "Difference TCP vs UDP en 5 phrases.",
    "refactor": "Refactore: def f(l): r=[]; [r.append(x) for x in l if x not in r]; return r",
    "debug": "Ce code plante: d={'a':1}; print(d['b']). Pourquoi et comment fixer?",
}

async def bench_lm(client, node, url, model, prompt, auth=None):
    headers = {"Content-Type": "application/json"}
    if auth: headers["Authorization"] = f"Bearer {auth}"
    prefix = "/nothink\n" if "qwen" in model.lower() and "deepseek" not in model.lower() else ""
    body = {"model": model, "input": f"{prefix}{prompt}", "temperature": 0.2,
            "max_output_tokens": 1024, "stream": False, "store": False}
    t0 = time.perf_counter()
    try:
        r = await client.post(url, json=body, headers=headers, timeout=TIMEOUT)
        dt = time.perf_counter() - t0
        d = r.json()
        # Extract: last message block content (skip reasoning blocks)
        content = ""
        for o in d.get("output", []):
            if o.get("type") == "message":
                c = o.get("content", "")
                if isinstance(c, str):
                    content = c
                elif isinstance(c, list):
                    content = " ".join(part.get("text", "") for part in c if isinstance(part, dict))
            elif o.get("type") == "reasoning" and not content:
                # For reasoning models, capture reasoning as content if no message
                c = o.get("content", "")
                if isinstance(c, list):
                    content = " ".join(part.get("text", "") for part in c if isinstance(part, dict))
                elif isinstance(c, str):
                    content = c
        toks = d.get("usage", {}).get("output_tokens", max(1, len(content.split())))
        return {"node": node, "model": model, "ok": True, "dt": round(dt, 2),
                "toks": toks, "tps": round(toks/dt, 1) if dt > 0 else 0,
                "chars": len(content), "preview": content[:120]}
    except Exception as e:
        return {"node": node, "model": model, "ok": False, "dt": round(time.perf_counter()-t0, 2),
                "toks": 0, "tps": 0, "chars": 0, "preview": f"{type(e).__name__}: {e}"[:100]}

async def bench_ollama(client, node, model, prompt):
    is_cloud = "cloud" in model
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False}
    if is_cloud: body["think"] = False
    t0 = time.perf_counter()
    try:
        r = await client.post(OL1, json=body, timeout=TIMEOUT)
        dt = time.perf_counter() - t0
        d = r.json()
        if d.get("StatusCode") == 429:
            return {"node": node, "model": model, "ok": False, "dt": round(dt, 2),
                    "toks": 0, "tps": 0, "chars": 0, "preview": "429 RATE LIMITED"}
        content = d.get("message", {}).get("content", "")
        toks = d.get("eval_count", max(1, len(content.split())))
        ed = d.get("eval_duration", 0)
        tps = toks / (ed/1e9) if ed > 0 else (toks/dt if dt > 0 else 0)
        return {"node": node, "model": model, "ok": True, "dt": round(dt, 2),
                "toks": toks, "tps": round(tps, 1), "chars": len(content), "preview": content[:120]}
    except Exception as e:
        return {"node": node, "model": model, "ok": False, "dt": round(time.perf_counter()-t0, 2),
                "toks": 0, "tps": 0, "chars": 0, "preview": f"{type(e).__name__}: {e}"[:100]}

async def bench_gemini(client, model, prompt):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {GEMINI_KEY}"}
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024}
    t0 = time.perf_counter()
    try:
        r = await client.post(GEMINI, json=body, headers=headers, timeout=TIMEOUT)
        dt = time.perf_counter() - t0
        d = r.json()
        content = d.get("choices", [{}])[0].get("message", {}).get("content", "")
        toks = d.get("usage", {}).get("completion_tokens", max(1, len(content.split())))
        return {"node": "GEMINI", "model": model, "ok": bool(content), "dt": round(dt, 2),
                "toks": toks, "tps": round(toks/dt, 1) if dt > 0 else 0,
                "chars": len(content), "preview": content[:120]}
    except Exception as e:
        return {"node": "GEMINI", "model": model, "ok": False, "dt": round(time.perf_counter()-t0, 2),
                "toks": 0, "tps": 0, "chars": 0, "preview": f"{type(e).__name__}: {e}"[:100]}

async def run_scenario(sc_name, prompt):
    print(f"\n{'='*70}")
    print(f"  {sc_name.upper()}")
    print(f"{'='*70}")
    async with httpx.AsyncClient() as c:
        # Wave 1: Fast models in parallel
        wave1 = await asyncio.gather(
            bench_lm(c, "M1", M1, "qwen3-8b", prompt),
            bench_ollama(c, "OL1", "qwen3:1.7b", prompt),
            bench_gemini(c, "gemini-2.5-flash", prompt),
            bench_gemini(c, "gemini-2.5-pro", prompt),
            bench_ollama(c, "OL1-cloud", "glm-4.7:cloud", prompt),
            bench_ollama(c, "OL1-cloud", "deepseek-v3.2:cloud", prompt),
            bench_ollama(c, "OL1-cloud", "qwen3-next:80b-cloud", prompt),
            return_exceptions=True,
        )
        # Wave 2: Heavy models (sequential to avoid GPU contention)
        wave2_m2 = await bench_lm(c, "M2", M2, "deepseek/deepseek-r1-0528-qwen3-8b", prompt)
        wave2_ol14 = await bench_ollama(c, "OL1", "qwen3:14b", prompt)

    all_results = []
    for r in list(wave1) + [wave2_m2, wave2_ol14]:
        if isinstance(r, Exception):
            r = {"node": "?", "model": "?", "ok": False, "dt": 0, "toks": 0, "tps": 0, "chars": 0, "preview": str(r)[:100]}
        r["scenario"] = sc_name
        all_results.append(r)
        st = "OK" if r["ok"] else "FAIL"
        print(f"  [{st:4}] {r['node']:10} {r['model']:30} | {r['dt']:5.1f}s | {r['tps']:6.1f} t/s | {r['chars']:5}ch | {r['preview'][:60]}")

    RESULTS.extend(all_results)

async def main():
    print(f"BENCHMARK ROUND 2 — {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"5 scenarios x 9 models = ~45 requests (wave parallel + sequential)")
    t0 = time.perf_counter()

    for name, prompt in SCENARIOS.items():
        await run_scenario(name, prompt)

    total = time.perf_counter() - t0

    # Rankings
    stats = {}
    for r in RESULTS:
        if not r["ok"]: continue
        k = f"{r['node']}/{r['model']}"
        stats.setdefault(k, []).append(r)

    print(f"\n{'='*70}")
    print(f"  CLASSEMENT (avg sur scenarios reussis)")
    print(f"{'='*70}")
    ranked = []
    for k, rs in stats.items():
        n = len(rs)
        avg_dt = sum(r["dt"] for r in rs)/n
        avg_tps = sum(r["tps"] for r in rs)/n
        avg_ch = sum(r["chars"] for r in rs)/n
        speed = min(100, avg_tps * 1.5)
        quality = min(100, avg_ch / 8)
        score = speed * 0.4 + quality * 0.6
        ranked.append({"model": k, "n": n, "avg_dt": avg_dt, "avg_tps": avg_tps,
                       "avg_ch": avg_ch, "speed": speed, "quality": quality, "score": score})
    ranked.sort(key=lambda x: (-x["n"], -x["score"]))

    print(f"  {'#':3} {'Model':40} {'N':2} {'Lat':5} {'T/s':6} {'Chars':5} {'Spd':4} {'Qly':4} {'Score':5}")
    for i, r in enumerate(ranked, 1):
        print(f"  {i:3} {r['model']:40} {r['n']:2} {r['avg_dt']:5.1f} {r['avg_tps']:6.1f} {r['avg_ch']:5.0f} {r['speed']:4.0f} {r['quality']:4.0f} {r['score']:5.1f}")

    ok = sum(1 for r in RESULTS if r["ok"])
    fail = sum(1 for r in RESULTS if not r["ok"])
    print(f"\n  Total: {len(RESULTS)} req | OK: {ok} | FAIL: {fail} | Duree: {total:.0f}s")

    report = {"ts": datetime.now().isoformat(), "total_s": round(total, 1),
              "ok": ok, "fail": fail, "rankings": ranked, "details": RESULTS}
    out = "F:/BUREAU/turbo/data/bench_round2.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Sauvegarde: {out}")
    return report

if __name__ == "__main__":
    asyncio.run(main())
