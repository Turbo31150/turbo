#!/usr/bin/env python3
"""jarvis_message_router.py — Routage intelligent des messages JARVIS.

Decide si reponse texte, vocal (TTS), notification Windows, ou Telegram.

Usage:
    python dev/jarvis_message_router.py --once
    python dev/jarvis_message_router.py --route "Le GPU est a 85 degres"
    python dev/jarvis_message_router.py --history
"""
import argparse
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "message_router.db"
TELEGRAM_PROXY = "http://127.0.0.1:18800"
WS_URL = "http://127.0.0.1:9742"

URGENCY_KEYWORDS = {
    "critical": ["crash", "offline", "down", "erreur critique", "echec", "failed", "alert"],
    "high": ["warning", "attention", "alerte", "gpu chaud", "temperature", "degradation"],
    "medium": ["rapport", "status", "resultat", "mise a jour", "update"],
    "low": ["info", "note", "suggestion", "recommandation"],
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, message TEXT, urgency TEXT,
        channel TEXT, delivered INTEGER)""")
    db.commit()
    return db


def classify_urgency(message):
    """Classify message urgency."""
    msg_lower = message.lower()
    for level, keywords in URGENCY_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            return level
    return "low"


def choose_channel(message, urgency):
    """Choose delivery channel based on message + urgency."""
    length = len(message)

    if urgency == "critical":
        return ["telegram", "tts"]  # Both for critical
    elif urgency == "high":
        if length < 100:
            return ["tts"]  # Short + urgent = voice
        return ["telegram"]
    elif urgency == "medium":
        return ["telegram"]
    else:
        if length < 50:
            return ["log"]  # Just log for low priority short messages
        return ["telegram"]


def send_telegram(message):
    """Send via Telegram proxy."""
    try:
        data = json.dumps({"text": message}).encode()
        req = urllib.request.Request(
            f"{TELEGRAM_PROXY}/chat", data=data,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def send_tts(message):
    """Send via TTS (FastAPI WS)."""
    try:
        data = json.dumps({"text": message}).encode()
        req = urllib.request.Request(
            f"{WS_URL}/api/tts/speak", data=data,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def route_message(message):
    """Route a message to appropriate channels."""
    db = init_db()
    urgency = classify_urgency(message)
    channels = choose_channel(message, urgency)
    delivered = []

    for ch in channels:
        ok = False
        if ch == "telegram":
            ok = send_telegram(message)
        elif ch == "tts":
            ok = send_tts(message)
        elif ch == "log":
            ok = True  # Just logged in DB
        delivered.append({"channel": ch, "ok": ok})

    db.execute(
        "INSERT INTO routes (ts, message, urgency, channel, delivered) VALUES (?,?,?,?,?)",
        (time.time(), message[:500], urgency, json.dumps(channels), int(any(d["ok"] for d in delivered)))
    )
    db.commit()
    db.close()

    return {
        "message": message[:200],
        "urgency": urgency,
        "channels": channels,
        "delivered": delivered,
    }


def get_history():
    """Get routing history."""
    db = init_db()
    rows = db.execute("SELECT ts, message, urgency, channel FROM routes ORDER BY ts DESC LIMIT 20").fetchall()
    db.close()
    return [{"ts": datetime.fromtimestamp(r[0]).isoformat() if r[0] else None,
             "message": r[1][:100], "urgency": r[2], "channels": json.loads(r[3]) if r[3] else []}
            for r in rows]


def main():
    parser = argparse.ArgumentParser(description="JARVIS Message Router")
    parser.add_argument("--once", action="store_true", help="Show status")
    parser.add_argument("--route", metavar="MSG", help="Route a message")
    parser.add_argument("--history", action="store_true", help="Routing history")
    args = parser.parse_args()

    if args.route:
        result = route_message(args.route)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.history:
        result = get_history()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = get_history()
        print(json.dumps({"history": result, "channels": ["telegram", "tts", "log"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
