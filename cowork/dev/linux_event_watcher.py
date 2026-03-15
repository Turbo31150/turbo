#!/usr/bin/env python3
"""win_event_watcher.py

Monitor Windows Event Viewer using ``wevtutil``.

Features:
  * ``--watch``   – Continuously poll (default interval 30s).
  * ``--once``    – Run a single poll and exit.
  * ``--filter <expr>`` – Simple substring filter applied to Provider name or Message.
  * ``--export``  – Store matched events into SQLite database ``dev/data/events.db``.
  * Critical levels (Critical/Error/Warning) are considered; GPU‑related events are additionally matched
    by provider names containing ``GPU`` or ``Display``.
  * When a *critical* event (Level 1) is detected, a Telegram alert is sent using environment variables
    ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID``.

Usage example::

    python win_event_watcher.py --watch --filter "GPU" --export

"""

import argparse
import subprocess
import sys
import time
import sqlite3
import os
import xml.etree.ElementTree as ET
from datetime import datetime
import shlex

# Constants
DEFAULT_INTERVAL = 30  # seconds
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "events.db")
TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    provider TEXT,
    event_id INTEGER,
    message TEXT
);
"""

def send_telegram_alert(message: str):
    """Send alert via Telegram bot.
    Requires ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` in environment.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        # Silent fail – environment not configured.
        return
    import urllib.parse, urllib.request
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        urllib.request.urlopen(url, data=payload, timeout=5)
    except Exception:
        pass

def query_events():
    """Run ``wevtutil`` to fetch recent events (last 5 minutes)."""
    # Build query: fetch events with Level 1 (Critical), 2 (Error), 3 (Warning)
    # We limit to events from the last 5 minutes using "TimeCreated[timediff(@SystemTime) <= 300000]"
    query = "*[System[(Level=1 or Level=2 or Level=3) and TimeCreated[timediff(@SystemTime) <= 300000]]]"
    cmd = ["wevtutil", "qe", "System", f"/q:{query}", "/f:xml"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"wevtutil failed: {e}\n")
        return ""

def parse_events(xml_data: str):
    """Parse XML returned by ``wevtutil`` and yield dicts."""
    events = []
    try:
        root = ET.fromstring(f"<Events>{xml_data}</Events>")
    except ET.ParseError:
        return events
    for ev in root.findall('.//Event'):
        system = ev.find('System')
        if system is None:
            continue
        level = system.findtext('Level')
        level_map = {"1": "Critical", "2": "Error", "3": "Warning"}
        level_str = level_map.get(level, "Other")
        provider = system.find('Provider')
        provider_name = provider.get('Name') if provider is not None else None
        event_id = system.findtext('EventID')
        time_created = system.find('TimeCreated')
        timestamp = time_created.get('SystemTime') if time_created is not None else None
        # Message is under Event/RenderingInfo/Message or Event/Message
        message = ev.findtext('.//Message')
        events.append({
            "timestamp": timestamp,
            "level": level_str,
            "provider": provider_name,
            "event_id": int(event_id) if event_id and event_id.isdigit() else None,
            "message": message,
        })
    return events

def filter_events(events, substr: str | None):
    if not substr:
        return events
    substr_low = substr.lower()
    return [e for e in events if (e["provider"] and substr_low in e["provider"].lower()) or (e["message"] and substr_low in e["message"].lower())]

def export_to_sqlite(events):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(TABLE_SCHEMA)
    for ev in events:
        cur.execute(
            "INSERT INTO events (timestamp, level, provider, event_id, message) VALUES (?,?,?,?,?)",
            (ev["timestamp"], ev["level"], ev["provider"], ev["event_id"], ev["message"]),
        )
    conn.commit()
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Watch Windows Event Viewer and optionally export to SQLite and send Telegram alerts.")
    parser.add_argument("--watch", action="store_true", help="Continuously monitor (default interval 30s).")
    parser.add_argument("--once", action="store_true", help="Run a single poll and exit.")
    parser.add_argument("--filter", type=str, help="Substring filter applied to provider or message.")
    parser.add_argument("--export", action="store_true", help="Store matched events into SQLite database.")
    args = parser.parse_args()

    if not args.watch and not args.once:
        parser.error("Either --watch or --once must be specified.")

    def process_cycle():
        raw = query_events()
        evs = parse_events(raw)
        evs = filter_events(evs, args.filter)
        if not evs:
            return
        # Alert for critical events
        for ev in evs:
            if ev["level"] == "Critical":
                alert_msg = f"⚠️ Critical Windows event detected:\nProvider: {ev['provider']}\nID: {ev['event_id']}\nTime: {ev['timestamp']}\nMessage: {ev['message']}"
                send_telegram_alert(alert_msg)
        if args.export:
            export_to_sqlite(evs)

    if args.once:
        process_cycle()
        return

    # Watch mode loop
    while True:
        process_cycle()
        time.sleep(DEFAULT_INTERVAL)

if __name__ == "__main__":
    main()
