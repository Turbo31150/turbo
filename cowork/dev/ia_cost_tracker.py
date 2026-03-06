#!/usr/bin/env python3
"""ia_cost_tracker.py — Tracker de couts IA.

Mesure consommation tokens cloud, estime couts, alerte budget.

Usage:
    python dev/ia_cost_tracker.py --once
    python dev/ia_cost_tracker.py --track
    python dev/ia_cost_tracker.py --daily
    python dev/ia_cost_tracker.py --budget
"""
import argparse, json, os, sqlite3, time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "cost_tracker.db"
from _paths import ETOILE_DB
COST_RATES = {
    "glm-4.7": 0.0001,
    "qwen3-coder:480b": 0.0004, "minimax-m2.5": 0.0001, "kimi-k2.5": 0.0002,
}
DAILY_BUDGET = 5.0
MONTHLY_BUDGET = 100.0

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS costs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, model TEXT,
        tokens INTEGER, cost_usd REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS daily_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, date TEXT,
        total_tokens INTEGER, total_cost REAL, over_budget INTEGER)""")
    db.commit()
    return db

def estimate_costs():
    usage = defaultdict(int)
    if ETOILE_DB.exists():
        try:
            db = sqlite3.connect(str(ETOILE_DB))
            for t in [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
                if "metric" in t.lower():
                    cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])").fetchall()]
                    if "node" in cols:
                        for r in db.execute(f"SELECT node FROM [{t}] WHERE ts > ?", (time.time()-86400,)).fetchall():
                            usage[r[0] or "unknown"] += 500  # est ~500 tokens/req
            db.close()
        except Exception: pass
    costs = []
    for model, tokens in usage.items():
        rate = next((v for k, v in COST_RATES.items() if k.lower() in model.lower()), 0)
        cost = tokens * rate / 1000
        costs.append({"model": model, "tokens": tokens, "cost_usd": round(cost, 4)})
    return costs

def do_track():
    db = init_db()
    costs = estimate_costs()
    total_tokens = sum(c["tokens"] for c in costs)
    total_cost = sum(c["cost_usd"] for c in costs)
    for c in costs:
        db.execute("INSERT INTO costs (ts, model, tokens, cost_usd) VALUES (?,?,?,?)",
                   (time.time(), c["model"], c["tokens"], c["cost_usd"]))
    over = total_cost > DAILY_BUDGET
    db.execute("INSERT INTO daily_reports (ts, date, total_tokens, total_cost, over_budget) VALUES (?,?,?,?,?)",
               (time.time(), datetime.now().strftime("%Y-%m-%d"), total_tokens, total_cost, int(over)))
    db.commit(); db.close()
    return {
        "ts": datetime.now().isoformat(), "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 4), "daily_budget": DAILY_BUDGET,
        "over_budget": over, "by_model": costs,
    }

def main():
    parser = argparse.ArgumentParser(description="IA Cost Tracker")
    parser.add_argument("--once", "--track", action="store_true", help="Track costs")
    parser.add_argument("--daily", action="store_true", help="Daily report")
    parser.add_argument("--monthly", action="store_true", help="Monthly report")
    parser.add_argument("--budget", action="store_true", help="Budget status")
    args = parser.parse_args()
    print(json.dumps(do_track(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
