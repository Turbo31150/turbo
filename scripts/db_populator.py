
import sqlite3
import re
from pathlib import Path

DB_JARVIS = Path("/home/turbo/jarvis/data/jarvis.db")
PIPELINES_FILE = Path("/home/turbo/jarvis/src/commands_pipelines.py")

def extract_commands():
    if not PIPELINES_FILE.exists():
        return []
    
    with open(PIPELINES_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Regex to extract JarvisCommand(name, category, description, triggers, type, action, ...)
    # Simplified for basic import
    commands = []
    pattern = r'JarvisCommand\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*,\s*\[([^\]]+)\]'
    matches = re.finditer(pattern, content)
    
    for m in matches:
        name, cat, desc, trig_raw = m.groups()
        triggers = trig_raw.replace('"', '').replace("'", "").strip()
        commands.append((name, cat, desc, triggers))
        
    return commands

def populate():
    cmds = extract_commands()
    print(f"Extracted {len(cmds)} commands from pipelines.")
    
    conn = sqlite3.connect(DB_JARVIS)
    cursor = conn.cursor()
    
    # Clear existing
    cursor.execute("DELETE FROM commands;")
    
    for c in cmds:
        name, cat, desc, triggers = c
        cursor.execute("""
            INSERT OR REPLACE INTO commands (name, category, description, triggers, action_type, action)
            VALUES (?, ?, ?, ?, 'pipeline', '');
        """, (name, cat, desc, triggers))
    
    conn.commit()
    count = cursor.execute("SELECT COUNT(*) FROM commands;").fetchone()[0]
    conn.close()
    print(f"Populated {count} commands into jarvis.db")

if __name__ == "__main__":
    populate()
