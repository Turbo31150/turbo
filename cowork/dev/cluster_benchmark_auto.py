#!/usr/bin/env python3
"""cluster_benchmark_auto.py — Mini-benchmark cluster automatique.

Lance 5 prompts Python sur M1/OL1/M2, mesure tok/s + quality,
compare aux scores precedents, alerte si degradation >15%.

Usage:
    python dev/cluster_benchmark_auto.py --once
    python dev/cluster_benchmark_auto.py --bench
    python dev/cluster_benchmark_auto.py --compare
    python dev/cluster_benchmark_auto.py --report
"""
import argparse
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "cluster_bench.db"
TELEGRAM_PROXY = "http://127.0.0.1:18800"

# Test prompts (Python focused)
PROMPTS = [
    {"id": "fizzbuzz", "prompt": "Write a Python function fizzbuzz(n) that returns 'Fizz' for multiples of 3, 'Buzz' for multiples of 5, 'FizzBuzz' for both, else the number as string.", "expected": "def fizzbuzz"},
    {"id": "fibonacci", "prompt": "Write a Python function fibonacci(n) that returns the nth Fibonacci number using iteration.", "expected": "def fibonacci"},
    {"id": "palindrome", "prompt": "Write a Python function is_palindrome(s) that checks if a string is a palindrome, ignoring case and spaces.", "expected": "def is_palindrome"},
    {"id": "sort", "prompt": "Write a Python function merge_sort(arr) that implements merge sort.", "expected": "def merge_sort"},
    {"id": "api", "prompt": "Write a Python async function fetch_json(url) using urllib that fetches a URL and returns the parsed JSON.", "expected": "def fetch_json"},
]

# Nodes to benchmark
NODES = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "model": "qwen3-8b",
        "format": "lmstudio",
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b",
        "format": "ollama",
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "model": "deepseek-r1-0528-qwen3-8b",
        "format": "lmstudio",
    },
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS bench_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, node TEXT, prompt_id TEXT,
        latency_s REAL, tokens INTEGER, tok_s REAL,
        quality_score REAL, response_preview TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS bench_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, nodes_tested INTEGER, prompts_tested INTEGER,
        avg_tok_s REAL, avg_quality REAL, degradation_detected INTEGER,
        report TEXT)""")
    db.commit()
    return db


def query_lmstudio(url, model, prompt, timeout=30):
    """Query LM Studio Responses API."""
    data = json.dumps({
        "model": model,
        "input": f"/nothink\n{prompt}",
        "temperature": 0.3,
        "max_output_tokens": 512,
        "stream": False,
        "store": False,
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        result = json.loads(r.read().decode())
    latency = time.time() - start

    # Extract text from output
    text = ""
    for item in reversed(result.get("output", [])):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    text = c.get("text", "")
                    break
            if text:
                break

    tokens = len(text.split())
    return {"text": text, "latency": latency, "tokens": tokens}


def query_ollama(url, model, prompt, timeout=60):
    """Query Ollama API."""
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        result = json.loads(r.read().decode())
    latency = time.time() - start

    text = result.get("message", {}).get("content", "")
    tokens = len(text.split())
    return {"text": text, "latency": latency, "tokens": tokens}


def score_quality(response_text, expected_keyword):
    """Score response quality (0-1)."""
    score = 0.0
    text = response_text.strip()

    if not text:
        return 0.0

    # Contains expected keyword
    if expected_keyword.lower() in text.lower():
        score += 0.4

    # Contains Python code (def, return, etc.)
    code_markers = ["def ", "return ", "if ", "for ", "while "]
    matches = sum(1 for m in code_markers if m in text)
    score += min(matches * 0.1, 0.3)

    # Reasonable length
    if 50 < len(text) < 2000:
        score += 0.2

    # Has proper indentation (Python style)
    if "    " in text:
        score += 0.1

    return round(min(score, 1.0), 3)


def benchmark_node(node_name, node_config, prompts):
    """Benchmark a single node with all prompts."""
    results = []
    for p in prompts:
        try:
            if node_config["format"] == "lmstudio":
                resp = query_lmstudio(node_config["url"], node_config["model"], p["prompt"])
            else:
                resp = query_ollama(node_config["url"], node_config["model"], p["prompt"])

            quality = score_quality(resp["text"], p["expected"])
            tok_s = resp["tokens"] / max(resp["latency"], 0.01)

            results.append({
                "node": node_name,
                "prompt_id": p["id"],
                "latency_s": round(resp["latency"], 2),
                "tokens": resp["tokens"],
                "tok_s": round(tok_s, 1),
                "quality": quality,
                "preview": resp["text"][:150],
            })
        except Exception as e:
            results.append({
                "node": node_name,
                "prompt_id": p["id"],
                "error": str(e),
                "quality": 0,
                "tok_s": 0,
            })

    return results


def get_previous_scores(db, node_name, limit=3):
    """Get previous benchmark scores for comparison."""
    rows = db.execute("""
        SELECT AVG(tok_s), AVG(quality_score)
        FROM bench_results
        WHERE node=? AND ts > ?
        GROUP BY CAST(ts / 86400 AS INTEGER)
        ORDER BY ts DESC LIMIT ?
    """, (node_name, time.time() - 7 * 86400, limit)).fetchall()

    if rows:
        avg_tok = sum(r[0] for r in rows if r[0]) / max(len(rows), 1)
        avg_q = sum(r[1] for r in rows if r[1]) / max(len(rows), 1)
        return {"avg_tok_s": round(avg_tok, 1), "avg_quality": round(avg_q, 3)}
    return None


def send_telegram_alert(message):
    """Send alert via Telegram proxy."""
    try:
        data = json.dumps({"text": message}).encode()
        req = urllib.request.Request(
            f"{TELEGRAM_PROXY}/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def do_bench():
    """Run full benchmark."""
    db = init_db()
    all_results = []
    degradation = False

    for node_name, node_config in NODES.items():
        results = benchmark_node(node_name, node_config, PROMPTS)
        all_results.extend(results)

        # Store results
        for r in results:
            if "error" not in r:
                db.execute(
                    "INSERT INTO bench_results (ts, node, prompt_id, latency_s, tokens, tok_s, quality_score, response_preview) VALUES (?,?,?,?,?,?,?,?)",
                    (time.time(), r["node"], r["prompt_id"],
                     r.get("latency_s", 0), r.get("tokens", 0),
                     r.get("tok_s", 0), r.get("quality", 0),
                     r.get("preview", ""))
                )

        # Compare with previous
        prev = get_previous_scores(db, node_name)
        if prev:
            current_tok = sum(r.get("tok_s", 0) for r in results) / max(len(results), 1)
            if prev["avg_tok_s"] > 0 and current_tok < prev["avg_tok_s"] * 0.85:
                degradation = True

    # Summary
    nodes_ok = len(set(r["node"] for r in all_results if "error" not in r))
    avg_tok = sum(r.get("tok_s", 0) for r in all_results) / max(len(all_results), 1)
    avg_q = sum(r.get("quality", 0) for r in all_results) / max(len(all_results), 1)

    report = {
        "ts": datetime.now().isoformat(),
        "nodes_tested": nodes_ok,
        "prompts_tested": len(PROMPTS),
        "avg_tok_s": round(avg_tok, 1),
        "avg_quality": round(avg_q, 3),
        "degradation_detected": degradation,
        "results_by_node": {},
    }

    for node_name in NODES:
        node_results = [r for r in all_results if r["node"] == node_name]
        report["results_by_node"][node_name] = {
            "avg_tok_s": round(sum(r.get("tok_s", 0) for r in node_results) / max(len(node_results), 1), 1),
            "avg_quality": round(sum(r.get("quality", 0) for r in node_results) / max(len(node_results), 1), 3),
            "errors": sum(1 for r in node_results if "error" in r),
        }

    db.execute(
        "INSERT INTO bench_runs (ts, nodes_tested, prompts_tested, avg_tok_s, avg_quality, degradation_detected, report) VALUES (?,?,?,?,?,?,?)",
        (time.time(), nodes_ok, len(PROMPTS), avg_tok, avg_q, 1 if degradation else 0, json.dumps(report))
    )
    db.commit()
    db.close()

    # Alert if degradation
    if degradation:
        msg = f"[CLUSTER BENCH] DEGRADATION DETECTED\nAvg tok/s: {avg_tok:.1f}, Quality: {avg_q:.3f}\n"
        for name, data in report["results_by_node"].items():
            msg += f"  {name}: {data['avg_tok_s']} tok/s, Q={data['avg_quality']}\n"
        send_telegram_alert(msg)

    return report


def get_report():
    """Get benchmark history."""
    db = init_db()
    rows = db.execute("SELECT * FROM bench_runs ORDER BY ts DESC LIMIT 10").fetchall()
    db.close()
    report = []
    for r in rows:
        report.append({
            "ts": datetime.fromtimestamp(r[1]).isoformat() if r[1] else None,
            "nodes": r[2], "prompts": r[3],
            "avg_tok_s": r[4], "avg_quality": r[5],
            "degradation": bool(r[6]),
        })
    return report


def main():
    parser = argparse.ArgumentParser(description="Cluster Benchmark Auto — Daily automated benchmark")
    parser.add_argument("--once", "--bench", action="store_true", help="Run benchmark")
    parser.add_argument("--compare", action="store_true", help="Compare with previous runs")
    parser.add_argument("--report", action="store_true", help="Benchmark history")
    args = parser.parse_args()

    if args.report or args.compare:
        report = get_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        result = do_bench()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
