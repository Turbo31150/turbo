#!/usr/bin/env python3
"""JARVIS Clipboard History — Historique presse-papiers Windows."""
import json, sys, os, sqlite3, subprocess, time
from datetime import datetime

DB_PATH = "C:/Users/franc/.openclaw/workspace/dev/clipboard.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS clips (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT,
        content TEXT NOT NULL, content_type TEXT DEFAULT 'text',
        length INTEGER
    )""")
    conn.commit()
    return conn

def get_clipboard():
    try:
        r = subprocess.run(["bash", "-Command", "Get-Clipboard"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else None
    except: return None

def set_clipboard(text):
    subprocess.run(["bash", "-Command", f"Set-Clipboard -Value '{text}'"], timeout=5)

def detect_type(text):
    if not text: return "empty"
    if text.startswith(("http://", "https://")): return "url"
    if any(kw in text for kw in ["def ", "class ", "import ", "function ", "const ", "var "]): return "code"
    if len(text) > 500: return "long_text"
    return "text"

def save_clip(conn, content):
    if not content: return
    c = conn.cursor()
    # Check duplicate (last entry)
    c.execute("SELECT content FROM clips ORDER BY id DESC LIMIT 1")
    last = c.fetchone()
    if last and last[0] == content: return  # Skip duplicate
    ctype = detect_type(content)
    c.execute("INSERT INTO clips (ts, content, content_type, length) VALUES (?,?,?,?)",
              (datetime.now().isoformat(), content[:5000], ctype, len(content)))
    conn.commit()
    # Keep only last 100
    c.execute("DELETE FROM clips WHERE id NOT IN (SELECT id FROM clips ORDER BY id DESC LIMIT 100)")
    conn.commit()

def monitor(conn):
    print("[CLIPBOARD] Monitoring... Ctrl+C to stop")
    last = None
    while True:
        current = get_clipboard()
        if current and current != last:
            save_clip(conn, current)
            ctype = detect_type(current)
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] [{ctype}] {current[:60]}...")
            last = current
        time.sleep(2)

if __name__ == "__main__":
    conn = init_db()
    if "--monitor" in sys.argv:
        monitor(conn)
    elif "--list" in sys.argv:
        c = conn.cursor()
        c.execute("SELECT id, ts, content_type, length, content FROM clips ORDER BY id DESC LIMIT 20")
        for r in c.fetchall():
            print(f"  #{r[0]} [{r[1][:16]}] {r[2]} ({r[3]}c): {r[4][:80]}")
    elif "--search" in sys.argv:
        idx = sys.argv.index("--search")
        q = " ".join(sys.argv[idx+1:])
        c = conn.cursor()
        c.execute("SELECT id, ts, content FROM clips WHERE content LIKE ? ORDER BY id DESC LIMIT 10", (f"%{q}%",))
        for r in c.fetchall():
            print(f"  #{r[0]} [{r[1][:16]}]: {r[2][:100]}")
    elif "--paste" in sys.argv:
        idx = sys.argv.index("--paste")
        clip_id = int(sys.argv[idx+1])
        c = conn.cursor()
        c.execute("SELECT content FROM clips WHERE id=?", (clip_id,))
        row = c.fetchone()
        if row:
            set_clipboard(row[0])
            print(f"Pasted #{clip_id} to clipboard")
        else:
            print(f"Clip #{clip_id} not found")
    else:
        print("Usage: clipboard_history.py --monitor | --list | --search TEXT | --paste ID")
    conn.close()
