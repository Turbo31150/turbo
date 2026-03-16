
import sqlite3
import json
from pathlib import Path

DB_ETOILE = Path("/home/turbo/jarvis/data/etoile.db")

PATTERNS = [
    ("task-router", "core", "Routeur de tâches principal", "all", "M1", 1.0),
    ("code-champion", "dev", "Expert en génération de code", "python,js,cpp", "gpt-oss", 1.9),
    ("deep-reasoning", "brain", "Raisonnement logique complexe", "logic,math", "M2", 1.5),
    ("quick-dispatch", "utility", "Réponses ultra-rapides", "chat,info", "OL1", 1.3),
    ("system-ops", "win", "Gestion système Linux/Bash", "system,process", "M1", 1.8),
    ("trading-analyst", "trading", "Analyse de signaux MEXC", "crypto,mexc", "OL1", 1.5),
    # Ajout des patterns dynamiques (catégories)
    ("win_registry", "system", "Expert Registre", "registry", "M1", 1.0),
    ("ia_vision", "multimodal", "Analyse d'images", "vision,image", "GEMINI", 1.2),
]

def migrate_patterns():
    conn = sqlite3.connect(DB_ETOILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category TEXT,
            description TEXT,
            keywords TEXT,
            target_node TEXT,
            weight REAL
        );
    """)
    
    for name, cat, desc, keys, node, weight in PATTERNS:
        cursor.execute("""
            INSERT OR REPLACE INTO agent_patterns (name, category, description, keywords, target_node, weight)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (name, cat, desc, keys, node, weight))
        
    conn.commit()
    count = cursor.execute("SELECT COUNT(*) FROM agent_patterns;").fetchone()[0]
    conn.close()
    print(f"✅ {count} Agent Patterns migrés vers etoile.db")

if __name__ == "__main__":
    migrate_patterns()
