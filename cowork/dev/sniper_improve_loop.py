"""
JARVIS Sniper Improvement Loop — Continuous optimization via full cluster.

Runs 1000 cycles of:
1. Analyze current signal_tracker performance (win rate, PnL)
2. Ask cluster nodes for parameter suggestions
3. Apply best improvements dynamically
4. Log results for comparison

Usage:
  python cowork/dev/sniper_improve_loop.py --cycles 1000
"""

import json
import os
import sys
import time
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TURBO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = TURBO_ROOT / "data" / "sniper_scan.db"
IMPROVE_DB = TURBO_ROOT / "data" / "sniper_improve.db"

# Full cluster
CLUSTER = [
    {"id": "gpt-oss", "url": "http://127.0.0.1:11434/api/chat", "model": "gpt-oss:120b-cloud", "type": "ollama", "weight": 1.9},
    {"id": "M1", "url": "http://127.0.0.1:1234/v1/chat/completions", "model": "qwen3-8b", "type": "lmstudio", "weight": 1.8},
    {"id": "devstral", "url": "http://127.0.0.1:11434/api/chat", "model": "devstral-2:123b-cloud", "type": "ollama", "weight": 1.5},
    {"id": "M2", "url": "http://192.168.1.26:1234/v1/chat/completions", "model": "deepseek-coder-v2-lite-instruct", "type": "lmstudio", "weight": 1.4},
    {"id": "OL1", "url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b", "type": "ollama", "weight": 1.3},
    {"id": "M3", "url": "http://192.168.1.113:1234/v1/chat/completions", "model": "mistral-7b-instruct-v0.3", "type": "lmstudio", "weight": 1.0},
]

import urllib.request

def http_post(url, data, timeout=60, headers=None):
    body = json.dumps(data).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def init_improve_db():
    IMPROVE_DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(IMPROVE_DB))
    c.executescript("""
        CREATE TABLE IF NOT EXISTS improve_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            cycle INTEGER,
            total_signals INTEGER,
            tp1_rate REAL, tp2_rate REAL, tp3_rate REAL, sl_rate REAL,
            avg_pnl REAL, avg_score REAL,
            cluster_suggestions TEXT,
            improvements_applied TEXT,
            duration_s REAL
        );
        CREATE TABLE IF NOT EXISTS param_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            param_name TEXT,
            old_value REAL,
            new_value REAL,
            reason TEXT,
            suggested_by TEXT
        );
    """)
    c.close()


def get_performance_stats():
    """Get current signal tracker performance stats."""
    try:
        db = sqlite3.connect(str(DB_PATH))
        total = db.execute("SELECT COUNT(*) FROM signal_tracker").fetchone()[0]
        if total == 0:
            db.close()
            return None

        closed = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status != 'OPEN'").fetchone()[0]
        tp1 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE tp1_hit=1").fetchone()[0]
        tp2 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE tp2_hit=1").fetchone()[0]
        tp3 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE tp3_hit=1").fetchone()[0]
        sl = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE sl_hit=1").fetchone()[0]
        avg_pnl = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE status != 'OPEN'").fetchone()[0] or 0
        avg_score = db.execute("SELECT AVG(score) FROM signal_tracker").fetchone()[0] or 0

        # Recent signals (last 50)
        recent = db.execute(
            "SELECT symbol, direction, score, pnl_pct, tp1_hit, sl_hit, validations, status "
            "FROM signal_tracker ORDER BY id DESC LIMIT 50"
        ).fetchall()

        # Direction bias
        longs = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE direction='LONG'").fetchone()[0]
        shorts = total - longs
        long_win = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE direction='LONG' AND tp1_hit=1").fetchone()[0]
        short_win = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE direction='SHORT' AND tp1_hit=1").fetchone()[0]

        # Score distribution
        high_score = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE score >= 85").fetchone()[0]
        high_tp1 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE score >= 85 AND tp1_hit=1").fetchone()[0]
        low_score = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE score < 85 AND score >= 70").fetchone()[0]
        low_tp1 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE score < 85 AND score >= 70 AND tp1_hit=1").fetchone()[0]

        # Top patterns in winning signals
        winning_patterns = db.execute(
            "SELECT ss.pattern FROM scan_signals ss "
            "JOIN signal_tracker st ON ss.symbol = st.symbol AND ss.direction = st.direction "
            "WHERE st.tp1_hit = 1 ORDER BY st.id DESC LIMIT 30"
        ).fetchall()

        db.close()
        return {
            "total": total, "closed": closed,
            "tp1": tp1, "tp2": tp2, "tp3": tp3, "sl": sl,
            "tp1_rate": tp1 / total * 100 if total > 0 else 0,
            "sl_rate": sl / total * 100 if total > 0 else 0,
            "avg_pnl": avg_pnl, "avg_score": avg_score,
            "longs": longs, "shorts": shorts,
            "long_win_rate": long_win / longs * 100 if longs > 0 else 0,
            "short_win_rate": short_win / shorts * 100 if shorts > 0 else 0,
            "high_score_tp1": high_tp1 / high_score * 100 if high_score > 0 else 0,
            "low_score_tp1": low_tp1 / low_score * 100 if low_score > 0 else 0,
            "recent": recent,
            "winning_patterns": [r[0] for r in winning_patterns if r[0]],
        }
    except Exception as e:
        log(f"  Stats error: {e}")
        return None


def query_node(node, prompt):
    """Query a single cluster node."""
    import re
    try:
        if node["type"] == "ollama":
            resp = http_post(node["url"], {
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False
            }, timeout=90)
            text = resp.get("message", {}).get("content", "")
        else:
            resp = http_post(node["url"], {
                "model": node["model"],
                "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}],
                "temperature": 0.3, "max_tokens": 1024, "stream": False
            }, timeout=60)
            choices = resp.get("choices", [])
            text = choices[0]["message"]["content"] if choices else ""
        text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
        return {"node": node["id"], "text": text, "weight": node["weight"]}
    except Exception as e:
        return {"node": node["id"], "text": "", "error": str(e), "weight": node["weight"]}


def ask_cluster_improvements(stats):
    """Ask all cluster nodes for improvement suggestions based on performance data."""
    prompt = f"""Tu es un expert en trading algorithmique. Voici les stats du scanner JARVIS Sniper:

PERFORMANCE ACTUELLE:
- Total signaux: {stats['total']} | Fermes: {stats['closed']}
- TP1 touche: {stats['tp1']} ({stats['tp1_rate']:.1f}%) | SL touche: {stats['sl']} ({stats['sl_rate']:.1f}%)
- PnL moyen: {stats['avg_pnl']:+.2f}% | Score moyen: {stats['avg_score']:.0f}
- LONG win rate: {stats['long_win_rate']:.1f}% | SHORT win rate: {stats['short_win_rate']:.1f}%
- Score>=85 TP1 rate: {stats['high_score_tp1']:.1f}% | Score 70-85 TP1 rate: {stats['low_score_tp1']:.1f}%

PARAMETRES ACTUELS:
- min_move realtime: 0.4% en 30s
- Score min alerte: 75 (realtime) / 85 (sniper)
- Min validations: 3
- TP1: 0.6x ATR | TP2: 1.2x ATR | TP3: 2.0x ATR | SL: 1.0x ATR (realtime)
- Cooldown: 5 min par coin
- Indicateurs: BB squeeze, Volume ratio, RSI, EMA stack, ADX, VWAP, Consolidation, Order book, Momentum accel, Volume climax, Big candle, Hammer/Star, MTF 5min+15min, Momentum streak

Reponds UNIQUEMENT en JSON avec cette structure:
{{
  "analysis": "resume en 1 ligne",
  "improvements": [
    {{"param": "nom_param", "current": valeur, "suggested": valeur, "reason": "pourquoi"}}
  ],
  "priority": "HIGH/MEDIUM/LOW",
  "confidence": 0.0-1.0
}}"""

    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(query_node, node, prompt): node for node in CLUSTER}
        for f in as_completed(futs, timeout=100):
            try:
                r = f.result()
                if r.get("text"):
                    results.append(r)
            except Exception:
                pass
    return results


def parse_suggestion(text):
    """Extract JSON from cluster node response."""
    try:
        # Find JSON block
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return None


def weighted_consensus_improvements(cluster_responses):
    """Build consensus from all cluster suggestions using weighted voting."""
    all_improvements = {}  # param -> list of (suggested_value, weight, reason)

    for resp in cluster_responses:
        suggestion = parse_suggestion(resp["text"])
        if not suggestion or "improvements" not in suggestion:
            continue
        weight = resp["weight"]
        for imp in suggestion.get("improvements", []):
            param = imp.get("param", "")
            if not param:
                continue
            if param not in all_improvements:
                all_improvements[param] = []
            all_improvements[param].append({
                "value": imp.get("suggested"),
                "weight": weight,
                "reason": imp.get("reason", ""),
                "node": resp["node"],
            })

    # For each param, take weighted average if numeric, or majority vote
    consensus = []
    for param, suggestions in all_improvements.items():
        if len(suggestions) < 2:
            continue  # Need at least 2 nodes to agree
        total_weight = sum(s["weight"] for s in suggestions)
        # Check if values are numeric
        numeric = all(isinstance(s["value"], (int, float)) for s in suggestions if s["value"] is not None)
        if numeric:
            weighted_val = sum(s["value"] * s["weight"] for s in suggestions if s["value"] is not None) / total_weight
            consensus.append({
                "param": param,
                "suggested": round(weighted_val, 4),
                "confidence": total_weight / sum(n["weight"] for n in CLUSTER),
                "nodes": [s["node"] for s in suggestions],
                "reason": suggestions[0]["reason"],
            })
        else:
            # Take most weighted suggestion
            suggestions.sort(key=lambda s: s["weight"], reverse=True)
            consensus.append({
                "param": param,
                "suggested": suggestions[0]["value"],
                "confidence": suggestions[0]["weight"] / sum(n["weight"] for n in CLUSTER),
                "nodes": [s["node"] for s in suggestions],
                "reason": suggestions[0]["reason"],
            })

    consensus.sort(key=lambda c: c["confidence"], reverse=True)
    return consensus


def apply_safe_improvements(consensus, stats):
    """Apply improvements that are safe (within bounds) and high confidence."""
    applied = []
    # Define safe bounds for each tunable parameter
    BOUNDS = {
        "min_move": (0.2, 1.0),
        "min_score_realtime": (60, 90),
        "min_score_sniper": (75, 95),
        "min_validations": (2, 5),
        "tp1_mult": (0.3, 1.5),
        "tp2_mult": (0.8, 3.0),
        "tp3_mult": (1.5, 5.0),
        "sl_mult": (0.5, 2.5),
        "cooldown_s": (120, 600),
    }

    db = sqlite3.connect(str(IMPROVE_DB))
    for imp in consensus:
        param = imp["param"]
        if param not in BOUNDS:
            continue
        lo, hi = BOUNDS[param]
        val = imp["suggested"]
        if not isinstance(val, (int, float)):
            continue
        val = max(lo, min(hi, val))  # Clamp to safe range
        if imp["confidence"] < 0.3:
            continue  # Not enough consensus

        # Log the change
        db.execute(
            "INSERT INTO param_history (param_name, old_value, new_value, reason, suggested_by) VALUES (?,?,?,?,?)",
            (param, None, val, imp["reason"], ",".join(imp["nodes"]))
        )
        applied.append({"param": param, "value": val, "confidence": imp["confidence"]})
        log(f"  APPLY: {param} = {val} (conf={imp['confidence']:.2f}, by {','.join(imp['nodes'])})")

    db.commit()
    db.close()
    return applied


def run_improvement_cycle(cycle_num):
    """Run a single improvement cycle."""
    t0 = time.time()
    log(f"=== IMPROVE CYCLE {cycle_num} ===")

    # 1. Get current performance
    stats = get_performance_stats()
    if not stats:
        log("  No performance data yet — skipping")
        return None

    log(f"  Stats: {stats['total']} signals, TP1={stats['tp1_rate']:.1f}%, SL={stats['sl_rate']:.1f}%, PnL={stats['avg_pnl']:+.2f}%")

    # 2. Ask cluster for improvements
    log(f"  Querying full cluster (6 nodes)...")
    responses = ask_cluster_improvements(stats)
    log(f"  {len(responses)} cluster responses received")

    if not responses:
        log("  No cluster responses — skipping")
        return None

    # 3. Build weighted consensus
    consensus = weighted_consensus_improvements(responses)
    log(f"  {len(consensus)} consensus improvements identified")

    # 4. Apply safe improvements
    applied = apply_safe_improvements(consensus, stats)

    # 5. Save cycle results
    duration = time.time() - t0
    try:
        db = sqlite3.connect(str(IMPROVE_DB))
        db.execute(
            "INSERT INTO improve_cycles (cycle, total_signals, tp1_rate, tp2_rate, tp3_rate, sl_rate, "
            "avg_pnl, avg_score, cluster_suggestions, improvements_applied, duration_s) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (cycle_num, stats["total"], stats["tp1_rate"],
             stats["tp2"] / stats["total"] * 100 if stats["total"] > 0 else 0,
             stats["tp3"] / stats["total"] * 100 if stats["total"] > 0 else 0,
             stats["sl_rate"], stats["avg_pnl"], stats["avg_score"],
             json.dumps([{"node": r["node"], "text": r["text"][:200]} for r in responses]),
             json.dumps(applied),
             duration)
        )
        db.commit()
        db.close()
    except Exception as e:
        log(f"  DB save error: {e}")

    log(f"  Cycle {cycle_num} done in {duration:.1f}s — {len(applied)} improvements applied")
    return {"cycle": cycle_num, "applied": applied, "stats": stats, "duration": duration}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Sniper Improvement Loop")
    parser.add_argument("--cycles", type=int, default=1000, help="Number of improvement cycles")
    parser.add_argument("--interval", type=int, default=180, help="Seconds between cycles (default 180)")
    args = parser.parse_args()

    init_improve_db()
    log(f"SNIPER IMPROVE LOOP — {args.cycles} cycles, interval {args.interval}s")
    log(f"  Cluster: {', '.join(n['id'] for n in CLUSTER)} ({len(CLUSTER)} nodes)")

    total_applied = 0
    for cycle in range(1, args.cycles + 1):
        try:
            result = run_improvement_cycle(cycle)
            if result and result.get("applied"):
                total_applied += len(result["applied"])

            # Progress report every 10 cycles
            if cycle % 10 == 0:
                log(f"  PROGRESS: {cycle}/{args.cycles} cycles | {total_applied} total improvements applied")

        except Exception as e:
            log(f"  Cycle {cycle} error: {e}")

        # Wait before next cycle (but not after last)
        if cycle < args.cycles:
            time.sleep(args.interval)

    log(f"IMPROVE LOOP COMPLETE — {args.cycles} cycles, {total_applied} improvements applied")


if __name__ == "__main__":
    main()
