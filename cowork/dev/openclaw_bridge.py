#!/usr/bin/env python3
"""OpenClaw Bridge — Bridge MCP entre cowork et OpenClaw Gateway.

Connecte le système cowork aux 40 agents OpenClaw via WebSocket.
Routes: dispatch_task, get_status, list_agents.

Usage:
    python cowork/dev/openclaw_bridge.py --once     # Single check
    python cowork/dev/openclaw_bridge.py             # Continuous mode
"""

import asyncio
import argparse
import sqlite3
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent
DB_PATH = TURBO / "etoile.db"
GATEWAY_URI = "ws://127.0.0.1:18789"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BRIDGE] %(message)s")


def log_to_db(action, status, details=""):
    """Log bridge action to etoile.db."""
    try:
        db = sqlite3.connect(str(DB_PATH))
        db.execute("""INSERT OR IGNORE INTO cluster_health
            (timestamp, node, status, model, latency_ms)
            VALUES (?, ?, ?, ?, ?)""",
            (datetime.now().isoformat(), "openclaw_bridge", status, action, 0))
        db.commit()
        db.close()
    except Exception as e:
        logging.error(f"DB log failed: {e}")


def dispatch_task(task_name, task_data=None):
    """Dispatch a cowork task to OpenClaw via HTTP API."""
    import urllib.request
    payload = json.dumps({
        "type": "dispatch",
        "task": task_name,
        "data": task_data or {},
        "source": "cowork_bridge",
        "timestamp": datetime.now().isoformat()
    }).encode()
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:18789/api/dispatch",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        log_to_db(f"dispatch:{task_name}", "OK")
        return result
    except Exception as e:
        log_to_db(f"dispatch:{task_name}", "FAIL", str(e))
        return {"error": str(e)}


def get_status():
    """Get OpenClaw Gateway status."""
    import urllib.request
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:18789/api/status", timeout=5)
        data = json.loads(resp.read())
        log_to_db("status", "OK")
        return data
    except Exception as e:
        log_to_db("status", "FAIL", str(e))
        return {"error": str(e), "gateway": "offline"}


def list_agents():
    """List all OpenClaw agents."""
    import urllib.request
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:18789/api/agents", timeout=5)
        data = json.loads(resp.read())
        log_to_db("list_agents", "OK")
        return data
    except Exception as e:
        log_to_db("list_agents", "FAIL", str(e))
        return {"error": str(e), "agents": []}


def run_once():
    """Single execution: check gateway, list agents, report."""
    status = get_status()
    agents = list_agents()
    result = {
        "timestamp": datetime.now().isoformat(),
        "gateway": status,
        "agents_count": len(agents.get("agents", [])) if isinstance(agents, dict) else 0,
        "bridge": "operational"
    }
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description="OpenClaw Bridge for Cowork")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dispatch", type=str, help="Dispatch a task by name")
    parser.add_argument("--status", action="store_true", help="Get gateway status")
    parser.add_argument("--agents", action="store_true", help="List agents")
    args = parser.parse_args()

    if args.dispatch:
        result = dispatch_task(args.dispatch)
        print(json.dumps(result, indent=2))
    elif args.status:
        result = get_status()
        print(json.dumps(result, indent=2))
    elif args.agents:
        result = list_agents()
        print(json.dumps(result, indent=2))
    elif args.once:
        run_once()
    else:
        logging.info("Bridge continuous mode — checking every 60s")
        while True:
            run_once()
            import time
            time.sleep(60)


if __name__ == "__main__":
    main()
