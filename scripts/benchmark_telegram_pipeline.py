#!/usr/bin/env python3
"""Benchmark: Pipeline Telegram massif via M1 (gpt-oss-20b + qwen3-8b) + OpenClaw.

Architecture:
  1. gpt-oss-20b recoit et classifie la demande (intake/triage)
  2. qwen3-8b redige la reponse formatee (generation, /nothink)
  3. OpenClaw route vers l'agent optimal
  4. Reponse envoyee sur Telegram API direct + Electron WS

Usage:
  uv run python scripts/benchmark_telegram_pipeline.py
  uv run python scripts/benchmark_telegram_pipeline.py --batch 50 --parallel 3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import sys
from dataclasses import dataclass
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    import httpx
except ImportError:
    print("ERREUR: httpx requis. uv pip install httpx")
    sys.exit(1)

# ============================================================================
# CONFIG
# ============================================================================
M1_URL = "http://127.0.0.1:1234/v1/chat/completions"
WS_URL = "http://127.0.0.1:9742"

MODEL_INTAKE = "gpt-oss-20b"      # triage: classifie la demande (20B reasoning)
MODEL_RESPONSE = "qwen3-8b"       # redaction: genere la reponse (rapide, /nothink)

# Load .env
_env_path = _root / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT", "2010747443")

# Requetes simulees (comme si envoyees par Telegram)
TEST_REQUESTS = [
    # --- Cluster / Systeme ---
    "Quel est le statut du cluster ?",
    "Montre les temperatures GPU",
    "Combien de modeles sont charges sur M1 ?",
    "Fais un health check complet",
    "Quelle est la charge CPU et RAM ?",
    # --- Trading ---
    "Scan les top 10 cryptos pour un signal",
    "Quel est le prix du BTC ?",
    "Analyse technique SOL/USDT",
    "Resume les positions ouvertes",
    "Quels sont les signaux forts aujourd'hui ?",
    # --- Code / Dev ---
    "Liste les derniers commits git",
    "Combien de tests passent ?",
    "Montre les fichiers modifies recemment",
    "Quel est le nombre de modules dans src/ ?",
    "Explique le role de dispatch_engine.py",
    # --- Recherche / Web ---
    "Cherche les dernieres news sur l'IA",
    "Quel temps fait-il a Paris ?",
    "Resume les tendances crypto de la semaine",
    "Quelles sont les dernieres mises a jour de Claude ?",
    "Trouve la doc Azure sur les GPU VMs",
    # --- Actions / Automation ---
    "Cree une tache pour auditer la securite",
    "Envoie un rapport status sur Telegram",
    "Lance un backup de la base de donnees",
    "Planifie un scan trading dans 10 minutes",
    "Genere un rapport quotidien",
    # --- Conversation / Divers ---
    "Bonjour JARVIS, comment ca va ?",
    "Raconte-moi une blague sur les devs",
    "Quelle heure est-il ?",
    "Combien de jours depuis le dernier deploy ?",
    "Resume ce que tu as fait aujourd'hui",
]


@dataclass
class RequestResult:
    request: str
    category: str = ""
    response: str = ""
    agent: str = ""
    intent: str = ""
    intake_ms: float = 0
    generation_ms: float = 0
    delivery_ms: float = 0
    total_ms: float = 0
    tg_sent: bool = False
    success: bool = False
    error: str = ""


# ============================================================================
# PIPELINE STEPS
# ============================================================================

def _extract_content(data: dict) -> str:
    """Extract content from LM Studio response, handling reasoning + channel tokens."""
    if "choices" not in data:
        return data.get("error", {}).get("message", str(data)[:200])
    msg = data["choices"][0]["message"]
    content = msg.get("content", "") or ""
    # Strip gpt-oss special tokens: <|channel|>...<|message|>JSON
    import re as _re
    content = _re.sub(r"<\|[^|]+\|>[^{]*", "", content).strip()
    if not content:
        # Fallback: extract from reasoning field
        reasoning = msg.get("reasoning", "") or ""
        # Find last JSON in reasoning
        json_match = None
        for m in _re.finditer(r'\{[^{}]*"category"[^{}]*\}', reasoning):
            json_match = m.group()
        if json_match:
            return json_match
        return reasoning[-200:] if reasoning else ""
    return content.strip()


async def step1_intake(client: httpx.AsyncClient, request: str) -> tuple[str, str, float]:
    """gpt-oss-20b classifie la demande (triage, reasoning)."""
    t0 = time.perf_counter()
    resp = await client.post(M1_URL, json={
        "model": MODEL_INTAKE,
        "messages": [
            {"role": "system", "content": (
                "Tu es un routeur JARVIS. Classifie la demande en UNE categorie "
                "(cluster, trading, code, web, action, conversation) et extrais "
                "l'intent en 1 ligne. Format JSON: {\"category\": \"...\", \"intent\": \"...\", "
                "\"needs_tools\": true/false, \"response_format\": \"court/detaille\"}"
            )},
            {"role": "user", "content": request}
        ],
        "temperature": 0.1,
        "max_tokens": 200,
    }, timeout=90)
    elapsed = (time.perf_counter() - t0) * 1000
    data = resp.json()
    content = _extract_content(data)
    # Extract category from JSON in content
    category = "unknown"
    try:
        # Find JSON object in content
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(content[start:end])
            category = parsed.get("category", "unknown")
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    return content, category, elapsed


async def step2_generate(client: httpx.AsyncClient, request: str, intake_result: str) -> tuple[str, float]:
    """qwen3-8b redige la reponse (rapide, /nothink). Retry 1x si model swap."""
    payload = {
        "model": MODEL_RESPONSE,
        "messages": [
            {"role": "system", "content": (
                "/nothink\nTu es JARVIS, assistant IA. Reponds de facon concise et utile. "
                "Max 3-5 lignes. Format Telegram (pas de markdown complexe). "
                "Contexte classification: " + intake_result
            )},
            {"role": "user", "content": request}
        ],
        "temperature": 0.3,
        "max_tokens": 300,
    }
    t0 = time.perf_counter()
    for attempt in range(2):
        resp = await client.post(M1_URL, json=payload, timeout=90)
        data = resp.json()
        if "choices" in data:
            content = _extract_content(data)
            elapsed = (time.perf_counter() - t0) * 1000
            return content, elapsed
        # Model swap in progress, wait and retry
        if attempt == 0:
            await asyncio.sleep(2)
    # Last resort: return error info
    elapsed = (time.perf_counter() - t0) * 1000
    return f"[ERREUR] {data.get('error', {}).get('message', 'no choices')[:100]}", elapsed


def _openclaw_route(request: str) -> dict:
    """Route via OpenClaw bridge (sync, fast regex)."""
    try:
        from src.openclaw_bridge import get_bridge
        bridge = get_bridge()
        result = bridge.route(request)
        return {"agent": result.agent, "intent": result.intent,
                "confidence": result.confidence, "source": result.source}
    except Exception as e:
        return {"agent": "fallback", "error": str(e)}


async def step3_deliver(client: httpx.AsyncClient, request: str, response: str,
                        category: str) -> tuple[bool, dict, float]:
    """OpenClaw route + Telegram API direct + Electron WS push."""
    t0 = time.perf_counter()

    # 3a. OpenClaw routing (fast regex, <1ms)
    oc_info = _openclaw_route(request)

    # 3b. Telegram API direct
    tg_ok = False
    if TELEGRAM_TOKEN:
        try:
            tg_text = f"[{oc_info.get('agent', category)}] {response[:3800]}"
            tg_resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": tg_text},
                timeout=15,
            )
            tg_ok = tg_resp.status_code == 200
        except Exception:
            pass

    # 3c. Electron WS push (non-blocking, best-effort)
    try:
        await client.post(f"{WS_URL}/api/chat", json={
            "message": request[:200], "response": response[:500],
            "metadata": {"category": category, **oc_info}, "source": "benchmark",
        }, timeout=5)
    except Exception:
        pass

    elapsed = (time.perf_counter() - t0) * 1000
    return tg_ok, oc_info, elapsed


# ============================================================================
# BENCHMARK RUNNER (batch par modele pour eviter model swap ping-pong)
# ============================================================================

async def run_benchmark(batch_size: int = 30, parallel: int = 3, send_telegram: bool = True):
    requests = (TEST_REQUESTS * ((batch_size // len(TEST_REQUESTS)) + 1))[:batch_size]

    print("=" * 80)
    print(f"  BENCHMARK PIPELINE TELEGRAM -- {batch_size} requetes, parallelisme={parallel}")
    print(f"  Triage: {MODEL_INTAKE} | Redaction: {MODEL_RESPONSE}")
    print(f"  Delivery: Telegram API{'(ON)' if send_telegram and TELEGRAM_TOKEN else '(OFF)'} + Electron WS")
    print(f"  Mode: batch par modele (pas de model swap ping-pong)")
    print("=" * 80)
    print()

    if not TELEGRAM_TOKEN:
        print("[WARN] TELEGRAM_TOKEN non trouve dans .env, delivery Telegram OFF")

    # Warmup intake model
    print("[WARMUP] Chargement des modeles...")
    async with httpx.AsyncClient() as client:
        try:
            await client.post(M1_URL, json={
                "model": MODEL_INTAKE,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            }, timeout=120)
            print(f"  {MODEL_INTAKE}: OK")
        except Exception as e:
            print(f"  {MODEL_INTAKE}: ERREUR {e}")
    print()

    results: list[RequestResult] = [RequestResult(request=r) for r in requests]
    t_start = time.perf_counter()
    sem = asyncio.Semaphore(parallel)

    # ── PHASE 1: Tous les intakes (gpt-oss-20b) ──
    print(f"[PHASE 1] Triage x{batch_size} via {MODEL_INTAKE} (parallel={parallel})...")
    print("-" * 80)
    intake_results: list[tuple[str, str]] = [("", "")] * batch_size

    async def do_intake(idx: int) -> None:
        async with sem:
            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient() as client:
                    content, category, ms = await step1_intake(client, requests[idx])
                    intake_results[idx] = (content, category)
                    results[idx].category = category
                    results[idx].intake_ms = ms
                    print(f"  [{idx+1:2d}/{batch_size}] {ms:6.0f}ms | {category:12s} | {requests[idx][:55]}")
            except Exception as e:
                results[idx].intake_ms = (time.perf_counter() - t0) * 1000
                results[idx].error = f"intake: {e}"
                print(f"  [{idx+1:2d}/{batch_size}] ERREUR intake: {str(e)[:50]}")

    await asyncio.gather(*[do_intake(i) for i in range(batch_size)])
    t_phase1 = (time.perf_counter() - t_start) * 1000
    ok1 = sum(1 for c, _ in intake_results if c)
    print(f"\n  Phase 1 terminee: {ok1}/{batch_size} OK en {t_phase1/1000:.1f}s\n")

    # ── PHASE 2: Toutes les generations (qwen3-8b) ──
    print(f"[PHASE 2] Redaction x{ok1} via {MODEL_RESPONSE} (parallel={parallel})...")
    print("-" * 80)
    t_phase2_start = time.perf_counter()

    # Warmup qwen3-8b
    async with httpx.AsyncClient() as client:
        try:
            await client.post(M1_URL, json={
                "model": MODEL_RESPONSE,
                "messages": [{"role": "user", "content": "/nothink\nping"}],
                "max_tokens": 5,
            }, timeout=120)
        except Exception:
            pass

    async def do_generate(idx: int) -> None:
        content, category = intake_results[idx]
        if not content:
            return
        async with sem:
            try:
                async with httpx.AsyncClient() as client:
                    response, ms = await step2_generate(client, requests[idx], content)
                    results[idx].response = response
                    results[idx].generation_ms = ms
                    print(f"  [{idx+1:2d}/{batch_size}] {ms:6.0f}ms | {len(response):4d}c | {requests[idx][:55]}")
            except Exception as e:
                results[idx].error = f"gen: {e}"
                print(f"  [{idx+1:2d}/{batch_size}] ERREUR gen: {str(e)[:50]}")

    await asyncio.gather(*[do_generate(i) for i in range(batch_size)])
    t_phase2 = (time.perf_counter() - t_phase2_start) * 1000
    ok2 = sum(1 for r in results if r.response)
    print(f"\n  Phase 2 terminee: {ok2}/{ok1} OK en {t_phase2/1000:.1f}s\n")

    # ── PHASE 3: Delivery (OpenClaw route + Telegram + Electron) ──
    print(f"[PHASE 3] Delivery x{ok2} (OpenClaw route + Telegram + Electron)...")
    print("-" * 80)
    t_phase3_start = time.perf_counter()

    async def do_deliver(idx: int) -> None:
        if not results[idx].response:
            return
        async with sem:
            try:
                async with httpx.AsyncClient() as client:
                    tg_ok, oc_info, ms = await step3_deliver(
                        client, requests[idx], results[idx].response,
                        results[idx].category,
                    )
                    results[idx].delivery_ms = ms
                    results[idx].tg_sent = tg_ok
                    results[idx].agent = oc_info.get("agent", "")
                    results[idx].intent = oc_info.get("intent", "")
                    results[idx].success = True
                    results[idx].total_ms = results[idx].intake_ms + results[idx].generation_ms + ms
                    tg_str = "TG" if tg_ok else "noTG"
                    agent = oc_info.get("agent", "?")[:15]
                    print(f"  [{idx+1:2d}/{batch_size}] {ms:5.0f}ms | {tg_str:4s} | {agent:15s} | {requests[idx][:45]}")
            except Exception as e:
                results[idx].error = f"deliver: {e}"
                print(f"  [{idx+1:2d}/{batch_size}] ERREUR: {str(e)[:50]}")

    await asyncio.gather(*[do_deliver(i) for i in range(batch_size)])
    t_phase3 = (time.perf_counter() - t_phase3_start) * 1000
    tg_count = sum(1 for r in results if r.tg_sent)
    print(f"\n  Phase 3 terminee en {t_phase3/1000:.1f}s ({tg_count} Telegram envoyes)\n")

    t_total = (time.perf_counter() - t_start) * 1000

    # ========================================================================
    # RAPPORT
    # ========================================================================
    print()
    print("=" * 80)
    print("  RESULTATS BENCHMARK PIPELINE")
    print("=" * 80)

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    print(f"  Total:          {batch_size} requetes en {t_total/1000:.1f}s")
    print(f"  Succes:         {len(successes)}/{batch_size} ({100*len(successes)/batch_size:.0f}%)")
    print(f"  Echecs:         {len(failures)}")
    print(f"  Telegram sent:  {tg_count}/{batch_size}")
    print(f"  Debit:          {batch_size/(t_total/1000):.2f} req/s")
    print()

    avg_intake = avg_gen = avg_del = avg_total = p50 = p95 = 0.0
    if successes:
        avg_intake = sum(r.intake_ms for r in successes) / len(successes)
        avg_gen = sum(r.generation_ms for r in successes) / len(successes)
        avg_del = sum(r.delivery_ms for r in successes) / len(successes)
        avg_total = sum(r.total_ms for r in successes) / len(successes)
        sorted_totals = sorted(r.total_ms for r in successes)
        p50 = sorted_totals[len(sorted_totals) // 2]
        p95 = sorted_totals[int(len(sorted_totals) * 0.95)]

        print(f"  LATENCES (moyennes):")
        print(f"    Triage   ({MODEL_INTAKE}):  {avg_intake:7.0f}ms")
        print(f"    Redaction ({MODEL_RESPONSE}):     {avg_gen:7.0f}ms")
        print(f"    Delivery (OC+TG+WS):       {avg_del:7.0f}ms")
        print(f"    Total pipeline:             {avg_total:7.0f}ms")
        print(f"    P50:                        {p50:7.0f}ms")
        print(f"    P95:                        {p95:7.0f}ms")
        print()

        # Phase breakdown
        print(f"  PHASES:")
        print(f"    Phase 1 (triage):    {t_phase1/1000:6.1f}s")
        print(f"    Phase 2 (redaction): {t_phase2/1000:6.1f}s")
        print(f"    Phase 3 (delivery):  {t_phase3/1000:6.1f}s")
        print()

        # Categories breakdown
        cats: dict[str, list[RequestResult]] = {}
        for r in successes:
            cats.setdefault(r.category, []).append(r)
        print(f"  CATEGORIES:")
        for cat, items in sorted(cats.items(), key=lambda x: -len(x[1])):
            avg = sum(r.total_ms for r in items) / len(items)
            print(f"    {cat:15s}: {len(items):3d} req, {avg:.0f}ms moy")

        # Agents breakdown
        agents: dict[str, int] = {}
        for r in successes:
            agents[r.agent] = agents.get(r.agent, 0) + 1
        print(f"\n  AGENTS OPENCLAW:")
        for agent, count in sorted(agents.items(), key=lambda x: -x[1]):
            print(f"    {agent:20s}: {count:3d} req")

    if failures:
        print(f"\n  ERREURS ({len(failures)}):")
        for r in failures[:10]:
            print(f"    - {r.request[:40]}: {r.error[:60]}")

    # Send summary to Telegram
    if send_telegram and successes and TELEGRAM_TOKEN:
        summary = (
            f"BENCHMARK PIPELINE JARVIS\n"
            f"{'='*30}\n"
            f"{len(successes)}/{batch_size} OK | {t_total/1000:.1f}s total\n"
            f"Debit: {batch_size/(t_total/1000):.2f} req/s\n"
            f"Latence moy: {avg_total:.0f}ms\n"
            f"  triage={avg_intake:.0f}ms redact={avg_gen:.0f}ms delivery={avg_del:.0f}ms\n"
            f"P50={p50:.0f}ms P95={p95:.0f}ms\n"
            f"Telegram: {tg_count}/{batch_size} envoyes"
        )
        print(f"\n[TELEGRAM] Envoi du resume final...")
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": TELEGRAM_CHAT_ID, "text": summary},
                    timeout=10,
                )
                print("  Resume envoye sur Telegram!")
            except Exception as e:
                print(f"  Erreur Telegram: {e}")

    # Save results JSON
    report_path = _root / "data" / "benchmark_pipeline_results.json"
    report = {
        "timestamp": time.time(),
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "batch_size": batch_size, "parallel": parallel,
            "model_intake": MODEL_INTAKE, "model_response": MODEL_RESPONSE,
        },
        "summary": {
            "total_ms": round(t_total),
            "success_rate": round(len(successes) / batch_size, 3) if batch_size else 0,
            "throughput_rps": round(batch_size / (t_total / 1000), 2) if t_total else 0,
            "avg_latency_ms": round(avg_total),
            "p50_ms": round(p50), "p95_ms": round(p95),
            "telegram_sent": tg_count,
            "phase1_s": round(t_phase1 / 1000, 1),
            "phase2_s": round(t_phase2 / 1000, 1),
            "phase3_s": round(t_phase3 / 1000, 1),
        },
        "results": [
            {"request": r.request, "category": r.category, "agent": r.agent,
             "success": r.success, "tg_sent": r.tg_sent,
             "intake_ms": round(r.intake_ms), "generation_ms": round(r.generation_ms),
             "delivery_ms": round(r.delivery_ms), "total_ms": round(r.total_ms),
             "response_preview": r.response[:150], "error": r.error}
            for r in results
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Rapport sauvegarde: {report_path}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Benchmark pipeline Telegram JARVIS")
    parser.add_argument("--batch", type=int, default=30, help="Nombre de requetes (default: 30)")
    parser.add_argument("--parallel", type=int, default=3, help="Parallelisme max (default: 3)")
    parser.add_argument("--no-telegram", action="store_true", help="Ne pas envoyer sur Telegram")
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.batch, args.parallel, not args.no_telegram))


if __name__ == "__main__":
    main()
