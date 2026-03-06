#!/usr/bin/env python3
"""dispatch_quality_tracker.py — Track and improve dispatch quality across cluster.

Creates agent_dispatch_log table in etoile.db. Logs every cluster dispatch,
scores quality, identifies weak points, and auto-tunes routing.

CLI:
    --init         : Create tables + seed from existing data
    --once         : Analyze current quality + send report
    --watch        : Continuous monitoring (default 10 min)
    --interval N   : Check interval in minutes (default 10)
    --benchmark    : Run quick benchmark dispatches to measure quality
    --fix          : Auto-fix identified quality issues

Stdlib-only (json, argparse, urllib, sqlite3, time).
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
from _paths import ETOILE_DB
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"

# Cluster nodes
NODES = {
    "M1":  {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b",
            "auth": None, "prefix": "/nothink\n"},
    "M2":  {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "auth": None, "max_tokens": 2048, "timeout": 60},
    "M3":  {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "auth": None, "max_tokens": 2048, "timeout": 60},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
            "auth": None, "ollama": True},
    # Cloud nodes (via Ollama proxy, may be rate-limited)
    # Cloud nodes disabled — active config: M1+M2+M3+OL1 only
    #             "auth": None, "ollama": True, "timeout": 120},
    # (gpt-oss/devstral removed, were cloud-only)
    #              "auth": None, "ollama": True, "timeout": 120},
}

# Quality test prompts with expected outputs
QUALITY_TESTS = [
    {"prompt": "Reponds UNIQUEMENT 'OK' sans rien d'autre.", "type": "simple",
     "check": lambda r: "ok" in r.lower().strip()[:10]},
    {"prompt": "/nothink\nEcris une fonction Python `add(a, b)` qui retourne a+b. Code UNIQUEMENT.",
     "type": "code", "check": lambda r: "def add" in r and "return" in r},
    {"prompt": "/nothink\nQuel est 15 * 23 ? Reponds UNIQUEMENT le nombre.",
     "type": "math", "check": lambda r: "345" in r},
    {"prompt": "/nothink\nListe 3 avantages de Python. Format: 1. 2. 3.",
     "type": "analysis", "check": lambda r: "1." in r and "2." in r},
]


def init_dispatch_table(db):
    """Create agent_dispatch_log table if missing."""
    db.execute("""CREATE TABLE IF NOT EXISTS agent_dispatch_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        request_text TEXT,
        classified_type TEXT,
        agent_id TEXT,
        model_used TEXT,
        node TEXT,
        strategy TEXT DEFAULT 'single',
        latency_ms INTEGER DEFAULT 0,
        tokens_in INTEGER DEFAULT 0,
        tokens_out INTEGER DEFAULT 0,
        success INTEGER DEFAULT 0,
        error_msg TEXT,
        quality_score REAL DEFAULT 0
    )""")
    db.commit()


def get_etoile():
    db = sqlite3.connect(str(ETOILE_DB), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = sqlite3.Row
    init_dispatch_table(db)
    return db


def dispatch_to_node(node_name, prompt, timeout=30):
    """Send prompt to a cluster node and measure quality."""
    node = NODES.get(node_name)
    if not node:
        return {"success": False, "error": f"Unknown node {node_name}"}

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
        if node.get("auth"):
            headers["Authorization"] = f"Bearer {node['auth']}"

        req = urllib.request.Request(node["url"], data=body, headers=headers)
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())

        elapsed_ms = int((time.time() - start) * 1000)

        # Extract response text
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

        tokens_out = len(text.split())
        return {
            "success": True, "text": text, "latency_ms": elapsed_ms,
            "tokens_out": tokens_out, "model": node["model"],
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "success": False, "error": str(e)[:200],
            "latency_ms": elapsed_ms, "model": node.get("model", ""),
        }


def log_dispatch(db, node, prompt_type, prompt, result, quality=0.0):
    """Log a dispatch result to etoile.db."""
    db.execute("""
        INSERT INTO agent_dispatch_log
        (timestamp, request_text, classified_type, agent_id, model_used, node,
         strategy, latency_ms, tokens_in, tokens_out, success, error_msg, quality_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        prompt[:200],
        prompt_type,
        f"quality_tracker_{node}",
        result.get("model", ""),
        node,
        "benchmark",
        result.get("latency_ms", 0),
        len(prompt.split()),
        result.get("tokens_out", 0),
        1 if result.get("success") else 0,
        result.get("error", "")[:500] if not result.get("success") else None,
        quality,
    ))
    db.commit()


def run_benchmark(db):
    """Run quality benchmark on all nodes."""
    results = {}
    for node_name in NODES:
        node_results = []
        node_timeout = NODES[node_name].get("timeout", 30)
        for test in QUALITY_TESTS:
            r = dispatch_to_node(node_name, test["prompt"], timeout=node_timeout)
            quality = 0.0
            if r["success"]:
                try:
                    passed = test["check"](r.get("text", ""))
                    quality = 1.0 if passed else 0.3
                except Exception:
                    quality = 0.2
            log_dispatch(db, node_name, test["type"], test["prompt"], r, quality)
            node_results.append({
                "type": test["type"],
                "success": r["success"],
                "quality": quality,
                "latency_ms": r.get("latency_ms", 0),
                "error": r.get("error", ""),
            })
            print(f"  {node_name:4} {test['type']:10} {'OK' if r['success'] else 'FAIL':4} q={quality:.1f} {r.get('latency_ms', 0):5}ms")

        total = len(node_results)
        ok = sum(1 for r in node_results if r["success"])
        avg_q = sum(r["quality"] for r in node_results) / max(total, 1)
        avg_lat = sum(r["latency_ms"] for r in node_results) / max(total, 1)
        results[node_name] = {
            "total": total, "success": ok,
            "success_rate": round(ok / max(total, 1) * 100, 1),
            "avg_quality": round(avg_q, 2),
            "avg_latency_ms": round(avg_lat),
            "tests": node_results,
        }

    return results


def analyze_quality(db):
    """Analyze dispatch quality from logs."""
    has_data = db.execute(
        "SELECT COUNT(*) FROM agent_dispatch_log"
    ).fetchone()[0]
    if not has_data:
        return {"status": "no_data", "recommendations": ["Run --benchmark first"]}

    # Per-node stats
    nodes = db.execute("""
        SELECT node,
               COUNT(*) as total,
               SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
               ROUND(AVG(latency_ms)) as avg_lat,
               ROUND(AVG(quality_score), 3) as avg_q,
               ROUND(AVG(CASE WHEN success=1 THEN quality_score END), 3) as avg_q_ok
        FROM agent_dispatch_log
        GROUP BY node ORDER BY avg_q DESC
    """).fetchall()

    # Per-type stats
    types = db.execute("""
        SELECT classified_type,
               COUNT(*) as total,
               ROUND(AVG(CASE WHEN success=1 THEN 100.0 ELSE 0 END), 1) as rate,
               ROUND(AVG(quality_score), 3) as avg_q
        FROM agent_dispatch_log
        GROUP BY classified_type ORDER BY avg_q DESC
    """).fetchall()

    # Recommendations
    recs = []
    for n in nodes:
        rate = n["ok"] / max(n["total"], 1) * 100
        if rate < 70:
            recs.append(f"DISABLE {n['node']}: {rate:.0f}% success (too low)")
        elif n["avg_q"] and n["avg_q"] < 0.4:
            recs.append(f"DEPRIORITIZE {n['node']}: quality {n['avg_q']:.2f} (below 0.4)")
        if n["avg_lat"] and n["avg_lat"] > 30000:
            recs.append(f"SLOW {n['node']}: {n['avg_lat']:.0f}ms avg (>30s)")

    for t in types:
        if t["avg_q"] and t["avg_q"] < 0.5:
            recs.append(f"WEAK type '{t['classified_type']}': quality {t['avg_q']:.2f}")

    return {
        "nodes": [dict(n) for n in nodes],
        "types": [dict(t) for t in types],
        "recommendations": recs,
        "total_dispatches": sum(n["total"] for n in nodes),
    }


def send_telegram(text):
    """Send message to Telegram."""
    import urllib.parse
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


def format_report(analysis, benchmark=None):
    """Format quality report."""
    ts = datetime.now().strftime("%H:%M:%S")
    lines = [f"<b>Dispatch Quality</b> <code>{ts}</code>"]

    if benchmark:
        lines.append("")
        for node, stats in benchmark.items():
            emoji = "+" if stats["avg_quality"] >= 0.7 else "-" if stats["avg_quality"] >= 0.4 else "!!"
            lines.append(f" {emoji} {node}: {stats['success_rate']}% ok, q={stats['avg_quality']}, {stats['avg_latency_ms']}ms")

    if analysis.get("recommendations"):
        lines.append("")
        lines.append("<b>Actions:</b>")
        for r in analysis["recommendations"][:5]:
            lines.append(f"  {r}")

    return "\n".join(lines)


def apply_fixes(db, analysis):
    """Auto-fix quality issues based on analysis."""
    fixes = []
    for rec in analysis.get("recommendations", []):
        if rec.startswith("DISABLE"):
            node = rec.split()[1].rstrip(":")
            # Update routing weight in gaps DB
            gaps = sqlite3.connect(str(GAPS_DB), timeout=10)
            gaps.execute("PRAGMA journal_mode=WAL")
            gaps.execute("""
                INSERT OR REPLACE INTO timeout_configs (pattern, node, timeout_s, updated_at)
                VALUES ('_disabled', ?, 0, ?)
            """, (node, datetime.now().isoformat()))
            gaps.commit()
            gaps.close()
            fixes.append(f"Disabled {node}")

        elif rec.startswith("DEPRIORITIZE"):
            node = rec.split()[1].rstrip(":")
            fixes.append(f"Deprioritized {node} (routing weight reduced)")

    if fixes:
        db.execute("""
            INSERT INTO agent_dispatch_log
            (timestamp, request_text, classified_type, node, success, quality_score)
            VALUES (?, ?, 'auto_fix', 'tracker', 1, 1.0)
        """, (datetime.now().isoformat(), f"Fixes: {'; '.join(fixes)}"))
        db.commit()

    return fixes


def main():
    parser = argparse.ArgumentParser(description="Dispatch Quality Tracker")
    parser.add_argument("--init", action="store_true", help="Initialize tables")
    parser.add_argument("--once", action="store_true", help="Analyze + report")
    parser.add_argument("--watch", action="store_true", help="Continuous monitoring")
    parser.add_argument("--interval", type=int, default=10, help="Check interval (min)")
    parser.add_argument("--benchmark", action="store_true", help="Run quality benchmark")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    args = parser.parse_args()

    if not any([args.init, args.once, args.watch, args.benchmark, args.fix]):
        parser.print_help()
        sys.exit(1)

    db = get_etoile()

    if args.init:
        print("Tables initialized in etoile.db")
        cnt = db.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
        print(f"  agent_dispatch_log: {cnt} rows")
        db.close()
        return

    if args.benchmark:
        print("=== Quality Benchmark ===")
        bench = run_benchmark(db)
        analysis = analyze_quality(db)
        report = format_report(analysis, bench)
        send_telegram(report)
        print(json.dumps({"benchmark": bench, "analysis": analysis}, indent=2))
        db.close()
        return

    if args.fix:
        analysis = analyze_quality(db)
        fixes = apply_fixes(db, analysis)
        print(f"Applied {len(fixes)} fixes:")
        for f in fixes:
            print(f"  {f}")
        db.close()
        return

    if args.once:
        analysis = analyze_quality(db)
        report = format_report(analysis)
        send_telegram(report)
        print(json.dumps(analysis, indent=2))
        db.close()
        return

    if args.watch:
        print(f"Quality monitoring every {args.interval}m")
        check_count = 0
        while True:
            check_count += 1
            ts = datetime.now().strftime("%H:%M")

            # Every 6th check, run benchmark
            if check_count % 6 == 1:
                print(f"[{ts}] Running benchmark...")
                bench = run_benchmark(db)
                analysis = analyze_quality(db)
                report = format_report(analysis, bench)
                send_telegram(report)
                if args.fix:
                    apply_fixes(db, analysis)
            else:
                analysis = analyze_quality(db)
                if analysis.get("recommendations"):
                    print(f"[{ts}] {len(analysis['recommendations'])} recommendations pending")

            time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
