"""Deep Scan — Pipeline entonnoir multi-pass pour MEXC Futures.

800+ coins -> 100 -> 30 -> 5-10 signaux explosifs.
Chaque pass sauvegarde tout en SQL (nom, prix, heure, sentiment, score).

Usage:
    python cowork/dev/sniper_deep.py [--top 10] [--no-consensus] [--chat-id=ID]
"""
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

TURBO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(TURBO_ROOT / "cowork" / "dev"))

from sniper_scanner import (
    DB_PATH,
    analyze_coin,
    cluster_consensus,
    compute_history_bonus,
    fetch_all_tickers,
    fetch_depth,
    fetch_klines,
    format_signal,
    get_previous_snapshot,
    log,
    save_coin_snapshots,
    send_telegram,
    send_voice_summary,
    try_gpu_pipeline,
    update_coin_registry,
    update_registry_scores,
)


def deep_scan(final_count=10, with_consensus=True, chat_id=None):
    """Pipeline entonnoir multi-pass: 800+ -> 100 -> 30 -> 5-10 coins explosifs."""
    t_start = time.time()
    db = sqlite3.connect(str(DB_PATH))

    # === PASS 1 -- Quick scan ALL (800+) =====================================
    log("DEEP SCAN PASS 1/3: Scan rapide ALL tickers...")
    if chat_id:
        send_telegram("Pass 1/3 -- Scan rapide 750+ coins...", chat_id)

    tickers = fetch_all_tickers()
    valid_tickers = [
        t for t in tickers
        if t.get("symbol", "").endswith("_USDT") and float(t.get("lastPrice", 0)) > 0
    ]
    update_coin_registry(db, valid_tickers)
    db.commit()
    log(f"  {len(valid_tickers)} coins enregistres en SQL")

    all_pass1 = []

    def quick_analyze(t):
        sym = t["symbol"]
        try:
            candles = fetch_klines(sym, interval="Min15", limit=100)
            if candles and len(candles) >= 20:
                sig = analyze_coin(sym, candles, t, None)
                if sig:
                    return sig
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = {pool.submit(quick_analyze, t): t for t in valid_tickers}
        for f in as_completed(futs, timeout=300):
            try:
                r = f.result()
                if r:
                    all_pass1.append(r)
            except Exception:
                pass

    # Enrichissement historique (sequentiel, thread-safe)
    for r in all_pass1:
        try:
            prev = get_previous_snapshot(db, r["symbol"])
            bonus, h_pats = compute_history_bonus(prev, r)
            if bonus > 0:
                r["score"] = min(r["score"] + bonus, 100)
                r["patterns"].extend(h_pats)
            if prev:
                r["prev_price"] = prev.get("price", 0)
                r["prev_score"] = prev.get("score", 0)
                r["prev_direction"] = prev.get("direction", "")
                if prev.get("price", 0) > 0:
                    r["price_evolution"] = (r["price"] - prev["price"]) / prev["price"] * 100
        except Exception:
            pass

    # Sauvegarder TOUS les snapshots pass 1
    tickers_map = {t["symbol"]: t for t in valid_tickers}
    try:
        cur = db.execute(
            "INSERT INTO scan_runs (coins_scanned, signals_found, breakouts, duration_s, phase1_ms, phase2_ms, phase3_ms) VALUES (?,?,?,?,?,?,?)",
            (len(valid_tickers), len([r for r in all_pass1 if r["score"] >= 50]), 0, time.time() - t_start, 0, 0, 0),
        )
        scan_id = cur.lastrowid
        save_coin_snapshots(db, scan_id, all_pass1, tickers_map)
        for r in all_pass1:
            update_registry_scores(db, r["symbol"], r["score"], r["direction"])
        db.commit()
    except Exception as e:
        log(f"  DB pass1 error: {e}")

    all_pass1.sort(key=lambda s: s["score"], reverse=True)
    top100 = all_pass1[:100]
    p1_time = time.time() - t_start
    log(f"  Pass 1: {len(all_pass1)} analyses, top 100 (score min {top100[-1]['score'] if top100 else 0}) [{p1_time:.0f}s]")

    # === PASS 2 -- Multi-TF re-scan top 100 ==================================
    t2 = time.time()
    log(f"DEEP SCAN PASS 2/3: Multi-TF sur {len(top100)} coins...")
    if chat_id:
        scores_range = f"{top100[-1]['score']}-{top100[0]['score']}" if top100 else "?"
        send_telegram(f"Pass 2/3 -- Re-scan multi-TF {len(top100)} coins (scores {scores_range})...", chat_id)

    def deep_analyze(sig):
        """Re-analyse avec 3 timeframes (1min, 5min, 15min) + orderbook."""
        sym = sig["symbol"]
        tf_scores = []
        tf_directions = []
        try:
            for tf in ["Min1", "Min5", "Min15"]:
                candles = fetch_klines(sym, interval=tf, limit=60)
                if candles and len(candles) >= 20:
                    sub = analyze_coin(sym, candles, {}, None)
                    if sub:
                        tf_scores.append(sub["score"])
                        tf_directions.append(sub["direction"])

            if tf_scores:
                avg_score = sum(tf_scores) / len(tf_scores)
                all_same = len(set(tf_directions)) == 1
                convergence_bonus = 15 if all_same and len(tf_directions) >= 3 else (8 if all_same else 0)
                sig["score"] = min(
                    int(sig["score"] * 0.4 + avg_score * 0.4 + convergence_bonus * 0.2 + convergence_bonus),
                    100,
                )
                sig["tf_scores"] = tf_scores
                sig["tf_directions"] = tf_directions
                if all_same:
                    sig["patterns"].append("MTF_CONVERGENCE")
                sig["mtf_avg"] = avg_score

            # Orderbook pression
            depth = fetch_depth(sym)
            if depth:
                asks = depth.get("asks", [])
                bids = depth.get("bids", [])
                if asks and bids:
                    top10_bid = sum(b[1] for b in bids[:10])
                    top10_ask = sum(a[1] for a in asks[:10])
                    total = top10_bid + top10_ask
                    if total > 0:
                        ob_ratio = top10_bid / total
                        if sig["direction"] == "LONG" and ob_ratio > 0.55:
                            sig["score"] = min(sig["score"] + 5, 100)
                            sig["patterns"].append("OB_BULL")
                        elif sig["direction"] == "SHORT" and ob_ratio < 0.45:
                            sig["score"] = min(sig["score"] + 5, 100)
                            sig["patterns"].append("OB_BEAR")
                        sig["ob_ratio"] = ob_ratio
        except Exception:
            pass
        return sig

    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = [pool.submit(deep_analyze, s) for s in top100]
        pass2_results = []
        for f in as_completed(futs, timeout=120):
            try:
                pass2_results.append(f.result())
            except Exception:
                pass

    pass2_results.sort(key=lambda s: s["score"], reverse=True)
    top30 = pass2_results[:30]
    p2_time = time.time() - t2
    mtf_conv = sum(1 for s in pass2_results if "MTF_CONVERGENCE" in s.get("patterns", []))
    log(f"  Pass 2: {len(pass2_results)} re-analyses, {mtf_conv} MTF convergents, top 30 (score min {top30[-1]['score'] if top30 else 0}) [{p2_time:.0f}s]")

    # === PASS 3 -- GPU + Cluster consensus sur top 30 ========================
    t3 = time.time()
    log(f"DEEP SCAN PASS 3/3: GPU + Cluster sur {len(top30)} coins...")
    if chat_id:
        names = ", ".join(s["symbol"].replace("_USDT", "") for s in top30[:8])
        send_telegram(f"Pass 3/3 -- GPU + IA cluster sur {len(top30)} coins ({names}...)", chat_id)

    # GPU 100 strategies
    gpu_symbols = [s["symbol"] for s in top30]
    gpu_data = try_gpu_pipeline(gpu_symbols) if gpu_symbols else {}
    for sig in top30:
        gd = gpu_data.get(sig["symbol"])
        if gd:
            sig["gpu_confidence"] = gd["confidence"]
            sig["gpu_regime"] = gd["regime"]
            sig["gpu_strategies"] = gd["strategies"][:5]
            gpu_bonus = int(gd["confidence"] * 15)
            sig["score"] = min(sig["score"] + gpu_bonus, 100)
            if gd["strategies"]:
                sig["patterns"].append(f"GPU_{len(gd['strategies'])}strats")

    # Cluster consensus
    if with_consensus:
        top_for_cons = sorted(top30, key=lambda s: s["score"], reverse=True)[: min(final_count + 2, 12)]
        log(f"  Cluster consensus sur {len(top_for_cons)} coins...")
        for sig in top_for_cons:
            try:
                cons = cluster_consensus(sig)
                sig["consensus"] = cons["consensus"]
                sig["consensus_pct"] = cons["consensus_pct"]
                sig["cluster_nodes"] = cons["nodes_used"]
            except Exception:
                sig["consensus"] = "SKIP"

    # Tri final
    top30.sort(key=lambda s: s["score"], reverse=True)
    final = top30[:final_count]

    # Sauvegarder signaux finaux
    try:
        for sig in final:
            db.execute(
                "INSERT INTO scan_signals (symbol, direction, score, entry, tp1, tp2, tp3, sl, atr, rsi, volume_ratio, bb_squeeze, pattern, consensus, cluster_nodes, gpu_confidence, gpu_strategies, gpu_regime) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    sig["symbol"], sig["direction"], sig["score"], sig["entry"],
                    sig["tp1"], sig["tp2"], sig["tp3"], sig["sl"], sig["atr"],
                    sig["rsi"], sig["volume_ratio"], sig["bb_squeeze"],
                    ",".join(sig["patterns"]), sig.get("consensus", ""),
                    ",".join(sig.get("cluster_nodes", [])),
                    sig.get("gpu_confidence", 0),
                    ",".join(sig.get("gpu_strategies", [])[:5]),
                    sig.get("gpu_regime", ""),
                ),
            )
        db.commit()
    except Exception as e:
        log(f"  DB pass3 error: {e}")
    db.close()

    p3_time = time.time() - t3
    total_time = time.time() - t_start
    log(f"  Pass 3: GPU + consensus [{p3_time:.0f}s]")
    log(f"  DEEP SCAN TOTAL: {total_time:.0f}s | {len(valid_tickers)}->{len(all_pass1)}->{len(pass2_results)}->{len(final)} coins")

    return {
        "signals": final,
        "total_coins": len(valid_tickers),
        "pass1_count": len(all_pass1),
        "pass2_count": len(pass2_results),
        "pass3_count": len(top30),
        "final_count": len(final),
        "duration": total_time,
        "funnel": f"{len(valid_tickers)}->{len(all_pass1)}->{len(pass2_results)}->{len(final)}",
    }


def format_deep_report(result):
    """Format rapport deep scan pour Telegram."""
    signals = result.get("signals", [])
    if not signals:
        return "Deep scan termine -- aucun signal explosif detecte."

    now = datetime.now().strftime("%H:%M")
    funnel = result.get("funnel", "?")
    dur = result.get("duration", 0)
    longs = sum(1 for s in signals if s["direction"] == "LONG")
    shorts = len(signals) - longs

    lines = [
        f"DEEP SCAN -- {now}",
        f"Duree {dur:.0f}s | Entonnoir: {funnel}",
        f"{len(signals)} signaux finaux ({longs}L/{shorts}S)",
        "---",
    ]
    for i, sig in enumerate(signals):
        lines.append("")
        lines.append(format_signal(sig, i + 1))
    lines.append("")
    lines.append("---")
    lines.append("3 passes x multi-TF -- pas un conseil financier")
    return "\n".join(lines)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    import argparse

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="JARVIS Deep Scanner")
    parser.add_argument("--top", type=int, default=10, help="Nombre de signaux finaux (defaut 10)")
    parser.add_argument("--no-consensus", action="store_true", help="Skip cluster consensus")
    parser.add_argument("--chat-id", type=str, default=None, help="Telegram chat ID pour updates")
    parser.add_argument("--notify", action="store_true", help="Envoyer resultat sur Telegram")
    args = parser.parse_args()

    result = deep_scan(
        final_count=args.top,
        with_consensus=not args.no_consensus,
        chat_id=args.chat_id,
    )

    # Afficher rapport
    report = format_deep_report(result)
    print(report)

    # Envoyer sur Telegram
    if args.notify or args.chat_id:
        cid = args.chat_id
        send_telegram(report, chat_id=cid)
        send_voice_summary(result["signals"], chat_id=cid)


if __name__ == "__main__":
    main()
