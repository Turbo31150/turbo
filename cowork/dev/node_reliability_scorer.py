#!/usr/bin/env python3
"""node_reliability_scorer.py — Compute reliability scores for each cluster node.

Combines metrics from multiple sources to produce a single reliability score:
- Heartbeat uptime (25%)
- Dispatch success rate (25%)
- Latency percentile (25%)
- Quality score (25%)

Outputs a ranked list of nodes for routing decisions.

CLI:
    --once         : Compute and display scores
    --update       : Compute and store in DB
    --json         : JSON output

Stdlib-only (json, argparse, sqlite3).
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")

ALL_NODES = ["M1", "OL1", "M2", "M3"]


def get_db(path):
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def get_uptime_score(gaps_db):
    """Uptime score from heartbeat data."""
    scores = {}
    try:
        rows = gaps_db.execute("""
            SELECT node,
                   SUM(CASE WHEN status='online' THEN 1 ELSE 0 END) as online,
                   COUNT(*) as total
            FROM heartbeat_log
            WHERE timestamp > datetime('now', '-24 hours')
            GROUP BY node
        """).fetchall()
        for r in rows:
            scores[r["node"]] = r["online"] / max(r["total"], 1) * 100
    except Exception:
        pass

    # Default 50 for nodes without data
    for n in ALL_NODES:
        if n not in scores:
            scores[n] = 50.0
    return scores


def get_dispatch_score(edb):
    """Dispatch success rate from agent_dispatch_log."""
    scores = {}
    try:
        has = edb.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='agent_dispatch_log'"
        ).fetchone()[0]
        if has:
            rows = edb.execute("""
                SELECT node,
                       SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
                       COUNT(*) as total
                FROM agent_dispatch_log
                GROUP BY node
            """).fetchall()
            for r in rows:
                scores[r["node"]] = r["ok"] / max(r["total"], 1) * 100
    except Exception:
        pass

    for n in ALL_NODES:
        if n not in scores:
            scores[n] = 50.0
    return scores


def get_latency_score(gaps_db):
    """Latency score from baselines (lower is better)."""
    scores = {}
    try:
        rows = gaps_db.execute("""
            SELECT node, avg_ms, p95_ms FROM latency_baselines
        """).fetchall()

        if rows:
            # Score: 100 for fastest, proportionally less for slower
            min_lat = min(r["avg_ms"] for r in rows if r["avg_ms"])
            for r in rows:
                if r["avg_ms"] and min_lat > 0:
                    ratio = min_lat / r["avg_ms"]
                    scores[r["node"]] = min(ratio * 100, 100)
    except Exception:
        pass

    for n in ALL_NODES:
        if n not in scores:
            scores[n] = 50.0
    return scores


def get_quality_score(edb):
    """Quality score from dispatch quality data."""
    scores = {}
    try:
        has = edb.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='agent_dispatch_log'"
        ).fetchone()[0]
        if has:
            rows = edb.execute("""
                SELECT node, ROUND(AVG(quality_score) * 100, 1) as avg_q
                FROM agent_dispatch_log
                WHERE success=1
                GROUP BY node
            """).fetchall()
            for r in rows:
                if r["avg_q"] is not None:
                    scores[r["node"]] = r["avg_q"]
    except Exception:
        pass

    for n in ALL_NODES:
        if n not in scores:
            scores[n] = 50.0
    return scores


def compute_reliability(gaps_db, edb):
    """Compute composite reliability scores."""
    uptime = get_uptime_score(gaps_db)
    dispatch = get_dispatch_score(edb)
    latency = get_latency_score(gaps_db)
    quality = get_quality_score(edb)

    results = {}
    for node in ALL_NODES:
        u = uptime.get(node, 50)
        d = dispatch.get(node, 50)
        l = latency.get(node, 50)
        q = quality.get(node, 50)

        composite = u * 0.25 + d * 0.25 + l * 0.25 + q * 0.25
        results[node] = {
            "composite": round(composite, 1),
            "uptime": round(u, 1),
            "dispatch": round(d, 1),
            "latency": round(l, 1),
            "quality": round(q, 1),
            "rank": 0,
        }

    # Assign ranks
    ranked = sorted(results.items(), key=lambda x: -x[1]["composite"])
    for i, (node, data) in enumerate(ranked):
        data["rank"] = i + 1

    return results


def store_scores(gaps_db, scores):
    """Store reliability scores in DB."""
    gaps_db.execute("""CREATE TABLE IF NOT EXISTS node_reliability (
        node TEXT PRIMARY KEY,
        composite REAL,
        uptime REAL,
        dispatch REAL,
        latency REAL,
        quality REAL,
        rank INTEGER,
        updated_at TEXT
    )""")

    now = datetime.now().isoformat()
    for node, data in scores.items():
        gaps_db.execute("""
            INSERT INTO node_reliability (node, composite, uptime, dispatch, latency, quality, rank, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(node) DO UPDATE SET
                composite=?, uptime=?, dispatch=?, latency=?, quality=?, rank=?, updated_at=?
        """, (node, data["composite"], data["uptime"], data["dispatch"],
              data["latency"], data["quality"], data["rank"], now,
              data["composite"], data["uptime"], data["dispatch"],
              data["latency"], data["quality"], data["rank"], now))
    gaps_db.commit()


def main():
    parser = argparse.ArgumentParser(description="Node Reliability Scorer")
    parser.add_argument("--once", action="store_true", help="Compute scores")
    parser.add_argument("--update", action="store_true", help="Compute and store")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not any([args.once, args.update]):
        parser.print_help()
        sys.exit(1)

    gaps_db = get_db(GAPS_DB)
    edb = get_db(ETOILE_DB)

    scores = compute_reliability(gaps_db, edb)

    if args.update:
        store_scores(gaps_db, scores)
        print("Scores stored in node_reliability table")

    if args.json:
        print(json.dumps(scores, indent=2))
    else:
        print("=== Node Reliability Scores ===")
        ranked = sorted(scores.items(), key=lambda x: -x[1]["composite"])
        for node, data in ranked:
            bar = "#" * int(data["composite"] / 5)
            print(f"  #{data['rank']} {node:4} {data['composite']:5.1f}/100 {bar}")
            print(f"       uptime={data['uptime']:.0f} dispatch={data['dispatch']:.0f} "
                  f"latency={data['latency']:.0f} quality={data['quality']:.0f}")

    gaps_db.close()
    edb.close()


if __name__ == "__main__":
    main()
