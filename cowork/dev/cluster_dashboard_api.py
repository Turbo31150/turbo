#!/usr/bin/env python3
"""cluster_dashboard_api.py

Simple REST API (http.server) listening on port 8085 for the JARVIS Electron dashboard.
Endpoints (all return JSON):
    GET /api/status   – basic cluster information (static placeholder).
    GET /api/trading  – latest trading signals (read from ``trading_latest.db`` if present).
    GET /api/metrics  – CPU, RAM and GPU utilisation.
    GET /api/cron     – current cron jobs status (via the OpenClaw ``cron`` tool).

The implementation deliberately uses only the Python standard library and optional
``psutil`` (fallback to PowerShell if unavailable).  Errors are reported as JSON
objects with an ``error`` key so the front-end can handle them gracefully.
"""

import json
import os
import subprocess
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Helper: safe JSON response
# ---------------------------------------------------------------------------

def json_response(handler: BaseHTTPRequestHandler, data, status=HTTPStatus.OK):
    payload = json.dumps(data).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)

# ---------------------------------------------------------------------------
# Endpoint implementations
# ---------------------------------------------------------------------------

def get_status():
    """Return a static description of the cluster.
    In a real deployment this could query the OpenClaw orchestrator.
    """
    return {
        "cluster": "JARVIS",
        "nodes": {
            "M1": {"host": "127.0.0.1", "port": 1234, "gpu": "qwen3-30b"},
            "M2": {"host": "192.168.1.26", "port": 1234, "gpu": "deepseek-coder"},
            "OL1": {"host": "127.0.0.1", "port": 11434, "gpu": "qwen3-8b"},
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

def get_trading():
    """Read the latest trading signals from the SQLite DB if it exists.
    The DB schema used by JARVIS stores a table ``signals`` with columns
    ``ts`` (ISO timestamp) and ``signal`` (text).  If the DB or table is
    missing we return an empty list.
    """
    db_path = Path(r"F:/BUREAU/turbo/projects/carV1_data/database/trading_latest.db")
    if not db_path.is_file():
        return []
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT ts, signal FROM signals ORDER BY ts DESC LIMIT 20")
        rows = cur.fetchall()
        conn.close()
        return [{"ts": ts, "signal": sig} for ts, sig in rows]
    except Exception as e:
        return {"error": str(e)}

def get_metrics():
    """Collect CPU, RAM and GPU temperature/utilisation.
    Uses ``psutil`` when available; otherwise falls back to PowerShell.
    """
    result = {}
    # CPU & RAM via psutil or PowerShell
    try:
        import psutil
        result["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        result["ram_percent"] = mem.percent
    except Exception:
        # PowerShell fallback (Windows only)
        try:
            cpu_out = subprocess.check_output(
                ["powershell", "-Command", "(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples[0].CookedValue"],
                text=True,
                timeout=5,
            )
            result["cpu_percent"] = float(cpu_out.strip())
            ram_out = subprocess.check_output(
                ["powershell", "-Command", "(Get-Counter '\\Memory\\% Committed Bytes In Use').CounterSamples[0].CookedValue"],
                text=True,
                timeout=5,
            )
            result["ram_percent"] = float(ram_out.strip())
        except Exception:
            result["cpu_percent"] = None
            result["ram_percent"] = None
    # GPU temperature via nvidia-smi (if present)
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        )
        temps = []
        utils = []
        for line in out.strip().splitlines():
            if not line:
                continue
            t, u = line.split(',')
            temps.append(int(t.strip()))
            utils.append(int(u.strip()))
        if temps:
            result["gpu_temperature"] = max(temps)
            result["gpu_utilization"] = max(utils)
    except Exception:
        result["gpu_temperature"] = None
        result["gpu_utilization"] = None
    return result

def get_cron_jobs():
    """Invoke the OpenClaw ``cron`` tool to list jobs.
    The tool is exposed via the OpenClaw function ``cron`` – we can call it
    via the internal API if the sandbox permits.  As a fallback we return a
    placeholder indicating that the feature is unavailable.
    """
    try:
        # Use the OpenClaw tool ``cron`` with action=list and includeDisabled=True
        from functions import cron  # type: ignore
        resp = cron({
            "action": "list",
            "includeDisabled": True,
            "timeoutMs": 15000,
        })
        # The tool returns a JSON-serialisable dict; we just forward it.
        return resp
    except Exception:
        # If the tool is not reachable, return an empty list.
        return []

# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------
from datetime import datetime

class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            json_response(self, get_status())
        elif parsed.path == "/api/trading":
            json_response(self, {"signals": get_trading()})
        elif parsed.path == "/api/metrics":
            json_response(self, get_metrics())
        elif parsed.path == "/api/cron":
            json_response(self, {"jobs": get_cron_jobs()})
        else:
            json_response(self, {"error": "Endpoint not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format, *args):
        # Suppress standard logging; optional debug print could be added.
        return

# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------
def run_server(host="0.0.0.0", port=8085):
    server = HTTPServer((host, port), APIHandler)
    print(f"[cluster_dashboard_api] Listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[cluster_dashboard_api] Shutting down.")
        server.server_close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="REST API for the JARVIS Electron dashboard (port 8085).")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8085, help="Bind port (default: 8085)")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)

if __name__ == "__main__":
    main()
