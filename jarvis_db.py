#!/usr/bin/env python3
"""jarvis_db.py — Helper DB pour jarvis.ps1 → etoile.db"""
import sqlite3, json, sys, os
from datetime import datetime

try:
    from src.config import PATHS
    DB_PATH = str(PATHS["etoile_db"])
except ImportError:
    DB_PATH = os.path.join(os.path.dirname(__file__), "data", "etoile.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def log_query(node, domain, latency_ms, success, routing_source="static", prompt="", response_preview=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO jarvis_queries (timestamp, node, domain, latency_ms, success, routing_source, prompt, response_preview) VALUES (?,?,?,?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), node, domain, int(latency_ms), 1 if success else 0, routing_source, prompt[:200], response_preview[:200])
    )
    conn.commit()
    conn.close()

def get_adaptive_route(domain, min_points=3):
    conn = get_conn()
    rows = conn.execute(
        "SELECT node, COUNT(*) as cnt, AVG(latency_ms) as avg_lat, SUM(success)*1.0/COUNT(*) as success_rate "
        "FROM jarvis_queries WHERE domain=? GROUP BY node HAVING cnt>=?",
        (domain, min_points)
    ).fetchall()
    conn.close()
    if not rows:
        print("null")
        return
    scores = []
    for r in rows:
        speed = max(0, 10 - r["avg_lat"] / 5000)
        final = speed * 0.4 + r["success_rate"] * 10 * 0.6
        scores.append((r["node"], round(final, 2)))
    scores.sort(key=lambda x: x[1], reverse=True)
    print(json.dumps([s[0] for s in scores]))

def log_consensus(query, nodes_queried, nodes_responded, verdict, confidence, details=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO consensus_log (timestamp, query, nodes_queried, nodes_responded, verdict, confidence, details) VALUES (?,?,?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), query[:500], nodes_queried, nodes_responded, verdict, confidence, details[:2000])
    )
    conn.commit()
    conn.close()

def log_health(node, status, model, latency_ms=0):
    conn = get_conn()
    conn.execute(
        "INSERT INTO cluster_health (timestamp, node, status, model, latency_ms) VALUES (?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), node, status, model, int(latency_ms))
    )
    conn.commit()
    conn.close()

def log_metric(agent, metric_type, value, unit=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO metrics (agent, metric_type, value, unit, recorded_at) VALUES (?,?,?,?,?)",
        (agent, metric_type, float(value), unit, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    )
    conn.commit()
    conn.close()

def show_scores(domain=None):
    conn = get_conn()
    where = "WHERE domain=?" if domain else ""
    params = (domain,) if domain else ()
    rows = conn.execute(
        f"SELECT domain, node, COUNT(*) as cnt, CAST(AVG(latency_ms) AS INT) as avg_lat, "
        f"CAST(SUM(success)*100.0/COUNT(*) AS INT) as success_pct "
        f"FROM jarvis_queries {where} GROUP BY domain, node ORDER BY domain, avg_lat", params
    ).fetchall()
    conn.close()
    if not rows:
        print("NO_DATA")
        return
    result = []
    for r in rows:
        speed = max(0, 10 - r["avg_lat"] / 5000)
        final = round(speed * 0.4 + (r["success_pct"] / 10) * 0.6, 2)
        result.append({"domain": r["domain"], "node": r["node"], "count": r["cnt"],
                       "avg_latency": r["avg_lat"], "success_pct": r["success_pct"], "score": final})
    print(json.dumps(result))

def log_json(filepath, node, domain, latency_ms, success):
    """Append to JSON routing log file (legacy sync)."""
    data = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                content = f.read().strip()
                if content:
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        data = parsed
        except (json.JSONDecodeError, ValueError):
            data = []
    entry = {"node": node, "domain": domain, "latency_ms": int(latency_ms),
             "success": success == "1" or success is True, "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
    data.append(entry)
    if len(data) > 500:
        data = data[-500:]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def scenario_route(domain):
    """Get best agent for a domain using scenario_weights + agent_keywords."""
    conn = get_conn()
    # Map domain to scenario
    domain_map = {
        "code": "code_generation", "securite": "critical", "math": "short_answer",
        "raisonnement": "reasoning", "trading": "trading_signal", "web": "web_research",
        "general": "short_answer", "traduction": "short_answer", "systeme": "cmd_systeme",
    }
    scenario = domain_map.get(domain, "short_answer")
    rows = conn.execute(
        "SELECT agent, weight, priority, chain_next FROM scenario_weights WHERE scenario=? ORDER BY priority ASC",
        (scenario,)
    ).fetchall()
    conn.close()
    if not rows:
        print("null")
        return
    result = [{"agent": r["agent"], "weight": r["weight"], "priority": r["priority"], "chain_next": r["chain_next"]} for r in rows]
    print(json.dumps(result))

def get_dominos(trigger_cmd, condition="always"):
    """Get domino chains for a trigger command."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT next_cmd, delay_ms, auto, description FROM domino_chains WHERE trigger_cmd=? AND (condition=? OR condition='always')",
        (trigger_cmd, condition)
    ).fetchall()
    conn.close()
    if not rows:
        print("[]")
        return
    result = [{"next_cmd": r["next_cmd"], "delay_ms": r["delay_ms"], "auto": bool(r["auto"]), "desc": r["description"]} for r in rows]
    print(json.dumps(result))

def update_keyword_hit(agent, keyword):
    """Increment hit count for an agent keyword pair."""
    conn = get_conn()
    conn.execute("UPDATE agent_keywords SET hit_count = hit_count + 1 WHERE agent=? AND keyword=?", (agent, keyword))
    conn.commit()
    conn.close()

def keyword_match(text):
    """Find best agent match based on keywords in text."""
    conn = get_conn()
    words = text.lower().split()
    scores = {}
    for word in words:
        rows = conn.execute(
            "SELECT agent, weight, domain FROM agent_keywords WHERE keyword=?", (word,)
        ).fetchall()
        for r in rows:
            key = r["agent"]
            if key not in scores:
                scores[key] = {"score": 0, "domains": set(), "hits": 0}
            scores[key]["score"] += r["weight"]
            scores[key]["domains"].add(r["domain"])
            scores[key]["hits"] += 1
    conn.close()
    if not scores:
        print("null")
        return
    result = []
    for agent, data in sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True):
        result.append({"agent": agent, "score": round(data["score"], 2), "hits": data["hits"], "domains": list(data["domains"])})
    print(json.dumps(result))

def db_summary():
    """Full summary of all jarvis tables in etoile.db."""
    conn = get_conn()
    tables = {
        "jarvis_queries": "SELECT COUNT(*) FROM jarvis_queries",
        "cluster_health": "SELECT COUNT(*) FROM cluster_health",
        "consensus_log": "SELECT COUNT(*) FROM consensus_log",
        "agent_keywords": "SELECT COUNT(*) FROM agent_keywords",
        "pipeline_dictionary": "SELECT COUNT(*) FROM pipeline_dictionary",
        "scenario_weights": "SELECT COUNT(*) FROM scenario_weights",
        "domino_chains": "SELECT COUNT(*) FROM domino_chains",
        "benchmark_results": "SELECT COUNT(*) FROM benchmark_results",
        "metrics": "SELECT COUNT(*) FROM metrics",
        "map": "SELECT COUNT(*) FROM map",
    }
    result = {}
    for name, query in tables.items():
        try:
            result[name] = conn.execute(query).fetchone()[0]
        except:
            result[name] = 0
    # Top agents by keyword count
    result["agents_keywords"] = {}
    for row in conn.execute("SELECT agent, COUNT(*) as cnt FROM agent_keywords GROUP BY agent ORDER BY cnt DESC"):
        result["agents_keywords"][row[0]] = row[1]
    # Scenarios count
    result["scenarios_count"] = conn.execute("SELECT COUNT(DISTINCT scenario) FROM scenario_weights").fetchone()[0]
    conn.close()
    print(json.dumps(result))

def stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM jarvis_queries").fetchone()[0]
    domains = conn.execute("SELECT COUNT(DISTINCT domain) FROM jarvis_queries").fetchone()[0]
    nodes = conn.execute("SELECT COUNT(DISTINCT node) FROM jarvis_queries").fetchone()[0]
    last = conn.execute("SELECT timestamp FROM jarvis_queries ORDER BY id DESC LIMIT 1").fetchone()
    health_count = conn.execute("SELECT COUNT(*) FROM cluster_health").fetchone()[0]
    consensus_count = conn.execute("SELECT COUNT(*) FROM consensus_log").fetchone()[0]
    conn.close()
    print(json.dumps({
        "total_queries": total, "domains": domains, "nodes_used": nodes,
        "last_query": last[0] if last else None,
        "health_checks": health_count, "consensus_logs": consensus_count
    }))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: jarvis_db.py <command> [args...]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "log_query":
        # node domain latency_ms success routing_source [prompt] [preview]
        log_query(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] == "1",
                  sys.argv[6] if len(sys.argv) > 6 else "static",
                  sys.argv[7] if len(sys.argv) > 7 else "",
                  sys.argv[8] if len(sys.argv) > 8 else "")
    elif cmd == "log_json":
        log_json(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
    elif cmd == "adaptive_route":
        get_adaptive_route(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 3)
    elif cmd == "log_consensus":
        log_consensus(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], float(sys.argv[6]),
                      sys.argv[7] if len(sys.argv) > 7 else "")
    elif cmd == "log_health":
        log_health(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else 0)
    elif cmd == "log_metric":
        log_metric(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else "")
    elif cmd == "scores":
        show_scores(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "stats":
        stats()
    elif cmd == "scenario_route":
        scenario_route(sys.argv[2])
    elif cmd == "dominos":
        get_dominos(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "always")
    elif cmd == "keyword_match":
        keyword_match(" ".join(sys.argv[2:]))
    elif cmd == "hit":
        update_keyword_hit(sys.argv[2], sys.argv[3])
    elif cmd == "summary":
        db_summary()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
