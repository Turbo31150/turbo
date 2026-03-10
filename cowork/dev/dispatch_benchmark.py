#!/usr/bin/env python3
"""Benchmark dispatch engine — send test prompts and measure avg latency/quality."""

import argparse
import json
import time
import urllib.request
import urllib.error

DISPATCH_URL = "http://127.0.0.1:9742/api/dispatch_engine/dispatch"

TEST_PROMPTS = [
    "What is 2+2?",
    "Explain Python decorators in one sentence.",
    "List 3 sorting algorithms.",
    "What is the capital of France?",
    "Convert 100 Fahrenheit to Celsius.",
]


def dispatch(prompt, timeout=30):
    """Send a prompt to dispatch engine, return response + timing."""
    payload = json.dumps({"prompt": prompt}).encode()
    req = urllib.request.Request(
        DISPATCH_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            elapsed = round(time.perf_counter() - t0, 3)
            return {"ok": True, "latency_s": elapsed, "data": data}
    except Exception as e:
        elapsed = round(time.perf_counter() - t0, 3)
        return {"ok": False, "latency_s": elapsed, "error": str(e)}


def run_once():
    results = []
    for i, prompt in enumerate(TEST_PROMPTS):
        result = dispatch(prompt)
        result["prompt"] = prompt
        result["index"] = i + 1
        results.append(result)

    latencies = [r["latency_s"] for r in results]
    successes = [r for r in results if r["ok"]]
    qualities = []
    for r in successes:
        q = r.get("data", {}).get("quality_score")
        if q is not None:
            qualities.append(q)

    benchmark = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_prompts": len(TEST_PROMPTS),
        "successes": len(successes),
        "failures": len(results) - len(successes),
        "avg_latency_s": round(sum(latencies) / len(latencies), 3) if latencies else 0,
        "min_latency_s": round(min(latencies), 3) if latencies else 0,
        "max_latency_s": round(max(latencies), 3) if latencies else 0,
        "avg_quality": round(sum(qualities) / len(qualities), 2) if qualities else None,
        "results": results,
    }
    print(json.dumps(benchmark, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Benchmark dispatch engine latency/quality")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        print("Use --once for a single run. Use --help for options.")


if __name__ == "__main__":
    main()
