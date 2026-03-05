#!/usr/bin/env python3
"""jarvis_event_stream.py (#193) — Event bus SQLite-based.

Bus d'evenements avec publish/subscribe, TTL 1h, cleanup auto.
Table events avec ts, topic, payload, consumed.

Usage:
    python dev/jarvis_event_stream.py --once
    python dev/jarvis_event_stream.py --publish '{"topic":"system","data":"hello"}'
    python dev/jarvis_event_stream.py --subscribe system
    python dev/jarvis_event_stream.py --history
    python dev/jarvis_event_stream.py --stats
"""
import argparse
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "event_stream.db"

TTL_SECONDS = 3600  # 1 hour TTL for events
MAX_BATCH = 50  # Max events per subscribe call


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        topic TEXT NOT NULL,
        payload TEXT NOT NULL,
        consumed INTEGER DEFAULT 0,
        consumed_ts REAL,
        consumer TEXT,
        ttl_expires REAL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        created_ts REAL,
        last_event_ts REAL,
        total_published INTEGER DEFAULT 0,
        total_consumed INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS consumers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        topic TEXT NOT NULL,
        last_consumed_ts REAL,
        total_consumed INTEGER DEFAULT 0
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_topic ON events(topic)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_consumed ON events(consumed)")
    # Migrate: add missing columns if table existed before
    try:
        db.execute("ALTER TABLE events ADD COLUMN consumed_ts REAL")
    except sqlite3.OperationalError:
        pass  # column already exists
    try:
        db.execute("ALTER TABLE events ADD COLUMN consumer TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE events ADD COLUMN ttl_expires REAL")
    except sqlite3.OperationalError:
        pass
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_ttl ON events(ttl_expires)")
    db.commit()
    return db


def cleanup_expired(db):
    """Remove expired events (TTL passed)."""
    now = time.time()
    deleted = db.execute(
        "DELETE FROM events WHERE ttl_expires < ? AND ttl_expires > 0", (now,)
    ).rowcount
    if deleted > 0:
        db.commit()
    return deleted


def publish_event(db, event_data):
    """Publish an event to the bus."""
    cleanup_expired(db)

    # Parse event data
    if isinstance(event_data, str):
        try:
            event_data = json.loads(event_data)
        except json.JSONDecodeError:
            event_data = {"topic": "default", "data": event_data}

    topic = event_data.get("topic", "default")
    payload = event_data.get("data", event_data.get("payload", event_data))
    if isinstance(payload, dict) and "topic" in payload:
        payload = {k: v for k, v in payload.items() if k != "topic"}

    now = time.time()
    ttl_expires = now + TTL_SECONDS

    db.execute(
        """INSERT INTO events (ts, topic, payload, consumed, ttl_expires)
           VALUES (?,?,?,0,?)""",
        (now, topic, json.dumps(payload, ensure_ascii=False), ttl_expires)
    )

    # Update topic stats
    existing = db.execute("SELECT id FROM topics WHERE name = ?", (topic,)).fetchone()
    if existing:
        db.execute(
            "UPDATE topics SET last_event_ts = ?, total_published = total_published + 1 WHERE name = ?",
            (now, topic)
        )
    else:
        db.execute(
            "INSERT INTO topics (name, created_ts, last_event_ts, total_published) VALUES (?,?,?,1)",
            (topic, now, now)
        )

    db.commit()
    event_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    pending = db.execute(
        "SELECT COUNT(*) FROM events WHERE topic = ? AND consumed = 0 AND (ttl_expires > ? OR ttl_expires = 0)",
        (topic, now)
    ).fetchone()[0]

    return {
        "status": "ok",
        "event_id": event_id,
        "topic": topic,
        "ttl_expires": datetime.fromtimestamp(ttl_expires).strftime("%Y-%m-%d %H:%M:%S"),
        "pending_in_topic": pending
    }


def subscribe_topic(db, topic, consumer="default"):
    """Subscribe: read unconsumed events for a topic."""
    cleanup_expired(db)
    now = time.time()

    rows = db.execute(
        """SELECT id, ts, payload FROM events
           WHERE topic = ? AND consumed = 0
             AND (ttl_expires > ? OR ttl_expires = 0)
           ORDER BY ts ASC LIMIT ?""",
        (topic, now, MAX_BATCH)
    ).fetchall()

    events = []
    ids_to_mark = []

    for row in rows:
        eid, ts, payload_str = row
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            payload = payload_str

        events.append({
            "id": eid,
            "ts": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
            "payload": payload
        })
        ids_to_mark.append(eid)

    # Mark as consumed
    if ids_to_mark:
        placeholders = ",".join("?" for _ in ids_to_mark)
        db.execute(
            f"UPDATE events SET consumed = 1, consumed_ts = ?, consumer = ? WHERE id IN ({placeholders})",
            [now, consumer] + ids_to_mark
        )
        # Update topic stats
        db.execute(
            "UPDATE topics SET total_consumed = total_consumed + ? WHERE name = ?",
            (len(ids_to_mark), topic)
        )
        # Update consumer stats
        existing_consumer = db.execute(
            "SELECT id FROM consumers WHERE name = ? AND topic = ?", (consumer, topic)
        ).fetchone()
        if existing_consumer:
            db.execute(
                "UPDATE consumers SET last_consumed_ts = ?, total_consumed = total_consumed + ? WHERE name = ? AND topic = ?",
                (now, len(ids_to_mark), consumer, topic)
            )
        else:
            db.execute(
                "INSERT INTO consumers (name, topic, last_consumed_ts, total_consumed) VALUES (?,?,?,?)",
                (consumer, topic, now, len(ids_to_mark))
            )
        db.commit()

    remaining = db.execute(
        "SELECT COUNT(*) FROM events WHERE topic = ? AND consumed = 0 AND (ttl_expires > ? OR ttl_expires = 0)",
        (topic, now)
    ).fetchone()[0]

    return {
        "status": "ok",
        "topic": topic,
        "consumed": len(events),
        "remaining": remaining,
        "events": events
    }


def get_history(db, limit=30):
    """Get recent events across all topics."""
    now = time.time()
    cleanup_expired(db)

    rows = db.execute(
        """SELECT id, ts, topic, payload, consumed, consumer, ttl_expires
           FROM events ORDER BY ts DESC LIMIT ?""", (limit,)
    ).fetchall()

    return {
        "status": "ok",
        "total_events": db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "total_unconsumed": db.execute(
            "SELECT COUNT(*) FROM events WHERE consumed = 0 AND (ttl_expires > ? OR ttl_expires = 0)",
            (now,)
        ).fetchone()[0],
        "history": [
            {
                "id": r[0],
                "ts": datetime.fromtimestamp(r[1]).strftime("%Y-%m-%d %H:%M:%S"),
                "topic": r[2],
                "payload": r[3][:200],
                "consumed": bool(r[4]),
                "consumer": r[5],
                "expired": r[6] < now if r[6] and r[6] > 0 else False
            }
            for r in rows
        ]
    }


def get_stats(db):
    """Get event bus statistics."""
    now = time.time()
    cleanup_expired(db)

    topics = db.execute(
        "SELECT name, total_published, total_consumed, last_event_ts FROM topics ORDER BY total_published DESC"
    ).fetchall()

    consumers = db.execute(
        "SELECT name, topic, total_consumed, last_consumed_ts FROM consumers ORDER BY total_consumed DESC"
    ).fetchall()

    total = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    unconsumed = db.execute(
        "SELECT COUNT(*) FROM events WHERE consumed = 0 AND (ttl_expires > ? OR ttl_expires = 0)",
        (now,)
    ).fetchone()[0]
    expired = db.execute(
        "SELECT COUNT(*) FROM events WHERE ttl_expires < ? AND ttl_expires > 0", (now,)
    ).fetchone()[0]

    # Events per hour (last 24h)
    h24_ago = now - 86400
    rate = db.execute(
        "SELECT COUNT(*) FROM events WHERE ts > ?", (h24_ago,)
    ).fetchone()[0]

    return {
        "status": "ok",
        "total_events": total,
        "unconsumed": unconsumed,
        "expired_cleaned": expired,
        "events_last_24h": rate,
        "events_per_hour": round(rate / 24, 1) if rate > 0 else 0,
        "ttl_seconds": TTL_SECONDS,
        "topics": [
            {
                "name": t[0], "published": t[1], "consumed": t[2],
                "last_event": datetime.fromtimestamp(t[3]).strftime("%Y-%m-%d %H:%M:%S") if t[3] else None
            }
            for t in topics
        ],
        "consumers": [
            {
                "name": c[0], "topic": c[1], "consumed": c[2],
                "last_consumed": datetime.fromtimestamp(c[3]).strftime("%Y-%m-%d %H:%M:%S") if c[3] else None
            }
            for c in consumers
        ]
    }


def once(db):
    """Run once with demo publish/subscribe."""
    # Publish a demo event
    pub_result = publish_event(db, {
        "topic": "system",
        "data": {
            "type": "health_check",
            "source": "jarvis_event_stream",
            "message": "Event bus operational",
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    })

    stats = get_stats(db)

    return {
        "status": "ok",
        "mode": "once",
        "script": "jarvis_event_stream.py (#193)",
        "ttl_seconds": TTL_SECONDS,
        "max_batch": MAX_BATCH,
        "demo_publish": pub_result,
        "stats": stats
    }


def main():
    parser = argparse.ArgumentParser(
        description="jarvis_event_stream.py (#193) — Event bus SQLite-based"
    )
    parser.add_argument("--publish", type=str, metavar="EVENT",
                        help="Publish event JSON (or plain text to 'default' topic)")
    parser.add_argument("--subscribe", type=str, metavar="TOPIC",
                        help="Subscribe and consume events from topic")
    parser.add_argument("--consumer", type=str, default="default",
                        help="Consumer name for subscribe (default: 'default')")
    parser.add_argument("--history", action="store_true",
                        help="Show recent events across all topics")
    parser.add_argument("--stats", action="store_true",
                        help="Show event bus statistics")
    parser.add_argument("--once", action="store_true",
                        help="Run once with demo publish")
    args = parser.parse_args()

    db = init_db()

    if args.publish:
        result = publish_event(db, args.publish)
    elif args.subscribe:
        result = subscribe_topic(db, args.subscribe, args.consumer)
    elif args.history:
        result = get_history(db)
    elif args.stats:
        result = get_stats(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        db.close()
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
