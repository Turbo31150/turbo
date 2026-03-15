"""Export SQL data to JSON for Git versioning.
Exports voice_commands, intents, and pipelines to data/export/
"""
import sqlite3
import json
import os
from pathlib import Path

EXPORT_DIR = Path("/home/turbo/jarvis/data/export")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def export_table(db_path, table_name, output_name):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
        data = [dict(r) for r in rows]
        with open(EXPORT_DIR / f"{output_name}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Exported {table_name} to {output_name}.json")
        conn.close()
    except Exception as e:
        print(f"Error exporting {table_name}: {e}")

if __name__ == "__main__":
    export_table("/home/turbo/jarvis/data/jarvis.db", "voice_commands", "voice_commands_linux")
    export_table("/home/turbo/jarvis/data/etoile.db", "intents", "intents_cluster")
    export_table("/home/turbo/jarvis/data/etoile.db", "pipelines", "pipelines_production")
