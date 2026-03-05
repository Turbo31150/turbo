#!/usr/bin/env python3
"""jarvis_telegram_enhanced.py — Enhanced Telegram bot features (#255).

Inline keyboard menus, message templates, scheduled messages,
conversation tracking.

Usage:
    python dev/jarvis_telegram_enhanced.py --once
    python dev/jarvis_telegram_enhanced.py --status
    python dev/jarvis_telegram_enhanced.py --send "MSG"
    python dev/jarvis_telegram_enhanced.py --inline-menu
    python dev/jarvis_telegram_enhanced.py --history
"""
import argparse
import json
import os
import sqlite3
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "telegram_enhanced.db"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "2010747443")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        direction TEXT NOT NULL,
        chat_id TEXT,
        text TEXT,
        message_id INTEGER,
        reply_markup TEXT,
        status TEXT DEFAULT 'sent'
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        text TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        usage_count INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS scheduled (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        send_at TEXT NOT NULL,
        text TEXT NOT NULL,
        chat_id TEXT,
        sent INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        chat_id TEXT,
        user_msg TEXT,
        bot_msg TEXT,
        context TEXT
    )""")

    count = db.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
    if count == 0:
        defaults = [
            ("status_report", "JARVIS Status Report\n- Cluster: {cluster}\n- GPU: {gpu}\n- Services: {services}", "system"),
            ("trading_alert", "Trading Alert\n- Pair: {pair}\n- Signal: {signal}\n- Score: {score}/100", "trading"),
            ("error_alert", "Error Alert\n- Source: {source}\n- Error: {error}\n- Time: {time}", "alert"),
            ("daily_summary", "Daily Summary\n- Tasks: {tasks}\n- Trades: {trades}\n- Uptime: {uptime}", "daily"),
            ("health_check", "Health Check\n- M1: {m1}\n- M2: {m2}\n- OL1: {ol1}\n- GEMINI: {gemini}", "system"),
        ]
        for name, text, cat in defaults:
            db.execute("INSERT INTO templates (name, text, category) VALUES (?,?,?)", (name, text, cat))

    db.commit()
    return db


def telegram_api(method, data=None):
    """Call Telegram Bot API."""
    if not BOT_TOKEN:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not set"}
    url = f"{API_BASE}/{method}"
    try:
        if data:
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e)}


def do_send(msg):
    """Send a message to Telegram."""
    db = init_db()
    now = datetime.now()

    resp = telegram_api("sendMessage", {
        "chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown",
    })

    msg_id = None
    status = "failed"
    if resp.get("ok"):
        msg_id = resp.get("result", {}).get("message_id")
        status = "sent"

    db.execute(
        "INSERT INTO messages (ts, direction, chat_id, text, message_id, status) VALUES (?,?,?,?,?,?)",
        (now.isoformat(), "outgoing", CHAT_ID, msg, msg_id, status),
    )
    db.commit()

    result = {
        "ts": now.isoformat(), "action": "send", "chat_id": CHAT_ID,
        "text": msg[:200], "message_id": msg_id, "status": status,
        "api_ok": resp.get("ok", False),
        "error": resp.get("error") if not resp.get("ok") else None,
    }
    db.close()
    return result


def do_inline_menu():
    """Send an inline keyboard menu."""
    db = init_db()
    now = datetime.now()

    keyboard = {
        "inline_keyboard": [
            [{"text": "Status", "callback_data": "cmd_status"}, {"text": "Health", "callback_data": "cmd_health"}],
            [{"text": "Trading", "callback_data": "cmd_trading"}, {"text": "GPU", "callback_data": "cmd_gpu"}],
            [{"text": "Cluster Check", "callback_data": "cmd_cluster"}],
        ]
    }

    resp = telegram_api("sendMessage", {
        "chat_id": CHAT_ID, "text": "JARVIS Control Panel - Select an action:",
        "reply_markup": keyboard,
    })

    status = "sent" if resp.get("ok") else "failed"
    db.execute(
        "INSERT INTO messages (ts, direction, chat_id, text, message_id, reply_markup, status) VALUES (?,?,?,?,?,?,?)",
        (now.isoformat(), "outgoing", CHAT_ID, "inline_menu",
         resp.get("result", {}).get("message_id") if resp.get("ok") else None,
         json.dumps(keyboard), status),
    )
    db.commit()

    result = {
        "ts": now.isoformat(), "action": "inline_menu", "status": status,
        "api_ok": resp.get("ok", False), "buttons": 5,
        "error": resp.get("error") if not resp.get("ok") else None,
    }
    db.close()
    return result


def do_history():
    """Show message history."""
    db = init_db()
    messages = db.execute(
        "SELECT ts, direction, text, message_id, status FROM messages ORDER BY id DESC LIMIT 30"
    ).fetchall()
    total = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    sent = db.execute("SELECT COUNT(*) FROM messages WHERE direction='outgoing'").fetchone()[0]
    received = db.execute("SELECT COUNT(*) FROM messages WHERE direction='incoming'").fetchone()[0]
    templates = db.execute("SELECT name, category, usage_count FROM templates ORDER BY usage_count DESC").fetchall()

    result = {
        "ts": datetime.now().isoformat(), "action": "history",
        "total_messages": total, "sent": sent, "received": received,
        "templates": [{"name": t[0], "category": t[1], "uses": t[2]} for t in templates],
        "recent": [
            {"ts": m[0], "direction": m[1], "text": (m[2] or "")[:100], "message_id": m[3], "status": m[4]}
            for m in messages[:15]
        ],
    }
    db.close()
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(), "script": "jarvis_telegram_enhanced.py", "script_id": 255,
        "db": str(DB_PATH), "chat_id": CHAT_ID, "bot_token_set": bool(BOT_TOKEN),
        "total_messages": db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
        "templates": db.execute("SELECT COUNT(*) FROM templates").fetchone()[0],
        "pending_scheduled": db.execute("SELECT COUNT(*) FROM scheduled WHERE sent=0").fetchone()[0],
        "conversations": db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="jarvis_telegram_enhanced.py — Enhanced Telegram (#255)")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--send", type=str, metavar="MSG", help="Send a message")
    parser.add_argument("--inline-menu", action="store_true", help="Send inline menu")
    parser.add_argument("--history", action="store_true", help="Show message history")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.send:
        result = do_send(args.send)
    elif args.inline_menu:
        result = do_inline_menu()
    elif args.history:
        result = do_history()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
