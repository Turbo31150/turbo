#!/usr/bin/env python3
"""dispatch_cost_estimator.py — Estimates resource cost of cluster dispatches.

Reads agent_dispatch_log from etoile.db, computes GPU-time cost units,
waste from failures, retry overhead, and per-pattern/per-node efficiency.

Usage:
    python dev/dispatch_cost_estimator.py --once
    python dev/dispatch_cost_estimator.py --by-pattern
    python dev/dispatch_cost_estimator.py --stats
"""
import argparse
import json
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from _paths import ETOILE_DB
GAPS_DB = Path(__file__).parent / "data" / "cowork_gaps.db"


def _connect_etoile():
    """Connect to etoile.db read-only."""
    if not ETOILE_DB.exists():
        raise FileNotFoundError(f"etoile.db not found: {ETOILE_DB}")
    return sqlite3.connect(str(ETOILE_DB))


def _init_gaps_db():
    """Ensure cost_estimates table exists in cowork_gaps.db."""
    GAPS_DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(GAPS_DB))
    db.execute("""CREATE TABLE IF NOT EXISTS cost_estimates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        total_cost REAL NOT NULL,
        waste_pct REAL NOT NULL,
        details_json TEXT NOT NULL
    )""")
    db.commit()
    return db


def _fetch_dispatches():
    """Load all dispatch log rows."""
    db = _connect_etoile()
    cur = db.execute(
        "SELECT id, timestamp, request_text, classified_type, agent_id, "
        "model_used, node, strategy, latency_ms, tokens_in, tokens_out, "
        "success, error_msg, quality_score FROM agent_dispatch_log"
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    db.close()
    return rows


def _compute_cost_unit(row):
    """Cost unit = latency_ms * max(tokens_out, 1) / 1000.

    For failed dispatches, tokens_out is typically 0, so the cost is
    latency_ms / 1000 (full latency wasted with no output).
    """
    tokens = max(row.get("tokens_out") or 0, 1) if row.get("success") else 1
    latency = row.get("latency_ms") or 0.0
    return latency * tokens / 1000.0


def _detect_retries(rows):
    """Group dispatches by request_text; entries with count > 1 are retries."""
    groups = defaultdict(list)
    for r in rows:
        key = (r.get("request_text") or "").strip()
        if key:
            groups[key].append(r)
    retries = {}
    for text, group in groups.items():
        if len(group) > 1:
            retries[text] = group
    return retries


def analyze_costs(rows):
    """Full cost analysis: per-pattern, per-node, retries, optimization targets."""
    total_cost = 0.0
    failed_cost = 0.0
    total_count = len(rows)
    failed_count = 0

    by_pattern = defaultdict(lambda: {
        "count": 0, "success": 0, "failed": 0,
        "total_cost": 0.0, "failed_cost": 0.0,
        "total_tokens_out": 0, "total_latency_ms": 0.0,
    })
    by_node = defaultdict(lambda: {
        "count": 0, "success": 0, "failed": 0,
        "total_cost": 0.0, "failed_cost": 0.0,
        "total_tokens_out": 0, "total_latency_ms": 0.0,
    })

    for r in rows:
        cost = _compute_cost_unit(r)
        total_cost += cost
        is_fail = not r.get("success")
        pattern = r.get("classified_type") or "unknown"
        node = r.get("node") or "unknown"

        if is_fail:
            failed_cost += cost
            failed_count += 1

        for bucket, key in [(by_pattern, pattern), (by_node, node)]:
            bucket[key]["count"] += 1
            bucket[key]["total_cost"] += cost
            bucket[key]["total_tokens_out"] += (r.get("tokens_out") or 0)
            bucket[key]["total_latency_ms"] += (r.get("latency_ms") or 0.0)
            if is_fail:
                bucket[key]["failed"] += 1
                bucket[key]["failed_cost"] += cost
            else:
                bucket[key]["success"] += 1

    # Retry analysis
    retries = _detect_retries(rows)
    retry_count = sum(len(g) - 1 for g in retries.values())
    retry_cost = 0.0
    for group in retries.values():
        # All dispatches after the first are retry overhead
        for r in group[1:]:
            retry_cost += _compute_cost_unit(r)

    # Enrich pattern stats
    pattern_results = []
    for pat, d in by_pattern.items():
        waste = (d["failed_cost"] / d["total_cost"] * 100) if d["total_cost"] > 0 else 0.0
        successful_time = d["total_latency_ms"] - sum(
            r.get("latency_ms", 0) for r in rows
            if (r.get("classified_type") or "unknown") == pat and not r.get("success")
        )
        efficiency = (
            d["total_tokens_out"] / (successful_time / 1000.0)
            if successful_time > 0 else 0.0
        )
        pattern_results.append({
            "pattern": pat,
            "count": d["count"],
            "success": d["success"],
            "failed": d["failed"],
            "total_cost": round(d["total_cost"], 2),
            "avg_cost": round(d["total_cost"] / d["count"], 2) if d["count"] else 0,
            "waste_pct": round(waste, 1),
            "efficiency_tok_per_s": round(efficiency, 2),
        })
    pattern_results.sort(key=lambda x: x["total_cost"], reverse=True)

    # Enrich node stats
    node_results = []
    for nd, d in by_node.items():
        waste = (d["failed_cost"] / d["total_cost"] * 100) if d["total_cost"] > 0 else 0.0
        successful_time = d["total_latency_ms"] - sum(
            r.get("latency_ms", 0) for r in rows
            if (r.get("node") or "unknown") == nd and not r.get("success")
        )
        efficiency = (
            d["total_tokens_out"] / (successful_time / 1000.0)
            if successful_time > 0 else 0.0
        )
        # Efficiency score 0-100 based on success rate and output density
        success_rate = d["success"] / d["count"] if d["count"] else 0
        token_density = d["total_tokens_out"] / d["count"] if d["count"] else 0
        # Normalize: assume 200 tok/dispatch as reference
        density_score = min(token_density / 200.0, 1.0)
        eff_score = round((success_rate * 0.6 + density_score * 0.4) * 100, 1)

        node_results.append({
            "node": nd,
            "count": d["count"],
            "success": d["success"],
            "failed": d["failed"],
            "total_cost": round(d["total_cost"], 2),
            "avg_cost": round(d["total_cost"] / d["count"], 2) if d["count"] else 0,
            "waste_pct": round(waste, 1),
            "efficiency_score": eff_score,
            "efficiency_tok_per_s": round(efficiency, 2),
        })
    node_results.sort(key=lambda x: x["total_cost"], reverse=True)

    # Optimization targets: patterns with highest waste (absolute cost wasted)
    optimization_targets = []
    for p in pattern_results:
        wasted_abs = p["total_cost"] * p["waste_pct"] / 100.0
        if wasted_abs > 0 or p["failed"] > 0:
            saving_if_fixed = wasted_abs + (
                retry_cost * (p["count"] / total_count) if total_count else 0
            )
            optimization_targets.append({
                "pattern": p["pattern"],
                "wasted_cost": round(wasted_abs, 2),
                "failed_dispatches": p["failed"],
                "potential_saving": round(saving_if_fixed, 2),
                "recommendation": _recommend(p),
            })
    optimization_targets.sort(key=lambda x: x["potential_saving"], reverse=True)

    waste_pct = (failed_cost / total_cost * 100) if total_cost > 0 else 0.0

    return {
        "timestamp": datetime.now().isoformat(),
        "total_dispatches": total_count,
        "successful": total_count - failed_count,
        "failed": failed_count,
        "total_cost_units": round(total_cost, 2),
        "failed_cost_units": round(failed_cost, 2),
        "waste_pct": round(waste_pct, 1),
        "retry_dispatches": retry_count,
        "retry_cost_units": round(retry_cost, 2),
        "by_pattern": pattern_results[:10],
        "by_node": node_results,
        "optimization_targets": optimization_targets[:5],
    }


def _recommend(pattern_stats):
    """Generate a short recommendation based on pattern stats."""
    if pattern_stats["waste_pct"] > 50:
        return "High failure rate — consider switching node or disabling pattern"
    if pattern_stats["waste_pct"] > 20:
        return "Moderate waste — add fallback node or increase timeout"
    if pattern_stats["avg_cost"] > 1000:
        return "Expensive dispatches — optimize prompt or reduce output length"
    if pattern_stats["failed"] > 0:
        return "Some failures — review error logs for this pattern"
    return "Healthy"


def do_once():
    """--once: Full cost analysis, output JSON, store in cowork_gaps.db."""
    rows = _fetch_dispatches()
    if not rows:
        result = {
            "timestamp": datetime.now().isoformat(),
            "error": "No dispatches found in agent_dispatch_log",
            "total_cost_units": 0, "waste_pct": 0,
            "by_pattern": [], "by_node": [], "optimization_targets": [],
        }
        print(json.dumps(result, indent=2))
        return result

    result = analyze_costs(rows)

    # Store in cowork_gaps.db
    gdb = _init_gaps_db()
    gdb.execute(
        "INSERT INTO cost_estimates (timestamp, total_cost, waste_pct, details_json) "
        "VALUES (?, ?, ?, ?)",
        (result["timestamp"], result["total_cost_units"],
         result["waste_pct"], json.dumps(result)),
    )
    gdb.commit()
    gdb.close()

    print(json.dumps(result, indent=2))
    return result


def do_by_pattern():
    """--by-pattern: Cost breakdown per pattern."""
    rows = _fetch_dispatches()
    if not rows:
        print(json.dumps({"error": "No dispatches found"}, indent=2))
        return

    result = analyze_costs(rows)
    patterns = result["by_pattern"]

    # Table output
    print(f"\n{'Pattern':<20} {'Count':>6} {'OK':>5} {'Fail':>5} {'TotalCost':>12} "
          f"{'AvgCost':>10} {'Waste%':>7} {'Eff tok/s':>10}")
    print("-" * 85)
    for p in patterns:
        print(f"{p['pattern']:<20} {p['count']:>6} {p['success']:>5} {p['failed']:>5} "
              f"{p['total_cost']:>12.2f} {p['avg_cost']:>10.2f} "
              f"{p['waste_pct']:>6.1f}% {p['efficiency_tok_per_s']:>10.2f}")

    total = result["total_cost_units"]
    waste = result["waste_pct"]
    print(f"\n  Total cost units: {total:.2f}  |  Waste: {waste:.1f}%  "
          f"|  Retries: {result['retry_dispatches']}  "
          f"|  Retry cost: {result['retry_cost_units']:.2f}")

    if result["optimization_targets"]:
        print(f"\n  Top optimization targets:")
        for t in result["optimization_targets"][:5]:
            print(f"    - {t['pattern']}: save ~{t['potential_saving']:.2f} units "
                  f"({t['failed_dispatches']} failures) — {t['recommendation']}")


def do_stats():
    """--stats: Historical cost estimates from cowork_gaps.db."""
    gdb = _init_gaps_db()
    rows = gdb.execute(
        "SELECT id, timestamp, total_cost, waste_pct, details_json "
        "FROM cost_estimates ORDER BY id DESC LIMIT 20"
    ).fetchall()
    gdb.close()

    if not rows:
        print(json.dumps({"message": "No historical estimates yet. Run --once first."}, indent=2))
        return

    print(f"\n{'ID':>4} {'Timestamp':<22} {'TotalCost':>12} {'Waste%':>8}")
    print("-" * 50)
    for r in rows:
        print(f"{r[0]:>4} {r[1]:<22} {r[2]:>12.2f} {r[3]:>7.1f}%")

    # Show trend if enough data
    if len(rows) >= 2:
        latest = rows[0]
        previous = rows[1]
        cost_delta = latest[2] - previous[2]
        waste_delta = latest[3] - previous[3]
        direction_cost = "+" if cost_delta >= 0 else ""
        direction_waste = "+" if waste_delta >= 0 else ""
        print(f"\n  Trend: cost {direction_cost}{cost_delta:.2f} units  |  "
              f"waste {direction_waste}{waste_delta:.1f}%")

    # Summary from latest
    details = json.loads(rows[0][4])
    print(f"\n  Latest run ({details.get('timestamp', 'N/A')}):")
    print(f"    Dispatches: {details.get('total_dispatches', 0)}  |  "
          f"Failed: {details.get('failed', 0)}  |  "
          f"Retries: {details.get('retry_dispatches', 0)}")
    if details.get("optimization_targets"):
        print(f"    Top target: {details['optimization_targets'][0]['pattern']} "
              f"(save ~{details['optimization_targets'][0]['potential_saving']:.2f})")


def main():
    parser = argparse.ArgumentParser(
        description="Dispatch Cost Estimator — analyze resource cost of cluster dispatches"
    )
    parser.add_argument("--once", action="store_true",
                        help="Full cost analysis (JSON output, stored in cowork_gaps.db)")
    parser.add_argument("--by-pattern", action="store_true",
                        help="Cost breakdown per dispatch pattern (table output)")
    parser.add_argument("--stats", action="store_true",
                        help="Historical cost estimates from cowork_gaps.db")
    args = parser.parse_args()

    if args.once:
        do_once()
    elif args.by_pattern:
        do_by_pattern()
    elif args.stats:
        do_stats()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
