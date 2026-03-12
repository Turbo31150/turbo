"""JARVIS Ultra Stress Auto-Amelioratif — 10 000 cycles.

ALL machines, ALL models, ALL agents, ALL cloud.
Auto-learn: adjusts weights, routing, timeouts based on results.

Inventory:
  M1 (20 models): qwen3-8b, gpt-oss-20b, qwen3-30b, deepseek-r1, qwq-32b,
                   grok-3-gemma3-12b, ministral-14b, devstral-24b, glm-4.7,
                   gemma-3-12b, qwen3-coder-30b, nemotron-30b, etc.
  OL1 (5 models): qwen3:1.7b, minimax:cloud, glm-5:cloud, kimi:cloud, gpt-oss:120b-cloud
  M2 (15 models): deepseek-r1, qwen3-8b, gpt-oss-20b, nemotron, glm-4.7, etc.
  M3 (9 models):  deepseek-r1, gpt-oss-20b, nemotron, phi-3.1, mistral-7b
  HF cloud:       Qwen3.5-27B
  OpenClaw:       40 agents
"""

import asyncio
import json
import os
import sys
import time
import random
import sqlite3
from pathlib import Path
from datetime import datetime

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

HF_TOKEN = os.getenv("HF_TOKEN", "")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT", "")
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ultra_stress_v2.db"

# ══════════════════════════════════════════════════════════════════════
# ALL NODES — every model on every machine
# ══════════════════════════════════════════════════════════════════════
NODES = {
    # ── M1 Local (6 GPU, parallel=11) ──
    "M1/qwen3-8b":        {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "qwen3-8b", "type": "openai", "timeout": 15, "sys": "/nothink\n"},
    "M1/gpt-oss-20b":     {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "gpt-oss-20b", "type": "openai", "timeout": 30, "sys": "/nothink\n"},
    "M1/qwen3-30b":       {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "qwen3-30b-a3b-instruct-2507", "type": "openai", "timeout": 30, "sys": "/nothink\n"},
    "M1/deepseek-r1":     {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "deepseek-r1-0528-qwen3-8b", "type": "openai", "timeout": 30, "sys": ""},
    "M1/qwq-32b":         {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "qwq-32b", "type": "openai", "timeout": 30, "sys": "/nothink\n"},
    "M1/grok3-12b":       {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "grok-3-gemma3-12b-distilled", "type": "openai", "timeout": 20, "sys": "/nothink\n"},
    "M1/glm-4.7":         {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "glm-4.7-flash", "type": "openai", "timeout": 20, "sys": "/nothink\n"},
    "M1/gemma3-12b":      {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "gemma-3-12b-it", "type": "openai", "timeout": 20, "sys": "/nothink\n"},
    "M1/devstral-24b":    {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "devstral-small-2-24b-instruct-2512", "type": "openai", "timeout": 30, "sys": "/nothink\n"},
    "M1/qwen3-coder-30b": {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "qwen3-coder-30b-a3b-instruct", "type": "openai", "timeout": 30, "sys": "/nothink\n"},
    "M1/nemotron-30b":    {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "nvidia-nemotron-3-nano-30b-a3b", "type": "openai", "timeout": 30, "sys": "/nothink\n"},
    "M1/ministral-14b":   {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "ministral-3-14b-reasoning-2512", "type": "openai", "timeout": 30, "sys": ""},
    "M1/llama-1b":        {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "llama-3.2-1b-instruct", "type": "openai", "timeout": 10, "sys": "/nothink\n"},
    "M1/rnj-1":           {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "rnj-1-instruct", "type": "openai", "timeout": 20, "sys": "/nothink\n"},
    "M1/lfm2.5-1.2b":     {"url": "http://127.0.0.1:1234/v1/chat/completions", "model": "lfm2.5-1.2b-instruct", "type": "openai", "timeout": 10, "sys": "/nothink\n"},
    # ── OL1 Ollama (local + cloud) ──
    "OL1/qwen3:1.7b":     {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b", "type": "ollama", "timeout": 10},
    "OL1/minimax-cloud":   {"url": "http://127.0.0.1:11434/api/chat", "model": "minimax-m2.5:cloud", "type": "ollama", "timeout": 20},
    "OL1/glm5-cloud":      {"url": "http://127.0.0.1:11434/api/chat", "model": "glm-5:cloud", "type": "ollama", "timeout": 20},
    "OL1/kimi-cloud":      {"url": "http://127.0.0.1:11434/api/chat", "model": "kimi-k2.5:cloud", "type": "ollama", "timeout": 20},
    "OL1/gpt-oss-cloud":   {"url": "http://127.0.0.1:11434/api/chat", "model": "gpt-oss:120b-cloud", "type": "ollama", "timeout": 30},
    # ── M2 Distant (3 GPU) ──
    "M2/deepseek-r1":     {"url": "http://192.168.1.26:1234/v1/chat/completions", "model": "deepseek-r1-0528-qwen3-8b", "type": "openai", "timeout": 15, "sys": ""},
    "M2/qwen3-8b":        {"url": "http://192.168.1.26:1234/v1/chat/completions", "model": "qwen/qwen3-8b", "type": "openai", "timeout": 15, "sys": "/nothink\n"},
    "M2/gpt-oss-20b":     {"url": "http://192.168.1.26:1234/v1/chat/completions", "model": "openai/gpt-oss-20b", "type": "openai", "timeout": 20, "sys": "/nothink\n"},
    "M2/nemotron":        {"url": "http://192.168.1.26:1234/v1/chat/completions", "model": "nvidia/nemotron-3-nano", "type": "openai", "timeout": 15, "sys": "/nothink\n"},
    "M2/glm-4.7":         {"url": "http://192.168.1.26:1234/v1/chat/completions", "model": "zai-org/glm-4.7-flash", "type": "openai", "timeout": 15, "sys": "/nothink\n"},
    # ── M3 Distant (1 GPU) ──
    "M3/deepseek-r1":     {"url": "http://192.168.1.113:1234/v1/chat/completions", "model": "deepseek/deepseek-r1-0528-qwen3-8b", "type": "openai", "timeout": 10, "sys": ""},
    "M3/gpt-oss-20b":     {"url": "http://192.168.1.113:1234/v1/chat/completions", "model": "openai/gpt-oss-20b", "type": "openai", "timeout": 10, "sys": "/nothink\n"},
    "M3/nemotron":        {"url": "http://192.168.1.113:1234/v1/chat/completions", "model": "nvidia/nemotron-3-nano", "type": "openai", "timeout": 10, "sys": "/nothink\n"},
    "M3/mistral-7b":      {"url": "http://192.168.1.113:1234/v1/chat/completions", "model": "mistral-7b-instruct-v0.3", "type": "openai", "timeout": 10, "sys": "/nothink\n"},
    # ── HuggingFace Cloud ──
    "HF/Qwen3.5-27B":    {"url": "https://router.huggingface.co/novita/v3/openai/chat/completions", "model": "Qwen/Qwen3.5-27B", "type": "openai", "timeout": 20, "auth": f"Bearer {HF_TOKEN}"},
}

# ── OpenClaw agents to test ──
OPENCLAW_AGENTS = [
    "coding", "fast-chat", "deep-work", "trading", "debug-detective",
    "creative-brainstorm", "data-analyst", "securite-audit", "doc-writer",
    "recherche-synthese", "consensus-master", "translator", "trading-scanner",
    "m1-deep", "m1-reason", "ol1-fast", "ol1-web", "system-ops",
    "code-champion", "analysis-engine", "deep-reasoning", "voice-assistant",
    "pipeline-monitor", "pipeline-trading", "devops-ci", "quick-dispatch",
]

# ── Diverse prompts (50) ──
PROMPTS = [
    "Ecris une fonction Python quicksort optimisee",
    "Corrige: KeyError dans un dict nested",
    "Cree un decorator retry avec backoff exponentiel",
    "Refactorise avec le pattern Strategy",
    "Test pytest pour une API FastAPI",
    "Escargot 3m jour 2m nuit mur 10m combien de jours",
    "Prouve racine(2) irrationnel",
    "Si A implique B et B implique C alors A implique C ?",
    "Analyse technique BTC RSI 65 MACD convergent",
    "Compare DCA vs lump sum ETH 2025",
    "Architecture event-driven notifications",
    "PostgreSQL vs SQLite 10M rows 50 req/s",
    "Pattern circuit breaker exemple concret",
    "Consensus Raft distribue explication",
    "Nom de projet dashboard IA temps reel",
    "Slogan JARVIS 5 mots",
    "FastAPI 422 debug schema Pydantic",
    "asyncio.CancelledError producer-consumer",
    "Integrale x*ln(x) dx",
    "Probabilite 3 as sur 5 cartes tirees de 52",
    "Nouveautes Python 3.13",
    "Tendances crypto mars 2026",
    "1337 * 42 =",
    "Capitale du Japon",
    "Pi 10 decimales",
    "Ecris un haiku sur le machine learning",
    "Compare Redis vs Memcached",
    "Optimise SELECT * FROM logs WHERE ts > now()-1h",
    "Difference WebSocket vs SSE vs long polling",
    "Script bash monitor disk usage alerte 90%",
    "Trading RSI MACD PEPE momentum",
    "Singleton vs dependency injection avantages",
    "GPU offloading comment ca marche",
    "Cree une classe Python LinkedList",
    "Explique les goroutines Go vs async Python",
    "Architecture hexagonale vs clean architecture",
    "Kubernetes vs Docker Swarm pour 50 pods",
    "SOLID principes avec exemples Python",
    "Rate limiter token bucket implementation",
    "Bloom filter probabiliste explication",
    "B-tree vs LSM-tree pour une DB",
    "Zero-copy networking explication",
    "Lock-free queue en C++ principe",
    "MapReduce vs Spark streaming differences",
    "gRPC vs REST pour microservices internes",
    "CRDT types et cas d'usage",
    "Ecris un parser JSON minimal en Python",
    "Compare transformer vs RNN pour du NLP",
    "Backpropagation expliquee simplement",
    "Monte Carlo Tree Search pour jeux",
]

# ══════════════════════════════════════════════════════════════════════
# Auto-learn state
# ══════════════════════════════════════════════════════════════════════
node_stats = {}
for nid in NODES:
    node_stats[nid] = {"ok": 0, "fail": 0, "total_ms": 0, "weight": 1.0, "disabled": False, "consecutive_fail": 0}

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS cycles (
        id INTEGER PRIMARY KEY, cycle INT, node TEXT, model TEXT,
        ok BOOLEAN, ms INT, response_len INT, error TEXT, ts REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS autolearn (
        id INTEGER PRIMARY KEY, cycle INT, node TEXT,
        weight REAL, success_rate REAL, avg_ms INT, action TEXT, ts REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS agent_tests (
        id INTEGER PRIMARY KEY, cycle INT, agent TEXT,
        ok BOOLEAN, ms INT, response_len INT, ts REAL
    )""")
    conn.commit()
    return conn


async def call_node(client, nid, cfg, prompt):
    if node_stats[nid]["disabled"]:
        return {"node": nid, "ok": False, "ms": 0, "err": "disabled", "len": 0}
    t0 = time.time()
    try:
        headers = {"Content-Type": "application/json"}
        if "auth" in cfg:
            headers["Authorization"] = cfg["auth"]

        if cfg["type"] == "ollama":
            body = {"model": cfg["model"], "messages": [{"role": "user", "content": prompt}], "stream": False, "think": False}
        else:
            sys_prefix = cfg.get("sys", "")
            messages = [{"role": "system", "content": f"{sys_prefix}Tu es JARVIS. Reponds en francais, concis."}, {"role": "user", "content": prompt}]
            body = {"model": cfg["model"], "messages": messages, "max_tokens": 200, "temperature": 0.3, "stream": False}

        resp = await client.post(cfg["url"], json=body, headers=headers, timeout=cfg["timeout"])
        ms = int((time.time() - t0) * 1000)
        if resp.status_code != 200:
            return {"node": nid, "ok": False, "ms": ms, "err": f"HTTP {resp.status_code}", "len": 0}

        data = resp.json()
        if cfg["type"] == "ollama":
            text = data.get("message", {}).get("content", "")
        else:
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"node": nid, "ok": bool(text.strip()), "ms": ms, "len": len(text), "err": None}
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return {"node": nid, "ok": False, "ms": ms, "err": str(e)[:80], "len": 0}


async def call_openclaw_agent(client, agent, prompt):
    t0 = time.time()
    try:
        resp = await client.post(
            "http://127.0.0.1:18789/v1/chat/completions",
            json={"model": agent, "messages": [{"role": "user", "content": prompt}], "max_tokens": 200, "stream": False},
            timeout=30,
        )
        ms = int((time.time() - t0) * 1000)
        if resp.status_code != 200:
            return {"agent": agent, "ok": False, "ms": ms, "len": 0}
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"agent": agent, "ok": bool(text.strip()), "ms": ms, "len": len(text)}
    except Exception:
        return {"agent": agent, "ok": False, "ms": int((time.time() - t0) * 1000), "len": 0}


def autolearn(cycle, conn):
    """Auto-adjust: disable failing nodes, boost good ones."""
    actions = []
    for nid, s in node_stats.items():
        total = s["ok"] + s["fail"]
        if total < 5:
            continue
        sr = s["ok"] / total
        avg = s["total_ms"] // max(s["ok"], 1)

        # Disable if <10% success
        if sr < 0.10 and not s["disabled"]:
            s["disabled"] = True
            s["weight"] = 0.0
            actions.append(f"DISABLE {nid} (sr={sr:.0%})")
        # Re-enable if was disabled but got 3 consecutive OK
        elif s["disabled"] and s["consecutive_fail"] == 0 and s["ok"] > 3:
            s["disabled"] = False
            s["weight"] = 0.5
            actions.append(f"RE-ENABLE {nid}")
        # Boost weight for fast+reliable nodes
        elif sr > 0.9 and avg < 5000:
            s["weight"] = min(s["weight"] + 0.05, 3.0)
        # Decrease weight for slow nodes
        elif sr > 0.5 and avg > 15000:
            s["weight"] = max(s["weight"] - 0.1, 0.3)
        # Decrease for unreliable
        elif sr < 0.5:
            s["weight"] = max(s["weight"] - 0.1, 0.1)

        conn.execute(
            "INSERT INTO autolearn (cycle, node, weight, success_rate, avg_ms, action, ts) VALUES (?,?,?,?,?,?,?)",
            (cycle, nid, s["weight"], sr, avg, "|".join(actions) if actions else "adjust", time.time())
        )
    conn.commit()
    return actions


async def send_telegram(client, text):
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
    TOTAL = 10_000
    AGENT_INTERVAL = 50  # test agents every N cycles

    conn = init_db()
    all_ok = all_fail = 0
    agent_ok = agent_fail = 0
    t_global = time.time()

    # Group nodes by HOST to avoid model-loading conflicts on LM Studio
    HOST_GROUPS = {
        "M1": [n for n in NODES if n.startswith("M1/")],
        "OL1": [n for n in NODES if n.startswith("OL1/")],
        "M2": [n for n in NODES if n.startswith("M2/")],
        "M3": [n for n in NODES if n.startswith("M3/")],
        "HF": [n for n in NODES if n.startswith("HF/")],
    }

    print(f"\n{'='*70}")
    print(f"  JARVIS ULTRA STRESS AUTO-AMELIORATIF")
    print(f"  {TOTAL} cycles | {len(NODES)} nodes | {len(OPENCLAW_AGENTS)} agents | {len(PROMPTS)} prompts")
    print(f"  Strategy: 1 model/host/cycle (rotate models), all hosts parallel")
    print(f"  DB: {DB_PATH}")
    print(f"{'='*70}\n")
    sys.stdout.flush()

    async with httpx.AsyncClient() as client:
        await send_telegram(client, f"<b>ULTRA STRESS START</b>\n{TOTAL} cycles | {len(NODES)} nodes | {len(OPENCLAW_AGENTS)} agents\nStrategy: 1 model/host, rotate")

        for cycle in range(TOTAL):
            prompt = PROMPTS[cycle % len(PROMPTS)]

            # Pick 1 model per host (rotate through models each cycle)
            selected = []
            for host, models in HOST_GROUPS.items():
                enabled = [m for m in models if not node_stats[m]["disabled"]]
                if not enabled:
                    continue
                # Rotate: pick model based on cycle index
                pick = enabled[cycle % len(enabled)]
                selected.append(pick)

            # Launch 1 per host in parallel (max 5 concurrent = fast!)
            tasks = [call_node(client, nid, NODES[nid], prompt) for nid in selected]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, Exception):
                    all_fail += 1
                    continue
                nid = r["node"]
                s = node_stats[nid]
                if r["ok"]:
                    all_ok += 1
                    s["ok"] += 1
                    s["total_ms"] += r["ms"]
                    s["consecutive_fail"] = 0
                else:
                    all_fail += 1
                    s["fail"] += 1
                    s["consecutive_fail"] += 1
                conn.execute(
                    "INSERT INTO cycles (cycle, node, model, ok, ms, response_len, error, ts) VALUES (?,?,?,?,?,?,?,?)",
                    (cycle, nid, NODES[nid]["model"], r["ok"], r["ms"], r["len"], r.get("err"), time.time())
                )

            # Commit every cycle for real-time monitoring
            conn.commit()

            # Test OpenClaw agents periodically
            if cycle > 0 and cycle % AGENT_INTERVAL == 0:
                agent = OPENCLAW_AGENTS[(cycle // AGENT_INTERVAL) % len(OPENCLAW_AGENTS)]
                ar = await call_openclaw_agent(client, agent, prompt)
                if ar["ok"]:
                    agent_ok += 1
                else:
                    agent_fail += 1
                conn.execute(
                    "INSERT INTO agent_tests (cycle, agent, ok, ms, response_len, ts) VALUES (?,?,?,?,?,?)",
                    (cycle, agent, ar["ok"], ar["ms"], ar["len"], time.time())
                )

            # Auto-learn every 100 cycles
            if cycle > 0 and cycle % 100 == 0:
                actions = autolearn(cycle, conn)
                conn.commit()

            done = cycle + 1
            elapsed = int(time.time() - t_global)

            # Progress every 100 cycles
            if done % 100 == 0:
                avg = node_stats.get("M1/qwen3-8b", {}).get("total_ms", 0) // max(node_stats.get("M1/qwen3-8b", {}).get("ok", 1), 1)
                active = len([n for n in node_stats.values() if not n["disabled"]])
                disabled = len([n for n in node_stats.values() if n["disabled"]])
                line = f"  [{done}/{TOTAL}] OK={all_ok} FAIL={all_fail} agents={agent_ok}ok/{agent_fail}fail active={active} disabled={disabled} elapsed={elapsed}s"
                print(line)
                sys.stdout.flush()

            # Telegram every 500 cycles
            if done % 500 == 0:
                active = len([n for n in node_stats.values() if not n["disabled"]])
                top5 = sorted(node_stats.items(), key=lambda x: x[1]["ok"], reverse=True)[:5]
                top_str = "\n".join(
                    f"  {n}: {s['ok']}ok w={s['weight']:.1f} avg={s['total_ms']//max(s['ok'],1)}ms"
                    for n, s in top5
                )
                await send_telegram(client, (
                    f"<b>ULTRA [{done}/{TOTAL}]</b>\n"
                    f"OK={all_ok} FAIL={all_fail}\n"
                    f"Active: {active}/{len(NODES)} | Agents: {agent_ok}ok/{agent_fail}fail\n"
                    f"Elapsed: {elapsed}s\n\n<b>Top 5:</b>\n{top_str}"
                ))

        # ── FINAL REPORT ──
        elapsed = int(time.time() - t_global)
        conn.commit()

        print(f"\n{'='*70}")
        print(f"  ULTRA STRESS COMPLETE — {TOTAL} cycles")
        print(f"{'='*70}")
        print(f"  Total: {all_ok+all_fail} | OK: {all_ok} | FAIL: {all_fail} | Rate: {all_ok*100//(all_ok+all_fail+1)}%")
        print(f"  Agents: {agent_ok} OK / {agent_fail} FAIL")
        print(f"  Time: {elapsed}s ({elapsed//3600}h{(elapsed%3600)//60}m)")
        print(f"\n  Per-node breakdown (sorted by success):")
        for nid, s in sorted(node_stats.items(), key=lambda x: x[1]["ok"], reverse=True):
            total = s["ok"] + s["fail"]
            if total == 0:
                continue
            sr = s["ok"] * 100 // total
            avg = s["total_ms"] // max(s["ok"], 1)
            status = "DISABLED" if s["disabled"] else "ACTIVE"
            print(f"    {nid:25s} OK={s['ok']:5d} FAIL={s['fail']:5d} sr={sr:3d}% avg={avg:5d}ms w={s['weight']:.1f} [{status}]")
        sys.stdout.flush()

        # Telegram final
        top10 = sorted(node_stats.items(), key=lambda x: x[1]["ok"], reverse=True)[:10]
        report = "\n".join(
            f"  {n}: {s['ok']}ok/{s['fail']}fail w={s['weight']:.1f}"
            for n, s in top10
        )
        await send_telegram(client, (
            f"<b>ULTRA STRESS DONE</b>\n"
            f"OK={all_ok} FAIL={all_fail} | {elapsed//3600}h{(elapsed%3600)//60}m\n"
            f"Agents: {agent_ok}/{agent_fail}\n\n<b>Top 10:</b>\n{report}"
        ))

        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
