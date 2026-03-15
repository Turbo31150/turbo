
import sqlite3
import logging
from pathlib import Path

DB_ETOILE = Path("/home/turbo/jarvis/data/etoile.db")

class DynamicAgentLoader:
    """Loads agent patterns from DB at runtime."""

    def __init__(self):
        self.cached_patterns = {}

    def refresh_patterns(self):
        """Fetch all patterns from agent_patterns table."""
        conn = sqlite3.connect(DB_ETOILE)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM agent_patterns").fetchall()
        
        self.cached_patterns = {r["name"]: dict(r) for r in rows}
        conn.close()
        return self.cached_patterns

    def get_pattern_for_task(self, task_type):
        if not self.cached_patterns:
            self.refresh_patterns()
        return self.cached_patterns.get(task_type)

dynamic_agents = DynamicAgentLoader()
