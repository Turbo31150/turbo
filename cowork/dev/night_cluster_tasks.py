#!/usr/bin/env python3
"""JARVIS Night Cluster Tasks — Make the cluster work overnight.

Dispatches useful tasks to M1/M2/M3/OL1 in parallel:
1. DB optimization (VACUUM + ANALYZE all DBs)
2. Cluster benchmark (quality check all nodes)
3. Dispatch learning (analyze history, optimize routes)
4. Code quality scan (lint key modules)
5. Strategy evolution monitoring
6. Morning summary report → Telegram

Usage:
    python cowork/dev/night_cluster_tasks.py --all
    python cowork/dev/night_cluster_tasks.py --task bench
    python cowork/dev/night_cluster_tasks.py --task learn
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from _paths import TURBO_DIR as TURBO
DATA = TURBO / "data"

NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b",
            "prefix": "/nothink\n", "max_tokens": 1024, "timeout": 30},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek/deepseek-r1-0528-qwen3-8b",
            "prefix": "", "max_tokens": 2048, "timeout": 60},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek/deepseek-r1-0528-qwen3-8b",
            "prefix": "", "max_tokens": 1024, "timeout": 120},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
            "ollama": True, "max_tokens": 1024, "timeout": 30},
}

TELEGRAM_CHAT = "2010747443"


def query_lmstudio(node_name, prompt, timeout=None):
    """Query a LM Studio node."""
    node = NODES[node_name]
    if timeout is None:
        timeout = node.get("timeout", 60)
    body = json.dumps({
        "model": node["model"],
        "input": node.get("prefix", "") + prompt,
        "temperature": 0.3,
        "max_output_tokens": node.get("max_tokens", 1024),
        "stream": False, "store": False
    })
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), node["url"],
             "-H", "Content-Type: application/json", "-d", body],
            capture_output=True, text=True, timeout=timeout + 10)
        if r.returncode != 0:
            return None, f"curl error: {r.returncode}"
        data = json.loads(r.stdout)
        # Extract last message block from output[]
        for item in reversed(data.get("output", [])):
            if item.get("type") == "message":
                content = item.get("content", "")
                if isinstance(content, str):
                    return content.strip(), None
                # Fallback: content as list of objects
                for c in content:
                    if c.get("type") == "output_text":
                        return c["text"], None
        return str(data.get("output", "")), None
    except Exception as e:
        return None, str(e)


def query_ollama(prompt, model="qwen3:1.7b", timeout=30):
    """Query Ollama."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False, "think": False
    })
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout),
             "http://127.0.0.1:11434/api/chat", "-d", body],
            capture_output=True, text=True, timeout=timeout + 5)
        if r.returncode != 0:
            return None, f"curl error: {r.returncode}"
        data = json.loads(r.stdout)
        return data.get("message", {}).get("content", ""), None
    except Exception as e:
        return None, str(e)


def send_telegram(msg):
    """Send message to Telegram."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    body = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg[:4000]}).encode()
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


# ── TASK 1: DB Optimization ──────────────────────────────────

def task_db_optimize():
    """VACUUM + ANALYZE all databases."""
    print("[DB] Optimizing databases...")
    results = []
    for dbpath in DATA.glob("*.db"):
        try:
            size_before = dbpath.stat().st_size
            conn = sqlite3.connect(str(dbpath))
            conn.execute("ANALYZE")
            conn.execute("VACUUM")
            conn.commit()
            conn.close()
            size_after = dbpath.stat().st_size
            saved = size_before - size_after
            results.append(f"  {dbpath.name}: {size_after // 1024}KB (saved {saved // 1024}KB)")
        except Exception as e:
            results.append(f"  {dbpath.name}: FAIL {e}")
    return "DB Optimization", results


# ── TASK 2: Cluster Benchmark ────────────────────────────────

def task_cluster_bench():
    """Quick benchmark all nodes with a standard prompt."""
    print("[BENCH] Benchmarking cluster nodes...")
    prompt = "Write a Python function that checks if a number is prime. Just the code, no explanation."
    results = []

    def bench_node(name):
        t0 = time.time()
        if name == "OL1":
            resp, err = query_ollama(prompt)
        else:
            resp, err = query_lmstudio(name, prompt)
        elapsed = time.time() - t0
        if err:
            return f"  {name}: OFFLINE ({err[:50]})"
        has_def = "def " in (resp or "")
        tokens = len((resp or "").split())
        tps = tokens / elapsed if elapsed > 0 else 0
        return f"  {name}: {elapsed:.1f}s | {tokens}tok | {tps:.0f}tok/s | {'OK' if has_def else 'WEAK'}"

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(bench_node, n): n for n in NODES}
        for f in as_completed(futs):
            results.append(f.result())

    return "Cluster Benchmark", sorted(results)


# ── TASK 3: Dispatch Learning ────────────────────────────────

def task_dispatch_learn():
    """Analyze dispatch history and learn optimal routes."""
    print("[LEARN] Analyzing dispatch history...")
    results = []
    etoile = DATA / "etoile.db"
    if not etoile.exists():
        return "Dispatch Learning", ["  etoile.db not found"]
    try:
        conn = sqlite3.connect(str(etoile))
        c = conn.cursor()
        # Get dispatch stats
        c.execute("""SELECT node, COUNT(*) as cnt,
                     AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) as sr,
                     AVG(latency_ms) as lat
                     FROM agent_dispatch_log
                     GROUP BY node ORDER BY cnt DESC LIMIT 10""")
        for node, cnt, sr, lat in c.fetchall():
            results.append(f"  {node}: {cnt} calls | {sr * 100:.0f}% success | {lat:.0f}ms avg")

        # Find patterns with low success
        c.execute("""SELECT pattern, node, COUNT(*) as cnt,
                     AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) as sr
                     FROM agent_dispatch_log
                     GROUP BY pattern, node
                     HAVING sr < 0.5 AND cnt > 3
                     ORDER BY sr ASC LIMIT 10""")
        weak = c.fetchall()
        if weak:
            results.append("  --- Weak routes (< 50% success) ---")
            for pat, node, cnt, sr in weak:
                results.append(f"  {pat} -> {node}: {sr * 100:.0f}% ({cnt} calls)")
        conn.close()
    except Exception as e:
        results.append(f"  Error: {e}")

    return "Dispatch Learning", results


# ── TASK 4: Code Quality Review ──────────────────────────────

def task_code_review():
    """Ask M1 to review critical modules for issues."""
    print("[REVIEW] Code quality scan via M1...")
    results = []
    targets = ["src/config.py", "src/mcp_server.py", "src/tools.py"]
    for target in targets:
        fpath = TURBO / target
        if not fpath.exists():
            results.append(f"  {target}: not found")
            continue
        # Read first 100 lines
        try:
            code = fpath.read_text(encoding="utf-8", errors="replace")
            lines = code.splitlines()[:100]
            snippet = "\n".join(lines)
        except Exception:
            results.append(f"  {target}: read error")
            continue

        prompt = f"Review this Python code for bugs or security issues. List max 3 critical issues, one line each. Code:\n```python\n{snippet}\n```"
        resp, err = query_lmstudio("M1", prompt, timeout=30)
        if err:
            results.append(f"  {target}: M1 error ({err[:40]})")
        else:
            results.append(f"  {target}:")
            for line in (resp or "").strip().splitlines()[:3]:
                results.append(f"    {line[:120]}")

    return "Code Review (M1)", results


# ── TASK 5: Evolution Monitor ────────────────────────────────

def task_evolution_status():
    """Check strategy evolution progress."""
    print("[EVOL] Checking evolution status...")
    results = []
    evo_db = DATA / "strategy_evolution.db"
    if not evo_db.exists():
        return "Evolution Status", ["  No evolution DB found"]
    try:
        conn = sqlite3.connect(str(evo_db))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM strategies")
        strats = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM generations")
        gens = c.fetchone()[0]
        c.execute("SELECT name, fitness, avg_wr, avg_pnl, best_coin FROM strategies WHERE fitness > 0 ORDER BY fitness DESC LIMIT 5")
        top = c.fetchall()
        results.append(f"  {strats} strategies | {gens} generations")
        if top:
            results.append("  --- Top 5 ---")
            for name, fit, wr, pnl, coin in top:
                results.append(f"  {name}: fitness={fit:.3f} wr={wr:.0f}% pnl={pnl:.4f} ({coin})")
        # Check PID
        pid_file = DATA / "evolution_loop.pid"
        if pid_file.exists():
            pid = pid_file.read_text().strip()
            results.append(f"  PID: {pid} (running)")
        conn.close()
    except Exception as e:
        results.append(f"  Error: {e}")

    return "Evolution Status", results


# ── TASK 6: Cluster IA Work — Useful Prompts ─────────────────

def task_cluster_work():
    """Give the cluster actual useful work to do."""
    print("[WORK] Dispatching work to cluster...")
    results = []

    tasks_for_cluster = [
        ("M1", "List 5 Python best practices for SQLite in multi-threaded apps. One line each."),
        ("M2", "Write a Python function to calculate Sharpe ratio from a list of daily returns. Just code."),
        ("M3", "List 3 common security issues in Python web APIs. One line each."),
        ("OL1", "What are the top 3 indicators for crypto scalping? One line each."),
    ]

    def run_task(node_name, prompt):
        t0 = time.time()
        if node_name == "OL1":
            resp, err = query_ollama(prompt)
        else:
            resp, err = query_lmstudio(node_name, prompt)
        elapsed = time.time() - t0
        if err:
            return f"  {node_name}: FAIL ({err[:50]})"
        preview = (resp or "")[:200].replace("\n", " | ")
        return f"  {node_name} ({elapsed:.1f}s): {preview}"

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(run_task, n, p): n for n, p in tasks_for_cluster}
        for f in as_completed(futs):
            results.append(f.result())

    return "Cluster Work", sorted(results)


# ── MAIN ─────────────────────────────────────────────────────

ALL_TASKS = {
    "db": task_db_optimize,
    "bench": task_cluster_bench,
    "learn": task_dispatch_learn,
    "review": task_code_review,
    "evolution": task_evolution_status,
    "work": task_cluster_work,
}


def run_all(notify=False):
    """Run all tasks and generate report."""
    report_lines = [f"=== JARVIS Night Cluster Tasks — {time.strftime('%Y-%m-%d %H:%M')} ===\n"]
    total_start = time.time()

    for name, func in ALL_TASKS.items():
        t0 = time.time()
        try:
            title, results = func()
            elapsed = time.time() - t0
            report_lines.append(f"\n[{title}] ({elapsed:.1f}s)")
            report_lines.extend(results)
        except Exception as e:
            report_lines.append(f"\n[{name}] ERROR: {e}")

    total = time.time() - total_start
    report_lines.append(f"\n--- Total: {total:.0f}s ---")

    report = "\n".join(report_lines)
    print(report)

    if notify:
        send_telegram(f"[NIGHT OPS]\n{report}")
        print("\n[Telegram] Report sent")

    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS Night Cluster Tasks")
    parser.add_argument("--all", action="store_true", help="Run all tasks")
    parser.add_argument("--task", type=str, help="Run specific task: " + ", ".join(ALL_TASKS))
    parser.add_argument("--notify", action="store_true", help="Send report to Telegram")
    parser.add_argument("--loop", action="store_true", help="Run every hour")
    args = parser.parse_args()

    if args.task:
        if args.task not in ALL_TASKS:
            print(f"Unknown task: {args.task}. Available: {', '.join(ALL_TASKS)}")
            sys.exit(1)
        title, results = ALL_TASKS[args.task]()
        print(f"\n[{title}]")
        for r in results:
            print(r)
    elif args.loop:
        print("Night Cluster Tasks — Loop mode (every 60min)")
        while True:
            try:
                run_all(args.notify)
                print(f"\nNext run in 60min... (Ctrl+C to stop)")
                time.sleep(3600)
            except KeyboardInterrupt:
                print("\nStopped.")
                break
    else:
        run_all(args.notify)


if __name__ == "__main__":
    main()
