
import sqlite3
import os
from pathlib import Path

DB_JARVIS = Path("/home/turbo/jarvis/data/jarvis.db")
DB_ETOILE = Path("/home/turbo/jarvis/data/etoile.db")

def check_db(path):
    if not path.exists():
        return f"MISSING: {path}"
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()[0]
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        count = len(tables)
        conn.close()
        return f"OK ({res}), {count} tables found"
    except Exception as e:
        return f"ERROR: {e}"

def validate_sync():
    print("=== JARVIS DATABASE SYNC VALIDATOR ===")
    print(f"Jarvis DB: {check_db(DB_JARVIS)}")
    print(f"Etoile DB: {check_db(DB_ETOILE)}")
    
    # Specific check for crucial tables
    conn_j = sqlite3.connect(DB_JARVIS)
    cmd_count = conn_j.execute("SELECT COUNT(*) FROM commands;").fetchone()[0]
    voice_count = conn_j.execute("SELECT COUNT(*) FROM voice_commands;").fetchone()[0]
    print(f"Stats Jarvis: {cmd_count} commands, {voice_count} voice entries")
    conn_j.close()

    conn_e = sqlite3.connect(DB_ETOILE)
    intent_count = conn_e.execute("SELECT COUNT(*) FROM intents;").fetchone()[0]
    map_count = conn_e.execute("SELECT COUNT(*) FROM map;").fetchone()[0]
    print(f"Stats Etoile: {intent_count} intents, {map_count} map entries")
    conn_e.close()

if __name__ == "__main__":
    validate_sync()
