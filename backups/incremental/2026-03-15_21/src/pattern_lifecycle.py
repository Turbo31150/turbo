"""JARVIS Pattern Lifecycle — Manages pattern creation, evolution, and deprecation.

Full lifecycle management:
  - Create new patterns from discovered clusters
  - Evolve patterns (update model, strategy, weights)
  - Deprecate underperforming patterns
  - Merge similar patterns
  - Split overloaded patterns
  - Track pattern health over time

Usage:
    from src.pattern_lifecycle import PatternLifecycle, get_lifecycle
    lc = get_lifecycle()
    lc.create_pattern("nlp", model="qwen3-8b", strategy="single")
    lc.evolve_pattern("code", model="qwen3-8b")
    lc.deprecate_pattern("fix_math_M3")
    report = lc.health_report()
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


__all__ = [
    "LifecycleEvent",
    "PatternLifecycle",
    "PatternState",
    "get_lifecycle",
]

logger = logging.getLogger("jarvis.pattern_lifecycle")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")


@dataclass
class PatternState:
    """Current state of a pattern."""
    pattern_type: str
    agent_id: str
    model_primary: str
    strategy: str
    status: str          # active, degraded, deprecated, new
    total_calls: int
    success_rate: float
    avg_quality: float
    avg_latency_ms: float
    last_used: str
    created: str


@dataclass
class LifecycleEvent:
    """A lifecycle event (create, evolve, deprecate, merge, split)."""
    event_type: str
    pattern: str
    detail: str
    old_value: str = ""
    new_value: str = ""


class PatternLifecycle:
    """Full lifecycle management for JARVIS patterns."""

    DEPRECATION_THRESHOLDS = {
        "min_calls": 10,
        "max_error_rate": 0.6,
        "min_quality": 0.2,
        "idle_days": 7,
    }

    def __init__(self):
        self._events: list[LifecycleEvent] = []
        self._ensure_table()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                CREATE TABLE IF NOT EXISTS pattern_lifecycle_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT, pattern TEXT,
                    detail TEXT, old_value TEXT, new_value TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.commit()
            db.close()
        except Exception:
            pass

    def get_all_patterns(self) -> list[PatternState]:
        """Get all patterns with their current state."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            patterns = db.execute("""
                SELECT p.pattern_type, p.agent_id, p.model_primary, p.strategy,
                       COALESCE(d.total, 0) as total_calls,
                       COALESCE(d.success_rate, 0) as success_rate,
                       COALESCE(d.avg_quality, 0) as avg_quality,
                       COALESCE(d.avg_latency, 0) as avg_latency,
                       COALESCE(d.last_used, '') as last_used
                FROM agent_patterns p
                LEFT JOIN (
                    SELECT classified_type,
                           COUNT(*) as total,
                           AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate,
                           AVG(quality_score) as avg_quality,
                           AVG(latency_ms) as avg_latency,
                           MAX(timestamp) as last_used
                    FROM agent_dispatch_log
                    GROUP BY classified_type
                ) d ON p.pattern_type = d.classified_type
                ORDER BY total_calls DESC
            """).fetchall()
            db.close()

            result = []
            for p in patterns:
                total = p["total_calls"]
                sr = p["success_rate"] or 0
                q = p["avg_quality"] or 0

                # Determine status
                if total == 0:
                    status = "new"
                elif sr < 0.4 or q < self.DEPRECATION_THRESHOLDS["min_quality"]:
                    status = "degraded"
                elif total < 3:
                    status = "new"
                else:
                    status = "active"

                result.append(PatternState(
                    pattern_type=p["pattern_type"],
                    agent_id=p["agent_id"],
                    model_primary=p["model_primary"],
                    strategy=p["strategy"],
                    status=status,
                    total_calls=total,
                    success_rate=round(sr, 3),
                    avg_quality=round(q, 3),
                    avg_latency_ms=round(p["avg_latency"] or 0, 1),
                    last_used=p["last_used"] or "",
                    created="",
                ))

            return result
        except Exception as e:
            logger.warning(f"Failed to get patterns: {e}")
            return []

    def create_pattern(self, pattern_type: str, agent_id: str = "",
                       model: str = "qwen3-8b", strategy: str = "single",
                       fallbacks: str = "") -> bool:
        """Create a new pattern."""
        if not agent_id:
            agent_id = f"agent-{pattern_type}"

        try:
            db = sqlite3.connect(DB_PATH)
            # Check if exists
            existing = db.execute(
                "SELECT COUNT(*) FROM agent_patterns WHERE pattern_type = ?",
                (pattern_type,)
            ).fetchone()[0]
            if existing:
                logger.info(f"Pattern {pattern_type} already exists")
                return False

            db.execute("""
                INSERT INTO agent_patterns
                (pattern_id, agent_id, pattern_type, strategy, model_primary, model_fallbacks)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (f"PAT_{pattern_type.upper()}", agent_id, pattern_type, strategy, model, fallbacks))
            db.commit()
            db.close()

            self._log_event("create", pattern_type, f"Created with model={model}, strategy={strategy}")
            return True
        except Exception as e:
            logger.warning(f"Failed to create pattern {pattern_type}: {e}")
            return False

    def evolve_pattern(self, pattern_type: str,
                       model: Optional[str] = None,
                       strategy: Optional[str] = None,
                       fallbacks: Optional[str] = None) -> bool:
        """Evolve a pattern (update model, strategy, etc.)."""
        try:
            db = sqlite3.connect(DB_PATH)
            updates = []
            params = []
            old_values = []

            if model:
                old = db.execute("SELECT model_primary FROM agent_patterns WHERE pattern_type = ?",
                                 (pattern_type,)).fetchone()
                old_values.append(f"model:{old[0] if old else 'none'}")
                updates.append("model_primary = ?")
                params.append(model)

            if strategy:
                old = db.execute("SELECT strategy FROM agent_patterns WHERE pattern_type = ?",
                                 (pattern_type,)).fetchone()
                old_values.append(f"strategy:{old[0] if old else 'none'}")
                updates.append("strategy = ?")
                params.append(strategy)

            if fallbacks is not None:
                updates.append("model_fallbacks = ?")
                params.append(fallbacks)

            if not updates:
                return False

            params.append(pattern_type)
            db.execute(f"UPDATE agent_patterns SET {', '.join(updates)} WHERE pattern_type = ?", params)
            db.commit()
            db.close()

            self._log_event("evolve", pattern_type,
                           f"Updated: {', '.join(updates)}",
                           old_value="; ".join(old_values),
                           new_value=f"model={model}, strategy={strategy}")
            return True
        except Exception as e:
            logger.warning(f"Failed to evolve pattern {pattern_type}: {e}")
            return False

    def deprecate_pattern(self, pattern_type: str) -> bool:
        """Deprecate (remove) a pattern."""
        try:
            db = sqlite3.connect(DB_PATH)
            existing = db.execute(
                "SELECT agent_id, model_primary FROM agent_patterns WHERE pattern_type = ?",
                (pattern_type,)
            ).fetchone()
            if not existing:
                return False

            db.execute("DELETE FROM agent_patterns WHERE pattern_type = ?", (pattern_type,))
            db.commit()
            db.close()

            self._log_event("deprecate", pattern_type,
                           f"Removed agent={existing[0]}, model={existing[1]}")
            return True
        except Exception as e:
            logger.warning(f"Failed to deprecate {pattern_type}: {e}")
            return False

    def merge_patterns(self, source: str, target: str) -> bool:
        """Merge source pattern into target (deprecate source, keep target)."""
        success = self.deprecate_pattern(source)
        if success:
            self._log_event("merge", source, f"Merged into {target}")
        return success

    def suggest_actions(self) -> list[dict]:
        """Suggest lifecycle actions based on current pattern health."""
        patterns = self.get_all_patterns()
        actions = []

        for p in patterns:
            # Deprecation candidates
            if (p.status == "degraded" and p.total_calls >= self.DEPRECATION_THRESHOLDS["min_calls"]
                    and p.success_rate < 1 - self.DEPRECATION_THRESHOLDS["max_error_rate"]):
                actions.append({
                    "action": "deprecate",
                    "pattern": p.pattern_type,
                    "reason": f"High error rate ({p.success_rate:.0%}) over {p.total_calls} calls",
                    "priority": 1,
                })

            # Model upgrade candidates
            if (p.status == "active" and p.avg_quality < 0.5
                    and p.total_calls >= 20 and p.model_primary in ("qwen3:1.7b",)):
                actions.append({
                    "action": "evolve",
                    "pattern": p.pattern_type,
                    "reason": f"Low quality ({p.avg_quality:.2f}) with basic model",
                    "suggestion": "Upgrade to qwen3-8b",
                    "priority": 2,
                })

            # Unused patterns
            if p.status == "new" and p.total_calls == 0:
                # Check if pattern_type starts with discovered prefixes
                if p.pattern_type.startswith(("fix_", "cross_", "discovered-")):
                    actions.append({
                        "action": "deprecate",
                        "pattern": p.pattern_type,
                        "reason": "Discovered pattern with 0 calls — no real usage",
                        "priority": 3,
                    })

            # Strategy optimization
            if (p.strategy == "race" and p.total_calls >= 20
                    and p.avg_latency_ms > 10000):
                actions.append({
                    "action": "evolve",
                    "pattern": p.pattern_type,
                    "reason": f"Race strategy with high latency ({p.avg_latency_ms:.0f}ms)",
                    "suggestion": "Switch to single strategy",
                    "priority": 2,
                })

        return sorted(actions, key=lambda a: a["priority"])

    def health_report(self) -> dict:
        """Full pattern health report."""
        patterns = self.get_all_patterns()

        status_counts = {"active": 0, "degraded": 0, "new": 0, "deprecated": 0}
        for p in patterns:
            status_counts[p.status] = status_counts.get(p.status, 0) + 1

        total_calls = sum(p.total_calls for p in patterns)
        active = [p for p in patterns if p.status == "active"]
        avg_quality = sum(p.avg_quality for p in active) / max(1, len(active))

        return {
            "total_patterns": len(patterns),
            "status_distribution": status_counts,
            "total_dispatches": total_calls,
            "avg_quality_active": round(avg_quality, 3),
            "top_patterns": [
                {"pattern": p.pattern_type, "calls": p.total_calls,
                 "quality": p.avg_quality, "status": p.status}
                for p in sorted(patterns, key=lambda p: -p.total_calls)[:10]
            ],
            "degraded_patterns": [
                {"pattern": p.pattern_type, "calls": p.total_calls,
                 "quality": p.avg_quality, "success_rate": p.success_rate}
                for p in patterns if p.status == "degraded"
            ],
            "suggested_actions": self.suggest_actions()[:10],
            "lifecycle_events": self._events[-20:],
        }

    def _log_event(self, event_type: str, pattern: str, detail: str,
                   old_value: str = "", new_value: str = ""):
        event = LifecycleEvent(event_type, pattern, detail, old_value, new_value)
        self._events.append(event)
        if len(self._events) > 500:
            self._events = self._events[-500:]

        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                INSERT INTO pattern_lifecycle_log
                (event_type, pattern, detail, old_value, new_value)
                VALUES (?, ?, ?, ?, ?)
            """, (event_type, pattern, detail, old_value, new_value))
            db.commit()
            db.close()
        except Exception:
            pass

    def get_lifecycle_history(self, pattern: Optional[str] = None,
                              limit: int = 50) -> list[dict]:
        """Get lifecycle event history."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            if pattern:
                rows = db.execute("""
                    SELECT * FROM pattern_lifecycle_log
                    WHERE pattern = ? ORDER BY id DESC LIMIT ?
                """, (pattern, limit)).fetchall()
            else:
                rows = db.execute("""
                    SELECT * FROM pattern_lifecycle_log ORDER BY id DESC LIMIT ?
                """, (limit,)).fetchall()
            db.close()
            return [dict(r) for r in rows]
        except Exception:
            return []


# Singleton
_lifecycle: Optional[PatternLifecycle] = None

def get_lifecycle() -> PatternLifecycle:
    global _lifecycle
    if _lifecycle is None:
        _lifecycle = PatternLifecycle()
    return _lifecycle
