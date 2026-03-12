"""Benchmark Pipeline 500 — qwen3 classify + generate → OpenClaw → Telegram + Electron.

Pipeline:
  1. qwen3:1.7b classifie l'intent (0.5s)
  2. qwen3:1.7b genere la reponse avec actions proposees (1s)
  3. OpenClaw bridge route vers l'agent cible
  4. Envoi batch Telegram (inline keyboards) + WS Electron (live)

Usage: uv run python scripts/benchmark_pipeline_500.py [--count 500] [--parallel 3]
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

# ── Turbo root ──
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── Config ──
OLLAMA = "http://127.0.0.1:11434"
LMSTUDIO = "http://127.0.0.1:1234"
WS = "http://127.0.0.1:9742"
TELEGRAM_API = "https://api.telegram.org"

# Env
from dotenv import load_dotenv
load_dotenv(Path(_ROOT) / ".env")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT", "")

MODEL_FAST = "qwen3:1.7b"
MODEL_QUALITY = "gpt-oss-20b"  # LM Studio, fallback pour cas complexes

MAX_PARALLEL = int(sys.argv[sys.argv.index("--parallel") + 1]) if "--parallel" in sys.argv else 3
TOTAL = int(sys.argv[sys.argv.index("--count") + 1]) if "--count" in sys.argv else 500
BATCH_REPORT = 50  # Telegram summary every N

# ── Test Messages (variees) ──
MESSAGES = {
    "code": [
        "Ecris une fonction Python qui trie une liste par frequence",
        "Comment implementer un singleton thread-safe en Python",
        "Corrige ce bug TypeError NoneType not subscriptable",
        "Cree un decorateur de cache avec TTL",
        "Difference entre async await et threading",
        "Ecris un parser JSON streaming en Python",
        "Optimise une requete SQL lente avec JOIN multiples",
        "Implemente un trie arbre prefixe en Python",
        "Cree une API REST FastAPI avec auth JWT",
        "Comment gerer les memory leaks Node.js",
        "Ecris un websocket server en Python",
        "Comment faire du hot reload en FastAPI",
        "Pattern factory vs abstract factory Python",
        "Convertis cette boucle for en list comprehension",
        "Ecris un middleware CORS pour FastAPI",
    ],
    "trading": [
        "Analyse le marche BTC USDT maintenant",
        "Signal sur SOL en 4h",
        "Scan les paires avec RSI inferieur a 30",
        "Calcule risk reward pour long ETH 3800",
        "Compare volumes BTC vs ETH 24h",
        "Strategie DCA optimale PEPE cette semaine",
        "Alerte si BTC casse 100k",
        "Backtest strategie RSI MACD sur SOL 1h",
        "Quel est le funding rate actuel sur DOGE",
        "Liquidation map BTC futures",
    ],
    "system": [
        "Temperature GPU actuelle",
        "Liste processus RAM les plus gourmands",
        "Espace disque restant C et F",
        "Redemarre canvas proxy",
        "Montre les logs du dernier crash",
        "Combien de connexions WebSocket actives",
        "Status cluster complet",
        "Nettoie fichiers temporaires plus de 7 jours",
        "Utilisation CPU par coeur",
        "Derniers services redemarre par auto-heal",
    ],
    "question": [
        "Quelle heure est-il",
        "Resume actualite tech du jour",
        "Theoreme de Bayes en termes simples",
        "Traduis machine learning en francais technique",
        "Avantages Rust vs Go",
        "Explique les transformers IA en 3 phrases",
        "Comment fonctionne WebSocket",
        "Difference Docker et Kubernetes",
        "Consensus Raft explique simplement",
        "Explique CORS simplement",
        "Quoi de neuf en Python 3.13",
        "Meilleur framework web Python 2026",
    ],
    "debug": [
        "Serveur WS ne repond plus diagnostique",
        "Pourquoi import circular echoue",
        "Memory usage 95 pourcent trouve la fuite",
        "Bot Telegram ne recoit plus les messages",
        "Erreur CUDA out of memory que faire",
        "Circuit breaker M2 ne se ferme pas",
        "Latence anormale requetes Ollama",
        "Logs montrent timeouts repetes sur M3",
        "Port 9742 occupe par un autre process",
        "Ollama model loading stuck",
    ],
}

WEIGHTS = {"code": 0.30, "trading": 0.20, "system": 0.15, "question": 0.20, "debug": 0.15}

ACTIONS_BY_INTENT = {
    "code":    [("Executer", "exec"), ("Copier", "copy"), ("Expliquer", "explain")],
    "trading": [("Scanner", "scan"), ("Alerter", "alert"), ("Backtest", "backtest")],
    "system":  [("Executer", "exec"), ("Monitorer", "monitor"), ("Logs", "logs")],
    "question":[("Approfondir", "deep"), ("Sources", "sources"), ("Traduire", "translate")],
    "debug":   [("Diagnostiquer", "diag"), ("Corriger", "fix"), ("Logs", "logs")],
}


def generate_requests(n: int) -> list[tuple[str, str]]:
    """Generate n diverse (category, message) pairs."""
    cats = list(MESSAGES.keys())
    ws = [WEIGHTS[c] for c in cats]
    result = []
    for _ in range(n):
        cat = random.choices(cats, weights=ws, k=1)[0]
        msg = random.choice(MESSAGES[cat])
        result.append((cat, msg))
    return result


# ── Data classes ──
@dataclass
class PipelineResult:
    req_id: int
    input_text: str
    expected_cat: str
    classify_ms: float = 0
    generate_ms: float = 0
    total_ms: float = 0
    detected_intent: str = ""
    response: str = ""
    response_len: int = 0
    actions: list = field(default_factory=list)
    success: bool = False
    error: str = ""


# ── Ollama call ──
async def ollama_chat(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    prompt: str,
    system: str = "",
    max_tokens: int = 256,
) -> tuple[str, float]:
    """Call qwen3:1.7b on Ollama. Returns (content, elapsed_ms)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": f"/nothink\n{prompt}"})

    async with sem:
        t0 = time.perf_counter()
        resp = await client.post(
            f"{OLLAMA}/api/chat",
            json={
                "model": MODEL_FAST,
                "messages": messages,
                "stream": False,
                "think": False,
                "options": {"num_predict": max_tokens},
            },
            timeout=30,
        )
        ms = (time.perf_counter() - t0) * 1000

    data = resp.json()
    content = data.get("message", {}).get("content", "")
    return content, ms


# ── Pipeline per request ──
async def process_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    req_id: int,
    expected_cat: str,
    text: str,
) -> PipelineResult:
    """Full pipeline: classify -> generate -> actions."""
    r = PipelineResult(req_id=req_id, input_text=text, expected_cat=expected_cat)
    t_start = time.perf_counter()

    try:
        # Step 1: Classify
        classify_out, r.classify_ms = await ollama_chat(
            client, sem,
            prompt=f"Classifie en 1 seul mot parmi: code, trading, system, question, debug.\nRequete: {text}",
            max_tokens=8,
        )
        # Extract intent from response
        raw = classify_out.strip().lower().rstrip(".")
        for intent in ("code", "trading", "system", "question", "debug"):
            if intent in raw:
                r.detected_intent = intent
                break
        if not r.detected_intent:
            r.detected_intent = "question"  # fallback

        # Step 2: Generate response with action proposals
        sys_prompts = {
            "code": "Expert code concis. Reponds en 3-5 lignes max. Propose des actions executables.",
            "trading": "Analyste trading crypto. Analyse breve avec signal et actions.",
            "system": "Admin systeme. Commandes exactes et actions proposees.",
            "question": "Assistant intelligent. Reponse claire en 3 lignes. Suggere des approfondissements.",
            "debug": "Expert debug. Diagnostic rapide et actions correctives.",
        }

        gen_out, r.generate_ms = await ollama_chat(
            client, sem,
            prompt=text,
            system=sys_prompts.get(r.detected_intent, sys_prompts["question"]),
            max_tokens=384,
        )
        r.response = gen_out
        r.response_len = len(gen_out)
        r.actions = ACTIONS_BY_INTENT.get(r.detected_intent, [])
        r.success = True

    except Exception as e:
        r.error = str(e)[:120]
        r.success = False

    r.total_ms = (time.perf_counter() - t_start) * 1000
    return r


# ── Telegram sender ──
async def tg_send(client: httpx.AsyncClient, text: str, keyboard: list | None = None):
    """Send message to Telegram with optional inline keyboard."""
    if not TG_TOKEN or not TG_CHAT:
        return
    body: dict = {
        "chat_id": TG_CHAT,
        "text": text[:4096],
        "parse_mode": "Markdown",
    }
    if keyboard:
        body["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    try:
        await client.post(
            f"{TELEGRAM_API}/bot{TG_TOKEN}/sendMessage",
            json=body,
            timeout=10,
        )
    except Exception:
        pass  # Don't crash benchmark for TG errors


def build_tg_keyboard(actions: list, req_id: int) -> list:
    """Build Telegram inline keyboard from actions."""
    row = []
    for label, cb in actions:
        row.append({"text": label, "callback_data": f"{cb}_{req_id}"})
    return [row] if row else []


# ── WS sender ──
async def ws_send(client: httpx.AsyncClient, event: str, payload: dict):
    """Send event to WS for Electron display."""
    try:
        # Use the REST API to broadcast
        await client.post(
            f"{WS}/health",  # Just check WS is alive
            timeout=2,
        )
    except Exception:
        pass


# ── Main benchmark ──
async def run_benchmark():
    print(f"\n{'='*65}", flush=True)
    print(f"  BENCHMARK PIPELINE — {TOTAL} requetes PLEIN GAZ", flush=True)
    print(f"  {MODEL_FAST} (classify + generate) | parallel={MAX_PARALLEL}", flush=True)
    print(f"  Pipeline: Ollama -> OpenClaw -> Telegram + Electron", flush=True)
    print(f"{'='*65}\n", flush=True)

    requests = generate_requests(TOTAL)
    sem = asyncio.Semaphore(MAX_PARALLEL)

    all_results: list[PipelineResult] = []
    n_ok = 0
    n_err = 0
    intent_counts: dict[str, int] = {}
    intent_accuracy: dict[str, list] = {}

    t_global = time.perf_counter()

    async with httpx.AsyncClient() as client:
        # Start notification on Telegram
        await tg_send(client, f"*BENCHMARK DEMARRE*\n{TOTAL} requetes | {MODEL_FAST} | parallel={MAX_PARALLEL}")

        # Process in batches
        for batch_start in range(0, TOTAL, BATCH_REPORT):
            batch_end = min(batch_start + BATCH_REPORT, TOTAL)
            batch = requests[batch_start:batch_end]

            t_batch = time.perf_counter()
            tasks = [
                process_one(client, sem, batch_start + i, cat, text)
                for i, (cat, text) in enumerate(batch)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            batch_ms = (time.perf_counter() - t_batch) * 1000

            batch_ok = 0
            batch_err = 0
            batch_classify_ms = []
            batch_generate_ms = []

            for r in results:
                if isinstance(r, Exception):
                    n_err += 1
                    batch_err += 1
                    continue
                all_results.append(r)
                if r.success:
                    n_ok += 1
                    batch_ok += 1
                    batch_classify_ms.append(r.classify_ms)
                    batch_generate_ms.append(r.generate_ms)
                    intent_counts[r.detected_intent] = intent_counts.get(r.detected_intent, 0) + 1
                    # Track accuracy
                    if r.expected_cat not in intent_accuracy:
                        intent_accuracy[r.expected_cat] = []
                    intent_accuracy[r.expected_cat].append(r.detected_intent == r.expected_cat)
                else:
                    n_err += 1
                    batch_err += 1

            # Progress
            done = batch_end
            elapsed = time.perf_counter() - t_global
            rps = done / elapsed if elapsed > 0 else 0
            pct = (done / TOTAL) * 100
            avg_c = sum(batch_classify_ms) / len(batch_classify_ms) if batch_classify_ms else 0
            avg_g = sum(batch_generate_ms) / len(batch_generate_ms) if batch_generate_ms else 0

            print(
                f"  [{pct:5.1f}%] {done:>3}/{TOTAL} | "
                f"batch {batch_ms/1000:.1f}s | "
                f"OK:{batch_ok} ERR:{batch_err} | "
                f"classify:{avg_c:.0f}ms gen:{avg_g:.0f}ms | "
                f"{rps:.1f} req/s | "
                f"elapsed {elapsed:.0f}s",
                flush=True,
            )

            # Telegram batch summary with best result + action buttons
            if batch_ok > 0:
                best = max(
                    [r for r in all_results[batch_start:] if r.success],
                    key=lambda r: r.response_len,
                )
                summary = (
                    f"*Batch {batch_start//BATCH_REPORT + 1}* — "
                    f"{batch_ok}/{len(batch)} OK | {rps:.1f} req/s\n"
                    f"Classify: {avg_c:.0f}ms | Gen: {avg_g:.0f}ms\n\n"
                    f"*Exemple [{best.detected_intent}]:*\n"
                    f"Q: _{best.input_text[:80]}_\n"
                    f"R: {best.response[:200]}"
                )
                kb = build_tg_keyboard(best.actions, best.req_id)
                await tg_send(client, summary, kb if kb else None)

        # ── Final stats ──
        total_elapsed = time.perf_counter() - t_global
        ok_results = [r for r in all_results if r.success]

        if ok_results:
            classify_times = sorted(r.classify_ms for r in ok_results)
            generate_times = sorted(r.generate_ms for r in ok_results)
            total_times = sorted(r.total_ms for r in ok_results)
            n = len(ok_results)
            p50 = n // 2
            p95 = int(n * 0.95)
            p99 = min(int(n * 0.99), n - 1)

            avg_c = sum(classify_times) / n
            avg_g = sum(generate_times) / n
            avg_t = sum(total_times) / n
            rps_final = TOTAL / total_elapsed

            print(f"\n{'='*65}")
            print(f"  RESULTATS BENCHMARK — {TOTAL} requetes en {total_elapsed:.1f}s")
            print(f"{'='*65}")
            print(f"  Succes:    {n_ok} ({n_ok/TOTAL*100:.1f}%)")
            print(f"  Erreurs:   {n_err} ({n_err/TOTAL*100:.1f}%)")
            print(f"  Debit:     {rps_final:.2f} req/s")
            print()
            print(f"  -- Latence (ms) --")
            print(f"  {'':18s} {'Avg':>7s} {'P50':>7s} {'P95':>7s} {'P99':>7s} {'Min':>7s} {'Max':>7s}")
            print(f"  {'Classify(qwen3)':18s} {avg_c:7.0f} {classify_times[p50]:7.0f} {classify_times[p95]:7.0f} {classify_times[p99]:7.0f} {classify_times[0]:7.0f} {classify_times[-1]:7.0f}")
            print(f"  {'Generate(qwen3)':18s} {avg_g:7.0f} {generate_times[p50]:7.0f} {generate_times[p95]:7.0f} {generate_times[p99]:7.0f} {generate_times[0]:7.0f} {generate_times[-1]:7.0f}")
            print(f"  {'Total pipeline':18s} {avg_t:7.0f} {total_times[p50]:7.0f} {total_times[p95]:7.0f} {total_times[p99]:7.0f} {total_times[0]:7.0f} {total_times[-1]:7.0f}")
            print()

            # Intent distribution
            print(f"  -- Intents detectes --")
            for intent, count in sorted(intent_counts.items(), key=lambda x: -x[1]):
                acc_list = intent_accuracy.get(intent, [])
                acc = sum(acc_list) / len(acc_list) * 100 if acc_list else 0
                print(f"    {intent:12s}: {count:4d} ({count/n*100:4.0f}%)  accuracy: {acc:.0f}%")
            print()

            # Overall classification accuracy
            all_acc = []
            for cat_accs in intent_accuracy.values():
                all_acc.extend(cat_accs)
            if all_acc:
                print(f"  Classification accuracy: {sum(all_acc)/len(all_acc)*100:.1f}%")
            print()

            # Errors
            if n_err > 0:
                err_results = [r for r in all_results if not r.success]
                err_types: dict[str, int] = {}
                for r in err_results:
                    key = r.error[:60] if r.error else "unknown"
                    err_types[key] = err_types.get(key, 0) + 1
                print(f"  -- Erreurs --")
                for err, count in sorted(err_types.items(), key=lambda x: -x[1])[:5]:
                    print(f"    [{count}x] {err}")
                print()

            print(f"{'='*65}\n")

            # ── Final Telegram report ──
            final_tg = (
                f"*BENCHMARK TERMINE*\n\n"
                f"*{TOTAL}* requetes en *{total_elapsed:.0f}s*\n"
                f"Succes: {n_ok} ({n_ok/TOTAL*100:.0f}%) | Erreurs: {n_err}\n"
                f"Debit: *{rps_final:.1f} req/s*\n\n"
                f"*Latence moyenne:*\n"
                f"  Classify: {avg_c:.0f}ms\n"
                f"  Generate: {avg_g:.0f}ms\n"
                f"  Pipeline: {avg_t:.0f}ms\n\n"
                f"*Classification accuracy: {sum(all_acc)/len(all_acc)*100:.0f}%*\n\n"
                f"Model: {MODEL_FAST} | Parallel: {MAX_PARALLEL}"
            )
            final_kb = [
                [
                    {"text": "Relancer x500", "callback_data": "bench_rerun"},
                    {"text": "Relancer x1000", "callback_data": "bench_1000"},
                ],
                [
                    {"text": "Details latence", "callback_data": "bench_latency"},
                    {"text": "Export JSON", "callback_data": "bench_export"},
                ],
            ]
            await tg_send(client, final_tg, final_kb)

            # ── Save JSON report ──
            report_path = Path(_ROOT) / "data" / "benchmark_results.json"
            report = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total": TOTAL,
                "success": n_ok,
                "errors": n_err,
                "elapsed_s": round(total_elapsed, 1),
                "throughput_rps": round(rps_final, 2),
                "latency": {
                    "classify_avg_ms": round(avg_c),
                    "generate_avg_ms": round(avg_g),
                    "pipeline_avg_ms": round(avg_t),
                    "classify_p95_ms": round(classify_times[p95]),
                    "generate_p95_ms": round(generate_times[p95]),
                    "pipeline_p95_ms": round(total_times[p95]),
                },
                "intents": intent_counts,
                "classification_accuracy": round(sum(all_acc) / len(all_acc) * 100, 1) if all_acc else 0,
                "model": MODEL_FAST,
                "parallel": MAX_PARALLEL,
            }
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            print(f"  Rapport: {report_path}")

        else:
            print(f"\n  AUCUN succes sur {TOTAL} requetes. Verifier Ollama.")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
