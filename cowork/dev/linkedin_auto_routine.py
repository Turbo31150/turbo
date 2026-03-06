#!/usr/bin/env python3
"""linkedin_auto_routine.py — LinkedIn automation routine (scroll, notifs, interactions).

Automated daily routine for LinkedIn engagement:
  1. CHECK NOTIFICATIONS: Scan and summarize new notifications
  2. SCROLL FEED: Collect trending posts for inspiration
  3. GENERATE RESPONSES: Draft comments/replies via cluster AI
  4. PUBLISH SCHEDULED: Push any due posts from linkedin_schedule
  5. REPORT: Send summary to Telegram

CLI:
    --once              : Run full routine once
    --scroll            : Scroll feed and collect posts
    --notifs            : Check and summarize notifications
    --respond ID        : Generate response for a notification/post
    --routine           : Full daily routine (scroll + notifs + publish + report)
    --telegram          : Send results to Telegram
    --dry-run           : Show actions without executing

Integrates with: linkedin_scheduler.py, linkedin_content_generator.py, linkedin_publisher.py
Stdlib-only for core.
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _paths import ETOILE_DB, TELEGRAM_TOKEN, TELEGRAM_CHAT


def get_db():
    db = sqlite3.connect(str(ETOILE_DB), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS linkedin_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        interaction_type TEXT NOT NULL,
        source_text TEXT,
        generated_reply TEXT,
        agent_used TEXT,
        status TEXT DEFAULT 'draft',
        posted_at TEXT,
        generation_time_ms INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS linkedin_feed_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        collected_at TEXT DEFAULT (datetime('now','localtime')),
        author TEXT,
        preview TEXT,
        engagement_hint TEXT,
        used_for_inspiration INTEGER DEFAULT 0
    )""")
    db.commit()
    return db


def call_m1(prompt, max_tokens=1024, timeout=60):
    """Call M1/qwen3-8b."""
    try:
        data = json.dumps({
            "model": "qwen3-8b",
            "input": f"/nothink\n{prompt}",
            "temperature": 0.5,
            "max_output_tokens": max_tokens,
            "stream": False,
            "store": False,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:1234/api/v1/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read())
        elapsed = int((time.time() - t0) * 1000)
        for block in reversed(d.get("output", [])):
            if isinstance(block, dict) and block.get("type") == "message":
                content = block.get("content", "")
                return (content if isinstance(content, str) else str(content)), elapsed, "M1"
    except Exception:
        pass
    return None, 0, None


def call_ol1(prompt, timeout=30):
    """Fallback OL1/qwen3:1.7b."""
    try:
        data = json.dumps({
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read())
        elapsed = int((time.time() - t0) * 1000)
        return d.get("message", {}).get("content", ""), elapsed, "OL1"
    except Exception:
        return None, 0, None


def generate_comment(post_preview, tone="expert"):
    """Generate a LinkedIn comment reply via cluster AI."""
    prompt = (
        f"Ecris un commentaire LinkedIn percutant en francais (80 mots max) "
        f"en reponse a ce post:\n\n\"{post_preview[:500]}\"\n\n"
        f"Ton: {tone}. Apporte de la valeur (experience, donnees, question pertinente). "
        f"Pas de flatterie vide. Texte brut, pas de guillemets."
    )
    text, ms, agent = call_m1(prompt, max_tokens=256)
    if not text:
        text, ms, agent = call_ol1(prompt)
    if text:
        text = text.strip().strip('"')
    return text, ms, agent


def generate_reply(notification_text, context=""):
    """Generate a reply to a LinkedIn notification/message."""
    prompt = (
        f"Ecris une reponse LinkedIn courte et professionnelle en francais (50 mots max) "
        f"pour cette notification:\n\n\"{notification_text[:300]}\"\n\n"
        f"{'Contexte: ' + context if context else ''}"
        f"Sois cordial, authentique. Texte brut."
    )
    text, ms, agent = call_m1(prompt, max_tokens=256)
    if not text:
        text, ms, agent = call_ol1(prompt)
    if text:
        text = text.strip().strip('"')
    return text, ms, agent


def collect_feed_inspiration(db, count=5):
    """Simulate feed collection (store topic ideas for future posts)."""
    # In production, this would use CDP/Playwright to scroll LinkedIn feed
    # For now, generate trending topic ideas via cluster
    prompt = (
        f"Donne {count} sujets tendance LinkedIn cette semaine dans le secteur IA/Tech/DevOps. "
        f"Format: un sujet par ligne, avec un angle de post original. "
        f"Pas de numerotation, juste le sujet."
    )
    text, ms, agent = call_m1(prompt, max_tokens=512)
    if not text:
        text, ms, agent = call_ol1(prompt)

    items = []
    if text:
        for line in text.strip().split("\n"):
            line = line.strip().lstrip("-*0123456789. ")
            if len(line) > 10:
                db.execute("""
                    INSERT INTO linkedin_feed_items (author, preview, engagement_hint)
                    VALUES (?, ?, ?)
                """, (agent or "cluster", line[:500], "trending"))
                items.append(line[:80])
        db.commit()
    return items


def check_scheduled_posts(db):
    """Check and publish any due posts from linkedin_schedule."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    due = db.execute("""
        SELECT * FROM linkedin_schedule
        WHERE status='pending' AND scheduled_at <= ?
        ORDER BY scheduled_at
    """, (now,)).fetchall()
    published = 0
    for row in due:
        # Import publish from scheduler
        try:
            r = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "linkedin_scheduler.py"),
                 "--publish-next", "--method", "all"],
                capture_output=True, text=True, timeout=60,
                env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}
            )
            if r.returncode == 0:
                published += 1
                print(f"  Published post #{row['id']}")
            else:
                print(f"  Failed post #{row['id']}: {r.stderr[:200]}")
        except Exception as e:
            print(f"  Error: {e}")
    return published, len(due)


def auto_refill_check(db):
    """Check if queue needs refilling."""
    pending = db.execute(
        "SELECT COUNT(*) FROM linkedin_schedule WHERE status='pending'"
    ).fetchone()[0]
    if pending < 3:
        print(f"  Queue low ({pending} pending), generating 3 posts...")
        try:
            r = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "linkedin_scheduler.py"),
                 "--generate", "3"],
                capture_output=True, text=True, timeout=300,
                env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}
            )
            print(f"  Auto-generate: {'OK' if r.returncode == 0 else 'FAIL'}")
            return True
        except Exception as e:
            print(f"  Auto-generate error: {e}")
    return False


def send_telegram(msg):
    """Send a message to Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return False
    try:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT,
            "text": msg[:4000],
            "parse_mode": "",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data)
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read()).get("ok", False)
    except Exception:
        return False


def run_full_routine(db, dry_run=False, send_tg=True):
    """Execute the full LinkedIn daily routine."""
    print(f"\n  LinkedIn Auto-Routine {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("  " + "=" * 50)
    report = []
    t0 = time.time()

    # Step 1: Collect feed inspiration
    print("\n  [1/5] Collecting feed inspiration...")
    if not dry_run:
        items = collect_feed_inspiration(db, count=5)
        report.append(f"Feed: {len(items)} trending topics collected")
        for item in items[:3]:
            print(f"    - {item[:60]}")
    else:
        report.append("Feed: DRY RUN")

    # Step 2: Generate engagement comments
    print("\n  [2/5] Generating engagement comments...")
    if not dry_run:
        # Get recent feed items to comment on
        feed_items = db.execute("""
            SELECT preview FROM linkedin_feed_items
            WHERE used_for_inspiration = 0
            ORDER BY collected_at DESC LIMIT 3
        """).fetchall()
        comments_gen = 0
        for item in feed_items:
            text, ms, agent = generate_comment(item["preview"])
            if text:
                db.execute("""
                    INSERT INTO linkedin_interactions
                    (interaction_type, source_text, generated_reply, agent_used, generation_time_ms)
                    VALUES ('comment', ?, ?, ?, ?)
                """, (item["preview"][:300], text, agent, ms))
                comments_gen += 1
                print(f"    [{agent}] Comment: {text[:60]}...")
        db.commit()
        # Mark as used
        db.execute("UPDATE linkedin_feed_items SET used_for_inspiration=1 WHERE used_for_inspiration=0")
        db.commit()
        report.append(f"Comments: {comments_gen} drafted")
    else:
        report.append("Comments: DRY RUN")

    # Step 3: Check and publish scheduled posts
    print("\n  [3/5] Checking scheduled posts...")
    if not dry_run:
        published, total_due = check_scheduled_posts(db)
        report.append(f"Published: {published}/{total_due} due posts")
    else:
        report.append("Publish: DRY RUN")

    # Step 4: Auto-refill queue
    print("\n  [4/5] Checking post queue...")
    if not dry_run:
        refilled = auto_refill_check(db)
        pending = db.execute("SELECT COUNT(*) FROM linkedin_schedule WHERE status='pending'").fetchone()[0]
        report.append(f"Queue: {pending} pending" + (" (refilled)" if refilled else ""))
    else:
        report.append("Queue: DRY RUN")

    # Step 5: Summary
    elapsed = int(time.time() - t0)
    print(f"\n  [5/5] Summary ({elapsed}s)")
    print("  " + "-" * 50)
    for line in report:
        print(f"    {line}")

    # Telegram report
    if send_tg and not dry_run:
        tg_msg = f"LinkedIn Routine {datetime.now().strftime('%H:%M')}\n" + "\n".join(report)
        send_telegram(tg_msg)
        print("  Telegram: sent")

    return report


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Auto-Routine")
    parser.add_argument("--once", action="store_true", help="Run full routine once")
    parser.add_argument("--routine", action="store_true", help="Full daily routine")
    parser.add_argument("--scroll", action="store_true", help="Collect feed inspiration")
    parser.add_argument("--notifs", action="store_true", help="Check notifications")
    parser.add_argument("--respond", type=str, help="Generate response for text")
    parser.add_argument("--telegram", action="store_true", help="Send to Telegram")
    parser.add_argument("--dry-run", action="store_true", help="Show without executing")
    args = parser.parse_args()

    db = get_db()

    if args.routine or args.once:
        run_full_routine(db, dry_run=args.dry_run, send_tg=args.telegram or args.once)

    elif args.scroll:
        items = collect_feed_inspiration(db, count=5)
        print(f"Collected {len(items)} topics:")
        for i in items:
            print(f"  - {i}")

    elif args.respond:
        text, ms, agent = generate_comment(args.respond)
        if text:
            print(f"[{agent}] ({ms}ms):\n{text}")
            db.execute("""
                INSERT INTO linkedin_interactions
                (interaction_type, source_text, generated_reply, agent_used, generation_time_ms)
                VALUES ('manual_reply', ?, ?, ?, ?)
            """, (args.respond[:300], text, agent, ms))
            db.commit()
        else:
            print("No response from cluster")

    elif args.notifs:
        print("Notification check requires browser automation (CDP/Playwright).")
        print("Use: linkedin_scheduler.py --list to see pending posts.")

    else:
        parser.print_help()
        print("\nQuick start:")
        print("  --routine        Full daily automation")
        print("  --scroll         Collect feed topics")
        print("  --respond 'text' Generate reply to a post")
        print("  --once           Single run (for Task Scheduler)")

    db.close()


if __name__ == "__main__":
    main()
