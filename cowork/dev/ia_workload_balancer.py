#!/usr/bin/env python3
"""ia_workload_balancer.py — Equilibreur de charge IA.

Distribue les requetes optimalement entre noeuds.

Usage:
    python dev/ia_workload_balancer.py --once
    python dev/ia_workload_balancer.py --balance
    python dev/ia_workload_balancer.py --status
    python dev/ia_workload_balancer.py --report
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
DB_PATH = DEV / "data" / "workload_balancer.db"
NODES = {
    "M1": {"host": "127.0.0.1", "port": 1234, "type": "lmstudio", "weight": 1.8},
    "M2": {"host": "192.168.1.26", "port": 1234, "type": "lmstudio", "weight": 1.4},
    "M3": {"host": "192.168.1.113", "port": 1234, "type": "lmstudio", "weight": 1.0},
    "OL1": {"host": "127.0.0.1", "port": 11434, "type": "ollama", "weight": 1.3},
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS balance_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, node TEXT, online INTEGER,
        latency_ms REAL, score REAL)""")
    db.commit()
    return db


def check_node(name, info):
    host, port = info["host"], info["port"]
    try:
        start = time.time()
        if info["type"] == "lmstudio":
            url = f"http://{host}:{port}/api/v1/models"
        else:
            url = f"http://{host}:{port}/api/tags"

        out = subprocess.run(
            ["curl", "-s", "--max-time", "3", url],
            capture_output=True, text=True, timeout=5
        )
        latency = (time.time() - start) * 1000

        if out.returncode == 0 and out.stdout.strip():
            data = json.loads(out.stdout)
            if info["type"] == "lmstudio":
                models = len([m for m in data.get("data", data.get("models", [])) if m.get("loaded_instances")])
            else:
                models = len(data.get("models", []))
            return {"online": True, "latency_ms": round(latency), "models": models}
    except Exception:
        pass
    return {"online": False, "latency_ms": -1, "models": 0}


def calculate_score(node_name, status, weight):
    if not status["online"]:
        return 0.0
    # Score = weight * (1 / latency_factor) * model_bonus
    latency_factor = max(status["latency_ms"], 50) / 100
    model_bonus = 1.0 + (status["models"] * 0.1)
    return round(weight * (1 / latency_factor) * model_bonus, 3)


def do_balance():
    db = init_db()
    results = []

    for name, info in NODES.items():
        status = check_node(name, info)
        score = calculate_score(name, status, info["weight"])
        results.append({
            "node": name,
            "host": f"{info['host']}:{info['port']}",
            "online": status["online"],
            "latency_ms": status["latency_ms"],
            "models_loaded": status.get("models", 0),
            "weight": info["weight"],
            "score": score,
        })
        db.execute("INSERT INTO balance_snapshots (ts, node, online, latency_ms, score) VALUES (?,?,?,?,?)",
                   (time.time(), name, int(status["online"]), status["latency_ms"], score))

    db.commit()
    db.close()

    results.sort(key=lambda x: x["score"], reverse=True)
    online = [r for r in results if r["online"]]

    return {
        "ts": datetime.now().isoformat(),
        "nodes": results,
        "online": len(online),
        "offline": len(results) - len(online),
        "recommended_order": [r["node"] for r in results if r["online"]],
        "best_node": results[0]["node"] if results and results[0]["online"] else "none",
    }


def main():
    parser = argparse.ArgumentParser(description="IA Workload Balancer")
    parser.add_argument("--once", "--balance", action="store_true", help="Balance check")
    parser.add_argument("--status", action="store_true", help="Status")
    parser.add_argument("--migrate", action="store_true", help="Migrate tasks")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()
    print(json.dumps(do_balance(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
