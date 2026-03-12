#!/usr/bin/env python3
"""IA Benchmark: measure M1 tokens/sec via chat completions API."""
import argparse
import json
import time
import sys
import urllib.request
import urllib.error

M1_URL = "http://127.0.0.1:1234/v1/chat/completions"
DEFAULT_PROMPT = "Explain quicksort in 3 sentences."


def benchmark_m1(prompt: str, model: str = "qwen3-8b",
                 max_tokens: int = 256, temperature: float = 0.3) -> dict:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        M1_URL, data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return {"error": str(e), "elapsed_sec": round(time.monotonic() - t0, 3)}

    elapsed = time.monotonic() - t0
    usage = data.get("usage", {})
    completion_tokens = usage.get("completion_tokens", 0)
    prompt_tokens = usage.get("prompt_tokens", 0)
    tps = round(completion_tokens / elapsed, 1) if elapsed > 0 and completion_tokens else 0
    content = ""
    choices = data.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content", "")

    return {
        "model": data.get("model", model),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "elapsed_sec": round(elapsed, 3),
        "tokens_per_sec": tps,
        "response_preview": content[:200],
    }


def benchmark_cycle(prompt: str, model: str, runs: int) -> dict:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    results = []
    for i in range(runs):
        r = benchmark_m1(prompt, model)
        r["run"] = i + 1
        results.append(r)
    tps_values = [r["tokens_per_sec"] for r in results if r.get("tokens_per_sec", 0) > 0]
    avg_tps = round(sum(tps_values) / len(tps_values), 1) if tps_values else 0
    return {
        "timestamp": ts,
        "runs": results,
        "avg_tokens_per_sec": avg_tps,
        "success_rate": f"{len(tps_values)}/{runs}",
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark M1 tokens/sec")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT)
    parser.add_argument("--model", type=str, default="qwen3-8b")
    parser.add_argument("--runs", type=int, default=3, help="Number of benchmark runs")
    parser.add_argument("--interval", type=int, default=600, help="Loop interval (sec)")
    args = parser.parse_args()

    while True:
        result = benchmark_cycle(args.prompt, args.model, args.runs)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.once:
            sys.exit(0 if result["avg_tokens_per_sec"] > 0 else 1)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
