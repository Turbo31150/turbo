#!/usr/bin/env python3
"""jarvis_preloader.py — Intelligent model preloading (#247).

Analyzes usage patterns by hour, preloads models via curl to
LM Studio (127.0.0.1:1234) and Ollama (127.0.0.1:11434) before peak hours.

Usage:
    python dev/jarvis_preloader.py --once
    python dev/jarvis_preloader.py --status
    python dev/jarvis_preloader.py --preload
    python dev/jarvis_preloader.py --schedule
    python dev/jarvis_preloader.py --stats
"""
import argparse
import json
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "preloader.db"

LM_STUDIO_URL = "http://127.0.0.1:1234"
OLLAMA_URL = "http://127.0.0.1:11434"

# Default model profiles by hour ranges
DEFAULT_SCHEDULE = {
    "morning": {"hours": list(range(7, 12)), "models": ["qwen3-8b"], "provider": "lmstudio"},
    "afternoon": {"hours": list(range(12, 18)), "models": ["qwen3:1.7b", "qwen3:14b"], "provider": "ollama"},
    "evening": {"hours": list(range(18, 23)), "models": ["qwen3-8b"], "provider": "lmstudio"},
    "night": {"hours": list(range(0, 7)) + [23], "models": [], "provider": "none"},
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS usage_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        hour INTEGER NOT NULL,
        weekday INTEGER NOT NULL,
        model TEXT NOT NULL,
        provider TEXT NOT NULL,
        request_count INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS preload_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        model TEXT NOT NULL,
        provider TEXT NOT NULL,
        success INTEGER,
        latency_ms REAL,
        reason TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_name TEXT UNIQUE NOT NULL,
        hours TEXT NOT NULL,
        models TEXT NOT NULL,
        provider TEXT NOT NULL,
        active INTEGER DEFAULT 1
    )""")
    db.commit()
    return db


def check_lmstudio():
    """Check LM Studio availability."""
    try:
        out = subprocess.check_output(
            ["curl", "-s", "--max-time", "3", f"{LM_STUDIO_URL}/api/v1/models"],
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        data = json.loads(out)
        models = data.get("data", data.get("models", []))
        loaded = [m for m in models if m.get("loaded_instances")]
        return {"online": True, "total": len(models), "loaded": len(loaded),
                "loaded_models": [m.get("id", "?") for m in loaded]}
    except Exception:
        return {"online": False}


def check_ollama():
    """Check Ollama availability."""
    try:
        out = subprocess.check_output(
            ["curl", "-s", "--max-time", "3", f"{OLLAMA_URL}/api/tags"],
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        data = json.loads(out)
        models = data.get("models", [])
        return {"online": True, "models": len(models),
                "model_names": [m.get("name", "?") for m in models[:10]]}
    except Exception:
        return {"online": False}


def preload_ollama_model(model_name):
    """Preload an Ollama model by sending a dummy request."""
    start = time.time()
    try:
        body = json.dumps({
            "model": model_name,
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
        })
        out = subprocess.check_output(
            ["curl", "-s", "--max-time", "60", f"{OLLAMA_URL}/api/chat",
             "-d", body],
            stderr=subprocess.DEVNULL, text=True, timeout=65,
        )
        latency = (time.time() - start) * 1000
        return True, latency
    except Exception as e:
        latency = (time.time() - start) * 1000
        return False, latency


def preload_lmstudio_model(model_name):
    """Preload a LM Studio model via a small request."""
    start = time.time()
    try:
        body = json.dumps({
            "model": model_name,
            "input": "/nothink\nping",
            "temperature": 0.1,
            "max_output_tokens": 10,
            "stream": False,
            "store": False,
        })
        out = subprocess.check_output(
            ["curl", "-s", "--max-time", "60",
             f"{LM_STUDIO_URL}/api/v1/chat",
             "-H", "Content-Type: application/json",
             "-d", body],
            stderr=subprocess.DEVNULL, text=True, timeout=65,
        )
        latency = (time.time() - start) * 1000
        return True, latency
    except Exception:
        latency = (time.time() - start) * 1000
        return False, latency


def do_preload():
    """Preload models based on current hour schedule."""
    db = init_db()
    now = datetime.now()
    hour = now.hour
    preloaded = []

    # Find matching schedule
    for profile, config in DEFAULT_SCHEDULE.items():
        if hour in config["hours"]:
            for model in config["models"]:
                provider = config["provider"]
                reason = f"scheduled_{profile}_h{hour}"

                if provider == "ollama":
                    success, latency = preload_ollama_model(model)
                elif provider == "lmstudio":
                    success, latency = preload_lmstudio_model(model)
                else:
                    continue

                db.execute(
                    "INSERT INTO preload_log (ts, model, provider, success, latency_ms, reason) VALUES (?,?,?,?,?,?)",
                    (now.isoformat(), model, provider, int(success), round(latency, 1), reason),
                )
                preloaded.append({
                    "model": model, "provider": provider,
                    "success": success, "latency_ms": round(latency, 1),
                })
            break

    db.commit()
    result = {
        "ts": now.isoformat(),
        "action": "preload",
        "hour": hour,
        "preloaded": preloaded,
        "count": len(preloaded),
    }
    db.close()
    return result


def do_schedule():
    """Show preloading schedule."""
    db = init_db()
    # Check for custom schedules
    custom = db.execute("SELECT profile_name, hours, models, provider, active FROM schedules").fetchall()

    schedule = {}
    if custom:
        for row in custom:
            schedule[row[0]] = {
                "hours": json.loads(row[1]),
                "models": json.loads(row[2]),
                "provider": row[3],
                "active": bool(row[4]),
            }
    else:
        schedule = DEFAULT_SCHEDULE

    now = datetime.now()
    current_profile = None
    for name, config in schedule.items():
        if now.hour in config.get("hours", []):
            current_profile = name
            break

    result = {
        "ts": now.isoformat(),
        "action": "schedule",
        "current_hour": now.hour,
        "current_profile": current_profile,
        "schedules": schedule,
    }
    db.close()
    return result


def do_stats():
    """Show preloading statistics."""
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM preload_log").fetchone()[0]
    success = db.execute("SELECT COUNT(*) FROM preload_log WHERE success=1").fetchone()[0]
    avg_latency = db.execute("SELECT AVG(latency_ms) FROM preload_log WHERE success=1").fetchone()[0]
    by_model = db.execute(
        "SELECT model, COUNT(*), AVG(latency_ms) FROM preload_log GROUP BY model ORDER BY COUNT(*) DESC"
    ).fetchall()
    recent = db.execute(
        "SELECT ts, model, provider, success, latency_ms FROM preload_log ORDER BY id DESC LIMIT 10"
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "stats",
        "total_preloads": total,
        "successful": success,
        "success_rate": round(success / max(total, 1), 3),
        "avg_latency_ms": round(avg_latency or 0, 1),
        "by_model": [{"model": r[0], "count": r[1], "avg_ms": round(r[2] or 0, 1)} for r in by_model],
        "recent": [
            {"ts": r[0], "model": r[1], "provider": r[2], "success": bool(r[3]), "latency_ms": r[4]}
            for r in recent
        ],
    }
    db.close()
    return result


def do_status():
    """Overall preloader status with node checks."""
    db = init_db()
    lm = check_lmstudio()
    ol = check_ollama()

    result = {
        "ts": datetime.now().isoformat(),
        "script": "jarvis_preloader.py",
        "script_id": 247,
        "db": str(DB_PATH),
        "lmstudio": lm,
        "ollama": ol,
        "total_preloads": db.execute("SELECT COUNT(*) FROM preload_log").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="jarvis_preloader.py — Intelligent model preloading (#247)")
    parser.add_argument("--status", action="store_true", help="Show preloader status")
    parser.add_argument("--preload", action="store_true", help="Preload models for current hour")
    parser.add_argument("--schedule", action="store_true", help="Show preloading schedule")
    parser.add_argument("--stats", action="store_true", help="Show preloading statistics")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.preload:
        result = do_preload()
    elif args.schedule:
        result = do_schedule()
    elif args.stats:
        result = do_stats()
    elif args.status:
        result = do_status()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
