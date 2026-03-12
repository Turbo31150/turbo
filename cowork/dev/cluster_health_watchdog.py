#!/usr/bin/env python3
"""cluster_health_watchdog.py — Continuous cluster health monitoring with alerts.

Pings all cluster nodes (M1/M2/M3/OL1), records health snapshots,
detects degradation patterns, and suggests preemptive actions.

CLI:
    --once       : single health check
    --history    : show health history
    --alerts     : show active alerts

Stdlib-only (sqlite3, json, argparse, urllib).
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"

CLUSTER_NODES = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/models",
        "type": "lmstudio",
        "timeout": 5,
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/models",
        "type": "lmstudio",
        "timeout": 5,
    },
    "M3": {
        "url": "http://192.168.1.113:1234/api/v1/models",
        "type": "lmstudio",
        "timeout": 5,
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/tags",
        "type": "ollama",
        "timeout": 5,
    },
}

HEALTH_THRESHOLDS = {
    "response_time_warning_ms": 3000,
    "response_time_critical_ms": 10000,
    "consecutive_failures_alert": 3,
    "loaded_models_warning": 0,
}


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS health_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        node TEXT NOT NULL,
        status TEXT NOT NULL,
        response_ms INTEGER,
        models_loaded INTEGER,
        error TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS health_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        node TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        message TEXT NOT NULL,
        resolved INTEGER DEFAULT 0
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def check_node(name, config):
    """Check a single node's health."""
    t0 = time.time()
    try:
        req = urllib.request.Request(config["url"])
        req.add_header("User-Agent", "JARVIS-HealthCheck/1.0")
        resp = urllib.request.urlopen(req, timeout=config["timeout"])
        data = json.loads(resp.read())
        elapsed_ms = int((time.time() - t0) * 1000)

        # Count loaded models
        if config["type"] == "lmstudio":
            models = data.get("data", data.get("models", []))
            loaded = len([m for m in models if m.get("loaded_instances")])
        else:
            models = data.get("models", [])
            loaded = len(models)

        status = "healthy"
        if elapsed_ms > HEALTH_THRESHOLDS["response_time_critical_ms"]:
            status = "degraded"
        elif elapsed_ms > HEALTH_THRESHOLDS["response_time_warning_ms"]:
            status = "slow"

        return {
            "node": name,
            "status": status,
            "response_ms": elapsed_ms,
            "models_loaded": loaded,
            "error": None,
        }
    except urllib.error.URLError as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "node": name,
            "status": "offline",
            "response_ms": elapsed_ms,
            "models_loaded": 0,
            "error": str(e.reason)[:100] if hasattr(e, 'reason') else str(e)[:100],
        }
    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "node": name,
            "status": "error",
            "response_ms": elapsed_ms,
            "models_loaded": 0,
            "error": str(e)[:100],
        }


def action_once():
    """Run a single health check cycle."""
    conn = get_db()
    ts = datetime.now().isoformat()
    results = []
    alerts = []

    for name, config in CLUSTER_NODES.items():
        result = check_node(name, config)
        results.append(result)

        # Record snapshot
        conn.execute("""
            INSERT INTO health_snapshots
            (timestamp, node, status, response_ms, models_loaded, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, name, result["status"], result["response_ms"],
              result["models_loaded"], result["error"]))

        # Check for alert conditions
        if result["status"] == "offline":
            # Check consecutive failures
            recent = conn.execute("""
                SELECT COUNT(*) as cnt FROM health_snapshots
                WHERE node = ? AND status = 'offline'
                AND id > (SELECT COALESCE(MAX(id), 0) FROM health_snapshots WHERE node = ? AND status = 'healthy')
            """, (name, name)).fetchone()["cnt"]

            if recent >= HEALTH_THRESHOLDS["consecutive_failures_alert"]:
                alert = {
                    "node": name, "type": "persistent_offline",
                    "message": f"{name} offline for {recent}+ checks — consider restart"
                }
                alerts.append(alert)
                conn.execute("""
                    INSERT INTO health_alerts (timestamp, node, alert_type, message)
                    VALUES (?, ?, ?, ?)
                """, (ts, name, alert["type"], alert["message"]))

        elif result["status"] == "degraded":
            alert = {
                "node": name, "type": "high_latency",
                "message": f"{name} response time {result['response_ms']}ms — degraded performance"
            }
            alerts.append(alert)

        if result["models_loaded"] == 0 and result["status"] == "healthy":
            alert = {
                "node": name, "type": "no_models",
                "message": f"{name} online but 0 models loaded"
            }
            alerts.append(alert)

    conn.commit()

    # Overall cluster health
    online = sum(1 for r in results if r["status"] in ("healthy", "slow"))
    total = len(results)
    cluster_status = "healthy" if online == total else "degraded" if online >= 2 else "critical"

    conn.close()

    return {
        "timestamp": ts,
        "cluster_status": cluster_status,
        "nodes_online": f"{online}/{total}",
        "nodes": results,
        "alerts": alerts,
    }


def action_history():
    """Show health check history."""
    conn = get_db()
    rows = conn.execute("""
        SELECT timestamp, node, status, response_ms, models_loaded
        FROM health_snapshots
        ORDER BY id DESC LIMIT 50
    """).fetchall()
    conn.close()
    return {"history": [dict(r) for r in rows]}


def action_alerts():
    """Show active alerts."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM health_alerts
        WHERE resolved = 0
        ORDER BY timestamp DESC LIMIT 20
    """).fetchall()
    conn.close()
    return {"active_alerts": [dict(r) for r in rows]}


def main():
    parser = argparse.ArgumentParser(description="Cluster Health Watchdog")
    parser.add_argument("--once", action="store_true", help="Single health check")
    parser.add_argument("--history", action="store_true", help="Show history")
    parser.add_argument("--alerts", action="store_true", help="Show alerts")
    args = parser.parse_args()

    if not any([args.once, args.history, args.alerts]):
        parser.print_help()
        sys.exit(1)

    if args.history:
        result = action_history()
    elif args.alerts:
        result = action_alerts()
    else:
        result = action_once()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
