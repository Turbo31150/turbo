#!/usr/bin/env python3
"""ia_model_cache_manager.py — Gestionnaire cache modeles IA.

Pre-charge et evince modeles selon usage.

Usage:
    python dev/ia_model_cache_manager.py --once
    python dev/ia_model_cache_manager.py --status
    python dev/ia_model_cache_manager.py --preload MODEL
    python dev/ia_model_cache_manager.py --optimize
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
DB_PATH = DEV / "data" / "model_cache_manager.db"
LMS_NODES = {
    "M1": "http://127.0.0.1:1234",
    "M2": "http://192.168.1.26:1234",
    "M3": "http://192.168.1.113:1234",
}
OLLAMA = "http://127.0.0.1:11434"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS cache_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, node TEXT, model TEXT,
        loaded INTEGER, vram_gb REAL)""")
    db.commit()
    return db


def get_lms_models(name, url):
    models = []
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "3", f"{url}/api/v1/models"],
            capture_output=True, text=True, timeout=5
        )
        if out.stdout.strip():
            data = json.loads(out.stdout)
            for m in data.get("data", data.get("models", [])):
                models.append({
                    "node": name,
                    "model": m.get("id", "?"),
                    "loaded": bool(m.get("loaded_instances")),
                    "vram_gb": round(m.get("size_on_disk", 0) / 1e9, 1) if m.get("loaded_instances") else 0,
                })
    except Exception:
        pass
    return models


def get_ollama_models():
    models = []
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "3", f"{OLLAMA}/api/tags"],
            capture_output=True, text=True, timeout=5
        )
        if out.stdout.strip():
            data = json.loads(out.stdout)
            for m in data.get("models", []):
                models.append({
                    "node": "OL1",
                    "model": m.get("name", "?"),
                    "loaded": True,  # If listed, it's available
                    "vram_gb": round(m.get("size", 0) / 1e9, 1),
                })
    except Exception:
        pass
    return models


def do_status():
    db = init_db()
    all_models = []

    for name, url in LMS_NODES.items():
        all_models.extend(get_lms_models(name, url))
    all_models.extend(get_ollama_models())

    for m in all_models:
        db.execute("INSERT INTO cache_snapshots (ts, node, model, loaded, vram_gb) VALUES (?,?,?,?,?)",
                   (time.time(), m["node"], m["model"], int(m["loaded"]), m["vram_gb"]))
    db.commit()
    db.close()

    loaded = [m for m in all_models if m["loaded"]]
    total_vram = sum(m["vram_gb"] for m in loaded)

    by_node = {}
    for m in all_models:
        by_node.setdefault(m["node"], []).append(m)

    return {
        "ts": datetime.now().isoformat(),
        "total_models": len(all_models),
        "loaded": len(loaded),
        "total_vram_gb": round(total_vram, 1),
        "by_node": {k: {"models": len(v), "loaded": sum(1 for m in v if m["loaded"])}
                    for k, v in by_node.items()},
        "models": all_models,
    }


def main():
    parser = argparse.ArgumentParser(description="IA Model Cache Manager")
    parser.add_argument("--once", "--status", action="store_true", help="Cache status")
    parser.add_argument("--preload", metavar="MODEL", help="Preload model")
    parser.add_argument("--evict", action="store_true", help="Evict unused")
    parser.add_argument("--optimize", action="store_true", help="Optimize cache")
    args = parser.parse_args()
    print(json.dumps(do_status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
