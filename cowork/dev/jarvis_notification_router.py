#!/usr/bin/env python3
"""jarvis_notification_router.py — Notification routing (#257).

Routes messages to appropriate channels (console/file/telegram)
based on priority+type rules. Rate limiting.

Usage:
    python dev/jarvis_notification_router.py --once
    python dev/jarvis_notification_router.py --route "MSG"
    python dev/jarvis_notification_router.py --channels
    python dev/jarvis_notification_router.py --rules
    python dev/jarvis_notification_router.py --stats
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "notification_router.db"
LOG_DIR = DEV / "data" / "notifications"

DEFAULT_RULES = [
    {"priority": "critical", "channels": ["console", "file", "telegram"], "rate_limit_seconds": 0},
    {"priority": "high", "channels": ["console", "file", "telegram"], "rate_limit_seconds": 60},
    {"priority": "medium", "channels": ["console", "file"], "rate_limit_seconds": 300},
    {"priority": "low", "channels": ["file"], "rate_limit_seconds": 600},
    {"priority": "debug", "channels": ["file"], "rate_limit_seconds": 0},
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        message TEXT NOT NULL,
        priority TEXT DEFAULT 'medium',
        msg_type TEXT DEFAULT 'general',
        channels_sent TEXT,
        rate_limited INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        priority TEXT NOT NULL,
        channels TEXT NOT NULL,
        rate_limit_seconds INTEGER DEFAULT 300,
        active INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS channel_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT NOT NULL,
        sent_count INTEGER DEFAULT 0,
        last_sent TEXT,
        errors INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS rate_limits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        priority TEXT UNIQUE NOT NULL,
        last_sent_ts REAL DEFAULT 0
    )""")

    # Seed rules if empty
    if db.execute("SELECT COUNT(*) FROM rules").fetchone()[0] == 0:
        for r in DEFAULT_RULES:
            db.execute(
                "INSERT INTO rules (priority, channels, rate_limit_seconds) VALUES (?,?,?)",
                (r["priority"], json.dumps(r["channels"]), r["rate_limit_seconds"]),
            )

    # Seed channel stats if empty
    if db.execute("SELECT COUNT(*) FROM channel_stats").fetchone()[0] == 0:
        for ch in ["console", "file", "telegram"]:
            db.execute("INSERT INTO channel_stats (channel, sent_count) VALUES (?,0)", (ch,))

    db.commit()
    return db


def classify_priority(message):
    """Auto-classify message priority."""
    msg_lower = message.lower()
    if any(k in msg_lower for k in ["error", "critical", "crash", "fail", "down", "offline"]):
        return "critical"
    if any(k in msg_lower for k in ["warning", "alert", "high", "urgent"]):
        return "high"
    if any(k in msg_lower for k in ["info", "update", "status", "report"]):
        return "medium"
    if any(k in msg_lower for k in ["debug", "trace", "verbose"]):
        return "debug"
    return "low"


def classify_type(message):
    """Auto-classify message type."""
    msg_lower = message.lower()
    if any(k in msg_lower for k in ["trade", "trading", "signal", "position"]):
        return "trading"
    if any(k in msg_lower for k in ["cluster", "gpu", "model", "agent"]):
        return "system"
    if any(k in msg_lower for k in ["deploy", "build", "test", "code"]):
        return "dev"
    if any(k in msg_lower for k in ["backup", "restore", "data"]):
        return "maintenance"
    return "general"


def check_rate_limit(db, priority):
    """Check if rate limit allows sending."""
    rule = db.execute(
        "SELECT rate_limit_seconds FROM rules WHERE priority=? AND active=1", (priority,)
    ).fetchone()
    if not rule or rule[0] == 0:
        return True  # No limit

    rate_limit = rule[0]
    row = db.execute("SELECT last_sent_ts FROM rate_limits WHERE priority=?", (priority,)).fetchone()
    if not row:
        db.execute("INSERT INTO rate_limits (priority, last_sent_ts) VALUES (?,?)", (priority, time.time()))
        db.commit()
        return True

    elapsed = time.time() - row[0]
    if elapsed >= rate_limit:
        db.execute("UPDATE rate_limits SET last_sent_ts=? WHERE priority=?", (time.time(), priority))
        db.commit()
        return True
    return False


def send_to_console(message, priority):
    """Send to console (print)."""
    prefix = {"critical": "[CRIT]", "high": "[HIGH]", "medium": "[INFO]", "low": "[LOW]", "debug": "[DBG]"}
    print(f"{prefix.get(priority, '[???]')} {message}")
    return True


def send_to_file(message, priority):
    """Append to notification log file."""
    try:
        log_file = LOG_DIR / f"notifications_{datetime.now().strftime('%Y%m%d')}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} [{priority.upper()}] {message}\n")
        return True
    except Exception:
        return False


def send_to_telegram(message, priority):
    """Placeholder for Telegram send (requires bot token)."""
    # In production, this would use the Telegram API
    return True  # Simulated success


def do_route(message):
    """Route a message based on rules."""
    db = init_db()
    now = datetime.now()
    priority = classify_priority(message)
    msg_type = classify_type(message)

    # Check rate limit
    if not check_rate_limit(db, priority):
        db.execute(
            "INSERT INTO notifications (ts, message, priority, msg_type, rate_limited) VALUES (?,?,?,?,1)",
            (now.isoformat(), message, priority, msg_type),
        )
        db.commit()
        db.close()
        return {
            "ts": now.isoformat(), "action": "route", "message": message[:200],
            "priority": priority, "type": msg_type, "rate_limited": True,
            "channels_sent": [],
        }

    # Get channels for this priority
    rule = db.execute(
        "SELECT channels FROM rules WHERE priority=? AND active=1", (priority,)
    ).fetchone()
    channels = json.loads(rule[0]) if rule else ["console"]

    sent_channels = []
    for ch in channels:
        success = False
        if ch == "console":
            success = send_to_console(message, priority)
        elif ch == "file":
            success = send_to_file(message, priority)
        elif ch == "telegram":
            success = send_to_telegram(message, priority)

        if success:
            sent_channels.append(ch)
            db.execute(
                "UPDATE channel_stats SET sent_count=sent_count+1, last_sent=? WHERE channel=?",
                (now.isoformat(), ch),
            )

    db.execute(
        "INSERT INTO notifications (ts, message, priority, msg_type, channels_sent) VALUES (?,?,?,?,?)",
        (now.isoformat(), message, priority, msg_type, json.dumps(sent_channels)),
    )
    db.commit()

    result = {
        "ts": now.isoformat(), "action": "route", "message": message[:200],
        "priority": priority, "type": msg_type,
        "channels_sent": sent_channels, "rate_limited": False,
    }
    db.close()
    return result


def do_channels():
    """Show channel statistics."""
    db = init_db()
    rows = db.execute("SELECT channel, sent_count, last_sent, errors FROM channel_stats").fetchall()

    result = {
        "ts": datetime.now().isoformat(), "action": "channels",
        "channels": [
            {"channel": r[0], "sent_count": r[1], "last_sent": r[2], "errors": r[3]}
            for r in rows
        ],
    }
    db.close()
    return result


def do_rules():
    """Show routing rules."""
    db = init_db()
    rows = db.execute("SELECT priority, channels, rate_limit_seconds, active FROM rules").fetchall()

    result = {
        "ts": datetime.now().isoformat(), "action": "rules",
        "rules": [
            {"priority": r[0], "channels": json.loads(r[1]),
             "rate_limit_seconds": r[2], "active": bool(r[3])}
            for r in rows
        ],
    }
    db.close()
    return result


def do_stats():
    """Show notification statistics."""
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
    by_priority = db.execute(
        "SELECT priority, COUNT(*) FROM notifications GROUP BY priority ORDER BY COUNT(*) DESC"
    ).fetchall()
    rate_limited = db.execute("SELECT COUNT(*) FROM notifications WHERE rate_limited=1").fetchone()[0]
    recent = db.execute(
        "SELECT ts, priority, msg_type, channels_sent, rate_limited FROM notifications ORDER BY id DESC LIMIT 10"
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(), "action": "stats",
        "total_notifications": total,
        "rate_limited": rate_limited,
        "by_priority": {r[0]: r[1] for r in by_priority},
        "recent": [
            {"ts": r[0], "priority": r[1], "type": r[2],
             "channels": json.loads(r[3]) if r[3] else [], "rate_limited": bool(r[4])}
            for r in recent
        ],
    }
    db.close()
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(), "script": "jarvis_notification_router.py", "script_id": 257,
        "db": str(DB_PATH),
        "total_notifications": db.execute("SELECT COUNT(*) FROM notifications").fetchone()[0],
        "rules_count": db.execute("SELECT COUNT(*) FROM rules").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="jarvis_notification_router.py — Notification routing (#257)")
    parser.add_argument("--route", type=str, metavar="MSG", help="Route a message")
    parser.add_argument("--channels", action="store_true", help="Show channel stats")
    parser.add_argument("--rules", action="store_true", help="Show routing rules")
    parser.add_argument("--stats", action="store_true", help="Show notification stats")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.route:
        result = do_route(args.route)
    elif args.channels:
        result = do_channels()
    elif args.rules:
        result = do_rules()
    elif args.stats:
        result = do_stats()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
