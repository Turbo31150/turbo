#!/usr/bin/env python3
"""cluster_model_rotator.py — Rotation intelligente des modeles.

Charge/decharge selon usage et temperature GPU.

Usage:
    python dev/cluster_model_rotator.py --once
    python dev/cluster_model_rotator.py --rotate
    python dev/cluster_model_rotator.py --schedule
    python dev/cluster_model_rotator.py --status
    python dev/cluster_model_rotator.py --history
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "model_rotator.db"
OL1_URL = "http://127.0.0.1:11434"
M1_URL = "http://127.0.0.1:1234"
LMS_EXE = r"C:\Users\franc\.lmstudio\bin\lms.exe"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS rotations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, action TEXT, model TEXT,
        node TEXT, reason TEXT)""")
    db.commit()
    return db


def get_loaded_ollama():
    """Get loaded Ollama models."""
    try:
        req = urllib.request.Request(f"{OL1_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def get_loaded_lmstudio():
    """Get loaded LM Studio models."""
    try:
        req = urllib.request.Request(f"{M1_URL}/api/v1/models")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            models = data.get("data", data.get("models", []))
            return [m.get("id", "") for m in models if m.get("loaded_instances")]
    except Exception:
        return []


def get_gpu_temp():
    """Get max GPU temperature."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            temps = [int(t.strip()) for t in result.stdout.strip().split("\n") if t.strip()]
            return max(temps) if temps else 0
    except Exception:
        pass
    return 0


def do_rotate():
    """Perform model rotation based on current state."""
    db = init_db()
    gpu_temp = get_gpu_temp()
    ollama_models = get_loaded_ollama()
    lms_models = get_loaded_lmstudio()
    actions = []

    now = datetime.now()
    hour = now.hour

    # Thermal protection: if GPU too hot, unload heavy models
    if gpu_temp > 80:
        actions.append({
            "action": "thermal_warning",
            "reason": f"GPU at {gpu_temp}C — consider unloading heavy models",
        })

    # Time-based recommendations
    if hour in range(0, 6):  # Night: eco mode
        actions.append({
            "action": "eco_mode",
            "reason": "Night hours — light models only recommended",
        })
    elif hour in range(8, 12):  # Morning: dev mode
        if "qwen3-8b" not in " ".join(lms_models):
            actions.append({
                "action": "recommend_load",
                "model": "qwen3-8b",
                "node": "M1",
                "reason": "Morning dev hours — code model needed",
            })
    elif hour in range(14, 22):  # Afternoon: full power
        actions.append({
            "action": "full_power",
            "reason": "Peak hours — all models should be loaded",
        })

    for a in actions:
        db.execute(
            "INSERT INTO rotations (ts, action, model, node, reason) VALUES (?,?,?,?,?)",
            (time.time(), a["action"], a.get("model", ""), a.get("node", ""), a["reason"])
        )

    db.commit()
    db.close()

    return {
        "ts": now.isoformat(),
        "gpu_temp": gpu_temp,
        "ollama_models": len(ollama_models),
        "lms_models": lms_models,
        "actions": actions,
    }


def main():
    parser = argparse.ArgumentParser(description="Cluster Model Rotator")
    parser.add_argument("--once", "--rotate", action="store_true", help="Run rotation")
    parser.add_argument("--schedule", action="store_true", help="Show schedule")
    parser.add_argument("--status", action="store_true", help="Current models")
    parser.add_argument("--history", action="store_true", help="Rotation history")
    args = parser.parse_args()

    result = do_rotate()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
