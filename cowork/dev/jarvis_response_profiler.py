#!/usr/bin/env python3
"""jarvis_response_profiler.py — Profiling temps de reponse JARVIS.

Identifie goulots d'etranglement par composant.

Usage:
    python dev/jarvis_response_profiler.py --once
    python dev/jarvis_response_profiler.py --profile
    python dev/jarvis_response_profiler.py --bottlenecks
    python dev/jarvis_response_profiler.py --optimize
"""
import argparse
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "response_profiler.db"

ENDPOINTS = [
    {"name": "ws_server", "url": "http://127.0.0.1:9742/api/status", "component": "backend"},
    {"name": "ollama", "url": "http://127.0.0.1:11434/api/tags", "component": "ai"},
    {"name": "m1_lmstudio", "url": "http://127.0.0.1:1234/api/v1/models", "component": "ai"},
    {"name": "openclaw", "url": "http://127.0.0.1:18789/health", "component": "gateway"},
    {"name": "dashboard", "url": "http://127.0.0.1:8080", "component": "frontend"},
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, endpoint TEXT, component TEXT,
        latency_ms REAL, status TEXT, size_bytes INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, p50_ms REAL, p95_ms REAL, p99_ms REAL,
        bottleneck TEXT, total_endpoints INTEGER)""")
    db.commit()
    return db


def measure_endpoint(ep):
    """Measure latency of an endpoint."""
    try:
        req = urllib.request.Request(ep["url"])
        start = time.time()
        with urllib.request.urlopen(req, timeout=5) as r:
            data = r.read()
            latency = (time.time() - start) * 1000
            return {
                "name": ep["name"], "component": ep["component"],
                "latency_ms": round(latency, 1), "status": "ok",
                "size_bytes": len(data),
            }
    except Exception as e:
        latency = (time.time() - start) * 1000 if 'start' in dir() else 5000
        return {
            "name": ep["name"], "component": ep["component"],
            "latency_ms": round(latency, 1), "status": "error",
            "size_bytes": 0,
        }


def do_profile():
    """Profile all endpoints."""
    db = init_db()
    results = []

    for ep in ENDPOINTS:
        result = measure_endpoint(ep)
        results.append(result)
        db.execute(
            "INSERT INTO profiles (ts, endpoint, component, latency_ms, status, size_bytes) VALUES (?,?,?,?,?,?)",
            (time.time(), result["name"], result["component"],
             result["latency_ms"], result["status"], result["size_bytes"])
        )

    # Calculate percentiles
    latencies = sorted([r["latency_ms"] for r in results if r["status"] == "ok"])
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[-1] if latencies else 0

    # Find bottleneck
    bottleneck = max(results, key=lambda r: r["latency_ms"]) if results else None

    # Historical comparison
    prev = db.execute(
        "SELECT AVG(latency_ms) FROM profiles WHERE ts > ? AND status='ok'",
        (time.time() - 86400,)
    ).fetchone()
    avg_24h = round(prev[0], 1) if prev and prev[0] else 0

    report = {
        "ts": datetime.now().isoformat(),
        "endpoints_tested": len(results),
        "endpoints_ok": sum(1 for r in results if r["status"] == "ok"),
        "p50_ms": p50, "p95_ms": p95, "p99_ms": p99,
        "avg_24h_ms": avg_24h,
        "bottleneck": bottleneck["name"] if bottleneck else "none",
        "results": results,
    }

    db.execute(
        "INSERT INTO reports (ts, p50_ms, p95_ms, p99_ms, bottleneck, total_endpoints) VALUES (?,?,?,?,?,?)",
        (time.time(), p50, p95, p99, bottleneck["name"] if bottleneck else "", len(results))
    )
    db.commit()
    db.close()
    return report


def show_bottlenecks():
    """Show historical bottlenecks."""
    db = init_db()
    rows = db.execute(
        "SELECT endpoint, AVG(latency_ms), COUNT(*) FROM profiles WHERE ts > ? GROUP BY endpoint ORDER BY AVG(latency_ms) DESC",
        (time.time() - 86400 * 7,)
    ).fetchall()
    db.close()
    return [{"endpoint": r[0], "avg_ms": round(r[1], 1), "samples": r[2]} for r in rows]


def main():
    parser = argparse.ArgumentParser(description="JARVIS Response Profiler")
    parser.add_argument("--once", "--profile", action="store_true", help="Profile endpoints")
    parser.add_argument("--bottlenecks", action="store_true", help="Show bottlenecks")
    parser.add_argument("--optimize", action="store_true", help="Optimization suggestions")
    args = parser.parse_args()

    if args.bottlenecks:
        print(json.dumps(show_bottlenecks(), ensure_ascii=False, indent=2))
    else:
        result = do_profile()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
