#!/usr/bin/env python3
"""multi_strategy_dispatcher.py — Multi-strategy dispatch engine.

Selects optimal dispatch strategy based on task type:
- SINGLE: fastest node, lowest latency (simple, web, system)
- RACE: parallel dispatch to 2+ nodes, first response wins (code, math)
- CONSENSUS: parallel dispatch, compare results, vote (trading, security, architecture)
- DEEP: sequential with reasoning chain (reasoning, analysis)

CLI:
    --dispatch TYPE PROMPT  : Auto-select strategy and dispatch
    --strategy STRAT TYPE PROMPT : Force strategy
    --strategies            : Show strategy matrix
    --test                  : Test all strategies

Stdlib-only (json, argparse, sqlite3, urllib, time, concurrent.futures).
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB

# Strategy matrix: task_type -> strategy
STRATEGY_MATRIX = {
    "simple":       "single",
    "web":          "single",
    "system":       "single",
    "creative":     "single",
    "code":         "race",
    "math":         "race",
    "data":         "single",
    "devops":       "single",
    "trading":      "consensus",
    "security":     "consensus",
    "architecture": "consensus",
    "reasoning":    "deep",
    "analysis":     "deep",
}

# Strategy configs
STRATEGY_CONFIG = {
    "single":    {"nodes": 1, "timeout": 30},
    "race":      {"nodes": 2, "timeout": 30},
    "consensus": {"nodes": 3, "timeout": 45},
    "deep":      {"nodes": 2, "timeout": 60},
}

NODES = {
    "M1":  {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b",
            "ollama": False, "prefix": "/nothink\n", "timeout": 30, "weight": 1.8},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
            "ollama": True, "timeout": 20, "weight": 1.3},
    "M2":  {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "ollama": False, "max_tokens": 2048, "timeout": 60, "weight": 1.0},
    "M3":  {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "ollama": False, "max_tokens": 2048, "timeout": 60, "weight": 0.8},
}

# Node priority by strategy
STRATEGY_NODES = {
    "single":    ["M1", "OL1"],
    "race":      ["M1", "OL1"],
    "consensus": ["M1", "OL1", "M2"],
    "deep":      ["M1", "M2"],
}


def get_db(path):
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def dispatch_node(node_name, prompt, timeout=30):
    """Send prompt to a single node."""
    node = NODES.get(node_name)
    if not node:
        return {"success": False, "node": node_name, "error": "Unknown node"}

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

        return {
            "success": True, "node": node_name, "text": text,
            "latency_ms": elapsed, "weight": node.get("weight", 1.0),
        }
    except Exception as e:
        return {
            "success": False, "node": node_name, "error": str(e)[:200],
            "latency_ms": int((time.time() - start) * 1000),
        }


def strategy_single(prompt, nodes, timeout):
    """Single node dispatch - fastest."""
    for node in nodes:
        result = dispatch_node(node, prompt, timeout)
        if result["success"]:
            result["strategy"] = "single"
            return result
    return {"success": False, "strategy": "single", "error": "All nodes failed"}


def strategy_race(prompt, nodes, timeout):
    """Parallel race - first response wins."""
    with ThreadPoolExecutor(max_workers=len(nodes)) as pool:
        futures = {pool.submit(dispatch_node, n, prompt, timeout): n for n in nodes}
        for future in as_completed(futures, timeout=timeout + 5):
            result = future.result()
            if result["success"]:
                result["strategy"] = "race"
                result["race_nodes"] = nodes
                # Cancel remaining futures
                for f in futures:
                    f.cancel()
                return result

    return {"success": False, "strategy": "race", "error": "All race nodes failed"}


def strategy_consensus(prompt, nodes, timeout):
    """Parallel consensus - compare and vote."""
    results = []
    with ThreadPoolExecutor(max_workers=len(nodes)) as pool:
        futures = {pool.submit(dispatch_node, n, prompt, timeout): n for n in nodes}
        for future in as_completed(futures, timeout=timeout + 5):
            try:
                result = future.result()
                if result["success"]:
                    results.append(result)
            except Exception:
                pass

    if not results:
        return {"success": False, "strategy": "consensus", "error": "No responses"}

    # Weight votes
    total_weight = sum(r["weight"] for r in results)
    best = max(results, key=lambda r: r["weight"])

    return {
        "success": True,
        "strategy": "consensus",
        "text": best["text"],
        "node": best["node"],
        "latency_ms": max(r["latency_ms"] for r in results),
        "votes": len(results),
        "total_weight": round(total_weight, 1),
        "respondents": [r["node"] for r in results],
    }


def strategy_deep(prompt, nodes, timeout):
    """Sequential deep analysis - first node analyzes, second verifies."""
    if not nodes:
        return {"success": False, "strategy": "deep", "error": "No nodes"}

    # Step 1: Primary analysis
    primary = dispatch_node(nodes[0], prompt, timeout)
    if not primary["success"]:
        # Fallback to single
        if len(nodes) > 1:
            primary = dispatch_node(nodes[1], prompt, timeout)
        if not primary["success"]:
            return {"success": False, "strategy": "deep", "error": "Analysis failed"}

    if len(nodes) < 2:
        primary["strategy"] = "deep"
        return primary

    # Step 2: Verification (shorter prompt)
    verify_prompt = f"/nothink\nVerifie cette reponse et corrige si besoin (reponds le resultat final uniquement):\n{primary['text'][:500]}"
    verify = dispatch_node(nodes[1], verify_prompt, timeout)

    if verify["success"]:
        return {
            "success": True, "strategy": "deep",
            "text": verify["text"],
            "node": f"{nodes[0]}+{nodes[1]}",
            "latency_ms": primary["latency_ms"] + verify["latency_ms"],
            "primary": primary["text"][:200],
            "verified": True,
        }
    else:
        primary["strategy"] = "deep"
        primary["verified"] = False
        return primary


def dispatch(task_type, prompt, force_strategy=None):
    """Main dispatch entry point."""
    strategy = force_strategy or STRATEGY_MATRIX.get(task_type, "single")
    config = STRATEGY_CONFIG.get(strategy, STRATEGY_CONFIG["single"])
    nodes = STRATEGY_NODES.get(strategy, ["M1", "OL1"])[:config["nodes"]]

    # Dynamic timeout based on prompt complexity
    try:
        from dynamic_timeout import compute_timeout
        to_result = compute_timeout(task_type, prompt, nodes[0] if nodes else "M1")
        timeout = to_result["timeout_s"]
    except ImportError:
        timeout = config["timeout"]

    if strategy == "single":
        return strategy_single(prompt, nodes, timeout)
    elif strategy == "race":
        return strategy_race(prompt, nodes, timeout)
    elif strategy == "consensus":
        return strategy_consensus(prompt, nodes, timeout)
    elif strategy == "deep":
        return strategy_deep(prompt, nodes, timeout)
    else:
        return strategy_single(prompt, nodes, timeout)


def log_dispatch(result, task_type):
    """Log dispatch result."""
    try:
        edb = get_db(ETOILE_DB)
        edb.execute("""
            INSERT INTO agent_dispatch_log
            (timestamp, request_text, classified_type, agent_id, model_used, node,
             strategy, latency_ms, success, quality_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            f"[{result.get('strategy', '?')}] {task_type}",
            task_type,
            f"multi_strategy_{result.get('strategy', 'unknown')}",
            "", result.get("node", ""),
            result.get("strategy", "single"),
            result.get("latency_ms", 0),
            1 if result.get("success") else 0,
            1.0 if result.get("success") else 0.0,
        ))
        edb.commit()
        edb.close()
    except Exception:
        pass


def show_strategies():
    """Show the strategy matrix."""
    print("=== Strategy Matrix ===")
    for task_type, strategy in sorted(STRATEGY_MATRIX.items()):
        config = STRATEGY_CONFIG[strategy]
        nodes = STRATEGY_NODES.get(strategy, [])[:config["nodes"]]
        print(f"  {task_type:15} -> {strategy:10} nodes={','.join(nodes)} timeout={config['timeout']}s")


def run_test():
    """Test all strategies."""
    print("=== Multi-Strategy Test ===\n")
    tests = [
        {"type": "simple", "prompt": "/nothink\nDis OK.", "expected_strategy": "single"},
        {"type": "code", "prompt": "/nothink\ndef add(a,b): return a+b", "expected_strategy": "race"},
        {"type": "math", "prompt": "/nothink\n7*8=?", "expected_strategy": "race"},
    ]

    ok = 0
    for t in tests:
        result = dispatch(t["type"], t["prompt"])
        log_dispatch(result, t["type"])
        passed = result["success"] and result.get("strategy") == t["expected_strategy"]
        if passed:
            ok += 1
        status = "PASS" if passed else "FAIL"
        print(f"  {status} {t['type']:10} strategy={result.get('strategy', '?'):10} "
              f"node={result.get('node', '?'):8} {result.get('latency_ms', 0)}ms")

    print(f"\n  {ok}/{len(tests)} passed")


def main():
    parser = argparse.ArgumentParser(description="Multi-Strategy Dispatcher")
    parser.add_argument("--dispatch", nargs=2, metavar=("TYPE", "PROMPT"))
    parser.add_argument("--strategy", nargs=3, metavar=("STRAT", "TYPE", "PROMPT"))
    parser.add_argument("--strategies", action="store_true", help="Show matrix")
    parser.add_argument("--test", action="store_true", help="Test all")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not any([args.dispatch, args.strategy, args.strategies, args.test]):
        parser.print_help()
        sys.exit(1)

    if args.strategies:
        show_strategies()
        return

    if args.test:
        run_test()
        return

    if args.dispatch:
        task_type, prompt = args.dispatch
        result = dispatch(task_type, prompt)
        log_dispatch(result, task_type)
    elif args.strategy:
        strat, task_type, prompt = args.strategy
        result = dispatch(task_type, prompt, force_strategy=strat)
        log_dispatch(result, task_type)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        if result["success"]:
            print(f"[{result.get('strategy', '?')}/{result.get('node', '?')}] "
                  f"{result.get('text', '')[:500]}")
        else:
            print(f"FAIL [{result.get('strategy', '?')}]: {result.get('error', '')}")


if __name__ == "__main__":
    main()
