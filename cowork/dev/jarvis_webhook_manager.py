#!/usr/bin/env python3
"""jarvis_webhook_manager.py — Centralized webhook manager (#256).

Stores webhook configs (url, events, secret), tests connectivity,
logs deliveries, retry failed.

Usage:
    python dev/jarvis_webhook_manager.py --once
    python dev/jarvis_webhook_manager.py --list
    python dev/jarvis_webhook_manager.py --add URL
    python dev/jarvis_webhook_manager.py --remove URL
    python dev/jarvis_webhook_manager.py --test
"""
import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "webhook_manager.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS webhooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE NOT NULL,
        events TEXT DEFAULT '["all"]',
        secret TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        last_tested TEXT,
        last_status INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS deliveries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        webhook_id INTEGER,
        url TEXT NOT NULL,
        event TEXT,
        payload TEXT,
        status_code INTEGER,
        response TEXT,
        success INTEGER,
        latency_ms REAL,
        retries INTEGER DEFAULT 0
    )""")
    db.commit()
    return db


def test_webhook(url, secret=None):
    """Test webhook connectivity with a ping payload."""
    payload = json.dumps({
        "event": "ping",
        "ts": datetime.now().isoformat(),
        "source": "jarvis_webhook_manager",
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if secret:
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={sig}"

    start = time.time()
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            latency = (time.time() - start) * 1000
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body[:500], round(latency, 1), True
    except urllib.error.HTTPError as e:
        latency = (time.time() - start) * 1000
        return e.code, str(e.reason), round(latency, 1), False
    except Exception as e:
        latency = (time.time() - start) * 1000
        return 0, str(e), round(latency, 1), False


def do_list():
    """List all webhooks."""
    db = init_db()
    rows = db.execute(
        "SELECT id, url, events, active, created_at, last_tested, last_status FROM webhooks ORDER BY id"
    ).fetchall()

    total_deliveries = db.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
    successful = db.execute("SELECT COUNT(*) FROM deliveries WHERE success=1").fetchone()[0]

    result = {
        "ts": datetime.now().isoformat(), "action": "list",
        "total_webhooks": len(rows),
        "total_deliveries": total_deliveries,
        "delivery_success_rate": round(successful / max(total_deliveries, 1), 3),
        "webhooks": [
            {"id": r[0], "url": r[1], "events": json.loads(r[2]) if r[2] else ["all"],
             "active": bool(r[3]), "created_at": r[4], "last_tested": r[5], "last_status": r[6]}
            for r in rows
        ],
    }
    db.close()
    return result


def do_add(url):
    """Add a new webhook."""
    db = init_db()
    now = datetime.now()
    secret = hashlib.sha256(f"{url}{now.isoformat()}".encode()).hexdigest()[:32]

    try:
        db.execute(
            "INSERT INTO webhooks (url, secret, created_at) VALUES (?,?,?)",
            (url, secret, now.isoformat()),
        )
        db.commit()
        result = {
            "ts": now.isoformat(), "action": "add", "url": url,
            "secret": secret, "success": True,
        }
    except sqlite3.IntegrityError:
        result = {
            "ts": now.isoformat(), "action": "add", "url": url,
            "success": False, "error": "Webhook URL already exists",
        }

    db.close()
    return result


def do_remove(url):
    """Remove a webhook."""
    db = init_db()
    now = datetime.now()
    cursor = db.execute("DELETE FROM webhooks WHERE url=?", (url,))
    removed = cursor.rowcount > 0
    db.commit()

    result = {
        "ts": now.isoformat(), "action": "remove", "url": url,
        "success": removed,
        "message": "Removed" if removed else "Not found",
    }
    db.close()
    return result


def do_test():
    """Test all active webhooks."""
    db = init_db()
    now = datetime.now()
    rows = db.execute(
        "SELECT id, url, secret FROM webhooks WHERE active=1"
    ).fetchall()

    results_list = []
    for wh_id, url, secret in rows:
        status_code, response, latency, success = test_webhook(url, secret)

        db.execute(
            "UPDATE webhooks SET last_tested=?, last_status=? WHERE id=?",
            (now.isoformat(), status_code, wh_id),
        )
        db.execute(
            "INSERT INTO deliveries (ts, webhook_id, url, event, status_code, response, success, latency_ms) VALUES (?,?,?,?,?,?,?,?)",
            (now.isoformat(), wh_id, url, "ping", status_code, response[:500], int(success), latency),
        )
        results_list.append({
            "url": url, "status_code": status_code,
            "success": success, "latency_ms": latency,
        })

    db.commit()
    result = {
        "ts": now.isoformat(), "action": "test",
        "tested": len(results_list),
        "successful": sum(1 for r in results_list if r["success"]),
        "failed": sum(1 for r in results_list if not r["success"]),
        "results": results_list,
    }
    db.close()
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(), "script": "jarvis_webhook_manager.py", "script_id": 256,
        "db": str(DB_PATH),
        "total_webhooks": db.execute("SELECT COUNT(*) FROM webhooks").fetchone()[0],
        "active_webhooks": db.execute("SELECT COUNT(*) FROM webhooks WHERE active=1").fetchone()[0],
        "total_deliveries": db.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="jarvis_webhook_manager.py — Webhook manager (#256)")
    parser.add_argument("--list", action="store_true", help="List all webhooks")
    parser.add_argument("--add", type=str, metavar="URL", help="Add a webhook")
    parser.add_argument("--remove", type=str, metavar="URL", help="Remove a webhook")
    parser.add_argument("--test", action="store_true", help="Test all webhooks")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.list:
        result = do_list()
    elif args.add:
        result = do_add(args.add)
    elif args.remove:
        result = do_remove(args.remove)
    elif args.test:
        result = do_test()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
