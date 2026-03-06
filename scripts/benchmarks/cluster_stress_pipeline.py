#!/usr/bin/env python3
"""Cluster Stress Pipeline v1.0 — Tests massifs multi-scenarios.

Teste la distribution de taches en crescendo:
  Phase 1: Micro-taches (1 ligne) — routing rapide
  Phase 2: Taches moyennes (code) — parallelisme
  Phase 3: Taches longues (analyse) — endurance
  Phase 4: Mix pipeline (chaine de taches) — orchestration
  Phase 5: Race conditions — tous noeuds meme tache
  Phase 6: Circuit routing — tache → noeud optimal

Mesure: latence, throughput, qualite, routing optimal.
Sauvegarde: SQLite + JSON.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

TURBO = Path("F:/BUREAU/turbo")
DB_PATH = TURBO / "data" / "etoile.db"

# ============================================================================
# NODES
# ============================================================================
def call_lmstudio(url, model, prompt, max_tokens, nothink=True, timeout=60):
    prefix = "/nothink\n" if nothink else ""
    body = json.dumps({
        "model": model, "input": f"{prefix}{prompt}",
        "temperature": 0.2, "max_output_tokens": max_tokens,
        "stream": False, "store": False,
    }).encode()
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urlopen(req, timeout=timeout) as resp:
        d = json.loads(resp.read().decode())
    lat = time.time() - t0
    content = ""
    for o in reversed(d.get("output", [])):
        if o.get("type") == "message":
            content = o.get("content", "")
            break
    return lat, content

def call_ollama(model, prompt, max_tokens, timeout=90):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False, "think": False,
        "options": {"num_predict": max_tokens},
    }).encode()
    req = Request("http://127.0.0.1:11434/api/chat", data=body,
                  headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urlopen(req, timeout=timeout) as resp:
        d = json.loads(resp.read().decode())
    lat = time.time() - t0
    return lat, d.get("message", {}).get("content", "")

NODES = {
    "M1": lambda p, mt: call_lmstudio("http://127.0.0.1:1234/api/v1/chat", "qwen3-8b", p, mt),
    "M2": lambda p, mt: call_lmstudio("http://192.168.1.26:1234/api/v1/chat",
                                       "deepseek/deepseek-r1-0528-qwen3-8b", p, mt, False),
    "M3": lambda p, mt: call_lmstudio("http://192.168.1.113:1234/api/v1/chat",
                                       "deepseek/deepseek-r1-0528-qwen3-8b", p, mt, False),
    "OL1-14b": lambda p, mt: call_ollama("qwen3:14b", p, mt),
    "OL1-cloud": lambda p, mt: call_ollama("gpt-oss:120b-cloud", p, mt),
}

def safe_call(node_name, prompt, max_tokens):
    try:
        lat, content = NODES[node_name](prompt, max_tokens)
        toks = len(content.split())
        return {
            "node": node_name, "ok": True, "lat": round(lat, 2),
            "toks": toks, "toks_s": round(toks / max(lat, 0.01), 1),
            "content": content[:300],
        }
    except Exception as e:
        err = str(e)[:80]
        return {"node": node_name, "ok": False, "lat": 0, "toks": 0, "toks_s": 0,
                "error": err, "content": ""}

# ============================================================================
# ROUTING
# ============================================================================
ROUTING = {
    "micro":  ["M1", "OL1-14b", "M2"],
    "code":   ["M1", "M2", "OL1-14b"],
    "analyse": ["M1", "M2", "M3"],
    "debug":  ["M1", "M2"],
    "archi":  ["M1", "M2", "M3"],
}

def route(category):
    return ROUTING.get(category, ["M1", "M2"])

# ============================================================================
# TASK DEFINITIONS
# ============================================================================
MICRO_TASKS = [
    ("Qu'est-ce que REST?", 64),
    ("Difference entre let et const en JS?", 64),
    ("Qu'est-ce qu'un mutex?", 64),
    ("C'est quoi CORS?", 64),
    ("Explique TCP vs UDP en 1 phrase.", 64),
    ("Qu'est-ce qu'un index SQL?", 64),
    ("Difference entre stack et heap?", 64),
    ("C'est quoi un CDN?", 64),
    ("Qu'est-ce que le DNS?", 64),
    ("Explique OAuth2 en 1 phrase.", 64),
]

CODE_TASKS = [
    ("Ecris un decorateur Python de cache LRU.", 256),
    ("Ecris un middleware Express.js de logging.", 256),
    ("Ecris une classe TypeScript de file d'attente (queue).", 256),
    ("Ecris un generateur Python de nombres de Fibonacci.", 128),
    ("Ecris une fonction de debounce en JavaScript.", 192),
]

ANALYSE_TASKS = [
    ("Compare les architectures microservices vs monolithe pour une startup. 3 criteres.", 512),
    ("Analyse les trade-offs entre consistance forte et eventuelle dans un systeme distribue.", 512),
    ("Explique le CAP theorem avec des exemples concrets de bases de donnees.", 512),
]

CHAIN_TASKS = [
    # (prompt1, prompt2_template) — output de 1 est input de 2
    ("Liste 3 design patterns pour un systeme de cache.",
     "Pour chaque pattern ci-dessous, donne un exemple de code Python:\n{prev}"),
    ("Identifie 3 failles de securite courantes dans une API REST.",
     "Pour chaque faille ci-dessous, ecris un test Python qui detecte la faille:\n{prev}"),
]

# ============================================================================
# PHASES
# ============================================================================
def phase_micro():
    """Phase 1: 10 micro-taches en rafale sur M1."""
    print(f"\n{'='*60}")
    print(f"  PHASE 1 — MICRO-TACHES (10x, route=M1)")
    print(f"{'='*60}")
    results = []
    t0 = time.time()
    for i, (prompt, mt) in enumerate(MICRO_TASKS):
        r = safe_call("M1", prompt, mt)
        results.append(r)
        status = f"{r['lat']:.1f}s {r['toks']}tok" if r["ok"] else "FAIL"
        print(f"  [{i+1:2d}/10] {status:20s} | {prompt[:40]}")
    duration = time.time() - t0
    ok = [r for r in results if r["ok"]]
    avg_lat = sum(r["lat"] for r in ok) / max(len(ok), 1)
    throughput = len(ok) / duration
    print(f"\n  Resultats: {len(ok)}/10 OK | Avg: {avg_lat:.2f}s | Throughput: {throughput:.1f} req/s | Total: {duration:.1f}s")
    return {"phase": "micro", "results": results, "duration": round(duration, 1),
            "throughput": round(throughput, 2), "avg_lat": round(avg_lat, 2)}


def phase_code_parallel():
    """Phase 2: 5 taches code en parallele sur M1+M2."""
    print(f"\n{'='*60}")
    print(f"  PHASE 2 — CODE PARALLELE (5x, M1+M2)")
    print(f"{'='*60}")
    results = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = []
        for i, (prompt, mt) in enumerate(CODE_TASKS):
            # Alternate between M1 and M2
            node = "M1" if i % 2 == 0 else "M2"
            futures.append((i, prompt, ex.submit(safe_call, node, prompt, mt)))
        for i, prompt, f in futures:
            r = f.result()
            results.append(r)
            if r["ok"]:
                print(f"  [{i+1}] {r['node']:8s} {r['lat']:5.1f}s {r['toks']:4d}tok | {prompt[:40]}")
            else:
                print(f"  [{i+1}] {r['node']:8s} FAIL | {prompt[:40]}")
    duration = time.time() - t0
    ok = [r for r in results if r["ok"]]
    print(f"\n  Resultats: {len(ok)}/5 OK | Total: {duration:.1f}s")
    return {"phase": "code_parallel", "results": results, "duration": round(duration, 1)}


def phase_analyse_distributed():
    """Phase 3: 3 analyses longues distribuees sur M1+M2+M3."""
    print(f"\n{'='*60}")
    print(f"  PHASE 3 — ANALYSE DISTRIBUEE (3x, M1+M2+M3)")
    print(f"{'='*60}")
    node_cycle = ["M1", "M2", "M3"]
    results = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futures = []
        for i, (prompt, mt) in enumerate(ANALYSE_TASKS):
            node = node_cycle[i % len(node_cycle)]
            futures.append((i, prompt, node, ex.submit(safe_call, node, prompt, mt)))
        for i, prompt, node, f in futures:
            r = f.result()
            results.append(r)
            if r["ok"]:
                print(f"  [{i+1}] {r['node']:8s} {r['lat']:5.1f}s {r['toks']:4d}tok | {prompt[:45]}")
            else:
                print(f"  [{i+1}] {r['node']:8s} FAIL: {r.get('error','')[:30]} | {prompt[:35]}")
    duration = time.time() - t0
    ok = [r for r in results if r["ok"]]
    print(f"\n  Resultats: {len(ok)}/3 OK | Total: {duration:.1f}s")
    return {"phase": "analyse_distributed", "results": results, "duration": round(duration, 1)}


def phase_chain():
    """Phase 4: Pipeline chaine — output noeud 1 → input noeud 2."""
    print(f"\n{'='*60}")
    print(f"  PHASE 4 -- PIPELINE CHAINE (2 chains, M1->M2)")
    print(f"{'='*60}")
    results = []
    t0 = time.time()
    for i, (prompt1, prompt2_tpl) in enumerate(CHAIN_TASKS):
        # Step 1: M1
        print(f"  Chain {i+1} Step 1 (M1): {prompt1[:50]}...")
        r1 = safe_call("M1", prompt1, 256)
        results.append({**r1, "chain": i+1, "step": 1})
        if r1["ok"]:
            print(f"    → {r1['lat']:.1f}s {r1['toks']}tok")
            # Step 2: M2 with output of step 1
            chained_prompt = prompt2_tpl.format(prev=r1["content"][:400])
            print(f"  Chain {i+1} Step 2 (M2): {chained_prompt[:50]}...")
            r2 = safe_call("M2", chained_prompt, 512)
            results.append({**r2, "chain": i+1, "step": 2})
            if r2["ok"]:
                print(f"    → {r2['lat']:.1f}s {r2['toks']}tok")
            else:
                print(f"    → FAIL: {r2.get('error','')[:40]}")
        else:
            print(f"    → FAIL step 1, skip chain")
    duration = time.time() - t0
    ok = [r for r in results if r["ok"]]
    print(f"\n  Resultats: {len(ok)}/{len(results)} OK | Total: {duration:.1f}s")
    return {"phase": "chain", "results": results, "duration": round(duration, 1)}


def phase_race():
    """Phase 5: Race — meme tache sur tous les noeuds, premier gagne."""
    print(f"\n{'='*60}")
    print(f"  PHASE 5 — RACE (1 tache, tous noeuds)")
    print(f"{'='*60}")
    prompt = "Ecris un serveur WebSocket minimaliste en Python avec asyncio. Code uniquement."
    available = ["M1", "M2", "M3", "OL1-14b"]  # skip cloud (429)
    results = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(available)) as ex:
        futures = {ex.submit(safe_call, n, prompt, 512): n for n in available}
        rank = 0
        for f in concurrent.futures.as_completed(futures):
            r = f.result()
            rank += 1
            r["rank"] = rank
            results.append(r)
            if r["ok"]:
                winner = " *** WINNER ***" if rank == 1 else ""
                print(f"  #{rank} [{r['lat']:5.1f}s] {r['node']:<14} {r['toks']:4d}tok {r['toks_s']:5.1f}tok/s{winner}")
            else:
                print(f"  #{rank} [     ] {r['node']:<14} FAIL: {r.get('error','')[:30]}")
    duration = time.time() - t0
    print(f"\n  Total: {duration:.1f}s")
    return {"phase": "race", "results": results, "duration": round(duration, 1)}


def phase_routing_test():
    """Phase 6: Test routing — tache → noeud optimal automatique."""
    print(f"\n{'='*60}")
    print(f"  PHASE 6 — ROUTING AUTO (5 categories)")
    print(f"{'='*60}")
    test_cases = [
        ("micro", "C'est quoi un webhook?", 64),
        ("code", "Ecris un singleton thread-safe en Python.", 256),
        ("analyse", "Compare Redis vs Memcached pour un cache applicatif.", 512),
        ("debug", "Trouve le bug: def fib(n): return fib(n-1) + fib(n-2)", 256),
        ("archi", "Design un pipeline ETL pour 1M rows/jour.", 512),
    ]
    results = []
    t0 = time.time()
    for cat, prompt, mt in test_cases:
        nodes = route(cat)
        primary = nodes[0]
        r = safe_call(primary, prompt, mt)
        r["category"] = cat
        r["routed_to"] = primary
        results.append(r)
        if r["ok"]:
            print(f"  [{cat:8s}] → {primary:8s} {r['lat']:5.1f}s {r['toks']:4d}tok | {prompt[:40]}")
        else:
            # Fallback
            if len(nodes) > 1:
                r2 = safe_call(nodes[1], prompt, mt)
                r2["category"] = cat
                r2["routed_to"] = f"{primary}→{nodes[1]}"
                results.append(r2)
                if r2["ok"]:
                    print(f"  [{cat:8s}] → {nodes[1]:8s} {r2['lat']:5.1f}s (fallback) | {prompt[:35]}")
                else:
                    print(f"  [{cat:8s}] → BOTH FAIL")
    duration = time.time() - t0
    ok = [r for r in results if r["ok"]]
    print(f"\n  Resultats: {len(ok)}/{len(test_cases)} OK | Total: {duration:.1f}s")
    return {"phase": "routing", "results": results, "duration": round(duration, 1)}


# ============================================================================
# SAVE
# ============================================================================
def save_all(phases: list[dict]):
    ts = datetime.now().isoformat()
    run_id = f"stress_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # JSON
    json_path = TURBO / "data" / f"{run_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "ts": ts, "phases": phases}, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON: {json_path}")

    # SQLite
    if DB_PATH.exists():
        try:
            db = sqlite3.connect(str(DB_PATH))
            db.execute("""CREATE TABLE IF NOT EXISTS stress_pipeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT, ts TEXT, phase TEXT, node TEXT,
                ok INTEGER, lat REAL, toks INTEGER, toks_s REAL,
                category TEXT, routed_to TEXT)""")
            total = 0
            for ph in phases:
                for r in ph.get("results", []):
                    db.execute(
                        """INSERT INTO stress_pipeline
                        (run_id,ts,phase,node,ok,lat,toks,toks_s,category,routed_to)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (run_id, ts, ph["phase"], r["node"], 1 if r["ok"] else 0,
                         r["lat"], r["toks"], r["toks_s"],
                         r.get("category", ""), r.get("routed_to", "")))
                    total += 1
            db.commit()
            db.close()
            print(f"  SQLite: {total} rows dans etoile.db/stress_pipeline")
        except Exception as e:
            print(f"  SQLite error: {e}")

    return run_id


# ============================================================================
# MAIN
# ============================================================================
def main():
    if sys.platform == "win32":
        os.system("")

    print(f"\n{'='*60}")
    print(f"  CLUSTER STRESS PIPELINE v1.0")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Phases: 6 | Noeuds: {len(NODES)}")
    print(f"{'='*60}")

    t0 = time.time()
    phases = []

    phases.append(phase_micro())
    phases.append(phase_code_parallel())
    phases.append(phase_analyse_distributed())
    phases.append(phase_chain())
    phases.append(phase_race())
    phases.append(phase_routing_test())

    total_duration = time.time() - t0

    # Summary
    print(f"\n{'='*60}")
    print(f"  RESUME PIPELINE")
    print(f"{'='*60}")
    total_ok = 0
    total_tasks = 0
    for ph in phases:
        ok = sum(1 for r in ph.get("results", []) if r["ok"])
        total = len(ph.get("results", []))
        total_ok += ok
        total_tasks += total
        print(f"  {ph['phase']:22s} {ok:2d}/{total:2d} OK  {ph['duration']:6.1f}s")

    print(f"\n  TOTAL: {total_ok}/{total_tasks} OK en {total_duration:.1f}s")

    run_id = save_all(phases)
    print(f"  Run: {run_id}")


if __name__ == "__main__":
    main()
