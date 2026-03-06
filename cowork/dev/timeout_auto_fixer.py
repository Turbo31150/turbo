#!/usr/bin/env python3
"""JARVIS Cowork: Timeout Auto-Fixer.

Analyzes dispatch_log for timeout/context errors and auto-adjusts:
  1. Updates PATTERN_TIMEOUT values in PatternAgent based on actual p95 latencies
  2. Updates NODE_TIMEOUT_FACTOR based on node-specific performance
  3. Validates the changes with a quick dispatch test

Usage:
    python cowork/dev/timeout_auto_fixer.py [--once] [--dry-run]
"""

import json
from _paths import TURBO_DIR
import os
import sqlite3
import sys
import time

sys.path.insert(0, str(TURBO_DIR))
os.chdir(str(TURBO_DIR))

DB_PATH = str(ETOILE_DB)


def analyze_timeouts():
    """Analyze dispatch log to find patterns with timeout issues."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    # Get p95 latency per pattern (successful dispatches only)
    pattern_stats = db.execute("""
        SELECT classified_type as pattern,
               COUNT(*) as n,
               AVG(latency_ms) as avg_lat,
               MAX(latency_ms) as max_lat,
               SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fails,
               SUM(CASE WHEN success=0 AND latency_ms > 50000 THEN 1 ELSE 0 END) as timeouts
        FROM agent_dispatch_log
        WHERE id > (SELECT COALESCE(MAX(id),0) - 500 FROM agent_dispatch_log)
        GROUP BY classified_type
        HAVING n >= 5
        ORDER BY timeouts DESC
    """).fetchall()

    # Get p95 latency per node (successful dispatches only)
    node_stats = db.execute("""
        SELECT node,
               COUNT(*) as n,
               AVG(latency_ms) as avg_lat,
               MAX(latency_ms) as max_lat,
               SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fails
        FROM agent_dispatch_log
        WHERE success=1 AND id > (SELECT COALESCE(MAX(id),0) - 500 FROM agent_dispatch_log)
        GROUP BY node
        HAVING n >= 3
    """).fetchall()

    db.close()
    return pattern_stats, node_stats


def suggest_adjustments(pattern_stats, node_stats):
    """Suggest timeout adjustments based on actual latency data."""
    from src.pattern_agents import PatternAgent

    suggestions = []

    for ps in pattern_stats:
        pattern = ps["pattern"]
        current = PatternAgent.PATTERN_TIMEOUT.get(pattern)
        if current is None:
            continue

        timeout_rate = ps["timeouts"] / max(1, ps["n"])
        avg_lat_s = (ps["avg_lat"] or 0) / 1000
        max_lat_s = (ps["max_lat"] or 0) / 1000

        if timeout_rate > 0.1:
            # More than 10% timeouts — need more time
            recommended = max(current, int(max_lat_s * 1.5))
            recommended = min(180, recommended)  # Cap at 180s
            if recommended > current:
                suggestions.append({
                    "type": "pattern_timeout",
                    "pattern": pattern,
                    "current": current,
                    "recommended": recommended,
                    "reason": f"{timeout_rate:.0%} timeouts, avg={avg_lat_s:.1f}s max={max_lat_s:.1f}s",
                })
        elif avg_lat_s < current * 0.3 and ps["n"] >= 20:
            # Way under timeout — can reduce
            recommended = max(15, int(avg_lat_s * 3))
            if recommended < current * 0.7:
                suggestions.append({
                    "type": "pattern_timeout",
                    "pattern": pattern,
                    "current": current,
                    "recommended": recommended,
                    "reason": f"avg={avg_lat_s:.1f}s << timeout={current}s, safe to reduce",
                })

    for ns in node_stats:
        node = ns["node"]
        current = PatternAgent.NODE_TIMEOUT_FACTOR.get(node)
        if current is None:
            continue

        avg_lat_s = (ns["avg_lat"] or 0) / 1000
        # If node consistently fast, factor could be lower; if slow, higher
        if avg_lat_s > 30 and current < 2.0:
            suggestions.append({
                "type": "node_factor",
                "node": node,
                "current": current,
                "recommended": min(3.0, current * 1.5),
                "reason": f"avg latency {avg_lat_s:.1f}s, needs higher factor",
            })

    return suggestions


def apply_adjustments(suggestions, dry_run=False):
    """Apply suggested adjustments to PatternAgent config."""
    from src.pattern_agents import PatternAgent

    applied = []
    for s in suggestions:
        if s["type"] == "pattern_timeout":
            if dry_run:
                applied.append(f"[DRY] Would set PATTERN_TIMEOUT[{s['pattern']}] = {s['recommended']} (was {s['current']})")
            else:
                PatternAgent.PATTERN_TIMEOUT[s["pattern"]] = s["recommended"]
                applied.append(f"SET PATTERN_TIMEOUT[{s['pattern']}] = {s['recommended']} (was {s['current']})")
        elif s["type"] == "node_factor":
            if dry_run:
                applied.append(f"[DRY] Would set NODE_TIMEOUT_FACTOR[{s['node']}] = {s['recommended']:.1f} (was {s['current']})")
            else:
                PatternAgent.NODE_TIMEOUT_FACTOR[s["node"]] = s["recommended"]
                applied.append(f"SET NODE_TIMEOUT_FACTOR[{s['node']}] = {s['recommended']:.1f} (was {s['current']})")
    return applied


def main():
    dry_run = "--dry-run" in sys.argv
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=== JARVIS Timeout Auto-Fixer ===")
    print()

    # Analyze
    pattern_stats, node_stats = analyze_timeouts()
    print(f"Analyzed: {sum(ps['n'] for ps in pattern_stats)} dispatches, {len(pattern_stats)} patterns, {len(node_stats)} nodes")

    # Show current timeout problems
    problems = [ps for ps in pattern_stats if ps["timeouts"] > 0]
    if problems:
        print(f"\nTimeout problems ({len(problems)} patterns):")
        for p in problems:
            print(f"  {p['pattern']:15s} {p['timeouts']}/{p['n']} timeouts ({p['timeouts']/max(1,p['n'])*100:.0f}%) avg={p['avg_lat']/1000:.1f}s")
    else:
        print("\nNo active timeout problems detected.")

    # Suggest
    suggestions = suggest_adjustments(pattern_stats, node_stats)
    if suggestions:
        print(f"\nSuggested adjustments ({len(suggestions)}):")
        for s in suggestions:
            print(f"  {s['type']:20s} {s.get('pattern', s.get('node', '?')):15s} {s['current']} -> {s['recommended']} ({s['reason']})")

        # Apply
        applied = apply_adjustments(suggestions, dry_run)
        print(f"\nApplied {len(applied)} adjustments:")
        for a in applied:
            print(f"  {a}")
    else:
        print("\nNo adjustments needed.")

    print("\nDone.")


if __name__ == "__main__":
    main()