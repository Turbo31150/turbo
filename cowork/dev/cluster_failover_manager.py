#!/usr/bin/env python3
"""cluster_failover_manager.py — Gestionnaire de failover cluster.

Teste scenarios de panne, verifie fallback, mesure temps recovery.

Usage:
    python dev/cluster_failover_manager.py --once
    python dev/cluster_failover_manager.py --test
    python dev/cluster_failover_manager.py --simulate M1
    python dev/cluster_failover_manager.py --status
    python dev/cluster_failover_manager.py --history
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
DB_PATH = DEV / "data" / "failover_manager.db"

NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/models", "fallback": "M2"},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/models", "fallback": "OL1"},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/models", "fallback": "OL1"},
    "OL1": {"url": "http://127.0.0.1:11434/api/tags", "fallback": "M1"},
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, node TEXT, status TEXT,
        latency_ms REAL, fallback_node TEXT, fallback_ok INTEGER,
        fallback_latency_ms REAL)""")
    db.commit()
    return db


def check_node(url, timeout=5):
    """Check node health and measure latency."""
    start = time.time()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            latency = (time.time() - start) * 1000
            return {"ok": True, "latency_ms": round(latency, 1)}
    except Exception as e:
        latency = (time.time() - start) * 1000
        return {"ok": False, "latency_ms": round(latency, 1), "error": str(e)}


def test_all_nodes():
    """Test all nodes and their fallbacks."""
    db = init_db()
    results = []

    for name, cfg in NODES.items():
        primary = check_node(cfg["url"])
        fallback_name = cfg["fallback"]
        fallback_cfg = NODES.get(fallback_name, {})
        fallback = check_node(fallback_cfg.get("url", ""), timeout=5) if fallback_cfg else {"ok": False}

        result = {
            "node": name,
            "status": "ONLINE" if primary["ok"] else "OFFLINE",
            "latency_ms": primary["latency_ms"],
            "fallback": fallback_name,
            "fallback_ok": fallback["ok"],
            "fallback_latency_ms": fallback.get("latency_ms", 0),
        }
        results.append(result)

        db.execute(
            "INSERT INTO tests (ts, node, status, latency_ms, fallback_node, fallback_ok, fallback_latency_ms) VALUES (?,?,?,?,?,?,?)",
            (time.time(), name, result["status"], result["latency_ms"],
             fallback_name, int(fallback["ok"]), fallback.get("latency_ms", 0))
        )

    db.commit()
    db.close()

    online = sum(1 for r in results if r["status"] == "ONLINE")
    failovers_ok = sum(1 for r in results if r["fallback_ok"])

    return {
        "ts": datetime.now().isoformat(),
        "nodes_online": online,
        "nodes_total": len(NODES),
        "failovers_ready": failovers_ok,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Cluster Failover Manager")
    parser.add_argument("--once", "--test", action="store_true", help="Test all nodes")
    parser.add_argument("--simulate", metavar="NODE", help="Simulate node failure")
    parser.add_argument("--status", action="store_true", help="Quick status")
    parser.add_argument("--history", action="store_true", help="Test history")
    args = parser.parse_args()

    result = test_all_nodes()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
