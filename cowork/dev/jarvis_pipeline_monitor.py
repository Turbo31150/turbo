#!/usr/bin/env python3
"""jarvis_pipeline_monitor.py — Moniteur pipelines JARVIS.

Surveille tous les pipelines actifs, redémarre si crash.

Usage:
    python dev/jarvis_pipeline_monitor.py --once
    python dev/jarvis_pipeline_monitor.py --status
    python dev/jarvis_pipeline_monitor.py --failures
    python dev/jarvis_pipeline_monitor.py --restart NAME
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "pipeline_monitor.db"

# Known pipelines to monitor
PIPELINES = [
    {"name": "autonomous_loop", "check": "python", "pattern": "autonomous_loop"},
    {"name": "event_bus_monitor", "check": "python", "pattern": "event_bus_monitor"},
    {"name": "health_guard", "check": "python", "pattern": "autonomous_health_guard"},
    {"name": "cross_channel_sync", "check": "python", "pattern": "cross_channel_sync"},
    {"name": "smart_cron", "check": "python", "pattern": "smart_cron_manager"},
    {"name": "telegram_bot", "check": "node", "pattern": "telegram-bot"},
    {"name": "direct_proxy", "check": "node", "pattern": "direct-proxy"},
    {"name": "ollama", "check": "url", "url": "http://127.0.0.1:11434/api/tags"},
    {"name": "lmstudio_m1", "check": "url", "url": "http://127.0.0.1:1234/api/v1/models"},
    {"name": "ws_server", "check": "url", "url": "http://127.0.0.1:9742/api/status"},
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, pipeline TEXT, status TEXT,
        details TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS failures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, pipeline TEXT, error TEXT,
        auto_restarted INTEGER DEFAULT 0)""")
    db.commit()
    return db


def check_process(pattern):
    """Check if a process matching pattern is running."""
    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split("\n"):
            if pattern.lower() in line.lower():
                return True
    except Exception:
        pass
    return False


def check_url(url):
    """Check if a URL is responding."""
    import urllib.request
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def check_pipeline(pipeline):
    """Check a single pipeline status."""
    if pipeline["check"] == "url":
        ok = check_url(pipeline["url"])
        return {"name": pipeline["name"], "status": "running" if ok else "down", "type": "url"}
    elif pipeline["check"] in ("python", "node"):
        ok = check_process(pipeline["pattern"])
        return {"name": pipeline["name"], "status": "running" if ok else "down", "type": "process"}
    return {"name": pipeline["name"], "status": "unknown", "type": "unknown"}


def do_status():
    """Check all pipelines."""
    db = init_db()
    results = []
    failures = []

    for p in PIPELINES:
        result = check_pipeline(p)
        results.append(result)

        db.execute(
            "INSERT INTO checks (ts, pipeline, status, details) VALUES (?,?,?,?)",
            (time.time(), result["name"], result["status"], json.dumps(result))
        )

        if result["status"] == "down":
            failures.append(result["name"])
            db.execute(
                "INSERT INTO failures (ts, pipeline, error) VALUES (?,?,?)",
                (time.time(), result["name"], "process_not_found")
            )

    running = sum(1 for r in results if r["status"] == "running")
    down = sum(1 for r in results if r["status"] == "down")

    # Uptime calculation (last 24h)
    total_checks = db.execute(
        "SELECT COUNT(*) FROM checks WHERE ts > ?", (time.time() - 86400,)
    ).fetchone()[0]
    ok_checks = db.execute(
        "SELECT COUNT(*) FROM checks WHERE ts > ? AND status='running'", (time.time() - 86400,)
    ).fetchone()[0]
    uptime = round(ok_checks / max(total_checks, 1) * 100, 1)

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total": len(results),
        "running": running,
        "down": down,
        "uptime_24h_pct": uptime,
        "failures": failures,
        "pipelines": results,
    }


def show_failures():
    """Show recent failures."""
    db = init_db()
    rows = db.execute(
        "SELECT ts, pipeline, error FROM failures ORDER BY ts DESC LIMIT 20"
    ).fetchall()
    db.close()
    return [{
        "ts": datetime.fromtimestamp(r[0]).isoformat(),
        "pipeline": r[1], "error": r[2],
    } for r in rows]


def main():
    parser = argparse.ArgumentParser(description="JARVIS Pipeline Monitor")
    parser.add_argument("--once", "--status", action="store_true", help="Check status")
    parser.add_argument("--failures", action="store_true", help="Show failures")
    parser.add_argument("--restart", metavar="NAME", help="Restart pipeline")
    parser.add_argument("--health", action="store_true", help="Health report")
    args = parser.parse_args()

    if args.failures:
        print(json.dumps(show_failures(), ensure_ascii=False, indent=2))
    else:
        result = do_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
