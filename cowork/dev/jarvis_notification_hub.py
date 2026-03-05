#!/usr/bin/env python3
"""jarvis_notification_hub.py (#184) — Multi-channel notification hub.

Channels: console (print), file (append log), telegram (placeholder).
Priority levels: critical, warning, info.
Rate-limiting per channel.

Usage:
    python dev/jarvis_notification_hub.py --once
    python dev/jarvis_notification_hub.py --send "Disk full" --priority critical
    python dev/jarvis_notification_hub.py --channels
    python dev/jarvis_notification_hub.py --history
"""
import argparse
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "notification_hub.db"
LOG_PATH = DEV / "data" / "notifications.log"

# Rate limits: max N messages per window_seconds per channel
RATE_LIMITS = {
    "console": {"max": 60, "window": 60},
    "file": {"max": 120, "window": 60},
    "telegram": {"max": 10, "window": 60},
}

PRIORITY_LEVELS = {"critical": 3, "warning": 2, "info": 1}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        message TEXT NOT NULL,
        priority TEXT DEFAULT 'info',
        priority_level INTEGER DEFAULT 1,
        channels_sent TEXT DEFAULT '[]',
        source TEXT DEFAULT 'manual'
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS channels (
        name TEXT PRIMARY KEY,
        enabled INTEGER DEFAULT 1,
        config_json TEXT DEFAULT '{}',
        send_count INTEGER DEFAULT 0,
        last_send REAL DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS rate_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT,
        ts REAL
    )""")
    # Seed default channels
    for ch in ["console", "file", "telegram"]:
        db.execute(
            "INSERT OR IGNORE INTO channels (name, enabled, config_json) VALUES (?,?,?)",
            (ch, 1 if ch != "telegram" else 0, json.dumps(RATE_LIMITS.get(ch, {})))
        )
    db.commit()
    return db


def check_rate_limit(db, channel):
    """Return True if sending is allowed (not rate-limited)."""
    limits = RATE_LIMITS.get(channel, {"max": 100, "window": 60})
    window_start = time.time() - limits["window"]
    count = db.execute(
        "SELECT COUNT(*) FROM rate_log WHERE channel=? AND ts>?",
        (channel, window_start)
    ).fetchone()[0]
    return count < limits["max"]


def record_send(db, channel):
    """Record a send event for rate limiting."""
    db.execute("INSERT INTO rate_log (channel, ts) VALUES (?,?)", (channel, time.time()))
    db.execute("UPDATE channels SET send_count=send_count+1, last_send=? WHERE name=?", (time.time(), channel))
    # Cleanup old rate log entries (older than 5 min)
    db.execute("DELETE FROM rate_log WHERE ts < ?", (time.time() - 300,))
    db.commit()


def send_console(message, priority):
    """Send to console."""
    prefix = {"critical": "[!!!]", "warning": "[!]", "info": "[i]"}.get(priority, "[?]")
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{prefix} [{ts}] {message}")
    return True


def send_file(message, priority):
    """Append to log file."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{priority.upper()}] {message}\n")
    return True


def send_telegram(message, priority):
    """Telegram placeholder — returns False (not configured)."""
    # Placeholder: would call Telegram Bot API
    # curl -s "https://api.telegram.org/bot{TOKEN}/sendMessage" -d "chat_id={CHAT_ID}&text={message}"
    return False


CHANNEL_HANDLERS = {
    "console": send_console,
    "file": send_file,
    "telegram": send_telegram,
}


def send_notification(db, message, priority="info", source="manual"):
    """Send notification through all enabled channels."""
    priority = priority.lower()
    if priority not in PRIORITY_LEVELS:
        priority = "info"

    channels_sent = []
    channels_blocked = []
    channels_failed = []

    enabled = db.execute("SELECT name FROM channels WHERE enabled=1").fetchall()

    for (ch_name,) in enabled:
        if not check_rate_limit(db, ch_name):
            channels_blocked.append(ch_name)
            continue

        handler = CHANNEL_HANDLERS.get(ch_name)
        if handler:
            try:
                ok = handler(message, priority)
                if ok:
                    channels_sent.append(ch_name)
                    record_send(db, ch_name)
                else:
                    channels_failed.append(ch_name)
            except Exception as e:
                channels_failed.append(f"{ch_name}:{e}")
        else:
            channels_failed.append(f"{ch_name}:no_handler")

    db.execute(
        "INSERT INTO notifications (ts, message, priority, priority_level, channels_sent, source) VALUES (?,?,?,?,?,?)",
        (time.time(), message, priority, PRIORITY_LEVELS.get(priority, 1),
         json.dumps(channels_sent), source)
    )
    db.commit()

    return {
        "status": "ok", "message": message, "priority": priority,
        "sent_to": channels_sent, "rate_limited": channels_blocked,
        "failed": channels_failed
    }


def list_channels(db):
    """List all notification channels."""
    rows = db.execute("SELECT name, enabled, config_json, send_count, last_send FROM channels").fetchall()
    channels = []
    for r in rows:
        channels.append({
            "name": r[0], "enabled": bool(r[1]),
            "config": json.loads(r[2]),
            "send_count": r[3],
            "last_send": datetime.fromtimestamp(r[4]).isoformat() if r[4] > 0 else "never"
        })
    return {"status": "ok", "channels": channels}


def get_history(db, limit=50):
    """Get notification history."""
    rows = db.execute(
        "SELECT id, ts, message, priority, channels_sent, source FROM notifications ORDER BY ts DESC LIMIT ?",
        (limit,)
    ).fetchall()
    history = []
    for r in rows:
        history.append({
            "id": r[0],
            "time": datetime.fromtimestamp(r[1]).isoformat(),
            "message": r[2], "priority": r[3],
            "channels": json.loads(r[4]), "source": r[5]
        })
    return {"status": "ok", "count": len(history), "history": history}


def once(db):
    """Run once: show channels, stats, send test notification."""
    channels = list_channels(db)
    total = db.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
    by_priority = {}
    for p in PRIORITY_LEVELS:
        cnt = db.execute("SELECT COUNT(*) FROM notifications WHERE priority=?", (p,)).fetchone()[0]
        by_priority[p] = cnt

    # Send a test info notification
    test_result = send_notification(db, "Notification hub health check", "info", "once_check")

    return {
        "status": "ok", "mode": "once",
        "total_notifications": total,
        "by_priority": by_priority,
        "channels": channels["channels"],
        "test_send": test_result
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Notification Hub (#184) — Multi-channel notifications")
    parser.add_argument("--send", type=str, help="Send a notification message")
    parser.add_argument("--priority", type=str, default="info", choices=["critical", "warning", "info"],
                        help="Notification priority")
    parser.add_argument("--channels", action="store_true", help="List notification channels")
    parser.add_argument("--history", action="store_true", help="Show notification history")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    db = init_db()

    if args.send:
        result = send_notification(db, args.send, args.priority)
    elif args.channels:
        result = list_channels(db)
    elif args.history:
        result = get_history(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))
    db.close()


if __name__ == "__main__":
    main()
