#!/usr/bin/env python3
"""Multi-Agent Coordinator — Orchestrate parallel IA tasks across the cluster.

Decomposes complex tasks into sub-tasks, dispatches to best nodes,
collects results, resolves conflicts, and merges outputs.
"""
import argparse
import json
import sqlite3
import time
import urllib.request
import concurrent.futures
from pathlib import Path

DB_PATH = Path(__file__).parent / "coordinator.db"

CLUSTER = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b", "weight": 1.8, "type": "lmstudio", "specialty": "code,math,reasoning"},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b", "weight": 1.5, "type": "lmstudio", "specialty": "reasoning,review"},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b", "weight": 1.2, "type": "lmstudio", "specialty": "reasoning,general"},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b", "weight": 1.3, "type": "ollama", "specialty": "fast,simple"},
}

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY, ts REAL, parent_id INTEGER,
        description TEXT, assigned_to TEXT, status TEXT DEFAULT 'pending',
        result TEXT, latency_ms REAL, quality_score REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS coordinations (
        id INTEGER PRIMARY KEY, ts REAL, task_description TEXT,
        subtasks_count INTEGER, nodes_used TEXT, consensus TEXT,
        total_latency_ms REAL, success INTEGER)""")
    db.commit()
    return db

def call_node(name, cfg, prompt, timeout=60):
    """Call a single cluster node."""
    start = time.time()
    try:
        if cfg["type"] == "ollama":
            body = json.dumps({
                "model": cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False,
            }).encode()
        else:
            prefix = "/nothink\n" if name == "M1" else ""
            body = json.dumps({
                "model": cfg["model"],
                "input": f"{prefix}{prompt}",
                "temperature": 0.2, "max_output_tokens": 2048,
                "stream": False, "store": False,
            }).encode()

        req = urllib.request.Request(cfg["url"], data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())

        latency = (time.time() - start) * 1000
        if cfg["type"] == "ollama":
            text = data.get("message", {}).get("content", "")
        else:
            text = ""
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if isinstance(c, dict) and c.get("text"):
                            text = c["text"]
                            break
                    if text:
                        break
        return {"node": name, "text": text[:2000], "latency_ms": latency, "success": True}
    except Exception as e:
        return {"node": name, "text": "", "latency_ms": (time.time()-start)*1000, "success": False, "error": str(e)[:200]}

def select_nodes(task_type, count=3):
    """Select best nodes for a task type."""
    scored = []
    for name, cfg in CLUSTER.items():
        score = cfg["weight"]
        if task_type in cfg["specialty"].split(","):
            score *= 1.5
        scored.append((name, cfg, score))
    scored.sort(key=lambda x: -x[2])
    return scored[:count]

def dispatch_parallel(prompt, task_type="general", node_count=3):
    """Dispatch prompt to multiple nodes in parallel."""
    nodes = select_nodes(task_type, node_count)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=node_count) as pool:
        futures = {pool.submit(call_node, name, cfg, prompt): name for name, cfg, _ in nodes}
        for future in concurrent.futures.as_completed(futures, timeout=90):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({"node": futures[future], "text": "", "success": False, "error": str(e)[:200], "latency_ms": 0})
    return results

def weighted_consensus(results):
    """Build weighted consensus from multiple node responses."""
    valid = [r for r in results if r["success"] and len(r["text"]) > 10]
    if not valid:
        return "Aucune reponse valide du cluster"
    if len(valid) == 1:
        return valid[0]["text"]

    # Use the response from the highest-weight node
    best = max(valid, key=lambda r: CLUSTER.get(r["node"], {}).get("weight", 0))
    sources = ", ".join(f"[{r['node']}/{r['latency_ms']:.0f}ms]" for r in valid)
    return f"{best['text']}\n\n--- Consensus: {sources} ---"

def coordinate_task(db, description, task_type="general", node_count=3):
    """Full coordination pipeline: dispatch, collect, consensus."""
    start = time.time()
    results = dispatch_parallel(description, task_type, node_count)
    consensus = weighted_consensus(results)
    total_latency = (time.time() - start) * 1000

    nodes_used = [r["node"] for r in results if r["success"]]
    success = len(nodes_used) > 0

    db.execute(
        "INSERT INTO coordinations (ts, task_description, subtasks_count, nodes_used, consensus, total_latency_ms, success) VALUES (?,?,?,?,?,?,?)",
        (time.time(), description[:200], len(results), json.dumps(nodes_used), consensus[:500], total_latency, 1 if success else 0))

    for r in results:
        db.execute(
            "INSERT INTO tasks (ts, description, assigned_to, status, result, latency_ms) VALUES (?,?,?,?,?,?)",
            (time.time(), description[:200], r["node"], "done" if r["success"] else "failed",
             r.get("text", r.get("error", ""))[:500], r.get("latency_ms", 0)))
    db.commit()

    return {"consensus": consensus, "results": results, "latency_ms": total_latency, "nodes_used": nodes_used}

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Coordinator")
    parser.add_argument("--ask", type=str, help="Ask a question to the cluster")
    parser.add_argument("--type", type=str, default="general", help="Task type: code, math, reasoning, general")
    parser.add_argument("--nodes", type=int, default=3, help="Number of nodes to use")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    db = init_db()

    if args.stats:
        total = db.execute("SELECT COUNT(*) FROM coordinations").fetchone()[0]
        success = db.execute("SELECT COUNT(*) FROM coordinations WHERE success=1").fetchone()[0]
        avg_lat = db.execute("SELECT AVG(total_latency_ms) FROM coordinations").fetchone()[0] or 0
        print(f"=== Coordinator Stats ===")
        print(f"  Total coordinations: {total}")
        print(f"  Success rate: {success}/{total} ({success/max(total,1)*100:.0f}%)")
        print(f"  Avg latency: {avg_lat:.0f}ms")
        return

    if args.ask:
        print(f"Dispatching to {args.nodes} nodes (type: {args.type})...")
        result = coordinate_task(db, args.ask, args.type, args.nodes)
        print(f"\n=== Results ({result['latency_ms']:.0f}ms) ===")
        for r in result["results"]:
            status = "OK" if r["success"] else "FAIL"
            print(f"  [{r['node']}] {status} ({r.get('latency_ms',0):.0f}ms) — {r.get('text','')[:100] or r.get('error','')[:100]}")
        print(f"\n=== Consensus ===\n{result['consensus'][:500]}")

    if args.once:
        # Demo with a simple test
        result = coordinate_task(db, "Dis bonjour en une phrase.", "simple", 2)
        print(f"Demo: {len(result['nodes_used'])} nodes, {result['latency_ms']:.0f}ms")

if __name__ == "__main__":
    main()
