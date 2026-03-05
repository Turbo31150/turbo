"""JARVIS Agent Feedback Loop — Quality assessment and continuous improvement feedback.

Implements:
  - Post-dispatch quality scoring (auto + user feedback)
  - A/B testing between strategies/nodes
  - Trend detection (improving/degrading patterns)
  - Automatic strategy adjustment based on accumulated feedback
  - Quality threshold enforcement

Usage:
    from src.agent_feedback_loop import FeedbackLoop, get_feedback
    fb = get_feedback()
    fb.record_feedback("code", "M1", quality=0.9, user_rating=5)
    trends = fb.get_trends()
    adjustments = fb.suggest_adjustments()
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("jarvis.feedback_loop")

DB_PATH = "F:/BUREAU/turbo/etoile.db"


@dataclass
class FeedbackEntry:
    """A single feedback data point."""
    pattern: str
    node: str
    strategy: str
    auto_quality: float    # 0-1, machine-scored
    user_rating: int = 0   # 0-5, 0 = no rating
    latency_ms: float = 0
    success: bool = True
    timestamp: str = ""
    prompt_preview: str = ""


@dataclass
class PatternTrend:
    """Trend for a pattern over time."""
    pattern: str
    direction: str          # improving, stable, degrading
    recent_quality: float   # Last 10 dispatches avg
    older_quality: float    # Previous 10 dispatches avg
    change_pct: float       # Percentage change
    sample_size: int
    best_node: str
    best_strategy: str


@dataclass
class Adjustment:
    """Suggested routing adjustment."""
    pattern: str
    action: str             # switch_node, switch_strategy, increase_timeout, disable
    current: str
    suggested: str
    reason: str
    confidence: float
    expected_improvement: str


class FeedbackLoop:
    """Quality feedback and continuous improvement loop."""

    QUALITY_THRESHOLD = 0.4  # Minimum acceptable quality
    TREND_WINDOW = 20        # Last N dispatches for trend analysis

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._feedback_cache: list[FeedbackEntry] = []
        self._ensure_table()
        self._load_feedback()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(self.db_path)
            db.execute("""
                CREATE TABLE IF NOT EXISTS agent_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT, node TEXT, strategy TEXT,
                    auto_quality REAL, user_rating INTEGER DEFAULT 0,
                    latency_ms REAL, success INTEGER,
                    prompt_preview TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_fb_pattern ON agent_feedback(pattern)")
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to create feedback table: {e}")

    def _load_feedback(self):
        """Load recent feedback from DB."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT * FROM agent_feedback ORDER BY id DESC LIMIT 1000
            """).fetchall()
            db.close()
            self._feedback_cache = [
                FeedbackEntry(
                    pattern=r["pattern"], node=r["node"], strategy=r["strategy"] or "",
                    auto_quality=r["auto_quality"] or 0, user_rating=r["user_rating"] or 0,
                    latency_ms=r["latency_ms"] or 0, success=bool(r["success"]),
                    timestamp=r["timestamp"] or "", prompt_preview=r["prompt_preview"] or "",
                )
                for r in rows
            ]
        except Exception:
            self._feedback_cache = []

        # Seed from dispatch_log if empty
        if not self._feedback_cache:
            self._seed_from_dispatch_log()

    def _seed_from_dispatch_log(self):
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT classified_type as pattern, node, strategy,
                       quality_score, latency_ms, success,
                       request_text, timestamp
                FROM agent_dispatch_log
                WHERE classified_type IS NOT NULL
                ORDER BY id DESC LIMIT 500
            """).fetchall()
            db.close()

            for r in rows:
                self._feedback_cache.append(FeedbackEntry(
                    pattern=r["pattern"] or "unknown",
                    node=r["node"] or "M1",
                    strategy=r["strategy"] or "single",
                    auto_quality=r["quality_score"] or 0,
                    latency_ms=r["latency_ms"] or 0,
                    success=bool(r["success"]),
                    timestamp=r["timestamp"] or "",
                    prompt_preview=(r["request_text"] or "")[:100],
                ))
        except Exception:
            pass

    def record_feedback(self, pattern: str, node: str, strategy: str = "single",
                        quality: float = 0.5, user_rating: int = 0,
                        latency_ms: float = 0, success: bool = True,
                        prompt_preview: str = ""):
        """Record a feedback data point."""
        entry = FeedbackEntry(
            pattern=pattern, node=node, strategy=strategy,
            auto_quality=quality, user_rating=user_rating,
            latency_ms=latency_ms, success=success,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            prompt_preview=prompt_preview[:100],
        )
        self._feedback_cache.insert(0, entry)
        if len(self._feedback_cache) > 2000:
            self._feedback_cache = self._feedback_cache[:2000]

        try:
            db = sqlite3.connect(self.db_path)
            db.execute("""
                INSERT INTO agent_feedback
                (pattern, node, strategy, auto_quality, user_rating,
                 latency_ms, success, prompt_preview)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (pattern, node, strategy, quality, user_rating,
                  latency_ms, int(success), prompt_preview[:100]))
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to save feedback: {e}")

    def get_trends(self) -> list[PatternTrend]:
        """Analyze trends for each pattern."""
        trends = []
        pattern_data = defaultdict(list)
        for fb in self._feedback_cache:
            pattern_data[fb.pattern].append(fb)

        for pattern, entries in pattern_data.items():
            if len(entries) < 4:
                continue

            # Split into recent and older halves
            mid = min(self.TREND_WINDOW, len(entries) // 2)
            recent = entries[:mid]
            older = entries[mid:mid*2]

            if not recent or not older:
                continue

            recent_q = sum(e.auto_quality for e in recent) / len(recent)
            older_q = sum(e.auto_quality for e in older) / len(older)

            if older_q > 0:
                change = (recent_q - older_q) / older_q * 100
            else:
                change = 100 if recent_q > 0 else 0

            direction = "improving" if change > 10 else "degrading" if change < -10 else "stable"

            # Find best node and strategy
            node_quality = defaultdict(list)
            strat_quality = defaultdict(list)
            for e in entries:
                if e.success:
                    node_quality[e.node].append(e.auto_quality)
                    strat_quality[e.strategy].append(e.auto_quality)

            best_node = max(node_quality.items(),
                           key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0,
                           default=("M1", [0]))
            best_strat = max(strat_quality.items(),
                            key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0,
                            default=("single", [0]))

            trends.append(PatternTrend(
                pattern=pattern,
                direction=direction,
                recent_quality=round(recent_q, 3),
                older_quality=round(older_q, 3),
                change_pct=round(change, 1),
                sample_size=len(entries),
                best_node=best_node[0],
                best_strategy=best_strat[0],
            ))

        return sorted(trends, key=lambda t: abs(t.change_pct), reverse=True)

    def suggest_adjustments(self) -> list[Adjustment]:
        """Suggest routing adjustments based on feedback."""
        adjustments = []
        trends = self.get_trends()

        for trend in trends:
            if trend.direction == "degrading" and trend.sample_size >= 10:
                # Suggest switching node
                adjustments.append(Adjustment(
                    pattern=trend.pattern,
                    action="switch_node",
                    current=f"quality={trend.recent_quality:.2f}",
                    suggested=trend.best_node,
                    reason=f"Quality degrading {trend.change_pct:.0f}% ({trend.older_quality:.2f} -> {trend.recent_quality:.2f})",
                    confidence=min(1.0, trend.sample_size / 30),
                    expected_improvement=f"Best node {trend.best_node} has higher avg quality",
                ))

            if trend.recent_quality < self.QUALITY_THRESHOLD and trend.sample_size >= 5:
                adjustments.append(Adjustment(
                    pattern=trend.pattern,
                    action="increase_timeout",
                    current=f"quality={trend.recent_quality:.2f}",
                    suggested="Increase timeout or switch strategy",
                    reason=f"Quality below threshold ({trend.recent_quality:.2f} < {self.QUALITY_THRESHOLD})",
                    confidence=0.7,
                    expected_improvement="Higher quality responses with more time/tokens",
                ))

        # Check for A/B opportunities
        pattern_nodes = defaultdict(lambda: defaultdict(lambda: {"q": [], "n": 0}))
        for fb in self._feedback_cache[:200]:
            pn = pattern_nodes[fb.pattern][fb.node]
            pn["q"].append(fb.auto_quality)
            pn["n"] += 1

        for pattern, nodes in pattern_nodes.items():
            if len(nodes) < 2:
                continue
            node_scores = {
                n: sum(s["q"]) / max(1, len(s["q"]))
                for n, s in nodes.items()
                if s["n"] >= 3
            }
            if len(node_scores) >= 2:
                best = max(node_scores.items(), key=lambda x: x[1])
                worst = min(node_scores.items(), key=lambda x: x[1])
                if best[1] - worst[1] > 0.2:
                    adjustments.append(Adjustment(
                        pattern=pattern,
                        action="switch_node",
                        current=worst[0],
                        suggested=best[0],
                        reason=f"A/B: {best[0]} ({best[1]:.2f}) >> {worst[0]} ({worst[1]:.2f})",
                        confidence=min(1.0, min(nodes[best[0]]["n"], nodes[worst[0]]["n"]) / 10),
                        expected_improvement=f"+{(best[1] - worst[1]) * 100:.0f}% quality",
                    ))

        return sorted(adjustments, key=lambda a: -a.confidence)

    def get_quality_report(self) -> dict:
        """Overall quality report."""
        if not self._feedback_cache:
            return {"total": 0, "avg_quality": 0}

        total = len(self._feedback_cache)
        avg_q = sum(e.auto_quality for e in self._feedback_cache) / total
        success_rate = sum(1 for e in self._feedback_cache if e.success) / total
        rated = [e for e in self._feedback_cache if e.user_rating > 0]
        avg_user = sum(e.user_rating for e in rated) / max(1, len(rated))

        by_pattern = defaultdict(lambda: {"q": [], "n": 0})
        for e in self._feedback_cache:
            bp = by_pattern[e.pattern]
            bp["q"].append(e.auto_quality)
            bp["n"] += 1

        return {
            "total_feedback": total,
            "avg_quality": round(avg_q, 3),
            "success_rate": round(success_rate, 3),
            "user_rated": len(rated),
            "avg_user_rating": round(avg_user, 1),
            "patterns": {
                p: {"avg_quality": round(sum(s["q"]) / max(1, len(s["q"])), 3), "count": s["n"]}
                for p, s in sorted(by_pattern.items(), key=lambda x: -x[1]["n"])
            },
        }

    def get_ab_results(self) -> dict:
        """Get A/B test results per pattern (node comparison)."""
        results = {}
        pattern_nodes = defaultdict(lambda: defaultdict(lambda: {"q": [], "ok": 0, "n": 0}))

        for fb in self._feedback_cache:
            pn = pattern_nodes[fb.pattern][fb.node]
            pn["q"].append(fb.auto_quality)
            pn["n"] += 1
            if fb.success:
                pn["ok"] += 1

        for pattern, nodes in pattern_nodes.items():
            if len(nodes) >= 2:
                results[pattern] = {
                    n: {
                        "avg_quality": round(sum(s["q"]) / max(1, len(s["q"])), 3),
                        "success_rate": round(s["ok"] / max(1, s["n"]), 3),
                        "count": s["n"],
                    }
                    for n, s in sorted(nodes.items(), key=lambda x: -sum(x[1]["q"]) / max(1, len(x[1]["q"])))
                }

        return results


# Singleton
_feedback: Optional[FeedbackLoop] = None

def get_feedback() -> FeedbackLoop:
    global _feedback
    if _feedback is None:
        _feedback = FeedbackLoop()
    return _feedback
