#!/usr/bin/env python3
"""auto_publisher.py — Content publishing pipeline.

Checks content queue in etoile.db, publishes pending items to the right
platform, and can generate new posts via M1.

Usage:
  python dev/auto_publisher.py --once
  python dev/auto_publisher.py --schedule
  python dev/auto_publisher.py --generate 3
"""

import argparse, json, os, sqlite3, subprocess, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "etoile.db"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = 2010747443
M1_URL = "http://127.0.0.1:1234/api/v1/chat"

TEMPLATES = {
    "linkedin": "Write a professional LinkedIn post (150 words max) about: {topic}. "
                "Tone: insightful, expert. Include a call-to-action. No hashtags spam.",
    "github":   "Write a concise GitHub discussion post about: {topic}. "
                "Tone: technical, clear. Include code context if relevant.",
    "telegram": "Write a short Telegram message (80 words max) about: {topic}. "
                "Tone: direct, informative. Use minimal formatting.",
}

def _post(url, payload, timeout=30):
    req = urllib.request.Request(url, json.dumps(payload).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None

def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS memories "
                 "(id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, "
                 "key TEXT NOT NULL, value TEXT NOT NULL, source TEXT DEFAULT 'jarvis', "
                 "confidence REAL DEFAULT 1.0, created_at TEXT DEFAULT (datetime('now')), "
                 "updated_at TEXT DEFAULT (datetime('now')), UNIQUE(category, key))")
    return conn

def _ask_m1(prompt):
    resp = _post(M1_URL, {"model": "qwen3-8b", "input": f"/nothink\n{prompt}",
                          "temperature": 0.5, "max_output_tokens": 1024,
                          "stream": False, "store": False})
    if not resp:
        return ""
    for block in reversed(resp.get("output", [])):
        if block.get("type") == "message":
            for c in block.get("content", []):
                if c.get("type") == "output_text":
                    return c.get("text", "")
    return ""

def get_pending():
    conn = _db()
    rows = conn.execute(
        "SELECT key, value FROM memories WHERE category='content_queue' "
        "AND key LIKE 'pending_%' ORDER BY created_at").fetchall()
    conn.close()
    items = []
    for k, v in rows:
        try:
            data = json.loads(v)
        except json.JSONDecodeError:
            data = {"content": v, "platform": "telegram"}
        data["_key"] = k
        items.append(data)
    return items

def publish_telegram(item):
    if not TELEGRAM_TOKEN:
        return False
    text = item.get("content", "")[:4000]
    url = (f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?"
           f"chat_id={TELEGRAM_CHAT}&text={urllib.request.quote(text)}")
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception:
        return False

def publish_github(item):
    content = item.get("content", "")
    repo = item.get("repo", "Turbo31150/bibliotheque-prompts-multi-ia")
    title = item.get("title", "Auto-published content")
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{repo}/discussions", "-X", "POST",
             "-f", f"title={title}", "-f", f"body={content}", "-f", "categoryId=1"],
            capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False

def publish_linkedin(item):
    # LinkedIn publishing requires BrowserOS MCP (browser automation)
    # Store intent for BrowserOS to pick up
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO memories (category, key, value) VALUES (?, ?, ?)",
                 ("browseros_queue", f"linkedin_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                  json.dumps({"action": "linkedin_post", "content": item.get("content", "")})))
    conn.commit(); conn.close()
    return True  # Queued for BrowserOS

PUBLISHERS = {"telegram": publish_telegram, "github": publish_github, "linkedin": publish_linkedin}

def mark_published(key):
    conn = _db()
    row = conn.execute("SELECT value FROM memories WHERE category='content_queue' AND key=?",
                       (key,)).fetchone()
    if row:
        new_key = key.replace("pending_", "published_", 1)
        conn.execute("DELETE FROM memories WHERE category='content_queue' AND key=?", (key,))
        conn.execute("INSERT OR REPLACE INTO memories (category, key, value) VALUES (?, ?, ?)",
                     ("published", new_key, row[0]))
        conn.commit()
    conn.close()

def run_once():
    results = {"queued": 0, "published": 0, "failed": 0, "platforms": []}
    pending = get_pending()
    results["queued"] = len(pending)
    for item in pending:
        platform = item.get("platform", "telegram")
        pub_fn = PUBLISHERS.get(platform, publish_telegram)
        ok = pub_fn(item)
        if ok:
            mark_published(item["_key"])
            results["published"] += 1
            if platform not in results["platforms"]:
                results["platforms"].append(platform)
        else:
            results["failed"] += 1
    ts = datetime.now().isoformat(timespec="seconds")
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO memories (category, key, value) VALUES (?, ?, ?)",
                 ("published", f"run_{ts}", json.dumps(results)))
    conn.commit(); conn.close()
    return results

def show_schedule():
    pending = get_pending()
    schedule = []
    for item in pending:
        schedule.append({"key": item["_key"], "platform": item.get("platform", "telegram"),
                         "preview": item.get("content", "")[:80]})
    return {"pending_count": len(schedule), "items": schedule}

def generate_posts(n):
    conn = _db()
    generated = 0
    platforms = list(TEMPLATES.keys())
    for i in range(n):
        platform = platforms[i % len(platforms)]
        topic = f"AI automation trends #{i+1} - {datetime.now().strftime('%Y%m%d')}"
        prompt = TEMPLATES[platform].format(topic=topic)
        content = _ask_m1(prompt)
        if content:
            key = f"pending_{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}"
            conn.execute("INSERT OR REPLACE INTO memories (category, key, value) VALUES (?, ?, ?)",
                         ("content_queue", key,
                          json.dumps({"platform": platform, "content": content, "topic": topic})))
            generated += 1
    conn.commit(); conn.close()
    return {"generated": generated, "requested": n}

def main():
    ap = argparse.ArgumentParser(description="Content publishing pipeline")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true", help="Publish all pending content")
    g.add_argument("--schedule", action="store_true", help="Show publishing schedule")
    g.add_argument("--generate", type=int, metavar="N", help="Generate N posts via M1")
    args = ap.parse_args()
    if args.once:
        print(json.dumps(run_once(), indent=2))
    elif args.schedule:
        print(json.dumps(show_schedule(), indent=2))
    elif args.generate:
        print(json.dumps(generate_posts(args.generate), indent=2))

if __name__ == "__main__":
    main()
