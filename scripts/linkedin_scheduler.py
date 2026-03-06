#!/usr/bin/env python3
"""LinkedIn Scheduler — JARVIS Turbo

Scheduler autonome qui tourne en boucle et execute:
1. Verifie les posts planifies a publier (toutes les minutes)
2. Routine quotidienne configurable (scroll, like, comment, notifs)
3. Log toutes les actions en DB
4. Notification Telegram a chaque publication

Usage:
  python linkedin_scheduler.py                  # Lance le scheduler
  python linkedin_scheduler.py --once           # Execute 1 cycle et quitte
  python linkedin_scheduler.py --check-only     # Verifie sans publier
  python linkedin_scheduler.py --routine        # Lance la routine interactive

Declenchable via:
  - Telegram: /post check
  - WhisperFlow: "JARVIS verifie les posts LinkedIn"
  - Cron Windows: Task Scheduler toutes les heures
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

TURBO_DIR = Path(__file__).resolve().parent.parent
DB_PATH = TURBO_DIR / "data" / "jarvis.db"
POSTS_DIR = TURBO_DIR / "data" / "linkedin_posts"
POSTS_DIR.mkdir(exist_ok=True)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT", "2010747443")

CHECK_INTERVAL = 60  # secondes entre chaque verification
ROUTINE_HOURS = [8, 12, 18]  # heures de routine quotidienne


def db_conn():
    return sqlite3.connect(str(DB_PATH))


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def send_telegram(text):
    """Envoie une notification Telegram."""
    if not TELEGRAM_TOKEN:
        # Try loading from .env
        env_path = TURBO_DIR / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("TELEGRAM_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"')
                    break
            else:
                return
        else:
            return
    else:
        token = TELEGRAM_TOKEN

    try:
        data = json.dumps({
            "chat_id": TELEGRAM_CHAT,
            "text": text,
            "parse_mode": "Markdown",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log(f"Telegram erreur: {e}")


def check_scheduled_posts():
    """Verifie et prepare les posts planifies."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    db = db_conn()
    rows = db.execute(
        "SELECT id, content, theme, scheduled_at FROM linkedin_scheduled_posts "
        "WHERE status='scheduled' AND scheduled_at <= ? ORDER BY scheduled_at",
        (now,)
    ).fetchall()

    if not rows:
        return []

    ready_posts = []
    for post_id, content, theme, sched_at in rows:
        log(f"Post #{post_id} pret a publier (planifie: {sched_at})")

        # Sauvegarder le fichier pour Playwright
        post_file = POSTS_DIR / f"post_{post_id}.txt"
        post_file.write_text(content, encoding="utf-8")

        # Mettre a jour le status
        db.execute(
            "UPDATE linkedin_scheduled_posts SET status='ready' WHERE id=?",
            (post_id,)
        )

        # Log action
        db.execute(
            "INSERT INTO linkedin_actions (action_type, target, content, status) VALUES (?, ?, ?, ?)",
            ("schedule_triggered", f"post_{post_id}", content[:100], "ready")
        )

        ready_posts.append({
            "id": post_id,
            "content": content,
            "theme": theme,
            "file": str(post_file),
        })

        # Notification Telegram
        send_telegram(
            f"*LinkedIn Post #{post_id} pret*\n"
            f"Theme: {theme}\n"
            f"Contenu: {content[:100]}...\n\n"
            f"Fichier: `{post_file.name}`\n"
            f"Publier via Claude Code ou `/post publish`"
        )

    db.commit()
    db.close()
    return ready_posts


def update_daily_routine(action, count=1):
    """Met a jour les compteurs de routine du jour."""
    today = datetime.now().strftime("%Y-%m-%d")
    db = db_conn()

    row = db.execute(
        "SELECT id FROM linkedin_daily_routine WHERE routine_date=?", (today,)
    ).fetchone()

    if not row:
        db.execute(
            "INSERT INTO linkedin_daily_routine (routine_date, started_at, status) VALUES (?, ?, 'running')",
            (today, int(time.time()))
        )

    col_map = {
        "scroll": "scroll_count",
        "like": "likes_count",
        "comment": "comments_count",
        "reply": "replies_count",
        "notif": "notif_checked",
        "publish": "posts_published",
    }

    col = col_map.get(action)
    if col:
        db.execute(
            f"UPDATE linkedin_daily_routine SET {col} = {col} + ? WHERE routine_date=?",
            (count, today)
        )

    db.commit()
    db.close()


def get_routine_status():
    """Retourne le statut de la routine du jour."""
    today = datetime.now().strftime("%Y-%m-%d")
    db = db_conn()
    row = db.execute(
        "SELECT scroll_count, likes_count, comments_count, replies_count, "
        "notif_checked, posts_published, status FROM linkedin_daily_routine "
        "WHERE routine_date=?", (today,)
    ).fetchone()
    db.close()

    if not row:
        return None
    return {
        "scrolls": row[0],
        "likes": row[1],
        "comments": row[2],
        "replies": row[3],
        "notifs": row[4],
        "published": row[5],
        "status": row[6],
    }


def should_run_routine():
    """Verifie si c'est l'heure d'une routine."""
    now = datetime.now()
    current_hour = now.hour

    if current_hour not in ROUTINE_HOURS:
        return False

    # Verifier qu'on n'a pas deja fait la routine cette heure
    today = datetime.now().strftime("%Y-%m-%d")
    db = db_conn()
    row = db.execute(
        "SELECT COUNT(*) FROM linkedin_actions "
        "WHERE action_type='routine_start' AND date(timestamp, 'unixepoch')=? "
        "AND CAST(strftime('%%H', timestamp, 'unixepoch') AS INTEGER)=?",
        (today, current_hour)
    ).fetchone()
    db.close()

    return row[0] == 0


def trigger_routine():
    """Declenche la routine LinkedIn via notification."""
    log("Routine LinkedIn declenchee!")

    db = db_conn()
    db.execute(
        "INSERT INTO linkedin_actions (action_type, target, content, status) VALUES (?, ?, ?, ?)",
        ("routine_start", "scheduler", f"Routine {datetime.now().strftime('%H:%M')}", "done")
    )
    db.commit()
    db.close()

    update_daily_routine("scroll", 0)

    send_telegram(
        "*Routine LinkedIn*\n"
        f"Heure: {datetime.now().strftime('%H:%M')}\n\n"
        "Actions a effectuer:\n"
        "1. Scroll feed + like posts pertinents\n"
        "2. Verifier notifications\n"
        "3. Repondre aux commentaires\n"
        "4. Publier posts planifies\n\n"
        "Lancer via Claude Code: `scroll LinkedIn et interagis`"
    )


def scheduler_loop():
    """Boucle principale du scheduler."""
    log("LinkedIn Scheduler demarre")
    log(f"Interval: {CHECK_INTERVAL}s | Routine hours: {ROUTINE_HOURS}")

    cycle = 0
    while True:
        cycle += 1

        try:
            # 1. Verifier posts planifies
            ready = check_scheduled_posts()
            if ready:
                log(f"{len(ready)} post(s) pret(s) a publier")

            # 2. Verifier si routine a lancer
            if should_run_routine():
                trigger_routine()

            # 3. Status toutes les 10 minutes
            if cycle % 10 == 0:
                status = get_routine_status()
                if status:
                    log(f"Routine: {status['likes']}L {status['comments']}C {status['replies']}R {status['published']}P")

        except Exception as e:
            log(f"Erreur cycle: {e}")

        time.sleep(CHECK_INTERVAL)


def run_once():
    """Execute 1 cycle de verification."""
    log("Check unique...")
    ready = check_scheduled_posts()
    if ready:
        for p in ready:
            log(f"Post #{p['id']} pret: {p['file']}")
    else:
        log("Aucun post a publier.")

    status = get_routine_status()
    if status:
        log(f"Routine jour: {status}")
    else:
        log("Pas de routine aujourd'hui.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LinkedIn Scheduler — JARVIS")
    parser.add_argument("--once", action="store_true", help="Execute 1 cycle")
    parser.add_argument("--check-only", action="store_true", help="Verifie sans action")
    parser.add_argument("--routine", action="store_true", help="Force routine maintenant")
    parser.add_argument("--interval", type=int, default=60, help="Interval en secondes")
    parser.add_argument("--hours", help="Heures de routine (ex: 8,12,18)")
    args = parser.parse_args()

    global CHECK_INTERVAL, ROUTINE_HOURS
    CHECK_INTERVAL = args.interval

    if args.hours:
        ROUTINE_HOURS = [int(h) for h in args.hours.split(",")]

    if args.once or args.check_only:
        run_once()
    elif args.routine:
        trigger_routine()
    else:
        scheduler_loop()


if __name__ == "__main__":
    main()
