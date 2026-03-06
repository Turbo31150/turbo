#!/usr/bin/env python3
"""jarvis_self_improve.py — Meta-agent d'auto-amelioration JARVIS.

Lance improve_loop.py, analyse les resultats, ajuste les seuils
AUTO_EXEC du proactive_agent, et compare les scores avant/apres.

Usage:
    python dev/jarvis_self_improve.py --once
    python dev/jarvis_self_improve.py --cycle
    python dev/jarvis_self_improve.py --report
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
from _paths import TURBO_DIR as TURBO
DB_PATH = DEV / "data" / "self_improve.db"
WS_URL = "http://127.0.0.1:9742"
IMPROVE_LOOP = TURBO / "canvas" / "improve_loop.py"
PROACTIVE_AGENT = TURBO / "src" / "proactive_agent.py"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS cycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, score_before REAL, score_after REAL,
        improvements TEXT, threshold_adjustments TEXT, report TEXT)""")
    db.commit()
    return db


def get_current_scores():
    """Get current system scores from various endpoints."""
    scores = {}

    # Autonomous loop
    try:
        req = urllib.request.Request(f"{WS_URL}/api/autonomous/status")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            tasks = data.get("tasks", {})
            if tasks:
                ok = sum(1 for t in tasks.values()
                         if isinstance(t, dict) and t.get("fail_count", 0) <= 3)
                scores["autonomous"] = round(ok / max(len(tasks), 1), 3)
    except Exception:
        scores["autonomous"] = 0

    # Prediction engine
    try:
        req = urllib.request.Request(f"{WS_URL}/api/predictions/stats")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            scores["prediction"] = data.get("accuracy", 0)
            scores["patterns"] = data.get("total_patterns", 0)
    except Exception:
        scores["prediction"] = 0

    # Proactive agent
    try:
        req = urllib.request.Request(f"{WS_URL}/api/proactive/stats")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            scores["proactive_exec"] = data.get("auto_executed", 0)
            scores["proactive_total"] = data.get("total_suggestions", 0)
    except Exception:
        pass

    # Calculate composite score
    auto = scores.get("autonomous", 0)
    pred = scores.get("prediction", 0)
    composite = (auto * 0.5 + pred * 0.3 + min(scores.get("patterns", 0) / 100, 1.0) * 0.2)
    scores["composite"] = round(composite, 3)

    return scores


def run_improve_loop(cycles=5):
    """Run improve_loop.py for N cycles."""
    if not IMPROVE_LOOP.exists():
        return {"error": "improve_loop.py not found"}

    try:
        result = subprocess.run(
            [sys.executable, str(IMPROVE_LOOP), "--cycles", str(cycles)],
            capture_output=True, text=True, timeout=300,
            cwd=str(TURBO)
        )
        output = result.stdout + result.stderr
        return {"success": result.returncode == 0, "output": output[:2000]}
    except subprocess.TimeoutExpired:
        return {"error": "timeout after 300s"}
    except Exception as e:
        return {"error": str(e)}


def analyze_threshold_adjustments(scores_before, scores_after):
    """Suggest threshold adjustments based on score changes."""
    adjustments = {}

    composite_before = scores_before.get("composite", 0)
    composite_after = scores_after.get("composite", 0)
    delta = composite_after - composite_before

    # If prediction accuracy improved, we can be slightly more aggressive
    pred_before = scores_before.get("prediction", 0)
    pred_after = scores_after.get("prediction", 0)

    if pred_after > pred_before + 0.05:
        adjustments["maintenance"] = {"current": 0.8, "suggested": 0.75, "reason": "prediction improved"}
        adjustments["reporting"] = {"current": 0.7, "suggested": 0.65, "reason": "prediction improved"}

    # If autonomous loop is very stable, lower health threshold slightly
    auto_after = scores_after.get("autonomous", 0)
    if auto_after >= 0.9:
        adjustments["health"] = {"current": 0.9, "suggested": 0.85, "reason": "autonomous loop stable"}

    # If things degraded, be more conservative
    if delta < -0.05:
        adjustments["thermal"] = {"current": 0.95, "suggested": 0.98, "reason": "degradation detected"}
        adjustments["health"] = {"current": 0.9, "suggested": 0.95, "reason": "degradation detected"}

    return adjustments


def do_cycle():
    """Full improvement cycle."""
    db = init_db()

    # 1. Measure before
    scores_before = get_current_scores()

    # 2. Run improve_loop
    improve_result = run_improve_loop(cycles=5)

    # 3. Wait for effects to propagate
    time.sleep(10)

    # 4. Measure after
    scores_after = get_current_scores()

    # 5. Analyze and suggest threshold adjustments
    adjustments = analyze_threshold_adjustments(scores_before, scores_after)

    report = {
        "ts": datetime.now().isoformat(),
        "scores_before": scores_before,
        "scores_after": scores_after,
        "delta": round(scores_after.get("composite", 0) - scores_before.get("composite", 0), 4),
        "improve_loop": improve_result,
        "threshold_adjustments": adjustments,
    }

    db.execute(
        "INSERT INTO cycles (ts, score_before, score_after, improvements, threshold_adjustments, report) VALUES (?,?,?,?,?,?)",
        (time.time(), scores_before.get("composite", 0), scores_after.get("composite", 0),
         json.dumps(improve_result), json.dumps(adjustments), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def get_report():
    """Get improvement history."""
    db = init_db()
    rows = db.execute("SELECT ts, score_before, score_after, threshold_adjustments FROM cycles ORDER BY ts DESC LIMIT 10").fetchall()
    db.close()
    report = []
    for r in rows:
        report.append({
            "ts": datetime.fromtimestamp(r[0]).isoformat() if r[0] else None,
            "score_before": r[1],
            "score_after": r[2],
            "delta": round((r[2] or 0) - (r[1] or 0), 4),
            "adjustments": json.loads(r[3]) if r[3] else {},
        })
    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS Self-Improve — Meta-agent d'auto-amelioration")
    parser.add_argument("--once", "--cycle", action="store_true", help="Run improvement cycle")
    parser.add_argument("--report", action="store_true", help="Improvement history")
    args = parser.parse_args()

    if args.report:
        report = get_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        result = do_cycle()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
