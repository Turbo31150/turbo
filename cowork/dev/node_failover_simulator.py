#!/usr/bin/env python3
"""
node_failover_simulator.py — Simulates node failure and measures cluster resilience.

Reads agent_dispatch_log and agent_patterns from etoile.db to answer:
  - What happens if a node goes down?
  - Which patterns lose their only capable node?
  - How does success rate / latency / capacity change?

CLI:
  --once              Simulate all nodes, output JSON summary
  --node NODE         Detailed simulation for a specific node (M1, M2, M3, OL1)
  --stats             Show history of past simulations from cowork_gaps.db

Stdlib-only: sqlite3, json, argparse, datetime, pathlib, collections
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")
GAPS_DB = Path(r"F:/BUREAU/turbo/cowork/dev/data/cowork_gaps.db")

# Fallback chain: if a node dies, redistribute to these in order
FALLBACK_CHAIN = ["M1", "M2", "M3", "OL1"]

# Typical latency multipliers when a fallback node absorbs extra load
# (based on benchmark data: degradation under load)
LATENCY_PENALTY = {
    "M1": 1.0,    # baseline
    "M2": 2.0,    # ~2x slower than M1
    "M3": 2.2,    # ~2.2x slower
    "OL1": 0.8,   # fast for simple tasks
}

# Success rate baseline per node (from real data)
NODE_SUCCESS_BASELINE = {
    "M1": 0.747,   # 1241/1662
    "M2": 0.633,   # 57/90
    "M3": 0.051,   # 3/59
    "OL1": 0.950,  # 659/694
}


def ensure_gaps_table():
    """Create failover_simulations table in cowork_gaps.db if missing."""
    conn = sqlite3.connect(str(GAPS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS failover_simulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node_simulated TEXT NOT NULL,
            resilience_score REAL NOT NULL,
            details_json TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def load_dispatch_data():
    """Load all dispatch log entries from etoile.db."""
    if not ETOILE_DB.exists():
        print(f"ERROR: {ETOILE_DB} not found", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(ETOILE_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, node, classified_type, agent_id, model_used,
               latency_ms, success, quality_score
        FROM agent_dispatch_log
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_patterns():
    """Load agent patterns with their primary model and fallbacks."""
    conn = sqlite3.connect(str(ETOILE_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT pattern_id, agent_id, model_primary, model_fallbacks,
               total_calls, success_rate, avg_latency_ms
        FROM agent_patterns
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def model_to_node(model_str):
    """Map a model string to a node name.

    Examples:
        'qwen3-8b' -> 'M1'
        'M2:deepseek-r1' -> 'M2'
        'gpt-oss:120b-cloud' -> 'OL1' (cloud via Ollama)
        'deepseek-r1-0528-qwen3-8b' -> 'M2' (primary reasoning model)
        'minimax-m2.5:cloud' -> 'OL1'
        'qwen3:1.7b' -> 'OL1'
    """
    if not model_str:
        return None
    s = model_str.strip()

    # Explicit node prefix (e.g. "M2:deepseek-r1", "M1:qwen3-8b")
    for prefix in ["M1:", "M2:", "M3:", "OL1:"]:
        if s.startswith(prefix):
            return prefix.rstrip(":")

    # Cloud models route through OL1 (Ollama)
    if "cloud" in s or s.startswith("minimax"):
        return "OL1"

    # Known model -> node mappings
    if s in ("qwen3-8b", "qwen/qwen3-8b"):
        return "M1"
    if s.startswith("deepseek-r1"):
        return "M2"  # M2 primary reasoning; M3 also runs deepseek-r1 but use M2 by default
    if s.startswith("qwen3:") or s == "qwen3:1.7b":
        return "OL1"

    # Fallback: check if it looks like a node name directly
    upper = s.upper()
    if upper in ("M1", "M2", "M3", "OL1"):
        return upper

    return None


def get_pattern_node_map(patterns):
    """For each pattern, determine its primary node and fallback nodes."""
    result = []
    for p in patterns:
        primary_node = model_to_node(p["model_primary"])

        fallback_nodes = []
        if p["model_fallbacks"]:
            for fb in p["model_fallbacks"].split(","):
                fb_node = model_to_node(fb.strip())
                if fb_node and fb_node != primary_node:
                    fallback_nodes.append(fb_node)

        result.append({
            "pattern_id": p["pattern_id"],
            "agent_id": p["agent_id"],
            "primary_node": primary_node,
            "fallback_nodes": fallback_nodes,
            "total_calls": p["total_calls"] or 0,
            "success_rate": p["success_rate"] or 0.0,
            "avg_latency_ms": p["avg_latency_ms"] or 0.0,
        })
    return result


def get_available_fallbacks(dead_node, original_fallbacks):
    """Return fallback nodes excluding the dead node, preserving order."""
    candidates = [n for n in original_fallbacks if n != dead_node]
    if not candidates:
        # Use global fallback chain minus dead node
        candidates = [n for n in FALLBACK_CHAIN if n != dead_node]
    return candidates


def simulate_node_failure(dead_node, dispatches, pattern_map):
    """Simulate removing a node and redistributing its traffic.

    Returns a dict with simulation results.
    """
    # --- Dispatch analysis ---
    total_dispatches = len(dispatches)
    affected_dispatches = [d for d in dispatches if d["node"] == dead_node]
    unaffected_dispatches = [d for d in dispatches if d["node"] != dead_node]
    affected_count = len(affected_dispatches)

    if total_dispatches == 0:
        return {
            "node": dead_node,
            "resilience_score": 100.0,
            "error": "No dispatch data available",
        }

    traffic_pct = (affected_count / total_dispatches) * 100 if total_dispatches else 0

    # Current stats for affected dispatches
    affected_successes = sum(1 for d in affected_dispatches if d["success"])
    affected_avg_latency = (
        sum(d["latency_ms"] for d in affected_dispatches if d["latency_ms"])
        / max(affected_count, 1)
    )

    # --- Redistribution simulation ---
    # For each affected dispatch, find where it would go
    redistributed = defaultdict(list)  # target_node -> list of dispatches
    orphaned = []  # dispatches with no fallback at all

    # Build a quick map: task_type -> best fallback from pattern definitions
    type_fallback_map = {}
    for pm in pattern_map:
        ptype = pm.get("agent_id", "")
        if pm["primary_node"] == dead_node:
            fb = get_available_fallbacks(dead_node, pm["fallback_nodes"])
            type_fallback_map[ptype] = fb
        elif dead_node in pm.get("fallback_nodes", []):
            # This pattern uses dead_node as fallback, still has primary
            pass

    for d in affected_dispatches:
        agent_id = d.get("agent_id", "")
        task_type = d.get("classified_type", "")

        # Try agent-specific fallback first
        fallbacks = type_fallback_map.get(agent_id, [])
        if not fallbacks:
            # Generic fallback chain
            fallbacks = [n for n in FALLBACK_CHAIN if n != dead_node]

        if fallbacks:
            target = fallbacks[0]
            redistributed[target].append(d)
        else:
            orphaned.append(d)

    # --- Capacity impact on receiving nodes ---
    # Current load per node
    node_current_load = defaultdict(int)
    for d in dispatches:
        node_current_load[d["node"]] += 1

    # Compute stats per receiving node
    node_stats_before = {}
    for node in FALLBACK_CHAIN:
        nd = [d for d in dispatches if d["node"] == node]
        if nd:
            node_stats_before[node] = {
                "count": len(nd),
                "success_rate": sum(1 for d in nd if d["success"]) / len(nd),
                "avg_latency_ms": sum(d["latency_ms"] for d in nd if d["latency_ms"]) / len(nd),
            }
        else:
            node_stats_before[node] = {"count": 0, "success_rate": 0.0, "avg_latency_ms": 0.0}

    redistribution_detail = {}
    estimated_new_success = 0
    estimated_new_latency_sum = 0
    estimated_new_count = 0

    for target, target_dispatches in redistributed.items():
        extra_load = len(target_dispatches)
        current = node_stats_before.get(target, {"count": 0, "success_rate": 0.0, "avg_latency_ms": 0.0})
        current_count = current["count"]
        new_total = current_count + extra_load

        # Load increase factor -> latency degradation
        if current_count > 0:
            load_factor = new_total / current_count
        else:
            load_factor = 1.5  # new node, moderate penalty

        # Estimate degraded latency (based on stress test data: ~56-86% degradation at 5x)
        degradation = min(1.0 + (load_factor - 1.0) * 0.4, 3.0)  # cap at 3x

        base_latency = current["avg_latency_ms"] if current["avg_latency_ms"] > 0 else affected_avg_latency
        estimated_latency = base_latency * degradation * LATENCY_PENALTY.get(target, 1.0)

        # Success rate: use target node baseline, with slight penalty for overload
        base_success = NODE_SUCCESS_BASELINE.get(target, 0.5)
        overload_penalty = max(0, (load_factor - 1.5) * 0.05)  # starts penalizing above 1.5x
        estimated_success = max(0.1, base_success - overload_penalty)

        redistribution_detail[target] = {
            "extra_dispatches": extra_load,
            "load_increase_pct": round((load_factor - 1.0) * 100, 1),
            "estimated_latency_ms": round(estimated_latency, 1),
            "estimated_success_rate": round(estimated_success, 3),
        }

        estimated_new_success += estimated_success * extra_load
        estimated_new_latency_sum += estimated_latency * extra_load
        estimated_new_count += extra_load

    # --- Pattern dependency analysis ---
    critical_patterns = []  # patterns that have NO fallback if this node dies
    degraded_patterns = []  # patterns that lose primary but have fallbacks
    unaffected_patterns = []

    for pm in pattern_map:
        if pm["primary_node"] == dead_node:
            available_fb = get_available_fallbacks(dead_node, pm["fallback_nodes"])
            if not available_fb:
                critical_patterns.append({
                    "pattern_id": pm["pattern_id"],
                    "agent_id": pm["agent_id"],
                    "total_calls": pm["total_calls"],
                    "reason": "No fallback nodes defined outside dead node",
                })
            else:
                degraded_patterns.append({
                    "pattern_id": pm["pattern_id"],
                    "agent_id": pm["agent_id"],
                    "total_calls": pm["total_calls"],
                    "fallback_to": available_fb[0],
                    "all_fallbacks": available_fb,
                })
        elif dead_node in pm.get("fallback_nodes", []):
            # Loses a fallback option but primary still works
            remaining = [n for n in pm["fallback_nodes"] if n != dead_node]
            degraded_patterns.append({
                "pattern_id": pm["pattern_id"],
                "agent_id": pm["agent_id"],
                "total_calls": pm["total_calls"],
                "fallback_to": pm["primary_node"],
                "lost_fallback": dead_node,
                "remaining_fallbacks": remaining,
            })
        else:
            unaffected_patterns.append(pm["pattern_id"])

    # --- Resilience score (0-100) ---
    # Factors:
    #   - Traffic impact: lower % affected = better (weight 30)
    #   - Critical patterns: fewer = better (weight 25)
    #   - Redistribution success: higher estimated success = better (weight 25)
    #   - Latency impact: lower increase = better (weight 20)

    # Traffic score: 100 if 0% affected, 0 if 100% affected
    traffic_score = max(0, 100 - traffic_pct)

    # Critical pattern score: 100 if none, 0 if all patterns critical
    total_patterns = len(pattern_map)
    if total_patterns > 0:
        critical_score = max(0, 100 - (len(critical_patterns) / total_patterns) * 200)
    else:
        critical_score = 100

    # Redistribution success score
    if estimated_new_count > 0:
        avg_new_success = estimated_new_success / estimated_new_count
        success_score = avg_new_success * 100
    else:
        success_score = 100 if affected_count == 0 else 0

    # Latency impact score
    if estimated_new_count > 0 and affected_avg_latency > 0:
        avg_new_latency = estimated_new_latency_sum / estimated_new_count
        latency_ratio = avg_new_latency / affected_avg_latency
        latency_score = max(0, 100 - (latency_ratio - 1.0) * 50)
    else:
        latency_score = 100

    resilience_score = round(
        traffic_score * 0.30
        + critical_score * 0.25
        + success_score * 0.25
        + latency_score * 0.20,
        1,
    )
    resilience_score = max(0, min(100, resilience_score))

    # --- Recommendations ---
    recommendations = []
    if traffic_pct > 50:
        recommendations.append(
            f"{dead_node} handles {traffic_pct:.0f}% of traffic — "
            f"critical single point of failure. Distribute load proactively."
        )
    if critical_patterns:
        names = [cp["pattern_id"] for cp in critical_patterns[:5]]
        recommendations.append(
            f"{len(critical_patterns)} pattern(s) have NO fallback: {', '.join(names)}. "
            f"Add fallback nodes to these patterns."
        )
    for target, detail in redistribution_detail.items():
        if detail["load_increase_pct"] > 80:
            recommendations.append(
                f"{target} would see +{detail['load_increase_pct']}% load increase — "
                f"risk of overload and cascading failures."
            )
    if not recommendations:
        recommendations.append(
            f"Cluster is resilient to {dead_node} failure. "
            f"All traffic can be redistributed with acceptable impact."
        )

    return {
        "node": dead_node,
        "resilience_score": resilience_score,
        "traffic": {
            "total_dispatches": total_dispatches,
            "affected_dispatches": affected_count,
            "affected_pct": round(traffic_pct, 1),
            "orphaned_dispatches": len(orphaned),
        },
        "current_stats": {
            "success_rate": round(affected_successes / max(affected_count, 1), 3),
            "avg_latency_ms": round(affected_avg_latency, 1),
        },
        "redistribution": redistribution_detail,
        "patterns": {
            "critical_no_fallback": critical_patterns,
            "degraded_count": len(degraded_patterns),
            "unaffected_count": len(unaffected_patterns),
        },
        "recommendations": recommendations,
    }


def store_simulation(node, score, details):
    """Persist simulation result in cowork_gaps.db."""
    ensure_gaps_table()
    conn = sqlite3.connect(str(GAPS_DB))
    conn.execute(
        """INSERT INTO failover_simulations
           (timestamp, node_simulated, resilience_score, details_json)
           VALUES (?, ?, ?, ?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            node,
            score,
            json.dumps(details, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


def show_stats():
    """Display history of past simulations."""
    ensure_gaps_table()
    conn = sqlite3.connect(str(GAPS_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, timestamp, node_simulated, resilience_score
        FROM failover_simulations
        ORDER BY timestamp DESC
        LIMIT 50
    """).fetchall()
    conn.close()

    if not rows:
        print("No simulation history found.")
        return

    print(f"{'ID':>4}  {'Timestamp':<26}  {'Node':<5}  {'Resilience':>10}")
    print("-" * 52)
    for r in rows:
        print(f"{r['id']:>4}  {r['timestamp']:<26}  {r['node_simulated']:<5}  {r['resilience_score']:>9.1f}%")


def run_once():
    """Simulate all nodes, output JSON summary."""
    dispatches = load_dispatch_data()
    patterns = load_patterns()
    pattern_map = get_pattern_node_map(patterns)

    nodes = sorted(set(d["node"] for d in dispatches if d["node"]))
    results = {}

    for node in nodes:
        sim = simulate_node_failure(node, dispatches, pattern_map)
        results[node] = sim
        store_simulation(node, sim["resilience_score"], sim)

    # Build summary
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nodes_analyzed": len(results),
        "total_dispatches": len(dispatches),
        "total_patterns": len(pattern_map),
        "per_node": {},
        "critical_dependencies": [],
        "recommendations": [],
    }

    for node, sim in sorted(results.items(), key=lambda x: x[1]["resilience_score"]):
        summary["per_node"][node] = {
            "resilience_score": sim["resilience_score"],
            "traffic_pct": sim["traffic"]["affected_pct"],
            "critical_patterns": len(sim["patterns"]["critical_no_fallback"]),
        }
        for cp in sim["patterns"]["critical_no_fallback"]:
            summary["critical_dependencies"].append({
                "pattern": cp["pattern_id"],
                "sole_node": node,
                "calls": cp["total_calls"],
            })
        summary["recommendations"].extend(sim["recommendations"])

    # Deduplicate recommendations
    seen = set()
    unique_recs = []
    for r in summary["recommendations"]:
        if r not in seen:
            seen.add(r)
            unique_recs.append(r)
    summary["recommendations"] = unique_recs

    print(json.dumps(summary, indent=2, ensure_ascii=False))


def run_node(node_name):
    """Detailed simulation for one specific node."""
    node = node_name.upper()
    dispatches = load_dispatch_data()
    patterns = load_patterns()
    pattern_map = get_pattern_node_map(patterns)

    # Validate node exists in data
    known_nodes = set(d["node"] for d in dispatches if d["node"])
    if node not in known_nodes:
        print(f"ERROR: Node '{node}' not found in dispatch data.", file=sys.stderr)
        print(f"Available nodes: {', '.join(sorted(known_nodes))}", file=sys.stderr)
        sys.exit(1)

    sim = simulate_node_failure(node, dispatches, pattern_map)
    store_simulation(node, sim["resilience_score"], sim)

    # Pretty-print detailed output
    score = sim["resilience_score"]
    grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D" if score >= 20 else "F"

    print(f"=== FAILOVER SIMULATION: {node} DOWN ===\n")
    print(f"Resilience Score: {score:.1f}/100 (Grade {grade})\n")

    t = sim["traffic"]
    print(f"--- Traffic Impact ---")
    print(f"  Total dispatches:    {t['total_dispatches']}")
    print(f"  Affected dispatches: {t['affected_dispatches']} ({t['affected_pct']}%)")
    print(f"  Orphaned (no route): {t['orphaned_dispatches']}")

    cs = sim["current_stats"]
    print(f"\n--- Current Node Stats ---")
    print(f"  Success rate:   {cs['success_rate']*100:.1f}%")
    print(f"  Avg latency:    {cs['avg_latency_ms']:.0f} ms")

    print(f"\n--- Redistribution Plan ---")
    if sim["redistribution"]:
        for target, detail in sim["redistribution"].items():
            print(f"  -> {target}: +{detail['extra_dispatches']} dispatches "
                  f"(+{detail['load_increase_pct']}% load)")
            print(f"     Est. latency: {detail['estimated_latency_ms']:.0f} ms | "
                  f"Est. success: {detail['estimated_success_rate']*100:.1f}%")
    else:
        print("  No redistribution needed (no traffic on this node)")

    print(f"\n--- Pattern Dependencies ---")
    crit = sim["patterns"]["critical_no_fallback"]
    if crit:
        print(f"  CRITICAL ({len(crit)} patterns with NO fallback):")
        for cp in crit:
            print(f"    - {cp['pattern_id']} ({cp['total_calls']} calls): {cp['reason']}")
    else:
        print(f"  No critical single-point dependencies")
    print(f"  Degraded patterns: {sim['patterns']['degraded_count']}")
    print(f"  Unaffected patterns: {sim['patterns']['unaffected_count']}")

    print(f"\n--- Recommendations ---")
    for i, rec in enumerate(sim["recommendations"], 1):
        print(f"  {i}. {rec}")

    # Also output JSON for programmatic use
    print(f"\n--- JSON ---")
    print(json.dumps(sim, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="Node Failover Simulator — Measure cluster resilience to node failures"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true",
                       help="Simulate all nodes, output JSON summary")
    group.add_argument("--node", type=str, metavar="NODE",
                       help="Detailed simulation for a specific node (M1, M2, M3, OL1)")
    group.add_argument("--stats", action="store_true",
                       help="Show history of past simulations")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.node:
        run_node(args.node)
    elif args.once:
        run_once()


if __name__ == "__main__":
    main()
