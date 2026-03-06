#!/usr/bin/env python3
"""ia_weight_calibrator.py — Calibrateur de poids MAO.

Ajuste les poids des agents base sur performance reelle.

Usage:
    python dev/ia_weight_calibrator.py --once
    python dev/ia_weight_calibrator.py --calibrate
    python dev/ia_weight_calibrator.py --simulate
    python dev/ia_weight_calibrator.py --history
"""
import argparse, json, os, sqlite3, time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "weight_calibrator.db"
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")
CURRENT_WEIGHTS = {"M1": 1.8, "M2": 1.5, "OL1": 1.3, "M3": 1.2}

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS calibrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, agent TEXT,
        current_weight REAL, new_weight REAL, success_rate REAL, avg_latency REAL)""")
    db.commit()
    return db

def collect_stats():
    stats = defaultdict(lambda: {"ok": 0, "fail": 0, "lat": 0})
    if ETOILE_DB.exists():
        try:
            db = sqlite3.connect(str(ETOILE_DB))
            for t in [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
                if "metric" in t.lower():
                    try:
                        for r in db.execute(f"SELECT node, status, latency_ms FROM [{t}] WHERE ts > ?", (time.time()-604800,)).fetchall():
                            n = r[0] or "unknown"
                            stats[n]["ok" if r[1] == "ok" else "fail"] += 1
                            stats[n]["lat"] += (r[2] or 0)
                    except Exception: pass
            db.close()
        except Exception: pass
    return stats

def calibrate():
    db = init_db()
    stats = collect_stats()
    results = []
    for agent, w in CURRENT_WEIGHTS.items():
        s = next((v for k, v in stats.items() if agent.lower() in k.lower()), None)
        if not s or (s["ok"] + s["fail"]) < 3: continue
        total = s["ok"] + s["fail"]
        sr = s["ok"] / total
        al = s["lat"] / total
        perf = sr * 0.7 + max(0, 1 - al/10000) * 0.3
        nw = round(w * 0.8 + perf * 2.0 * 0.2, 2)
        nw = max(0.5, min(2.0, nw))
        results.append({"agent": agent, "current": w, "suggested": nw, "sr": round(sr, 3), "lat": round(al, 1), "delta": round(nw - w, 2)})
        db.execute("INSERT INTO calibrations (ts, agent, current_weight, new_weight, success_rate, avg_latency) VALUES (?,?,?,?,?,?)",
                   (time.time(), agent, w, nw, sr, al))
    db.commit(); db.close()
    return {"ts": datetime.now().isoformat(), "agents": len(results), "adjustments": results}

def main():
    parser = argparse.ArgumentParser(description="IA Weight Calibrator")
    parser.add_argument("--once", "--calibrate", action="store_true", help="Calibrate")
    parser.add_argument("--simulate", action="store_true", help="Simulate")
    parser.add_argument("--apply", action="store_true", help="Apply")
    parser.add_argument("--history", action="store_true", help="History")
    args = parser.parse_args()
    print(json.dumps(calibrate(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
