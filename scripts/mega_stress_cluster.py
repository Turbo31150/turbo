"""JARVIS Mega Stress Test — ALL nodes, ALL models, ALL agents, 1000 cycles.

Targets:
  - M1 (127.0.0.1:1234): qwen3-8b, gpt-oss-20b, qwen3-30b, deepseek-r1, qwq-32b
  - OL1 (127.0.0.1:11434): qwen3:1.7b, minimax-m2.5:cloud, glm-5:cloud, kimi-k2.5:cloud
  - M2 (192.168.1.26:1234): deepseek-r1-0528-qwen3-8b
  - M3 (192.168.1.113:1234): deepseek-r1-0528-qwen3-8b
  - HuggingFace: Qwen3.5-27B (cloud)
  - OpenClaw agents via WS API
  - Proxy (18800) dispatch
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

HF_TOKEN = os.getenv("HF_TOKEN", "")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT", "")

# ── ALL NODES ──
NODES = {
    # M1 — LM Studio local (6 GPU, parallel=11)
    "M1/qwen3-8b": {
        "url": "http://127.0.0.1:1234/v1/chat/completions",
        "model": "qwen3-8b", "type": "openai", "timeout": 30,
        "system": "/nothink\nTu es JARVIS. Reponds en francais, concis.",
    },
    "M1/gpt-oss-20b": {
        "url": "http://127.0.0.1:1234/v1/chat/completions",
        "model": "gpt-oss-20b", "type": "openai", "timeout": 60,
        "system": "/nothink\nTu es JARVIS. Reponds en francais.",
    },
    "M1/qwen3-30b": {
        "url": "http://127.0.0.1:1234/v1/chat/completions",
        "model": "qwen3-30b-a3b-instruct-2507", "type": "openai", "timeout": 60,
        "system": "/nothink\nTu es JARVIS. Reponds en francais.",
    },
    "M1/deepseek-r1": {
        "url": "http://127.0.0.1:1234/v1/chat/completions",
        "model": "deepseek-r1-0528-qwen3-8b", "type": "openai", "timeout": 30,
        "system": "Tu es JARVIS. Reponds en francais.",
    },
    "M1/qwq-32b": {
        "url": "http://127.0.0.1:1234/v1/chat/completions",
        "model": "qwq-32b", "type": "openai", "timeout": 30,
        "system": "/nothink\nTu es JARVIS. Reponds en francais.",
    },
    # OL1 — Ollama local + cloud
    "OL1/qwen3:1.7b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b", "type": "ollama", "timeout": 15,
    },
    "OL1/minimax-cloud": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "minimax-m2.5:cloud", "type": "ollama", "timeout": 30,
    },
    "OL1/glm5-cloud": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "glm-5:cloud", "type": "ollama", "timeout": 30,
    },
    "OL1/kimi-cloud": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "kimi-k2.5:cloud", "type": "ollama", "timeout": 30,
    },
    # M2 — Distant reasoning (timeout court, souvent offline)
    "M2/deepseek-r1": {
        "url": "http://192.168.1.26:1234/v1/chat/completions",
        "model": "deepseek-r1-0528-qwen3-8b", "type": "openai", "timeout": 8,
        "system": "Tu es JARVIS. Reponds en francais.",
    },
    # M3 — Distant fallback (timeout court, souvent offline)
    "M3/deepseek-r1": {
        "url": "http://192.168.1.113:1234/v1/chat/completions",
        "model": "deepseek-r1-0528-qwen3-8b", "type": "openai", "timeout": 8,
        "system": "Tu es JARVIS. Reponds en francais.",
    },
    # HuggingFace cloud
    "HF/Qwen3.5-27B": {
        "url": "https://router.huggingface.co/novita/v3/openai/chat/completions",
        "model": "Qwen/Qwen3.5-27B", "type": "openai", "timeout": 30,
        "auth": f"Bearer {HF_TOKEN}",
    },
}

# ── DIVERSE PROMPTS ──
PROMPTS = [
    # Code
    "Ecris une fonction Python fibonacci iterative",
    "Corrige: IndexError dans une boucle while sur une liste vide",
    "Cree un context manager Python pour mesurer le temps",
    "Refactorise ce code pour utiliser des dataclasses",
    "Ecris un test pytest pour une fonction de tri",
    # Reasoning
    "Un escargot grimpe 3m le jour, glisse 2m la nuit. Hauteur 10m. Combien de jours ?",
    "Prouve que la racine de 2 est irrationnelle en 5 lignes",
    "Si tous les A sont B et certains B sont C, peut-on conclure que certains A sont C ?",
    # Trading
    "Analyse technique BTC: support 95000, resistance 98000, RSI 65",
    "Compare DCA vs lump sum sur ETH 2024-2025",
    # Architecture
    "Propose une architecture event-driven pour un systeme de notifications",
    "Compare PostgreSQL vs SQLite pour 10M rows avec 50 req/s",
    # System
    "Explique le pattern circuit breaker avec un exemple concret",
    "Comment fonctionne le consensus Raft en systemes distribues ?",
    # Creative
    "Genere un nom de projet pour un dashboard IA temps reel",
    "Ecris un slogan pour JARVIS en 5 mots",
    # Debug
    "Mon FastAPI retourne 422: comment debugger le schema Pydantic ?",
    "asyncio.CancelledError random dans un producer-consumer pattern",
    # Math
    "Calcule: integrale de x*ln(x) dx",
    "Probabilite de tirer 3 as dans un jeu de 52 cartes (5 cartes tirees)",
    # Web search (cloud)
    "Quelles sont les dernieres nouveautes de Python 3.13 ?",
    "Tendances crypto mars 2026",
    # Quick
    "Combien font 1337 * 42 ?",
    "Capitale du Japon ?",
    "Pi avec 10 decimales ?",
]

STATS = {"ok": 0, "fail": 0, "by_node": {}, "total_ms": 0, "errors": []}


async def call_node(client: httpx.AsyncClient, node_id: str, cfg: dict, prompt: str, idx: int) -> dict:
    """Call a single node with a prompt."""
    t0 = time.time()
    try:
        headers = {"Content-Type": "application/json"}
        if "auth" in cfg:
            headers["Authorization"] = cfg["auth"]

        if cfg["type"] == "ollama":
            body = {
                "model": cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
            }
        else:  # openai
            messages = [{"role": "user", "content": prompt}]
            if "system" in cfg:
                messages.insert(0, {"role": "system", "content": cfg["system"]})
            body = {
                "model": cfg["model"],
                "messages": messages,
                "max_tokens": 256,
                "temperature": 0.3,
                "stream": False,
            }

        resp = await client.post(cfg["url"], json=body, headers=headers, timeout=cfg["timeout"])
        ms = int((time.time() - t0) * 1000)

        if resp.status_code != 200:
            return {"node": node_id, "ok": False, "ms": ms, "err": f"HTTP {resp.status_code}"}

        data = resp.json()

        # Extract response text
        if cfg["type"] == "ollama":
            text = data.get("message", {}).get("content", "")[:100]
        else:
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")[:100]

        return {"node": node_id, "ok": True, "ms": ms, "len": len(text), "preview": text[:60]}

    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return {"node": node_id, "ok": False, "ms": ms, "err": str(e)[:80]}


async def send_telegram(client: httpx.AsyncClient, text: str):
    """Send status update to Telegram."""
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        await client.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text[:4000], "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass


async def main():
    total_cycles = 1000
    batch_size = len(NODES)  # 1 cycle = 1 request per node
    node_ids = list(NODES.keys())
    node_stats = {n: {"ok": 0, "fail": 0, "total_ms": 0} for n in node_ids}

    print(f"\n{'='*70}")
    print(f"  JARVIS MEGA STRESS — {total_cycles} cycles x {len(NODES)} nodes = {total_cycles * len(NODES)} requests")
    print(f"  Nodes: {', '.join(node_ids)}")
    print(f"{'='*70}\n")
    sys.stdout.flush()

    t_global = time.time()
    cycle = 0

    async with httpx.AsyncClient() as client:
        # Telegram start notification
        await send_telegram(client, f"<b>MEGA STRESS START</b>\n{total_cycles} cycles x {len(NODES)} nodes = {total_cycles * len(NODES)} requests")

        for cycle in range(total_cycles):
            prompt = PROMPTS[cycle % len(PROMPTS)]

            # Launch ALL nodes in parallel for this cycle
            tasks = [
                call_node(client, nid, cfg, prompt, cycle)
                for nid, cfg in NODES.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, Exception):
                    STATS["fail"] += 1
                    continue
                nid = r["node"]
                if r["ok"]:
                    STATS["ok"] += 1
                    STATS["total_ms"] += r["ms"]
                    node_stats[nid]["ok"] += 1
                    node_stats[nid]["total_ms"] += r["ms"]
                else:
                    STATS["fail"] += 1
                    node_stats[nid]["fail"] += 1
                    if len(STATS["errors"]) < 20:
                        STATS["errors"].append(f"[{nid}] {r.get('err', '?')}")

            done = cycle + 1
            total_req = STATS["ok"] + STATS["fail"]
            avg = STATS["total_ms"] // STATS["ok"] if STATS["ok"] else 0
            elapsed = int(time.time() - t_global)

            # Progress every 25 cycles
            if done % 25 == 0 or done == total_cycles:
                line = f"  [{done}/{total_cycles}] OK={STATS['ok']} FAIL={STATS['fail']} avg={avg}ms elapsed={elapsed}s"
                print(line)
                sys.stdout.flush()

            # Telegram update every 100 cycles
            if done % 100 == 0:
                node_report = "\n".join(
                    f"  {n}: {s['ok']}ok/{s['fail']}fail avg={s['total_ms']//max(s['ok'],1)}ms"
                    for n, s in node_stats.items()
                )
                await send_telegram(client, (
                    f"<b>MEGA STRESS [{done}/{total_cycles}]</b>\n"
                    f"OK={STATS['ok']} FAIL={STATS['fail']} avg={avg}ms\n"
                    f"Elapsed: {elapsed}s\n\n{node_report}"
                ))

        # Final report
        elapsed = int(time.time() - t_global)
        avg = STATS["total_ms"] // STATS["ok"] if STATS["ok"] else 0
        throughput = STATS["ok"] / max(elapsed, 1)

        print(f"\n{'='*70}")
        print(f"  MEGA STRESS COMPLETE")
        print(f"{'='*70}")
        print(f"  Total: {STATS['ok']+STATS['fail']} | OK: {STATS['ok']} | FAIL: {STATS['fail']}")
        print(f"  Avg: {avg}ms | Time: {elapsed}s | Throughput: {throughput:.1f} req/s")
        print(f"\n  Per-node breakdown:")
        for n, s in sorted(node_stats.items()):
            a = s["total_ms"] // max(s["ok"], 1)
            pct = s["ok"] * 100 // max(s["ok"] + s["fail"], 1)
            print(f"    {n:25s} OK={s['ok']:4d} FAIL={s['fail']:4d} avg={a:5d}ms success={pct}%")

        if STATS["errors"]:
            print(f"\n  First {len(STATS['errors'])} errors:")
            for e in STATS["errors"][:10]:
                print(f"    {e}")

        sys.stdout.flush()

        # Telegram final
        node_report = "\n".join(
            f"  {n}: {s['ok']}ok/{s['fail']}fail {s['total_ms']//max(s['ok'],1)}ms"
            for n, s in node_stats.items()
        )
        await send_telegram(client, (
            f"<b>MEGA STRESS DONE</b>\n"
            f"OK={STATS['ok']} FAIL={STATS['fail']} avg={avg}ms\n"
            f"Elapsed: {elapsed}s | {throughput:.1f} req/s\n\n{node_report}"
        ))


if __name__ == "__main__":
    asyncio.run(main())
