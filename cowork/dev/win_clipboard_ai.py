#!/usr/bin/env python3
"""win_clipboard_ai.py — Presse-papier intelligent avec IA.

Historique clipboard, recherche, transformation via M1.

Usage:
    python dev/win_clipboard_ai.py --once
    python dev/win_clipboard_ai.py --history
    python dev/win_clipboard_ai.py --search TERM
    python dev/win_clipboard_ai.py --watch
"""
import argparse
import ctypes
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "clipboard_ai.db"
M1_URL = "http://127.0.0.1:1234/api/v1/chat"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS clipboard (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, content TEXT, content_type TEXT,
        length INTEGER)""")
    db.commit()
    return db


def get_clipboard():
    """Get current clipboard text content."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        CF_UNICODETEXT = 13

        user32.OpenClipboard(0)
        try:
            if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if handle:
                    ptr = kernel32.GlobalLock(handle)
                    if ptr:
                        text = ctypes.wstring_at(ptr)
                        kernel32.GlobalUnlock(handle)
                        return text[:5000]
        finally:
            user32.CloseClipboard()
    except Exception:
        pass
    return ""


def store_clipboard(content):
    """Store clipboard content if new."""
    if not content or len(content) < 2:
        return False
    db = init_db()
    # Check if same content already stored recently
    existing = db.execute(
        "SELECT COUNT(*) FROM clipboard WHERE content=? AND ts > ?",
        (content[:5000], time.time() - 60)
    ).fetchone()[0]
    if existing == 0:
        content_type = "text"
        if content.startswith("http"):
            content_type = "url"
        elif any(kw in content for kw in ["def ", "class ", "import ", "function"]):
            content_type = "code"
        db.execute(
            "INSERT INTO clipboard (ts, content, content_type, length) VALUES (?,?,?,?)",
            (time.time(), content[:5000], content_type, len(content))
        )
        db.commit()
        db.close()
        return True
    db.close()
    return False


def get_history(limit=20):
    """Get clipboard history."""
    db = init_db()
    rows = db.execute(
        "SELECT ts, content, content_type, length FROM clipboard ORDER BY ts DESC LIMIT ?",
        (limit,)
    ).fetchall()
    db.close()
    return [{
        "ts": datetime.fromtimestamp(r[0]).isoformat() if r[0] else None,
        "content": r[1][:100] + "..." if len(r[1] or "") > 100 else r[1],
        "type": r[2], "length": r[3],
    } for r in rows]


def search_clipboard(term):
    """Search clipboard history."""
    db = init_db()
    rows = db.execute(
        "SELECT ts, content, content_type FROM clipboard WHERE content LIKE ? ORDER BY ts DESC LIMIT 20",
        (f"%{term}%",)
    ).fetchall()
    db.close()
    return [{
        "ts": datetime.fromtimestamp(r[0]).isoformat() if r[0] else None,
        "content": r[1][:200], "type": r[2],
    } for r in rows]


def do_once():
    """Capture current clipboard and show stats."""
    db = init_db()
    content = get_clipboard()
    stored = store_clipboard(content) if content else False
    total = db.execute("SELECT COUNT(*) FROM clipboard").fetchone()[0]
    db.close()
    return {
        "ts": datetime.now().isoformat(),
        "current": content[:100] if content else "(empty)",
        "stored": stored,
        "total_entries": total,
    }


def do_watch():
    """Watch clipboard for changes."""
    print("[CLIPBOARD_AI] Watching clipboard...")
    last = ""
    while True:
        content = get_clipboard()
        if content and content != last:
            stored = store_clipboard(content)
            if stored:
                print(f"[{datetime.now().isoformat()}] New: {content[:80]}...")
            last = content
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="Windows Clipboard AI")
    parser.add_argument("--once", action="store_true", help="Capture current")
    parser.add_argument("--history", action="store_true", help="Show history")
    parser.add_argument("--search", metavar="TERM", help="Search history")
    parser.add_argument("--watch", action="store_true", help="Watch for changes")
    args = parser.parse_args()

    if args.history:
        print(json.dumps(get_history(), ensure_ascii=False, indent=2))
    elif args.search:
        print(json.dumps(search_clipboard(args.search), ensure_ascii=False, indent=2))
    elif args.watch:
        do_watch()
    else:
        result = do_once()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
