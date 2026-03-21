#!/usr/bin/env python3
"""MCP Health Monitor — Check all service ports and log to etoile.db.

Monitors: M1(1234), OL1(11434), OpenClaw(18789), Proxy(18800), WS(9742), Dispatcher(9800).

Usage:
    python cowork/dev/mcp_health_monitor.py --once
    python cowork/dev/mcp_health_monitor.py
"""

import argparse
import json
import socket
import sqlite3
import time
from datetime import datetime
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent
DB_PATH = TURBO / "etoile.db"

SERVICES = {
    "M1_LMStudio": ("127.0.0.1", 1234),
    "OL1_Ollama": ("127.0.0.1", 11434),
    "OpenClaw": ("127.0.0.1", 18789),
    "DirectProxy": ("127.0.0.1", 18800),
    "PythonWS": ("127.0.0.1", 9742),
    "CoworkDispatcher": ("127.0.0.1", 9800),
    "CoworkMCP": ("127.0.0.1", 9801),
    "n8n": ("127.0.0.1", 5678),
}


def check_port(host, port, timeout=2):
    """Check if a TCP port is open."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        start = time.time()
        s.connect((host, port))
        latency = int((time.time() - start) * 1000)
        s.close()
        return True, latency
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False, 0


def log_health(name, status, latency):
    """Log to etoile.db cluster_health."""
    try:
        db = sqlite3.connect(str(DB_PATH))
        db.execute(
            "INSERT INTO cluster_health (timestamp, node, status, model, latency_ms) VALUES (?,?,?,?,?)",
            (datetime.now().isoformat(), name, "OK" if status else "DOWN", "mcp_monitor", latency)
        )
        db.commit()
        db.close()
    except Exception:
        pass


def run_check():
    """Check all services and return results."""
    results = {}
    up = 0
    for name, (host, port) in SERVICES.items():
        ok, lat = check_port(host, port)
        results[name] = {"port": port, "status": "UP" if ok else "DOWN", "latency_ms": lat}
        log_health(name, ok, lat)
        if ok:
            up += 1

    output = {
        "timestamp": datetime.now().isoformat(),
        "services": results,
        "total": len(SERVICES),
        "up": up,
        "down": len(SERVICES) - up,
        "health_pct": round(up / len(SERVICES) * 100, 1)
    }
    print(json.dumps(output, indent=2))
    return output


def main():
    parser = argparse.ArgumentParser(description="MCP Health Monitor")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=60, help="Check interval (seconds)")
    args = parser.parse_args()

    if args.once:
        run_check()
    else:
        while True:
            run_check()
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
