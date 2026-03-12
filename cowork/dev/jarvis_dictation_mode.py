#!/usr/bin/env python3
"""jarvis_dictation_mode.py — Continuous dictation/transcription mode.
COWORK #233 — Batch 105: JARVIS Voice 2.0

Usage:
    python dev/jarvis_dictation_mode.py --start
    python dev/jarvis_dictation_mode.py --stop
    python dev/jarvis_dictation_mode.py --output dictation.txt
    python dev/jarvis_dictation_mode.py --format json
    python dev/jarvis_dictation_mode.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, re
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "dictation_mode.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS dictation_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        status TEXT DEFAULT 'active',
        total_chunks INTEGER DEFAULT 0,
        total_words INTEGER DEFAULT 0,
        total_duration_seconds INTEGER DEFAULT 0,
        language TEXT DEFAULT 'fr'
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS dictation_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        ts TEXT NOT NULL,
        text TEXT NOT NULL,
        confidence REAL,
        duration_ms INTEGER,
        word_count INTEGER,
        FOREIGN KEY (session_id) REFERENCES dictation_sessions(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS dictation_exports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        ts TEXT NOT NULL,
        format TEXT NOT NULL,
        file_path TEXT,
        word_count INTEGER,
        success INTEGER DEFAULT 1
    )""")
    db.commit()
    return db

def get_active_session(db):
    row = db.execute("SELECT id, started_at, total_chunks, total_words FROM dictation_sessions WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        return {"id": row[0], "started_at": row[1], "chunks": row[2], "words": row[3]}
    return None

def auto_punctuate(text):
    """Add basic auto-punctuation to raw transcription text."""
    if not text:
        return text
    # Capitalize first letter
    text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    # Add period if no ending punctuation
    if text and text[-1] not in ".!?;:":
        text += "."
    # Fix common patterns
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([.!?,;:])', r'\1', text)
    return text.strip()

def do_start():
    db = init_db()
    # Deactivate any existing active sessions
    db.execute("UPDATE dictation_sessions SET status='stopped', ended_at=? WHERE status='active'",
               (datetime.now().isoformat(),))

    now = datetime.now().isoformat()
    cursor = db.execute("INSERT INTO dictation_sessions (started_at, status, language) VALUES (?,?,?)",
                        (now, "active", "fr"))
    session_id = cursor.lastrowid

    # Add a simulated initial chunk (in real use, Whisper would feed chunks)
    initial_text = auto_punctuate("session de dictee demarree")
    db.execute("INSERT INTO dictation_chunks (session_id, ts, text, confidence, duration_ms, word_count) VALUES (?,?,?,?,?,?)",
               (session_id, now, initial_text, 0.95, 0, len(initial_text.split())))
    db.execute("UPDATE dictation_sessions SET total_chunks=1, total_words=? WHERE id=?",
               (len(initial_text.split()), session_id))
    db.commit()

    result = {
        "action": "start",
        "session_id": session_id,
        "started_at": now,
        "status": "active",
        "language": "fr",
        "note": "Dictation session started. Whisper chunks will be concatenated.",
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_stop():
    db = init_db()
    session = get_active_session(db)
    if not session:
        db.close()
        return {"error": "No active dictation session", "ts": datetime.now().isoformat()}

    now = datetime.now().isoformat()
    db.execute("UPDATE dictation_sessions SET status='stopped', ended_at=? WHERE id=?",
               (now, session["id"]))
    db.commit()

    # Get full text
    chunks = db.execute("SELECT text FROM dictation_chunks WHERE session_id=? ORDER BY id", (session["id"],)).fetchall()
    full_text = " ".join(c[0] for c in chunks if c[0])

    result = {
        "action": "stop",
        "session_id": session["id"],
        "started_at": session["started_at"],
        "ended_at": now,
        "total_chunks": session["chunks"],
        "total_words": session["words"],
        "full_text_preview": full_text[:500],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_output(file_path):
    db = init_db()
    # Get last session (active or stopped)
    session = db.execute("SELECT id, started_at, total_chunks, total_words, status FROM dictation_sessions ORDER BY id DESC LIMIT 1").fetchone()
    if not session:
        db.close()
        return {"error": "No dictation sessions found"}

    session_id = session[0]
    chunks = db.execute("SELECT ts, text, confidence FROM dictation_chunks WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
    full_text = " ".join(c[1] for c in chunks if c[1])

    # Determine format from extension
    ext = Path(file_path).suffix.lower()
    output_path = Path(file_path)

    try:
        if ext == ".json":
            data = {
                "session_id": session_id,
                "started_at": session[1],
                "chunks": [{"ts": c[0], "text": c[1], "confidence": c[2]} for c in chunks],
                "full_text": full_text,
                "word_count": len(full_text.split()),
                "exported_at": datetime.now().isoformat()
            }
            output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        elif ext == ".md":
            lines = [f"# Dictation — {session[1]}\n"]
            for c in chunks:
                lines.append(f"**[{c[0]}]** {c[1]}\n")
            lines.append(f"\n---\n*{len(full_text.split())} mots*\n")
            output_path.write_text("\n".join(lines), encoding="utf-8")
        else:  # .txt default
            output_path.write_text(full_text, encoding="utf-8")

        db.execute("INSERT INTO dictation_exports (session_id, ts, format, file_path, word_count, success) VALUES (?,?,?,?,?,?)",
                   (session_id, datetime.now().isoformat(), ext, str(output_path), len(full_text.split()), 1))
        db.commit()

        result = {
            "action": "export",
            "session_id": session_id,
            "format": ext,
            "file_path": str(output_path.resolve()),
            "word_count": len(full_text.split()),
            "success": True,
            "ts": datetime.now().isoformat()
        }
    except Exception as e:
        result = {"action": "export", "error": str(e), "ts": datetime.now().isoformat()}

    db.close()
    return result

def do_format(fmt):
    """Show format options and last session info."""
    db = init_db()
    session = db.execute("SELECT id, started_at, total_chunks, total_words, status FROM dictation_sessions ORDER BY id DESC LIMIT 1").fetchone()
    exports = db.execute("SELECT ts, format, file_path, word_count FROM dictation_exports ORDER BY id DESC LIMIT 5").fetchall()

    result = {
        "action": "format_info",
        "supported_formats": ["txt", "md", "json"],
        "requested_format": fmt,
        "last_session": {
            "id": session[0], "started_at": session[1], "chunks": session[2],
            "words": session[3], "status": session[4]
        } if session else None,
        "recent_exports": [{"ts": r[0], "format": r[1], "file": r[2], "words": r[3]} for r in exports],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    active = get_active_session(db)
    total_sessions = db.execute("SELECT COUNT(*) FROM dictation_sessions").fetchone()[0]
    total_chunks = db.execute("SELECT COUNT(*) FROM dictation_chunks").fetchone()[0]
    total_exports = db.execute("SELECT COUNT(*) FROM dictation_exports").fetchone()[0]
    total_words = db.execute("SELECT SUM(total_words) FROM dictation_sessions").fetchone()[0] or 0

    result = {
        "status": "ok",
        "active_session": active,
        "total_sessions": total_sessions,
        "total_chunks": total_chunks,
        "total_words_dictated": total_words,
        "total_exports": total_exports,
        "supported_formats": ["txt", "md", "json"],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="JARVIS Dictation Mode — COWORK #233")
    parser.add_argument("--start", action="store_true", help="Start dictation session")
    parser.add_argument("--stop", action="store_true", help="Stop dictation session")
    parser.add_argument("--output", type=str, metavar="FILE", help="Export to file (.txt/.md/.json)")
    parser.add_argument("--format", type=str, metavar="FMT", help="Show format info")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.start:
        print(json.dumps(do_start(), ensure_ascii=False, indent=2))
    elif args.stop:
        print(json.dumps(do_stop(), ensure_ascii=False, indent=2))
    elif args.output:
        print(json.dumps(do_output(args.output), ensure_ascii=False, indent=2))
    elif args.format:
        print(json.dumps(do_format(args.format), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
