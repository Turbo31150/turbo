
import json
import sqlite3
from pathlib import Path

DB_JARVIS = Path("/home/turbo/jarvis/data/jarvis.db")
SKILLS_JSON = Path("/home/turbo/jarvis/data/skills.json")

def import_skills():
    if not SKILLS_JSON.exists():
        print("Skills JSON not found.")
        return

    with open(SKILLS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    skills = data
    print(f"Found {len(skills)} skills in JSON.")

    conn = sqlite3.connect(DB_JARVIS)
    cursor = conn.cursor()
    
    # Clear and Import
    cursor.execute("DELETE FROM skills;")
    
    for s in skills:
        name = s.get("name")
        description = s.get("description", "")
        triggers_raw = s.get("triggers", name)
        if isinstance(triggers_raw, list):
            triggers = ", ".join(triggers_raw)
        else:
            triggers = str(triggers_raw)
        
        steps_raw = s.get("steps", [])
        steps = json.dumps(steps_raw)
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO skills (name, description, triggers, steps)
                VALUES (?, ?, ?, ?);
            """, (name, description, triggers, steps))
        except Exception as e:
            # Fallback if schema differs
            print(f"Error inserting {name}: {e}")
            
    conn.commit()
    count = cursor.execute("SELECT COUNT(*) FROM skills;").fetchone()[0]
    conn.close()
    print(f"Imported {count} skills into jarvis.db")

if __name__ == "__main__":
    import_skills()
