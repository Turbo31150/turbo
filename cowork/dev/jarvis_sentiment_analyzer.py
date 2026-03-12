#!/usr/bin/env python3
"""jarvis_sentiment_analyzer.py — Analyseur de sentiment JARVIS.

Detecte le ton des messages utilisateur.

Usage:
    python dev/jarvis_sentiment_analyzer.py --once
    python dev/jarvis_sentiment_analyzer.py --analyze "TEXT"
    python dev/jarvis_sentiment_analyzer.py --batch
    python dev/jarvis_sentiment_analyzer.py --trends
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "sentiment_analyzer.db"

POSITIVE_WORDS = {
    "merci", "super", "genial", "parfait", "excellent", "bravo", "cool", "top",
    "bien", "bon", "beau", "formidable", "incroyable", "magnifique", "great",
    "nice", "good", "perfect", "amazing", "awesome", "thanks", "love",
}
NEGATIVE_WORDS = {
    "merde", "bug", "erreur", "crash", "nul", "lent", "probleme", "echec",
    "fail", "error", "broken", "slow", "bad", "wrong", "worst", "terrible",
    "horrible", "pourquoi", "marche pas", "fonctionne pas", "impossible",
}
FRUSTRATION_MARKERS = {"!!!", "???", "!?", "wtf", "putain", "bordel", "fuck"}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS sentiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, text TEXT, score REAL,
        category TEXT, markers TEXT)""")
    db.commit()
    return db


def analyze_sentiment(text):
    words = set(text.lower().split())
    score = 0.0
    markers = []

    pos_count = len(words & POSITIVE_WORDS)
    neg_count = len(words & NEGATIVE_WORDS)

    score = (pos_count - neg_count) / max(pos_count + neg_count, 1)

    # Frustration detection
    text_lower = text.lower()
    for marker in FRUSTRATION_MARKERS:
        if marker in text_lower:
            markers.append(marker)
            score -= 0.2

    # Punctuation intensity
    if text.count("!") > 2:
        markers.append("excessive_exclamation")
    if text.count("?") > 2:
        markers.append("excessive_question")
    if text.upper() == text and len(text) > 5:
        markers.append("ALL_CAPS")
        score -= 0.3

    score = max(-1.0, min(1.0, score))

    if score > 0.3:
        category = "positive"
    elif score < -0.3:
        category = "negative"
    else:
        category = "neutral"

    return {
        "score": round(score, 2),
        "category": category,
        "positive_words": list(words & POSITIVE_WORDS),
        "negative_words": list(words & NEGATIVE_WORDS),
        "frustration_markers": markers,
    }


def do_analyze(text=None):
    db = init_db()
    if not text:
        text = "Tout fonctionne bien, merci JARVIS"

    result = analyze_sentiment(text)

    db.execute("INSERT INTO sentiments (ts, text, score, category, markers) VALUES (?,?,?,?,?)",
               (time.time(), text[:200], result["score"], result["category"],
                json.dumps(result["frustration_markers"])))
    db.commit()

    # Trends
    rows = db.execute(
        "SELECT AVG(score), COUNT(*) FROM sentiments WHERE ts > ?",
        (time.time() - 86400,)
    ).fetchone()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "text": text[:100],
        "analysis": result,
        "today_avg_score": round(rows[0] or 0, 2),
        "today_messages": rows[1] or 0,
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Sentiment Analyzer")
    parser.add_argument("--once", "--batch", action="store_true", help="Batch analyze")
    parser.add_argument("--analyze", metavar="TEXT", help="Analyze text")
    parser.add_argument("--history", action="store_true", help="History")
    parser.add_argument("--trends", action="store_true", help="Trends")
    args = parser.parse_args()

    if args.analyze:
        print(json.dumps(do_analyze(args.analyze), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_analyze(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
