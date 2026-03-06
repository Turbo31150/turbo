#!/usr/bin/env python3
"""proactive_alert_monitor.py — Proactive monitoring with Telegram alerts.

Runs periodic checks and sends Telegram alerts when:
- A cluster node goes offline
- Dispatch success rate drops below threshold
- Quality score degrades significantly
- New error patterns emerge
- GPU temperature exceeds threshold

CLI:
    --once       : single check + alert if needed
    --continuous : run every 5 minutes
    --stats      : show alert history

Stdlib-only (sqlite3, json, argparse, urllib).
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB
PYTHON = sys.executable

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"

# Thresholds
SUCCESS_RATE_MIN = 70.0
QUALITY_MIN = 0.6
LATENCY_MAX_MS = 45000
CHECK_INTERVAL_S = 300  # 5 minutes


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS proactive_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        message TEXT NOT NULL,
        sent_telegram INTEGER DEFAULT 0
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def send_alert(text, severity="warning"):
    """Send alert to Telegram."""
    icon = {"critical": "🔴", "warning": "🟡", "info": "🟢"}.get(severity, "⚪")
    msg = f"{icon} *COWORK Alert*\n{text}"

    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
    }).encode()

    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def check_cluster_health():
    """Check cluster nodes."""
    alerts = []
    try:
        r = subprocess.run(
            [PYTHON, str(SCRIPT_DIR / "cluster_health_watchdog.py"), "--once"],
            capture_output=True, text=True, timeout=30, cwd=str(SCRIPT_DIR)
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            for node in data.get("nodes", []):
                if node["status"] == "offline":
                    alerts.append({
                        "type": "node_offline",
                        "severity": "critical",
                        "message": f"Noeud {node['node']} OFFLINE"
                    })
                elif node["status"] == "degraded":
                    alerts.append({
                        "type": "node_degraded",
                        "severity": "warning",
                        "message": f"Noeud {node['node']} degrade ({node['response_ms']}ms)"
                    })
    except Exception as e:
        alerts.append({
            "type": "health_check_failed",
            "severity": "warning",
            "message": f"Health check echoue: {str(e)[:100]}"
        })
    return alerts


def check_dispatch_performance():
    """Check recent dispatch performance."""
    alerts = []
    if not ETOILE_DB.exists():
        return alerts

    try:
        edb = sqlite3.connect(str(ETOILE_DB))

        # Recent success rate (last 100 dispatches)
        row = edb.execute("""
            SELECT AVG(CASE WHEN success=1 THEN 100.0 ELSE 0.0 END) as rate,
                   AVG(latency_ms) as avg_lat,
                   AVG(quality_score) as avg_q
            FROM (SELECT * FROM agent_dispatch_log ORDER BY id DESC LIMIT 100)
        """).fetchone()

        rate = row[0] or 0
        avg_lat = row[1] or 0
        avg_q = row[2] or 0

        if rate < SUCCESS_RATE_MIN:
            alerts.append({
                "type": "low_success_rate",
                "severity": "critical",
                "message": f"Success rate recente: {rate:.1f}% (seuil: {SUCCESS_RATE_MIN}%)"
            })

        if avg_q < QUALITY_MIN:
            alerts.append({
                "type": "low_quality",
                "severity": "warning",
                "message": f"Qualite moyenne recente: {avg_q:.2f} (seuil: {QUALITY_MIN})"
            })

        if avg_lat > LATENCY_MAX_MS:
            alerts.append({
                "type": "high_latency",
                "severity": "warning",
                "message": f"Latence moyenne: {avg_lat:.0f}ms (seuil: {LATENCY_MAX_MS}ms)"
            })

        # Error spike detection (last 50 vs previous 50)
        recent_fails = edb.execute("""
            SELECT COUNT(*) FROM (SELECT * FROM agent_dispatch_log ORDER BY id DESC LIMIT 50)
            WHERE success = 0
        """).fetchone()[0]

        older_fails = edb.execute("""
            SELECT COUNT(*) FROM (SELECT * FROM agent_dispatch_log ORDER BY id DESC LIMIT 100 OFFSET 50)
            WHERE success = 0
        """).fetchone()[0]

        if recent_fails > older_fails * 2 and recent_fails > 5:
            alerts.append({
                "type": "error_spike",
                "severity": "critical",
                "message": f"Pic d'erreurs: {recent_fails} recents vs {older_fails} precedents"
            })

        edb.close()
    except Exception as e:
        alerts.append({
            "type": "db_check_failed",
            "severity": "warning",
            "message": f"Check DB echoue: {str(e)[:100]}"
        })

    return alerts


def check_gpu_thermal():
    """Check GPU temperatures via nvidia-smi."""
    alerts = []
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            for line in r.stdout.strip().split("\n"):
                parts = line.split(",")
                if len(parts) >= 2:
                    name = parts[0].strip()
                    temp = int(parts[1].strip())
                    if temp >= 85:
                        alerts.append({
                            "type": "gpu_critical_temp",
                            "severity": "critical",
                            "message": f"GPU {name}: {temp}C (critique!)"
                        })
                    elif temp >= 75:
                        alerts.append({
                            "type": "gpu_high_temp",
                            "severity": "warning",
                            "message": f"GPU {name}: {temp}C (chaud)"
                        })
    except FileNotFoundError:
        pass  # nvidia-smi not available
    except Exception:
        pass
    return alerts


def run_checks():
    """Run all proactive checks."""
    conn = get_db()
    ts = datetime.now().isoformat()
    all_alerts = []

    # Run all checks
    all_alerts.extend(check_cluster_health())
    all_alerts.extend(check_dispatch_performance())
    all_alerts.extend(check_gpu_thermal())

    # Record and send
    sent_count = 0
    for alert in all_alerts:
        sent = send_alert(alert["message"], alert["severity"])
        conn.execute("""
            INSERT INTO proactive_alerts
            (timestamp, alert_type, severity, message, sent_telegram)
            VALUES (?, ?, ?, ?, ?)
        """, (ts, alert["type"], alert["severity"], alert["message"], int(sent)))
        if sent:
            sent_count += 1

    conn.commit()
    conn.close()

    return {
        "timestamp": ts,
        "checks_run": 3,
        "alerts_generated": len(all_alerts),
        "alerts_sent": sent_count,
        "alerts": all_alerts,
        "status": "critical" if any(a["severity"] == "critical" for a in all_alerts) else
                  "warning" if all_alerts else "ok",
    }


def action_continuous():
    """Run checks periodically."""
    print(f"Starting proactive monitoring (every {CHECK_INTERVAL_S}s)...")
    while True:
        result = run_checks()
        status = result["status"]
        alerts = result["alerts_generated"]
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Status: {status} | Alerts: {alerts}")
        time.sleep(CHECK_INTERVAL_S)


def main():
    parser = argparse.ArgumentParser(description="Proactive Alert Monitor")
    parser.add_argument("--once", action="store_true", help="Single check")
    parser.add_argument("--continuous", action="store_true", help="Run periodically")
    parser.add_argument("--stats", action="store_true", help="Alert history")
    args = parser.parse_args()

    if not any([args.once, args.continuous, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.continuous:
        action_continuous()
    elif args.stats:
        conn = get_db()
        rows = conn.execute("""
            SELECT alert_type, severity, COUNT(*) as cnt
            FROM proactive_alerts
            GROUP BY alert_type, severity
            ORDER BY cnt DESC
        """).fetchall()
        conn.close()
        result = {"alert_types": [dict(r) for r in rows]}
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        result = run_checks()
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
