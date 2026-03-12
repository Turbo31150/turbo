#!/usr/bin/env python3
"""jarvis_api_gateway.py — Test gateway API JARVIS.

Verifie tous les endpoints (FastAPI, OpenClaw, n8n, Dashboard).

Usage:
    python dev/jarvis_api_gateway.py --once
    python dev/jarvis_api_gateway.py --status
    python dev/jarvis_api_gateway.py --endpoints
    python dev/jarvis_api_gateway.py --test-all
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
DB_PATH = DEV / "data" / "api_gateway.db"

ENDPOINTS = [
    {"name": "ws_server", "url": "http://127.0.0.1:9742/api/status", "critical": True},
    {"name": "ollama", "url": "http://127.0.0.1:11434/api/tags", "critical": True},
    {"name": "m1_lmstudio", "url": "http://127.0.0.1:1234/api/v1/models", "critical": True},
    {"name": "m2_lmstudio", "url": "http://192.168.1.26:1234/api/v1/models", "critical": False},
    {"name": "m3_lmstudio", "url": "http://192.168.1.113:1234/api/v1/models", "critical": False},
    {"name": "openclaw_gw", "url": "http://127.0.0.1:18789/health", "critical": False},
    {"name": "dashboard", "url": "http://127.0.0.1:8080", "critical": False},
    {"name": "mcp_sse", "url": "http://127.0.0.1:8901/health", "critical": False},
    {"name": "n8n", "url": "http://127.0.0.1:5678", "critical": False},
    {"name": "direct_proxy", "url": "http://127.0.0.1:18800/health", "critical": False},
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, endpoint TEXT, status TEXT,
        latency_ms REAL, http_code INTEGER, size_bytes INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total INTEGER, up INTEGER, down INTEGER,
        avg_latency_ms REAL)""")
    db.commit()
    return db


def test_endpoint(ep):
    """Test a single endpoint."""
    start = time.time()
    try:
        req = urllib.request.Request(ep["url"])
        with urllib.request.urlopen(req, timeout=5) as r:
            data = r.read()
            latency = (time.time() - start) * 1000
            return {
                "name": ep["name"], "url": ep["url"],
                "status": "up", "latency_ms": round(latency, 1),
                "http_code": r.status, "size_bytes": len(data),
                "critical": ep.get("critical", False),
            }
    except Exception as e:
        latency = (time.time() - start) * 1000
        return {
            "name": ep["name"], "url": ep["url"],
            "status": "down", "latency_ms": round(latency, 1),
            "http_code": 0, "size_bytes": 0,
            "critical": ep.get("critical", False),
            "error": str(e)[:80],
        }


def do_test_all():
    """Test all endpoints."""
    db = init_db()
    results = []

    for ep in ENDPOINTS:
        result = test_endpoint(ep)
        results.append(result)
        db.execute(
            "INSERT INTO checks (ts, endpoint, status, latency_ms, http_code, size_bytes) VALUES (?,?,?,?,?,?)",
            (time.time(), result["name"], result["status"],
             result["latency_ms"], result["http_code"], result["size_bytes"])
        )

    up = sum(1 for r in results if r["status"] == "up")
    down = sum(1 for r in results if r["status"] == "down")
    critical_down = [r["name"] for r in results if r["status"] == "down" and r.get("critical")]
    latencies = [r["latency_ms"] for r in results if r["status"] == "up"]
    avg_latency = round(sum(latencies) / max(len(latencies), 1), 1)

    # Uptime history
    total_24h = db.execute(
        "SELECT COUNT(*) FROM checks WHERE ts > ?", (time.time() - 86400,)
    ).fetchone()[0]
    up_24h = db.execute(
        "SELECT COUNT(*) FROM checks WHERE ts > ? AND status='up'", (time.time() - 86400,)
    ).fetchone()[0]
    uptime = round(up_24h / max(total_24h, 1) * 100, 1)

    report = {
        "ts": datetime.now().isoformat(),
        "total": len(results), "up": up, "down": down,
        "critical_down": critical_down,
        "avg_latency_ms": avg_latency,
        "uptime_24h_pct": uptime,
        "endpoints": results,
    }

    db.execute(
        "INSERT INTO reports (ts, total, up, down, avg_latency_ms) VALUES (?,?,?,?,?)",
        (time.time(), len(results), up, down, avg_latency)
    )
    db.commit()
    db.close()
    return report


def show_endpoints():
    """Show endpoint list."""
    return [{"name": ep["name"], "url": ep["url"], "critical": ep.get("critical", False)} for ep in ENDPOINTS]


def main():
    parser = argparse.ArgumentParser(description="JARVIS API Gateway")
    parser.add_argument("--once", "--status", "--test-all", action="store_true", help="Test all endpoints")
    parser.add_argument("--endpoints", action="store_true", help="List endpoints")
    parser.add_argument("--latency", action="store_true", help="Latency report")
    args = parser.parse_args()

    if args.endpoints:
        print(json.dumps(show_endpoints(), ensure_ascii=False, indent=2))
    else:
        result = do_test_all()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
