#!/usr/bin/env python3
"""jarvis_dashboard.py — Unified JARVIS cluster dashboard.

Single command to see everything:
- Health grade and components
- Node reliability rankings
- Circuit breaker states
- Load distribution
- Latency baselines
- Recent dispatch stats
- Active risks
- Orchestrator status

CLI:
    --once         : Show dashboard
    --compact      : Compact one-line summary
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
from _paths import ETOILE_DB


def get_db(path):
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def safe_query(db, sql, default=None):
    try:
        return db.execute(sql).fetchall()
    except Exception:
        return default or []


def build_dashboard():
    """Build complete dashboard data."""
    gaps = get_db(GAPS_DB)
    edb = get_db(ETOILE_DB)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data = {"timestamp": ts}

    # 1. Node status
    nodes = safe_query(gaps, "SELECT node, last_status, consecutive_fails FROM heartbeat_state ORDER BY node")
    data["nodes"] = {r["node"]: {"status": r["last_status"], "fails": r["consecutive_fails"]} for r in nodes}
    data["nodes_online"] = sum(1 for r in nodes if r["last_status"] == "online")
    data["nodes_total"] = len(nodes)

    # 2. Reliability scores
    rel = safe_query(gaps, "SELECT node, composite, rank FROM node_reliability ORDER BY rank")
    data["reliability"] = {r["node"]: {"score": r["composite"], "rank": r["rank"]} for r in rel}

    # 3. Circuit breakers
    cb = safe_query(gaps, "SELECT node, state, fail_count FROM circuit_breaker_state")
    data["circuit_breakers"] = {r["node"]: {"state": r["state"], "fails": r["fail_count"]} for r in cb}

    # 4. Load
    load = safe_query(gaps, "SELECT node, current_load, total_dispatched, avg_response_ms FROM node_load")
    data["load"] = {r["node"]: {"current": r["current_load"], "total": r["total_dispatched"],
                                 "avg_ms": round(r["avg_response_ms"])} for r in load}

    # 5. Latency baselines
    lat = safe_query(gaps, "SELECT node, avg_ms, p95_ms, sample_count FROM latency_baselines")
    data["latency"] = {r["node"]: {"avg_ms": round(r["avg_ms"]), "p95_ms": round(r["p95_ms"]),
                                    "samples": r["sample_count"]} for r in lat}

    # 6. Dispatch stats
    try:
        has = edb.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='agent_dispatch_log'").fetchone()[0]
        if has:
            row = edb.execute("""
                SELECT COUNT(*) as total,
                       ROUND(AVG(CASE WHEN success=1 THEN 100.0 ELSE 0 END), 1) as rate,
                       ROUND(AVG(quality_score)*100, 1) as quality,
                       ROUND(AVG(latency_ms)) as avg_lat
                FROM (SELECT * FROM agent_dispatch_log ORDER BY id DESC LIMIT 50)
            """).fetchone()
            data["dispatch"] = {"total": row["total"], "success_pct": row["rate"] or 0,
                                "quality_pct": row["quality"] or 0, "avg_lat_ms": row["avg_lat"] or 0}
            total_all = edb.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
            data["dispatch"]["total_all"] = total_all
    except Exception:
        data["dispatch"] = {"total": 0, "success_pct": 0}

    # 7. Risks
    risks = safe_query(gaps, """
        SELECT target, risk_level, risk_score FROM failure_predictions
        WHERE timestamp > datetime('now', '-2 hours')
        ORDER BY risk_score DESC LIMIT 5
    """)
    data["risks"] = [{"target": r["target"], "level": r["risk_level"],
                       "score": r["risk_score"]} for r in risks]
    data["max_risk"] = risks[0]["risk_score"] if risks else 0

    # 8. Orchestrator
    orch = safe_query(gaps, "SELECT task_name, run_count, fail_count FROM orchestrator_schedule")
    data["orchestrator"] = {
        "tasks": len(orch),
        "total_runs": sum(r["run_count"] for r in orch),
        "total_fails": sum(r["fail_count"] for r in orch),
    }
    if data["orchestrator"]["total_runs"] > 0:
        data["orchestrator"]["success_pct"] = round(
            (data["orchestrator"]["total_runs"] - data["orchestrator"]["total_fails"])
            / data["orchestrator"]["total_runs"] * 100, 1
        )

    # 9. Grade components
    scores = []
    if data["nodes_total"]:
        scores.append(data["nodes_online"] / data["nodes_total"] * 100)
    if data["dispatch"].get("total"):
        scores.append(data["dispatch"]["success_pct"])
    scores.append(100 if data["orchestrator"].get("success_pct", 0) >= 95
                  else data["orchestrator"].get("success_pct", 0))
    scores.append(100 - data["max_risk"])

    data["grade_score"] = round(sum(scores) / max(len(scores), 1), 1)
    g = data["grade_score"]
    data["grade"] = "A+" if g >= 95 else "A" if g >= 90 else "A-" if g >= 85 else "B" if g >= 75 else "C"

    # 10. Script count
    data["scripts"] = len(list(SCRIPT_DIR.glob("*.py")))

    # 11. DB stats
    gaps_size = GAPS_DB.stat().st_size / (1024 * 1024) if GAPS_DB.exists() else 0
    etoile_size = ETOILE_DB.stat().st_size / (1024 * 1024) if ETOILE_DB.exists() else 0
    data["db"] = {"gaps_mb": round(gaps_size, 1), "etoile_mb": round(etoile_size, 1)}

    gaps.close()
    edb.close()
    return data


def format_dashboard(data):
    """Format dashboard for terminal."""
    lines = []
    g = data["grade"]
    s = data["grade_score"]
    lines.append(f"  JARVIS Dashboard  [{g}] {s}/100  {data['timestamp']}")
    lines.append(f"  {'='*55}")

    # Nodes
    node_str = " ".join(
        f"{'OK' if v['status']=='online' else 'XX'}:{k}"
        for k, v in sorted(data.get("nodes", {}).items())
    )
    lines.append(f"  Cluster   {data['nodes_online']}/{data['nodes_total']} online  {node_str}")

    # Reliability
    if data.get("reliability"):
        rel_str = " ".join(
            f"#{v['rank']}{k}({v['score']:.0f})"
            for k, v in sorted(data["reliability"].items(), key=lambda x: x[1]["rank"])
        )
        lines.append(f"  Reliable  {rel_str}")

    # Circuit Breakers
    if data.get("circuit_breakers"):
        cb_parts = []
        for k, v in sorted(data["circuit_breakers"].items()):
            state = v["state"][:1]  # C, O, H
            cb_parts.append(f"{k}={state}")
        lines.append(f"  Circuits  {' '.join(cb_parts)}")

    # Latency
    if data.get("latency"):
        lat_str = " ".join(f"{k}={v['avg_ms']}ms" for k, v in sorted(data["latency"].items()))
        lines.append(f"  Latency   {lat_str}")

    # Dispatch
    d = data.get("dispatch", {})
    if d.get("total"):
        lines.append(f"  Dispatch  {d['success_pct']}% ok  q={d.get('quality_pct', 0)}%  "
                      f"avg={d.get('avg_lat_ms', 0):.0f}ms  ({d.get('total_all', d['total'])} total)")

    # Orchestrator
    o = data.get("orchestrator", {})
    lines.append(f"  Tasks     {o.get('tasks', 0)} tasks  {o.get('total_runs', 0)} runs  "
                  f"{o.get('success_pct', 0)}% ok")

    # Risks
    if data.get("risks"):
        risk_str = " ".join(f"{r['target']}({r['score']:.0f})" for r in data["risks"][:3])
        lines.append(f"  Risks     {len(data['risks'])} items  max={data['max_risk']:.0f}  {risk_str}")
    else:
        lines.append(f"  Risks     None")

    # Meta
    lines.append(f"  Scripts   {data['scripts']}  DB: gaps={data['db']['gaps_mb']}MB etoile={data['db']['etoile_mb']}MB")

    return "\n".join(lines)


def format_compact(data):
    """One-line summary."""
    g = data["grade"]
    s = data["grade_score"]
    n = data["nodes_online"]
    t = data["nodes_total"]
    d = data.get("dispatch", {}).get("success_pct", 0)
    return f"JARVIS [{g}] {s}/100 | {n}/{t} nodes | dispatch {d}% | {data['scripts']} scripts"


def main():
    parser = argparse.ArgumentParser(description="JARVIS Dashboard")
    parser.add_argument("--once", action="store_true", help="Show dashboard")
    parser.add_argument("--compact", action="store_true", help="One-line")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not any([args.once, args.compact, args.json]):
        parser.print_help()
        sys.exit(1)

    data = build_dashboard()

    if args.json:
        print(json.dumps(data, indent=2, default=str))
    elif args.compact:
        print(format_compact(data))
    else:
        print(format_dashboard(data))


if __name__ == "__main__":
    main()
