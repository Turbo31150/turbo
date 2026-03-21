#!/usr/bin/env python3
"""Telegram MCP Bridge — Send cowork alerts and reports via Telegram Bot API.

Bot: @turboSSebot | Chat ID: 2010747443

Usage:
    python cowork/dev/telegram_mcp_bridge.py --once          # Send health report
    python cowork/dev/telegram_mcp_bridge.py --alert "msg"   # Send alert
    python cowork/dev/telegram_mcp_bridge.py --report file   # Send JSON report
"""

import argparse
import json
import os
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent
DB_PATH = TURBO / "etoile.db"
CHAT_ID = "2010747443"


def get_bot_token():
    """Get Telegram bot token from env or etoile.db."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token
    try:
        db = sqlite3.connect(str(DB_PATH))
        row = db.execute("SELECT value FROM api_keys WHERE key_name='telegram'").fetchone()
        db.close()
        if row:
            return row[0]
    except Exception:
        pass
    return None


def send_message(text, parse_mode="HTML"):
    """Send a message via Telegram Bot API."""
    token = get_bot_token()
    if not token:
        return {"error": "No bot token found"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text[:4096],
        "parse_mode": parse_mode
    }).encode()
    try:
        req = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def send_alert(msg):
    """Send an alert message."""
    text = f"🚨 <b>JARVIS ALERT</b>\n{datetime.now().strftime('%H:%M:%S')}\n\n{msg}"
    return send_message(text)


def send_report(data):
    """Send a formatted JSON report."""
    if isinstance(data, dict):
        lines = [f"📊 <b>JARVIS REPORT</b> — {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
        for k, v in data.items():
            lines.append(f"• <b>{k}</b>: {v}")
        text = "\n".join(lines)
    else:
        text = str(data)
    return send_message(text)


def get_updates(limit=5):
    """Get recent Telegram updates."""
    token = get_bot_token()
    if not token:
        return {"error": "No bot token"}
    url = f"https://api.telegram.org/bot{token}/getUpdates?limit={limit}"
    try:
        resp = urllib.request.urlopen(url, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def run_once():
    """Send a health status report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "services": "checking...",
        "disk_c": "checking...",
        "status": "operational"
    }
    result = send_report(report)
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description="Telegram MCP Bridge")
    parser.add_argument("--once", action="store_true", help="Send health report")
    parser.add_argument("--alert", type=str, help="Send alert message")
    parser.add_argument("--report", type=str, help="Send JSON report from file")
    parser.add_argument("--updates", action="store_true", help="Get recent updates")
    args = parser.parse_args()

    if args.alert:
        r = send_alert(args.alert)
        print(json.dumps(r, indent=2))
    elif args.report:
        with open(args.report) as f:
            data = json.load(f)
        r = send_report(data)
        print(json.dumps(r, indent=2))
    elif args.updates:
        r = get_updates()
        print(json.dumps(r, indent=2))
    elif args.once:
        run_once()
    else:
        print("Use --once, --alert, --report, or --updates")


if __name__ == "__main__":
    main()
