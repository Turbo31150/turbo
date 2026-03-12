#!/usr/bin/env python3
"""ia_capability_tracker.py — Suivi des capacites IA au fil du temps.

Battery de tests standardises, compare scores historiques,
detecte regressions.

Usage:
    python dev/ia_capability_tracker.py --once
    python dev/ia_capability_tracker.py --assess
    python dev/ia_capability_tracker.py --compare
    python dev/ia_capability_tracker.py --report
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
DB_PATH = DEV / "data" / "capability_tracker.db"
M1_URL = "http://127.0.0.1:1234/api/v1/chat"
OL1_URL = "http://127.0.0.1:11434/api/chat"

CAPABILITY_TESTS = [
    {"id": "code_gen", "prompt": "Write a Python function that reverses a linked list", "expect": "def", "category": "code"},
    {"id": "math", "prompt": "What is the derivative of x^3 + 2x^2 - 5x + 3?", "expect": "3x", "category": "math"},
    {"id": "logic", "prompt": "If all roses are flowers and some flowers are red, can we conclude all roses are red?", "expect": "no", "category": "reasoning"},
    {"id": "translate", "prompt": "Translate to French: The quick brown fox jumps over the lazy dog", "expect": "renard", "category": "language"},
    {"id": "summary", "prompt": "Summarize in one sentence: Machine learning is a subset of AI that enables systems to learn from data.", "expect": "machine learning", "category": "language"},
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, node TEXT, test_id TEXT,
        score REAL, latency_s REAL, response_preview TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_score REAL, tests_passed INTEGER,
        tests_total INTEGER, report TEXT)""")
    db.commit()
    return db


def query_m1(prompt, timeout=20):
    """Query M1."""
    try:
        data = json.dumps({
            "model": "qwen3-8b", "input": f"/nothink\n{prompt}",
            "temperature": 0.3, "max_output_tokens": 256, "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(M1_URL, data=data, headers={"Content-Type": "application/json"})
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read().decode())
            latency = time.time() - start
            for item in reversed(result.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", ""), latency
        return "", time.time() - start
    except Exception:
        return "", 0


def run_test(test):
    """Run a single capability test."""
    response, latency = query_m1(test["prompt"])
    score = 0.0
    if response:
        if test["expect"].lower() in response.lower():
            score = 1.0
        elif len(response) > 20:
            score = 0.5
    return {
        "test_id": test["id"],
        "category": test["category"],
        "score": score,
        "latency_s": round(latency, 2),
        "preview": response[:100],
    }


def do_assess():
    """Run full capability assessment."""
    db = init_db()
    results = []

    for test in CAPABILITY_TESTS:
        result = run_test(test)
        results.append(result)
        db.execute(
            "INSERT INTO assessments (ts, node, test_id, score, latency_s, response_preview) VALUES (?,?,?,?,?,?)",
            (time.time(), "M1", result["test_id"], result["score"], result["latency_s"], result["preview"])
        )

    total_score = sum(r["score"] for r in results) / max(len(results), 1)
    passed = sum(1 for r in results if r["score"] >= 0.5)

    # Check for regression
    prev = db.execute("SELECT total_score FROM runs ORDER BY ts DESC LIMIT 1").fetchone()
    regression = False
    if prev and prev[0] > 0 and total_score < prev[0] * 0.85:
        regression = True

    report = {
        "ts": datetime.now().isoformat(),
        "total_score": round(total_score, 3),
        "tests_passed": passed,
        "tests_total": len(results),
        "regression_detected": regression,
        "results": results,
    }

    db.execute(
        "INSERT INTO runs (ts, total_score, tests_passed, tests_total, report) VALUES (?,?,?,?,?)",
        (time.time(), total_score, passed, len(results), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="IA Capability Tracker")
    parser.add_argument("--once", "--assess", action="store_true", help="Run assessment")
    parser.add_argument("--compare", action="store_true", help="Compare with previous")
    parser.add_argument("--report", action="store_true", help="History")
    args = parser.parse_args()

    result = do_assess()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
