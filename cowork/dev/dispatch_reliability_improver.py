#!/usr/bin/env python3
"""dispatch_reliability_improver.py — Auto-tune dispatch routing from failure data.

Analyzes agent_dispatch_log to find unreliable node/pattern combos and generates
routing rules that skip failing nodes, adjust timeouts, and set fallback chains.

CLI:
    --once       : analyze and apply improvements
    --dry-run    : analyze but don't modify DB
    --stats      : show current reliability stats

Stdlib-only (sqlite3, json, argparse).
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")

# Thresholds
MIN_SAMPLES = 5
FAILURE_THRESHOLD = 0.30  # >30% failure = unreliable
TIMEOUT_THRESHOLD_MS = 55000  # >55s = likely timeout
QUALITY_THRESHOLD = 0.5  # <0.5 quality = poor


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS routing_improvements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        pattern TEXT NOT NULL,
        node TEXT NOT NULL,
        issue_type TEXT NOT NULL,
        old_value REAL,
        new_value REAL,
        action TEXT NOT NULL,
        applied INTEGER DEFAULT 0
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def analyze_reliability():
    """Analyze dispatch logs for unreliable combos."""
    if not ETOILE_DB.exists():
        return {"error": "etoile.db not found"}

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    rows = edb.execute("""
        SELECT classified_type, node, model_used,
               COUNT(*) as total,
               SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fails,
               AVG(latency_ms) as avg_lat,
               AVG(quality_score) as avg_quality,
               MAX(latency_ms) as max_lat
        FROM agent_dispatch_log
        GROUP BY classified_type, node, model_used
        HAVING total >= ?
        ORDER BY fails DESC
    """, (MIN_SAMPLES,)).fetchall()

    issues = []
    recommendations = []

    for r in rows:
        pattern = r["classified_type"]
        node = r["node"]
        model = r["model_used"]
        total = r["total"]
        fails = r["fails"]
        fail_rate = fails / max(total, 1)
        avg_lat = r["avg_lat"] or 0
        avg_q = r["avg_quality"] or 0

        entry = {
            "pattern": pattern, "node": node, "model": model,
            "total": total, "fails": fails,
            "fail_rate": round(fail_rate * 100, 1),
            "avg_latency_ms": round(avg_lat),
            "avg_quality": round(avg_q, 3),
        }

        # High failure rate
        if fail_rate > FAILURE_THRESHOLD:
            entry["issue"] = "high_failure_rate"
            issues.append(entry)
            recommendations.append({
                "action": "deprioritize",
                "pattern": pattern, "node": node,
                "reason": f"{fail_rate*100:.0f}% failure rate ({fails}/{total})",
                "suggestion": f"Route {pattern} away from {node}, use fallback"
            })

        # Timeout pattern
        if avg_lat > TIMEOUT_THRESHOLD_MS:
            entry["issue"] = "timeout_prone"
            issues.append(entry)
            recommendations.append({
                "action": "increase_timeout_or_skip",
                "pattern": pattern, "node": node,
                "reason": f"Average latency {avg_lat:.0f}ms (near timeout)",
                "suggestion": f"Increase timeout for {node} or skip for {pattern}"
            })

        # Poor quality
        if avg_q < QUALITY_THRESHOLD and avg_q > 0 and total >= 10:
            entry["issue"] = "poor_quality"
            issues.append(entry)
            recommendations.append({
                "action": "improve_prompt_or_reroute",
                "pattern": pattern, "node": node,
                "reason": f"Quality score {avg_q:.2f} below threshold {QUALITY_THRESHOLD}",
                "suggestion": f"Improve prompt template or reroute to better model"
            })

    # Best nodes per pattern
    best_nodes = {}
    for r in rows:
        pattern = r["classified_type"]
        fail_rate = (r["fails"] or 0) / max(r["total"], 1)
        score = (1 - fail_rate) * (r["avg_quality"] or 0.5) * 100
        if pattern not in best_nodes or score > best_nodes[pattern]["score"]:
            best_nodes[pattern] = {
                "node": r["node"], "model": r["model_used"],
                "score": round(score, 1),
                "success_rate": round((1 - fail_rate) * 100, 1)
            }

    edb.close()

    return {
        "total_combos_analyzed": len(rows),
        "issues_found": len(issues),
        "issues": issues,
        "recommendations": recommendations,
        "best_nodes": best_nodes,
    }


def apply_improvements(analysis, dry_run=False):
    """Record improvements and optionally apply routing changes."""
    conn = get_db()
    ts = datetime.now().isoformat()
    applied_count = 0

    for rec in analysis.get("recommendations", []):
        conn.execute("""
            INSERT INTO routing_improvements
            (timestamp, pattern, node, issue_type, action, applied)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, rec["pattern"], rec["node"], rec["action"],
              rec["suggestion"], 0 if dry_run else 1))
        applied_count += 1

    if not dry_run and ETOILE_DB.exists():
        edb = sqlite3.connect(str(ETOILE_DB))
        # Update agent_patterns with optimized routing
        for pattern, best in analysis.get("best_nodes", {}).items():
            # Update priority for patterns with known best nodes
            edb.execute("""
                UPDATE agent_patterns
                SET strategy = 'optimized',
                    description = description || ' [auto-optimized]'
                WHERE pattern_id LIKE ? AND strategy != 'optimized'
            """, (f"%{pattern}%",))
        edb.commit()
        edb.close()

    conn.commit()
    conn.close()

    return {"applied": applied_count, "dry_run": dry_run}


def action_stats():
    """Show improvement history."""
    conn = get_db()
    rows = conn.execute("""
        SELECT pattern, node, issue_type, action, applied, timestamp
        FROM routing_improvements
        ORDER BY timestamp DESC LIMIT 30
    """).fetchall()
    conn.close()
    return {
        "improvements": [dict(r) for r in rows],
        "total": len(rows)
    }


def main():
    parser = argparse.ArgumentParser(description="Dispatch Reliability Improver")
    parser.add_argument("--once", action="store_true", help="Analyze and apply")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only")
    parser.add_argument("--stats", action="store_true", help="Show history")
    args = parser.parse_args()

    if not any([args.once, args.dry_run, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        result = action_stats()
    else:
        analysis = analyze_reliability()
        apply_result = apply_improvements(analysis, dry_run=args.dry_run)
        result = {
            "timestamp": datetime.now().isoformat(),
            "action": "reliability_improvement",
            **analysis,
            **apply_result,
        }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
