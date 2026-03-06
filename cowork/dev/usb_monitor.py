#!/usr/bin/env python3
"""usb_monitor.py

Moniteur USB Windows — détecte les branchements/débranchements.

CLI :
    --once     : Snapshot des périphériques USB actuels
    --loop     : Surveillance continue (toutes les 5s)
    --history  : Historique des événements USB (SQLite)
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"
DB_PATH = Path(__file__).parent / "usb.db"

def telegram_send(msg: str):
    import urllib.parse, urllib.request
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": msg}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass

def ps(cmd: str, timeout: int = 15) -> str:
    try:
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", cmd],
            text=True, stderr=subprocess.DEVNULL, timeout=timeout
        ).strip()
    except Exception:
        return ""

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS usb_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL,
        device_name TEXT,
        device_id TEXT,
        status TEXT
    )""")
    conn.commit()
    return conn

def log_event(conn: sqlite3.Connection, event_type: str, name: str, dev_id: str, status: str):
    conn.execute("INSERT INTO usb_events (timestamp, event_type, device_name, device_id, status) VALUES (?,?,?,?,?)",
                 (datetime.now().isoformat(), event_type, name, dev_id, status))
    conn.commit()

# ---------------------------------------------------------------------------
# Get USB devices
# ---------------------------------------------------------------------------
def get_usb_devices() -> List[Dict[str, str]]:
    out = ps("""
        Get-PnpDevice -Class USB -ErrorAction SilentlyContinue |
        Select-Object Status,FriendlyName,InstanceId |
        ConvertTo-Json -Compress
    """)
    if not out:
        return []
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        return [{"name": d.get("FriendlyName", ""), "id": d.get("InstanceId", ""), "status": d.get("Status", "")} for d in data]
    except Exception:
        return []

def show_once():
    devices = get_usb_devices()
    if not devices:
        print("[usb_monitor] Aucun périphérique USB détecté.")
        return
    print(f"Périphériques USB ({len(devices)}) :")
    for d in devices:
        status_icon = "🟢" if d["status"] == "OK" else "🔴"
        print(f"  {status_icon} {d['name']}")
        print(f"      ID: {d['id']}")

def monitor_loop():
    print("[usb_monitor] Surveillance USB active (Ctrl+C pour arrêter)...")
    conn = init_db()
    prev = {d["id"]: d for d in get_usb_devices()}
    try:
        while True:
            time.sleep(5)
            current = {d["id"]: d for d in get_usb_devices()}
            # Nouveaux appareils
            for dev_id, dev in current.items():
                if dev_id not in prev:
                    msg = f"🔌 USB branché : {dev['name']}"
                    print(f"  [+] {msg}")
                    log_event(conn, "connected", dev["name"], dev_id, dev["status"])
                    telegram_send(msg)
            # Appareils retirés
            for dev_id, dev in prev.items():
                if dev_id not in current:
                    msg = f"⏏️ USB débranché : {dev['name']}"
                    print(f"  [-] {msg}")
                    log_event(conn, "disconnected", dev["name"], dev_id, "removed")
                    telegram_send(msg)
            prev = current
    except KeyboardInterrupt:
        print("\n[usb_monitor] Surveillance arrêtée.")
    finally:
        conn.close()

def show_history():
    if not DB_PATH.is_file():
        print("[usb_monitor] Aucun historique (base inexistante).")
        return
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute("SELECT timestamp, event_type, device_name FROM usb_events ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    if not rows:
        print("[usb_monitor] Historique vide.")
        return
    print("Historique USB (20 derniers) :")
    for ts, evt, name in rows:
        icon = "🔌" if evt == "connected" else "⏏️"
        print(f"  {icon} {ts[:19]} — {name}")

def main():
    parser = argparse.ArgumentParser(description="Moniteur USB Windows.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Snapshot USB actuel")
    group.add_argument("--loop", action="store_true", help="Surveillance continue")
    group.add_argument("--history", action="store_true", help="Historique des événements")
    args = parser.parse_args()

    if args.once:
        show_once()
    elif args.loop:
        monitor_loop()
    elif args.history:
        show_history()

if __name__ == "__main__":
    main()
