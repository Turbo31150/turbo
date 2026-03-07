"""JARVIS Agent Factory — Auto-create and evolve agents from benchmark data.

Analyzes dispatch_log to:
  1. Discover new pattern types not yet in agent_patterns
  2. Tune existing agents (node, strategy, priority)
  3. Generate new PatternAgent configs automatically
  4. Score and rank agents by performance

Usage:
    from src.agent_factory import AgentFactory
    factory = AgentFactory()
    factory.analyze_and_evolve()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


__all__ = [
    "AgentEvolution",
    "AgentFactory",
    "main",
]

logger = logging.getLogger("jarvis.agent_factory")

DB_PATH = "F:/BUREAU/turbo/etoile.db"
PROJECT_ROOT = Path("F:/BUREAU/turbo")


@dataclass
class AgentEvolution:
    pattern_type: str
    action: str  # "create", "tune_node", "tune_strategy", "tune_priority"
    old_value: str
    new_value: str
    reason: str
    confidence: float  # 0-1


class AgentFactory:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def analyze_and_evolve(self) -> list[AgentEvolution]:
        """Main entry: analyze dispatch logs and propose/apply evolutions."""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row

        evolutions = []

        # 1. Check for new patterns not in agent_patterns
        evolutions.extend(self._discover_new_patterns(db))

        # 2. Tune node assignments based on performance
        evolutions.extend(self._tune_nodes(db))

        # 3. Tune strategies based on comparative results
        evolutions.extend(self._tune_strategies(db))

        # 4. Update success rates and latencies
        self._update_stats(db)

        db.close()
        return evolutions

    def _discover_new_patterns(self, db) -> list[AgentEvolution]:
        """Find classified_types in dispatch_log not yet in agent_patterns."""
        cur = db.cursor()
        known = {r["pattern_type"] for r in cur.execute("SELECT pattern_type FROM agent_patterns").fetchall()}

        # Get distinct classified_types from dispatch log
        log_types = cur.execute("""
            SELECT classified_type, COUNT(*) as cnt, AVG(latency_ms) as avg_ms, AVG(success) as rate
            FROM agent_dispatch_log
            WHERE classified_type IS NOT NULL
            GROUP BY classified_type
            HAVING cnt >= 5
        """).fetchall()

        evolutions = []
        for r in log_types:
            ptype = r["classified_type"]
            if ptype not in known:
                # Auto-create agent pattern
                agent_id = ptype.replace("_", "-")
                pattern_id = f"PAT_{ptype.upper().replace('-','_')}"

                # Determine best node from logs
                best_node = cur.execute("""
                    SELECT node, AVG(latency_ms) as avg_ms, AVG(success) as rate
                    FROM agent_dispatch_log
                    WHERE classified_type=? AND success=1
                    GROUP BY node ORDER BY rate DESC, avg_ms ASC LIMIT 1
                """, (ptype,)).fetchone()

                model = "qwen3-8b"  # default
                node = best_node["node"] if best_node else "M1"

                cur.execute("""INSERT INTO agent_patterns
                    (pattern_id, agent_id, pattern_type, keywords, description,
                     model_primary, model_fallbacks, strategy, priority,
                     avg_latency_ms, success_rate, total_calls, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (pattern_id, agent_id, ptype,
                     ptype,  # basic keyword
                     f"Auto-generated agent for {ptype} tasks",
                     model, f"M1:qwen3-8b,M2:deepseek-r1",
                     "category", 3,
                     r["avg_ms"] or 0, r["rate"] or 0, r["cnt"],
                     datetime.now().isoformat(), datetime.now().isoformat())
                )
                db.commit()

                evolutions.append(AgentEvolution(
                    pattern_type=ptype,
                    action="create",
                    old_value="none",
                    new_value=f"{pattern_id} (node={node}, model={model})",
                    reason=f"Found {r['cnt']} dispatches with no agent",
                    confidence=0.7
                ))
                logger.info(f"Created new agent: {pattern_id} for {ptype}")

        return evolutions

    def _tune_nodes(self, db) -> list[AgentEvolution]:
        """Check if a different node performs better for existing patterns."""
        cur = db.cursor()
        patterns = cur.execute("SELECT pattern_id, pattern_type, model_primary FROM agent_patterns").fetchall()

        evolutions = []
        for pat in patterns:
            # Get performance by node for this pattern
            stats = cur.execute("""
                SELECT node, COUNT(*) as cnt, AVG(latency_ms) as avg_ms,
                       AVG(success) as rate, AVG(quality_score) as avg_q
                FROM agent_dispatch_log
                WHERE classified_type=? AND node IS NOT NULL
                GROUP BY node HAVING cnt >= 3
                ORDER BY rate DESC, avg_ms ASC
            """, (pat["pattern_type"],)).fetchall()

            if len(stats) < 2:
                continue

            current_model = pat["model_primary"]
            best = stats[0]
            # Check if best node is significantly better
            current_stats = [s for s in stats if current_model and current_model in (s["node"] or "")]
            if current_stats:
                cs = current_stats[0]
                if best["rate"] > cs["rate"] + 0.1 or (best["rate"] >= cs["rate"] and best["avg_ms"] < cs["avg_ms"] * 0.7):
                    evolutions.append(AgentEvolution(
                        pattern_type=pat["pattern_type"],
                        action="tune_node",
                        old_value=current_model,
                        new_value=best["node"],
                        reason=f"Node {best['node']} has {best['rate']:.0%} rate / {best['avg_ms']:.0f}ms vs current {cs['rate']:.0%} / {cs['avg_ms']:.0f}ms",
                        confidence=min(1.0, best["cnt"] / 10)
                    ))

        return evolutions

    def _tune_strategies(self, db) -> list[AgentEvolution]:
        """Check if a different strategy works better for each pattern."""
        cur = db.cursor()
        patterns = cur.execute("SELECT pattern_id, pattern_type, strategy FROM agent_patterns").fetchall()

        evolutions = []
        for pat in patterns:
            stats = cur.execute("""
                SELECT strategy, COUNT(*) as cnt, AVG(latency_ms) as avg_ms,
                       AVG(success) as rate, AVG(quality_score) as avg_q
                FROM agent_dispatch_log
                WHERE classified_type=? AND strategy IS NOT NULL
                GROUP BY strategy HAVING cnt >= 3
                ORDER BY rate DESC, avg_q DESC
            """, (pat["pattern_type"],)).fetchall()

            if len(stats) < 2:
                continue

            current_strat = pat["strategy"]
            best = stats[0]
            # Only suggest change if significantly better
            current_s = [s for s in stats if s["strategy"] == current_strat]
            if current_s:
                cs = current_s[0]
                if best["rate"] > cs["rate"] + 0.15 or (best["rate"] >= cs["rate"] and best["avg_q"] and cs["avg_q"] and best["avg_q"] > cs["avg_q"] + 0.1):
                    evolutions.append(AgentEvolution(
                        pattern_type=pat["pattern_type"],
                        action="tune_strategy",
                        old_value=current_strat,
                        new_value=best["strategy"],
                        reason=f"Strategy {best['strategy']} has {best['rate']:.0%} rate / Q={best['avg_q']:.2f} vs {current_strat} {cs['rate']:.0%} / Q={cs['avg_q']:.2f}",
                        confidence=min(1.0, best["cnt"] / 15)
                    ))

        return evolutions

    def _update_stats(self, db):
        """Update agent_patterns with latest stats from dispatch_log."""
        cur = db.cursor()
        stats = cur.execute("""
            SELECT classified_type,
                   COUNT(*) as total,
                   AVG(latency_ms) as avg_ms,
                   AVG(success) as rate,
                   AVG(quality_score) as avg_q
            FROM agent_dispatch_log
            WHERE classified_type IS NOT NULL
            GROUP BY classified_type
        """).fetchall()

        for s in stats:
            cur.execute("""UPDATE agent_patterns
                SET avg_latency_ms=?, success_rate=?, total_calls=?, updated_at=?
                WHERE pattern_type=?""",
                (s["avg_ms"], s["rate"], s["total"],
                 datetime.now().isoformat(), s["classified_type"])
            )
        db.commit()

    def generate_report(self) -> dict:
        """Generate a comprehensive agent performance report."""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cur = db.cursor()

        # Agent patterns
        patterns = cur.execute("SELECT * FROM agent_patterns ORDER BY priority").fetchall()

        # Dispatch stats
        total_dispatches = cur.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
        recent = cur.execute("""
            SELECT classified_type, strategy, node,
                   COUNT(*) as cnt, AVG(latency_ms) as avg_ms,
                   AVG(success) as rate, AVG(quality_score) as avg_q
            FROM agent_dispatch_log
            GROUP BY classified_type, strategy, node
            ORDER BY cnt DESC
        """).fetchall()

        # Best combos
        best_combos = cur.execute("""
            SELECT classified_type, node, strategy,
                   COUNT(*) as cnt, AVG(latency_ms) as avg_ms,
                   AVG(success) as rate, AVG(quality_score) as avg_q
            FROM agent_dispatch_log
            WHERE success=1
            GROUP BY classified_type, node, strategy
            HAVING cnt >= 3
            ORDER BY rate DESC, avg_q DESC, avg_ms ASC
            LIMIT 30
        """).fetchall()

        db.close()

        return {
            "timestamp": datetime.now().isoformat(),
            "total_patterns": len(patterns),
            "total_dispatches": total_dispatches,
            "patterns": [dict(p) for p in patterns],
            "best_combos": [dict(b) for b in best_combos],
            "dispatch_breakdown": [dict(r) for r in recent],
        }


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    import sys

    factory = AgentFactory()

    if "--report" in sys.argv:
        report = factory.generate_report()
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    elif "--evolve" in sys.argv:
        evolutions = factory.analyze_and_evolve()
        if evolutions:
            print(f"\n=== {len(evolutions)} EVOLUTIONS ===")
            for e in evolutions:
                print(f"  [{e.action}] {e.pattern_type}: {e.old_value} -> {e.new_value}")
                print(f"    Reason: {e.reason} (confidence: {e.confidence:.0%})")
        else:
            print("No evolutions needed.")
    else:
        # Quick status
        report = factory.generate_report()
        print(f"Patterns: {report['total_patterns']} | Dispatches: {report['total_dispatches']}")
        print(f"\nTop combos (pattern -> node -> strategy):")
        for b in report["best_combos"][:15]:
            print(f"  {b['classified_type']:<14} {b['node']:<12} {b['strategy']:<14} "
                  f"{b['cnt']:>3} calls  {b['rate']:.0%} rate  {b['avg_ms']:.0f}ms  Q={b['avg_q']:.2f}")


if __name__ == "__main__":
    main()
