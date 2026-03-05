#!/usr/bin/env python3
"""telegram_scheduler.py — Planifie des messages et rappels Telegram.

Usage examples:
  python dev/telegram_scheduler.py --schedule "rappelle moi dans 30 minutes de checker le trading"
  python dev/telegram_scheduler.py --list
  python dev/telegram_scheduler.py --cancel 3
  python dev/telegram_scheduler.py --remind   # déclenche les rappels dus
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "scheduler.db"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remind_at TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','sent','canceled'))
        )
        """
    )
    return conn

# ---------------------------------------------------------------------------
# Natural‑language time parser (very small subset)
# ---------------------------------------------------------------------------

def parse_time(expr: str) -> datetime:
    """Parse simple French time expressions.
    Supported forms (case‑insensitive):
      - "dans X minutes" / "dans X minute"
      - "dans X heures" / "dans X heure" / "dans X h"
      - "à HH:MM" (24h style) – today or tomorrow if time already passed
      - "demain à HH:MM"
    Returns a datetime in the local timezone.
    Raises ValueError if parsing fails.
    """
    expr = expr.strip().lower()
    now = datetime.now()

    # "dans X minutes"
    m = re.search(r"dans\s+(\d+)\s+minute", expr)
    if m:
        minutes = int(m.group(1))
        return now + timedelta(minutes=minutes)
    m = re.search(r"dans\s+(\d+)\s+minutes", expr)
    if m:
        minutes = int(m.group(1))
        return now + timedelta(minutes=minutes)

    # "dans X heures" / "dans X h"
    m = re.search(r"dans\s+(\d+)\s+heure", expr)
    if m:
        hrs = int(m.group(1))
        return now + timedelta(hours=hrs)
    m = re.search(r"dans\s+(\d+)\s+heures", expr)
    if m:
        hrs = int(m.group(1))
        return now + timedelta(hours=hrs)
    m = re.search(r"dans\s+(\d+)\s*h", expr)
    if m:
        hrs = int(m.group(1))
        return now + timedelta(hours=hrs)

    # "demain à HH:MM"
    m = re.search(r"demain\s+à\s+(\d{1,2}):(\d{2})", expr)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        tomorrow = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        return tomorrow

    # "à HH:MM"
    m = re.search(r"à\s+(\d{1,2}):(\d{2})", expr)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            # time already passed today -> assume tomorrow
            candidate += timedelta(days=1)
        return candidate

    raise ValueError(f"Impossible de parser le temps : '{expr}'")

# ---------------------------------------------------------------------------
# Core actions
# ---------------------------------------------------------------------------

def schedule_reminder(raw_text: str):
    """Extract time expression and message from a raw natural language string.
    Expected pattern: '<texte> dans X minutes|heures|à HH:MM ...'
    For simplicity we look for the first time expression and treat the rest as message.
    """
    # Try to locate a time expression using the same regexes as parse_time.
    time_patterns = [
        r"dans\s+\d+\s+minute",
        r"dans\s+\d+\s+minutes",
        r"dans\s+\d+\s+heure",
        r"dans\s+\d+\s+heures",
        r"dans\s+\d+\s*h",
        r"demain\s+à\s+\d{1,2}:\d{2}",
        r"à\s+\d{1,2}:\d{2}",
    ]
    for pat in time_patterns:
        m = re.search(pat, raw_text, flags=re.IGNORECASE)
        if m:
            time_expr = m.group(0)
            try:
                remind_at = parse_time(time_expr)
            except ValueError:
                continue
            # Message is everything after the time expression, stripped.
            message = raw_text.replace(time_expr, "").strip()
            if not message:
                message = "(pas de texte)"
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO reminders (remind_at, message, status) VALUES (?,?,?)",
                (remind_at.isoformat(), message, "pending"),
            )
            conn.commit()
            rid = cur.lastrowid
            conn.close()
            return {"id": rid, "remind_at": remind_at.isoformat(), "message": message}
    raise ValueError("Aucune expression temporelle reconnue dans le texte fourni.")


def list_reminders():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, remind_at, message, status FROM reminders ORDER BY remind_at")
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "remind_at": r[1], "message": r[2], "status": r[3]}
        for r in rows
    ]


def cancel_reminder(rid: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE reminders SET status='canceled' WHERE id=?", (rid,))
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return changed


def trigger_due():
    now_iso = datetime.now().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, message FROM reminders WHERE status='pending' AND remind_at<=?",
        (now_iso,)
    )
    due = cur.fetchall()
    for rid, message in due:
        # mark as sent
        cur.execute("UPDATE reminders SET status='sent' WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    # Return list of messages that should be sent now
    return [{"id": rid, "message": message} for rid, message in due]

# ---------------------------------------------------------------------------
# CLI handling
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Planificateur de messages / rappels Telegram")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--schedule", type=str, help="Texte naturel contenant l'heure et le message à planifier")
    group.add_argument("--list", action="store_true", help="Lister tous les rappels")
    group.add_argument("--cancel", type=int, metavar="ID", help="Annuler le rappel avec l'ID donné")
    group.add_argument("--remind", action="store_true", help="Émettre les rappels dont le temps est atteint")

    args = parser.parse_args()

    if args.schedule is not None:
        try:
            result = schedule_reminder(args.schedule)
            print(json.dumps({"status": "scheduled", "reminder": result}, ensure_ascii=False, indent=2))
        except Exception as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
    elif args.list:
        reminders = list_reminders()
        print(json.dumps({"reminders": reminders}, ensure_ascii=False, indent=2))
    elif args.cancel is not None:
        changed = cancel_reminder(args.cancel)
        if changed:
            print(json.dumps({"status": "canceled", "id": args.cancel}, ensure_ascii=False))
        else:
            print(json.dumps({"error": f"ID {args.cancel} introuvable"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
    elif args.remind:
        due = trigger_due()
        print(json.dumps({"triggered": due}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
