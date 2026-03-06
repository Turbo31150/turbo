#!/usr/bin/env python3
"""JARVIS Conversation Memory — Long-term memory for conversations.

Stores conversation summaries, extracts key facts, builds user profile,
and provides context for future interactions.
"""
import argparse
import json
import sqlite3
import time
import hashlib
from pathlib import Path

DB_PATH = Path(__file__).parent / "conversation_memory.db"
from _paths import TURBO_DIR as TURBO

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY, ts REAL, source TEXT,
        summary TEXT, topics TEXT, sentiment TEXT,
        key_facts TEXT, duration_s REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY, ts REAL, category TEXT,
        fact TEXT, confidence REAL, source TEXT,
        last_referenced REAL, reference_count INTEGER DEFAULT 1)""")
    db.execute("""CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT,
        confidence REAL, updated_at REAL)""")
    db.commit()
    return db

def store_conversation(db, source, summary, topics, key_facts):
    """Store a conversation summary."""
    db.execute(
        "INSERT INTO conversations (ts, source, summary, topics, key_facts) VALUES (?,?,?,?,?)",
        (time.time(), source, summary[:500], json.dumps(topics), json.dumps(key_facts)))
    # Extract and store facts
    for fact in key_facts:
        if isinstance(fact, str) and len(fact) > 5:
            h = hashlib.md5(fact.encode()).hexdigest()[:8]
            existing = db.execute("SELECT id, reference_count FROM facts WHERE fact=?", (fact,)).fetchone()
            if existing:
                db.execute("UPDATE facts SET reference_count=reference_count+1, last_referenced=? WHERE id=?",
                           (time.time(), existing[0]))
            else:
                db.execute(
                    "INSERT INTO facts (ts, category, fact, confidence, source, last_referenced) VALUES (?,?,?,?,?,?)",
                    (time.time(), "conversation", fact[:200], 0.8, source, time.time()))
    db.commit()

def update_profile(db, key, value, confidence=1.0):
    """Update user profile."""
    db.execute(
        "INSERT OR REPLACE INTO user_profile (key, value, confidence, updated_at) VALUES (?,?,?,?)",
        (key, str(value), confidence, time.time()))
    db.commit()

def get_profile(db):
    """Get full user profile."""
    rows = db.execute("SELECT key, value, confidence FROM user_profile ORDER BY key").fetchall()
    return {r[0]: {"value": r[1], "confidence": r[2]} for r in rows}

def get_recent_facts(db, limit=20):
    """Get most recent/referenced facts."""
    return db.execute(
        "SELECT fact, category, confidence, reference_count FROM facts ORDER BY reference_count DESC, ts DESC LIMIT ?",
        (limit,)).fetchall()

def scan_telegram_history(db):
    """Scan Telegram bot history for conversations."""
    try:
        edb = sqlite3.connect(str(TURBO / "data" / "etoile.db"))
        # Check for telegram messages table
        tables = [r[0] for r in edb.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "telegram_messages" in tables:
            rows = edb.execute(
                "SELECT text, timestamp FROM telegram_messages ORDER BY timestamp DESC LIMIT 50"
            ).fetchall()
            for text, ts in rows:
                if text and len(text) > 10:
                    # Simple topic extraction
                    topics = []
                    if any(w in text.lower() for w in ["code", "python", "script"]):
                        topics.append("coding")
                    if any(w in text.lower() for w in ["trading", "btc", "crypto"]):
                        topics.append("trading")
                    if any(w in text.lower() for w in ["cluster", "gpu", "noeud"]):
                        topics.append("infrastructure")
                    store_conversation(db, "telegram", text[:200], topics, [])
            edb.close()
            return len(rows)
    except Exception:
        pass
    return 0

def init_user_profile(db):
    """Initialize known user profile facts."""
    known = {
        "name": "Turbo",
        "language": "fr",
        "ai_name": "JARVIS",
        "voice": "fr-FR-DeniseNeural",
        "workspace": "F:\\BUREAU\\turbo",
        "gpu_count": "10",
        "cluster_nodes": "M1,M2,M3,OL1",
        "trading_pairs": "BTC,ETH,SOL,SUI,PEPE,DOGE,XRP,ADA,AVAX,LINK",
    }
    for k, v in known.items():
        update_profile(db, k, v, 1.0)

def main():
    parser = argparse.ArgumentParser(description="JARVIS Conversation Memory")
    parser.add_argument("--init", action="store_true", help="Initialize user profile")
    parser.add_argument("--profile", action="store_true", help="Show user profile")
    parser.add_argument("--facts", action="store_true", help="Show top facts")
    parser.add_argument("--scan", action="store_true", help="Scan Telegram history")
    parser.add_argument("--store", nargs=2, metavar=("KEY", "VALUE"), help="Store profile fact")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=3600)
    args = parser.parse_args()

    db = init_db()

    if args.init:
        init_user_profile(db)
        print("User profile initialized")

    if args.store:
        update_profile(db, args.store[0], args.store[1])
        print(f"Stored: {args.store[0]} = {args.store[1]}")

    if args.profile or args.once:
        profile = get_profile(db)
        print("=== User Profile ===")
        for k, v in profile.items():
            print(f"  {k}: {v['value']} ({v['confidence']:.0%})")

    if args.facts:
        facts = get_recent_facts(db)
        print(f"=== Top Facts ({len(facts)}) ===")
        for fact, cat, conf, refs in facts:
            print(f"  [{cat}] {fact} (x{refs}, {conf:.0%})")

    if args.scan or args.once:
        n = scan_telegram_history(db)
        print(f"Scanned {n} Telegram messages")

    if args.loop:
        while True:
            try:
                scan_telegram_history(db)
                ts = time.strftime('%H:%M')
                facts = get_recent_facts(db, 5)
                print(f"[{ts}] Memory: {len(facts)} top facts")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
