#!/usr/bin/env python3
"""win_screen_recorder.py — Screenshot-based screen recorder concept.
COWORK #239 — Batch 107: Windows Gaming & Media

Usage:
    python dev/win_screen_recorder.py --start
    python dev/win_screen_recorder.py --stop
    python dev/win_screen_recorder.py --list
    python dev/win_screen_recorder.py --config
    python dev/win_screen_recorder.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, ctypes
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "screen_recorder.db"
SCREENSHOTS_DIR = DEV / "data" / "screenshots"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS recording_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        status TEXT DEFAULT 'active',
        interval_ms INTEGER DEFAULT 1000,
        region TEXT DEFAULT 'fullscreen',
        format TEXT DEFAULT 'png',
        frames_captured INTEGER DEFAULT 0,
        output_dir TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS frames (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        ts TEXT NOT NULL,
        frame_num INTEGER,
        file_path TEXT,
        width INTEGER,
        height INTEGER,
        size_bytes INTEGER,
        FOREIGN KEY (session_id) REFERENCES recording_sessions(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS recorder_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    # Default config
    defaults = {
        "interval_ms": "1000",
        "format": "png",
        "region": "fullscreen",
        "max_frames": "300",
        "quality": "high"
    }
    for k, v in defaults.items():
        if db.execute("SELECT COUNT(*) FROM recorder_config WHERE key=?", (k,)).fetchone()[0] == 0:
            db.execute("INSERT INTO recorder_config (key, value, updated_at) VALUES (?,?,?)",
                       (k, v, datetime.now().isoformat()))
    db.commit()
    return db

def get_config(db):
    rows = db.execute("SELECT key, value FROM recorder_config").fetchall()
    return {r[0]: r[1] for r in rows}

def get_screen_size():
    """Get screen size via ctypes."""
    try:
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        return w, h
    except Exception:
        return 1920, 1080

def take_screenshot(output_path):
    """Take a screenshot using powershell."""
    try:
        cmd = f'''powershell -NoProfile -Command "
Add-Type -AssemblyName System.Windows.Forms
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save('{output_path}')
$graphics.Dispose()
$bitmap.Dispose()
Write-Output OK
"'''
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        return "OK" in r.stdout
    except Exception:
        return False

def do_start():
    db = init_db()
    config = get_config(db)
    w, h = get_screen_size()

    # Deactivate any existing sessions
    db.execute("UPDATE recording_sessions SET status='stopped', ended_at=? WHERE status='active'",
               (datetime.now().isoformat(),))

    now = datetime.now()
    session_dir = SCREENSHOTS_DIR / now.strftime("%Y%m%d_%H%M%S")
    session_dir.mkdir(parents=True, exist_ok=True)

    cursor = db.execute("""INSERT INTO recording_sessions (started_at, status, interval_ms, region, format, output_dir)
                          VALUES (?,?,?,?,?,?)""",
                        (now.isoformat(), "active", int(config.get("interval_ms", 1000)),
                         config.get("region", "fullscreen"), config.get("format", "png"), str(session_dir)))
    session_id = cursor.lastrowid

    # Take first screenshot as proof of concept
    frame_path = str(session_dir / f"frame_0001.{config.get('format', 'png')}")
    success = take_screenshot(frame_path)

    if success and os.path.exists(frame_path):
        size = os.path.getsize(frame_path)
        db.execute("""INSERT INTO frames (session_id, ts, frame_num, file_path, width, height, size_bytes)
                      VALUES (?,?,?,?,?,?,?)""",
                   (session_id, now.isoformat(), 1, frame_path, w, h, size))
        db.execute("UPDATE recording_sessions SET frames_captured=1 WHERE id=?", (session_id,))
    db.commit()

    result = {
        "action": "start",
        "session_id": session_id,
        "started_at": now.isoformat(),
        "screen_size": f"{w}x{h}",
        "interval_ms": int(config.get("interval_ms", 1000)),
        "format": config.get("format", "png"),
        "output_dir": str(session_dir),
        "first_frame_captured": success,
        "note": "Single-frame capture. For continuous recording, run in loop externally.",
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_stop():
    db = init_db()
    session = db.execute("SELECT id, started_at, frames_captured FROM recording_sessions WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
    if not session:
        db.close()
        return {"error": "No active recording session"}

    now = datetime.now().isoformat()
    db.execute("UPDATE recording_sessions SET status='stopped', ended_at=? WHERE id=?", (now, session[0]))
    db.commit()

    result = {
        "action": "stop",
        "session_id": session[0],
        "started_at": session[1],
        "ended_at": now,
        "frames_captured": session[2],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_list():
    db = init_db()
    sessions = db.execute("""SELECT id, started_at, ended_at, status, frames_captured, interval_ms, output_dir
                            FROM recording_sessions ORDER BY id DESC LIMIT 20""").fetchall()
    result = {
        "action": "list",
        "sessions": [{
            "id": r[0], "started_at": r[1], "ended_at": r[2], "status": r[3],
            "frames": r[4], "interval_ms": r[5], "output_dir": r[6]
        } for r in sessions],
        "total": len(sessions),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_config():
    db = init_db()
    config = get_config(db)
    w, h = get_screen_size()
    result = {
        "action": "config",
        "current_config": config,
        "screen_size": f"{w}x{h}",
        "screenshots_dir": str(SCREENSHOTS_DIR),
        "supported_formats": ["png", "bmp", "jpg"],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    active = db.execute("SELECT COUNT(*) FROM recording_sessions WHERE status='active'").fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM recording_sessions").fetchone()[0]
    total_frames = db.execute("SELECT SUM(frames_captured) FROM recording_sessions").fetchone()[0] or 0
    w, h = get_screen_size()
    result = {
        "status": "ok",
        "active_recordings": active,
        "total_sessions": total,
        "total_frames": total_frames,
        "screen_size": f"{w}x{h}",
        "screenshots_dir": str(SCREENSHOTS_DIR),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="Screen Recorder — COWORK #239")
    parser.add_argument("--start", action="store_true", help="Start recording session")
    parser.add_argument("--stop", action="store_true", help="Stop recording session")
    parser.add_argument("--list", action="store_true", help="List recording sessions")
    parser.add_argument("--config", action="store_true", help="Show recorder config")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.start:
        print(json.dumps(do_start(), ensure_ascii=False, indent=2))
    elif args.stop:
        print(json.dumps(do_stop(), ensure_ascii=False, indent=2))
    elif args.list:
        print(json.dumps(do_list(), ensure_ascii=False, indent=2))
    elif args.config:
        print(json.dumps(do_config(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
