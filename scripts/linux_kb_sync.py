"""Linux Knowledge Base Sync.
Stores Linux-specific porting lessons in etoile.db for future agents.
"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path("/home/turbo/jarvis/data/etoile.db")

def add_lesson(pattern, replacement, category="linux_porting"):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("INSERT INTO user_patterns (pattern, category) VALUES (?, ?)", 
                 (f"REPLACE {pattern} WITH {replacement}", category))
    conn.commit()
    conn.close()
    print(f"Lesson saved: {pattern} -> {replacement}")

if __name__ == "__main__":
    # Sync initial lessons
    lessons = [
        ("powershell", "bash"),
        ("Win32_OperatingSystem", "psutil/platform"),
        ("Get-CimInstance", "subprocess Linux tools"),
        ("C:\\", "/home/turbo/jarvis"),
        ("F:\\", "/home/turbo/jarvis"),
        (".venv/Scripts/python.exe", ".venv/bin/python")
    ]
    for p, r in lessons:
        try:
            add_lesson(p, r)
        except: pass
