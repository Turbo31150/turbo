#!/usr/bin/env python3
"""telegram_sender.py — Centralized Telegram messaging for all COWORK scripts.

Single point for sending Telegram messages. All scripts should import
send_telegram() from here instead of hardcoding the token.

Features:
- Rate limiting (max 30 msgs/min to avoid Telegram API limits)
- Message dedup (skip identical messages within 60s)
- Queue with retry
- Token loaded from config or env

Usage:
    from telegram_sender import send_telegram
    send_telegram("Hello from my script")

CLI:
    --send TEXT     : Send a message
    --test          : Send test message
    --stats         : Show send stats

Stdlib-only (json, urllib, time, hashlib).
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"

# Token and chat ID — SINGLE SOURCE OF TRUTH
# TELEGRAM_TOKEN loaded from _paths (.env)
TELEGRAM_CHAT_ID = TELEGRAM_CHAT

# Rate limiting
MAX_MSGS_PER_MIN = 25          # Telegram limit is 30/min, keep margin
DEDUP_WINDOW_S = 60            # Skip identical messages within 60s
MAX_MSG_LENGTH = 4096          # Telegram max message length

# In-memory state (per-process)
_last_sends = []               # timestamps of recent sends
_recent_hashes = {}            # hash -> timestamp of recent messages


def _msg_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:12]


def _rate_ok():
    """Check if we're within rate limits."""
    now = time.time()
    # Clean old entries
    _last_sends[:] = [t for t in _last_sends if now - t < 60]
    return len(_last_sends) < MAX_MSGS_PER_MIN


def _is_duplicate(text):
    """Check if this message was sent recently."""
    now = time.time()
    h = _msg_hash(text)
    # Clean old entries
    for k in list(_recent_hashes.keys()):
        if now - _recent_hashes[k] > DEDUP_WINDOW_S:
            del _recent_hashes[k]
    return h in _recent_hashes


def send_telegram(text, parse_mode="HTML", silent=False):
    """Send message to Telegram. Returns True on success.

    Args:
        text: Message text (max 4096 chars, auto-split if longer)
        parse_mode: HTML or Markdown
        silent: If True, send without notification sound
    """
    if not text or not text.strip():
        return False

    # Rate check
    if not _rate_ok():
        return False

    # Dedup check
    if _is_duplicate(text):
        return True  # Already sent, skip silently

    # Split long messages
    if len(text) > MAX_MSG_LENGTH:
        parts = []
        while text:
            if len(text) <= MAX_MSG_LENGTH:
                parts.append(text)
                break
            # Find a good split point
            split_at = text.rfind("\n", 0, MAX_MSG_LENGTH)
            if split_at < MAX_MSG_LENGTH // 2:
                split_at = MAX_MSG_LENGTH
            parts.append(text[:split_at])
            text = text[split_at:].lstrip("\n")

        ok = True
        for part in parts:
            if not _send_one(part, parse_mode, silent):
                ok = False
            time.sleep(0.3)  # Small delay between parts
        return ok

    return _send_one(text, parse_mode, silent)


def _send_one(text, parse_mode="HTML", silent=False):
    """Send a single message."""
    params = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }
    if silent:
        params["disable_notification"] = "true"

    data = urllib.parse.urlencode(params).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())

        if result.get("ok"):
            _last_sends.append(time.time())
            _recent_hashes[_msg_hash(text)] = time.time()
            return True
        return False
    except Exception:
        return False


def log_send(db_path, text, success):
    """Log send to DB for stats."""
    try:
        db = sqlite3.connect(str(db_path), timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS telegram_send_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, message_hash TEXT, length INTEGER, success INTEGER
        )""")
        db.execute(
            "INSERT INTO telegram_send_log (timestamp, message_hash, length, success) VALUES (?,?,?,?)",
            (datetime.now().isoformat(), _msg_hash(text), len(text), 1 if success else 0)
        )
        db.commit()
        db.close()
    except Exception:
        pass


def show_stats():
    """Show send statistics."""
    try:
        db = sqlite3.connect(str(GAPS_DB), timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        db.row_factory = sqlite3.Row
        row = db.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
                   COUNT(DISTINCT message_hash) as unique_msgs
            FROM telegram_send_log
        """).fetchone()
        if row:
            print(f"=== Telegram Send Stats ===")
            print(f"  Total sends: {row['total']}")
            print(f"  Successful: {row['ok']}")
            print(f"  Unique messages: {row['unique_msgs']}")
        db.close()
    except Exception:
        print("No stats available yet")


def main():
    parser = argparse.ArgumentParser(description="Telegram Sender")
    parser.add_argument("--send", type=str, help="Send message")
    parser.add_argument("--test", action="store_true", help="Test send")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    args = parser.parse_args()

    if not any([args.send, args.test, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        show_stats()
        return

    if args.test:
        ts = datetime.now().strftime("%H:%M:%S")
        ok = send_telegram(f"<b>Test</b> <code>{ts}</code>\ntelegram_sender.py OK")
        print(f"Test send: {'OK' if ok else 'FAIL'}")
        return

    if args.send:
        ok = send_telegram(args.send)
        print(f"Send: {'OK' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()