
import sqlite3
import json
import time
from pathlib import Path

DB_MEMORY = Path("/home/turbo/jarvis/data/agent_memory.db")

class AgentMemory:
    """Blueprint Etoile Episodic Memory System."""

    def __init__(self):
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_MEMORY)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                role TEXT,
                content TEXT,
                summary TEXT,
                importance REAL DEFAULT 0.5
            );
        """)
        conn.close()

    def record(self, role: str, content: str, importance: float = 0.5):
        conn = sqlite3.connect(DB_MEMORY)
        conn.execute("""
            INSERT INTO memory (timestamp, role, content, importance)
            VALUES (?, ?, ?, ?);
        """, (time.time(), role, content, importance))
        conn.commit()
        conn.close()

    def get_context(self, current_prompt: str, limit: int = 5) -> str:
        """Retrieve recent relevant memories as context string."""
        conn = sqlite3.connect(DB_MEMORY)
        rows = conn.execute("""
            SELECT role, content FROM memory 
            ORDER BY timestamp DESC LIMIT ?;
        """, (limit,)).fetchall()
        conn.close()
        
        if not rows: return ""
        
        context = "Historique récent:\n"
        for role, content in reversed(rows):
            context += f"{role}: {content[:100]}...\n"
        return context

agent_memory = AgentMemory()
