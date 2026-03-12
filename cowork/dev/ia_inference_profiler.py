#!/usr/bin/env python3
"""ia_inference_profiler.py — Profileur inference IA.

Mesure performance detaillee de chaque modele.

Usage:
    python dev/ia_inference_profiler.py --once
    python dev/ia_inference_profiler.py --profile
    python dev/ia_inference_profiler.py --compare
    python dev/ia_inference_profiler.py --report
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "inference_profiler.db"
TEST_PROMPT = "Write a Python function that checks if a number is prime. Keep it short."

ENDPOINTS = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "body": lambda p: json.dumps({
            "model": "qwen3-8b", "input": f"/nothink\n{p}",
            "temperature": 0.2, "max_output_tokens": 256,
            "stream": False, "store": False,
        }),
        "extract": "lmstudio",
    },
    "OL1-local": {
        "url": "http://127.0.0.1:11434/api/chat",
        "body": lambda p: json.dumps({
            "model": "qwen3:1.7b", "messages": [{"role": "user", "content": p}],
            "stream": False,
        }),
        "extract": "ollama",
    },
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, node TEXT, latency_ms REAL,
        tokens INTEGER, tok_per_s REAL, quality_score REAL)""")
    db.commit()
    return db


def profile_endpoint(name, config):
    body = config["body"](TEST_PROMPT)
    try:
        start = time.time()
        out = subprocess.run(
            ["curl", "-s", "--max-time", "30", config["url"],
             "-H", "Content-Type: application/json", "-d", body],
            capture_output=True, text=True, timeout=35
        )
        latency = (time.time() - start) * 1000

        if out.returncode != 0 or not out.stdout.strip():
            return {"node": name, "online": False, "error": "No response"}

        data = json.loads(out.stdout)
        text = ""
        tokens = 0

        if config["extract"] == "lmstudio":
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            text = c.get("text", "")
            tokens = data.get("usage", {}).get("output_tokens", len(text.split()))
        else:  # ollama
            text = data.get("message", {}).get("content", "")
            tokens = data.get("eval_count", len(text.split()))

        tok_s = tokens / max(latency / 1000, 0.1)

        # Quality heuristic
        quality = 0.0
        if "def " in text:
            quality += 0.3
        if "prime" in text.lower():
            quality += 0.2
        if "return" in text:
            quality += 0.2
        if len(text) > 50:
            quality += 0.2
        if "```" in text:
            quality += 0.1

        return {
            "node": name,
            "online": True,
            "latency_ms": round(latency),
            "tokens": tokens,
            "tok_per_s": round(tok_s, 1),
            "quality_score": round(min(quality, 1.0), 2),
            "response_length": len(text),
        }
    except Exception as e:
        return {"node": name, "online": False, "error": str(e)[:100]}


def do_profile():
    db = init_db()
    results = []

    for name, config in ENDPOINTS.items():
        r = profile_endpoint(name, config)
        results.append(r)
        if r.get("online"):
            db.execute("INSERT INTO profiles (ts, node, latency_ms, tokens, tok_per_s, quality_score) VALUES (?,?,?,?,?,?)",
                       (time.time(), name, r["latency_ms"], r["tokens"], r["tok_per_s"], r["quality_score"]))

    db.commit()
    db.close()

    results.sort(key=lambda x: x.get("tok_per_s", 0), reverse=True)
    return {
        "ts": datetime.now().isoformat(),
        "prompt": TEST_PROMPT[:50],
        "results": results,
        "fastest": results[0]["node"] if results and results[0].get("online") else "none",
        "best_quality": max(results, key=lambda x: x.get("quality_score", 0))["node"] if results else "none",
    }


def main():
    parser = argparse.ArgumentParser(description="IA Inference Profiler")
    parser.add_argument("--once", "--profile", action="store_true", help="Profile")
    parser.add_argument("--compare", action="store_true", help="Compare models")
    parser.add_argument("--optimize", action="store_true", help="Optimize")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()
    print(json.dumps(do_profile(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
