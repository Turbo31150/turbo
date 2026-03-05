#!/usr/bin/env python3
"""win_app_usage_tracker.py — #205 Track active window/app usage time.
Usage:
    python dev/win_app_usage_tracker.py --track
    python dev/win_app_usage_tracker.py --report
    python dev/win_app_usage_tracker.py --top
    python dev/win_app_usage_tracker.py --weekly
    python dev/win_app_usage_tracker.py --once
"""
import argparse, json, sqlite3, time, os, ctypes, ctypes.wintypes, re
from datetime import datetime, timedelta
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "app_usage.db"

POLL_INTERVAL = 5  # seconds
PRODUCTIVE_APPS = {
    "code", "visual studio", "pycharm", "cursor", "windsurf",
    "terminal", "powershell", "cmd", "git", "python",
    "claude", "lm studio", "ollama", "jupyter",
    "excel", "word", "powerpoint", "notion", "obsidian"
}
DISTRACTION_APPS = {
    "youtube", "twitch", "netflix", "discord", "reddit",
    "tiktok", "instagram", "facebook", "twitter"
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_name TEXT NOT NULL,
        window_title TEXT,
        date TEXT NOT NULL,
        duration_sec INTEGER DEFAULT 0,
        category TEXT DEFAULT 'other',
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_name TEXT,
        window_title TEXT,
        started_at TEXT,
        ended_at TEXT,
        duration_sec INTEGER
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_usage_date ON usage(date)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_usage_app ON usage(app_name)")
    db.commit()
    return db


def _get_active_window():
    """Get foreground window title using ctypes."""
    if os.name != 'nt':
        return "Unknown", "unknown"
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if not title:
            return "Desktop", "desktop"
        # Extract app name from title
        app = title.split(" - ")[-1].strip() if " - " in title else title.split(" — ")[-1].strip() if " — " in title else title
        # Clean up common suffixes
        for suffix in [" - Google Chrome", " - Mozilla Firefox", " - Microsoft Edge"]:
            if title.endswith(suffix):
                app = suffix.replace(" - ", "").strip()
                break
        return app[:100], title[:500]
    except Exception:
        return "Unknown", "unknown"


def _categorize(app_name, title):
    """Categorize app as productive/distraction/other."""
    lower = (app_name + " " + title).lower()
    for p in PRODUCTIVE_APPS:
        if p in lower:
            return "productive"
    for d in DISTRACTION_APPS:
        if d in lower:
            return "distraction"
    return "other"


def track_usage(db, duration=300):
    """Track app usage for duration seconds (default 5 min)."""
    today = datetime.now().strftime("%Y-%m-%d")
    tracked = []
    start = time.time()
    last_app = None
    last_title = None
    session_start = time.time()

    while time.time() - start < duration:
        app, title = _get_active_window()
        cat = _categorize(app, title)

        if app != last_app:
            # Save previous session
            if last_app:
                sess_dur = int(time.time() - session_start)
                db.execute(
                    "INSERT INTO sessions (app_name, window_title, started_at, ended_at, duration_sec) VALUES (?,?,?,?,?)",
                    (last_app, last_title, datetime.fromtimestamp(session_start).isoformat(),
                     datetime.now().isoformat(), sess_dur)
                )
            session_start = time.time()
            last_app = app
            last_title = title

        # Upsert usage by app+date
        existing = db.execute(
            "SELECT id, duration_sec FROM usage WHERE app_name=? AND date=?",
            (app, today)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE usage SET duration_sec=duration_sec+?, window_title=?, category=? WHERE id=?",
                (POLL_INTERVAL, title, cat, existing[0])
            )
        else:
            db.execute(
                "INSERT INTO usage (app_name, window_title, date, duration_sec, category) VALUES (?,?,?,?,?)",
                (app, title, today, POLL_INTERVAL, cat)
            )
        db.commit()

        tracked.append({"app": app, "category": cat})
        time.sleep(POLL_INTERVAL)

    return {
        "tracked_seconds": int(time.time() - start),
        "polls": len(tracked),
        "unique_apps": len(set(t["app"] for t in tracked))
    }


def get_report(db, date=None):
    """Daily usage report."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    rows = db.execute(
        "SELECT app_name, duration_sec, category FROM usage WHERE date=? ORDER BY duration_sec DESC",
        (date,)
    ).fetchall()
    total = sum(r[1] for r in rows)
    by_cat = {}
    apps = []
    for app, dur, cat in rows:
        apps.append({
            "app": app,
            "duration_sec": dur,
            "duration_human": f"{dur//3600}h{(dur%3600)//60}m" if dur >= 3600 else f"{dur//60}m{dur%60}s",
            "pct": round(dur / total * 100, 1) if total else 0,
            "category": cat
        })
        by_cat[cat] = by_cat.get(cat, 0) + dur

    prod = by_cat.get("productive", 0)
    dist = by_cat.get("distraction", 0)
    score = round(prod / (prod + dist) * 100) if (prod + dist) > 0 else 50

    return {
        "date": date,
        "total_tracked_sec": total,
        "total_human": f"{total//3600}h{(total%3600)//60}m",
        "apps": apps[:15],
        "by_category": {k: {"seconds": v, "pct": round(v/total*100, 1) if total else 0} for k, v in by_cat.items()},
        "productivity_score": score
    }


def get_top(db, days=7):
    """Top apps over N days."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = db.execute(
        "SELECT app_name, SUM(duration_sec) as total FROM usage WHERE date>=? GROUP BY app_name ORDER BY total DESC LIMIT 10",
        (since,)
    ).fetchall()
    return {
        "period": f"last {days} days",
        "top_apps": [{"rank": i+1, "app": r[0], "total_sec": r[1],
                       "hours": round(r[1]/3600, 1)} for i, r in enumerate(rows)]
    }


def get_weekly(db):
    """Weekly breakdown by day."""
    days = []
    for i in range(7):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        row = db.execute(
            "SELECT SUM(duration_sec), COUNT(DISTINCT app_name) FROM usage WHERE date=?", (d,)
        ).fetchone()
        total = row[0] or 0
        apps = row[1] or 0
        prod = db.execute(
            "SELECT SUM(duration_sec) FROM usage WHERE date=? AND category='productive'", (d,)
        ).fetchone()[0] or 0
        days.append({
            "date": d,
            "total_sec": total,
            "hours": round(total / 3600, 1),
            "unique_apps": apps,
            "productive_pct": round(prod / total * 100) if total else 0
        })
    return {"weekly": days}


def do_status(db):
    """Quick status + single capture."""
    app, title = _get_active_window()
    cat = _categorize(app, title)
    today = datetime.now().strftime("%Y-%m-%d")
    today_total = db.execute(
        "SELECT SUM(duration_sec) FROM usage WHERE date=?", (today,)
    ).fetchone()[0] or 0
    total_entries = db.execute("SELECT COUNT(*) FROM usage").fetchone()[0]
    return {
        "script": "win_app_usage_tracker.py",
        "id": 205,
        "db": str(DB_PATH),
        "current_app": app,
        "current_title": title[:100],
        "current_category": cat,
        "today_tracked_sec": today_total,
        "today_human": f"{today_total//3600}h{(today_total%3600)//60}m",
        "total_entries": total_entries,
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="Windows App Usage Tracker — track active window time")
    parser.add_argument("--track", action="store_true", help="Track usage (5 min loop)")
    parser.add_argument("--report", action="store_true", help="Daily report")
    parser.add_argument("--top", action="store_true", help="Top 10 apps (7 days)")
    parser.add_argument("--weekly", action="store_true", help="Weekly breakdown")
    parser.add_argument("--once", action="store_true", help="Single capture + status")
    args = parser.parse_args()

    db = init_db()

    if args.track:
        result = track_usage(db)
    elif args.report:
        result = get_report(db)
    elif args.top:
        result = get_top(db)
    elif args.weekly:
        result = get_weekly(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
