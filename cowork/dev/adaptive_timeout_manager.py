#!/usr/bin/env python3
"""adaptive_timeout_manager.py - Dynamic timeout for cluster dispatches.

CLI: --once (analyze), --apply (write config), --stats (history)
Stdlib-only (sqlite3, json, argparse).
"""
import argparse, json, sqlite3, sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB
MIN_TO, MAX_TO, DEF_TO, MARGIN = 5, 180, 30, 1.5
NODE_SPEED = {"M1": 1.0, "OL1": 1.2, "M2": 2.5, "M3": 3.0}
TIER = {"classifier":10,"simple":10,"quick":10,"code":30,"system":30,"devops":30,"web":30,"analysis":60,"architecture":60,"creative":60,"reasoning":90,"math":90,"trading":90,"large":90}

def init_db(c):
    c.execute("CREATE TABLE IF NOT EXISTS timeout_configs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, pattern TEXT, node TEXT, recommended_timeout_s REAL, p50_latency_ms REAL, p95_latency_ms REAL, max_latency_ms REAL, sample_count INTEGER, applied INTEGER DEFAULT 0)")
    c.commit()

def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    init_db(c)
    return c

def pct(v, p):
    if not v: return 0
    s = sorted(v)
    return s[max(0, int(len(s)*p/100)-1)]

def analyze():
    if not ETOILE_DB.exists(): return {"error": "etoile.db not found"}
    edb = sqlite3.connect(str(ETOILE_DB), timeout=10)
    edb.row_factory = sqlite3.Row
    rows = edb.execute("SELECT classified_type,node,latency_ms,success FROM agent_dispatch_log WHERE latency_ms>0 ORDER BY id DESC LIMIT 2000").fetchall()
    edb.close()
    g = {}
    for r in rows:
        k = (r["classified_type"] or "?", r["node"] or "?")
        g.setdefault(k, {"l":[],"ok":0,"f":0})
        g[k]["l"].append(r["latency_ms"])
        if r["success"]: g[k]["ok"] += 1
        else: g[k]["f"] += 1
    recs = []
    for (pat,node),d in g.items():
        if len(d["l"])<3: continue
        p50,p95,mx = pct(d["l"],50), pct(d["l"],95), max(d["l"])
        fr = d["f"]/max(d["ok"]+d["f"],1)
        base = TIER.get(pat, DEF_TO)
        nf = NODE_SPEED.get(node, 1.5)
        rec = max((p95/1000)*MARGIN, base*nf)
        if fr>0.3 and p95>base*1000: rec = min(rec*1.5, MAX_TO)
        rec = max(MIN_TO, min(rec, MAX_TO))
        recs.append({"pattern":pat,"node":node,"samples":len(d["l"]),"ok_pct":round((1-fr)*100,1),"p50":round(p50),"p95":round(p95),"max":round(mx),"timeout_s":round(rec,1)})
    recs.sort(key=lambda x:(x["pattern"],x["node"]))
    probs = [r for r in recs if r["ok_pct"]<70 and r["p95"]>30000]
    return {"timestamp":datetime.now().isoformat(),"combos":len(recs),"avg_timeout":round(sum(r["timeout_s"] for r in recs)/max(len(recs),1),1),"problems":probs[:10],"recommendations":recs}

def apply_cfg(recs):
    c = get_db()
    ts = datetime.now().isoformat()
    for r in recs:
        c.execute("INSERT INTO timeout_configs (timestamp,pattern,node,recommended_timeout_s,p50_latency_ms,p95_latency_ms,max_latency_ms,sample_count,applied) VALUES (?,?,?,?,?,?,?,?,1)",(ts,r["pattern"],r["node"],r["timeout_s"],r["p50"],r["p95"],r["max"],r["samples"]))
    c.commit(); c.close()
    return len(recs)

def main():
    p = argparse.ArgumentParser(description="Adaptive Timeout Manager")
    p.add_argument("--once", action="store_true", help="Analyze")
    p.add_argument("--apply", action="store_true", help="Apply")
    p.add_argument("--stats", action="store_true", help="History")
    a = p.parse_args()
    if not any([a.once, a.apply, a.stats]): p.print_help(); sys.exit(1)
    if a.stats:
        c = get_db()
        rows = c.execute("SELECT pattern,node,recommended_timeout_s,p95_latency_ms,timestamp FROM timeout_configs ORDER BY id DESC LIMIT 20").fetchall()
        c.close()
        result = {"history":[dict(r) for r in rows]}
    else:
        data = analyze()
        if "error" in data: print(json.dumps(data)); return
        if a.apply: data["applied"] = apply_cfg(data["recommendations"])
        result = data
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
