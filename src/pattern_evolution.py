"""JARVIS Pattern Evolution Engine — Auto-create and evolve patterns from usage data.

Analyzes dispatch history to:
  - Detect unclassified request clusters
  - Suggest new patterns for emerging use cases
  - Evolve existing patterns (better system prompts, optimal nodes)
  - Merge redundant patterns
  - Track pattern health over time

Usage:
    from src.pattern_evolution import PatternEvolution, get_evolution
    evo = get_evolution()
    suggestions = evo.analyze_gaps()
    created = evo.auto_create_patterns()
    evolved = evo.evolve_patterns()
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


__all__ = [
    "PatternEvolution",
    "PatternSuggestion",
    "get_evolution",
]

logger = logging.getLogger("jarvis.pattern_evolution")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")


@dataclass
class PatternSuggestion:
    """A suggestion for a new or evolved pattern."""
    action: str            # create, evolve, merge, deprecate
    pattern_type: str
    description: str
    evidence: dict = field(default_factory=dict)
    confidence: float = 0.0
    model_suggestion: str = ""
    strategy_suggestion: str = "single"


class PatternEvolution:
    """Auto-evolve patterns based on usage data."""

    # Keyword clusters that suggest new patterns
    KEYWORD_CLUSTERS = {
        "deployment": ["deploy", "release", "publish", "build", "ci", "cd", "production"],
        "testing": ["test", "unittest", "pytest", "coverage", "assertion", "mock"],
        "documentation": ["doc", "readme", "comment", "docstring", "wiki", "manual"],
        "database": ["sql", "database", "sqlite", "postgres", "mysql", "migration", "schema"],
        "networking": ["api", "http", "rest", "graphql", "websocket", "endpoint", "route"],
        "frontend": ["html", "css", "react", "vue", "ui", "component", "layout", "style"],
        "infrastructure": ["docker", "kubernetes", "terraform", "ansible", "nginx", "cloud"],
        "nlp": ["nlp", "embedding", "sentiment", "tokenize", "language", "translation"],
        "visualization": ["chart", "graph", "plot", "dashboard", "visualize", "metric"],
        "automation": ["automate", "script", "batch", "cron", "schedule", "workflow"],
    }

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                CREATE TABLE IF NOT EXISTS pattern_evolution_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT, pattern_type TEXT, description TEXT,
                    confidence REAL, applied INTEGER DEFAULT 0,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.commit()
            db.close()
        except Exception:
            pass

    def analyze_gaps(self) -> list[PatternSuggestion]:
        """Analyze dispatch data to find gaps in pattern coverage."""
        suggestions = []

        # 1. Find prompts routed to generic patterns (simple/analysis) that match specific clusters
        suggestions.extend(self._find_misclassified())

        # 2. Find patterns with poor quality that need evolution
        suggestions.extend(self._find_underperforming())

        # 3. Find redundant patterns
        suggestions.extend(self._find_redundant())

        # Sort by confidence
        suggestions.sort(key=lambda s: -s.confidence)
        return suggestions

    def _find_misclassified(self) -> list[PatternSuggestion]:
        """Find prompts classified as generic but matching specific clusters."""
        suggestions = []
        try:
            db = sqlite3.connect(DB_PATH)

            # Get recent prompts classified as simple/analysis
            generic = db.execute("""
                SELECT request_text, classified_type FROM agent_dispatch_log
                WHERE classified_type IN ('simple', 'analysis')
                AND id > (SELECT COALESCE(MAX(id), 0) - 500 FROM agent_dispatch_log)
                LIMIT 200
            """).fetchall()

            db.close()

            # Check which clusters they match
            cluster_hits = {}
            for prompt_text, _ in generic:
                if not prompt_text:
                    continue
                lower = prompt_text.lower()
                for cluster_name, keywords in self.KEYWORD_CLUSTERS.items():
                    hits = sum(1 for kw in keywords if kw in lower)
                    if hits >= 2:
                        cluster_hits.setdefault(cluster_name, []).append(prompt_text[:100])

            # Check if cluster already has a pattern
            existing_patterns = set()
            try:
                db2 = sqlite3.connect(DB_PATH)
                rows = db2.execute("SELECT pattern_type FROM agent_patterns").fetchall()
                existing_patterns = {r[0] for r in rows}
                db2.close()
            except Exception:
                pass

            for cluster_name, prompts in cluster_hits.items():
                if len(prompts) >= 3 and cluster_name not in existing_patterns:
                    suggestions.append(PatternSuggestion(
                        action="create",
                        pattern_type=cluster_name,
                        description=f"Detected {len(prompts)} prompts matching '{cluster_name}' cluster, "
                                    f"currently misclassified as generic",
                        evidence={"sample_prompts": prompts[:5], "match_count": len(prompts)},
                        confidence=min(1.0, len(prompts) / 10),
                        model_suggestion="qwen3-8b",
                        strategy_suggestion="single",
                    ))

        except Exception:
            pass
        return suggestions

    def _find_underperforming(self) -> list[PatternSuggestion]:
        """Find patterns that need model/strategy evolution."""
        suggestions = []
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            underperformers = db.execute("""
                SELECT classified_type as pattern, node,
                       AVG(quality_score) as avg_q, COUNT(*) as n,
                       AVG(latency_ms) as avg_lat
                FROM agent_dispatch_log
                WHERE id > (SELECT COALESCE(MAX(id), 0) - 300 FROM agent_dispatch_log)
                GROUP BY classified_type, node
                HAVING n >= 5 AND avg_q < 0.5
                ORDER BY avg_q ASC
            """).fetchall()

            db.close()

            for u in underperformers:
                suggestions.append(PatternSuggestion(
                    action="evolve",
                    pattern_type=u["pattern"],
                    description=f"Pattern '{u['pattern']}' on node {u['node']} has low quality "
                                f"({u['avg_q']:.2f}) over {u['n']} dispatches",
                    evidence={
                        "node": u["node"], "avg_quality": round(u["avg_q"], 3),
                        "avg_latency_ms": round(u["avg_lat"] or 0, 0), "count": u["n"],
                    },
                    confidence=min(1.0, u["n"] / 20),
                    model_suggestion="qwen3-8b",
                ))

        except Exception:
            pass
        return suggestions

    def _find_redundant(self) -> list[PatternSuggestion]:
        """Find patterns that could be merged."""
        suggestions = []
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row

            # Patterns with very similar performance on same node
            patterns = db.execute("""
                SELECT classified_type as pattern, node,
                       AVG(quality_score) as avg_q, COUNT(*) as n
                FROM agent_dispatch_log
                WHERE id > (SELECT COALESCE(MAX(id), 0) - 500 FROM agent_dispatch_log)
                GROUP BY classified_type, node
                HAVING n >= 3
                ORDER BY node, avg_q
            """).fetchall()

            db.close()

            # Group by node and find very similar patterns
            by_node = {}
            for p in patterns:
                by_node.setdefault(p["node"], []).append(p)

            for node, pats in by_node.items():
                for i, p1 in enumerate(pats):
                    for p2 in pats[i + 1:]:
                        q_diff = abs((p1["avg_q"] or 0) - (p2["avg_q"] or 0))
                        if q_diff < 0.05 and p1["n"] < 5 and p2["n"] >= 10:
                            suggestions.append(PatternSuggestion(
                                action="merge",
                                pattern_type=p1["pattern"],
                                description=f"Pattern '{p1['pattern']}' (n={p1['n']}) "
                                            f"could merge into '{p2['pattern']}' (n={p2['n']}), "
                                            f"similar quality on {node}",
                                evidence={
                                    "merge_into": p2["pattern"],
                                    "quality_diff": round(q_diff, 4),
                                },
                                confidence=0.5,
                            ))
        except Exception:
            pass
        return suggestions

    def auto_create_patterns(self, min_confidence: float = 0.5) -> list[dict]:
        """Auto-create patterns from high-confidence suggestions."""
        suggestions = self.analyze_gaps()
        created = []

        for s in suggestions:
            if s.action == "create" and s.confidence >= min_confidence:
                success = self._create_pattern(s)
                created.append({
                    "pattern": s.pattern_type,
                    "description": s.description,
                    "confidence": s.confidence,
                    "created": success,
                })
                self._log_evolution(s, applied=success)

        return created

    def evolve_patterns(self, min_confidence: float = 0.3) -> list[dict]:
        """Apply evolution suggestions."""
        suggestions = self.analyze_gaps()
        evolved = []

        for s in suggestions:
            if s.action == "evolve" and s.confidence >= min_confidence:
                self._log_evolution(s, applied=False)
                evolved.append({
                    "pattern": s.pattern_type,
                    "description": s.description,
                    "model_suggestion": s.model_suggestion,
                    "action": "evolution_logged",
                })

        return evolved

    def _create_pattern(self, suggestion: PatternSuggestion) -> bool:
        """Create a new pattern in the DB."""
        try:
            # Generate system prompt from cluster keywords
            keywords = self.KEYWORD_CLUSTERS.get(suggestion.pattern_type, [])
            keywords_str = ", ".join(keywords[:5])
            system_prompt = f"Tu es un expert en {suggestion.pattern_type}. Domaines: {keywords_str}. Fournis des reponses precises et actionnables."

            db = sqlite3.connect(DB_PATH)
            db.execute("""
                INSERT OR IGNORE INTO agent_patterns
                (pattern_type, pattern_id, agent_id, model_primary, model_fallbacks, strategy)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                suggestion.pattern_type,
                f"PAT_EVO_{suggestion.pattern_type.upper()}",
                f"evo-{suggestion.pattern_type}",
                suggestion.model_suggestion or "qwen3-8b",
                "qwen3:1.7b",
                suggestion.strategy_suggestion or "single",
            ))
            db.commit()
            db.close()
            logger.info(f"Created evolved pattern: {suggestion.pattern_type}")
            return True
        except Exception as e:
            logger.warning(f"Failed to create pattern {suggestion.pattern_type}: {e}")
            return False

    def _log_evolution(self, suggestion: PatternSuggestion, applied: bool):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                INSERT INTO pattern_evolution_log
                (action, pattern_type, description, confidence, applied)
                VALUES (?, ?, ?, ?, ?)
            """, (suggestion.action, suggestion.pattern_type,
                  suggestion.description, suggestion.confidence, int(applied)))
            db.commit()
            db.close()
        except Exception:
            pass

    def get_evolution_history(self, limit: int = 50) -> list[dict]:
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT * FROM pattern_evolution_log ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            db.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_stats(self) -> dict:
        try:
            db = sqlite3.connect(DB_PATH)
            total = db.execute("SELECT COUNT(*) FROM pattern_evolution_log").fetchone()[0]
            applied = db.execute("SELECT COUNT(*) FROM pattern_evolution_log WHERE applied").fetchone()[0]
            by_action = db.execute("""
                SELECT action, COUNT(*) FROM pattern_evolution_log GROUP BY action
            """).fetchall()
            db.close()
            return {
                "total_suggestions": total,
                "total_applied": applied,
                "by_action": {r[0]: r[1] for r in by_action},
            }
        except Exception:
            return {"total_suggestions": 0}


_evolution: Optional[PatternEvolution] = None

def get_evolution() -> PatternEvolution:
    global _evolution
    if _evolution is None:
        _evolution = PatternEvolution()
    return _evolution
