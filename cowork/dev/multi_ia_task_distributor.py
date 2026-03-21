#!/usr/bin/env python3
"""Multi-IA Task Distributor — dispatch tasks across ALL available IAs simultaneously.

CLI:
  --once --task "desc"     Distribute single task to best IA
  --parallel --task "desc" Send to ALL IAs, merge results (consensus)
  --batch FILE             Load tasks from JSON, distribute optimally
  --routing                Show current routing table
  --status                 Check all IAs status
"""

import argparse
import json
import sqlite3
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# IA Registry
# ---------------------------------------------------------------------------

IAS = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "health": "http://127.0.0.1:1234/api/v1/models",
        "model": "qwen3-8b",
        "weight": 1.9,
        "tags": ["code", "script", "debug", "math", "refactor", "architecture"],
        "build_payload": lambda prompt: json.dumps({
            "model": "qwen3-8b",
            "input": f"/nothink\n{prompt}",
            "temperature": 0.2, "max_output_tokens": 2048,
            "stream": False, "store": False,
        }).encode(),
        "extract": lambda d: next(
            (b["text"] for b in reversed(d.get("output", []))
             if b.get("type") == "message" and "text" in b), str(d)),
    },
    "OL1_local": {
        "url": "http://127.0.0.1:11434/api/chat",
        "health": "http://127.0.0.1:11434/api/tags",
        "model": "qwen3:1.7b",
        "weight": 1.4,
        "tags": ["quick", "question", "simple", "triage"],
        "build_payload": lambda prompt: json.dumps({
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": f"/no_think\n{prompt}"}],
            "stream": False,
        }).encode(),
        "extract": lambda d: d.get("message", {}).get("content", str(d)),
    },
    "OL1_cloud": {
        "url": "http://127.0.0.1:11434/api/chat",
        "health": "http://127.0.0.1:11434/api/tags",
        "model": "minimax-m2.5:cloud",
        "weight": 1.3,
        "tags": ["web", "search", "news", "actualite", "research"],
        "build_payload": lambda prompt: json.dumps({
            "model": "minimax-m2.5:cloud",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False, "think": False,
        }).encode(),
        "extract": lambda d: d.get("message", {}).get("content", str(d)),
    },
    "Perplexity": {
        "url": None,  # CDP — browser-based
        "health": None,
        "model": "perplexity-web",
        "weight": 1.5,
        "tags": ["research", "deep", "analysis", "web"],
        "build_payload": lambda prompt: None,
        "extract": lambda d: str(d),
    },
    "OpenClaw": {
        "url": "http://127.0.0.1:18789",
        "health": "http://127.0.0.1:18789",
        "model": "openclaw-gateway",
        "weight": 1.0,
        "tags": ["agent", "orchestrate", "multi-step"],
        "build_payload": lambda prompt: json.dumps({
            "action": "dispatch", "prompt": prompt,
        }).encode(),
        "extract": lambda d: d.get("result", str(d)),
    },
    "BrowserOS": {
        "url": "http://127.0.0.1:9000/mcp",
        "health": "http://127.0.0.1:9000/mcp",
        "model": "browseros-mcp",
        "weight": 1.0,
        "tags": ["browser", "action", "navigate", "click", "web_action"],
        "build_payload": lambda prompt: json.dumps({
            "method": "tools/call",
            "params": {"name": "evaluate_script", "arguments": {"script": prompt}},
        }).encode(),
        "extract": lambda d: d.get("result", str(d)),
    },
    "Telegram": {
        "url": None,  # Bot API — notify only
        "health": None,
        "model": "telegram-bot",
        "weight": 0.5,
        "tags": ["notify", "alert", "message", "telegram"],
        "build_payload": lambda prompt: None,
        "extract": lambda d: str(d),
    },
}

# ---------------------------------------------------------------------------
# Routing rules  (keyword → IA name)
# ---------------------------------------------------------------------------

ROUTING_RULES = [
    (["web search", "news", "actualite", "recherche web", "trending"],  "OL1_cloud"),
    (["code", "script", "debug", "fix", "refactor", "program", "function"], "M1"),
    (["research", "deep", "analyse approfondie", "in-depth"],           "Perplexity"),
    (["quick", "question", "simple", "rapide", "triage"],               "OL1_local"),
    (["browser", "navigate", "click", "page", "screenshot"],            "BrowserOS"),
    (["notify", "alert", "telegram", "message"],                        "Telegram"),
    (["consensus"],                                                     "__ALL__"),
]

DB_PATH = Path("F:/BUREAU/turbo/data/etoile.db")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _http(url: str, data: bytes | None = None, timeout: int = 60) -> dict:
    """Fire an HTTP request and return parsed JSON (or error dict)."""
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"__error": str(e)}


def _log_dispatch(ia: str, task: str, result: str, latency_ms: int) -> None:
    """Log dispatch to etoile.db memories table."""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(DB_PATH))
        con.execute(
            "CREATE TABLE IF NOT EXISTS memories "
            "(id INTEGER PRIMARY KEY, ts TEXT, category TEXT, key TEXT, value TEXT, extra TEXT)"
        )
        con.execute(
            "INSERT INTO memories (ts, category, key, value, extra) VALUES (?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), "multi_ia_dispatch", ia,
             task[:500], json.dumps({"latency_ms": latency_ms, "result_len": len(result)})),
        )
        con.commit()
        con.close()
    except Exception:
        pass  # non-blocking


def _route_task(task: str) -> str:
    """Return best IA name for a task description."""
    low = task.lower()
    for keywords, ia_name in ROUTING_RULES:
        if any(kw in low for kw in keywords):
            return ia_name
    return "M1"  # default


def _dispatch_one(ia_name: str, task: str) -> dict:
    """Send task to a single IA, return structured result."""
    ia = IAS[ia_name]
    if ia["url"] is None:
        return {"ia": ia_name, "status": "skip", "reason": "no HTTP endpoint", "text": ""}
    payload = ia["build_payload"](task)
    t0 = time.perf_counter()
    raw = _http(ia["url"], data=payload, timeout=120)
    ms = int((time.perf_counter() - t0) * 1000)
    if "__error" in raw:
        _log_dispatch(ia_name, task, raw["__error"], ms)
        return {"ia": ia_name, "status": "error", "error": raw["__error"], "latency_ms": ms, "text": ""}
    text = ia["extract"](raw)
    _log_dispatch(ia_name, task, text[:300], ms)
    return {"ia": ia_name, "status": "ok", "latency_ms": ms, "model": ia["model"], "text": text}


def _check_health(ia_name: str) -> dict:
    """Ping an IA and return status dict."""
    ia = IAS[ia_name]
    if ia.get("health") is None:
        return {"ia": ia_name, "status": "no_endpoint", "model": ia["model"]}
    t0 = time.perf_counter()
    raw = _http(ia["health"], timeout=5)
    ms = int((time.perf_counter() - t0) * 1000)
    ok = "__error" not in raw
    return {"ia": ia_name, "status": "online" if ok else "offline",
            "model": ia["model"], "latency_ms": ms,
            "error": raw.get("__error", "")}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_status() -> dict:
    """Check all IAs status in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=len(IAS)) as pool:
        futs = {pool.submit(_check_health, name): name for name in IAS}
        for fut in as_completed(futs):
            results.append(fut.result())
    return {"command": "status", "ias": sorted(results, key=lambda r: r["ia"])}


def cmd_routing() -> dict:
    """Show routing table."""
    table = []
    for keywords, ia_name in ROUTING_RULES:
        entry = {"keywords": keywords, "target": ia_name}
        if ia_name in IAS:
            entry["weight"] = IAS[ia_name]["weight"]
            entry["model"] = IAS[ia_name]["model"]
        elif ia_name == "__ALL__":
            entry["weight"] = "consensus"
            entry["model"] = "all"
        table.append(entry)
    return {"command": "routing", "rules": table, "default": "M1"}


def cmd_once(task: str) -> dict:
    """Dispatch to the single best IA."""
    target = _route_task(task)
    if target == "__ALL__":
        return cmd_parallel(task)
    result = _dispatch_one(target, task)
    return {"command": "once", "task": task, "routed_to": target, "result": result}


def cmd_parallel(task: str) -> dict:
    """Send to ALL IAs with HTTP endpoints, merge via weighted consensus."""
    results = []
    with ThreadPoolExecutor(max_workers=len(IAS)) as pool:
        futs = {pool.submit(_dispatch_one, name, task): name for name in IAS}
        for fut in as_completed(futs):
            results.append(fut.result())
    ok = [r for r in results if r["status"] == "ok" and r["text"]]
    total_w = sum(IAS[r["ia"]]["weight"] for r in ok) or 1
    consensus = []
    for r in sorted(ok, key=lambda x: -IAS[x["ia"]]["weight"]):
        w = IAS[r["ia"]]["weight"]
        consensus.append({"ia": r["ia"], "weight": w, "share": round(w / total_w, 3),
                          "latency_ms": r["latency_ms"], "text": r["text"]})
    return {"command": "parallel", "task": task,
            "responses": len(ok), "total": len(results), "consensus": consensus}


def cmd_batch(filepath: str) -> dict:
    """Load JSON task list and distribute each optimally."""
    with open(filepath, "r", encoding="utf-8") as f:
        tasks = json.load(f)
    if not isinstance(tasks, list):
        return {"command": "batch", "error": "JSON must be a list of task strings or objects"}
    out = []
    for item in tasks:
        desc = item if isinstance(item, str) else item.get("task", str(item))
        mode = "parallel" if (isinstance(item, dict) and item.get("parallel")) else "once"
        if mode == "parallel":
            out.append(cmd_parallel(desc))
        else:
            out.append(cmd_once(desc))
    return {"command": "batch", "total": len(tasks), "results": out}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Multi-IA Task Distributor")
    ap.add_argument("--once", action="store_true", help="Dispatch to best single IA")
    ap.add_argument("--parallel", action="store_true", help="Send to ALL IAs (consensus)")
    ap.add_argument("--task", type=str, help="Task description")
    ap.add_argument("--batch", type=str, metavar="FILE", help="JSON file with task list")
    ap.add_argument("--routing", action="store_true", help="Show routing table")
    ap.add_argument("--status", action="store_true", help="Check all IAs status")
    args = ap.parse_args()

    if args.status:
        result = cmd_status()
    elif args.routing:
        result = cmd_routing()
    elif args.batch:
        result = cmd_batch(args.batch)
    elif args.parallel and args.task:
        result = cmd_parallel(args.task)
    elif args.once and args.task:
        result = cmd_once(args.task)
    elif args.task:
        result = cmd_once(args.task)
    else:
        ap.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
