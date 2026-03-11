#!/usr/bin/env python3
"""Benchmark v2: Pipeline hybride — OpenClaw regex triage + OSS-20B enrichment + Qwen redaction.

Optimisation: le triage regex (<1ms) remplace OSS-20B pour la classification.
OSS-20B est utilise uniquement pour enrichir le prompt quand la confidence est faible.
Resultat: throughput x10+ vs v1.

Architecture:
  1. OpenClaw bridge regex classifie (instant, <1ms)
  2. Si confidence < 0.7: gpt-oss-20b enrichit le prompt (reasoning)
  3. qwen3-8b redige la reponse (/nothink, rapide)
  4. Telegram API direct + Electron WS push

Usage:
  uv run python scripts/benchmark_telegram_pipeline_v2.py --batch 50 --parallel 5
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

import httpx

# ============================================================================
# CONFIG
# ============================================================================
M1_URL = "http://127.0.0.1:1234/v1/chat/completions"
WS_URL = "http://127.0.0.1:9742"
OSS_CONFIDENCE_THRESHOLD = 0.7  # Below this, use OSS-20B for enrichment

MODEL_ENRICHMENT = "gpt-oss-20b"   # enrichissement quand confidence faible
MODEL_RESPONSE = "qwen3-8b"        # redaction rapide (/nothink)

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

TEST_REQUESTS = [
    # Cluster / Systeme
    "Quel est le statut du cluster ?",
    "Montre les temperatures GPU",
    "Combien de modeles sont charges sur M1 ?",
    "Fais un health check complet",
    "Quelle est la charge CPU et RAM ?",
    # Trading
    "Scan les top 10 cryptos pour un signal",
    "Quel est le prix du BTC ?",
    "Analyse technique SOL/USDT",
    "Resume les positions ouvertes",
    "Quels sont les signaux forts aujourd'hui ?",
    # Code / Dev
    "Liste les derniers commits git",
    "Combien de tests passent ?",
    "Montre les fichiers modifies recemment",
    "Quel est le nombre de modules dans src/ ?",
    "Explique le role de dispatch_engine.py",
    # Recherche / Web
    "Cherche les dernieres news sur l'IA",
    "Quel temps fait-il a Paris ?",
    "Resume les tendances crypto de la semaine",
    "Quelles sont les dernieres mises a jour de Claude ?",
    "Trouve la doc Azure sur les GPU VMs",
    # Actions / Automation
    "Cree une tache pour auditer la securite",
    "Envoie un rapport status sur Telegram",
    "Lance un backup de la base de donnees",
    "Planifie un scan trading dans 10 minutes",
    "Genere un rapport quotidien",
    # Conversation / Divers
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
    agent: str = ""
    intent: str = ""
    confidence: float = 0.0
    oss_enriched: bool = False
    response: str = ""
    triage_ms: float = 0
    enrichment_ms: float = 0
    generation_ms: float = 0
    delivery_ms: float = 0
    total_ms: float = 0
    tg_sent: bool = False
    success: bool = False
    error: str = ""


# ============================================================================
# PIPELINE STEPS
# ============================================================================

def step1_triage(request: str) -> dict:
    """OpenClaw bridge regex — instant classification (<1ms)."""
    from src.openclaw_bridge import get_bridge
    bridge = get_bridge()
    result = bridge.route(request)
    return {
        "agent": result.agent,
        "intent": result.intent,
        "confidence": result.confidence,
        "source": result.source,
    }


def _extract_content(data: dict) -> str:
    """Extract content from LM Studio response."""
    import re as _re
    if "choices" not in data:
        return ""
    msg = data["choices"][0]["message"]
    content = msg.get("content", "") or ""
    content = _re.sub(r"<\|[^|]+\|>[^{]*", "", content).strip()
    if not content:
        reasoning = msg.get("reasoning", "") or ""
        return reasoning[-300:] if reasoning else ""
    return content.strip()


async def step2_enrich_oss(client: httpx.AsyncClient, request: str, triage: dict) -> tuple[str, float]:
    """gpt-oss-20b enrichit le prompt quand la confidence triage est faible."""
    t0 = time.perf_counter()
    try:
        resp = await client.post(M1_URL, json={
            "model": MODEL_ENRICHMENT,
            "messages": [
                {"role": "system", "content": (
                    "Tu es un assistant qui reformule et enrichit les demandes pour un LLM. "
                    "Reformule la demande ci-dessous de maniere claire et precise. "
                    "Ajoute le contexte necessaire. Reponds en 2-3 lignes max."
                )},
                {"role": "user", "content": request}
            ],
            "temperature": 0.2,
            "max_tokens": 200,
        }, timeout=90)
        data = resp.json()
        content = _extract_content(data)
        elapsed = (time.perf_counter() - t0) * 1000
        return content or request, elapsed
    except Exception:
        elapsed = (time.perf_counter() - t0) * 1000
        return request, elapsed


async def step3_generate(client: httpx.AsyncClient, request: str,
                         enriched_prompt: str, triage: dict) -> tuple[str, float]:
    """qwen3-8b genere la reponse (/nothink, rapide)."""
    agent = triage.get("agent", "jarvis")
    intent = triage.get("intent", "question")
    system_msg = (
        f"/nothink\nTu es JARVIS, assistant IA ({agent}). "
        f"Intent detecte: {intent}. Reponds de facon concise et utile. "
        "Max 3-5 lignes. Format Telegram (pas de markdown complexe)."
    )
    payload = {
        "model": MODEL_RESPONSE,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": enriched_prompt}
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
        if attempt == 0:
            await asyncio.sleep(2)
    elapsed = (time.perf_counter() - t0) * 1000
    return f"[ERREUR] model swap timeout", elapsed


async def step4_deliver(client: httpx.AsyncClient, request: str, response: str,
                        triage: dict) -> tuple[bool, float]:
    """Telegram API direct + Electron WS push."""
    t0 = time.perf_counter()
    tg_ok = False
    agent = triage.get("agent", "jarvis")

    if TELEGRAM_TOKEN:
        try:
            tg_text = f"[{agent}] {response[:3800]}"
            tg_resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": tg_text},
                timeout=15,
            )
            tg_ok = tg_resp.status_code == 200
        except Exception:
            pass

    try:
        await client.post(f"{WS_URL}/api/chat", json={
            "message": request[:200], "response": response[:500],
            "metadata": triage, "source": "benchmark_v2",
        }, timeout=5)
    except Exception:
        pass

    elapsed = (time.perf_counter() - t0) * 1000
    return tg_ok, elapsed


# ============================================================================
# BENCHMARK RUNNER
# ============================================================================

async def run_benchmark(batch_size: int = 50, parallel: int = 5, send_telegram: bool = True):
    requests = (TEST_REQUESTS * ((batch_size // len(TEST_REQUESTS)) + 1))[:batch_size]

    print("=" * 80)
    print(f"  BENCHMARK v2 HYBRIDE -- {batch_size} requetes, parallelisme={parallel}")
    print(f"  Triage: OpenClaw regex (<1ms) | Enrichment: {MODEL_ENRICHMENT} (si conf<{OSS_CONFIDENCE_THRESHOLD})")
    print(f"  Redaction: {MODEL_RESPONSE} (/nothink)")
    print(f"  Delivery: Telegram {'ON' if send_telegram and TELEGRAM_TOKEN else 'OFF'} + Electron WS")
    print("=" * 80)
    print()

    results: list[RequestResult] = [RequestResult(request=r) for r in requests]
    t_start = time.perf_counter()
    sem = asyncio.Semaphore(parallel)

    # ── PHASE 1: Triage regex (instant) ──
    print(f"[PHASE 1] Triage regex x{batch_size} (OpenClaw bridge)...")
    print("-" * 80)
    t_phase1 = time.perf_counter()
    triages: list[dict] = []
    needs_enrichment = 0
    for idx, req in enumerate(requests):
        t0 = time.perf_counter()
        triage = step1_triage(req)
        ms = (time.perf_counter() - t0) * 1000
        triages.append(triage)
        results[idx].category = triage.get("intent", "unknown")
        results[idx].agent = triage.get("agent", "")
        results[idx].intent = triage.get("intent", "")
        results[idx].confidence = triage.get("confidence", 0)
        results[idx].triage_ms = ms
        if triage["confidence"] < OSS_CONFIDENCE_THRESHOLD:
            needs_enrichment += 1
        conf_bar = "+" * int(triage["confidence"] * 10)
        print(f"  [{idx+1:2d}/{batch_size}] {ms:5.1f}ms | {triage['confidence']:.2f} {conf_bar:10s} | "
              f"{triage['agent']:20s} | {req[:45]}")
    t_phase1_elapsed = (time.perf_counter() - t_phase1) * 1000
    print(f"\n  Phase 1: {batch_size}/{batch_size} OK en {t_phase1_elapsed:.0f}ms "
          f"({needs_enrichment} need OSS enrichment)\n")

    # ── PHASE 2: Enrichment OSS-20B (only low confidence) ──
    if needs_enrichment > 0:
        print(f"[PHASE 2] Enrichment x{needs_enrichment} via {MODEL_ENRICHMENT}...")
        print("-" * 80)
    else:
        print(f"[PHASE 2] Enrichment: SKIP (all confidence >= {OSS_CONFIDENCE_THRESHOLD})")
    t_phase2 = time.perf_counter()
    enriched_prompts: list[str] = list(requests)  # Default: original request

    async def do_enrich(idx: int) -> None:
        if triages[idx]["confidence"] >= OSS_CONFIDENCE_THRESHOLD:
            return
        async with sem:
            async with httpx.AsyncClient() as client:
                enriched, ms = await step2_enrich_oss(client, requests[idx], triages[idx])
                enriched_prompts[idx] = enriched
                results[idx].enrichment_ms = ms
                results[idx].oss_enriched = True
                print(f"  [{idx+1:2d}/{batch_size}] {ms:6.0f}ms | {requests[idx][:55]}")

    await asyncio.gather(*[do_enrich(i) for i in range(batch_size)])
    t_phase2_elapsed = (time.perf_counter() - t_phase2) * 1000
    enriched_count = sum(1 for r in results if r.oss_enriched)
    print(f"\n  Phase 2: {enriched_count} enrichis en {t_phase2_elapsed/1000:.1f}s\n")

    # ── PHASE 3: Generation qwen3-8b (all) ──
    print(f"[PHASE 3] Redaction x{batch_size} via {MODEL_RESPONSE} (parallel={parallel})...")
    print("-" * 80)
    t_phase3 = time.perf_counter()

    # Warmup
    async with httpx.AsyncClient() as client:
        try:
            await client.post(M1_URL, json={
                "model": MODEL_RESPONSE,
                "messages": [{"role": "user", "content": "/nothink\nping"}],
                "max_tokens": 5,
            }, timeout=60)
        except Exception:
            pass

    async def do_generate(idx: int) -> None:
        async with sem:
            try:
                async with httpx.AsyncClient() as client:
                    response, ms = await step3_generate(
                        client, requests[idx], enriched_prompts[idx], triages[idx])
                    results[idx].response = response
                    results[idx].generation_ms = ms
                    print(f"  [{idx+1:2d}/{batch_size}] {ms:6.0f}ms | {len(response):4d}c | "
                          f"{results[idx].agent:15s} | {requests[idx][:40]}")
            except Exception as e:
                results[idx].error = f"gen: {e}"
                print(f"  [{idx+1:2d}/{batch_size}] ERREUR gen: {str(e)[:50]}")

    await asyncio.gather(*[do_generate(i) for i in range(batch_size)])
    t_phase3_elapsed = (time.perf_counter() - t_phase3) * 1000
    ok3 = sum(1 for r in results if r.response and "[ERREUR]" not in r.response)
    print(f"\n  Phase 3: {ok3}/{batch_size} OK en {t_phase3_elapsed/1000:.1f}s\n")

    # ── PHASE 4: Delivery ──
    if send_telegram:
        print(f"[PHASE 4] Delivery x{ok3} (Telegram + Electron)...")
        print("-" * 80)
    t_phase4 = time.perf_counter()

    async def do_deliver(idx: int) -> None:
        if not results[idx].response or "[ERREUR]" in results[idx].response:
            return
        async with sem:
            async with httpx.AsyncClient() as client:
                tg_ok, ms = await step4_deliver(
                    client, requests[idx], results[idx].response, triages[idx])
                results[idx].delivery_ms = ms
                results[idx].tg_sent = tg_ok
                results[idx].success = True
                results[idx].total_ms = (results[idx].triage_ms + results[idx].enrichment_ms +
                                         results[idx].generation_ms + ms)
                if send_telegram:
                    tg_str = "TG" if tg_ok else "noTG"
                    print(f"  [{idx+1:2d}/{batch_size}] {ms:5.0f}ms | {tg_str:4s} | "
                          f"{results[idx].agent:15s} | {requests[idx][:40]}")

    await asyncio.gather(*[do_deliver(i) for i in range(batch_size)])
    t_phase4_elapsed = (time.perf_counter() - t_phase4) * 1000
    tg_count = sum(1 for r in results if r.tg_sent)
    if send_telegram:
        print(f"\n  Phase 4: {tg_count} Telegram en {t_phase4_elapsed/1000:.1f}s\n")

    t_total = (time.perf_counter() - t_start) * 1000

    # ========================================================================
    # RAPPORT
    # ========================================================================
    print()
    print("=" * 80)
    print("  RESULTATS BENCHMARK v2 HYBRIDE")
    print("=" * 80)

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    print(f"  Total:          {batch_size} requetes en {t_total/1000:.1f}s")
    print(f"  Succes:         {len(successes)}/{batch_size} ({100*len(successes)/batch_size:.0f}%)")
    print(f"  Echecs:         {len(failures)}")
    print(f"  Telegram sent:  {tg_count}/{batch_size}")
    print(f"  OSS enriched:   {enriched_count}/{batch_size}")
    print(f"  Debit:          {batch_size/(t_total/1000):.2f} req/s")
    print()

    avg_triage = avg_enrich = avg_gen = avg_del = avg_total = p50 = p95 = 0.0
    if successes:
        avg_triage = sum(r.triage_ms for r in successes) / len(successes)
        avg_enrich = sum(r.enrichment_ms for r in successes) / len(successes)
        avg_gen = sum(r.generation_ms for r in successes) / len(successes)
        avg_del = sum(r.delivery_ms for r in successes) / len(successes)
        avg_total = sum(r.total_ms for r in successes) / len(successes)
        sorted_totals = sorted(r.total_ms for r in successes)
        p50 = sorted_totals[len(sorted_totals) // 2]
        p95 = sorted_totals[int(len(sorted_totals) * 0.95)]

        print(f"  LATENCES (moyennes):")
        print(f"    Triage regex:               {avg_triage:7.1f}ms")
        print(f"    OSS enrichment:             {avg_enrich:7.0f}ms")
        print(f"    Redaction ({MODEL_RESPONSE}):     {avg_gen:7.0f}ms")
        print(f"    Delivery (TG+WS):           {avg_del:7.0f}ms")
        print(f"    Total pipeline:             {avg_total:7.0f}ms")
        print(f"    P50:                        {p50:7.0f}ms")
        print(f"    P95:                        {p95:7.0f}ms")
        print()

        print(f"  PHASES:")
        print(f"    Phase 1 (triage regex):   {t_phase1_elapsed:8.0f}ms")
        print(f"    Phase 2 (OSS enrich):     {t_phase2_elapsed:8.0f}ms")
        print(f"    Phase 3 (redaction):      {t_phase3_elapsed:8.0f}ms")
        print(f"    Phase 4 (delivery):       {t_phase4_elapsed:8.0f}ms")
        print()

        # Agents breakdown
        agents: dict[str, list[RequestResult]] = {}
        for r in successes:
            agents.setdefault(r.agent, []).append(r)
        print(f"  AGENTS OPENCLAW:")
        for agent, items in sorted(agents.items(), key=lambda x: -len(x[1])):
            avg = sum(r.total_ms for r in items) / len(items)
            print(f"    {agent:20s}: {len(items):3d} req, {avg:.0f}ms moy")

        # Confidence distribution
        confs = [r.confidence for r in successes]
        print(f"\n  CONFIDENCE DISTRIBUTION:")
        print(f"    >= 0.9: {sum(1 for c in confs if c >= 0.9):3d}")
        print(f"    0.7-0.9: {sum(1 for c in confs if 0.7 <= c < 0.9):3d}")
        print(f"    < 0.7: {sum(1 for c in confs if c < 0.7):3d} (enriched by OSS)")

    if failures:
        print(f"\n  ERREURS ({len(failures)}):")
        for r in failures[:10]:
            print(f"    - {r.request[:40]}: {r.error[:60]}")

    # Summary to Telegram
    if send_telegram and successes and TELEGRAM_TOKEN:
        summary = (
            f"BENCHMARK v2 HYBRIDE JARVIS\n"
            f"{'='*30}\n"
            f"{len(successes)}/{batch_size} OK | {t_total/1000:.1f}s total\n"
            f"Debit: {batch_size/(t_total/1000):.2f} req/s\n"
            f"Latence moy: {avg_total:.0f}ms\n"
            f"  triage={avg_triage:.1f}ms gen={avg_gen:.0f}ms delivery={avg_del:.0f}ms\n"
            f"P50={p50:.0f}ms P95={p95:.0f}ms\n"
            f"OSS enriched: {enriched_count}/{batch_size}\n"
            f"Telegram: {tg_count}/{batch_size}"
        )
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": TELEGRAM_CHAT_ID, "text": summary},
                    timeout=10,
                )
                print(f"\n[TELEGRAM] Resume final envoye!")
            except Exception as e:
                print(f"\n[TELEGRAM] Erreur: {e}")

    # Save JSON
    report_path = _root / "data" / "benchmark_v2_results.json"
    report = {
        "timestamp": time.time(),
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": "v2_hybrid",
        "config": {
            "batch_size": batch_size, "parallel": parallel,
            "model_enrichment": MODEL_ENRICHMENT, "model_response": MODEL_RESPONSE,
            "oss_confidence_threshold": OSS_CONFIDENCE_THRESHOLD,
        },
        "summary": {
            "total_ms": round(t_total),
            "success_rate": round(len(successes) / batch_size, 3) if batch_size else 0,
            "throughput_rps": round(batch_size / (t_total / 1000), 2) if t_total else 0,
            "avg_latency_ms": round(avg_total),
            "p50_ms": round(p50), "p95_ms": round(p95),
            "telegram_sent": tg_count, "oss_enriched": enriched_count,
        },
        "results": [
            {"request": r.request, "agent": r.agent, "intent": r.intent,
             "confidence": r.confidence, "oss_enriched": r.oss_enriched,
             "success": r.success, "tg_sent": r.tg_sent,
             "triage_ms": round(r.triage_ms, 1), "enrichment_ms": round(r.enrichment_ms),
             "generation_ms": round(r.generation_ms), "delivery_ms": round(r.delivery_ms),
             "total_ms": round(r.total_ms),
             "response_preview": r.response[:150], "error": r.error}
            for r in results
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Rapport: {report_path}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Benchmark v2 hybride JARVIS")
    parser.add_argument("--batch", type=int, default=50, help="Nombre de requetes")
    parser.add_argument("--parallel", type=int, default=5, help="Parallelisme max")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram")
    parser.add_argument("--threshold", type=float, default=0.7, help="Seuil confidence OSS")
    args = parser.parse_args()
    global OSS_CONFIDENCE_THRESHOLD
    OSS_CONFIDENCE_THRESHOLD = args.threshold
    asyncio.run(run_benchmark(args.batch, args.parallel, not args.no_telegram))


if __name__ == "__main__":
    main()
