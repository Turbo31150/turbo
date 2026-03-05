#!/usr/bin/env python3
"""Cluster AutoTuner — Continuously optimize routing weights and model selection.

Reads autolearn scores from canvas proxy, benchmarks nodes,
and adjusts routing weights for optimal performance.
"""
import argparse
import json
import sqlite3
import time
import urllib.request
from pathlib import Path

DB_PATH = Path(__file__).parent / "autotuner.db"

NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/chat", "weight": 1.8},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/chat", "weight": 1.4},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/chat", "weight": 1.0},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "weight": 1.3},
}

TEST_PROMPTS = [
    ("simple", "Reponds en une phrase: quel est le langage le plus utilise en 2025?"),
    ("code", "Ecris une fonction Python qui trie une liste par frequence d'elements."),
    ("math", "Calcule la derivee de f(x) = x^3 * sin(x)."),
    ("raisonnement", "Si A implique B, et B implique C, et non-C est vrai, que peut-on deduire?"),
]

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS benchmarks (
        id INTEGER PRIMARY KEY, ts REAL, node TEXT, category TEXT,
        latency_ms REAL, tokens INTEGER, quality_score REAL, success INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS weight_history (
        id INTEGER PRIMARY KEY, ts REAL, node TEXT, old_weight REAL,
        new_weight REAL, reason TEXT)""")
    db.commit()
    return db

def bench_node(node_name, node_cfg, prompt_cat, prompt_text):
    """Benchmark a single node with a prompt."""
    url = node_cfg["url"]
    is_ollama = "11434" in url

    if is_ollama:
        body = json.dumps({
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": prompt_text}],
            "stream": False, "think": False,
        }).encode()
    else:
        model = {"M1": "qwen3-8b", "M2": "deepseek-coder-v2-lite-instruct", "M3": "mistral-7b-instruct-v0.3"}.get(node_name, "qwen3-8b")
        body = json.dumps({
            "model": model,
            "input": f"/nothink\n{prompt_text}" if node_name == "M1" else prompt_text,
            "temperature": 0.2, "max_output_tokens": 512, "stream": False, "store": False,
        }).encode()

    start = time.time()
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        latency = (time.time() - start) * 1000

        # Extract response
        if is_ollama:
            text = data.get("message", {}).get("content", "")
        else:
            text = ""
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    text = item.get("content", [{}])[0].get("text", "")
                    break

        tokens = len(text.split())
        quality = min(1.0, tokens / 20) if tokens > 5 else 0.2  # Simple heuristic
        return latency, tokens, quality, True
    except Exception:
        return (time.time() - start) * 1000, 0, 0.0, False

def get_autolearn_scores():
    """Fetch autolearn scores from canvas proxy."""
    try:
        req = urllib.request.Request("http://127.0.0.1:18800/autolearn/scores")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}

def run_benchmark(db):
    """Run full benchmark across all nodes."""
    results = {}
    for node_name, node_cfg in NODES.items():
        results[node_name] = {"total_latency": 0, "total_quality": 0, "success": 0, "fail": 0}
        for cat, prompt in TEST_PROMPTS:
            latency, tokens, quality, ok = bench_node(node_name, node_cfg, cat, prompt)
            db.execute(
                "INSERT INTO benchmarks (ts, node, category, latency_ms, tokens, quality_score, success) VALUES (?,?,?,?,?,?,?)",
                (time.time(), node_name, cat, latency, tokens, quality, 1 if ok else 0))
            if ok:
                results[node_name]["total_latency"] += latency
                results[node_name]["total_quality"] += quality
                results[node_name]["success"] += 1
            else:
                results[node_name]["fail"] += 1
    db.commit()
    return results

def compute_weights(results, db):
    """Compute new weights based on benchmark results."""
    new_weights = {}
    for node, r in results.items():
        if r["success"] == 0:
            new_weights[node] = 0.5
            continue
        avg_latency = r["total_latency"] / r["success"]
        avg_quality = r["total_quality"] / r["success"]
        # Score: quality * 0.6 + speed * 0.4 (inverse latency normalized)
        speed_score = max(0, 1.0 - (avg_latency / 10000))
        score = avg_quality * 0.6 + speed_score * 0.4
        # Map score [0-1] to weight [0.5-2.0]
        weight = round(0.5 + score * 1.5, 2)
        new_weights[node] = weight

    # Record changes
    for node, new_w in new_weights.items():
        old_w = NODES.get(node, {}).get("weight", 1.0)
        if abs(new_w - old_w) > 0.1:
            db.execute(
                "INSERT INTO weight_history (ts, node, old_weight, new_weight, reason) VALUES (?,?,?,?,?)",
                (time.time(), node, old_w, new_w, f"benchmark score"))
    db.commit()
    return new_weights

def main():
    parser = argparse.ArgumentParser(description="Cluster AutoTuner")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=7200, help="Seconds between benchmarks")
    args = parser.parse_args()

    db = init_db()

    if args.once or not args.loop:
        print("Benchmarking cluster nodes...")
        results = run_benchmark(db)
        weights = compute_weights(results, db)
        autolearn = get_autolearn_scores()

        for node, r in results.items():
            total = r["success"] + r["fail"]
            avg_lat = r["total_latency"] / r["success"] if r["success"] else 0
            avg_q = r["total_quality"] / r["success"] if r["success"] else 0
            print(f"  {node}: {r['success']}/{total} OK | avg {avg_lat:.0f}ms | quality {avg_q:.2f} | weight → {weights.get(node, '?')}")

        if autolearn:
            print(f"\nAutolearn scores: {json.dumps(autolearn, indent=2)[:500]}")

    if args.loop:
        print("AutoTuner en boucle continue...")
        while True:
            try:
                results = run_benchmark(db)
                weights = compute_weights(results, db)
                ts = time.strftime('%H:%M')
                summary = " | ".join(f"{n}={w}" for n, w in weights.items())
                print(f"[{ts}] Weights: {summary}")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
