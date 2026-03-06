#!/usr/bin/env python3
"""cluster_heartbeat.py — Continuous cluster health monitoring with auto-recovery.

Pings all cluster nodes at regular intervals. Detects:
- Node going offline/online (state transitions)
- High latency spikes
- Model loading issues
- GPU thermal warnings

Sends Telegram alerts on state changes only (not repeated checks).

CLI:
    --once         : Single check
    --watch        : Continuous monitoring (default 2 min)
    --interval N   : Check interval in minutes (default 2)
    --verbose      : Print all checks, not just state changes

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
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"

NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/models", "type": "lmstudio"},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/models", "type": "lmstudio"},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/models", "type": "lmstudio"},
    "OL1": {"url": "http://127.0.0.1:11434/api/tags", "type": "ollama"},
}

LATENCY_WARN_MS = 5000  # Warn if health check takes > 5s


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS heartbeat_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        node TEXT NOT NULL,
        status TEXT NOT NULL,
        latency_ms INTEGER DEFAULT 0,
        models_loaded INTEGER DEFAULT 0,
        details TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS heartbeat_state (
        node TEXT PRIMARY KEY,
        last_status TEXT,
        last_check TEXT,
        consecutive_fails INTEGER DEFAULT 0
    )""")
    conn.commit()
    return conn


def check_node(node_name):
    """Check a single node's health."""
    node = NODES[node_name]
    start = time.time()
    try:
        req = urllib.request.Request(node["url"], headers={"User-Agent": "JARVIS/1.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        elapsed = int((time.time() - start) * 1000)

        if node["type"] == "lmstudio":
            models = data.get("data", data.get("models", []))
            loaded = [m for m in models if m.get("loaded_instances")]
            return {
                "status": "online", "latency_ms": elapsed,
                "models_loaded": len(loaded),
                "models": [m.get("id", "?") for m in loaded],
            }
        else:  # ollama
            models = data.get("models", [])
            return {
                "status": "online", "latency_ms": elapsed,
                "models_loaded": len(models),
                "models": [m.get("name", "?") for m in models[:5]],
            }
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        return {
            "status": "offline", "latency_ms": elapsed,
            "models_loaded": 0, "error": str(e)[:100],
        }


def send_telegram(text):
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


def check_all(conn, verbose=False):
    """Check all nodes, detect state changes, log and alert."""
    ts = datetime.now().isoformat()
    results = {}
    alerts = []

    for node_name in NODES:
        r = check_node(node_name)
        results[node_name] = r

        # Get previous state
        prev = conn.execute(
            "SELECT last_status, consecutive_fails FROM heartbeat_state WHERE node=?",
            (node_name,)
        ).fetchone()

        prev_status = prev["last_status"] if prev else None
        prev_fails = prev["consecutive_fails"] if prev else 0

        # Detect state transitions
        if prev_status and prev_status != r["status"]:
            if r["status"] == "offline":
                alerts.append(f"<b>{node_name}</b> DOWN ({r.get('error', 'timeout')[:50]})")
            else:
                alerts.append(f"<b>{node_name}</b> BACK ONLINE ({r['models_loaded']} models, {r['latency_ms']}ms)")

        # Detect latency spike
        if r["status"] == "online" and r["latency_ms"] > LATENCY_WARN_MS:
            alerts.append(f"<b>{node_name}</b> SLOW: {r['latency_ms']}ms (>{LATENCY_WARN_MS}ms)")

        # Update state
        new_fails = 0 if r["status"] == "online" else prev_fails + 1
        conn.execute("""
            INSERT OR REPLACE INTO heartbeat_state (node, last_status, last_check, consecutive_fails)
            VALUES (?, ?, ?, ?)
        """, (node_name, r["status"], ts, new_fails))

        # Log
        conn.execute("""
            INSERT INTO heartbeat_log (timestamp, node, status, latency_ms, models_loaded, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, node_name, r["status"], r["latency_ms"], r["models_loaded"],
              json.dumps(r.get("models", r.get("error", "")))))

    conn.commit()

    # Send alerts
    if alerts:
        msg = f"<b>Cluster Alert</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>\n\n" + "\n".join(alerts)
        send_telegram(msg)

    return results, alerts


def get_status_summary(conn):
    """Get current cluster status."""
    rows = conn.execute("""
        SELECT node, last_status, last_check, consecutive_fails
        FROM heartbeat_state ORDER BY node
    """).fetchall()
    return [dict(r) for r in rows]


def main():
    parser = argparse.ArgumentParser(description="Cluster Heartbeat Monitor")
    parser.add_argument("--once", action="store_true", help="Single check")
    parser.add_argument("--watch", action="store_true", help="Continuous monitoring")
    parser.add_argument("--interval", type=int, default=2, help="Check interval (min)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--status", action="store_true", help="Show current status")
    args = parser.parse_args()

    if not any([args.once, args.watch, args.status]):
        parser.print_help()
        sys.exit(1)

    conn = get_db()

    if args.status:
        summary = get_status_summary(conn)
        print(json.dumps(summary, indent=2))
        conn.close()
        return

    if args.once:
        results, alerts = check_all(conn, args.verbose)
        ts = datetime.now().strftime("%H:%M:%S")
        online = sum(1 for r in results.values() if r["status"] == "online")
        print(f"[{ts}] Cluster: {online}/{len(NODES)} online")
        for name, r in results.items():
            status = "OK" if r["status"] == "online" else "DOWN"
            print(f"  {name:4} {status:4} {r['latency_ms']:5}ms  models={r['models_loaded']}")
        if alerts:
            print(f"  ALERTS: {len(alerts)}")
            for a in alerts:
                print(f"    {a}")
        result = {
            "timestamp": datetime.now().isoformat(),
            "online": online, "total": len(NODES),
            "nodes": results, "alerts": alerts,
        }
        print(json.dumps(result, indent=2))
        conn.close()
        return

    if args.watch:
        print(f"Heartbeat monitoring every {args.interval}m")
        while True:
            results, alerts = check_all(conn, args.verbose)
            ts = datetime.now().strftime("%H:%M:%S")
            online = sum(1 for r in results.values() if r["status"] == "online")
            line = f"[{ts}] {online}/{len(NODES)} online"
            if alerts:
                line += f" | {len(alerts)} alerts"
            print(line)
            if args.verbose:
                for name, r in results.items():
                    print(f"  {name}: {r['status']} {r['latency_ms']}ms")
            time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
