#!/usr/bin/env python3
"""openclaw_watchdog.py — Watchdog qui redemarre OpenClaw si il tombe.

Surveille le gateway OpenClaw (port 18789) en boucle.
Si le port ne repond plus → restart immediat via gateway.cmd.
Log tout dans SQLite.

Usage:
    python dev/openclaw_watchdog.py --loop           # Boucle continue (mode production)
    python dev/openclaw_watchdog.py --check           # Verification unique
    python dev/openclaw_watchdog.py --install         # Installer en tache planifiee Windows
    python dev/openclaw_watchdog.py --status          # Statut + historique
    python dev/openclaw_watchdog.py --uninstall       # Supprimer la tache planifiee
"""
import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GATEWAY_HOST = "127.0.0.1"
GATEWAY_PORT = 18789
GATEWAY_CMD = Path(os.path.expanduser("~")) / ".openclaw" / "gateway.cmd"
CHECK_INTERVAL = 15  # secondes entre chaque check
MAX_RESTART_PER_HOUR = 10  # securite anti-boucle
HEALTH_URL = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/health"
DB_PATH = Path(__file__).parent / "data" / "watchdog.db"
TASK_NAME = "OpenClaw Watchdog"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, alive INTEGER, latency_ms INTEGER,
        action TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS restarts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, reason TEXT, success INTEGER,
        duration_s REAL)""")
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
def check_gateway() -> dict:
    """Verifie si le gateway est accessible."""
    start = time.time()

    # Method 1: TCP socket check
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((GATEWAY_HOST, GATEWAY_PORT))
        sock.close()
        latency = int((time.time() - start) * 1000)
        if result == 0:
            return {"alive": True, "latency_ms": latency, "method": "tcp"}
    except Exception:
        pass

    # Method 2: HTTP health check
    try:
        import urllib.request
        req = urllib.request.Request(HEALTH_URL)
        with urllib.request.urlopen(req, timeout=5) as resp:
            latency = int((time.time() - start) * 1000)
            return {"alive": True, "latency_ms": latency, "method": "http"}
    except Exception:
        pass

    latency = int((time.time() - start) * 1000)
    return {"alive": False, "latency_ms": latency, "method": "failed"}

def is_gateway_process_running() -> bool:
    """Verifie si un processus gateway tourne via tasklist."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq node.exe"],
            capture_output=True, text=True, timeout=5
        )
        # Check if any node.exe has openclaw in its command line
        if "node.exe" in result.stdout:
            # More precise check via WMIC
            wmic = subprocess.run(
                ["wmic", "process", "where", "name='node.exe'", "get", "commandline"],
                capture_output=True, text=True, timeout=5
            )
            if "openclaw" in wmic.stdout.lower() or "gateway" in wmic.stdout.lower():
                return True
        return False
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Restart
# ---------------------------------------------------------------------------
def restart_gateway(db, reason: str = "watchdog") -> dict:
    """Redemarre le gateway OpenClaw."""
    start = time.time()

    # Anti-boucle: max restarts per hour
    one_hour_ago = time.time() - 3600
    recent = db.execute(
        "SELECT COUNT(*) FROM restarts WHERE ts > ?", (one_hour_ago,)
    ).fetchone()[0]

    if recent >= MAX_RESTART_PER_HOUR:
        return {
            "restarted": False,
            "reason": f"Securite: {recent} restarts dans la derniere heure (max={MAX_RESTART_PER_HOUR})",
        }

    success = False

    # Method 1: Scheduled Task restart (preferred)
    try:
        subprocess.run(
            ["schtasks", "/End", "/TN", "OpenClaw Gateway"],
            capture_output=True, timeout=10
        )
        time.sleep(2)
        result = subprocess.run(
            ["schtasks", "/Run", "/TN", "OpenClaw Gateway"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            # Wait for gateway to come up
            for _ in range(20):
                time.sleep(2)
                check = check_gateway()
                if check["alive"]:
                    success = True
                    break
    except Exception as e:
        pass

    # Method 2: Direct gateway.cmd if schtasks failed
    if not success and GATEWAY_CMD.exists():
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "/min", str(GATEWAY_CMD)],
                cwd=str(GATEWAY_CMD.parent),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            for _ in range(20):
                time.sleep(2)
                check = check_gateway()
                if check["alive"]:
                    success = True
                    break
        except Exception:
            pass

    duration = time.time() - start
    db.execute(
        "INSERT INTO restarts (ts, reason, success, duration_s) VALUES (?,?,?,?)",
        (time.time(), reason, int(success), round(duration, 1))
    )
    db.commit()

    return {
        "restarted": success,
        "reason": reason,
        "duration_s": round(duration, 1),
        "timestamp": datetime.now().isoformat(),
    }

# ---------------------------------------------------------------------------
# Watch loop
# ---------------------------------------------------------------------------
def watch_loop(db):
    """Boucle de surveillance continue."""
    consecutive_failures = 0
    print(f"[watchdog] Surveillance OpenClaw port {GATEWAY_PORT} (interval={CHECK_INTERVAL}s)")

    while True:
        try:
            check = check_gateway()

            if check["alive"]:
                consecutive_failures = 0
                action = "ok"
                db.execute(
                    "INSERT INTO checks (ts, alive, latency_ms, action) VALUES (?,1,?,?)",
                    (time.time(), check["latency_ms"], action)
                )
            else:
                consecutive_failures += 1

                if consecutive_failures >= 2:
                    # 2 echecs consecutifs → restart
                    print(f"[watchdog] Gateway DOWN ({consecutive_failures} echecs) → Restart...")
                    result = restart_gateway(db, f"down_{consecutive_failures}_checks")
                    action = "restarted" if result["restarted"] else "restart_failed"
                    print(f"[watchdog] Restart: {action} ({result.get('duration_s', 0)}s)")

                    if result["restarted"]:
                        consecutive_failures = 0
                else:
                    action = "warning"
                    print(f"[watchdog] Gateway pas de reponse (echec {consecutive_failures}/2)")

                db.execute(
                    "INSERT INTO checks (ts, alive, latency_ms, action) VALUES (?,0,?,?)",
                    (time.time(), check["latency_ms"], action)
                )

            db.commit()
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n[watchdog] Arrete.")
            break
        except Exception as e:
            print(f"[watchdog] Erreur: {e}")
            time.sleep(CHECK_INTERVAL)

# ---------------------------------------------------------------------------
# Windows Scheduled Task
# ---------------------------------------------------------------------------
def install_task() -> dict:
    """Installe le watchdog comme tache planifiee Windows."""
    python_exe = sys.executable
    script_path = Path(__file__).resolve()

    # Create a wrapper bat file
    bat_path = Path(os.path.expanduser("~")) / ".openclaw" / "watchdog.bat"
    bat_content = f'@echo off\ncd /d "{script_path.parent.parent}"\n"{python_exe}" "{script_path}" --loop\n'
    bat_path.write_text(bat_content)

    # Create scheduled task
    try:
        # Remove existing
        subprocess.run(
            ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
            capture_output=True, timeout=10
        )
    except Exception:
        pass

    result = subprocess.run(
        ["schtasks", "/Create",
         "/TN", TASK_NAME,
         "/TR", str(bat_path),
         "/SC", "ONLOGON",
         "/RL", "HIGHEST",
         "/F"],
        capture_output=True, text=True, timeout=10
    )

    success = result.returncode == 0

    if success:
        # Also start it now
        subprocess.run(
            ["schtasks", "/Run", "/TN", TASK_NAME],
            capture_output=True, timeout=10
        )

    return {
        "installed": success,
        "task_name": TASK_NAME,
        "bat_path": str(bat_path),
        "script": str(script_path),
        "output": result.stdout.strip() if result.stdout else result.stderr.strip(),
    }

def uninstall_task() -> dict:
    """Supprime la tache planifiee."""
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True, timeout=10
    )
    return {"removed": result.returncode == 0, "output": result.stdout.strip()}

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
def get_status(db) -> dict:
    """Statut complet du watchdog."""
    check = check_gateway()
    process_running = is_gateway_process_running()

    total_checks = db.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
    total_restarts = db.execute("SELECT COUNT(*) FROM restarts").fetchone()[0]
    recent_restarts = db.execute(
        "SELECT ts, reason, success, duration_s FROM restarts ORDER BY ts DESC LIMIT 5"
    ).fetchall()

    # Uptime estimation
    last_100 = db.execute(
        "SELECT alive FROM checks ORDER BY ts DESC LIMIT 100"
    ).fetchall()
    uptime_pct = sum(1 for r in last_100 if r[0]) / max(len(last_100), 1) * 100

    # Check if watchdog task is running
    try:
        task_result = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5
        )
        task_status = "running" if "Running" in task_result.stdout else "installed" if task_result.returncode == 0 else "not_installed"
    except Exception:
        task_status = "unknown"

    return {
        "gateway": {
            "alive": check["alive"],
            "latency_ms": check["latency_ms"],
            "process_running": process_running,
            "port": GATEWAY_PORT,
        },
        "watchdog": {
            "task_status": task_status,
            "total_checks": total_checks,
            "total_restarts": total_restarts,
            "uptime_pct": round(uptime_pct, 1),
            "check_interval_s": CHECK_INTERVAL,
            "max_restarts_hour": MAX_RESTART_PER_HOUR,
        },
        "recent_restarts": [
            {"when": datetime.fromtimestamp(ts).isoformat(), "reason": r, "success": bool(s), "duration_s": d}
            for ts, r, s, d in recent_restarts
        ],
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS OpenClaw Watchdog — Redemarre le gateway automatiquement")
    parser.add_argument("--loop", action="store_true", help="Boucle de surveillance continue")
    parser.add_argument("--check", action="store_true", help="Verification unique")
    parser.add_argument("--install", action="store_true", help="Installer en tache planifiee Windows")
    parser.add_argument("--uninstall", action="store_true", help="Supprimer la tache planifiee")
    parser.add_argument("--status", action="store_true", help="Statut complet")
    parser.add_argument("--restart", action="store_true", help="Forcer un restart")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL, help=f"Intervalle en secondes (default: {CHECK_INTERVAL})")
    args = parser.parse_args()

    db = init_db()

    if args.check:
        check = check_gateway()
        check["process_running"] = is_gateway_process_running()
        check["timestamp"] = datetime.now().isoformat()
        print(json.dumps(check, indent=2, ensure_ascii=False))
    elif args.install:
        result = install_task()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.uninstall:
        result = uninstall_task()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.status:
        result = get_status(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.restart:
        result = restart_gateway(db, "manual")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.loop:
        if args.interval != 15:
            # Override module-level interval
            import openclaw_watchdog
            openclaw_watchdog.CHECK_INTERVAL = args.interval
        watch_loop(db)
    else:
        # Default: check + status
        result = get_status(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    db.close()

if __name__ == "__main__":
    main()
