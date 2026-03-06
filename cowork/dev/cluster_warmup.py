#!/usr/bin/env python3
"""cluster_warmup.py — Warm up cluster nodes after startup.

Pre-loads models, populates caches, and validates all nodes are responsive.
Designed to run once after system boot or LM Studio restart.

Steps:
1. Probe each node with simple request (model loading)
2. Run mini-benchmark (3 tests per node)
3. Populate dispatch cache with common prompts
4. Update latency baselines
5. Refresh reliability scores
6. Send startup report

CLI:
    --once         : Full warmup cycle
    --quick        : Quick probe only
    --report       : Send warmup report to Telegram

Stdlib-only (json, argparse, sqlite3, urllib, time, subprocess).
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"

NODES = {
    "M1":  {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b",
            "ollama": False, "prefix": "/nothink\n", "timeout": 30},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
            "ollama": True, "timeout": 20},
    "M2":  {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "ollama": False, "max_tokens": 2048, "timeout": 60},
    "M3":  {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "ollama": False, "max_tokens": 2048, "timeout": 60},
}

WARMUP_PROMPTS = [
    {"prompt": "/nothink\nOK", "type": "simple"},
    {"prompt": "/nothink\ndef add(a,b): return a+b", "type": "code"},
    {"prompt": "/nothink\n2+2=?", "type": "math"},
]


def dispatch_node(node_name, prompt, timeout=30):
    """Send prompt to node."""
    node = NODES.get(node_name)
    if not node:
        return None

    start = time.time()
    try:
        if node.get("ollama"):
            body = json.dumps({
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False,
            }).encode()
        else:
            prefix = node.get("prefix", "")
            max_tokens = node.get("max_tokens", 1024)
            body = json.dumps({
                "model": node["model"],
                "input": f"{prefix}{prompt}",
                "temperature": 0.2, "max_output_tokens": max_tokens,
                "stream": False, "store": False,
            }).encode()

        req = urllib.request.Request(node["url"], data=body,
                                     headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        elapsed = int((time.time() - start) * 1000)

        if node.get("ollama"):
            text = data.get("message", {}).get("content", "")
        else:
            text = ""
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    content = item.get("content", [])
                    if content and isinstance(content, list):
                        text = content[0].get("text", "")
                    elif isinstance(content, str):
                        text = content
                    break

        return {"success": True, "text": text, "latency_ms": elapsed}
    except Exception as e:
        return {"success": False, "error": str(e)[:100],
                "latency_ms": int((time.time() - start) * 1000)}


def run_script(name, args, timeout=60):
    """Run a cowork script."""
    script = SCRIPT_DIR / name
    if not script.exists():
        return False
    try:
        r = subprocess.run(
            [sys.executable, str(script)] + args,
            capture_output=True, text=True, timeout=timeout, cwd=str(SCRIPT_DIR)
        )
        return r.returncode == 0
    except Exception:
        return False


def send_telegram(text):
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def warmup_full(report=False):
    """Full warmup cycle."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] === Cluster Warmup ===\n")

    results = {}
    total_start = time.time()

    # Step 1: Probe each node
    print("[1/5] Probing nodes...")
    for name in NODES:
        timeout = NODES[name].get("timeout", 30)
        r = dispatch_node(name, "/nothink\nOK", timeout)
        if r and r["success"]:
            results[name] = {"status": "online", "probe_ms": r["latency_ms"]}
            print(f"  + {name:4} online ({r['latency_ms']}ms)")
        else:
            results[name] = {"status": "offline", "error": r.get("error", "") if r else "timeout"}
            print(f"  - {name:4} offline ({r.get('error', 'timeout')[:40] if r else 'timeout'})")

    # Step 2: Mini benchmark on online nodes
    print("\n[2/5] Mini benchmark...")
    online = [n for n, v in results.items() if v["status"] == "online"]
    for name in online:
        ok = 0
        total_lat = 0
        for wp in WARMUP_PROMPTS:
            timeout = NODES[name].get("timeout", 30)
            r = dispatch_node(name, wp["prompt"], timeout)
            if r and r["success"]:
                ok += 1
                total_lat += r["latency_ms"]
        results[name]["benchmark"] = f"{ok}/{len(WARMUP_PROMPTS)}"
        results[name]["avg_ms"] = total_lat // max(ok, 1)
        print(f"  {name:4} {ok}/{len(WARMUP_PROMPTS)} OK  avg={results[name]['avg_ms']}ms")

    # Step 3: Update latency baselines
    print("\n[3/5] Updating baselines...")
    ok = run_script("latency_monitor.py", ["--once"], timeout=60)
    print(f"  {'OK' if ok else 'SKIP'}")

    # Step 4: Refresh reliability scores
    print("\n[4/5] Refreshing reliability...")
    ok = run_script("node_reliability_scorer.py", ["--once", "--update"], timeout=30)
    print(f"  {'OK' if ok else 'SKIP'}")

    # Step 5: Grade check
    print("\n[5/5] Grade check...")
    ok = run_script("grade_optimizer.py", ["--analyze"], timeout=15)
    print(f"  {'OK' if ok else 'SKIP'}")

    total_ms = int((time.time() - total_start) * 1000)
    online_count = len(online)

    print(f"\n=== Warmup Complete ===")
    print(f"  Nodes: {online_count}/{len(NODES)} online")
    print(f"  Duration: {total_ms}ms")

    summary = {
        "timestamp": datetime.now().isoformat(),
        "nodes_online": online_count,
        "nodes_total": len(NODES),
        "duration_ms": total_ms,
        "results": results,
    }

    if report:
        lines = [f"<b>Cluster Warmup</b> <code>{ts}</code>",
                 f"{online_count}/{len(NODES)} nodes online ({total_ms}ms)"]
        for name, data in sorted(results.items()):
            s = "+" if data["status"] == "online" else "-"
            bench = data.get("benchmark", "?")
            avg = data.get("avg_ms", 0)
            lines.append(f"  {s} {name}: {bench} avg={avg}ms")
        send_telegram("\n".join(lines))
        print("  Report sent to Telegram")

    print(json.dumps(summary, indent=2))
    return summary


def warmup_quick():
    """Quick probe only."""
    print("Quick warmup...")
    for name in NODES:
        timeout = NODES[name].get("timeout", 15)
        r = dispatch_node(name, "/nothink\nOK", min(timeout, 15))
        if r and r["success"]:
            print(f"  + {name:4} {r['latency_ms']}ms")
        else:
            err = r.get("error", "timeout")[:40] if r else "timeout"
            print(f"  - {name:4} {err}")


def main():
    parser = argparse.ArgumentParser(description="Cluster Warmup")
    parser.add_argument("--once", action="store_true", help="Full warmup")
    parser.add_argument("--quick", action="store_true", help="Quick probe")
    parser.add_argument("--report", action="store_true", help="Send report")
    args = parser.parse_args()

    if not any([args.once, args.quick]):
        parser.print_help()
        sys.exit(1)

    if args.quick:
        warmup_quick()
    elif args.once:
        warmup_full(report=args.report)


if __name__ == "__main__":
    main()
