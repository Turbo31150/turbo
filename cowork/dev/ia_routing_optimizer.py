#!/usr/bin/env python3
"""ia_routing_optimizer.py — Optimiseur routing IA.

Ameliore le dispatch des requetes vers le bon agent.

Usage:
    python dev/ia_routing_optimizer.py --once
    python dev/ia_routing_optimizer.py --analyze
    python dev/ia_routing_optimizer.py --optimize
    python dev/ia_routing_optimizer.py --deploy
"""
import argparse, json, os, sqlite3, time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "routing_optimizer.db"
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")
CATEGORIES = ["code", "math", "trading", "system", "web", "general"]

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS routing_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, category TEXT,
        agent TEXT, score REAL, samples INTEGER)""")
    db.commit()
    return db

def analyze_routing():
    matrix = defaultdict(lambda: defaultdict(lambda: {"ok": 0, "fail": 0, "lat": 0}))
    if ETOILE_DB.exists():
        try:
            db = sqlite3.connect(str(ETOILE_DB))
            for t in [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
                if "metric" in t.lower():
                    cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])").fetchall()]
                    if "category" in cols and "node" in cols:
                        for r in db.execute(f"SELECT category, node, status FROM [{t}] WHERE ts > ?", (time.time()-604800,)).fetchall():
                            cat, node = r[0] or "general", r[1] or "unknown"
                            matrix[cat][node]["ok" if r[2] == "ok" else "fail"] += 1
            db.close()
        except Exception: pass
    return matrix

def do_optimize():
    db = init_db()
    matrix = analyze_routing()
    recommendations = []
    for cat in CATEGORIES:
        agents = matrix.get(cat, {})
        if not agents:
            recommendations.append({"category": cat, "best": "M1", "reason": "default", "confidence": 0.5})
            continue
        best_agent, best_score = None, -1
        for agent, stats in agents.items():
            total = stats["ok"] + stats["fail"]
            if total < 2: continue
            score = stats["ok"] / total
            if score > best_score:
                best_score, best_agent = score, agent
            db.execute("INSERT INTO routing_scores (ts, category, agent, score, samples) VALUES (?,?,?,?,?)",
                       (time.time(), cat, agent, score, total))
        if best_agent:
            recommendations.append({"category": cat, "best": best_agent, "score": round(best_score, 3), "confidence": min(best_score, 0.95)})
    db.commit(); db.close()
    return {"ts": datetime.now().isoformat(), "categories": len(CATEGORIES), "recommendations": recommendations}

def main():
    parser = argparse.ArgumentParser(description="IA Routing Optimizer")
    parser.add_argument("--once", "--analyze", action="store_true", help="Analyze")
    parser.add_argument("--optimize", action="store_true", help="Optimize")
    parser.add_argument("--test", action="store_true", help="A/B test")
    parser.add_argument("--deploy", action="store_true", help="Deploy")
    args = parser.parse_args()
    print(json.dumps(do_optimize(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
