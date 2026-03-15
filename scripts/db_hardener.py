
import sqlite3
import os
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [SQL-HARDEN] %(message)s')

def harden_db(db_path):
    try:
        conn = sqlite3.connect(db_path)
        # Performance & Reliability settings
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA cache_size=-64000;") # 64MB cache
        
        # Maintenance
        conn.execute("REINDEX;")
        conn.execute("VACUUM;")
        
        # Integrity check
        res = conn.execute("PRAGMA integrity_check;").fetchone()[0]
        conn.close()
        return f"OK ({res})"
    except Exception as e:
        return f"ERROR: {e}"

def run_audit():
    root = "/home/turbo/jarvis"
    dbs = []
    for r, d, files in os.walk(root):
        if "node_modules" in r or ".venv" in r: continue
        for f in files:
            if f.endswith(".db"):
                dbs.append(os.path.join(r, f))
    
    print(f"--- JARVIS SQL HARDENING (Found {len(dbs)} bases) ---")
    for db in dbs:
        status = harden_db(db)
        print(f"  {os.path.basename(db):<25}: {status}")

if __name__ == "__main__":
    run_audit()
