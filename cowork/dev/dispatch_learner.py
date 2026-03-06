#!/usr/bin/env python3
"""dispatch_learner.py — Learn from dispatch history to optimize routing.

Analyzes agent_dispatch_log in etoile.db to:
- Identify best node per task type (based on success + quality + speed)
- Detect degrading patterns (quality dropping over time)
- Generate optimized routing table
- Update timeout configs based on real P95 latencies
- Produce actionable insights

CLI:
    --once         : Single analysis + recommendations
    --learn        : Full learning cycle (analyze + apply)
    --routing      : Show optimized routing table
    --trends       : Show quality trends over time

Stdlib-only (json, argparse, urllib, sqlite3, time).
"""

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"

# Minimum dispatches needed to draw conclusions
MIN_SAMPLES = 1


def get_etoile():
    db = sqlite3.connect(str(ETOILE_DB), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = sqlite3.Row
    return db


def get_gaps():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(GAPS_DB), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = sqlite3.Row
    return db


def analyze_routing(edb):
    """Find best node per task type based on composite score."""
    rows = edb.execute("""
        SELECT classified_type, node,
               COUNT(*) as total,
               SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
               ROUND(AVG(CASE WHEN success=1 THEN latency_ms END)) as avg_lat,
               ROUND(AVG(quality_score), 3) as avg_q,
               MAX(latency_ms) as max_lat
        FROM agent_dispatch_log
        GROUP BY classified_type, node
        HAVING COUNT(*) >= ?
        ORDER BY classified_type, avg_q DESC
    """, (MIN_SAMPLES,)).fetchall()

    routing = {}
    for r in rows:
        t = r["classified_type"]
        if t not in routing:
            routing[t] = []

        success_rate = r["ok"] / r["total"] if r["total"] else 0
        speed_score = max(0, 1 - (r["avg_lat"] or 30000) / 60000)
        quality = r["avg_q"] or 0

        # Composite: 40% quality + 30% success + 20% speed + 10% volume
        composite = quality * 0.4 + success_rate * 0.3 + speed_score * 0.2 + min(r["total"] / 20, 1) * 0.1

        routing[t].append({
            "node": r["node"],
            "total": r["total"],
            "success_rate": round(success_rate * 100, 1),
            "avg_latency_ms": r["avg_lat"],
            "avg_quality": quality,
            "composite_score": round(composite, 3),
        })

    # Sort each type by composite score
    for t in routing:
        routing[t].sort(key=lambda x: -x["composite_score"])

    return routing


def analyze_trends(edb):
    """Detect quality trends (comparing recent vs older dispatches)."""
    trends = []

    types_nodes = edb.execute("""
        SELECT DISTINCT classified_type, node FROM agent_dispatch_log
    """).fetchall()

    for tn in types_nodes:
        t, n = tn["classified_type"], tn["node"]

        # Recent 10 vs previous 10
        recent = edb.execute("""
            SELECT AVG(quality_score) as q, AVG(latency_ms) as l,
                   AVG(CASE WHEN success=1 THEN 1.0 ELSE 0 END) as s
            FROM (SELECT * FROM agent_dispatch_log
                  WHERE classified_type=? AND node=?
                  ORDER BY id DESC LIMIT 10)
        """, (t, n)).fetchone()

        older = edb.execute("""
            SELECT AVG(quality_score) as q, AVG(latency_ms) as l,
                   AVG(CASE WHEN success=1 THEN 1.0 ELSE 0 END) as s
            FROM (SELECT * FROM agent_dispatch_log
                  WHERE classified_type=? AND node=?
                  ORDER BY id DESC LIMIT 10 OFFSET 10)
        """, (t, n)).fetchone()

        if not recent["q"] or not older["q"]:
            continue

        q_change = (recent["q"] - older["q"]) / max(older["q"], 0.01) * 100
        l_change = (recent["l"] - older["l"]) / max(older["l"], 1) * 100
        s_change = (recent["s"] - older["s"]) * 100

        if abs(q_change) > 10 or abs(s_change) > 15 or abs(l_change) > 30:
            trends.append({
                "type": t, "node": n,
                "quality_change_pct": round(q_change, 1),
                "latency_change_pct": round(l_change, 1),
                "success_change_pct": round(s_change, 1),
                "direction": "improving" if q_change > 0 else "degrading",
            })

    return trends


def compute_optimal_timeouts(edb):
    """Compute P95 timeouts per pattern/node."""
    timeouts = []
    combos = edb.execute("""
        SELECT classified_type, node FROM agent_dispatch_log
        WHERE success=1
        GROUP BY classified_type, node
        HAVING COUNT(*) >= ?
    """, (MIN_SAMPLES,)).fetchall()

    for c in combos:
        # Get sorted latencies
        lats = edb.execute("""
            SELECT latency_ms FROM agent_dispatch_log
            WHERE classified_type=? AND node=? AND success=1
            ORDER BY latency_ms
        """, (c["classified_type"], c["node"])).fetchall()

        if not lats:
            continue

        values = [r["latency_ms"] for r in lats]
        p50 = values[len(values) // 2]
        p95_idx = min(int(len(values) * 0.95), len(values) - 1)
        p95 = values[p95_idx]

        # Timeout = P95 * 1.5 + 5s buffer, minimum 15s
        optimal = max(15000, int(p95 * 1.5 + 5000))

        timeouts.append({
            "type": c["classified_type"], "node": c["node"],
            "p50_ms": p50, "p95_ms": p95,
            "optimal_timeout_ms": optimal,
            "optimal_timeout_s": round(optimal / 1000),
        })

    return timeouts


def apply_learning(edb, gaps_db):
    """Apply learned routing and timeout optimizations."""
    applied = []

    # Apply timeouts
    timeouts = compute_optimal_timeouts(edb)
    for t in timeouts:
        gaps_db.execute("""
            INSERT OR REPLACE INTO timeout_configs
            (timestamp, pattern, node, recommended_timeout_s, p50_latency_ms,
             p95_latency_ms, max_latency_ms, sample_count, applied)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (datetime.now().isoformat(), t["type"], t["node"],
              t["optimal_timeout_s"], t["p50_ms"], t["p95_ms"],
              t["p95_ms"], 1))
        applied.append(f"timeout {t['type']}/{t['node']} = {t['optimal_timeout_s']}s")
    gaps_db.commit()

    # Store routing recommendations
    routing = analyze_routing(edb)
    gaps_db.execute("""CREATE TABLE IF NOT EXISTS routing_recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, task_type TEXT,
        best_node TEXT, score REAL,
        fallback_node TEXT, fallback_score REAL
    )""")

    for t, nodes in routing.items():
        if nodes:
            best = nodes[0]
            fallback = nodes[1] if len(nodes) > 1 else None
            gaps_db.execute("""
                INSERT INTO routing_recommendations
                (timestamp, task_type, best_node, score, fallback_node, fallback_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(), t,
                best["node"], best["composite_score"],
                fallback["node"] if fallback else None,
                fallback["composite_score"] if fallback else None,
            ))
            applied.append(f"route {t} -> {best['node']} ({best['composite_score']:.2f})")
    gaps_db.commit()

    return applied


def send_telegram(text):
    import urllib.parse
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Dispatch Learner")
    parser.add_argument("--once", action="store_true", help="Analyze + report")
    parser.add_argument("--learn", action="store_true", help="Full learning cycle")
    parser.add_argument("--routing", action="store_true", help="Show routing table")
    parser.add_argument("--trends", action="store_true", help="Show trends")
    args = parser.parse_args()

    if not any([args.once, args.learn, args.routing, args.trends]):
        parser.print_help()
        sys.exit(1)

    edb = get_etoile()

    # Check table exists
    has = edb.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='agent_dispatch_log'"
    ).fetchone()[0]
    if not has:
        print("No agent_dispatch_log table. Run dispatch_quality_tracker.py --init first.")
        edb.close()
        return

    total = edb.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
    print(f"Dispatch data: {total} records")

    if args.routing:
        routing = analyze_routing(edb)
        print("\n=== Optimal Routing Table ===")
        for t, nodes in sorted(routing.items()):
            print(f"\n  {t}:")
            for n in nodes:
                print(f"    {n['node']:6} score={n['composite_score']:.3f} "
                      f"ok={n['success_rate']}% q={n['avg_quality']:.2f} "
                      f"lat={n['avg_latency_ms']}ms ({n['total']}x)")
        edb.close()
        return

    if args.trends:
        trends = analyze_trends(edb)
        print("\n=== Quality Trends ===")
        if not trends:
            print("  No significant trends detected (need more data)")
        for t in trends:
            arrow = "+" if t["direction"] == "improving" else "-"
            print(f"  {arrow} {t['type']}/{t['node']}: "
                  f"q={t['quality_change_pct']:+.1f}% "
                  f"lat={t['latency_change_pct']:+.1f}% "
                  f"success={t['success_change_pct']:+.1f}%")
        edb.close()
        return

    if args.once:
        routing = analyze_routing(edb)
        trends = analyze_trends(edb)
        timeouts = compute_optimal_timeouts(edb)

        report = {
            "timestamp": datetime.now().isoformat(),
            "total_dispatches": total,
            "routing": {t: nodes[0] if nodes else None for t, nodes in routing.items()},
            "trends": trends,
            "timeout_adjustments": len(timeouts),
        }
        print(json.dumps(report, indent=2))

        # Telegram summary
        lines = [f"<b>Dispatch Learning</b> <code>{datetime.now().strftime('%H:%M')}</code>",
                 f"Data: {total} dispatches"]
        if routing:
            lines.append("")
            for t, nodes in sorted(routing.items()):
                if nodes:
                    lines.append(f"  {t} -> {nodes[0]['node']} (q={nodes[0]['avg_quality']:.2f})")
        if trends:
            lines.append("")
            for t in trends[:3]:
                lines.append(f"  {'++' if t['direction']=='improving' else '--'} {t['type']}/{t['node']}")
        send_telegram("\n".join(lines))
        edb.close()
        return

    if args.learn:
        print("=== Full Learning Cycle ===")
        gaps_db = get_gaps()

        # 1. Analyze routing
        routing = analyze_routing(edb)
        print(f"\n1. Routing: {len(routing)} task types analyzed")
        for t, nodes in sorted(routing.items()):
            if nodes:
                print(f"   {t} -> {nodes[0]['node']} (score={nodes[0]['composite_score']:.3f})")

        # 2. Check trends
        trends = analyze_trends(edb)
        print(f"\n2. Trends: {len(trends)} significant changes")
        for t in trends:
            print(f"   {t['direction']}: {t['type']}/{t['node']} q={t['quality_change_pct']:+.1f}%")

        # 3. Compute timeouts
        timeouts = compute_optimal_timeouts(edb)
        print(f"\n3. Timeouts: {len(timeouts)} configs computed")

        # 4. Apply
        applied = apply_learning(edb, gaps_db)
        print(f"\n4. Applied {len(applied)} optimizations:")
        for a in applied:
            print(f"   {a}")

        gaps_db.close()
        edb.close()

        # Telegram
        lines = [f"<b>Learning Cycle</b> <code>{datetime.now().strftime('%H:%M')}</code>",
                 f"Routes: {len(routing)} | Trends: {len(trends)} | Timeouts: {len(timeouts)}",
                 f"Applied: {len(applied)} optimizations"]
        send_telegram("\n".join(lines))
        return


if __name__ == "__main__":
    main()
