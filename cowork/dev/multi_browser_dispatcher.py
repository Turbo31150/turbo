#!/usr/bin/env python3
"""Multi-browser task dispatcher — splits tasks across Chrome CDP, BrowserOS MCP, Comet Playwright."""

import argparse
import json
import sqlite3
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError

# --- Browser endpoints ---
CHROME_CDP = "http://127.0.0.1:9222"
BROWSEROS_MCP = "http://127.0.0.1:9000/mcp"
COMET_PLAYWRIGHT = "playwright"  # via MCP bridge

# --- Color groups ---
COLOR_GROUPS = {
    "RED": {"role": "monitoring", "urls": ["http://127.0.0.1:8080", "http://127.0.0.1:5678", "http://127.0.0.1:18789"]},
    "ORANGE": {"role": "trading", "urls": ["https://www.mexc.com", "https://www.tradingview.com", "https://www.coingecko.com"]},
    "YELLOW": {"role": "AI", "urls": ["https://claude.ai", "https://aistudio.google.com", "https://gemini.google.com"]},
    "GREEN": {"role": "GitHub", "urls": ["https://github.com", "https://codeur.com"]},
    "BLUE": {"role": "docs/social", "urls": ["https://linkedin.com", "https://notion.so"]},
}

# --- Task templates ---
TASK_TEMPLATES = {
    "audit_profils": {
        "description": "Audit all profiles in parallel across 3 browsers",
        "tasks": [
            {"browser": "chrome", "url": "https://github.com/Turbo31150", "label": "GitHub profile"},
            {"browser": "browseros", "url": "https://www.linkedin.com/in/me", "label": "LinkedIn profile"},
            {"browser": "comet", "url": "https://www.codeur.com/-turbo31150", "label": "Codeur.com profile"},
        ],
    },
    "trading_scan": {
        "description": "Open trading dashboards via BrowserOS",
        "tasks": [
            {"browser": "browseros", "url": "https://www.mexc.com/exchange/BTC_USDT", "label": "MEXC BTC"},
            {"browser": "browseros", "url": "https://www.tradingview.com/chart", "label": "TradingView"},
            {"browser": "browseros", "url": "https://www.coingecko.com", "label": "CoinGecko"},
        ],
    },
    "ai_consensus": {
        "description": "Open AI platforms across browsers for consensus",
        "tasks": [
            {"browser": "chrome", "url": "https://claude.ai", "label": "Claude.ai"},
            {"browser": "browseros", "url": "https://aistudio.google.com", "label": "AI Studio"},
            {"browser": "comet", "url": "https://gemini.google.com", "label": "Gemini"},
        ],
    },
    "daily_monitor": {
        "description": "Open monitoring dashboards in RED tabs",
        "tasks": [
            {"browser": "chrome", "url": "http://127.0.0.1:8080", "label": "Dashboard"},
            {"browser": "browseros", "url": "http://127.0.0.1:5678", "label": "n8n"},
            {"browser": "comet", "url": "http://127.0.0.1:18789", "label": "OpenClaw"},
        ],
    },
}

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "etoile.db")


def _init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute(
        "CREATE TABLE IF NOT EXISTS browser_dispatch_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, browser TEXT, url TEXT, "
        "label TEXT, status TEXT, elapsed_ms INTEGER, error TEXT)"
    )
    db.commit()
    return db


def _log(db, browser, url, label, status, elapsed_ms, error=None):
    db.execute(
        "INSERT INTO browser_dispatch_log (ts,browser,url,label,status,elapsed_ms,error) VALUES (?,?,?,?,?,?,?)",
        (datetime.utcnow().isoformat(), browser, url, label, status, elapsed_ms, error),
    )
    db.commit()


def _http_post(url, payload, timeout=10):
    req = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def dispatch_to_chrome(url):
    """Open a tab via Chrome DevTools Protocol."""
    target = f"{CHROME_CDP}/json/new?{url}"
    req = Request(target)
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def dispatch_to_browseros(url):
    """Open a page via BrowserOS MCP new_page tool."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "new_page", "arguments": {"url": url}}}
    return _http_post(BROWSEROS_MCP, payload, timeout=15)


def dispatch_to_comet(url):
    """Dispatch to Comet browser via Playwright MCP (stub — returns intent)."""
    return {"browser": "comet", "url": url, "status": "dispatched", "note": "via Playwright MCP bridge"}


BROWSER_MAP = {
    "chrome": dispatch_to_chrome,
    "browseros": dispatch_to_browseros,
    "comet": dispatch_to_comet,
}


def _run_single(db, task):
    browser = task["browser"]
    url = task["url"]
    label = task.get("label", url)
    fn = BROWSER_MAP.get(browser)
    if not fn:
        return {"browser": browser, "url": url, "label": label, "status": "error", "error": f"unknown browser: {browser}"}
    t0 = time.perf_counter()
    try:
        result = fn(url)
        elapsed = int((time.perf_counter() - t0) * 1000)
        _log(db, browser, url, label, "ok", elapsed)
        return {"browser": browser, "url": url, "label": label, "status": "ok", "elapsed_ms": elapsed, "result": result}
    except (URLError, OSError, Exception) as exc:
        elapsed = int((time.perf_counter() - t0) * 1000)
        err = str(exc)[:200]
        _log(db, browser, url, label, "error", elapsed, err)
        return {"browser": browser, "url": url, "label": label, "status": "error", "elapsed_ms": elapsed, "error": err}


def dispatch_parallel(tasks_list):
    """Distribute tasks across browsers using ThreadPoolExecutor."""
    db = _init_db()
    results = []
    with ThreadPoolExecutor(max_workers=len(tasks_list) or 1) as pool:
        futures = {pool.submit(_run_single, db, t): t for t in tasks_list}
        for fut in as_completed(futures):
            results.append(fut.result())
    db.close()
    return results


def merge_results(results):
    """Combine all browser outputs into a summary."""
    ok = [r for r in results if r["status"] == "ok"]
    err = [r for r in results if r["status"] != "ok"]
    return {"total": len(results), "ok": len(ok), "errors": len(err), "results": results}


def split_task(description):
    """Heuristic: assign task fragments to browsers round-robin."""
    browsers = ["chrome", "browseros", "comet"]
    words = description.split(",") if "," in description else [description]
    tasks = []
    for i, part in enumerate(words):
        part = part.strip()
        url = part if part.startswith("http") else f"https://www.google.com/search?q={part.replace(' ', '+')}"
        tasks.append({"browser": browsers[i % len(browsers)], "url": url, "label": part})
    return tasks


def main():
    parser = argparse.ArgumentParser(description="Multi-browser task dispatcher")
    parser.add_argument("--once", action="store_true", help="Run once then exit")
    parser.add_argument("--task", type=str, help="Task description or template name")
    parser.add_argument("--audit", action="store_true", help="Audit all profiles in parallel")
    parser.add_argument("--monitor", action="store_true", help="Open monitoring dashboards")
    parser.add_argument("--list", action="store_true", help="List available task templates")
    args = parser.parse_args()

    if args.list:
        out = {k: v["description"] for k, v in TASK_TEMPLATES.items()}
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    if args.audit:
        tasks = TASK_TEMPLATES["audit_profils"]["tasks"]
    elif args.monitor:
        tasks = TASK_TEMPLATES["daily_monitor"]["tasks"]
    elif args.task:
        if args.task in TASK_TEMPLATES:
            tasks = TASK_TEMPLATES[args.task]["tasks"]
        else:
            tasks = split_task(args.task)
    else:
        parser.print_help()
        return

    results = dispatch_parallel(tasks)
    summary = merge_results(results)
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
