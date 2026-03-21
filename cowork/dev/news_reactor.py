#!/usr/bin/env python3
"""news_reactor.py — Tech news monitor + auto-commentary generator.

Fetches latest tech/AI/crypto news via OL1 minimax cloud, generates
LinkedIn-style commentaries via M1, stores in etoile.db.

Usage:
    python dev/news_reactor.py --once
    python dev/news_reactor.py --post
    python dev/news_reactor.py --topics
"""
import argparse
import json
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "etoile.db"
OL1_URL = "http://127.0.0.1:11434"
M1_URL = "http://127.0.0.1:1234"
BROWSEROS_URL = "http://192.168.1.85:9000"

TOPICS = ["AI", "LLM", "Crypto", "DevOps", "Python", "Cybersecurity", "Cloud", "Startups"]


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
        source TEXT DEFAULT 'jarvis', confidence REAL DEFAULT 1.0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(category, key))""")
    db.commit()
    return db


def call_ol1(prompt, timeout=60):
    """Call OL1 minimax cloud for web-enabled search."""
    body = json.dumps({
        "model": "minimax-m2.5:cloud",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False, "think": False
    }).encode()
    req = urllib.request.Request(f"{OL1_URL}/api/chat", data=body,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        return data.get("message", {}).get("content", "")
    except Exception as e:
        return f"[OL1 ERROR] {e}"


def call_m1(prompt, max_tokens=512, timeout=30):
    """Call M1 qwen3-8b for commentary generation."""
    body = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink\n{prompt}",
        "temperature": 0.4, "max_output_tokens": max_tokens,
        "stream": False, "store": False
    }).encode()
    req = urllib.request.Request(f"{M1_URL}/api/v1/chat", data=body,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        for block in reversed(data.get("output", [])):
            if block.get("type") == "message":
                for c in block.get("content", []):
                    if c.get("type") == "output_text":
                        return c["text"]
        return str(data)
    except Exception as e:
        return f"[M1 ERROR] {e}"


def fetch_news():
    """Fetch latest tech news via OL1 minimax cloud."""
    prompt = (
        "List the 5 most important tech news from today about: "
        f"{', '.join(TOPICS)}. "
        "For each: title, 1-line summary, source. Format as JSON array with "
        "keys: title, summary, source, topic. Only JSON, no markdown."
    )
    raw = call_ol1(prompt, timeout=90)
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return [{"title": line.strip(), "summary": "", "source": "minimax", "topic": "tech"}
                for line in raw.split("\n") if line.strip() and not line.startswith("[")][:5]


def generate_commentary(news_item):
    """Generate a LinkedIn-style commentary for a news item."""
    prompt = (
        f"Write a LinkedIn post commentary (3-5 lines + hashtags) about this news:\n"
        f"Title: {news_item.get('title', '')}\n"
        f"Summary: {news_item.get('summary', '')}\n"
        f"Topic: {news_item.get('topic', '')}\n\n"
        "Be professional, insightful, add a personal take. End with 3-5 relevant hashtags. "
        "Write in French. No markdown formatting."
    )
    return call_m1(prompt, max_tokens=400)


def store_commentary(db, news_item, commentary):
    """Store commentary in etoile.db memories."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    key = f"news_{ts}_{news_item.get('topic', 'tech')}"
    value = json.dumps({
        "title": news_item.get("title", ""),
        "summary": news_item.get("summary", ""),
        "commentary": commentary,
        "source": news_item.get("source", ""),
        "generated_at": datetime.now().isoformat()
    }, ensure_ascii=False)
    try:
        db.execute("INSERT OR REPLACE INTO memories (category, key, value, source) VALUES (?, ?, ?, ?)",
                   ("news_commentary", key, value, "news_reactor"))
        db.commit()
    except sqlite3.Error:
        pass


def cmd_once(args):
    """Fetch news, generate commentaries, store them."""
    db = get_db()
    print("Fetching latest tech news via OL1 minimax...", file=sys.stderr)
    news = fetch_news()
    results = []
    for item in news[:5]:
        print(f"  Generating commentary: {item.get('title', '?')[:60]}...", file=sys.stderr)
        commentary = generate_commentary(item)
        store_commentary(db, item, commentary)
        results.append({"title": item.get("title", ""), "topic": item.get("topic", ""),
                        "commentary": commentary[:200] + "..." if len(commentary) > 200 else commentary})
    db.close()
    output = {"news_count": len(news), "commentaries_generated": len(results),
              "topics": list({r["topic"] for r in results}), "items": results}
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_post(args):
    """Publish latest commentaries to LinkedIn via BrowserOS."""
    db = get_db()
    rows = db.execute(
        "SELECT key, value FROM memories WHERE category='news_commentary' "
        "ORDER BY created_at DESC LIMIT 3").fetchall()
    db.close()
    posted = []
    for key, val in rows:
        data = json.loads(val)
        text = data.get("commentary", "")
        if not text:
            continue
        body = json.dumps({"url": "https://www.linkedin.com/feed/", "action": "navigate"}).encode()
        try:
            req = urllib.request.Request(f"{BROWSEROS_URL}/mcp", data=body,
                                        headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass
        posted.append({"key": key, "title": data.get("title", ""), "status": "queued"})
    output = {"posted": len(posted), "items": posted}
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_topics(args):
    """List monitored topics."""
    output = {"topics": TOPICS, "count": len(TOPICS)}
    print(json.dumps(output, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Tech news monitor + commentary generator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Fetch news + generate commentaries")
    group.add_argument("--post", action="store_true", help="Publish to LinkedIn via BrowserOS")
    group.add_argument("--topics", action="store_true", help="List monitored topics")
    args = parser.parse_args()
    if args.once:
        cmd_once(args)
    elif args.post:
        cmd_post(args)
    elif args.topics:
        cmd_topics(args)


if __name__ == "__main__":
    main()
