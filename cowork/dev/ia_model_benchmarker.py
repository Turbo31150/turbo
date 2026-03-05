#!/usr/bin/env python3
"""ia_model_benchmarker.py — Benchmark continu des modeles.

Execute tests standardises, compare performances, leaderboard.

Usage:
    python dev/ia_model_benchmarker.py --once
    python dev/ia_model_benchmarker.py --run
    python dev/ia_model_benchmarker.py --leaderboard
    python dev/ia_model_benchmarker.py --compare
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "model_benchmarker.db"

BENCHMARK_PROMPTS = [
    {"id": "py_sort", "prompt": "Write a Python function to merge sort a list", "expect": "def", "category": "code"},
    {"id": "py_class", "prompt": "Write a Python class for a binary search tree with insert and search", "expect": "class", "category": "code"},
    {"id": "math_deriv", "prompt": "What is the integral of sin(x)*cos(x)?", "expect": "sin", "category": "math"},
    {"id": "logic_1", "prompt": "If A implies B and B implies C, does A imply C? Explain.", "expect": "yes", "category": "reasoning"},
    {"id": "json_gen", "prompt": "Generate a JSON config for a web server with host, port, ssl, and logging fields", "expect": "{", "category": "structured"},
    {"id": "debug", "prompt": "Find the bug: def fib(n): return fib(n-1)+fib(n-2)", "expect": "base", "category": "debug"},
    {"id": "explain", "prompt": "Explain how a hash table works in 3 sentences", "expect": "key", "category": "knowledge"},
    {"id": "translate", "prompt": "Translate to French: The server is running smoothly with no errors", "expect": "serveur", "category": "language"},
]

MODELS = [
    {"name": "M1/qwen3-8b", "type": "lmstudio", "url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b"},
    {"name": "OL1/qwen3:1.7b", "type": "ollama", "url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b"},
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS benchmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, model TEXT, prompt_id TEXT,
        score REAL, latency_s REAL, tokens INTEGER,
        tok_per_s REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, model TEXT, total_score REAL,
        avg_latency_s REAL, avg_tok_s REAL, tests_passed INTEGER)""")
    db.commit()
    return db


def query_model(model_cfg, prompt, timeout=30):
    """Query a model and measure performance."""
    start = time.time()
    try:
        if model_cfg["type"] == "lmstudio":
            data = json.dumps({
                "model": model_cfg["model"],
                "input": f"/nothink\n{prompt}",
                "temperature": 0.2, "max_output_tokens": 512,
                "stream": False, "store": False,
            }).encode()
            req = urllib.request.Request(model_cfg["url"], data=data,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                result = json.loads(r.read().decode())
                latency = time.time() - start
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
                return text, latency, tokens

        elif model_cfg["type"] == "ollama":
            data = json.dumps({
                "model": model_cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }).encode()
            req = urllib.request.Request(model_cfg["url"], data=data,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                result = json.loads(r.read().decode())
                latency = time.time() - start
                text = result.get("message", {}).get("content", "")
                tokens = len(text.split())
                return text, latency, tokens

    except Exception:
        return "", time.time() - start, 0

    return "", time.time() - start, 0


def do_benchmark():
    """Run full benchmark."""
    db = init_db()
    results = {}

    for model in MODELS:
        model_results = []
        for prompt in BENCHMARK_PROMPTS:
            text, latency, tokens = query_model(model, prompt["prompt"])
            score = 0.0
            if text:
                if prompt["expect"].lower() in text.lower():
                    score = 1.0
                elif len(text) > 30:
                    score = 0.5
            tok_s = round(tokens / max(latency, 0.01), 1)

            model_results.append({
                "prompt_id": prompt["id"], "category": prompt["category"],
                "score": score, "latency_s": round(latency, 2),
                "tokens": tokens, "tok_s": tok_s,
            })

            db.execute(
                "INSERT INTO benchmarks (ts, model, prompt_id, score, latency_s, tokens, tok_per_s) VALUES (?,?,?,?,?,?,?)",
                (time.time(), model["name"], prompt["id"], score, latency, tokens, tok_s)
            )

        total_score = sum(r["score"] for r in model_results) / max(len(model_results), 1)
        avg_latency = sum(r["latency_s"] for r in model_results) / max(len(model_results), 1)
        avg_tok = sum(r["tok_s"] for r in model_results) / max(len(model_results), 1)
        passed = sum(1 for r in model_results if r["score"] >= 0.5)

        results[model["name"]] = {
            "total_score": round(total_score, 3),
            "avg_latency_s": round(avg_latency, 2),
            "avg_tok_s": round(avg_tok, 1),
            "tests_passed": passed,
            "total_tests": len(model_results),
            "details": model_results,
        }

        db.execute(
            "INSERT INTO runs (ts, model, total_score, avg_latency_s, avg_tok_s, tests_passed) VALUES (?,?,?,?,?,?)",
            (time.time(), model["name"], total_score, avg_latency, avg_tok, passed)
        )

    db.commit()
    db.close()

    return {"ts": datetime.now().isoformat(), "models": results}


def show_leaderboard():
    """Show leaderboard from history."""
    db = init_db()
    rows = db.execute(
        "SELECT model, AVG(total_score), AVG(avg_tok_s), COUNT(*) FROM runs GROUP BY model ORDER BY AVG(total_score) DESC"
    ).fetchall()
    db.close()
    return [{
        "model": r[0], "avg_score": round(r[1], 3),
        "avg_tok_s": round(r[2], 1), "runs": r[3],
    } for r in rows]


def main():
    parser = argparse.ArgumentParser(description="IA Model Benchmarker")
    parser.add_argument("--once", "--run", action="store_true", help="Run benchmark")
    parser.add_argument("--leaderboard", action="store_true", help="Show leaderboard")
    parser.add_argument("--compare", action="store_true", help="Compare models")
    parser.add_argument("--history", action="store_true", help="History")
    args = parser.parse_args()

    if args.leaderboard or args.compare:
        print(json.dumps(show_leaderboard(), ensure_ascii=False, indent=2))
    else:
        result = do_benchmark()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
