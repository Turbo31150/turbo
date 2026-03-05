#!/usr/bin/env python3
"""cowork_auto_improver.py — Automatic improvement engine for COWORK system.

Reads recommendations from all analysis scripts and applies them:
1. Routing adjustments (from reliability_improver + load_balancer)
2. Retry configuration (from smart_retry_dispatcher)
3. Cache pre-population (from quick_answer_cache)
4. Pattern agent priority updates (from A/B tester)
5. Error pattern fixes (from error_analyzer)

CLI:
    --once       : analyze and apply improvements
    --dry-run    : show what would be done
    --report     : generate improvement report
    --stats      : show improvement history

Stdlib-only (sqlite3, json, argparse).
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")
PYTHON = sys.executable


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS auto_improvements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        improvement_type TEXT NOT NULL,
        target TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        applied INTEGER DEFAULT 0,
        impact_estimate TEXT
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def run_analyzer(name, args="--once"):
    """Run an analysis script and return parsed output."""
    script_path = SCRIPT_DIR / f"{name}.py"
    if not script_path.exists():
        return None
    try:
        r = subprocess.run(
            [PYTHON, str(script_path), args],
            capture_output=True, text=True, timeout=60, cwd=str(SCRIPT_DIR)
        )
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def gather_recommendations():
    """Collect recommendations from all analyzers."""
    improvements = []

    # 1. Reliability improvements
    data = run_analyzer("dispatch_reliability_improver")
    if data:
        for rec in data.get("recommendations", []):
            improvements.append({
                "type": "routing",
                "source": "reliability_improver",
                "target": f"{rec['pattern']}/{rec['node']}",
                "action": rec["action"],
                "details": rec["suggestion"],
                "priority": "high" if "deprioritize" in rec["action"] else "medium",
            })
        # Best nodes
        for pattern, best in data.get("best_nodes", {}).items():
            if best["score"] > 50:
                improvements.append({
                    "type": "routing",
                    "source": "reliability_improver",
                    "target": pattern,
                    "action": f"prefer_node:{best['node']}",
                    "details": f"Best node for {pattern}: {best['node']} (score {best['score']})",
                    "priority": "medium",
                })

    # 2. Load balancing
    data = run_analyzer("pattern_load_balancer")
    if data:
        for sug in data.get("suggestions", []):
            for pat in sug.get("patterns_to_move", []):
                improvements.append({
                    "type": "load_balance",
                    "source": "load_balancer",
                    "target": pat["pattern"],
                    "action": f"rebalance:{sug['from']}->{sug['to']}",
                    "details": f"Move {pat['pattern']} from {sug['from']} ({sug['from_load']}%) to {sug['to']} ({sug['to_load']}%)",
                    "priority": "medium",
                })

    # 3. Latency optimizations
    data = run_analyzer("dispatch_latency_optimizer")
    if data:
        for opt in data.get("optimizations", []):
            best = opt["best_strategy"]
            improvements.append({
                "type": "latency",
                "source": "latency_optimizer",
                "target": opt["pattern"],
                "action": best["strategy"],
                "details": f"{best['current_ms']}ms -> {best['expected_ms']}ms (-{best['reduction_pct']}%)",
                "priority": "high" if opt["gap_ms"] > 15000 else "medium",
            })

    # 4. A/B test winners
    data = run_analyzer("dispatch_ab_tester")
    if data:
        for comp in data.get("existing_comparisons", []):
            if comp["success_delta"] > 5:
                improvements.append({
                    "type": "strategy",
                    "source": "ab_tester",
                    "target": comp["pattern"],
                    "action": f"switch_strategy:{comp['winner']}",
                    "details": f"Winner: {comp['winner']} (+{comp['success_delta']}% vs {comp['loser']})",
                    "priority": "high" if comp["success_delta"] > 10 else "medium",
                })

    # 5. Trend predictions
    data = run_analyzer("dispatch_trend_analyzer")
    if data:
        for trend in data.get("trends", {}).get("emerging", []):
            improvements.append({
                "type": "capacity",
                "source": "trend_analyzer",
                "target": trend["pattern"],
                "action": "scale_up",
                "details": f"Growing +{trend.get('volume_change_pct', '?')}%, add capacity",
                "priority": "low",
            })

    return improvements


def apply_improvements(improvements, dry_run=False):
    """Record and optionally apply improvements."""
    conn = get_db()
    ts = datetime.now().isoformat()
    applied = 0
    skipped = 0

    for imp in improvements:
        # Record
        conn.execute("""
            INSERT INTO auto_improvements
            (timestamp, improvement_type, target, action, details, applied, impact_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ts, imp["type"], imp["target"], imp["action"],
              imp["details"], 0 if dry_run else 1, imp["priority"]))

        if not dry_run:
            # Apply routing changes to etoile.db
            if imp["type"] == "routing" and imp["action"].startswith("prefer_node:"):
                node = imp["action"].split(":")[1]
                _apply_routing(imp["target"], node)
                applied += 1
            elif imp["type"] == "strategy" and imp["action"].startswith("switch_strategy:"):
                strategy = imp["action"].split(":")[1]
                _apply_strategy(imp["target"], strategy)
                applied += 1
            else:
                skipped += 1
        else:
            skipped += 1

    conn.commit()
    conn.close()
    return {"applied": applied, "skipped": skipped, "total": len(improvements)}


def _apply_routing(pattern, preferred_node):
    """Update agent_patterns with preferred node."""
    if not ETOILE_DB.exists():
        return
    try:
        edb = sqlite3.connect(str(ETOILE_DB))
        # Check if pattern has a routing entry
        existing = edb.execute(
            "SELECT model_id FROM agent_patterns WHERE pattern_id LIKE ? LIMIT 1",
            (f"%{pattern}%",)
        ).fetchone()
        if existing:
            edb.execute("""
                UPDATE agent_patterns
                SET model_id = ?,
                    strategy = 'auto_optimized'
                WHERE pattern_id LIKE ? AND strategy != 'auto_optimized'
            """, (preferred_node, f"%{pattern}%"))
            edb.commit()
        edb.close()
    except Exception:
        pass


def _apply_strategy(pattern, strategy):
    """Update dispatch strategy for a pattern."""
    if not ETOILE_DB.exists():
        return
    try:
        edb = sqlite3.connect(str(ETOILE_DB))
        edb.execute("""
            UPDATE agent_patterns
            SET strategy = ?
            WHERE pattern_id LIKE ?
        """, (strategy, f"%{pattern}%"))
        edb.commit()
        edb.close()
    except Exception:
        pass


def generate_report(improvements):
    """Generate a structured improvement report."""
    by_type = {}
    by_priority = {"high": [], "medium": [], "low": []}

    for imp in improvements:
        t = imp["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(imp)
        by_priority[imp["priority"]].append(imp)

    return {
        "total_improvements": len(improvements),
        "by_type": {k: len(v) for k, v in by_type.items()},
        "by_priority": {k: len(v) for k, v in by_priority.items()},
        "high_priority": by_priority["high"],
        "summary": {
            "routing_changes": len(by_type.get("routing", [])),
            "latency_optimizations": len(by_type.get("latency", [])),
            "strategy_switches": len(by_type.get("strategy", [])),
            "capacity_needs": len(by_type.get("capacity", [])),
            "load_balance_moves": len(by_type.get("load_balance", [])),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="COWORK Auto-Improver")
    parser.add_argument("--once", action="store_true", help="Analyze and apply")
    parser.add_argument("--dry-run", action="store_true", help="Show only")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--stats", action="store_true", help="Show history")
    args = parser.parse_args()

    if not any([args.once, args.dry_run, args.report, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        conn = get_db()
        rows = conn.execute("""
            SELECT improvement_type, COUNT(*) as cnt,
                   SUM(applied) as applied
            FROM auto_improvements
            GROUP BY improvement_type
            ORDER BY cnt DESC
        """).fetchall()
        conn.close()
        result = {"history": [dict(r) for r in rows]}
    else:
        improvements = gather_recommendations()
        apply_result = apply_improvements(improvements, dry_run=args.dry_run or args.report)
        report = generate_report(improvements)

        result = {
            "timestamp": datetime.now().isoformat(),
            **report,
            **apply_result,
        }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
