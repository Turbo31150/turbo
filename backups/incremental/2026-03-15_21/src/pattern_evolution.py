"""Pattern Evolution — Auto-create and evolve dispatch patterns from usage data.

Analyzes misclassified prompts, underperforming patterns, and redundancies.
Suggests new patterns or modifications via TF-IDF keyword clustering.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.pattern_evolution")

DB_PATH = str(Path(__file__).parent.parent / "data" / "etoile.db")


@dataclass
class PatternSuggestion:
    """A suggested pattern action (create, evolve, merge, deprecate)."""
    action: str
    pattern_type: str
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    model_suggestion: str = ""
    strategy_suggestion: str = "single"


class PatternEvolution:
    """Analyzes dispatch logs to suggest and auto-create new patterns."""

    KEYWORD_CLUSTERS: dict[str, list[str]] = {
        "deployment": ["deploy", "release", "production", "rollback", "staging", "ci", "cd"],
        "testing": ["test", "unittest", "pytest", "coverage", "assertion", "mock"],
        "documentation": ["doc", "readme", "wiki", "changelog", "comment", "docstring"],
        "database": ["sql", "database", "migrate", "schema", "query", "table", "index"],
        "networking": ["network", "http", "api", "socket", "tcp", "dns", "proxy"],
        "frontend": ["css", "html", "react", "vue", "ui", "component", "layout"],
        "infrastructure": ["docker", "kubernetes", "terraform", "ansible", "cloud", "server"],
        "nlp": ["nlp", "tokenize", "embedding", "sentiment", "language", "translation"],
        "visualization": ["chart", "graph", "plot", "dashboard", "metrics", "visualization"],
        "automation": ["cron", "schedule", "pipeline", "workflow", "automation", "trigger"],
        "security": ["security", "auth", "token", "encrypt", "firewall", "vulnerability"],
        "monitoring": ["monitor", "alert", "health", "uptime", "log", "trace"],
    }

    def __init__(self) -> None:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pattern_evolution_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    pattern_type TEXT,
                    description TEXT,
                    confidence REAL,
                    applied INTEGER DEFAULT 0,
                    created_at REAL
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("PatternEvolution init DB error: %s", e)

    def _find_misclassified(self) -> list[PatternSuggestion]:
        """Find prompts dispatched to generic/simple that match known clusters."""
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT prompt, pattern_used FROM dispatch_log "
                "WHERE pattern_used IN ('simple', 'freeform', 'general') "
                "ORDER BY timestamp DESC LIMIT 200"
            ).fetchall()
            conn.close()
        except Exception:
            return []

        # Count keyword hits per cluster
        cluster_hits: dict[str, list[str]] = {k: [] for k in self.KEYWORD_CLUSTERS}
        for prompt, _pattern in rows:
            prompt_lower = prompt.lower() if prompt else ""
            for cluster_name, keywords in self.KEYWORD_CLUSTERS.items():
                if any(kw in prompt_lower for kw in keywords):
                    cluster_hits[cluster_name].append(prompt_lower)

        suggestions: list[PatternSuggestion] = []
        for cluster_name, hits in cluster_hits.items():
            if len(hits) >= 3:
                # Check if pattern already exists
                try:
                    conn = sqlite3.connect(DB_PATH)
                    existing = conn.execute(
                        "SELECT COUNT(*) FROM agent_patterns WHERE pattern_type = ?",
                        (cluster_name,)
                    ).fetchone()
                    conn.close()
                    if existing and existing[0] > 0:
                        continue
                except Exception:
                    pass

                confidence = min(len(hits) / 10.0, 1.0)
                suggestions.append(PatternSuggestion(
                    action="create",
                    pattern_type=cluster_name,
                    description=f"Auto-detected cluster '{cluster_name}' with {len(hits)} matching prompts",
                    evidence={"hit_count": len(hits), "sample": hits[:3]},
                    confidence=confidence,
                ))

        return suggestions

    def _find_underperforming(self) -> list[PatternSuggestion]:
        """Find patterns with low quality scores or high latency."""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT pattern_used as pattern, node, AVG(quality_score) as avg_q, "
                "COUNT(*) as n, AVG(latency_ms) as avg_lat "
                "FROM dispatch_log GROUP BY pattern_used, node "
                "HAVING n >= 5"
            ).fetchall()
            conn.close()
        except Exception:
            return []

        suggestions: list[PatternSuggestion] = []
        for row in rows:
            avg_q = row["avg_q"] if isinstance(row, dict) else (row["avg_q"] if hasattr(row, "__getitem__") else 0)
            pattern = row["pattern"] if isinstance(row, dict) else row["pattern"]
            if avg_q is not None and avg_q < 0.5:
                suggestions.append(PatternSuggestion(
                    action="evolve",
                    pattern_type=pattern,
                    description=f"Pattern '{pattern}' underperforming (avg_quality={avg_q:.2f})",
                    evidence=dict(row) if isinstance(row, dict) else {"pattern": pattern, "avg_q": avg_q},
                    confidence=0.7,
                ))

        return suggestions

    def _find_redundant(self) -> list[PatternSuggestion]:
        """Find redundant or overlapping patterns."""
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT pattern_type, keywords FROM agent_patterns"
            ).fetchall()
            conn.close()
        except Exception:
            return []

        # Simple overlap detection
        suggestions: list[PatternSuggestion] = []
        patterns = [(r[0], set((r[1] or "").lower().split(","))) for r in rows]
        for i, (p1, kw1) in enumerate(patterns):
            for j, (p2, kw2) in enumerate(patterns):
                if i >= j or not kw1 or not kw2:
                    continue
                overlap = kw1 & kw2
                if len(overlap) > len(kw1) * 0.7:
                    suggestions.append(PatternSuggestion(
                        action="merge",
                        pattern_type=f"{p1}+{p2}",
                        description=f"Patterns '{p1}' and '{p2}' overlap significantly",
                        confidence=0.5,
                    ))
        return suggestions

    def analyze_gaps(self) -> list[PatternSuggestion]:
        """Run all gap analysis and return sorted suggestions."""
        suggestions = (
            self._find_misclassified()
            + self._find_underperforming()
            + self._find_redundant()
        )
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        return suggestions

    def auto_create_patterns(self, min_confidence: float = 0.5) -> list[dict[str, Any]]:
        """Automatically create new patterns from high-confidence suggestions."""
        suggestions = self.analyze_gaps()
        created: list[dict[str, Any]] = []
        for s in suggestions:
            if s.action == "create" and s.confidence >= min_confidence:
                success = self._create_pattern(s)
                self._log_evolution(s, applied=success)
                created.append({
                    "pattern": s.pattern_type,
                    "created": success,
                    "confidence": s.confidence,
                })
        return created

    def evolve_patterns(self, min_confidence: float = 0.3) -> list[dict[str, Any]]:
        """Log evolution suggestions for existing patterns."""
        suggestions = self.analyze_gaps()
        evolved: list[dict[str, Any]] = []
        for s in suggestions:
            if s.action == "evolve" and s.confidence >= min_confidence:
                self._log_evolution(s, applied=True)
                evolved.append({
                    "pattern": s.pattern_type,
                    "action": "evolution_logged",
                    "confidence": s.confidence,
                })
        return evolved

    def _create_pattern(self, suggestion: PatternSuggestion) -> bool:
        """Insert a new pattern into agent_patterns."""
        try:
            keywords = ",".join(
                self.KEYWORD_CLUSTERS.get(suggestion.pattern_type, [suggestion.pattern_type])
            )
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO agent_patterns (pattern_type, agent_id, model_primary, strategy, system_prompt) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    suggestion.pattern_type,
                    f"auto_{suggestion.pattern_type}",
                    suggestion.model_suggestion or "qwen3-8b",
                    suggestion.strategy_suggestion or "single",
                    f"Expert {suggestion.pattern_type} agent. {suggestion.description}",
                ),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning("_create_pattern failed: %s", e)
            return False

    def _log_evolution(self, suggestion: PatternSuggestion, applied: bool = False) -> None:
        """Log an evolution event."""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO pattern_evolution_log (action, pattern_type, description, confidence, applied, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (suggestion.action, suggestion.pattern_type, suggestion.description,
                 suggestion.confidence, int(applied), time.time()),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug("_log_evolution failed: %s", e)

    def get_evolution_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent evolution events."""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM pattern_evolution_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get evolution statistics."""
        try:
            conn = sqlite3.connect(DB_PATH)
            total = conn.execute("SELECT COUNT(*) FROM pattern_evolution_log").fetchone()[0]
            applied = conn.execute("SELECT COUNT(*) FROM pattern_evolution_log WHERE applied = 1").fetchone()[0]
            by_action = conn.execute(
                "SELECT action, COUNT(*) as c FROM pattern_evolution_log GROUP BY action"
            ).fetchall()
            conn.close()
            return {
                "total_suggestions": total,
                "applied": applied,
                "by_action": {r[0]: r[1] for r in by_action},
            }
        except Exception:
            return {"total_suggestions": 0}


_evolution: PatternEvolution | None = None


def get_evolution() -> PatternEvolution:
    """Get or create the singleton PatternEvolution instance."""
    global _evolution
    if _evolution is None:
        _evolution = PatternEvolution()
    return _evolution
