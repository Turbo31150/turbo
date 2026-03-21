#!/usr/bin/env python3
"""Service watcher — Check Docker, LM Studio, Ollama, direct-proxy. Restart if down."""
import argparse
import json
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ETOILE_DB = Path("F:/BUREAU/turbo/etoile.db")
INTERVAL_SECONDS = 60

SERVICES = {
    "docker": {
        "check": "port", "host": "127.0.0.1", "port": 2375,
        "process": "Docker Desktop.exe",
        "restart_cmd": ["cmd", "/c", "start", "", "Docker Desktop"],
    },
    "lmstudio": {
        "check": "port", "host": "127.0.0.1", "port": 1234,
        "process": "LM Studio.exe",
        "restart_cmd": None,  # Manual restart required
    },
    "ollama": {
        "check": "port", "host": "127.0.0.1", "port": 11434,
        "process": "ollama.exe",
        "restart_cmd": ["ollama", "serve"],
    },
    "direct_proxy": {
        "check": "port", "host": "127.0.0.1", "port": 18800,
        "process": "node",
        "restart_cmd": ["node", "F:/BUREAU/turbo/direct-proxy.js"],
    },
}


def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a TCP port is listening."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def is_process_running(name: str) -> bool:
    """Check if a process is running via tasklist."""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        return name.lower() in r.stdout.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def restart_service(name: str, svc: dict) -> bool:
    """Attempt to restart a service."""
    cmd = svc.get("restart_cmd")
    if not cmd:
        return False
    try:
        subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x00000008,  # DETACHED_PROCESS
        )
        time.sleep(5)
        return check_port(svc["host"], svc["port"], timeout=5.0)
    except (FileNotFoundError, OSError):
        return False


def log_to_db(service: str, status: str, action: str) -> None:
    """Log service status to etoile.db."""
    if not ETOILE_DB.exists():
        return
    ts = datetime.now(timezone.utc).isoformat()
    try:
        conn = sqlite3.connect(str(ETOILE_DB), timeout=5)
        conn.execute(
            "INSERT INTO cluster_health (timestamp, node, status, model, latency_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, f"svc_{service}", status, action, 0),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"[WARN] DB error: {e}", file=sys.stderr)


def check_all(auto_restart: bool = True) -> dict:
    """Check all services, optionally restart if down."""
    results = {}
    for name, svc in SERVICES.items():
        up = check_port(svc["host"], svc["port"])
        action = "none"
        if not up and auto_restart:
            restarted = restart_service(name, svc)
            action = "restarted_ok" if restarted else "restart_failed"
            up = restarted
        status = "UP" if up else "DOWN"
        results[name] = {"status": status, "port": svc["port"], "action": action}
        if status == "DOWN" or action != "none":
            log_to_db(name, status, action)
    all_up = all(r["status"] == "UP" for r in results.values())
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": results,
        "status": "OK" if all_up else "DEGRADED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Service watcher with auto-restart")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--no-restart", action="store_true", help="Check only, no restart")
    args = parser.parse_args()
    while True:
        result = check_all(auto_restart=not args.no_restart)
        print(json.dumps(result, indent=2))
        if args.once:
            break
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
