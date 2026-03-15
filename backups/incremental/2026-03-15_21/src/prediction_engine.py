"""JARVIS Prediction Engine — Temporal pattern analysis for user action prediction.

Records every user action with timestamp context, then predicts the most likely
next actions based on hour-of-day and day-of-week patterns.

Usage:
    from src.prediction_engine import prediction_engine
    prediction_engine.record_action("trading_scan", {"source": "voice"})
    predictions = prediction_engine.predict_next(n=3)
    await prediction_engine.pre_warm()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.prediction")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "etoile.db"

# SQL for the user_patterns table
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    hour INTEGER NOT NULL,
    weekday INTEGER NOT NULL,
    context TEXT,
    timestamp REAL NOT NULL
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_patterns_hour_weekday ON user_patterns(hour, weekday);
CREATE INDEX IF NOT EXISTS idx_patterns_action ON user_patterns(action);
"""


class PredictionEngine:
    """Predicts user actions based on temporal patterns."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else DB_PATH
        self._cache: dict[str, list[dict[str, Any]]] = {}  # hour_weekday → predictions
        self._cache_ts: float = 0
        self._cache_ttl: float = 300.0  # 5min cache
        self._init_db()

    def _init_db(self) -> None:
        """Create table if not exists."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.executescript(CREATE_TABLE_SQL + CREATE_INDEX_SQL)
        except Exception as e:
            logger.warning("PredictionEngine DB init failed: %s", e)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    # ── Recording ─────────────────────────────────────────────────────────

    def record_action(self, action: str, context: dict[str, Any] | None = None) -> None:
        """Record a user action with temporal context."""
        now = datetime.now()
        ctx_json = json.dumps(context or {}, ensure_ascii=False)
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO user_patterns (action, hour, weekday, context, timestamp) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (action, now.hour, now.weekday(), ctx_json, time.time()),
                )
            # Invalidate cache
            self._cache_ts = 0
        except Exception as e:
            logger.warning("record_action failed: %s", e)

    # ── Prediction ────────────────────────────────────────────────────────

    def predict_next(self, n: int = 3, hour: int | None = None,
                     weekday: int | None = None) -> list[dict[str, Any]]:
        """Predict the N most likely next actions for given time context."""
        now = datetime.now()
        h = hour if hour is not None else now.hour
        wd = weekday if weekday is not None else now.weekday()

        # Check cache
        cache_key = f"{h}_{wd}"
        if (time.time() - self._cache_ts) < self._cache_ttl and cache_key in self._cache:
            return self._cache[cache_key][:n]

        # Query patterns: exact hour + same weekday, plus nearby hours for smoothing
        try:
            with self._conn() as conn:
                conn.row_factory = sqlite3.Row
                # Exact match (high weight)
                exact = conn.execute(
                    "SELECT action, COUNT(*) as cnt FROM user_patterns "
                    "WHERE hour = ? AND weekday = ? GROUP BY action ORDER BY cnt DESC LIMIT 20",
                    (h, wd),
                ).fetchall()

                # Same hour any day (medium weight)
                hourly = conn.execute(
                    "SELECT action, COUNT(*) as cnt FROM user_patterns "
                    "WHERE hour = ? GROUP BY action ORDER BY cnt DESC LIMIT 20",
                    (h,),
                ).fetchall()

                # Adjacent hours (low weight, for smoothing)
                adjacent = conn.execute(
                    "SELECT action, COUNT(*) as cnt FROM user_patterns "
                    "WHERE hour IN (?, ?) GROUP BY action ORDER BY cnt DESC LIMIT 20",
                    ((h - 1) % 24, (h + 1) % 24),
                ).fetchall()
        except Exception as e:
            logger.warning("predict_next query failed: %s", e)
            return []

        # Weighted scoring
        scores: dict[str, float] = defaultdict(float)
        for row in exact:
            scores[row["action"]] += row["cnt"] * 3.0  # exact: 3x weight
        for row in hourly:
            scores[row["action"]] += row["cnt"] * 1.5  # hourly: 1.5x
        for row in adjacent:
            scores[row["action"]] += row["cnt"] * 0.5  # adjacent: 0.5x

        if not scores:
            return []

        # Normalize to confidence [0, 1]
        max_score = max(scores.values())
        predictions = []
        for action, score in sorted(scores.items(), key=lambda x: -x[1]):
            confidence = min(1.0, score / max(max_score, 1))
            predictions.append({
                "action": action,
                "confidence": round(confidence, 3),
                "score": round(score, 1),
                "reason": f"hour={h} weekday={wd}",
            })

        # Update cache
        self._cache[cache_key] = predictions
        self._cache_ts = time.time()

        return predictions[:n]

    # ── Pre-warming ───────────────────────────────────────────────────────

    async def pre_warm(self) -> dict[str, Any]:
        """Pre-execute predicted actions (cache warming, pre-loading)."""
        predictions = self.predict_next(n=5)
        warmed = []

        for pred in predictions:
            if pred["confidence"] < 0.6:
                continue
            action = pred["action"]

            # Pre-warm specific action types
            try:
                if action in ("trading_scan", "trading_status"):
                    # Pre-load trading data
                    pass  # Trading module handles its own cache
                elif action in ("health_check", "cluster_status"):
                    from src.orchestrator_v2 import orchestrator_v2
                    orchestrator_v2.health_check()
                    warmed.append(action)
                elif action == "gpu_info":
                    import subprocess, asyncio
                    await asyncio.to_thread(
                        subprocess.run,
                        ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                        capture_output=True, timeout=3,
                    )
                    warmed.append(action)
            except Exception as e:
                logger.debug("Pre-warm failed for %s: %s", action, e)

        return {"predictions": len(predictions), "warmed": warmed}

    # ── User Profile ──────────────────────────────────────────────────────

    def get_user_profile(self) -> dict[str, Any]:
        """Deduce user profile from recorded patterns."""
        try:
            with self._conn() as conn:
                conn.row_factory = sqlite3.Row

                # Total actions
                total = conn.execute("SELECT COUNT(*) as c FROM user_patterns").fetchone()["c"]

                # Active hours
                hours = conn.execute(
                    "SELECT hour, COUNT(*) as cnt FROM user_patterns "
                    "GROUP BY hour ORDER BY cnt DESC"
                ).fetchall()

                # Top actions
                top_actions = conn.execute(
                    "SELECT action, COUNT(*) as cnt FROM user_patterns "
                    "GROUP BY action ORDER BY cnt DESC LIMIT 10"
                ).fetchall()

                # Active days
                days = conn.execute(
                    "SELECT weekday, COUNT(*) as cnt FROM user_patterns "
                    "GROUP BY weekday ORDER BY cnt DESC"
                ).fetchall()

                # Recent activity
                recent = conn.execute(
                    "SELECT action, timestamp FROM user_patterns "
                    "ORDER BY timestamp DESC LIMIT 5"
                ).fetchall()

            day_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
            return {
                "total_actions": total,
                "active_hours": [{"hour": r["hour"], "count": r["cnt"]} for r in hours[:5]],
                "top_actions": [{"action": r["action"], "count": r["cnt"]} for r in top_actions],
                "active_days": [{"day": day_names[r["weekday"]], "count": r["cnt"]} for r in days],
                "recent": [{"action": r["action"], "ts": r["timestamp"]} for r in recent],
            }
        except Exception as e:
            return {"error": str(e)}

    # ── Stats ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Prediction engine stats."""
        try:
            with self._conn() as conn:
                total = conn.execute("SELECT COUNT(*) FROM user_patterns").fetchone()[0]
                unique = conn.execute("SELECT COUNT(DISTINCT action) FROM user_patterns").fetchone()[0]
                latest = conn.execute("SELECT MAX(timestamp) FROM user_patterns").fetchone()[0]
            return {
                "total_patterns": total,
                "unique_actions": unique,
                "latest_record": latest,
                "cache_entries": len(self._cache),
            }
        except Exception as e:
            return {"error": str(e)}

    def cleanup(self, max_age_days: int = 90) -> int:
        """Remove old patterns."""
        cutoff = time.time() - (max_age_days * 86400)
        try:
            with self._conn() as conn:
                c = conn.execute("DELETE FROM user_patterns WHERE timestamp < ?", (cutoff,))
                return c.rowcount
        except Exception as e:
            logger.warning("cleanup failed: %s", e)
            return 0


# Global singleton
prediction_engine = PredictionEngine()
