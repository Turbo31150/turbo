"""JARVIS Pattern Discovery — Auto-discovers new patterns from dispatch logs and user behavior.

Analyzes dispatch_log for:
  - Keyword clusters not matching existing patterns
  - Emerging task types (new classify results)
  - Node performance shifts requiring new specialized agents
  - User behavior patterns (time-of-day, frequency, complexity trends)

Usage:
    from src.pattern_discovery import PatternDiscovery
    discovery = PatternDiscovery()
    new_patterns = discovery.discover()
    discovery.register_patterns(new_patterns)
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("jarvis.pattern_discovery")

DB_PATH = "F:/BUREAU/turbo/etoile.db"

# Known stop words to filter out
STOP_WORDS = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "en",
    "est", "sont", "a", "au", "aux", "ce", "cette", "ces", "que", "qui",
    "dans", "par", "pour", "sur", "avec", "pas", "plus", "ne", "se",
    "tu", "je", "il", "elle", "nous", "vous", "ils", "on",
    "the", "is", "are", "in", "on", "to", "for", "with", "and", "or",
    "a", "an", "it", "be", "do", "of", "at", "by", "from",
}


@dataclass
class DiscoveredPattern:
    """A newly discovered pattern candidate."""
    pattern_type: str
    keywords: list[str]
    sample_prompts: list[str]
    frequency: int       # How often seen
    confidence: float    # 0-1, how confident this is a real pattern
    suggested_node: str
    suggested_strategy: str
    reason: str


@dataclass
class BehaviorInsight:
    """User behavior pattern."""
    insight_type: str    # peak_hours, complexity_trend, pattern_shift, frequency_spike
    description: str
    data: dict
    actionable: bool = False
    suggestion: str = ""


class PatternDiscovery:
    """Discovers new patterns from dispatch logs and user behavior."""

    # Minimum occurrences to consider a new pattern
    MIN_FREQUENCY = 5
    MIN_CONFIDENCE = 0.6

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def discover(self) -> list[DiscoveredPattern]:
        """Run full discovery pipeline."""
        patterns = []
        patterns.extend(self._discover_from_unclassified())
        patterns.extend(self._discover_from_keyword_clusters())
        patterns.extend(self._discover_from_failed_dispatches())
        # Dedupe by pattern_type
        seen = set()
        unique = []
        for p in patterns:
            if p.pattern_type not in seen:
                seen.add(p.pattern_type)
                unique.append(p)
        return unique

    def _discover_from_unclassified(self) -> list[DiscoveredPattern]:
        """Find dispatches that were classified as 'simple' but have distinct keyword clusters."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT request_text as prompt, node, success, latency_ms
                FROM agent_dispatch_log
                WHERE classified_type = 'simple' OR classified_type IS NULL
                ORDER BY timestamp DESC
                LIMIT 500
            """).fetchall()
            db.close()
        except Exception:
            return []

        if len(rows) < self.MIN_FREQUENCY:
            return []

        # Extract keyword frequencies from "simple" prompts
        word_freq = Counter()
        prompt_words = defaultdict(list)  # word -> list of prompts

        for r in rows:
            prompt = (r["prompt"] or "").lower()
            words = set(re.findall(r'\b[a-zA-Zàéèùêôîû]{3,}\b', prompt)) - STOP_WORDS
            for w in words:
                word_freq[w] += 1
                prompt_words[w].append(prompt[:200])

        # Find keyword clusters (words that co-occur in multiple prompts)
        patterns = []
        existing_types = self._get_existing_types()

        # Look for frequent words that might indicate new patterns
        for word, count in word_freq.most_common(50):
            if count < self.MIN_FREQUENCY:
                break
            # Skip if this word is already a keyword for an existing pattern
            if word in existing_types:
                continue

            # Find co-occurring words
            co_words = Counter()
            for prompt in prompt_words[word]:
                words = set(re.findall(r'\b[a-zA-Zàéèùêôîû]{3,}\b', prompt)) - STOP_WORDS - {word}
                for w in words:
                    co_words[w] += 1

            # Build keyword cluster
            cluster = [word] + [w for w, c in co_words.most_common(5) if c >= count * 0.3]
            if len(cluster) >= 2:
                confidence = min(1.0, count / 20)  # Max confidence at 20+ occurrences
                patterns.append(DiscoveredPattern(
                    pattern_type=word,
                    keywords=cluster,
                    sample_prompts=prompt_words[word][:3],
                    frequency=count,
                    confidence=confidence,
                    suggested_node="M1",
                    suggested_strategy="single",
                    reason=f"Keyword '{word}' appears {count}x in 'simple' dispatches with co-words: {cluster[1:]}",
                ))

        return [p for p in patterns if p.confidence >= self.MIN_CONFIDENCE]

    def _discover_from_keyword_clusters(self) -> list[DiscoveredPattern]:
        """Cluster all prompts by TF-IDF-like scoring to find emerging topics."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT request_text as prompt, classified_type as pattern, node, success, quality_score
                FROM agent_dispatch_log
                WHERE request_text IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 1000
            """).fetchall()
            db.close()
        except Exception:
            return []

        # Count word-pattern associations
        word_pattern = defaultdict(Counter)  # word -> {pattern: count}
        word_total = Counter()

        for r in rows:
            prompt = (r["prompt"] or "").lower()
            pattern = r["pattern"] or "unknown"
            words = set(re.findall(r'\b[a-zA-Zàéèùêôîû]{3,}\b', prompt)) - STOP_WORDS
            for w in words:
                word_pattern[w][pattern] += 1
                word_total[w] += 1

        # Find words that don't clearly map to any pattern (entropy-like)
        patterns = []
        existing = self._get_existing_types()

        for word, total in word_total.most_common(100):
            if total < 3:
                break
            pattern_dist = word_pattern[word]
            # High entropy = word appears across many patterns = potential new domain
            n_patterns = len(pattern_dist)
            if n_patterns >= 3:
                # This word isn't specific to any pattern — possible new domain
                top_pattern = pattern_dist.most_common(1)[0]
                if top_pattern[1] / total < 0.5 and word not in existing:
                    patterns.append(DiscoveredPattern(
                        pattern_type=f"cross_{word}",
                        keywords=[word],
                        sample_prompts=[],
                        frequency=total,
                        confidence=min(1.0, total / 15) * (n_patterns / 5),
                        suggested_node="M1",
                        suggested_strategy="category",
                        reason=f"Cross-pattern word '{word}' ({total}x across {n_patterns} patterns)",
                    ))

        return [p for p in patterns if p.confidence >= self.MIN_CONFIDENCE]

    def _discover_from_failed_dispatches(self) -> list[DiscoveredPattern]:
        """Find patterns where current routing fails — potential specialized agent needed."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT classified_type as pattern, node, COUNT(*) as total,
                       SUM(success) as ok,
                       AVG(latency_ms) as avg_ms,
                       AVG(quality_score) as avg_q
                FROM agent_dispatch_log
                WHERE success = 0
                GROUP BY classified_type, node
                HAVING total >= 3
                ORDER BY total DESC
            """).fetchall()
            db.close()
        except Exception:
            return []

        patterns = []
        for r in rows:
            pattern = r["pattern"]
            node = r["node"]
            total = r["total"]
            ok = r["ok"] or 0
            fail_rate = 1 - (ok / max(1, total))

            if fail_rate > 0.5 and total >= 5:
                # Suggest re-routing or new specialized agent
                alt_node = "OL1" if node != "OL1" else "M1"
                patterns.append(DiscoveredPattern(
                    pattern_type=f"fix_{pattern}_{node}",
                    keywords=[],
                    sample_prompts=[],
                    frequency=total,
                    confidence=min(1.0, fail_rate),
                    suggested_node=alt_node,
                    suggested_strategy="single",
                    reason=f"Pattern '{pattern}' fails {fail_rate:.0%} on {node} ({total} calls). Suggest reroute to {alt_node}.",
                ))

        return patterns

    def analyze_behavior(self) -> list[BehaviorInsight]:
        """Analyze user behavior patterns from dispatch logs."""
        insights = []

        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row

            # Peak hours
            hours = db.execute("""
                SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*) as n
                FROM agent_dispatch_log
                GROUP BY hour
                ORDER BY n DESC
            """).fetchall()

            if hours:
                peak = hours[0]
                quiet = hours[-1] if len(hours) > 1 else None
                insights.append(BehaviorInsight(
                    insight_type="peak_hours",
                    description=f"Peak usage at {peak['hour']}h ({peak['n']} dispatches)",
                    data={"hours": {h["hour"]: h["n"] for h in hours}},
                    actionable=True,
                    suggestion=f"Pre-warm M1 models at {max(0, peak['hour'] - 1)}h for peak at {peak['hour']}h",
                ))

            # Pattern distribution
            patterns = db.execute("""
                SELECT classified_type as pattern, COUNT(*) as n,
                       ROUND(AVG(success) * 100, 1) as ok_pct,
                       ROUND(AVG(latency_ms), 0) as avg_ms
                FROM agent_dispatch_log
                WHERE classified_type IS NOT NULL
                GROUP BY classified_type
                ORDER BY n DESC
            """).fetchall()

            if patterns:
                total = sum(p["n"] for p in patterns)
                top3 = patterns[:3]
                insights.append(BehaviorInsight(
                    insight_type="pattern_distribution",
                    description=f"Top patterns: {', '.join(f'{p['pattern']}({p['n']})' for p in top3)} / {total} total",
                    data={"patterns": {p["pattern"]: {"count": p["n"], "success": p["ok_pct"], "latency": p["avg_ms"]} for p in patterns}},
                ))

            # Complexity trend (avg prompt length over time)
            complexity = db.execute("""
                SELECT DATE(timestamp) as day, AVG(LENGTH(request_text)) as avg_len, COUNT(*) as n
                FROM agent_dispatch_log
                WHERE request_text IS NOT NULL
                GROUP BY day
                ORDER BY day DESC
                LIMIT 14
            """).fetchall()

            if len(complexity) >= 2:
                recent = complexity[0]["avg_len"] or 0
                older = complexity[-1]["avg_len"] or 0
                trend = "increasing" if recent > older * 1.2 else "decreasing" if recent < older * 0.8 else "stable"
                insights.append(BehaviorInsight(
                    insight_type="complexity_trend",
                    description=f"Prompt complexity {trend}: {older:.0f} -> {recent:.0f} chars",
                    data={"days": {c["day"]: {"avg_len": c["avg_len"], "count": c["n"]} for c in complexity}},
                    actionable=trend == "increasing",
                    suggestion="Consider increasing max_tokens for frequent patterns" if trend == "increasing" else "",
                ))

            # Success rate trend
            success_trend = db.execute("""
                SELECT DATE(timestamp) as day,
                       ROUND(AVG(success) * 100, 1) as ok_pct,
                       COUNT(*) as n
                FROM agent_dispatch_log
                GROUP BY day
                ORDER BY day DESC
                LIMIT 14
            """).fetchall()

            if len(success_trend) >= 2:
                recent_ok = success_trend[0]["ok_pct"] or 0
                older_ok = success_trend[-1]["ok_pct"] or 0
                if recent_ok < older_ok - 10:
                    insights.append(BehaviorInsight(
                        insight_type="success_degradation",
                        description=f"Success rate dropping: {older_ok}% -> {recent_ok}%",
                        data={"days": {s["day"]: s["ok_pct"] for s in success_trend}},
                        actionable=True,
                        suggestion="Check node health, consider disabling failing nodes",
                    ))

            db.close()
        except Exception as e:
            logger.warning(f"Behavior analysis failed: {e}")

        return insights

    def register_patterns(self, patterns: list[DiscoveredPattern]) -> int:
        """Register discovered patterns in the database."""
        if not patterns:
            return 0

        try:
            db = sqlite3.connect(self.db_path)
            count = 0
            for p in patterns:
                if p.confidence < self.MIN_CONFIDENCE:
                    continue
                # Check if already exists
                existing = db.execute(
                    "SELECT 1 FROM agent_patterns WHERE pattern_type = ?",
                    (p.pattern_type,)
                ).fetchone()
                if existing:
                    continue

                db.execute("""
                    INSERT INTO agent_patterns (
                        pattern_id, agent_id, pattern_type, strategy,
                        model_primary, model_fallbacks,
                        avg_latency_ms, success_rate, total_calls
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0)
                """, (
                    f"PAT_DISCOVERED_{p.pattern_type.upper()}",
                    f"discovered-{p.pattern_type}",
                    p.pattern_type,
                    p.suggested_strategy,
                    p.suggested_node,
                    "OL1,M1",
                ))
                count += 1
                logger.info(f"Registered new pattern: {p.pattern_type} (confidence={p.confidence:.2f})")

            db.commit()
            db.close()
            return count
        except Exception as e:
            logger.warning(f"Failed to register patterns: {e}")
            return 0

    def _get_existing_types(self) -> set[str]:
        """Get all existing pattern types from DB + code."""
        types = set()
        try:
            db = sqlite3.connect(self.db_path)
            rows = db.execute("SELECT DISTINCT pattern_type FROM agent_patterns").fetchall()
            types.update(r[0] for r in rows if r[0])
            db.close()
        except Exception:
            pass

        # Also include hardcoded types
        try:
            from src.pattern_agents import AGENT_CONFIGS
            types.update(a.pattern_type for a in AGENT_CONFIGS)
        except Exception:
            pass

        return types

    def full_report(self) -> dict:
        """Complete discovery + behavior report."""
        discovered = self.discover()
        behavior = self.analyze_behavior()

        return {
            "discovered_patterns": [
                {
                    "type": p.pattern_type,
                    "keywords": p.keywords,
                    "frequency": p.frequency,
                    "confidence": round(p.confidence, 2),
                    "node": p.suggested_node,
                    "strategy": p.suggested_strategy,
                    "reason": p.reason,
                }
                for p in discovered
            ],
            "behavior_insights": [
                {
                    "type": i.insight_type,
                    "description": i.description,
                    "actionable": i.actionable,
                    "suggestion": i.suggestion,
                }
                for i in behavior
            ],
            "total_discovered": len(discovered),
            "actionable_insights": sum(1 for i in behavior if i.actionable),
        }
