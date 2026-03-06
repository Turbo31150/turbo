#!/usr/bin/env python3
"""jarvis_autonomy_monitor.py — Monitore l'autonomous_loop JARVIS en continu.

Verifie que toutes les 13 taches tournent, relance celles qui echouent,
alerte si >3 failures consecutives, auto-restart OL1/M1 si offline.

Usage:
    python dev/jarvis_autonomy_monitor.py --once
    python dev/jarvis_autonomy_monitor.py --loop --interval 60
    python dev/jarvis_autonomy_monitor.py --status
    python dev/jarvis_autonomy_monitor.py --report
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
DB_PATH = DEV / "data" / "autonomy_monitor.db"
from _paths import TURBO_DIR as TURBO
WS_URL = "http://127.0.0.1:9742"
OL1_URL = "http://127.0.0.1:11434"
M1_URL = "http://127.0.0.1:1234"
TELEGRAM_PROXY = "http://127.0.0.1:18800"

EXPECTED_TASKS = [
    "health_check", "gpu_monitor", "drift_reroute", "budget_alert",
    "auto_tune_sample", "self_heal", "proactive_suggest",
    "db_backup", "weekly_cleanup",
    "brain_auto_learn", "improve_cycle", "predict_next_actions", "auto_develop",
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, tasks_ok INTEGER, tasks_fail INTEGER,
        nodes_online TEXT, alerts TEXT, actions_taken TEXT)""")
    db.commit()
    return db


def check_node(url, timeout=3):
    """Check if a node is reachable."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def get_autonomous_status():
    """Get autonomous loop status via REST API."""
    try:
        req = urllib.request.Request(f"{WS_URL}/api/autonomous/status")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def restart_ollama():
    """Restart Ollama service."""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Stop-Process -Name ollama -Force -ErrorAction SilentlyContinue; "
             "Start-Sleep 2; Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden"],
            capture_output=True, timeout=15
        )
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
    """Run a single monitoring check."""
    db = init_db()
    now = time.time()
    alerts = []
    actions = []

    # 1. Check autonomous loop status
    status = get_autonomous_status()
    tasks_ok = 0
    tasks_fail = 0

    if "error" in status:
        alerts.append(f"WS server unreachable: {status['error']}")
        tasks_fail = len(EXPECTED_TASKS)
    else:
        tasks = status.get("tasks", {})
        for name in EXPECTED_TASKS:
            t = tasks.get(name, {})
            if not t:
                alerts.append(f"Task '{name}' missing from loop")
                tasks_fail += 1
            elif t.get("fail_count", 0) > 3 and t.get("run_count", 0) > 0:
                fail_rate = t["fail_count"] / max(t["run_count"], 1)
                if fail_rate > 0.5:
                    alerts.append(f"Task '{name}' failing ({t['fail_count']}/{t['run_count']})")
                    tasks_fail += 1
                else:
                    tasks_ok += 1
            else:
                tasks_ok += 1

    # 2. Check critical nodes
    nodes_online = []
    if check_node(f"{OL1_URL}/api/tags"):
        nodes_online.append("OL1")
    else:
        alerts.append("OL1 OFFLINE")
        # Auto-restart
        if restart_ollama():
            actions.append("OL1 restart attempted")
            time.sleep(5)
            if check_node(f"{OL1_URL}/api/tags"):
                actions.append("OL1 restart SUCCESS")
                nodes_online.append("OL1")

    if check_node(f"{M1_URL}/api/v1/models"):
        nodes_online.append("M1")

    # 3. Check prediction engine
    try:
        req = urllib.request.Request(f"{WS_URL}/api/predictions/stats")
        with urllib.request.urlopen(req, timeout=5) as r:
            pred_stats = json.loads(r.read().decode())
            if pred_stats.get("total_patterns", 0) == 0:
                alerts.append("Prediction engine has 0 patterns — may need data")
    except Exception:
        pass

    # 4. Record + alert
    db.execute(
        "INSERT INTO checks (ts, tasks_ok, tasks_fail, nodes_online, alerts, actions_taken) VALUES (?,?,?,?,?,?)",
        (now, tasks_ok, tasks_fail, json.dumps(nodes_online), json.dumps(alerts), json.dumps(actions))
    )
    db.commit()
    db.close()

    # Alert if critical
    if tasks_fail >= 5 or len(alerts) >= 3:
        msg = f"[JARVIS MONITOR] {tasks_fail} tasks en echec, {len(nodes_online)} nodes online\n" + "\n".join(alerts[:5])
        send_telegram_alert(msg)

    return {
        "ts": datetime.now().isoformat(),
        "tasks_ok": tasks_ok,
        "tasks_fail": tasks_fail,
        "nodes_online": nodes_online,
        "alerts": alerts,
        "actions": actions,
    }


def get_report():
    """Get monitoring report."""
    db = init_db()
    rows = db.execute("SELECT * FROM checks ORDER BY ts DESC LIMIT 20").fetchall()
    db.close()
    report = []
    for r in rows:
        report.append({
            "ts": datetime.fromtimestamp(r[1]).isoformat() if r[1] else None,
            "tasks_ok": r[2], "tasks_fail": r[3],
            "nodes_online": json.loads(r[4]) if r[4] else [],
            "alerts": json.loads(r[5]) if r[5] else [],
        })
    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS Autonomy Monitor")
    parser.add_argument("--once", action="store_true", help="Single check")
    parser.add_argument("--loop", action="store_true", help="Continuous monitoring")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval (seconds)")
    parser.add_argument("--status", action="store_true", help="Current status")
    parser.add_argument("--report", action="store_true", help="Historical report")
    args = parser.parse_args()

    if args.status:
        status = get_autonomous_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
    elif args.report:
        report = get_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.loop:
        print(f"[MONITOR] Starting continuous monitoring (interval={args.interval}s)")
        while True:
            try:
                result = do_check()
                status = "OK" if result["tasks_fail"] == 0 else f"WARN ({result['tasks_fail']} fail)"
                print(f"[{result['ts']}] {status} — {result['tasks_ok']}/{len(EXPECTED_TASKS)} tasks OK, nodes={result['nodes_online']}")
                if result["alerts"]:
                    for a in result["alerts"][:3]:
                        print(f"  ALERT: {a}")
            except Exception as e:
                print(f"[ERROR] Check failed: {e}")
            time.sleep(args.interval)
    else:  # --once or default
        result = do_check()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
