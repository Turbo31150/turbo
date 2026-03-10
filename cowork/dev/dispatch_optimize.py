#!/usr/bin/env python3
"""Dispatch Optimizer — analyzes dispatch history and suggests improvements."""
import argparse, json, sqlite3, os
from collections import Counter, defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "etoile.db")

def analyze_dispatches() -> dict:
    results = {"total": 0, "by_node": {}, "slow_queries": [], "suggestions": []}
    if not os.path.exists(DB_PATH):
        results["error"] = "etoile.db not found"
        return results

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT node, model, latency_ms, success FROM dispatch_log ORDER BY created_at DESC LIMIT 500"
        ).fetchall()
    except sqlite3.OperationalError:
        results["error"] = "dispatch_log table not found"
        conn.close()
        return results

    results["total"] = len(rows)
    node_stats = defaultdict(lambda: {"count": 0, "success": 0, "avg_latency": 0, "latencies": []})

    for node, model, latency, success in rows:
        s = node_stats[node]
        s["count"] += 1
        s["success"] += (1 if success else 0)
        s["latencies"].append(latency or 0)

    for node, s in node_stats.items():
        avg_lat = sum(s["latencies"]) / len(s["latencies"]) if s["latencies"] else 0
        success_rate = s["success"] / s["count"] if s["count"] > 0 else 0
        results["by_node"][node] = {
            "count": s["count"],
            "success_rate": round(success_rate, 3),
            "avg_latency_ms": round(avg_lat, 1),
        }
        if success_rate < 0.7:
            results["suggestions"].append(f"Reduce weight for {node} (success: {success_rate:.0%})")
        if avg_lat > 5000:
            results["suggestions"].append(f"Consider lighter model for {node} (avg: {avg_lat:.0f}ms)")

    conn.close()
    return results

def main():
    parser = argparse.ArgumentParser(description="Dispatch routing optimizer")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    analysis = analyze_dispatches()
    if args.json:
        print(json.dumps(analysis, indent=2))
    else:
        print(f"Dispatches analyzed: {analysis['total']}")
        for node, stats in analysis.get("by_node", {}).items():
            print(f"  {node}: {stats['count']} calls, {stats['success_rate']:.0%} success, {stats['avg_latency_ms']}ms avg")
        if analysis.get("suggestions"):
            print("\nSuggestions:")
            for s in analysis["suggestions"]:
                print(f"  - {s}")

if __name__ == "__main__":
    main()
