#!/usr/bin/env python3
"""linkedin_scheduler.py — Schedule and auto-publish LinkedIn posts.

Manages a queue of pre-generated posts with scheduled publication times.
Posts can be published via:
  - Clipboard + browser open (default)
  - Telegram notification with ready-to-paste text
  - Playwright automation (if available)

Cluster verification: each post can be validated by M1+OL1 before publishing.

CLI:
    --generate N          : Generate N posts in advance via cluster
    --schedule "YYYY-MM-DD HH:MM" "text"  : Schedule a specific post
    --list                : Show all scheduled posts
    --next                : Show next post to publish
    --publish-next        : Publish the next due post NOW
    --run                 : Daemon mode — check every 5min, publish when due
    --topics "t1,t2,..."  : Topics for generation (default: AI themes)
    --verify ID           : Cluster-verify a specific post before publishing
    --once                : Single check (for cron/task scheduler)
    --auto-generate       : Auto-refill queue when < 3 pending posts

Stdlib-only for core, optional playwright.
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _paths import ETOILE_DB, TELEGRAM_TOKEN, TELEGRAM_CHAT

# Default topics for auto-generation
DEFAULT_TOPICS = [
    "IA distribuee sur cluster GPU local",
    "Automatisation DevOps avec agents IA",
    "Solo dev augmente par IA (productivite x5)",
    "Open source et IA locale vs cloud",
    "Architecture MCP et orchestration multi-agents",
    "Trading algorithmique avec consensus multi-IA",
    "Voice-first computing et assistants vocaux",
    "Fine-tuning local avec QLoRA sur GPU consumer",
    "Resilience systeme : circuit breakers et fallback chains",
    "L'avenir du dev solo avec les outils IA 2026",
]

# Best hours to post on LinkedIn (Paris timezone)
OPTIMAL_HOURS = [8, 9, 12, 17, 18]


def get_db():
    db = sqlite3.connect(str(ETOILE_DB), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS linkedin_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        scheduled_at TEXT NOT NULL,
        post_text TEXT NOT NULL,
        post_lang TEXT DEFAULT 'fr',
        topic TEXT,
        status TEXT DEFAULT 'pending',
        published_at TEXT,
        method TEXT,
        agent_used TEXT,
        generation_time_ms INTEGER
    )""")
    db.commit()
    return db


def call_m1(prompt, max_tokens=1024, timeout=60):
    """Call M1/qwen3-8b."""
    try:
        data = json.dumps({
            "model": "qwen3-8b",
            "input": f"/nothink\n{prompt}",
            "temperature": 0.7,
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
    except Exception as e:
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


def load_real_specs():
    """Load real specs from README.md for fact-checking posts."""
    readme_path = Path(__file__).resolve().parent.parent.parent / "README.md"
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            # Read first 60 lines (key stats section)
            lines = []
            for i, line in enumerate(f):
                if i >= 60:
                    break
                lines.append(line.rstrip())
        return "\n".join(lines)
    except Exception:
        pass
    return ""

REAL_SPECS_STATIC = """
Specs REELLES du projet JARVIS Etoile v12.4 (GitHub: Turbo31150/turbo):
- 10 GPU NVIDIA ~78 GB VRAM: RTX 3080 10GB, RTX 2060 12GB, 4x GTX 1660S 6GB, M2 3GPU/24GB, M3 1GPU/8GB
- 3 machines physiques: M1 (6GPU/46GB), M2 (3GPU/24GB), M3 (1GPU/8GB)
- 14 modeles IA (4 local + 10 cloud): qwen3-8b (46tok/s), deepseek-r1, gpt-oss:120b cloud
- 167 MCP tools + 603 handlers, 504 REST endpoints
- 435 scripts COWORK, 253 modules source, 96086 lignes de code
- 3665 tests (100% pass), 80 skills, 96 agent patterns
- 7 Claude SDK agents + 11 plugin agents + 96 pattern DB agents
- Stack: Python 3.13 + SQLite + LM Studio + Ollama + Claude SDK + Electron 33
- Telegram bot @turboSSebot autonome, Electron desktop 29 pages, voice assistant JARVIS
- Trading MEXC Futures 10x multi-consensus
- Dev solo, 6 mois
- Navigateur: Comet (Perplexity) defaut CDP 9222
IMPORTANT: N'invente JAMAIS de specs. Pas d'A100, pas de milliers de requetes.
Utilise UNIQUEMENT les vrais chiffres ci-dessus.
"""


def get_real_specs():
    """Get specs from README or static fallback."""
    readme_content = load_real_specs()
    if readme_content and "JARVIS" in readme_content:
        return f"Extrait README.md officiel:\n{readme_content}\n\nIMPORTANT: Utilise UNIQUEMENT les specs du README. N'invente rien."
    return REAL_SPECS_STATIC


def generate_post(topic):
    """Generate a LinkedIn post via cluster (M1 > OL1 fallback)."""
    prompt = (
        f"Ecris un post LinkedIn professionnel en francais (250 mots max). "
        f"Theme: {topic}. "
        f"Structure: hook percutant (1 ligne), developpement avec chiffres/experience concrete, "
        f"conclusion avec question ouverte. Ajoute 5-7 hashtags pertinents. "
        f"Pas de titre, pas de guillemets autour du texte. Texte brut pret a coller.\n\n"
        f"{get_real_specs()}"
    )
    text, ms, agent = call_m1(prompt)
    if not text:
        text, ms, agent = call_ol1(prompt)
    if text:
        # Clean up common artifacts
        text = text.strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text.startswith("Voici") or text.startswith("Bien sur"):
            # Remove preamble before actual post
            lines = text.split("\n", 2)
            if len(lines) > 2:
                text = "\n".join(lines[1:]).strip()
    return text, ms, agent


def schedule_posts(db, count, topics=None):
    """Generate and schedule N posts at optimal times."""
    if not topics:
        topics = DEFAULT_TOPICS

    now = datetime.now()
    scheduled = []

    for i in range(count):
        topic = topics[i % len(topics)]
        print(f"\n  [{i+1}/{count}] Generating: {topic[:50]}...")

        text, ms, agent = generate_post(topic)
        if not text:
            print(f"    FAIL: no response from cluster")
            continue

        # Schedule at next optimal hour
        days_ahead = i // len(OPTIMAL_HOURS)
        hour_idx = i % len(OPTIMAL_HOURS)
        target = now + timedelta(days=1 + days_ahead)
        target = target.replace(
            hour=OPTIMAL_HOURS[hour_idx],
            minute=0, second=0, microsecond=0
        )
        scheduled_at = target.strftime("%Y-%m-%d %H:%M")

        db.execute("""
            INSERT INTO linkedin_schedule
            (scheduled_at, post_text, topic, agent_used, generation_time_ms, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (scheduled_at, text, topic, agent, ms))
        db.commit()

        print(f"    OK: {len(text)} chars, {ms}ms [{agent}] -> {scheduled_at}")
        scheduled.append({"topic": topic, "scheduled": scheduled_at, "chars": len(text)})

    return scheduled


def list_scheduled(db):
    """List all scheduled posts."""
    rows = db.execute("""
        SELECT id, scheduled_at, status, topic, LENGTH(post_text) as chars, agent_used
        FROM linkedin_schedule ORDER BY scheduled_at
    """).fetchall()
    print(f"\n  {'ID':>3} | {'Scheduled':16} | {'Status':9} | {'Chars':>5} | {'Agent':5} | Topic")
    print("  " + "-" * 80)
    for r in rows:
        icon = {"pending": " ", "published": "+", "failed": "X", "skipped": "-"}.get(r["status"], "?")
        print(f"  {r['id']:3} | {r['scheduled_at']:16} | [{icon}] {r['status']:7} | {r['chars']:5} | {r['agent_used'] or '?':5} | {(r['topic'] or '')[:30]}")
    print(f"\n  Total: {len(rows)} posts ({sum(1 for r in rows if r['status'] in ('pending','verified'))} pending)")


def get_next_due(db):
    """Get the next post that's due for publishing."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return db.execute("""
        SELECT * FROM linkedin_schedule
        WHERE status IN ('pending','verified') AND scheduled_at <= ?
        ORDER BY scheduled_at LIMIT 1
    """, (now,)).fetchone()


def publish_post(db, row, method="clipboard"):
    """Publish a scheduled post."""
    post_id = row["id"]
    text = row["post_text"]
    print(f"\n  Publishing post #{post_id} ({len(text)} chars)...")

    success = False

    if method in ("clipboard", "all"):
        try:
            r = subprocess.run(
                ['bash', '-Command', '$input | Set-Clipboard'],
                input=text.encode('utf-8'),
                capture_output=True, timeout=10)
            if r.returncode == 0:
                subprocess.Popen(
                    ['bash', '-Command', 'Start-Process "https://www.linkedin.com/feed/"'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"    [+] Clipboard: {len(text)} chars + LinkedIn opened")
                success = True
        except Exception as e:
            print(f"    [-] Clipboard: {e}")

    if method in ("telegram", "all"):
        try:
            if TELEGRAM_TOKEN and TELEGRAM_CHAT:
                header = f"LINKEDIN POST #{post_id} (planifie {row['scheduled_at']})\n{'='*30}\n\n"
                footer = f"\n\n{'='*30}\nCopiez et collez sur LinkedIn"
                msg = header + text + footer
                data = urllib.parse.urlencode({
                    "chat_id": TELEGRAM_CHAT,
                    "text": msg[:4000],
                    "parse_mode": "",
                }).encode()
                req = urllib.request.Request(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data)
                resp = urllib.request.urlopen(req, timeout=15)
                result = json.loads(resp.read())
                if result.get("ok"):
                    print(f"    [+] Telegram: sent to chat")
                    success = True
        except Exception as e:
            print(f"    [-] Telegram: {e}")

    # Update status
    status = "published" if success else "failed"
    db.execute("""
        UPDATE linkedin_schedule
        SET status=?, published_at=datetime('now','localtime'), method=?
        WHERE id=?
    """, (status, method, post_id))
    db.commit()
    print(f"    Status: {status}")
    return success


def run_daemon(db, method="all", interval=300):
    """Daemon mode — check every interval seconds, publish when due."""
    print(f"\n  LinkedIn Scheduler Daemon (check every {interval}s)")
    print(f"  Method: {method}")
    print(f"  Press Ctrl+C to stop\n")

    while True:
        try:
            due = get_next_due(db)
            if due:
                print(f"  [{datetime.now().strftime('%H:%M')}] Post #{due['id']} is due!")
                publish_post(db, due, method)
            else:
                # Show next upcoming
                upcoming = db.execute("""
                    SELECT scheduled_at FROM linkedin_schedule
                    WHERE status IN ('pending','verified') ORDER BY scheduled_at LIMIT 1
                """).fetchone()
                if upcoming:
                    next_time = upcoming["scheduled_at"]
                    print(f"  [{datetime.now().strftime('%H:%M')}] Next post: {next_time}")
                else:
                    print(f"  [{datetime.now().strftime('%H:%M')}] No pending posts")

            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n  Daemon stopped.")
            break


def call_gpt_oss(prompt, timeout=120):
    """Call gpt-oss:120b cloud (CHAMPION scorer) for verification."""
    try:
        data = json.dumps({
            "model": "gpt-oss:120b-cloud",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
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
        return d.get("message", {}).get("content", ""), elapsed, "gpt-oss"
    except Exception:
        return None, 0, None


def verify_post_cluster(post_text, topic=""):
    """Verify a post quality via cluster consensus (M1 + gpt-oss)."""
    verify_prompt = (
        f"Evalue ce post LinkedIn sur 10 (qualite, engagement, professionnalisme, exactitude).\n"
        f"Theme: {topic}\n\n{get_real_specs()}\n\n---\n{post_text[:1500]}\n---\n\n"
        f"Verifie que les chiffres/specs sont EXACTS (pas d'A100, pas de chiffres inventes).\n"
        f"Reponds UNIQUEMENT au format: SCORE:X/10 | VERDICT:OK/REFAIRE | RAISON:...\n"
        f"OK si score >= 7 ET specs exactes. REFAIRE sinon avec correction."
    )
    results = []

    # M1 verification
    text_m1, ms_m1, _ = call_m1(verify_prompt, max_tokens=256, timeout=30)
    if text_m1:
        results.append(("M1", text_m1.strip()))

    # gpt-oss verification (cloud champion)
    text_gpt, ms_gpt, _ = call_gpt_oss(verify_prompt, timeout=60)
    if text_gpt:
        results.append(("gpt-oss", text_gpt.strip()))

    # OL1 fallback if both fail
    if not results:
        text_ol1, ms_ol1, _ = call_ol1(verify_prompt, timeout=20)
        if text_ol1:
            results.append(("OL1", text_ol1.strip()))

    # Parse scores
    approved = 0
    total_score = 0
    details = []
    for agent, resp in results:
        score = 0
        verdict = "?"
        try:
            if "SCORE:" in resp:
                score_part = resp.split("SCORE:")[1].split("|")[0].strip()
                score = int(score_part.split("/")[0])
            if "VERDICT:" in resp:
                verdict = resp.split("VERDICT:")[1].split("|")[0].strip()
        except (ValueError, IndexError):
            pass
        total_score += score
        if verdict.upper().startswith("OK") or score >= 7:
            approved += 1
        details.append(f"[{agent}] {score}/10 {verdict}")

    avg_score = total_score / len(results) if results else 0
    is_approved = approved >= len(results) / 2 and avg_score >= 6
    return is_approved, avg_score, details


def auto_refill_queue(db, min_pending=3, generate_count=5, topics=None):
    """Auto-generate posts if queue is running low."""
    pending = db.execute(
        "SELECT COUNT(*) FROM linkedin_schedule WHERE status IN ('pending','verified')"
    ).fetchone()[0]
    if pending >= min_pending:
        return 0
    print(f"  Auto-refill: {pending} pending < {min_pending} min, generating {generate_count}...")
    results = schedule_posts(db, generate_count, topics)
    return len(results)


def send_telegram_status(db):
    """Send a status summary to Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    pending = db.execute("SELECT COUNT(*) FROM linkedin_schedule WHERE status IN ('pending','verified')").fetchone()[0]
    published = db.execute("SELECT COUNT(*) FROM linkedin_schedule WHERE status='published'").fetchone()[0]
    upcoming = db.execute("""
        SELECT scheduled_at, topic FROM linkedin_schedule
        WHERE status='pending' ORDER BY scheduled_at LIMIT 3
    """).fetchall()

    lines = [
        f"LinkedIn Scheduler {datetime.now().strftime('%H:%M')}",
        f"Pending: {pending} | Published: {published}",
    ]
    if upcoming:
        lines.append("")
        for u in upcoming:
            lines.append(f"  {u['scheduled_at']} - {(u['topic'] or '')[:30]}")

    msg = "\n".join(lines)
    try:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data)
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Post Scheduler")
    parser.add_argument("--generate", type=int, metavar="N",
                        help="Generate N posts in advance")
    parser.add_argument("--topics", type=str,
                        help="Comma-separated topics for generation")
    parser.add_argument("--schedule", nargs=2, metavar=("DATETIME", "TEXT"),
                        help="Schedule a specific post: 'YYYY-MM-DD HH:MM' 'text'")
    parser.add_argument("--list", action="store_true", help="List all scheduled posts")
    parser.add_argument("--next", action="store_true", help="Show next due post")
    parser.add_argument("--publish-next", action="store_true",
                        help="Publish the next due post now")
    parser.add_argument("--run", action="store_true", help="Daemon mode")
    parser.add_argument("--method", default="all",
                        choices=["clipboard", "telegram", "all"],
                        help="Publication method")
    parser.add_argument("--once", action="store_true",
                        help="Single check (for cron/task scheduler)")
    parser.add_argument("--verify", type=int, metavar="ID",
                        help="Cluster-verify a specific post")
    parser.add_argument("--auto-generate", action="store_true",
                        help="Auto-refill queue when < 3 pending")
    args = parser.parse_args()

    db = get_db()

    if args.generate:
        topics = args.topics.split(",") if args.topics else None
        print(f"Generating {args.generate} posts...")
        results = schedule_posts(db, args.generate, topics)
        print(f"\nScheduled {len(results)} posts")
        send_telegram_status(db)

    elif args.schedule:
        dt, text = args.schedule
        db.execute("""
            INSERT INTO linkedin_schedule (scheduled_at, post_text, topic, status)
            VALUES (?, ?, 'manual', 'pending')
        """, (dt, text))
        db.commit()
        print(f"Post scheduled for {dt} ({len(text)} chars)")

    elif args.list:
        list_scheduled(db)

    elif args.next:
        due = get_next_due(db)
        if due:
            print(f"Next due: #{due['id']} scheduled {due['scheduled_at']}")
            print(f"Topic: {due['topic']}")
            print(f"Text ({len(due['post_text'])} chars):")
            print(due["post_text"][:500])
        else:
            upcoming = db.execute("""
                SELECT * FROM linkedin_schedule
                WHERE status IN ('pending','verified') ORDER BY scheduled_at LIMIT 1
            """).fetchone()
            if upcoming:
                print(f"Next upcoming: #{upcoming['id']} at {upcoming['scheduled_at']}")
                print(f"Topic: {upcoming['topic']}")
            else:
                print("No pending posts. Use --generate N to create some.")

    elif args.publish_next:
        due = get_next_due(db)
        if due:
            publish_post(db, due, args.method)
        else:
            print("No post due right now.")

    elif args.run:
        run_daemon(db, args.method)

    elif args.verify:
        row = db.execute("SELECT * FROM linkedin_schedule WHERE id=?", (args.verify,)).fetchone()
        if not row:
            print(f"Post #{args.verify} not found")
        else:
            print(f"Verifying post #{row['id']} ({len(row['post_text'])} chars)...")
            ok, score, details = verify_post_cluster(row["post_text"], row["topic"] or "")
            for d in details:
                print(f"  {d}")
            print(f"  Average: {score:.1f}/10 -> {'APPROVED' if ok else 'REJECTED'}")
            if ok:
                db.execute("UPDATE linkedin_schedule SET status='verified' WHERE id=?", (args.verify,))
                db.commit()

    elif args.auto_generate:
        refilled = auto_refill_queue(db, min_pending=3, generate_count=5)
        if refilled:
            print(f"Generated {refilled} new posts")
            send_telegram_status(db)
        else:
            pending = db.execute("SELECT COUNT(*) FROM linkedin_schedule WHERE status IN ('pending','verified')").fetchone()[0]
            print(f"Queue OK: {pending} pending posts")

    elif args.once:
        # Single check — for Windows Task Scheduler
        # Auto-refill if needed
        auto_refill_queue(db, min_pending=3, generate_count=3)
        due = get_next_due(db)
        if due:
            publish_post(db, due, args.method)
            send_telegram_status(db)
        # Exit silently if nothing due

    else:
        parser.print_help()
        print("\nQuick start:")
        print("  --generate 5        Generate 5 posts for the week")
        print("  --list              See scheduled posts")
        print("  --run               Start daemon (checks every 5min)")
        print("  --once              Single check (for Task Scheduler)")

    db.close()


if __name__ == "__main__":
    main()
