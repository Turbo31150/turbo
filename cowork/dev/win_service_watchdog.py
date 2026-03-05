#!/usr/bin/env python3
"""win_service_watchdog.py (#195) — Service watchdog for critical services.

Monitors: LM Studio (1234), Ollama (11434), FastAPI (9742) via port check.
Tracks uptime/downtime. Reports health status.

Usage:
    python dev/win_service_watchdog.py --once
    python dev/win_service_watchdog.py --watch
    python dev/win_service_watchdog.py --critical
    python dev/win_service_watchdog.py --report
"""
import argparse
import json
import socket
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "service_watchdog.db"

# Critical services to monitor
CRITICAL_SERVICES = {
    "M1_LMStudio": {"host": "127.0.0.1", "port": 1234, "description": "M1 LM Studio (qwen3-8b)"},
    "M2_LMStudio": {"host": "192.168.1.26", "port": 1234, "description": "M2 LM Studio (deepseek-coder)"},
    "M3_LMStudio": {"host": "192.168.1.113", "port": 1234, "description": "M3 LM Studio (mistral-7b)"},
    "Ollama": {"host": "127.0.0.1", "port": 11434, "description": "Ollama (qwen3 + cloud models)"},
    "FastAPI_WS": {"host": "127.0.0.1", "port": 9742, "description": "FastAPI WebSocket backend"},
    "Electron_Dashboard": {"host": "127.0.0.1", "port": 8080, "description": "Electron dashboard"},
    "Webhook_Server": {"host": "127.0.0.1", "port": 9801, "description": "Webhook server"},
    "OpenClaw_Proxy": {"host": "127.0.0.1", "port": 18800, "description": "OpenClaw direct-proxy"},
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        service TEXT,
        host TEXT,
        port INTEGER,
        status TEXT,
        latency_ms REAL,
        error TEXT DEFAULT ''
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS service_state (
        service TEXT PRIMARY KEY,
        current_status TEXT DEFAULT 'unknown',
        last_check REAL,
        last_up REAL,
        last_down REAL,
        consecutive_fails INTEGER DEFAULT 0,
        total_checks INTEGER DEFAULT 0,
        total_up INTEGER DEFAULT 0,
        uptime_pct REAL DEFAULT 0
    )""")
    # Init service states
    for svc in CRITICAL_SERVICES:
        db.execute(
            "INSERT OR IGNORE INTO service_state (service, current_status) VALUES (?, 'unknown')",
            (svc,)
        )
    db.commit()
    return db


def check_port(host, port, timeout=3):
    """Check if a port is open. Returns (is_open, latency_ms, error)."""
    start = time.time()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        latency = (time.time() - start) * 1000
        s.close()
        if result == 0:
            return True, round(latency, 1), None
        else:
            return False, round(latency, 1), f"Connection refused (code {result})"
    except socket.timeout:
        return False, timeout * 1000, "Timeout"
    except Exception as e:
        return False, (time.time() - start) * 1000, str(e)


def watch_services(db):
    """Check all critical services."""
    now = time.time()
    results = []

    for svc_name, svc_info in CRITICAL_SERVICES.items():
        host = svc_info["host"]
        port = svc_info["port"]
        desc = svc_info["description"]

        is_up, latency, error = check_port(host, port)
        status = "up" if is_up else "down"

        # Log check
        db.execute(
            "INSERT INTO checks (ts, service, host, port, status, latency_ms, error) VALUES (?,?,?,?,?,?,?)",
            (now, svc_name, host, port, status, latency, error or "")
        )

        # Update service state
        db.execute("""
            UPDATE service_state SET
                current_status=?, last_check=?,
                consecutive_fails = CASE WHEN ?='down' THEN consecutive_fails+1 ELSE 0 END,
                total_checks = total_checks + 1,
                total_up = total_up + CASE WHEN ?='up' THEN 1 ELSE 0 END,
                last_up = CASE WHEN ?='up' THEN ? ELSE last_up END,
                last_down = CASE WHEN ?='down' THEN ? ELSE last_down END
            WHERE service=?
        """, (status, now, status, status, status, now, status, now, svc_name))

        # Calculate uptime percentage
        row = db.execute(
            "SELECT total_checks, total_up FROM service_state WHERE service=?", (svc_name,)
        ).fetchone()
        if row and row[0] > 0:
            uptime_pct = round(row[1] / row[0] * 100, 1)
            db.execute("UPDATE service_state SET uptime_pct=? WHERE service=?", (uptime_pct, svc_name))

        results.append({
            "service": svc_name,
            "description": desc,
            "host": host,
            "port": port,
            "status": status,
            "latency_ms": latency,
            "error": error
        })

    db.commit()

    up_count = sum(1 for r in results if r["status"] == "up")
    down_count = len(results) - up_count

    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "services_up": up_count,
        "services_down": down_count,
        "total": len(results),
        "health": "healthy" if down_count == 0 else "degraded" if down_count <= 2 else "critical",
        "services": results
    }


def get_critical(db):
    """Show only services that are down or degraded."""
    rows = db.execute(
        """SELECT service, current_status, consecutive_fails, last_down, uptime_pct
           FROM service_state WHERE current_status='down' OR consecutive_fails>0
           ORDER BY consecutive_fails DESC"""
    ).fetchall()

    critical = []
    for r in rows:
        svc_info = CRITICAL_SERVICES.get(r[0], {})
        critical.append({
            "service": r[0],
            "description": svc_info.get("description", ""),
            "status": r[1],
            "consecutive_fails": r[2],
            "last_down": datetime.fromtimestamp(r[3]).isoformat() if r[3] else "never",
            "uptime_pct": r[4]
        })

    if not critical:
        return {"status": "ok", "message": "All services healthy", "critical_count": 0}

    return {
        "status": "warning",
        "critical_count": len(critical),
        "services": critical
    }


def get_report(db):
    """Full service health report."""
    rows = db.execute(
        """SELECT service, current_status, last_check, total_checks, total_up, uptime_pct,
                  consecutive_fails, last_up, last_down
           FROM service_state ORDER BY uptime_pct ASC"""
    ).fetchall()

    report = []
    for r in rows:
        svc_info = CRITICAL_SERVICES.get(r[0], {})
        report.append({
            "service": r[0],
            "description": svc_info.get("description", ""),
            "status": r[1],
            "uptime_pct": r[5],
            "total_checks": r[3],
            "total_up": r[4],
            "consecutive_fails": r[6],
            "last_check": datetime.fromtimestamp(r[2]).isoformat() if r[2] else "never",
            "last_up": datetime.fromtimestamp(r[7]).isoformat() if r[7] else "never",
            "last_down": datetime.fromtimestamp(r[8]).isoformat() if r[8] else "never"
        })

    total_checks = db.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
    overall_uptime = db.execute("SELECT COALESCE(AVG(uptime_pct), 0) FROM service_state").fetchone()[0]

    return {
        "status": "ok",
        "overall_uptime_pct": round(overall_uptime, 1),
        "total_check_entries": total_checks,
        "services": report
    }


def once(db):
    """Run once: check all services and report."""
    watch_result = watch_services(db)
    report = get_report(db)

    return {
        "status": "ok", "mode": "once",
        "check": watch_result,
        "report_summary": {
            "overall_uptime": report["overall_uptime_pct"],
            "total_checks": report["total_check_entries"]
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Service Watchdog (#195) — Critical service monitoring")
    parser.add_argument("--watch", action="store_true", help="Check all services now")
    parser.add_argument("--critical", action="store_true", help="Show only critical/down services")
    parser.add_argument("--report", action="store_true", help="Full health report")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    db = init_db()

    if args.watch:
        result = watch_services(db)
    elif args.critical:
        result = get_critical(db)
    elif args.report:
        result = get_report(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))
    db.close()


if __name__ == "__main__":
    main()
