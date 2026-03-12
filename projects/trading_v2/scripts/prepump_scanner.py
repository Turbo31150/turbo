"""
SCANNER PRE-PUMP AVANCE — MEXC Futures 832 symboles
Detection breakout + reversal + liquidite + clusters
"""
import json, urllib.request, sys, time
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
ts = lambda: datetime.now().strftime('%H:%M:%S')


def fetch(url, timeout=8):
    try:
        return json.loads(urllib.request.urlopen(url, timeout=timeout).read())
    except:
        return None


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    return 100 - 100 / (1 + ag / al) if al > 0 else 100


def ema(data, period):
    if len(data) < 2:
        return data[-1] if data else 0
    k = 2 / (period + 1)
    val = data[0]
    for d in data[1:]:
        val = d * k + val * (1 - k)
    return val


def bb_squeeze(closes, period=20):
    if len(closes) < period:
        return 99
    sma = sum(closes[-period:]) / period
    std = (sum((c - sma) ** 2 for c in closes[-period:]) / period) ** 0.5
    return (std / sma * 100) if sma > 0 else 99


def vol_spike(vols, lookback=6):
    if len(vols) < lookback + 10:
        return 1
    avg = sum(vols[:-lookback]) / (len(vols) - lookback)
    recent = sum(vols[-lookback:]) / lookback
    return recent / avg if avg > 0 else 1


def analyze_coin(sym, price, chg24, vol_usdt, high24, low24, funding, oi):
    score_breakout = 0
    score_reversal = 0
    signals = []

    rng = high24 - low24
    range_pos = (price - low24) / rng if rng > 0 else 0.5

    # Klines 15min
    k15 = fetch(f"https://contract.mexc.com/api/v1/contract/kline/{sym}?interval=Min15&limit=60")
    if not k15 or "data" not in k15:
        return None
    d15 = k15["data"]
    c15 = [float(x) for x in d15.get("close", [])]
    v15 = [float(x) for x in d15.get("vol", [])]
    if len(c15) < 30:
        return None

    rsi_15 = rsi(c15)
    bb_w_15 = bb_squeeze(c15)
    vs_15 = vol_spike(v15)
    ema9_15 = ema(c15, 9)
    ema21_15 = ema(c15, 21)

    # Klines 1H
    k1h = fetch(f"https://contract.mexc.com/api/v1/contract/kline/{sym}?interval=Min60&limit=60")
    rsi_1h, bb_w_1h, vs_1h = 50, 99, 1
    if k1h and "data" in k1h:
        d1h = k1h["data"]
        c1h = [float(x) for x in d1h.get("close", [])]
        v1h = [float(x) for x in d1h.get("vol", [])]
        if len(c1h) >= 20:
            rsi_1h = rsi(c1h)
            bb_w_1h = bb_squeeze(c1h)
            vs_1h = vol_spike(v1h)

    # Klines 4H
    k4h = fetch(f"https://contract.mexc.com/api/v1/contract/kline/{sym}?interval=Hour4&limit=50")
    rsi_4h, bb_w_4h = 50, 99
    if k4h and "data" in k4h:
        d4h = k4h["data"]
        c4h = [float(x) for x in d4h.get("close", [])]
        if len(c4h) >= 20:
            rsi_4h = rsi(c4h)
            bb_w_4h = bb_squeeze(c4h)

    # Orderbook
    ob = fetch(f"https://contract.mexc.com/api/v1/contract/depth/{sym}?limit=20")
    buy_pct, ob_imbalance = 50, 1.0
    bid_wall_dist, ask_wall_dist = 99, 99
    if ob and "data" in ob:
        dd = ob["data"]
        bids = [(float(b[0]), float(b[1])) for b in dd.get("bids", [])]
        asks = [(float(a[0]), float(a[1])) for a in dd.get("asks", [])]
        tb = sum(b[1] for b in bids)
        ta = sum(a[1] for a in asks)
        buy_pct = tb / (tb + ta) * 100 if (tb + ta) > 0 else 50

        b1 = sum(v for p, v in bids if p >= price * 0.99)
        a1 = sum(v for p, v in asks if p <= price * 1.01)
        ob_imbalance = b1 / a1 if a1 > 0 else 1

        if bids:
            avg_b = tb / len(bids)
            walls_b = [p for p, v in bids if v > avg_b * 3]
            if walls_b:
                bid_wall_dist = (price - walls_b[0]) / price * 100
        if asks:
            avg_a = ta / len(asks)
            walls_a = [p for p, v in asks if v > avg_a * 3]
            if walls_a:
                ask_wall_dist = (walls_a[0] - price) / price * 100

    # ── SCORING BREAKOUT ──
    if bb_w_15 < 1.0:
        score_breakout += 20; signals.append("BB_SQUEEZE_15m")
    elif bb_w_15 < 2.0:
        score_breakout += 10
    if bb_w_1h < 1.5:
        score_breakout += 20; signals.append("BB_SQUEEZE_1H")
    elif bb_w_1h < 3.0:
        score_breakout += 10
    if bb_w_4h < 2.0:
        score_breakout += 15; signals.append("BB_SQUEEZE_4H")

    if vs_15 > 3.0:
        score_breakout += 20; signals.append(f"VOL_SPIKE_15m({vs_15:.1f}x)")
    elif vs_15 > 2.0:
        score_breakout += 12
    elif vs_15 > 1.5:
        score_breakout += 5
    if vs_1h > 2.0:
        score_breakout += 15; signals.append(f"VOL_SPIKE_1H({vs_1h:.1f}x)")

    if range_pos > 0.95:
        score_breakout += 15; signals.append("NEAR_HIGH")
    elif range_pos > 0.85:
        score_breakout += 8

    if ema9_15 > ema21_15 and c15[-1] > ema9_15:
        score_breakout += 10; signals.append("EMA_BULL_15m")

    if ob_imbalance > 1.5:
        score_breakout += 10; signals.append(f"OB_BUY({ob_imbalance:.1f})")
    elif ob_imbalance > 1.2:
        score_breakout += 5

    # ── SCORING REVERSAL ──
    if rsi_15 < 25:
        score_reversal += 15; signals.append(f"RSI_OS_15m({rsi_15:.0f})")
    elif rsi_15 < 35:
        score_reversal += 8
    if rsi_1h < 25:
        score_reversal += 20; signals.append(f"RSI_OS_1H({rsi_1h:.0f})")
    elif rsi_1h < 35:
        score_reversal += 10
    if rsi_4h < 30:
        score_reversal += 20; signals.append(f"RSI_OS_4H({rsi_4h:.0f})")
    elif rsi_4h < 40:
        score_reversal += 10

    if funding < -0.005:
        score_reversal += 20; signals.append(f"FUNDING_NEG({funding:.4f})")
    elif funding < 0:
        score_reversal += 10

    if buy_pct > 60:
        score_reversal += 15; signals.append(f"OB_BUY_PRESS({buy_pct:.0f}%)")
    elif buy_pct > 55:
        score_reversal += 8

    if vs_15 > 2.0 and rsi_15 < 35:
        score_reversal += 15; signals.append("CAPITULATION_SPIKE")

    bb_sma = sum(c15[-20:]) / 20
    bb_std = (sum((c - bb_sma) ** 2 for c in c15[-20:]) / 20) ** 0.5
    bb_low = bb_sma - 2 * bb_std
    bb_high = bb_sma + 2 * bb_std
    bb_pos = (c15[-1] - bb_low) / (bb_high - bb_low) * 100 if (bb_high - bb_low) > 0 else 50
    if bb_pos < 10:
        score_reversal += 15; signals.append(f"BB_EXTREME_LOW({bb_pos:.0f}%)")

    if bid_wall_dist < 1.0:
        score_reversal += 10; signals.append(f"BID_WALL_CLOSE({bid_wall_dist:.1f}%)")

    best_type = "BREAKOUT" if score_breakout >= score_reversal else "REVERSAL"
    best_score = max(score_breakout, score_reversal)

    return {
        "symbol": sym, "price": price, "chg24": chg24, "vol_usdt": vol_usdt,
        "funding": funding, "oi": oi, "range_pos": range_pos,
        "rsi_15": rsi_15, "rsi_1h": rsi_1h, "rsi_4h": rsi_4h,
        "bb_w_15": bb_w_15, "bb_w_1h": bb_w_1h, "bb_w_4h": bb_w_4h,
        "vs_15": vs_15, "vs_1h": vs_1h,
        "buy_pct": buy_pct, "ob_imbalance": ob_imbalance,
        "score_breakout": score_breakout, "score_reversal": score_reversal,
        "best_type": best_type, "best_score": best_score,
        "signals": signals,
        "bid_wall_dist": bid_wall_dist, "ask_wall_dist": ask_wall_dist,
    }


def fmt_vol(v):
    if v >= 1e9: return f"{v/1e9:.1f}B"
    if v >= 1e6: return f"{v/1e6:.1f}M"
    return f"{v/1e3:.0f}K"


def main():
    print(f"[{ts()}] {'='*70}")
    print(f"[{ts()}]   SCANNER PRE-PUMP AVANCE — MEXC Futures")
    print(f"[{ts()}]   Breakout + Reversal + Liquidite + Clusters")
    print(f"[{ts()}] {'='*70}")

    data = fetch("https://contract.mexc.com/api/v1/contract/ticker", timeout=15)
    if not data or "data" not in data:
        print("ERREUR: API MEXC indisponible")
        sys.exit(1)

    tickers = data["data"]
    print(f"[{ts()}] {len(tickers)} symboles recuperes")

    MIN_VOL = 500_000
    candidates = []
    for t in tickers:
        vol = float(t.get("amount24", 0))
        if vol >= MIN_VOL:
            candidates.append({
                "symbol": t.get("symbol", ""),
                "price": float(t.get("lastPrice", 0)),
                "chg24": float(t.get("riseFallRate", 0)) * 100,
                "vol_usdt": vol,
                "high24": float(t.get("high24Price", 0)),
                "low24": float(t.get("low24Price", 0)),
                "funding": float(t.get("fundingRate", 0)) * 100,
                "oi": float(t.get("holdVol", 0)),
            })

    print(f"[{ts()}] {len(candidates)} candidats (vol > {MIN_VOL/1e6:.1f}M)")
    print(f"[{ts()}] Analyse multi-TF + orderbook en cours...")

    results = []
    total = len(candidates)
    for i, c in enumerate(candidates):
        if (i + 1) % 25 == 0:
            print(f"[{ts()}]   ... {i+1}/{total}", flush=True)
        try:
            r = analyze_coin(
                c["symbol"], c["price"], c["chg24"], c["vol_usdt"],
                c["high24"], c["low24"], c["funding"], c["oi"],
            )
            if r and r["best_score"] > 0:
                results.append(r)
        except:
            pass
        time.sleep(0.15)

    print(f"[{ts()}] {len(results)} coins scores")

    breakouts = sorted(
        [r for r in results if r["best_type"] == "BREAKOUT"],
        key=lambda x: x["score_breakout"], reverse=True,
    )
    reversals = sorted(
        [r for r in results if r["best_type"] == "REVERSAL"],
        key=lambda x: x["score_reversal"], reverse=True,
    )
    all_ranked = sorted(results, key=lambda x: x["best_score"], reverse=True)

    print(f"\n{'='*70}")
    print(f"  TOP 15 BREAKOUT (compression -> explosion)")
    print(f"{'='*70}")
    hdr = f"  {'#':>2} {'Symbol':<16} {'Price':>10} {'Score':>6} {'BB15':>5} {'BB1H':>5} {'BB4H':>5} {'VolSp':>6} {'Range':>6} Signals"
    print(hdr)
    for i, r in enumerate(breakouts[:15]):
        sigs = ", ".join(r["signals"][:4])
        print(f"  {i+1:>2} {r['symbol']:<16} {r['price']:>10.6g} {r['score_breakout']:>5} {r['bb_w_15']:>4.1f}% {r['bb_w_1h']:>4.1f}% {r['bb_w_4h']:>4.1f}% {r['vs_15']:>5.1f}x {r['range_pos']:>5.0%} {sigs}")

    print(f"\n{'='*70}")
    print(f"  TOP 15 REVERSAL (survendu -> rebond pre-pump)")
    print(f"{'='*70}")
    hdr2 = f"  {'#':>2} {'Symbol':<16} {'Price':>10} {'Score':>6} {'RSI15':>5} {'RSI1H':>5} {'RSI4H':>5} {'Fund':>7} {'BuyOB':>6} Signals"
    print(hdr2)
    for i, r in enumerate(reversals[:15]):
        sigs = ", ".join(r["signals"][:4])
        print(f"  {i+1:>2} {r['symbol']:<16} {r['price']:>10.6g} {r['score_reversal']:>5} {r['rsi_15']:>5.1f} {r['rsi_1h']:>5.1f} {r['rsi_4h']:>5.1f} {r['funding']:>+6.4f}% {r['buy_pct']:>5.1f}% {sigs}")

    # TOP 3
    print(f"\n{'='*70}")
    print(f"  TOP 3 ABSOLUS — PLUS PROCHES DU PUMP")
    print(f"{'='*70}")
    top3 = all_ranked[:3]
    for i, r in enumerate(top3):
        if r["best_type"] == "BREAKOUT":
            entry = r["price"]
            tp1 = entry * 1.03
            tp2 = entry * 1.06
            sl = entry * 0.985
        else:
            entry = r["price"] * 0.995
            tp1 = entry * 1.04
            tp2 = entry * 1.08
            sl = entry * 0.975

        print(f"\n  #{i+1} {'*'*50}")
        print(f"  Coin:     {r['symbol']}")
        print(f"  Type:     {r['best_type']}")
        print(f"  Score:    {r['best_score']}/100")
        print(f"  Prix:     {r['price']} USDT")
        print(f"  Entry:    {entry:.6g} USDT")
        print(f"  TP1:      {tp1:.6g} USDT (+{(tp1/entry-1)*100:.1f}%)")
        print(f"  TP2:      {tp2:.6g} USDT (+{(tp2/entry-1)*100:.1f}%)")
        print(f"  SL:       {sl:.6g} USDT (-{(1-sl/entry)*100:.1f}%)")
        print(f"  Vol 24h:  {fmt_vol(r['vol_usdt'])}")
        print(f"  Funding:  {r['funding']:+.4f}%")
        print(f"  OB Buy:   {r['buy_pct']:.1f}%")
        print(f"  RSI:      15m={r['rsi_15']:.0f} 1H={r['rsi_1h']:.0f} 4H={r['rsi_4h']:.0f}")
        print(f"  BB width: 15m={r['bb_w_15']:.1f}% 1H={r['bb_w_1h']:.1f}% 4H={r['bb_w_4h']:.1f}%")
        print(f"  Signals:  {', '.join(r['signals'])}")

    import os
    os.makedirs("F:/BUREAU/TRADING_V2_PRODUCTION/data", exist_ok=True)
    with open("F:/BUREAU/TRADING_V2_PRODUCTION/data/prepump_scan.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_scanned": len(candidates),
            "total_scored": len(results),
            "top3": [{
                "symbol": r["symbol"], "type": r["best_type"],
                "score": r["best_score"], "price": r["price"],
                "signals": r["signals"],
            } for r in top3],
        }, f, indent=2)

    print(f"\n[{ts()}] SCAN TERMINE — {len(results)} coins, top 3 exportes")


if __name__ == "__main__":
    main()
