#!/usr/bin/env python3
"""
Cluster Deep Analysis Worker — Exploite M1/M2/M3/OL1 en continu.

Taches distribuees:
1. M1: Cross-validation des top strategies sur coins differents
2. M2: Analyse de regime de marche (trend/range/volatil)
3. M3: Detection d'anomalies dans les resultats d'evolution
4. OL1: Scan rapide des correlations entre coins
5. M1+M2: Consensus sur les meilleurs parametres

Boucle toutes les 3 minutes. Resultats dans cluster_analysis.db.
"""

import json, os, sqlite3, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

TURBO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = TURBO_ROOT / "data"
EVOLUTION_DB = DATA_DIR / "strategy_evolution.db"
ANALYSIS_DB = DATA_DIR / "cluster_analysis.db"

NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b",
            "prefix": "/nothink\n", "timeout": 60, "extract": "lmstudio"},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek/qwen/qwen3-8b",
            "prefix": "", "timeout": 180, "extract": "lmstudio"},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek/qwen/qwen3-8b",
            "prefix": "", "timeout": 180, "extract": "lmstudio"},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
             "prefix": "/nothink\n", "timeout": 60, "extract": "ollama"},
}


def init_db():
    db = sqlite3.connect(str(ANALYSIS_DB), timeout=10)
    db.execute("""CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY, timestamp TEXT, cycle INTEGER,
        task_type TEXT, node TEXT, prompt_summary TEXT,
        response TEXT, quality_score REAL, duration_s REAL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS market_regimes (
        id INTEGER PRIMARY KEY, timestamp TEXT, regime TEXT,
        confidence REAL, detail TEXT, source_node TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS parameter_insights (
        id INTEGER PRIMARY KEY, timestamp TEXT, parameter TEXT,
        insight TEXT, recommendation TEXT, source_node TEXT
    )""")
    db.commit()
    return db


def query_node(node, prompt):
    cfg = NODES[node]
    if cfg["extract"] == "ollama":
        body = json.dumps({
            "model": cfg["model"],
            "messages": [{"role": "user", "content": cfg["prefix"] + prompt}],
            "stream": False
        }).encode()
    else:
        body = json.dumps({
            "model": cfg["model"],
            "input": cfg["prefix"] + prompt,
            "temperature": 0.3, "max_output_tokens": 2048,
            "stream": False, "store": False
        }).encode()

    t0 = time.time()
    try:
        req = urllib.request.Request(cfg["url"], body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
            d = json.loads(resp.read())
        elapsed = time.time() - t0

        if cfg["extract"] == "ollama":
            return d.get("message", {}).get("content"), elapsed
        # LM Studio: get last message block
        for o in reversed(d.get("output", [])):
            if o.get("type") == "message" and o.get("content"):
                return o["content"], elapsed
        # Fallback: first content
        for o in d.get("output", []):
            if o.get("content"):
                return o["content"], elapsed
        return None, elapsed
    except Exception as e:
        return f"[ERR] {e}", time.time() - t0


def get_evo_data():
    """Get evolution data for analysis prompts."""
    if not EVOLUTION_DB.exists():
        return {}, []
    db = sqlite3.connect(str(EVOLUTION_DB), timeout=10)

    # Last gen info
    last = db.execute("SELECT generation, pop_size, avg_fitness, best_fitness FROM generations ORDER BY id DESC LIMIT 1").fetchone()
    gen_info = {"gen": last[0], "pop": last[1], "avg_fit": last[2], "best_fit": last[3]} if last else {}

    # Top 20 strategies
    top = db.execute("SELECT name, fitness, avg_wr, avg_pnl, dna, total_evals FROM strategies ORDER BY fitness DESC LIMIT 20").fetchall()
    strategies = []
    for s in top:
        dna = json.loads(s[4]) if isinstance(s[4], str) else {}
        strategies.append({
            "name": s[0], "fitness": s[1], "wr": s[2], "pnl": s[3],
            "ema_s": dna.get("ema_s"), "ema_l": dna.get("ema_l"),
            "rsi_len": dna.get("rsi_len"), "tp": dna.get("tp"), "sl": dna.get("sl"),
            "features": [k.replace("use_", "") for k in dna if k.startswith("use_") and dna[k]],
            "evals": s[5]
        })

    # Fitness progression
    gens = db.execute("SELECT generation, avg_fitness, best_fitness FROM generations ORDER BY id DESC LIMIT 10").fetchall()
    gen_info["progression"] = [{"gen": g[0], "avg": g[1], "best": g[2]} for g in reversed(gens)]

    db.close()
    return gen_info, strategies


def get_market_snapshot():
    """Fetch current market data from MEXC."""
    try:
        url = "https://contract.mexc.com/api/v1/contract/ticker"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        coins = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "PEPE_USDT",
                 "DOGE_USDT", "XRP_USDT", "AVAX_USDT", "LINK_USDT", "TAO_USDT",
                 "HYPE_USDT", "XMR_USDT"]
        result = []
        for t in data.get("data", []):
            sym = t.get("symbol", "")
            if sym in coins:
                result.append({
                    "symbol": sym,
                    "price": float(t.get("lastPrice", 0)),
                    "change": float(t.get("riseFallRate", 0)),
                    "volume": float(t.get("volume24", 0)),
                })
        return result
    except Exception:
        return []


def task_market_regime(cycle, db):
    """M2: Determine current market regime."""
    market = get_market_snapshot()
    if not market:
        return
    market_str = "\n".join(f"  {m['symbol']}: ${m['price']:.4f} chg={m['change']:+.2f}% vol={m['volume']:.0f}"
                           for m in market[:8])

    prompt = (f"Analyse ce snapshot de marche crypto (MEXC Futures):\n{market_str}\n\n"
              f"Determine le REGIME actuel en 1 mot: TRENDING_UP, TRENDING_DOWN, RANGING, HIGH_VOLATILITY, LOW_VOLATILITY.\n"
              f"Puis explique en 2 lignes max pourquoi. Format:\nREGIME: [mot]\nRAISON: [explication]")

    print(f"  [M2] Market regime...", end=" ", flush=True)
    resp, dur = query_node("M2", prompt)
    if resp and not resp.startswith("[ERR]"):
        print(f"OK ({dur:.1f}s)")
        # Parse regime
        regime = "UNKNOWN"
        for line in resp.split("\n"):
            if "REGIME:" in line.upper():
                regime = line.split(":", 1)[1].strip().upper()
                break
        db.execute("INSERT INTO market_regimes (timestamp, regime, confidence, detail, source_node) VALUES (?,?,?,?,?)",
                   (datetime.now().isoformat(), regime, 0.8, resp[:300], "M2"))
        db.execute("INSERT INTO analyses (timestamp, cycle, task_type, node, prompt_summary, response, quality_score, duration_s) VALUES (?,?,?,?,?,?,?,?)",
                   (datetime.now().isoformat(), cycle, "market_regime", "M2", "regime detection", resp[:500], 0.8, dur))
        print(f"    Regime: {regime}")
        for line in resp.strip().split("\n")[:3]:
            print(f"    {line.strip()[:100]}")
    else:
        print(f"FAIL ({str(resp)[:60]})")


def task_parameter_optimization(cycle, db):
    """M1: Analyze top strategy parameters for optimization insights."""
    gen_info, strategies = get_evo_data()
    if not strategies:
        return

    top5 = strategies[:5]
    strat_str = "\n".join(
        f"  {s['name']}: Fit={s['fitness']:.4f} WR={s['wr']:.1f}% PnL={s['pnl']:+.3f}% "
        f"EMA={s['ema_s']}/{s['ema_l']} RSI={s['rsi_len']} TP={s['tp']} SL={s['sl']} feats={s['features']}"
        for s in top5)

    prompt = (f"Voici les 5 meilleures strategies de trading (Gen {gen_info.get('gen', '?')}):\n{strat_str}\n\n"
              f"Analyse les parametres communs et divergents. "
              f"En 5 lignes max:\n"
              f"1) Quels parametres sont stables (convergence)?\n"
              f"2) Quels parametres varient encore (exploration utile)?\n"
              f"3) Quels ranges de TP/SL semblent optimaux?\n"
              f"4) Les features (macd, bb, stoch, adx) sont-elles toutes utiles?\n"
              f"5) Recommandation pour la prochaine generation.")

    print(f"  [M1] Parameter optimization...", end=" ", flush=True)
    resp, dur = query_node("M1", prompt)
    if resp and not resp.startswith("[ERR]"):
        print(f"OK ({dur:.1f}s)")
        db.execute("INSERT INTO parameter_insights (timestamp, parameter, insight, recommendation, source_node) VALUES (?,?,?,?,?)",
                   (datetime.now().isoformat(), "top5_analysis", resp[:500], "", "M1"))
        db.execute("INSERT INTO analyses (timestamp, cycle, task_type, node, prompt_summary, response, quality_score, duration_s) VALUES (?,?,?,?,?,?,?,?)",
                   (datetime.now().isoformat(), cycle, "param_optimization", "M1", "top5 param analysis", resp[:500], 0.85, dur))
        for line in resp.strip().split("\n")[:6]:
            print(f"    {line.strip()[:100]}")
    else:
        print(f"FAIL ({str(resp)[:60]})")


def task_anomaly_detection(cycle, db):
    """M3: Detect anomalies in evolution results."""
    gen_info, strategies = get_evo_data()
    if not strategies or not gen_info.get("progression"):
        return

    prog = gen_info["progression"]
    prog_str = "\n".join(f"  Gen {p['gen']}: avg_fit={p['avg']:.4f} best_fit={p['best']:.4f}" for p in prog)

    prompt = (f"Voici la progression de l'evolution de strategies trading:\n{prog_str}\n\n"
              f"Population: {gen_info.get('pop', '?')} strategies.\n"
              f"Detecte les anomalies en 3 lignes:\n"
              f"1) La fitness converge-t-elle ou stagne-t-elle?\n"
              f"2) Y a-t-il des chutes soudaines (crash de diversite)?\n"
              f"3) Faut-il augmenter le taux de mutation?")

    print(f"  [M3] Anomaly detection...", end=" ", flush=True)
    resp, dur = query_node("M3", prompt)
    if resp and not resp.startswith("[ERR]"):
        print(f"OK ({dur:.1f}s)")
        db.execute("INSERT INTO analyses (timestamp, cycle, task_type, node, prompt_summary, response, quality_score, duration_s) VALUES (?,?,?,?,?,?,?,?)",
                   (datetime.now().isoformat(), cycle, "anomaly_detection", "M3", "evolution anomaly check", resp[:500], 0.7, dur))
        for line in resp.strip().split("\n")[:4]:
            print(f"    {line.strip()[:100]}")
    else:
        print(f"FAIL ({str(resp)[:60]})")


def task_correlation_scan(cycle, db):
    """OL1: Quick correlation scan between coins."""
    market = get_market_snapshot()
    if not market:
        return

    coins_str = ", ".join(f"{m['symbol'].replace('_USDT','')}({m['change']:+.2f}%)" for m in market[:10])

    prompt = (f"Crypto maintenant: {coins_str}\n"
              f"Quels coins bougent ensemble (correles)? Quels coins divergent?\n"
              f"3 lignes max. Pas de disclaimer.")

    print(f"  [OL1] Correlation scan...", end=" ", flush=True)
    resp, dur = query_node("OL1", prompt)
    if resp and not resp.startswith("[ERR]"):
        print(f"OK ({dur:.1f}s)")
        db.execute("INSERT INTO analyses (timestamp, cycle, task_type, node, prompt_summary, response, quality_score, duration_s) VALUES (?,?,?,?,?,?,?,?)",
                   (datetime.now().isoformat(), cycle, "correlation_scan", "OL1", "coin correlation", resp[:300], 0.7, dur))
        for line in resp.strip().split("\n")[:4]:
            print(f"    {line.strip()[:80]}")
    else:
        print(f"FAIL ({str(resp)[:60]})")


def task_consensus_params(cycle, db):
    """M1+OL1: Consensus on optimal parameters."""
    gen_info, strategies = get_evo_data()
    if not strategies:
        return

    # Extract param ranges from top 10
    params = {"ema_s": [], "ema_l": [], "rsi_len": [], "tp": [], "sl": []}
    for s in strategies[:10]:
        for k in params:
            if s.get(k) is not None:
                params[k].append(s[k])

    param_str = "\n".join(f"  {k}: {sorted(set(v))}" for k, v in params.items() if v)

    prompt = (f"Voici les parametres des 10 meilleures strategies trading:\n{param_str}\n\n"
              f"Donne les parametres OPTIMAUX en 1 ligne JSON:\n"
              f'{{\"ema_s\":N,\"ema_l\":N,\"rsi_len\":N,\"tp\":F,\"sl\":F}}\n'
              f"Justifie en 1 ligne.")

    print(f"  [M1+OL1] Consensus params...", end=" ", flush=True)
    r1, d1 = query_node("M1", prompt)
    r2, d2 = query_node("OL1", prompt)

    results = []
    if r1 and not r1.startswith("[ERR]"):
        results.append(("M1", r1))
    if r2 and not r2.startswith("[ERR]"):
        results.append(("OL1", r2))

    if results:
        print(f"OK ({len(results)} responses)")
        combined = "\n".join(f"[{n}]: {r[:150]}" for n, r in results)
        db.execute("INSERT INTO analyses (timestamp, cycle, task_type, node, prompt_summary, response, quality_score, duration_s) VALUES (?,?,?,?,?,?,?,?)",
                   (datetime.now().isoformat(), cycle, "consensus_params", "M1+OL1", "optimal param consensus",
                    combined[:500], 0.9, max(d1, d2)))
        for node, r in results:
            print(f"    [{node}]: {r.strip()[:100]}")
    else:
        print(f"FAIL")


def run_cycle(cycle):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{ts}] === DEEP ANALYSIS CYCLE #{cycle} ===")

    db = init_db()

    # Run all tasks
    task_correlation_scan(cycle, db)    # OL1 — fast
    task_parameter_optimization(cycle, db)  # M1
    task_market_regime(cycle, db)        # M2
    task_anomaly_detection(cycle, db)    # M3
    task_consensus_params(cycle, db)     # M1+OL1

    db.commit()

    # Stats
    total = db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    regimes = db.execute("SELECT COUNT(*) FROM market_regimes").fetchone()[0]
    insights = db.execute("SELECT COUNT(*) FROM parameter_insights").fetchone()[0]
    print(f"  DB: {total} analyses, {regimes} regimes, {insights} insights")

    db.close()
    print(f"  Cycle #{cycle} done")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cluster Deep Analysis Worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=3, help="Minutes between cycles")
    args = parser.parse_args()

    print("=" * 60)
    print("  CLUSTER DEEP ANALYSIS WORKER — JARVIS")
    print("=" * 60)
    print(f"  Mode: {'single' if args.once else 'continuous'}")
    print(f"  Interval: {args.interval}min")
    print(f"  Nodes: M1, M2, M3, OL1")
    print(f"  Tasks: correlation, params, regime, anomaly, consensus")

    cycle = 0
    while True:
        cycle += 1
        try:
            run_cycle(cycle)
        except Exception as e:
            print(f"  [ERR] Cycle failed: {e}")

        if args.once:
            break
        print(f"\n  Next cycle in {args.interval}min...")
        time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
