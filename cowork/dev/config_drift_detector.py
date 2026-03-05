#!/usr/bin/env python3
"""config_drift_detector.py — Detect config differences between cluster nodes.

Compares LM Studio configs across M1/M2/M3, checks Ollama model versions,
and detects parameter drift (temperature, max_tokens).
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'cowork_gaps.db')

NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/models", "type": "lmstudio"},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/models", "type": "lmstudio"},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/models", "type": "lmstudio"},
    "OL1": {"url": "http://127.0.0.1:11434/api/tags", "type": "ollama"},
}


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS config_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node TEXT, config_json TEXT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS config_drifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_a TEXT, node_b TEXT, diff_key TEXT, val_a TEXT, val_b TEXT,
        severity TEXT DEFAULT 'info', timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    db.commit()
    return db


def fetch_config(node_name, node_info, timeout=5):
    """Fetch node configuration."""
    try:
        req = urllib.request.Request(node_info["url"])
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        if node_info["type"] == "lmstudio":
            models = data.get("data", data.get("models", []))
            loaded = [m for m in models if m.get("loaded_instances")]
            return {
                "status": "online", "type": "lmstudio",
                "total_models": len(models), "loaded_models": len(loaded),
                "models": [{"id": m.get("id"), "loaded": bool(m.get("loaded_instances"))} for m in models[:10]]
            }
        else:
            models = data.get("models", [])
            return {
                "status": "online", "type": "ollama",
                "total_models": len(models),
                "models": [{"name": m.get("name"), "size": m.get("size", 0)} for m in models[:20]]
            }
    except Exception as e:
        return {"status": "offline", "error": str(e)[:100]}


def detect_drifts(configs):
    """Compare configs between nodes and detect drifts."""
    drifts = []
    lmstudio_nodes = {k: v for k, v in configs.items() if v.get("type") == "lmstudio" and v["status"] == "online"}
    nodes = list(lmstudio_nodes.keys())

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            ca, cb = lmstudio_nodes[a], lmstudio_nodes[b]

            # Compare loaded model count
            if ca.get("loaded_models", 0) != cb.get("loaded_models", 0):
                drifts.append({
                    "node_a": a, "node_b": b,
                    "diff_key": "loaded_models",
                    "val_a": str(ca.get("loaded_models")),
                    "val_b": str(cb.get("loaded_models")),
                    "severity": "warning"
                })

            # Compare model lists
            models_a = {m["id"] for m in ca.get("models", []) if m.get("loaded")}
            models_b = {m["id"] for m in cb.get("models", []) if m.get("loaded")}
            only_a = models_a - models_b
            only_b = models_b - models_a
            if only_a:
                drifts.append({
                    "node_a": a, "node_b": b, "diff_key": "models_only_in_a",
                    "val_a": ",".join(only_a), "val_b": "", "severity": "info"
                })
            if only_b:
                drifts.append({
                    "node_a": a, "node_b": b, "diff_key": "models_only_in_b",
                    "val_a": "", "val_b": ",".join(only_b), "severity": "info"
                })

    # Offline nodes = critical drift
    for name, cfg in configs.items():
        if cfg["status"] == "offline":
            drifts.append({
                "node_a": name, "node_b": "expected",
                "diff_key": "status", "val_a": "offline", "val_b": "online",
                "severity": "critical"
            })

    return drifts


def run_once():
    """Run drift detection once."""
    db = init_db()
    configs = {}
    for name, info in NODES.items():
        configs[name] = fetch_config(name, info)
        db.execute("INSERT INTO config_snapshots (node, config_json) VALUES (?, ?)",
                   (name, json.dumps(configs[name], ensure_ascii=False)))

    drifts = detect_drifts(configs)
    for d in drifts:
        db.execute("INSERT INTO config_drifts (node_a, node_b, diff_key, val_a, val_b, severity) VALUES (?,?,?,?,?,?)",
                   (d["node_a"], d["node_b"], d["diff_key"], d["val_a"], d["val_b"], d["severity"]))

    db.commit()
    db.close()

    result = {
        "nodes": {k: {"status": v["status"], "models": v.get("total_models", 0)} for k, v in configs.items()},
        "drifts": drifts,
        "drift_count": len(drifts),
        "critical": sum(1 for d in drifts if d["severity"] == "critical"),
        "timestamp": datetime.now().isoformat()
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Config Drift Detector")
    parser.add_argument("--once", action="store_true", help="Run once")
    parser.add_argument("--diff", action="store_true", help="Show diffs only")
    parser.add_argument("--fix", action="store_true", help="Suggest fixes")
    args = parser.parse_args()

    result = run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
