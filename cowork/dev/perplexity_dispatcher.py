#!/usr/bin/env python3
"""perplexity_dispatcher.py

Distribute research tasks to Perplexity AI via Comet browser CDP.
Features:
- --once: send a single research query, collect answer
- --research TOPIC: deep research on a topic
- --batch FILE: batch multiple queries from a JSON file
- --monitor: poll Perplexity for new results
- Interacts via Chrome CDP (Runtime.evaluate) on pages already open
- Stores results in etoile.db memories (category='perplexity_research')
- Uses only Python stdlib (argparse, json, sqlite3, urllib, time, logging)
"""

import argparse
import json
import logging
import sqlite3
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

CDP_ENDPOINT = "http://127.0.0.1:9222"
ETOILE_DB = Path(__file__).resolve().parent.parent.parent / "etoile.db"
POLL_INTERVAL = 2.0
MAX_WAIT = 120

log = logging.getLogger("perplexity_dispatcher")
log.setLevel(logging.INFO)
_h = logging.StreamHandler()
_h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
log.addHandler(_h)


# ── CDP helpers ──────────────────────────────────────────────────────────

def _http_json(url: str, data: Optional[bytes] = None, timeout: int = 10) -> Any:
    """HTTP GET/POST returning parsed JSON."""
    req = urllib.request.Request(url)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def find_perplexity_pages() -> List[Dict[str, str]]:
    """Return CDP targets whose URL contains perplexity.ai."""
    targets = _http_json(f"{CDP_ENDPOINT}/json")
    return [t for t in targets if "perplexity.ai" in t.get("url", "")]


def cdp_evaluate(ws_url: str, expression: str, timeout: int = 10) -> Any:
    """Evaluate JS via CDP HTTP endpoint (uses /json/evaluate fallback via POST)."""
    # Use the target's id to send commands through the HTTP debug endpoint
    # Extract target id from wsDebuggerUrl
    target_id = ws_url.rsplit("/", 1)[-1]
    url = f"{CDP_ENDPOINT}/json/protocol"  # just verify connectivity
    # Use the REST-style evaluate: POST to the page endpoint
    payload = json.dumps({
        "id": 1, "method": "Runtime.evaluate",
        "params": {"expression": expression, "returnByValue": True}
    }).encode()
    # CDP requires websocket normally; we use a lightweight HTTP bridge
    # Fallback: use urllib to talk to the debug endpoint
    eval_url = f"http://127.0.0.1:9222/json/evaluate?targetId={target_id}"
    try:
        return _http_json(eval_url, payload, timeout)
    except urllib.error.HTTPError:
        # Some CDP versions need direct /devtools approach; use simple fetch
        return _execute_via_new_tab(expression, timeout)


def _execute_via_new_tab(expression: str, timeout: int = 10) -> Any:
    """Fallback: open about:blank, evaluate, close."""
    new = _http_json(f"{CDP_ENDPOINT}/json/new?about:blank")
    target_id = new["id"]
    payload = json.dumps({
        "id": 1, "method": "Runtime.evaluate",
        "params": {"expression": expression, "returnByValue": True}
    }).encode()
    try:
        result = _http_json(
            f"{CDP_ENDPOINT}/json/evaluate?targetId={target_id}", payload, timeout
        )
        return result
    finally:
        try:
            _http_json(f"{CDP_ENDPOINT}/json/close/{target_id}")
        except Exception:
            pass


# ── Perplexity interaction ───────────────────────────────────────────────

def send_query(query: str) -> Dict[str, Any]:
    """Send a query to Perplexity and wait for the response."""
    pages = find_perplexity_pages()
    if not pages:
        return {"ok": False, "error": "No Perplexity tab found in Comet browser"}

    target = pages[0]
    ws_url = target.get("webSocketDebuggerUrl", "")
    log.info("Using Perplexity tab: %s", target.get("url"))

    # Fill the textarea
    fill_js = (
        "(() => {"
        "  const ta = document.querySelector('textarea[placeholder]');"
        "  if (!ta) return JSON.stringify({ok:false,error:'textarea not found'});"
        f"  ta.value = {json.dumps(query)};"
        "  ta.dispatchEvent(new Event('input', {bubbles:true}));"
        "  return JSON.stringify({ok:true});"
        "})()"
    )
    fill_result = cdp_evaluate(ws_url, fill_js)
    log.info("Fill result: %s", fill_result)

    # Click submit button
    submit_js = (
        "(() => {"
        "  const btn = document.querySelector('button[aria-label=\"Submit\"]')"
        "    || document.querySelector('button[type=\"submit\"]')"
        "    || document.querySelector('button svg')?.closest('button');"
        "  if (!btn) return JSON.stringify({ok:false,error:'submit button not found'});"
        "  btn.click();"
        "  return JSON.stringify({ok:true});"
        "})()"
    )
    cdp_evaluate(ws_url, submit_js)
    log.info("Query submitted, waiting for response...")

    # Poll for response
    start = time.time()
    answer = None
    while time.time() - start < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        extract_js = (
            "(() => {"
            "  const el = document.querySelector('.prose')"
            "    || document.querySelector('[class*=\"markdown\"]')"
            "    || document.querySelector('.response-content');"
            "  if (!el || el.textContent.trim().length < 20) return '';"
            "  return el.textContent.trim();"
            "})()"
        )
        result = cdp_evaluate(ws_url, extract_js)
        text = ""
        if isinstance(result, dict) and "result" in result:
            text = result.get("result", {}).get("value", "")
        elif isinstance(result, str):
            text = result
        if text and len(text) > 20:
            answer = text
            break

    if not answer:
        return {"ok": False, "error": "Timeout waiting for Perplexity response"}

    return {"ok": True, "query": query, "answer": answer, "ts": datetime.now().isoformat()}


# ── Database ─────────────────────────────────────────────────────────────

def store_result(result: Dict[str, Any]) -> None:
    """Store a Perplexity result in etoile.db memories."""
    if not result.get("ok"):
        return
    conn = sqlite3.connect(str(ETOILE_DB))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO memories (category, key, value, source, confidence) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "perplexity_research",
                result["query"][:200],
                json.dumps(result, ensure_ascii=False),
                "perplexity_dispatcher",
                0.9,
            ),
        )
        conn.commit()
        log.info("Stored result for: %s", result["query"][:60])
    finally:
        conn.close()


# ── Commands ─────────────────────────────────────────────────────────────

def cmd_once(query: str) -> Dict[str, Any]:
    """Single query to Perplexity."""
    result = send_query(query)
    store_result(result)
    return result


def cmd_research(topic: str) -> Dict[str, Any]:
    """Deep research: prefix with instruction for thorough answer."""
    prompt = (
        f"Give me a comprehensive, in-depth research summary on: {topic}. "
        "Include key facts, recent developments, statistics, and sources."
    )
    result = send_query(prompt)
    if result.get("ok"):
        result["topic"] = topic
        result["mode"] = "deep_research"
    store_result(result)
    return result


def cmd_batch(filepath: str) -> List[Dict[str, Any]]:
    """Batch queries from a JSON file (list of strings or {query:...} objects)."""
    with open(filepath, "r", encoding="utf-8") as f:
        items = json.load(f)
    results = []
    for item in items:
        q = item if isinstance(item, str) else item.get("query", "")
        if not q:
            continue
        log.info("Batch query %d/%d: %s", len(results) + 1, len(items), q[:60])
        r = cmd_once(q)
        results.append(r)
        time.sleep(1)  # avoid hammering
    return results


def cmd_monitor() -> Dict[str, Any]:
    """Monitor: check Perplexity tabs for any visible results and extract them."""
    pages = find_perplexity_pages()
    collected = []
    for page in pages:
        ws_url = page.get("webSocketDebuggerUrl", "")
        extract_js = (
            "(() => {"
            "  const el = document.querySelector('.prose')"
            "    || document.querySelector('[class*=\"markdown\"]');"
            "  const q = document.querySelector('textarea[placeholder]');"
            "  return JSON.stringify({"
            "    answer: el ? el.textContent.trim() : '',"
            "    query: q ? q.value : '',"
            "    url: location.href"
            "  });"
            "})()"
        )
        raw = cdp_evaluate(ws_url, extract_js)
        text = raw if isinstance(raw, str) else str(raw)
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            data = {"answer": "", "query": "", "url": page.get("url", "")}
        if data.get("answer"):
            result = {"ok": True, "query": data["query"], "answer": data["answer"],
                       "url": data["url"], "ts": datetime.now().isoformat()}
            store_result(result)
            collected.append(result)
    return {"ok": True, "collected": len(collected), "results": collected}


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Perplexity AI dispatcher via Comet CDP")
    parser.add_argument("--once", metavar="QUERY", help="Send a single research query")
    parser.add_argument("--research", metavar="TOPIC", help="Deep research on a topic")
    parser.add_argument("--batch", metavar="FILE", help="Batch queries from JSON file")
    parser.add_argument("--monitor", action="store_true", help="Monitor for new results")
    args = parser.parse_args()

    if args.once:
        result = cmd_once(args.once)
    elif args.research:
        result = cmd_research(args.research)
    elif args.batch:
        result = cmd_batch(args.batch)
    elif args.monitor:
        result = cmd_monitor()
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
