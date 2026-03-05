#!/usr/bin/env python3
"""win_clipboard_history.py — #204 Clipboard history with search and pin.
Usage:
    python dev/win_clipboard_history.py --history
    python dev/win_clipboard_history.py --search "hello"
    python dev/win_clipboard_history.py --pin 3
    python dev/win_clipboard_history.py --clear
    python dev/win_clipboard_history.py --once
"""
import argparse, json, sqlite3, time, os, ctypes, ctypes.wintypes
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "clipboard_history.db"
MAX_ENTRIES = 1000

CF_UNICODETEXT = 13

user32 = ctypes.windll.user32 if os.name == 'nt' else None
kernel32 = ctypes.windll.kernel32 if os.name == 'nt' else None


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS clips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        content_hash TEXT,
        char_count INTEGER,
        pinned INTEGER DEFAULT 0,
        app_source TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_clips_hash ON clips(content_hash)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_clips_pinned ON clips(pinned)")
    db.commit()
    return db


def _get_clipboard_text():
    """Read clipboard text using ctypes on Windows."""
    if not user32:
        return None

    if not user32.OpenClipboard(0):
        return None

    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None

        h_data = user32.GetClipboardData(CF_UNICODETEXT)
        if not h_data:
            return None

        kernel32.GlobalLock.restype = ctypes.c_void_p
        ptr = kernel32.GlobalLock(h_data)
        if not ptr:
            return None

        try:
            text = ctypes.wstring_at(ptr)
            return text
        finally:
            kernel32.GlobalUnlock(h_data)
    finally:
        user32.CloseClipboard()


def _content_hash(text):
    """Simple hash for dedup."""
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()[:16]


def capture_clipboard(db):
    """Capture current clipboard content."""
    text = _get_clipboard_text()
    if not text or not text.strip():
        return {"captured": False, "reason": "clipboard empty or not text"}

    h = _content_hash(text)
    existing = db.execute("SELECT id FROM clips WHERE content_hash=? ORDER BY id DESC LIMIT 1", (h,)).fetchone()
    if existing:
        return {"captured": False, "reason": "duplicate", "existing_id": existing[0]}

    db.execute(
        "INSERT INTO clips (content, content_hash, char_count) VALUES (?,?,?)",
        (text[:50000], h, len(text))
    )
    db.commit()

    # Enforce max entries (keep pinned)
    total = db.execute("SELECT COUNT(*) FROM clips WHERE pinned=0").fetchone()[0]
    if total > MAX_ENTRIES:
        excess = total - MAX_ENTRIES
        db.execute(
            "DELETE FROM clips WHERE id IN (SELECT id FROM clips WHERE pinned=0 ORDER BY id ASC LIMIT ?)",
            (excess,)
        )
        db.commit()

    return {"captured": True, "chars": len(text), "preview": text[:100]}


def get_history(db, limit=30):
    """Get clipboard history."""
    rows = db.execute(
        "SELECT id, content, char_count, pinned, created_at FROM clips ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "preview": r[1][:200] if r[1] else "",
            "chars": r[2],
            "pinned": bool(r[3]),
            "created_at": r[4]
        })
    total = db.execute("SELECT COUNT(*) FROM clips").fetchone()[0]
    pinned = db.execute("SELECT COUNT(*) FROM clips WHERE pinned=1").fetchone()[0]
    return {"history": items, "total": total, "pinned_count": pinned}


def search_clips(db, text, limit=20):
    """Full-text search in clipboard history."""
    pattern = f"%{text}%"
    rows = db.execute(
        "SELECT id, content, char_count, pinned, created_at FROM clips WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
        (pattern, limit)
    ).fetchall()
    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "preview": r[1][:200] if r[1] else "",
            "chars": r[2],
            "pinned": bool(r[3]),
            "created_at": r[4]
        })
    return {"query": text, "results": items, "count": len(items)}


def pin_clip(db, clip_id):
    """Toggle pin on a clip."""
    row = db.execute("SELECT pinned FROM clips WHERE id=?", (clip_id,)).fetchone()
    if not row:
        return {"error": f"Clip {clip_id} not found"}
    new_pin = 0 if row[0] else 1
    db.execute("UPDATE clips SET pinned=? WHERE id=?", (new_pin, clip_id))
    db.commit()
    return {"id": clip_id, "pinned": bool(new_pin)}


def clear_clips(db):
    """Clear non-pinned clips."""
    count = db.execute("SELECT COUNT(*) FROM clips WHERE pinned=0").fetchone()[0]
    db.execute("DELETE FROM clips WHERE pinned=0")
    db.commit()
    return {"cleared": count, "remaining_pinned": db.execute("SELECT COUNT(*) FROM clips WHERE pinned=1").fetchone()[0]}


def do_status(db):
    """Status overview."""
    # Try to capture current clipboard on status check
    cap = capture_clipboard(db)
    total = db.execute("SELECT COUNT(*) FROM clips").fetchone()[0]
    pinned = db.execute("SELECT COUNT(*) FROM clips WHERE pinned=1").fetchone()[0]
    recent = db.execute(
        "SELECT id, content, created_at FROM clips ORDER BY id DESC LIMIT 3"
    ).fetchall()
    return {
        "script": "win_clipboard_history.py",
        "id": 204,
        "db": str(DB_PATH),
        "total_clips": total,
        "pinned": pinned,
        "max_entries": MAX_ENTRIES,
        "last_capture": cap,
        "recent": [{"id": r[0], "preview": r[1][:80], "at": r[2]} for r in recent],
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Clipboard History — capture, search, pin")
    parser.add_argument("--history", action="store_true", help="Show clipboard history")
    parser.add_argument("--search", type=str, metavar="TEXT", help="Search clips")
    parser.add_argument("--pin", type=int, metavar="ID", help="Toggle pin on clip")
    parser.add_argument("--clear", action="store_true", help="Clear non-pinned clips")
    parser.add_argument("--once", action="store_true", help="Capture + status")
    args = parser.parse_args()

    db = init_db()

    if args.history:
        result = get_history(db)
    elif args.search:
        result = search_clips(db, args.search)
    elif args.pin is not None:
        result = pin_clip(db, args.pin)
    elif args.clear:
        result = clear_clips(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
