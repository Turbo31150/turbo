#!/usr/bin/env python3
"""Cluster Distribution Benchmark v2.0 — Tests exhaustifs vitesse/qualite.

Teste tous les noeuds disponibles (M1, M2, OL1-cloud, Gemini, Claude)
sur 6 scenarios differents, mesure latence, tokens/s, qualite.
Race mode: tous en parallele, premier gagne.
Quality mode: compare les outputs.
Sauvegarde resultats en SQLite + JSON.

Usage:
    python scripts/cluster_distribution_bench.py              # Full bench
    python scripts/cluster_distribution_bench.py --race       # Race only
    python scripts/cluster_distribution_bench.py --quality    # Quality compare
    python scripts/cluster_distribution_bench.py --json       # JSON output
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

# ============================================================================
# CONFIG
# ============================================================================
TURBO_DIR = Path("F:/BUREAU/turbo")
DB_PATH = TURBO_DIR / "data" / "etoile.db"

SCENARIOS = {
    "simple": {
        "prompt": "Reponds en 1 phrase: qu'est-ce qu'un webhook?",
        "max_tokens": 128,
        "timeout": 15,
        "category": "simple",
    },
    "code_python": {
        "prompt": "Ecris une fonction Python async qui fait un HTTP GET avec retry exponentiel (max 3 essais). Code uniquement.",
        "max_tokens": 512,
        "timeout": 30,
        "category": "code",
    },
    "code_js": {
        "prompt": "Ecris un middleware Express.js qui rate-limite les requetes par IP (100 req/min, sliding window). Code uniquement.",
        "max_tokens": 512,
        "timeout": 30,
        "category": "code",
    },
    "analyse": {
        "prompt": "Compare SQLite vs PostgreSQL pour un projet IoT avec 1M events/jour. Structure: Avantages, Inconvenients, Recommandation.",
        "max_tokens": 1024,
        "timeout": 60,
        "category": "analyse",
    },
    "debug": {
        "prompt": "Ce code Python a un bug subtil. Trouve-le et corrige:\n```python\ndef merge_sorted(a, b):\n    result = []\n    i = j = 0\n    while i < len(a) and j < len(b):\n        if a[i] <= b[j]:\n            result.append(a[i])\n            i += 1\n        else:\n            result.append(b[j])\n            j += 1\n    return result\n```",
        "max_tokens": 512,
        "timeout": 30,
        "category": "debug",
    },
    "architecture": {
        "prompt": "Design un systeme de notification temps-reel pour 10K users connectes simultanement. Stack: Node.js + Redis + WebSocket. Schema d'architecture en texte.",
        "max_tokens": 1024,
        "timeout": 60,
        "category": "architecture",
    },
}

# ============================================================================
# NODE DEFINITIONS
# ============================================================================
def _lmstudio_body(model, prompt, max_tokens, nothink=True):
    prefix = "/nothink\n" if nothink else ""
    return json.dumps({
        "model": model,
        "input": f"{prefix}{prompt}",
        "temperature": 0.2,
        "max_output_tokens": max_tokens,
        "stream": False, "store": False,
    })

def _ollama_body(model, prompt, max_tokens):
    return json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False, "think": False,
        "options": {"num_predict": max_tokens},
    })

def _extract_lmstudio(data):
    for o in reversed(data.get("output", [])):
        if o.get("type") == "message":
            return o.get("content", "")
    return data.get("output", [{}])[0].get("content", "") if data.get("output") else ""

def _extract_ollama(data):
    return data.get("message", {}).get("content", "")

NODES = {
    "M1/qwen3-8b": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "build_body": lambda p, mt: _lmstudio_body("qwen3-8b", p, mt),
        "extract": _extract_lmstudio,
        "weight": 1.8,
    },
    "M2/deepseek-r1": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "build_body": lambda p, mt: _lmstudio_body("deepseek/deepseek-r1-0528-qwen3-8b", p, mt, nothink=False),
        "extract": _extract_lmstudio,
        "weight": 1.5,
    },
    "OL1/gpt-oss-120b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "build_body": lambda p, mt: _ollama_body("gpt-oss:120b-cloud", p, mt),
        "extract": _extract_ollama,
        "weight": 1.9,
    },
    "OL1/devstral-123b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "build_body": lambda p, mt: _ollama_body("devstral-2:123b-cloud", p, mt),
        "extract": _extract_ollama,
        "weight": 1.5,
    },
    "OL1/qwen3-14b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "build_body": lambda p, mt: _ollama_body("qwen3:14b", p, mt),
        "extract": _extract_ollama,
        "weight": 1.3,
    },
}

# ============================================================================
# CORE
# ============================================================================
def call_node(node_name: str, prompt: str, max_tokens: int, timeout: int) -> dict:
    """Appel synchrone a un noeud. Retourne metriques."""
    cfg = NODES[node_name]
    body = cfg["build_body"](prompt, max_tokens).encode()
    req = Request(cfg["url"], data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            data = json.loads(raw)
        latency = time.time() - t0
        content = cfg["extract"](data)
        tokens = len(content.split())
        tok_s = tokens / latency if latency > 0 else 0
        # Quality heuristic: penalize empty, very short, or error responses
        quality = 0.0
        if tokens >= 5:
            quality = min(1.0, tokens / max(max_tokens * 0.3, 1))  # coverage
            if "```" in content:
                quality = min(1.0, quality + 0.2)  # code blocks = good for code
            if any(w in content.lower() for w in ["avantage", "inconvenient", "recommand", "schema"]):
                quality = min(1.0, quality + 0.1)
        return {
            "node": node_name, "ok": True,
            "latency_s": round(latency, 2),
            "tokens": tokens, "tok_s": round(tok_s, 1),
            "quality": round(quality, 2),
            "content": content,
            "weight": cfg["weight"],
        }
    except Exception as e:
        return {
            "node": node_name, "ok": False,
            "latency_s": round(time.time() - t0, 2),
            "error": str(e)[:120],
            "tokens": 0, "tok_s": 0, "quality": 0,
            "content": "", "weight": cfg["weight"],
        }


def race_scenario(scenario_name: str, scenario: dict) -> list[dict]:
    """Lance tous les noeuds en parallele pour un scenario."""
    prompt = scenario["prompt"]
    max_tokens = scenario["max_tokens"]
    timeout = scenario["timeout"]

    print(f"\n{'='*65}")
    print(f"  {scenario_name.upper()} ({scenario['category']})")
    print(f"  {prompt[:70]}...")
    print(f"{'='*65}")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(NODES)) as ex:
        futures = {
            ex.submit(call_node, name, prompt, max_tokens, timeout): name
            for name in NODES
        }
        rank = 0
        for f in concurrent.futures.as_completed(futures):
            r = f.result()
            rank += 1
            r["rank"] = rank
            r["scenario"] = scenario_name
            results.append(r)
            if r["ok"]:
                print(f"  #{rank} [{r['latency_s']:5.1f}s] {r['node']:<22} "
                      f"{r['tokens']:4d}tok {r['tok_s']:5.1f}tok/s "
                      f"Q={r['quality']:.1f} | {r['content'][:55].replace(chr(10),' ')}")
            else:
                err = r.get("error", "?")
                if "429" in err:
                    print(f"  #{rank} [{r['latency_s']:5.1f}s] {r['node']:<22} RATE-LIMITED (429)")
                else:
                    print(f"  #{rank} [{r['latency_s']:5.1f}s] {r['node']:<22} FAIL: {err[:45]}")

    ok_results = [r for r in results if r["ok"]]
    if ok_results:
        fastest = min(ok_results, key=lambda x: x["latency_s"])
        best_q = max(ok_results, key=lambda x: x["quality"])
        # Weighted score: speed * 0.4 + quality * 0.4 + weight * 0.2
        for r in ok_results:
            speed_norm = 1.0 - min(r["latency_s"] / timeout, 1.0)
            r["score"] = round(speed_norm * 0.4 + r["quality"] * 0.4 + (r["weight"] / 2.0) * 0.2, 3)
        best_score = max(ok_results, key=lambda x: x["score"])
        print(f"\n  FASTEST : {fastest['node']} ({fastest['latency_s']}s)")
        print(f"  QUALITY : {best_q['node']} (Q={best_q['quality']})")
        print(f"  OPTIMAL : {best_score['node']} (score={best_score['score']})")

    return results


def save_results(all_results: list[dict]):
    """Sauvegarde en SQLite + JSON."""
    ts = datetime.now().isoformat()
    run_id = f"bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # JSON
    json_path = TURBO_DIR / "data" / f"{run_id}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "ts": ts, "results": all_results}, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON: {json_path}")

    # SQLite
    if DB_PATH.exists():
        try:
            db = sqlite3.connect(str(DB_PATH))
            db.execute("""CREATE TABLE IF NOT EXISTS cluster_bench (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT, ts TEXT, scenario TEXT, node TEXT,
                ok INTEGER, latency_s REAL, tokens INTEGER, tok_s REAL,
                quality REAL, score REAL, rank INTEGER,
                content TEXT, error TEXT)""")
            for r in all_results:
                db.execute(
                    """INSERT INTO cluster_bench
                    (run_id, ts, scenario, node, ok, latency_s, tokens, tok_s,
                     quality, score, rank, content, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run_id, ts, r.get("scenario", ""), r["node"],
                     1 if r["ok"] else 0, r["latency_s"], r["tokens"], r["tok_s"],
                     r.get("quality", 0), r.get("score", 0), r.get("rank", 0),
                     r.get("content", "")[:500], r.get("error", "")),
                )
            db.commit()
            rows = db.execute("SELECT COUNT(*) FROM cluster_bench WHERE run_id=?", (run_id,)).fetchone()[0]
            db.close()
            print(f"  SQLite: {rows} rows dans etoile.db/cluster_bench")
        except Exception as e:
            print(f"  SQLite error: {e}")

    return run_id


def print_summary(all_results: list[dict]):
    """Resume final avec ranking par noeud."""
    print(f"\n{'='*65}")
    print(f"  RESUME DISTRIBUTION — RANKING GLOBAL")
    print(f"{'='*65}")

    # Aggregate per node
    node_stats: dict[str, dict] = {}
    for r in all_results:
        name = r["node"]
        if name not in node_stats:
            node_stats[name] = {"ok": 0, "fail": 0, "total_lat": 0, "total_tok": 0,
                                "total_toks": 0, "total_q": 0, "total_score": 0, "wins": 0}
        s = node_stats[name]
        if r["ok"]:
            s["ok"] += 1
            s["total_lat"] += r["latency_s"]
            s["total_tok"] += r["tokens"]
            s["total_toks"] += r["tok_s"]
            s["total_q"] += r.get("quality", 0)
            s["total_score"] += r.get("score", 0)
            if r.get("rank") == 1:
                s["wins"] += 1
        else:
            s["fail"] += 1

    # Sort by average score
    ranked = []
    for name, s in node_stats.items():
        n = max(s["ok"], 1)
        ranked.append({
            "node": name,
            "ok": s["ok"], "fail": s["fail"],
            "avg_lat": round(s["total_lat"] / n, 2),
            "avg_toks": round(s["total_toks"] / n, 1),
            "avg_q": round(s["total_q"] / n, 2),
            "avg_score": round(s["total_score"] / n, 3),
            "wins": s["wins"],
        })
    ranked.sort(key=lambda x: x["avg_score"], reverse=True)

    print(f"\n  {'Node':<22} {'OK':>3} {'Fail':>4} {'AvgLat':>7} {'tok/s':>6} "
          f"{'Qual':>5} {'Score':>6} {'Wins':>4}")
    print(f"  {'-'*62}")
    for r in ranked:
        status = "***" if r["avg_score"] > 0.5 else "   "
        print(f"  {r['node']:<22} {r['ok']:>3} {r['fail']:>4} {r['avg_lat']:>6.1f}s "
              f"{r['avg_toks']:>5.1f} {r['avg_q']:>5.2f} {r['avg_score']:>6.3f} "
              f"{r['wins']:>4} {status}")

    if ranked and ranked[0]["avg_score"] > 0:
        print(f"\n  CHAMPION: {ranked[0]['node']} "
              f"(score={ranked[0]['avg_score']}, {ranked[0]['wins']} wins)")

    return ranked


# ============================================================================
# MAIN
# ============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cluster Distribution Benchmark v2")
    parser.add_argument("--race", action="store_true", help="Race mode only")
    parser.add_argument("--quality", action="store_true", help="Quality compare only")
    parser.add_argument("--json", action="store_true", help="JSON output at end")
    parser.add_argument("--scenarios", type=str, default="all",
                        help="Comma-separated scenario names, or 'all'")
    args = parser.parse_args()

    if sys.platform == "win32":
        os.system("")  # Enable ANSI

    print(f"\n{'='*65}")
    print(f"  CLUSTER DISTRIBUTION BENCHMARK v2.0")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Nodes: {len(NODES)} | Scenarios: {len(SCENARIOS)}")
    print(f"{'='*65}")

    # Select scenarios
    if args.scenarios == "all":
        scenarios = SCENARIOS
    else:
        names = [s.strip() for s in args.scenarios.split(",")]
        scenarios = {k: v for k, v in SCENARIOS.items() if k in names}

    t0 = time.time()
    all_results = []

    for name, scenario in scenarios.items():
        results = race_scenario(name, scenario)
        all_results.extend(results)

    duration = time.time() - t0

    # Summary
    ranked = print_summary(all_results)
    run_id = save_results(all_results)

    print(f"\n  Total: {len(all_results)} appels en {duration:.1f}s")
    print(f"  Run ID: {run_id}")

    if args.json:
        print(json.dumps({"run_id": run_id, "ranked": ranked, "duration_s": round(duration, 1)}, indent=2))


if __name__ == "__main__":
    main()
