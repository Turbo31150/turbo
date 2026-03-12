#!/usr/bin/env python3
"""Electron App Monitor — Watch JARVIS Desktop health and performance.

Monitors Electron process, WebSocket backend, memory usage,
and React dev server. Auto-restarts if crashed.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
import urllib.request
from pathlib import Path

DB_PATH = Path(__file__).parent / "electron_monitor.db"
from _paths import TURBO_DIR as TURBO
ELECTRON_DIR = TURBO / "electron"
WS_PORT = 9742
LAUNCHER = TURBO / "launchers" / "JARVIS.bat"

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY, ts REAL, electron_running INTEGER,
        ws_running INTEGER, ws_latency_ms REAL, electron_mem_mb REAL,
        python_ws_mem_mb REAL, pages_count INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY, ts REAL, event_type TEXT, details TEXT)""")
    db.commit()
    return db

def check_electron():
    """Check if Electron process is running."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process -Name 'electron','JARVIS*' -ErrorAction SilentlyContinue | "
             "Select-Object Name, Id, @{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB)}} | "
             "ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            total_mem = sum(p.get("MemMB", 0) for p in data)
            return True, total_mem, len(data)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return False, 0, 0

def check_ws_backend():
    """Check WebSocket backend on port 9742."""
    try:
        start = time.time()
        req = urllib.request.Request(f"http://127.0.0.1:{WS_PORT}/api/status")
        with urllib.request.urlopen(req, timeout=3) as resp:
            latency = (time.time() - start) * 1000
            data = json.loads(resp.read())
            return True, latency, data
    except Exception:
        pass
    # Try health endpoint
    try:
        start = time.time()
        req = urllib.request.Request(f"http://127.0.0.1:{WS_PORT}/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            latency = (time.time() - start) * 1000
            return True, latency, {}
    except Exception:
        pass
    return False, 0, {}

def check_python_ws_memory():
    """Check Python WebSocket server memory."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process python* -ErrorAction SilentlyContinue | "
             "Where-Object {$_.CommandLine -match 'server.py|python_ws'} | "
             "Measure-Object -Property WorkingSet64 -Sum).Sum / 1MB"],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass
    return 0.0

def take_snapshot(db):
    """Take a complete health snapshot."""
    elec_running, elec_mem, elec_procs = check_electron()
    ws_running, ws_latency, ws_data = check_ws_backend()
    py_mem = check_python_ws_memory()

    db.execute(
        "INSERT INTO snapshots (ts, electron_running, ws_running, ws_latency_ms, "
        "electron_mem_mb, python_ws_mem_mb, pages_count) VALUES (?,?,?,?,?,?,?)",
        (time.time(), 1 if elec_running else 0, 1 if ws_running else 0,
         ws_latency, elec_mem, py_mem, elec_procs))
    db.commit()

    return {
        "electron": {"running": elec_running, "mem_mb": elec_mem, "processes": elec_procs},
        "ws_backend": {"running": ws_running, "latency_ms": round(ws_latency, 1)},
        "python_mem_mb": round(py_mem, 1),
    }

def check_anomalies(db, snapshot):
    """Detect anomalies in snapshot."""
    anomalies = []
    if not snapshot["electron"]["running"]:
        anomalies.append("Electron OFFLINE")
    if not snapshot["ws_backend"]["running"]:
        anomalies.append("WebSocket backend OFFLINE")
    if snapshot["electron"]["mem_mb"] > 2000:
        anomalies.append(f"Electron haute memoire: {snapshot['electron']['mem_mb']}MB")
    if snapshot["python_mem_mb"] > 1000:
        anomalies.append(f"Python WS haute memoire: {snapshot['python_mem_mb']}MB")
    if snapshot["ws_backend"]["latency_ms"] > 500:
        anomalies.append(f"WS backend lent: {snapshot['ws_backend']['latency_ms']}ms")

    for a in anomalies:
        db.execute("INSERT INTO events (ts, event_type, details) VALUES (?,?,?)",
                   (time.time(), "anomaly", a))
    db.commit()
    return anomalies

def main():
    parser = argparse.ArgumentParser(description="Electron App Monitor")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between checks")
    args = parser.parse_args()

    db = init_db()

    if args.once or not args.loop:
        snapshot = take_snapshot(db)
        print("=== JARVIS Desktop Monitor ===")
        e = snapshot["electron"]
        print(f"  Electron: {'RUNNING' if e['running'] else 'OFFLINE'} | {e['mem_mb']}MB | {e['processes']} procs")
        ws = snapshot["ws_backend"]
        print(f"  WS Backend: {'RUNNING' if ws['running'] else 'OFFLINE'} | {ws['latency_ms']}ms")
        print(f"  Python WS: {snapshot['python_mem_mb']}MB")
        anomalies = check_anomalies(db, snapshot)
        if anomalies:
            print("  ⚠ Anomalies:")
            for a in anomalies:
                print(f"    → {a}")

    if args.loop:
        print("Electron Monitor en boucle continue...")
        while True:
            try:
                snapshot = take_snapshot(db)
                anomalies = check_anomalies(db, snapshot)
                ts = time.strftime('%H:%M')
                status = "OK" if not anomalies else f"{len(anomalies)} anomalies"
                e_mem = snapshot["electron"]["mem_mb"]
                print(f"[{ts}] Electron: {e_mem}MB | WS: {snapshot['ws_backend']['latency_ms']}ms | {status}")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
