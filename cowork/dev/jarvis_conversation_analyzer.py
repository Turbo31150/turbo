#!/usr/bin/env python3
"""jarvis_conversation_analyzer.py — Analyse les conversations JARVIS.

Detecte sujets recurrents, sentiment, tendances.

Usage:
    python dev/jarvis_conversation_analyzer.py --once
    python dev/jarvis_conversation_analyzer.py --analyze
    python dev/jarvis_conversation_analyzer.py --topics
    python dev/jarvis_conversation_analyzer.py --sentiment
"""
import argparse
import json
import os
import sqlite3
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
JARVIS_DB = Path("F:/BUREAU/turbo/data/jarvis.db")
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")
DB_PATH = DEV / "data" / "conversation_analyzer.db"

TOPIC_KEYWORDS = {
    "trading": ["trading", "mexc", "btc", "eth", "sol", "crypto", "futures", "position"],
    "cluster": ["cluster", "m1", "m2", "m3", "ollama", "gpu", "modele", "model"],
    "code": ["code", "script", "python", "dev", "bug", "fix", "function", "class"],
    "system": ["windows", "service", "process", "disk", "memory", "cpu", "ram"],
    "voice": ["voix", "commande", "whisper", "tts", "parle", "dis", "jarvis"],
    "telegram": ["telegram", "message", "bot", "envoie", "notification"],
}

SENTIMENT_WORDS = {
    "positive": ["bien", "parfait", "excellent", "ok", "merci", "super", "bravo", "genial"],
    "negative": ["erreur", "bug", "crash", "fail", "probleme", "merde", "nul", "lent"],
    "neutral": ["status", "rapport", "info", "check", "liste", "montre"],
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, messages_analyzed INTEGER, topics TEXT,
        sentiment TEXT, trends TEXT, report TEXT)""")
    db.commit()
    return db


def get_conversations():
    """Get recent conversations from databases."""
    messages = []
    for db_path in [JARVIS_DB, ETOILE_DB]:
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            for (table,) in tables:
                cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
                text_cols = [c for c in cols if any(k in c.lower() for k in ["text", "message", "query", "content"])]
                for col in text_cols:
                    rows = conn.execute(
                        f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL ORDER BY rowid DESC LIMIT 100"
                    ).fetchall()
                    for (val,) in rows:
                        if val and len(str(val)) > 3:
                            messages.append(str(val)[:300])
            conn.close()
        except Exception:
            continue
    return messages


def detect_topics(messages):
    """Detect topics from messages."""
    topic_counts = Counter()
    for msg in messages:
        msg_lower = msg.lower()
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(kw in msg_lower for kw in keywords):
                topic_counts[topic] += 1
    return dict(topic_counts.most_common(10))


def analyze_sentiment(messages):
    """Analyze sentiment distribution."""
    sentiments = Counter()
    for msg in messages:
        msg_lower = msg.lower()
        for sentiment, words in SENTIMENT_WORDS.items():
            if any(w in msg_lower for w in words):
                sentiments[sentiment] += 1
                break
        else:
            sentiments["neutral"] += 1
    total = sum(sentiments.values())
    return {k: {"count": v, "pct": round(v / max(total, 1) * 100, 1)} for k, v in sentiments.items()}


def do_analyze():
    """Full conversation analysis."""
    db = init_db()
    messages = get_conversations()
    topics = detect_topics(messages)
    sentiment = analyze_sentiment(messages)

    report = {
        "ts": datetime.now().isoformat(),
        "messages_analyzed": len(messages),
        "topics": topics,
        "sentiment": sentiment,
        "top_topic": max(topics, key=topics.get) if topics else "none",
    }

    db.execute(
        "INSERT INTO analyses (ts, messages_analyzed, topics, sentiment, trends, report) VALUES (?,?,?,?,?,?)",
        (time.time(), len(messages), json.dumps(topics), json.dumps(sentiment), "{}", json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS Conversation Analyzer")
    parser.add_argument("--once", "--analyze", action="store_true", help="Full analysis")
    parser.add_argument("--topics", action="store_true", help="Topics only")
    parser.add_argument("--sentiment", action="store_true", help="Sentiment only")
    args = parser.parse_args()

    result = do_analyze()
    if args.topics:
        print(json.dumps({"topics": result["topics"]}, indent=2))
    elif args.sentiment:
        print(json.dumps({"sentiment": result["sentiment"]}, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
