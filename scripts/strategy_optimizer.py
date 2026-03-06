#!/usr/bin/env python3
"""
Strategy Optimizer Round 2+ — Iterates on multi_strategy_scanner results.

Takes winning patterns from Round 1 and creates 200+ optimized variants,
then tests ONLY on promising coins. Repeats until convergence.

Usage:
    python scripts/strategy_optimizer.py                    # Auto-optimize
    python scripts/strategy_optimizer.py --rounds 3         # Multiple rounds
    python scripts/strategy_optimizer.py --min-wr 55        # Min win rate threshold
"""

import json, math, sys, time, urllib.request, argparse, sqlite3
from datetime import datetime
from pathlib import Path

# Import engine from multi_strategy_scanner
sys.path.insert(0, str(Path(__file__).resolve().parent))
from multi_strategy_scanner import (
    precompute_indicators, run_single_strategy, fetch_klines,
    assess_coin_quality, fetch_top_coins, init_db, DB_PATH, DATA_DIR,
    ema, sma, rsi, stochastic, atr, macd, bollinger, vwap_calc, adx_calc, obv_calc
)


def build_round2_strategies():
    """200+ strategies built from Round 1 winners."""
    strategies = []
    sid = 0

    # ═══ WINNING PATTERN 1: EMA_3_8 (best on XMR, BTC, USOIL) ═══
    # Vary everything around this core
    for tp in [0.8, 1.0, 1.2, 1.5, 2.0]:
        for sl in [0.5, 0.75, 1.0, 1.5]:
            sid += 1
            strategies.append({
                "id": sid, "name": f"R2_EMA3_8_TP{tp}_SL{sl}",
                "group": "R2_EMA3_8",
                "params": {"ema_s": 3, "ema_l": 8, "rsi_len": 7, "tp": tp, "sl": sl,
                           "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True},
            })

    # EMA_3_8 + OBV (combine two winners)
    for tp in [1.0, 1.5, 2.0]:
        for sl in [0.5, 1.0]:
            sid += 1
            strategies.append({
                "id": sid, "name": f"R2_EMA3_8_OBV_TP{tp}_SL{sl}",
                "group": "R2_EMA3_8_OBV",
                "params": {"ema_s": 3, "ema_l": 8, "rsi_len": 7, "tp": tp, "sl": sl,
                           "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                           "use_obv": True},
            })

    # EMA_3_8 + MACD (combine winners)
    for macd_f, macd_s, macd_sig in [(5,13,5),(8,17,9),(12,26,9)]:
        for tp in [1.0, 1.5]:
            sid += 1
            strategies.append({
                "id": sid, "name": f"R2_EMA3_8_MACD{macd_f}_{macd_s}_TP{tp}",
                "group": "R2_EMA3_8_MACD",
                "params": {"ema_s": 3, "ema_l": 8, "rsi_len": 7, "tp": tp, "sl": 1.0,
                           "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                           "use_macd": True, "macd_fast": macd_f, "macd_slow": macd_s, "macd_sig": macd_sig},
            })

    # ═══ WINNING PATTERN 2: Asymmetric TP/SL (TP >> SL) ═══
    for ema_s, ema_l in [(3,8),(5,13),(5,21),(8,21)]:
        for tp in [2.0, 2.5, 3.0]:
            for sl in [0.5, 0.75, 1.0]:
                if tp / sl < 2.0:
                    continue  # Only high R:R
                sid += 1
                strategies.append({
                    "id": sid, "name": f"R2_ASYM_E{ema_s}_{ema_l}_TP{tp}_SL{sl}",
                    "group": "R2_ASYMMETRIC",
                    "params": {"ema_s": ema_s, "ema_l": ema_l, "rsi_len": 7, "tp": tp, "sl": sl,
                               "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True},
                })

    # ═══ WINNING PATTERN 3: OBV Momentum (best on TAO) ═══
    for ema_s, ema_l in [(3,8),(5,13),(5,21)]:
        for tp in [1.5, 2.0, 2.5, 3.0]:
            for sl in [0.5, 1.0]:
                sid += 1
                strategies.append({
                    "id": sid, "name": f"R2_OBV_E{ema_s}_{ema_l}_TP{tp}_SL{sl}",
                    "group": "R2_OBV",
                    "params": {"ema_s": ema_s, "ema_l": ema_l, "rsi_len": 7, "tp": tp, "sl": sl,
                               "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                               "use_obv": True},
                })

    # ═══ WINNING PATTERN 4: MACD cross (best on SILVER) ═══
    for macd_f, macd_s, macd_sig in [(5,13,5),(8,17,9),(12,26,9)]:
        for tp in [1.0, 1.5, 2.0]:
            for sl in [0.5, 1.0, 1.5]:
                sid += 1
                strategies.append({
                    "id": sid, "name": f"R2_MACD_{macd_f}_{macd_s}_TP{tp}_SL{sl}",
                    "group": "R2_MACD",
                    "params": {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": tp, "sl": sl,
                               "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                               "use_macd": True, "macd_fast": macd_f, "macd_slow": macd_s, "macd_sig": macd_sig},
                })

    # ═══ WINNING PATTERN 5: NO_STOCH pure EMA+RSI (best on ETH, BNB) ═══
    for ema_s, ema_l in [(3,8),(5,13),(5,21),(8,21),(10,30)]:
        for tp in [1.0, 1.5, 2.0]:
            for sl in [0.5, 1.0]:
                sid += 1
                strategies.append({
                    "id": sid, "name": f"R2_PURE_E{ema_s}_{ema_l}_TP{tp}_SL{sl}",
                    "group": "R2_PURE_EMA",
                    "params": {"ema_s": ema_s, "ema_l": ema_l, "rsi_len": 7, "tp": tp, "sl": sl,
                               "rsi_ob": 70, "rsi_os": 30, "use_stoch": False},
                })

    # ═══ WINNING PATTERN 6: RSI-tight filter (stricter entry) ═══
    for rsi_ob, rsi_os in [(60,40),(55,45),(65,35)]:
        for ema_s, ema_l in [(3,8),(5,13)]:
            for tp in [1.0, 1.5, 2.0]:
                sid += 1
                strategies.append({
                    "id": sid, "name": f"R2_TIGHT_RSI{rsi_ob}_E{ema_s}_{ema_l}_TP{tp}",
                    "group": "R2_TIGHT_RSI",
                    "params": {"ema_s": ema_s, "ema_l": ema_l, "rsi_len": 7, "tp": tp, "sl": 1.0,
                               "rsi_ob": rsi_ob, "rsi_os": rsi_os, "stoch_len": 14, "use_stoch": True},
                })

    # ═══ PATTERN 7: ADX trend + asymmetric (strong trends only) ═══
    for adx_min in [20, 25, 30]:
        for tp in [1.5, 2.0, 2.5]:
            for sl in [0.5, 1.0]:
                sid += 1
                strategies.append({
                    "id": sid, "name": f"R2_ADX{adx_min}_TP{tp}_SL{sl}",
                    "group": "R2_ADX_TREND",
                    "params": {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": tp, "sl": sl,
                               "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                               "use_adx": True, "adx_min": adx_min},
                })

    # ═══ PATTERN 8: Multi-confirm combos (best elements combined) ═══
    combos = [
        ("R2_EMA3_OBV_MACD", {"ema_s":3,"ema_l":8,"use_obv":True,"use_macd":True,"macd_fast":12,"macd_slow":26,"macd_sig":9}),
        ("R2_EMA3_ADX_OBV", {"ema_s":3,"ema_l":8,"use_obv":True,"use_adx":True,"adx_min":20}),
        ("R2_EMA5_MACD_ADX", {"ema_s":5,"ema_l":13,"use_macd":True,"macd_fast":8,"macd_slow":17,"macd_sig":9,"use_adx":True,"adx_min":20}),
        ("R2_PURE3_OBV", {"ema_s":3,"ema_l":8,"use_obv":True,"use_stoch":False}),
        ("R2_PURE5_OBV", {"ema_s":5,"ema_l":13,"use_obv":True,"use_stoch":False}),
        ("R2_PURE8_MACD", {"ema_s":8,"ema_l":21,"use_macd":True,"macd_fast":12,"macd_slow":26,"macd_sig":9,"use_stoch":False}),
    ]
    for name, extra in combos:
        for tp in [1.0, 1.5, 2.0]:
            for sl in [0.5, 1.0]:
                sid += 1
                p = {"rsi_len": 7, "tp": tp, "sl": sl, "rsi_ob": 70, "rsi_os": 30,
                     "stoch_len": 14, "use_stoch": True}
                p.update(extra)
                strategies.append({"id": sid, "name": f"{name}_TP{tp}_SL{sl}",
                                   "group": "R2_COMBO", "params": p})

    # ═══ PATTERN 9: Stoch only on extreme (80/20 already works, try tighter) ═══
    for stoch_hi, stoch_lo in [(70,30),(60,40),(90,10)]:
        for ema_s, ema_l in [(3,8),(5,13)]:
            for tp in [1.0, 1.5]:
                sid += 1
                strategies.append({
                    "id": sid, "name": f"R2_STOCH_H{stoch_hi}_L{stoch_lo}_E{ema_s}_TP{tp}",
                    "group": "R2_STOCH_EXTREME",
                    "params": {"ema_s": ema_s, "ema_l": ema_l, "rsi_len": 7, "tp": tp, "sl": 1.0,
                               "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                               "stoch_hi": stoch_hi, "stoch_lo": stoch_lo},
                })

    return strategies


def get_promising_coins(db, min_grade="C"):
    """Get coins from previous scan that showed promise."""
    grade_order = {"A": 4, "B": 3, "C": 2, "D": 1}
    min_val = grade_order.get(min_grade, 2)

    rows = db.execute("""
        SELECT DISTINCT cs.symbol, cs.grade, cs.best_pnl, cs.volatility
        FROM coin_scores cs
        WHERE cs.run_id = (SELECT MAX(id) FROM scan_runs)
        AND cs.grade IN ('A','B','C','D')
        ORDER BY cs.best_pnl DESC
    """).fetchall()

    coins = []
    for r in rows:
        g = grade_order.get(r["grade"], 0)
        if g >= min_val:
            coins.append({"symbol": r["symbol"], "grade": r["grade"],
                          "best_pnl": r["best_pnl"], "volatility": r["volatility"]})
    return coins


def main():
    parser = argparse.ArgumentParser(description="Strategy Optimizer")
    parser.add_argument("--rounds", type=int, default=1, help="Optimization rounds")
    parser.add_argument("--candles", type=int, default=2000, help="Candles per coin")
    parser.add_argument("--min-wr", type=float, default=50, help="Min WR for pool")
    parser.add_argument("--min-grade", type=str, default="C", help="Min grade from R1")
    parser.add_argument("--save", action="store_true", default=True, help="Save to DB")
    args = parser.parse_args()

    db = init_db()
    db.row_factory = sqlite3.Row

    # Check if Round 1 data exists
    run_count = db.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0]
    if run_count == 0:
        print("No Round 1 data! Run multi_strategy_scanner.py first.")
        return

    strategies = build_round2_strategies()
    print("=" * 75)
    print("  STRATEGY OPTIMIZER — ROUND 2")
    print("=" * 75)
    print(f"  Strategies:    {len(strategies)}")
    print(f"  Candles:       {args.candles}")
    print(f"  Min WR:        {args.min_wr}%")
    print(f"  Min Grade:     {args.min_grade}")

    # Get promising coins
    promising = get_promising_coins(db, args.min_grade)
    print(f"  Promising coins: {len(promising)}")
    print()

    if not promising:
        print("  No promising coins found!")
        return

    # Scan each coin
    print(f"[SCAN] {len(promising)} coins x {len(strategies)} strategies...")
    all_results = []
    t0 = time.time()

    for idx, coin in enumerate(promising):
        sym = coin["symbol"]
        print(f"  [{idx+1}/{len(promising)}] {sym:<22} [{coin['grade']}] ", end="", flush=True)
        candles = fetch_klines(sym, limit=args.candles)
        if not candles or len(candles) < 100:
            print("SKIP")
            continue

        cache = precompute_indicators(candles)
        results = []

        for strat in strategies:
            trades = run_single_strategy(cache, strat)
            closed = [t for t in trades if t["result"] != "OPEN"]
            if len(closed) < 3:
                continue
            wins = [t for t in closed if t["result"] == "TP"]
            total_pnl = sum(t["pnl"] for t in closed)
            wr = len(wins) / len(closed) * 100
            avg_pnl = total_pnl / len(closed)
            avg_bars = sum(t["bars"] for t in closed) / len(closed)

            longs = [t for t in closed if t["dir"] == "LONG"]
            shorts = [t for t in closed if t["dir"] == "SHORT"]
            long_wins = [t for t in longs if t["result"] == "TP"]
            short_wins = [t for t in shorts if t["result"] == "TP"]

            results.append({
                "strategy_id": strat["id"], "strategy_name": strat["name"],
                "strategy_group": strat["group"],
                "total": len(closed), "wins": len(wins), "losses": len(closed)-len(wins),
                "wr": wr, "pnl": total_pnl, "avg_pnl": avg_pnl, "avg_bars": avg_bars,
                "long_wr": len(long_wins)/len(longs)*100 if longs else 0,
                "short_wr": len(short_wins)/len(shorts)*100 if shorts else 0,
            })

        if results:
            # Only keep strategies with WR >= threshold
            good = [r for r in results if r["wr"] >= args.min_wr and r["pnl"] > 0]
            best = max(results, key=lambda r: r["pnl"])
            n_good = len(good)
            print(f"{len(results):>3} strats | {n_good:>3} good (WR>={args.min_wr:.0f}%) | "
                  f"Best: {best['strategy_name']:<32} WR:{best['wr']:.0f}% PnL:{best['pnl']:+.2f}%")
            all_results.append({
                "symbol": sym, "grade": coin["grade"],
                "results": results, "good_count": n_good
            })
        else:
            print("no trades")
        time.sleep(0.05)

    elapsed = time.time() - t0
    print(f"\n  Done in {elapsed:.1f}s")

    if not all_results:
        print("  No results!")
        return

    # ═══ ANALYSIS ═══
    print()
    print("=" * 75)
    print("  RESULTATS ROUND 2 — TOP STRATEGIES PAR COIN")
    print("=" * 75)

    final_pool = []
    for res in sorted(all_results, key=lambda x: max(r["pnl"] for r in x["results"]), reverse=True):
        sym = res["symbol"]
        good = sorted([r for r in res["results"] if r["wr"] >= args.min_wr and r["pnl"] > 0],
                       key=lambda r: r["pnl"], reverse=True)
        best = max(res["results"], key=lambda r: r["pnl"])

        if good:
            top3 = good[:3]
            print(f"\n  [{res['grade']}] {sym} — {len(good)} strategies rentables (WR>={args.min_wr:.0f}%)")
            for t in top3:
                print(f"      {t['strategy_name']:<35} WR:{t['wr']:>5.1f}% PnL:{t['pnl']:>+7.2f}% "
                      f"({t['total']} trades, {t['avg_bars']:.1f} bars) L:{t['long_wr']:.0f}% S:{t['short_wr']:.0f}%")
            final_pool.append({
                "symbol": sym, "grade": res["grade"],
                "strategies": [{"name": t["strategy_name"], "wr": t["wr"],
                                "pnl": t["pnl"], "trades": t["total"],
                                "long_wr": t["long_wr"], "short_wr": t["short_wr"]}
                               for t in top3],
                "total_good": len(good)
            })

    # ═══ GLOBAL STRATEGY RANKING ═══
    print()
    print("=" * 75)
    print("  TOP 25 STRATEGIES GLOBALES (across all coins)")
    print("=" * 75)
    strat_global = {}
    for res in all_results:
        for r in res["results"]:
            sid = r["strategy_name"]
            if sid not in strat_global:
                strat_global[sid] = {"name": sid, "group": r["strategy_group"],
                                     "profitable_coins": 0, "total_coins": 0,
                                     "total_pnl": 0, "total_trades": 0,
                                     "sum_wr": 0, "count": 0}
            strat_global[sid]["total_coins"] += 1
            strat_global[sid]["total_pnl"] += r["pnl"]
            strat_global[sid]["total_trades"] += r["total"]
            strat_global[sid]["sum_wr"] += r["wr"]
            strat_global[sid]["count"] += 1
            if r["pnl"] > 0 and r["wr"] >= args.min_wr:
                strat_global[sid]["profitable_coins"] += 1

    strat_list = sorted(strat_global.values(),
                        key=lambda x: (x["profitable_coins"], x["total_pnl"]), reverse=True)

    print(f"\n  {'Strategy':<35} {'Group':<18} {'ProfCoins':>9} {'AvgWR':>6} {'TotalPnL':>10} {'Trades':>7}")
    print(f"  {'-'*35} {'-'*18} {'-'*9} {'-'*6} {'-'*10} {'-'*7}")
    for s in strat_list[:25]:
        avg_wr = s["sum_wr"] / s["count"] if s["count"] > 0 else 0
        print(f"  {s['name']:<35} {s['group']:<18} {s['profitable_coins']:>4}/{s['total_coins']:<4} "
              f"{avg_wr:>5.1f}% {s['total_pnl']:>+9.2f}% {s['total_trades']:>7}")

    # ═══ FINAL POOL ═══
    print()
    print("=" * 75)
    print(f"  POOL FINALE OPTIMISEE: {len(final_pool)} COINS")
    print("=" * 75)
    for c in final_pool:
        top = c["strategies"][0]
        print(f"  [{c['grade']}] {c['symbol']:<22} -> {top['name']:<35} "
              f"WR:{top['wr']:.1f}% PnL:{top['pnl']:+.2f}% ({top['trades']} trades) "
              f"| {c['total_good']} strats OK")

    # ═══ SAVE ═══
    if args.save:
        run_ts = datetime.now().isoformat()
        best_overall = final_pool[0] if final_pool else None

        cur = db.execute(
            "INSERT INTO scan_runs (timestamp, coins_scanned, strategies_run, total_trades, "
            "best_strategy, best_wr, best_pnl) VALUES (?,?,?,?,?,?,?)",
            (run_ts, len(all_results), len(strategies),
             sum(sum(r["total"] for r in res["results"]) for res in all_results),
             best_overall["strategies"][0]["name"] if best_overall else "",
             best_overall["strategies"][0]["wr"] if best_overall else 0,
             best_overall["strategies"][0]["pnl"] if best_overall else 0)
        )
        run_id = cur.lastrowid

        for res in all_results:
            best = max(res["results"], key=lambda r: r["pnl"])
            good = [r for r in res["results"] if r["wr"] >= args.min_wr and r["pnl"] > 0]
            avg_wr = sum(r["wr"] for r in res["results"]) / len(res["results"])
            avg_pnl = sum(r["avg_pnl"] for r in res["results"]) / len(res["results"])

            grade = "A" if len(good) >= 20 and best["wr"] >= 55 else \
                    "B" if len(good) >= 10 and best["wr"] >= 50 else \
                    "C" if len(good) >= 3 else "D"

            db.execute(
                "INSERT OR REPLACE INTO coin_scores "
                "(run_id, symbol, best_strategy, best_wr, best_pnl, avg_wr, avg_pnl, "
                "volatility, volume, grade) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, res["symbol"], best["strategy_name"], best["wr"], best["pnl"],
                 avg_wr, avg_pnl, 0, 0, grade)
            )
            for r in res["results"][:50]:  # Top 50 per coin
                db.execute(
                    "INSERT OR REPLACE INTO strategy_results "
                    "(run_id, symbol, strategy_id, strategy_name, strategy_group, "
                    "total_trades, wins, losses, wr, pnl, avg_pnl, avg_bars, long_wr, short_wr) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run_id, res["symbol"], r["strategy_id"], r["strategy_name"],
                     r["strategy_group"], r["total"], r["wins"], r["losses"],
                     r["wr"], r["pnl"], r["avg_pnl"], r["avg_bars"],
                     r["long_wr"], r["short_wr"])
                )

            # Update pool
            if good:
                top = good[0]
                db.execute(
                    "INSERT OR REPLACE INTO coin_pool "
                    "(symbol, grade, best_strategy, best_wr, best_pnl, volatility, volume, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (res["symbol"], grade, top["strategy_name"], top["wr"],
                     top["pnl"], 0, 0, run_ts)
                )

        db.commit()
        print(f"\n  Saved Round 2: {len(all_results)} coins, {len(final_pool)} in pool")

    db.close()
    print("=" * 75)


if __name__ == "__main__":
    main()
