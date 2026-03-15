#!/usr/bin/env python3
"""autonomous_health_guard.py — Guardian de sante globale JARVIS.

Combine orchestrator_v2 + autonomous_loop + prediction_engine pour un
score de sante composite. Relance les services tombes, escalade sur Telegram.

Usage:
    python dev/autonomous_health_guard.py --once
    python dev/autonomous_health_guard.py --loop --interval 120
    python dev/autonomous_health_guard.py --report
"""
import argparse
from _paths import ETOILE_DB, JARVIS_DB
import json
import os
import sqlite3
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "health_guard.db"
WS_URL = "http://127.0.0.1:9742"
OL1_URL = "http://127.0.0.1:11434"
M1_URL = "http://127.0.0.1:1234"
TELEGRAM_PROXY = "http://127.0.0.1:18800"

# Health components and their weights
COMPONENTS = {
    "ws_server": {"weight": 0.20, "url": f"{WS_URL}/api/automation/status"},
    "ol1": {"weight": 0.15, "url": f"{OL1_URL}/api/tags"},
    "m1": {"weight": 0.15, "url": f"{M1_URL}/api/v1/models"},
    "autonomous_loop": {"weight": 0.20, "url": f"{WS_URL}/api/autonomous/status"},
    "prediction_engine": {"weight": 0.10, "url": f"{WS_URL}/api/predictions/stats"},
    "event_bus": {"weight": 0.10, "url": f"{WS_URL}/api/eventbus/stats"},
    "databases": {"weight": 0.10, "check": "db"},
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, score REAL, grade TEXT,
        components TEXT, alerts TEXT, actions TEXT)""")
    db.commit()
    return db


def check_url(url, timeout=5):
    """Check if URL is reachable and returns 200."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status == 200:
                data = r.read().decode()
                try:
                    return {"ok": True, "data": json.loads(data)}
                except Exception:
                    return {"ok": True, "data": data[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "unknown"}


def check_databases():
    """Check integrity of critical databases."""
    dbs = {
        "etoile": Path(str(ETOILE_DB)),
        "jarvis": Path(str(JARVIS_DB)),
    }
    results = {}
    for name, path in dbs.items():
        if path.exists():
            try:
                conn = sqlite3.connect(str(path))
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                results[name] = {"ok": integrity == "ok", "size_mb": round(path.stat().st_size / 1048576, 2)}
                conn.close()
            except Exception as e:
                results[name] = {"ok": False, "error": str(e)}
        else:
            results[name] = {"ok": False, "error": "file_not_found"}
    all_ok = all(r.get("ok") for r in results.values())
    return {"ok": all_ok, "databases": results}


def restart_service(name):
    """Attempt to restart a failed service."""
    actions = {
        "ol1": ["bash", "-NoProfile", "-Command",
                 "Stop-Process -Name ollama -Force -ErrorAction SilentlyContinue; "
                 "Start-Sleep 2; Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden"],
    }
    cmd = actions.get(name)
    if not cmd:
        return False
    try:
        subprocess.run(cmd, capture_output=True, timeout=15)
        return True
    except Exception:
        return False


def send_telegram_alert(message):
    """Send alert via Telegram proxy."""
    try:
        data = json.dumps({"text": message}).encode()
        req = urllib.request.Request(
            f"{TELEGRAM_PROXY}/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def do_check():
    """Run comprehensive health check."""
    db = init_db()
    now = time.time()
    alerts = []
    actions = []
    component_results = {}
    total_score = 0.0

    for name, cfg in COMPONENTS.items():
        if cfg.get("check") == "db":
            result = check_databases()
            component_results[name] = result
            if result["ok"]:
                total_score += cfg["weight"]
            else:
                alerts.append(f"DB integrity issue: {result}")
            continue

        url = cfg.get("url", "")
        result = check_url(url)
        component_results[name] = {"ok": result["ok"]}

        if result["ok"]:
            total_score += cfg["weight"]

            # Extra checks for autonomous_loop
            if name == "autonomous_loop" and isinstance(result.get("data"), dict):
                tasks = result["data"].get("tasks", {})
                if tasks:
                    failing = sum(1 for t in tasks.values()
                                  if isinstance(t, dict) and t.get("fail_count", 0) > 3)
                    if failing > 3:
                        alerts.append(f"autonomous_loop: {failing} tasks failing")
                        total_score -= cfg["weight"] * 0.3

            # Extra check for prediction_engine
            if name == "prediction_engine" and isinstance(result.get("data"), dict):
                patterns = result["data"].get("total_patterns", 0)
                if patterns == 0:
                    alerts.append("prediction_engine: 0 patterns — needs training")
        else:
            alerts.append(f"{name} DOWN: {result.get('error', 'unreachable')}")

            # Auto-restart OL1
            if name == "ol1":
                if restart_service("ol1"):
                    actions.append("OL1 restart attempted")
                    time.sleep(5)
                    recheck = check_url(url)
                    if recheck["ok"]:
                        actions.append("OL1 restart SUCCESS")
                        total_score += cfg["weight"]
                        component_results[name]["ok"] = True

    # Calculate grade
    score = round(total_score * 100, 1)
    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    # Store result
    db.execute(
        "INSERT INTO checks (ts, score, grade, components, alerts, actions) VALUES (?,?,?,?,?,?)",
        (now, score, grade, json.dumps(component_results),
         json.dumps(alerts), json.dumps(actions))
    )
    db.commit()
    db.close()

    # Alert if critical
    if grade in ("D", "F") or len(alerts) >= 4:
        msg = f"[HEALTH GUARD] Score: {score}/100 Grade: {grade}\n" + "\n".join(alerts[:5])
        send_telegram_alert(msg)

    return {
        "ts": datetime.now().isoformat(),
        "score": score,
        "grade": grade,
        "components": component_results,
        "alerts": alerts,
        "actions": actions,
    }


def get_report():
    """Get health history."""
    db = init_db()
    rows = db.execute("SELECT ts, score, grade, alerts FROM checks ORDER BY ts DESC LIMIT 20").fetchall()
    db.close()
    report = []
    for r in rows:
        report.append({
            "ts": datetime.fromtimestamp(r[0]).isoformat() if r[0] else None,
            "score": r[1], "grade": r[2],
            "alerts": json.loads(r[3]) if r[3] else [],
        })
    return report


def main():
    parser = argparse.ArgumentParser(description="Autonomous Health Guard — Global JARVIS health")
    parser.add_argument("--once", action="store_true", help="Single health check")
    parser.add_argument("--loop", action="store_true", help="Continuous monitoring")
    parser.add_argument("--interval", type=int, default=120, help="Loop interval (seconds)")
    parser.add_argument("--report", action="store_true", help="Health history")
    args = parser.parse_args()

    if args.report:
        report = get_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.loop:
        print(f"[HEALTH_GUARD] Starting continuous monitoring (interval={args.interval}s)")
        while True:
            try:
                result = do_check()
                print(f"[{result['ts']}] Score: {result['score']}/100 Grade: {result['grade']} — {len(result['alerts'])} alerts")
                if result["alerts"]:
                    for a in result["alerts"][:3]:
                        print(f"  ALERT: {a}")
            except Exception as e:
                print(f"[ERROR] Check failed: {e}")
            time.sleep(args.interval)
    else:
        result = do_check()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()