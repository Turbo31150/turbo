#!/usr/bin/env python3
"""JARVIS Context Engine — Moteur de contexte persistant (conversations + preferences)."""
import json, sys, os, sqlite3
from datetime import datetime
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT

DB_PATH = "C:/Users/franc/.openclaw/workspace/dev/context.db"
# TELEGRAM_TOKEN loaded from _paths (.env)
# TELEGRAM_CHAT loaded from _paths (.env)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        source TEXT DEFAULT 'telegram',
        topic TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS preferences (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        fact TEXT NOT NULL,
        confidence REAL DEFAULT 1.0,
        source TEXT,
        created TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT UNIQUE NOT NULL,
        last_mentioned TEXT NOT NULL,
        mention_count INTEGER DEFAULT 1
    )""")
    conn.commit()
    return conn

def add_message(conn, role, content, source="telegram", topic=None):
    c = conn.cursor()
    c.execute("INSERT INTO conversations (ts, role, content, source, topic) VALUES (?, ?, ?, ?, ?)",
              (datetime.now().isoformat(), role, content, source, topic))
    conn.commit()
    return c.lastrowid

def add_preference(conn, key, value):
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO preferences (key, value, updated) VALUES (?, ?, ?)",
              (key, json.dumps(value) if not isinstance(value, str) else value, datetime.now().isoformat()))
    conn.commit()

def get_preference(conn, key, default=None):
    c = conn.cursor()
    c.execute("SELECT value FROM preferences WHERE key = ?", (key,))
    row = c.fetchone()
    if row:
        try: return json.loads(row[0])
        except: return row[0]
    return default

def add_fact(conn, category, fact, confidence=1.0, source=None):
    c = conn.cursor()
    c.execute("INSERT INTO facts (category, fact, confidence, source, created) VALUES (?, ?, ?, ?, ?)",
              (category, fact, confidence, source, datetime.now().isoformat()))
    conn.commit()

def get_facts(conn, category=None, limit=20):
    c = conn.cursor()
    if category:
        c.execute("SELECT category, fact, confidence FROM facts WHERE category = ? ORDER BY created DESC LIMIT ?",
                  (category, limit))
    else:
        c.execute("SELECT category, fact, confidence FROM facts ORDER BY created DESC LIMIT ?", (limit,))
    return [{"category": r[0], "fact": r[1], "confidence": r[2]} for r in c.fetchall()]

def track_topic(conn, topic):
    c = conn.cursor()
    c.execute("""INSERT INTO topics (topic, last_mentioned, mention_count) VALUES (?, ?, 1)
                 ON CONFLICT(topic) DO UPDATE SET last_mentioned=excluded.last_mentioned, mention_count=mention_count+1""",
              (topic, datetime.now().isoformat()))
    conn.commit()

def get_recent_context(conn, limit=10):
    c = conn.cursor()
    c.execute("SELECT ts, role, content, source FROM conversations ORDER BY id DESC LIMIT ?", (limit,))
    return [{"ts": r[0], "role": r[1], "content": r[2], "source": r[3]} for r in c.fetchall()][::-1]

def get_hot_topics(conn, limit=5):
    c = conn.cursor()
    c.execute("SELECT topic, mention_count, last_mentioned FROM topics ORDER BY mention_count DESC LIMIT ?", (limit,))
    return [{"topic": r[0], "count": r[1], "last": r[2]} for r in c.fetchall()]

def get_stats(conn):
    c = conn.cursor()
    stats = {}
    for table in ["conversations", "preferences", "facts", "topics"]:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        stats[table] = c.fetchone()[0]
    return stats

if __name__ == "__main__":
    conn = init_db()

    if "--stats" in sys.argv:
        stats = get_stats(conn)
        print(f"[CONTEXT ENGINE] Stats:")
        for k, v in stats.items():
            print(f"  {k}: {v} entries")

    elif "--add-pref" in sys.argv:
        idx = sys.argv.index("--add-pref")
        if len(sys.argv) > idx + 2:
            key, value = sys.argv[idx+1], sys.argv[idx+2]
            add_preference(conn, key, value)
            print(f"Preference '{key}' = '{value}' saved")
        else:
            print("Usage: --add-pref <key> <value>")

    elif "--add-fact" in sys.argv:
        idx = sys.argv.index("--add-fact")
        if len(sys.argv) > idx + 2:
            cat, fact = sys.argv[idx+1], " ".join(sys.argv[idx+2:])
            add_fact(conn, cat, fact)
            print(f"Fact [{cat}]: {fact}")
        else:
            print("Usage: --add-fact <category> <fact text>")

    elif "--context" in sys.argv:
        msgs = get_recent_context(conn, limit=20)
        topics = get_hot_topics(conn)
        print(f"[CONTEXT ENGINE] Last {len(msgs)} messages:")
        for m in msgs:
            print(f"  [{m['ts'][:16]}] {m['role']}: {m['content'][:80]}")
        if topics:
            print(f"\nHot topics:")
            for t in topics:
                print(f"  {t['topic']}: {t['count']}x (last: {t['last'][:16]})")

    elif "--facts" in sys.argv:
        cat = sys.argv[sys.argv.index("--facts") + 1] if len(sys.argv) > sys.argv.index("--facts") + 1 else None
        facts = get_facts(conn, category=cat)
        print(f"[CONTEXT ENGINE] {len(facts)} facts" + (f" [{cat}]" if cat else ""))
        for f in facts:
            print(f"  [{f['category']}] {f['fact']} (conf: {f['confidence']})")

    else:
        print("Usage: context_engine.py --stats | --context | --facts [category]")
        print("       --add-pref <key> <value> | --add-fact <category> <text>")

    conn.close()