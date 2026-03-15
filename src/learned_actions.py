"""Moteur Learned Actions — sauvegarde et replay de pipelines appris."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "learned_actions.db"
_FUZZY_THRESHOLD = 0.75
_CURRENT_PLATFORM = "linux" if os.name != "nt" else "windows"


def _similarity(a: str, b: str) -> float:
    """Score de similarité — aligné sur src.commands.similarity().
    Utilise max(SequenceMatcher, (jaccard + coverage) / 2).
    """
    a_lower, b_lower = a.lower().strip(), b.lower().strip()
    seq_score = SequenceMatcher(None, a_lower, b_lower).ratio()
    words_a = set(a_lower.split())
    words_b = set(b_lower.split())
    if words_a and words_b:
        intersection = words_a & words_b
        union = words_a | words_b
        jaccard = len(intersection) / len(union)
        coverage = len(intersection) / len(words_b)
        bow_score = (jaccard + coverage) / 2.0
    else:
        bow_score = 0.0
    return max(seq_score, bow_score)


class LearnedActionsEngine:
    """CRUD + match + exécution pour actions apprises."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or _DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._trigger_cache: dict[str, int] | None = None

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS learned_actions (
                    id INTEGER PRIMARY KEY,
                    canonical_name TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    platform TEXT DEFAULT 'both',
                    pipeline_steps TEXT NOT NULL,
                    context_required TEXT,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    avg_duration_ms REAL,
                    last_used TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    learned_from TEXT
                );
                CREATE TABLE IF NOT EXISTS learned_action_triggers (
                    id INTEGER PRIMARY KEY,
                    action_id INTEGER NOT NULL REFERENCES learned_actions(id) ON DELETE CASCADE,
                    phrase TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_executions (
                    id INTEGER PRIMARY KEY,
                    action_id INTEGER REFERENCES learned_actions(id),
                    trigger_text TEXT,
                    status TEXT,
                    duration_ms REAL,
                    output TEXT,
                    error TEXT,
                    executed_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_trigger_phrase ON learned_action_triggers(phrase);
                CREATE INDEX IF NOT EXISTS idx_trigger_action ON learned_action_triggers(action_id);
                CREATE INDEX IF NOT EXISTS idx_la_category ON learned_actions(category);
                CREATE INDEX IF NOT EXISTS idx_la_platform ON learned_actions(platform);
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _invalidate_cache(self) -> None:
        self._trigger_cache = None

    def _build_cache(self) -> dict[str, int]:
        if self._trigger_cache is not None:
            return self._trigger_cache
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT phrase, action_id FROM learned_action_triggers"
            ).fetchall()
        self._trigger_cache = {r["phrase"].lower().strip(): r["action_id"] for r in rows}
        return self._trigger_cache

    def save_action(
        self,
        canonical_name: str,
        category: str,
        platform: str,
        trigger_phrases: list[str],
        pipeline_steps: list[dict[str, Any]],
        context_required: dict[str, Any] | None = None,
        learned_from: str | None = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO learned_actions
                   (canonical_name, category, platform, pipeline_steps, context_required, learned_from)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(canonical_name) DO UPDATE SET
                       category = excluded.category,
                       platform = excluded.platform,
                       pipeline_steps = excluded.pipeline_steps,
                       context_required = excluded.context_required,
                       learned_from = excluded.learned_from""",
                (
                    canonical_name,
                    category,
                    platform,
                    json.dumps(pipeline_steps),
                    json.dumps(context_required) if context_required else None,
                    learned_from,
                ),
            )
            # lastrowid peut être 0 après ON CONFLICT UPDATE — récupérer l'id réel
            action_id = cur.lastrowid
            if not action_id:
                row = conn.execute(
                    "SELECT id FROM learned_actions WHERE canonical_name = ?",
                    (canonical_name,),
                ).fetchone()
                action_id = row["id"]
            # Supprimer anciens triggers et réinsérer
            conn.execute(
                "DELETE FROM learned_action_triggers WHERE action_id = ?",
                (action_id,),
            )
            for phrase in trigger_phrases:
                conn.execute(
                    "INSERT INTO learned_action_triggers (action_id, phrase) VALUES (?, ?)",
                    (action_id, phrase.lower().strip()),
                )
        self._invalidate_cache()
        return action_id

    def get_action(self, action_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM learned_actions WHERE id = ?", (action_id,)
            ).fetchone()
            if not row:
                return None
            triggers = conn.execute(
                "SELECT phrase FROM learned_action_triggers WHERE action_id = ?",
                (action_id,),
            ).fetchall()
        return {
            **dict(row),
            "pipeline_steps": json.loads(row["pipeline_steps"]),
            "triggers": [t["phrase"] for t in triggers],
        }

    def match(
        self, text: str, platform: str | None = None
    ) -> dict[str, Any] | None:
        platform = platform or _CURRENT_PLATFORM
        text_lower = text.lower().strip()
        cache = self._build_cache()

        # 1. Match exact O(1)
        if text_lower in cache:
            action_id = cache[text_lower]
            action = self.get_action(action_id)
            if action and action["platform"] in (platform, "both"):
                return action

        # 2. Fuzzy match
        best_score = 0.0
        best_action_id = None
        for phrase, action_id in cache.items():
            score = _similarity(text_lower, phrase)
            if score > best_score:
                best_score = score
                best_action_id = action_id

        if best_score >= _FUZZY_THRESHOLD and best_action_id is not None:
            action = self.get_action(best_action_id)
            if action and action["platform"] in (platform, "both"):
                return action

        return None

    def record_execution(
        self,
        action_id: int,
        trigger_text: str,
        status: str,
        duration_ms: float,
        output: str = "",
        error: str = "",
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO action_executions
                   (action_id, trigger_text, status, duration_ms, output, error)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (action_id, trigger_text, status, duration_ms, output, error),
            )
            if status == "success":
                conn.execute(
                    """UPDATE learned_actions SET
                       success_count = success_count + 1,
                       last_used = CURRENT_TIMESTAMP,
                       avg_duration_ms = COALESCE(
                           (avg_duration_ms * success_count + ?) / (success_count + 1),
                           ?
                       )
                       WHERE id = ?""",
                    (duration_ms, duration_ms, action_id),
                )
            else:
                conn.execute(
                    "UPDATE learned_actions SET fail_count = fail_count + 1 WHERE id = ?",
                    (action_id,),
                )

    def list_actions(
        self, category: str | None = None, platform: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM learned_actions WHERE 1=1"
        params: list[Any] = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if platform:
            query += " AND platform IN (?, 'both')"
            params.append(platform)
        query += " ORDER BY success_count DESC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
