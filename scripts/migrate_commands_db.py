import sqlite3
from pathlib import Path

db_path = Path("/home/turbo/jarvis/data/jarvis.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Renommer la table existante
try:
    cursor.execute("ALTER TABLE voice_commands RENAME TO voice_commands_old;")
except sqlite3.OperationalError:
    pass

# Créer la nouvelle table avec le bon schéma (attendu par src/commands.py)
cursor.execute("""
CREATE TABLE IF NOT EXISTS voice_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    description TEXT,
    triggers TEXT NOT NULL,
    action_type TEXT NOT NULL,
    action TEXT NOT NULL,
    params TEXT DEFAULT '[]',
    confirm INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    created_at REAL,
    usage_count INTEGER DEFAULT 0,
    last_used REAL,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0
);
""")

# Essayer de migrer les données existantes si possible
try:
    cursor.execute("""
    INSERT INTO voice_commands (name, category, description, triggers, action_type, action)
    SELECT 
        command as name, 
        'legacy' as category, 
        'Legacy command ' || command as description, 
        '["' || command || '"]' as triggers, 
        'bash' as action_type, 
        action 
    FROM voice_commands_old;
    """)
except Exception as e:
    print(f"Erreur de migration des anciennes données : {e}")

conn.commit()
conn.close()
print("Migration de la table voice_commands terminée.")
