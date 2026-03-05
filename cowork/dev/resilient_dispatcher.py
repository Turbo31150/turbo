#!/usr/bin/env python3
"""resilient_dispatcher.py — Resilient dispatch with retry, circuit breaker, and fallback.

Provides a robust dispatch function that:
- Tries primary node first
- On failure: exponential backoff retry (up to 2 retries)
- Circuit breaker with HALF_OPEN state (probe after cooldown)
- Automatic fallback chain traversal
- Logs all attempts to agent_dispatch_log

CLI:
    --dispatch TYPE PROMPT  : Dispatch a prompt with resilience
    --status                : Show circuit breaker states
    --reset NODE            : Reset circuit breaker for a node
    --test                  : Run resilience test suite

Stdlib-only (json, argparse, sqlite3, urllib, time).
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")

# Circuit breaker config
CB_FAIL_THRESHOLD = 3
CB_COOLDOWN_S = 300       # 5 min before HALF_OPEN probe
CB_HALF_OPEN_MAX = 1      # Max concurrent probes in HALF_OPEN
CB_SUCCESS_TO_CLOSE = 2   # Successes needed to close circuit

# Retry config
MAX_RETRIES = 2
BASE_BACKOFF_S = 1.0      # Initial backoff
BACKOFF_MULTIPLIER = 2.0  # Exponential factor

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


def get_db(path):
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_cb_table(db):
    """Create circuit breaker state table."""
    db.execute("""CREATE TABLE IF NOT EXISTS circuit_breaker_state (
        node TEXT PRIMARY KEY,
        state TEXT DEFAULT 'CLOSED',
        fail_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        last_fail TEXT,
        last_success TEXT,
        last_transition TEXT,
        updated_at TEXT
    )""")
    db.commit()


def get_cb_state(db, node):
    """Get circuit breaker state for a node."""
    init_cb_table(db)
    row = db.execute(
        "SELECT * FROM circuit_breaker_state WHERE node=?", (node,)
    ).fetchone()
    if not row:
        return {"state": "CLOSED", "fail_count": 0, "success_count": 0}

    state = dict(row)

    # Check if OPEN should transition to HALF_OPEN
    if state["state"] == "OPEN" and state.get("last_fail"):
        try:
            last_fail = datetime.fromisoformat(state["last_fail"])
            elapsed = (datetime.now() - last_fail).total_seconds()
            if elapsed >= CB_COOLDOWN_S:
                state["state"] = "HALF_OPEN"
                db.execute("""
                    UPDATE circuit_breaker_state
                    SET state='HALF_OPEN', last_transition=?, updated_at=?
                    WHERE node=?
                """, (datetime.now().isoformat(), datetime.now().isoformat(), node))
                db.commit()
        except Exception:
            pass

    return state


def record_cb_success(db, node):
    """Record a successful dispatch for circuit breaker."""
    init_cb_table(db)
    now = datetime.now().isoformat()

    state = get_cb_state(db, node)
    new_success = state.get("success_count", 0) + 1

    # HALF_OPEN: close after enough successes
    new_state = state["state"]
    if state["state"] == "HALF_OPEN" and new_success >= CB_SUCCESS_TO_CLOSE:
        new_state = "CLOSED"
        new_success = 0
    elif state["state"] == "CLOSED":
        new_state = "CLOSED"

    db.execute("""
        INSERT INTO circuit_breaker_state (node, state, fail_count, success_count, last_success, last_transition, updated_at)
        VALUES (?, ?, 0, ?, ?, ?, ?)
        ON CONFLICT(node) DO UPDATE SET
            state=?, fail_count=0, success_count=?, last_success=?, last_transition=?, updated_at=?
    """, (node, new_state, new_success, now, now, now,
          new_state, new_success, now, now, now))
    db.commit()


def record_cb_failure(db, node):
    """Record a failed dispatch for circuit breaker."""
    init_cb_table(db)
    now = datetime.now().isoformat()

    state = get_cb_state(db, node)
    new_fails = state.get("fail_count", 0) + 1

    # Open circuit if threshold reached
    new_state = state["state"]
    if new_fails >= CB_FAIL_THRESHOLD:
        new_state = "OPEN"
    elif state["state"] == "HALF_OPEN":
        new_state = "OPEN"  # HALF_OPEN probe failed -> back to OPEN

    db.execute("""
        INSERT INTO circuit_breaker_state (node, state, fail_count, success_count, last_fail, last_transition, updated_at)
        VALUES (?, ?, ?, 0, ?, ?, ?)
        ON CONFLICT(node) DO UPDATE SET
            state=?, fail_count=?, success_count=0, last_fail=?, last_transition=?, updated_at=?
    """, (node, new_state, new_fails, now, now, now,
          new_state, new_fails, now, now, now))
    db.commit()


def dispatch_to_node(node_name, prompt, timeout=None):
    """Send prompt to a node."""
    node = NODES.get(node_name)
    if not node:
        return {"success": False, "error": f"Unknown node {node_name}"}

    t = timeout or node.get("timeout", 30)
    start = time.time()

    try:
        prefix = node.get("prefix", "")
        max_tokens = node.get("max_tokens", 1024)

        if node.get("ollama"):
            body = json.dumps({
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False,
            }).encode()
        else:
            body = json.dumps({
                "model": node["model"],
                "input": f"{prefix}{prompt}",
                "temperature": 0.2, "max_output_tokens": max_tokens,
                "stream": False, "store": False,
            }).encode()

        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(node["url"], data=body, headers=headers)
        resp = urllib.request.urlopen(req, timeout=t)
        data = json.loads(resp.read())
        elapsed_ms = int((time.time() - start) * 1000)

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

        return {"success": True, "text": text, "latency_ms": elapsed_ms, "node": node_name}
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return {"success": False, "error": str(e)[:200], "latency_ms": elapsed_ms, "node": node_name}


def log_dispatch(edb, node, task_type, prompt, result, attempt=1):
    """Log dispatch attempt."""
    try:
        edb.execute("""
            INSERT INTO agent_dispatch_log
            (timestamp, request_text, classified_type, agent_id, model_used, node,
             strategy, latency_ms, tokens_in, tokens_out, success, error_msg, quality_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            prompt[:200],
            task_type,
            f"resilient_attempt{attempt}",
            NODES.get(node, {}).get("model", ""),
            node,
            f"resilient_retry{attempt}",
            result.get("latency_ms", 0),
            len(prompt.split()),
            len(result.get("text", "").split()) if result.get("text") else 0,
            1 if result.get("success") else 0,
            result.get("error", "")[:500] if not result.get("success") else None,
            1.0 if result.get("success") else 0.0,
        ))
        edb.commit()
    except Exception:
        pass


def resilient_dispatch(task_type, prompt, route_chain=None):
    """Dispatch with full resilience: retry + circuit breaker + fallback chain."""
    gaps_db = get_db(GAPS_DB)
    edb = get_db(ETOILE_DB)

    # Get route chain from smart routing if not provided
    if not route_chain:
        try:
            sys.path.insert(0, str(SCRIPT_DIR))
            from smart_routing_engine import get_optimal_route
            route_chain = get_optimal_route(task_type, gaps_db, edb)
        except Exception:
            route_chain = ["M1", "OL1", "M2", "M3"]

    all_attempts = []

    for node in route_chain:
        # Check circuit breaker
        cb = get_cb_state(gaps_db, node)
        if cb["state"] == "OPEN":
            all_attempts.append({"node": node, "skipped": True, "reason": "circuit_open"})
            continue

        # Retry loop with exponential backoff
        for attempt in range(1, MAX_RETRIES + 2):
            result = dispatch_to_node(node, prompt)
            log_dispatch(edb, node, task_type, prompt, result, attempt)

            if result["success"]:
                record_cb_success(gaps_db, node)
                result["attempts"] = all_attempts
                result["total_attempts"] = len(all_attempts) + 1
                gaps_db.close()
                edb.close()
                return result

            all_attempts.append({
                "node": node, "attempt": attempt,
                "error": result.get("error", "")[:100],
                "latency_ms": result.get("latency_ms", 0),
            })

            # Don't retry on last attempt for this node
            if attempt <= MAX_RETRIES:
                backoff = BASE_BACKOFF_S * (BACKOFF_MULTIPLIER ** (attempt - 1))
                time.sleep(backoff)

        # All retries failed for this node
        record_cb_failure(gaps_db, node)

    # All nodes failed
    gaps_db.close()
    edb.close()
    return {
        "success": False,
        "error": "All nodes exhausted",
        "attempts": all_attempts,
        "total_attempts": len(all_attempts),
    }


def show_status():
    """Show circuit breaker status for all nodes."""
    db = get_db(GAPS_DB)
    init_cb_table(db)

    print("=== Circuit Breaker Status ===")
    for node in ["M1", "OL1", "M2", "M3"]:
        state = get_cb_state(db, node)
        s = state.get("state", "CLOSED")
        f = state.get("fail_count", 0)
        ok = state.get("success_count", 0)
        indicator = "+" if s == "CLOSED" else "~" if s == "HALF_OPEN" else "!"
        print(f"  {indicator} {node:4} {s:10} fails={f} ok={ok}")

    db.close()


def reset_cb(node):
    """Reset circuit breaker for a node."""
    db = get_db(GAPS_DB)
    init_cb_table(db)
    now = datetime.now().isoformat()
    db.execute("""
        INSERT INTO circuit_breaker_state (node, state, fail_count, success_count, last_transition, updated_at)
        VALUES (?, 'CLOSED', 0, 0, ?, ?)
        ON CONFLICT(node) DO UPDATE SET state='CLOSED', fail_count=0, success_count=0, last_transition=?, updated_at=?
    """, (node, now, now, now, now))
    db.commit()
    print(f"Circuit breaker reset for {node}")
    db.close()


def run_test():
    """Test resilience features."""
    print("=== Resilience Test ===\n")

    tests = [
        {"type": "simple", "prompt": "/nothink\nReponds OK.", "expect": "ok"},
        {"type": "math", "prompt": "/nothink\n2+2=? Nombre.", "expect": "4"},
        {"type": "code", "prompt": "/nothink\ndef add(a,b): Code uniquement.", "expect": "def"},
    ]

    ok = 0
    for t in tests:
        result = resilient_dispatch(t["type"], t["prompt"])
        passed = result["success"] and t["expect"] in result.get("text", "").lower()
        status = "PASS" if passed else "FAIL"
        if passed:
            ok += 1
        attempts = result.get("total_attempts", 1)
        node = result.get("node", "?")
        lat = result.get("latency_ms", 0)
        print(f"  {status} {t['type']:8} node={node} {lat}ms attempts={attempts}")

    print(f"\n  Result: {ok}/{len(tests)} passed")

    # Show CB states after test
    print()
    show_status()


def main():
    parser = argparse.ArgumentParser(description="Resilient Dispatcher")
    parser.add_argument("--dispatch", nargs=2, metavar=("TYPE", "PROMPT"), help="Dispatch")
    parser.add_argument("--status", action="store_true", help="CB status")
    parser.add_argument("--reset", type=str, help="Reset CB for node")
    parser.add_argument("--test", action="store_true", help="Test suite")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not any([args.dispatch, args.status, args.reset, args.test]):
        parser.print_help()
        sys.exit(1)

    if args.status:
        show_status()
        return

    if args.reset:
        reset_cb(args.reset)
        return

    if args.test:
        run_test()
        return

    if args.dispatch:
        task_type, prompt = args.dispatch
        result = resilient_dispatch(task_type, prompt)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            if result["success"]:
                print(f"[{result['node']}] {result['text'][:500]}")
            else:
                print(f"FAILED: {result.get('error', 'unknown')}")
                for a in result.get("attempts", []):
                    print(f"  {a}")


if __name__ == "__main__":
    main()
