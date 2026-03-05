#!/usr/bin/env python3
"""pipeline_orchestrator.py — Orchestrateur de pipelines multi-etapes.

Execute des pipelines complexes avec etapes conditionnelles,
parallelisme, retry, et reporting.

Usage:
    python dev/pipeline_orchestrator.py --run "pipeline_name"
    python dev/pipeline_orchestrator.py --list
    python dev/pipeline_orchestrator.py --create "name" --steps "cmd1;cmd2;cmd3"
    python dev/pipeline_orchestrator.py --status
    python dev/pipeline_orchestrator.py --history
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "pipelines.db"

# ---------------------------------------------------------------------------
# Built-in pipelines
# ---------------------------------------------------------------------------
BUILTIN_PIPELINES = {
    "morning_check": {
        "description": "Check matinal complet",
        "steps": [
            {"name": "cluster_health", "cmd": "python dev/api_monitor.py --once", "timeout": 30, "required": True},
            {"name": "gpu_check", "cmd": "nvidia-smi --query-gpu=name,temperature.gpu,memory.used --format=csv,noheader", "timeout": 10},
            {"name": "disk_check", "cmd": "python -c \"import shutil;u=shutil.disk_usage('C:/');print(f'{u.free//1024**3}GB free')\"", "timeout": 5},
            {"name": "email_check", "cmd": "python dev/email_reader.py --unread", "timeout": 30},
            {"name": "predictions", "cmd": "python dev/interaction_predictor.py --predict", "timeout": 10},
        ],
    },
    "dev_cycle": {
        "description": "Cycle de developpement complet",
        "steps": [
            {"name": "code_review", "cmd": "python dev/self_feeding_engine.py --review", "timeout": 60},
            {"name": "generate", "cmd": "python dev/continuous_coder.py --once --max 1", "timeout": 180},
            {"name": "self_feed", "cmd": "python dev/self_feeding_engine.py --feed", "timeout": 120},
        ],
    },
    "trading_scan": {
        "description": "Pipeline trading complet",
        "steps": [
            {"name": "signals", "cmd": "python dev/telegram_commander.py --cmd trading", "timeout": 30},
            {"name": "log", "cmd": "python dev/interaction_predictor.py --log \"trading_scan\"", "timeout": 5},
        ],
    },
    "full_diagnostic": {
        "description": "Diagnostic systeme complet",
        "steps": [
            {"name": "api_monitor", "cmd": "python dev/api_monitor.py --once", "timeout": 30},
            {"name": "gpu", "cmd": "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used --format=csv,noheader", "timeout": 10},
            {"name": "disk_c", "cmd": "python -c \"import shutil;u=shutil.disk_usage('C:/');print(f'C: {u.free//1024**3}GB/{u.total//1024**3}GB')\"", "timeout": 5},
            {"name": "disk_f", "cmd": "python -c \"import shutil;u=shutil.disk_usage('F:/');print(f'F: {u.free//1024**3}GB/{u.total//1024**3}GB')\"", "timeout": 5},
            {"name": "dev_status", "cmd": "python dev/continuous_coder.py --status", "timeout": 10},
        ],
    },
    "cleanup": {
        "description": "Nettoyage systeme",
        "steps": [
            {"name": "organize_desktop", "cmd": "python dev/desktop_organizer.py --organize", "timeout": 30},
            {"name": "organize_downloads", "cmd": "python dev/desktop_organizer.py --downloads", "timeout": 30},
        ],
    },
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS pipeline_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, pipeline TEXT, steps_total INTEGER,
        steps_ok INTEGER, steps_failed INTEGER,
        duration_s REAL, status TEXT, details TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS custom_pipelines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, name TEXT UNIQUE, description TEXT, steps TEXT)""")
    db.commit()
    return db

def load_pipelines(db) -> dict:
    pipelines = dict(BUILTIN_PIPELINES)
    rows = db.execute("SELECT name, description, steps FROM custom_pipelines").fetchall()
    for name, desc, steps in rows:
        pipelines[name] = {"description": desc, "steps": json.loads(steps), "custom": True}
    return pipelines

# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
def run_pipeline(name: str, pipeline: dict, db) -> dict:
    start = time.time()
    steps_ok = 0
    steps_failed = 0
    details = []

    for step in pipeline["steps"]:
        step_start = time.time()
        timeout = step.get("timeout", 60)
        try:
            result = subprocess.run(
                step["cmd"], shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(DEV.parent),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
            ok = result.returncode == 0
            if ok:
                steps_ok += 1
            else:
                steps_failed += 1
                if step.get("required"):
                    details.append({"name": step["name"], "ok": False, "error": "required step failed", "aborted": True})
                    break
            details.append({
                "name": step["name"],
                "ok": ok,
                "duration_s": round(time.time() - step_start, 1),
                "output": (result.stdout.strip() or result.stderr.strip())[:300],
            })
        except subprocess.TimeoutExpired:
            steps_failed += 1
            details.append({"name": step["name"], "ok": False, "error": "timeout"})
        except Exception as e:
            steps_failed += 1
            details.append({"name": step["name"], "ok": False, "error": str(e)[:100]})

    duration = time.time() - start
    status = "success" if steps_failed == 0 else "partial" if steps_ok > 0 else "failed"

    db.execute(
        "INSERT INTO pipeline_runs (ts, pipeline, steps_total, steps_ok, steps_failed, duration_s, status, details) VALUES (?,?,?,?,?,?,?,?)",
        (time.time(), name, len(pipeline["steps"]), steps_ok, steps_failed, round(duration, 1), status, json.dumps(details))
    )
    db.commit()

    return {
        "pipeline": name,
        "description": pipeline.get("description", ""),
        "status": status,
        "steps_total": len(pipeline["steps"]),
        "steps_ok": steps_ok,
        "steps_failed": steps_failed,
        "duration_s": round(duration, 1),
        "details": details,
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Pipeline Orchestrator")
    parser.add_argument("--run", type=str, help="Executer un pipeline")
    parser.add_argument("--list", action="store_true", help="Lister les pipelines")
    parser.add_argument("--create", type=str, help="Creer un pipeline")
    parser.add_argument("--steps", type=str, help="Etapes (separees par ;)")
    parser.add_argument("--status", action="store_true", help="Statut")
    parser.add_argument("--history", action="store_true", help="Historique")
    args = parser.parse_args()

    db = init_db()
    pipelines = load_pipelines(db)

    if args.list:
        output = [{"name": n, "description": p["description"], "steps": len(p["steps"]),
                    "custom": p.get("custom", False)} for n, p in pipelines.items()]
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif args.run:
        if args.run not in pipelines:
            print(json.dumps({"error": f"Pipeline '{args.run}' inconnu", "available": list(pipelines.keys())}))
            sys.exit(1)
        result = run_pipeline(args.run, pipelines[args.run], db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.create and args.steps:
        steps = [{"name": f"step_{i+1}", "cmd": cmd.strip(), "timeout": 60}
                 for i, cmd in enumerate(args.steps.split(";")) if cmd.strip()]
        db.execute("INSERT OR REPLACE INTO custom_pipelines (ts, name, description, steps) VALUES (?,?,?,?)",
                   (time.time(), args.create, args.create, json.dumps(steps)))
        db.commit()
        print(json.dumps({"created": args.create, "steps": len(steps)}))
    elif args.status:
        runs = db.execute("SELECT COUNT(*), SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) FROM pipeline_runs").fetchone()
        last = db.execute("SELECT pipeline, status, duration_s, ts FROM pipeline_runs ORDER BY ts DESC LIMIT 5").fetchall()
        print(json.dumps({
            "total_runs": runs[0] or 0,
            "successes": runs[1] or 0,
            "pipelines": len(pipelines),
            "recent": [{"name": p, "status": s, "duration": d,
                        "when": datetime.fromtimestamp(t).strftime("%H:%M")} for p, s, d, t in last],
        }, indent=2, ensure_ascii=False))
    elif args.history:
        rows = db.execute("SELECT pipeline, status, steps_ok, steps_failed, duration_s, ts FROM pipeline_runs ORDER BY ts DESC LIMIT 20").fetchall()
        print(json.dumps([{"name": p, "status": s, "ok": o, "failed": f, "duration": d,
                            "when": datetime.fromtimestamp(t).isoformat()} for p, s, o, f, d, t in rows],
                         indent=2, ensure_ascii=False))
    else:
        parser.print_help()

    db.close()

if __name__ == "__main__":
    main()
