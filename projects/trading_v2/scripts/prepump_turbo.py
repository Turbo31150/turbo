"""Pre-pump scanner TURBO — parallel HTTP + MAO cluster analysis."""
import json, urllib.request, sys, time, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
START = time.time()


def fetch(url, timeout=12):
    try:
        return json.loads(urllib.request.urlopen(url, timeout=timeout).read())
    except Exception:
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


def bb_width(closes, period=20):
    if len(closes) < period:
        return 99
    sma = sum(closes[-period:]) / period
    std = (sum((c - sma) ** 2 for c in closes[-period:]) / period) ** 0.5
    return (std / sma * 100) if sma > 0 else 99


def bb(closes, period=20):
    if len(closes) < period:
        return 0, 0, 0
    sma = sum(closes[-period:]) / period
    std = (sum((c - sma) ** 2 for c in closes[-period:]) / period) ** 0.5
    return sma - 2 * std, sma, sma + 2 * std


# ─── PHASE 1: Fetch all tickers ───
print(f"{'='*70}")
print(f"  PRE-PUMP TURBO SCANNER — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*70}")
print(f"\n  [1/5] Chargement tickers...", flush=True)

ticker = fetch("https://contract.mexc.com/api/v1/contract/ticker")
if not ticker or "data" not in ticker:
    print("  ERREUR: impossible de charger les tickers")
    sys.exit(1)

all_coins = ticker["data"]
print(f"         {len(all_coins)} symboles trouves")

# Filter by volume
candidates = []
for c in all_coins:
    vol = float(c.get("amount24", 0))
    sym = c.get("symbol", "")
    if vol > 500000 and sym.endswith("_USDT"):
        candidates.append(c)

candidates.sort(key=lambda x: float(x.get("amount24", 0)), reverse=True)
print(f"         {len(candidates)} candidats (vol > 500K USDT)")

# ─── PHASE 2: Parallel kline + orderbook fetch ───
print(f"\n  [2/5] Fetch parallel klines + orderbook ({len(candidates)} coins x 4 TF)...", flush=True)


def fetch_coin_data(coin):
    """Fetch all data for one coin in one thread."""
    sym = coin["symbol"]
    result = {"symbol": sym, "coin": coin, "tf": {}, "ob": None}

    # 3 timeframes
    for interval, label in [("Min15", "15m"), ("Min60", "1H"), ("Hour4", "4H")]:
        data = fetch(f"https://contract.mexc.com/api/v1/contract/kline/{sym}?interval={interval}&limit=60")
        if data and "data" in data:
            d = data["data"]
            closes = [float(x) for x in d.get("close", [])]
            vols = [float(x) for x in d.get("vol", [])]
            highs = [float(x) for x in d.get("high", [])]
            lows = [float(x) for x in d.get("low", [])]
            if closes:
                result["tf"][label] = {"closes": closes, "vols": vols, "highs": highs, "lows": lows}

    # Orderbook
    ob = fetch(f"https://contract.mexc.com/api/v1/contract/depth/{sym}?limit=30")
    if ob and "data" in ob:
        result["ob"] = ob["data"]

    return result


# ThreadPool — 40 workers parallel
done = 0
coin_data = []
with ThreadPoolExecutor(max_workers=40) as pool:
    futures = {pool.submit(fetch_coin_data, c): c for c in candidates}
    for future in as_completed(futures):
        done += 1
        if done % 50 == 0:
            elapsed = time.time() - START
            print(f"         {done}/{len(candidates)} ({elapsed:.0f}s)", flush=True)
        try:
            r = future.result()
            if r and r["tf"]:
                coin_data.append(r)
        except Exception:
            pass

elapsed = time.time() - START
print(f"         {len(coin_data)} coins avec data ({elapsed:.0f}s)")

# ─── PHASE 3: Score all coins ───
print(f"\n  [3/5] Scoring {len(coin_data)} coins...", flush=True)

results = []
for cd in coin_data:
    sym = cd["symbol"]
    coin = cd["coin"]
    price = float(coin.get("lastPrice", 0))
    chg24 = float(coin.get("riseFallRate", 0)) * 100
    vol24 = float(coin.get("amount24", 0))
    funding = float(coin.get("fundingRate", 0)) * 100
    oi = float(coin.get("holdVol", 0))
    high24 = float(coin.get("high24Price", 0))
    low24 = float(coin.get("low24Price", 0))

    if price <= 0:
        continue

    breakout_score = 0
    reversal_score = 0
    signals = []

    # BB squeeze multi-TF
    squeeze_count = 0
    for label in ["15m", "1H", "4H"]:
        if label in cd["tf"]:
            bw = bb_width(cd["tf"][label]["closes"])
            if bw < 2.0:
                squeeze_count += 1
    if squeeze_count >= 3:
        breakout_score += 40
        signals.append(f"BB_SQUEEZE_3TF")
    elif squeeze_count >= 2:
        breakout_score += 25
        signals.append(f"BB_SQUEEZE_{squeeze_count}TF")
    elif squeeze_count >= 1:
        breakout_score += 10

    # Volume spike
    for label in ["15m", "1H"]:
        if label in cd["tf"]:
            vols = cd["tf"][label]["vols"]
            if len(vols) > 6:
                avg = sum(vols[:-6]) / max(len(vols) - 6, 1)
                recent = sum(vols[-3:]) / 3
                ratio = recent / avg if avg > 0 else 1
                if ratio > 10:
                    breakout_score += 25
                    signals.append(f"VOL_{label}_{ratio:.0f}x")
                elif ratio > 5:
                    breakout_score += 15
                    signals.append(f"VOL_{label}_{ratio:.0f}x")
                elif ratio > 3:
                    breakout_score += 8

    # Range position (near low = accumulation)
    if high24 > low24 > 0:
        range_pos = (price - low24) / (high24 - low24)
        if range_pos < 0.15:
            breakout_score += 15
            reversal_score += 15
            signals.append(f"RANGE_LOW_{range_pos:.0%}")
        elif range_pos < 0.3:
            breakout_score += 8
            reversal_score += 8

    # RSI oversold multi-TF
    for label in ["1H", "4H"]:
        if label in cd["tf"]:
            r = rsi(cd["tf"][label]["closes"])
            if r < 20:
                reversal_score += 25
                signals.append(f"RSI_{label}_{r:.0f}")
            elif r < 30:
                reversal_score += 15
                signals.append(f"RSI_{label}_{r:.0f}")

    # Funding negative
    if funding < -0.01:
        reversal_score += 20
        signals.append(f"FUND_{funding:+.3f}%")
    elif funding < -0.005:
        reversal_score += 10

    # EMA cross
    if "15m" in cd["tf"]:
        closes = cd["tf"]["15m"]["closes"]
        e9 = ema(closes, 9)
        e21 = ema(closes, 21)
        if e9 > e21 and closes[-1] > e9:
            breakout_score += 10
            signals.append("EMA_BULL_15m")
        elif e9 < e21 and closes[-1] < e9:
            reversal_score += 5

    # Orderbook imbalance
    buy_pct = 50
    if cd["ob"]:
        bids = [(float(b[0]), float(b[1])) for b in cd["ob"].get("bids", [])]
        asks = [(float(a[0]), float(a[1])) for a in cd["ob"].get("asks", [])]
        tb = sum(v for _, v in bids)
        ta = sum(v for _, v in asks)
        buy_pct = tb / (tb + ta) * 100 if (tb + ta) > 0 else 50
        if buy_pct > 65:
            breakout_score += 15
            reversal_score += 10
            signals.append(f"OB_BUY_{buy_pct:.0f}%")
        elif buy_pct > 58:
            breakout_score += 8

    # Liquidation clusters (support strength)
    if cd["ob"]:
        bids = [(float(b[0]), float(b[1])) for b in cd["ob"].get("bids", [])]
        asks = [(float(a[0]), float(a[1])) for a in cd["ob"].get("asks", [])]
        avg_bid = sum(v for _, v in bids) / max(len(bids), 1)
        walls = [(p, v) for p, v in bids if v > avg_bid * 3]
        if walls:
            breakout_score += 5
            signals.append(f"WALLS_{len(walls)}")

    total = breakout_score + reversal_score
    results.append({
        "symbol": sym, "price": price, "chg24": chg24, "vol24": vol24,
        "funding": funding, "oi": oi, "buy_pct": buy_pct,
        "breakout": breakout_score, "reversal": reversal_score,
        "total": total, "signals": signals
    })

results.sort(key=lambda x: x["total"], reverse=True)
print(f"         {len(results)} coins scores")

# ─── PHASE 4: Display top results ───
print(f"\n  [4/5] Resultats")
print(f"  {'='*70}")
print(f"  TOP 15 BREAKOUT:")
print(f"  {'Rank':<5} {'Symbol':<18} {'Price':>10} {'Brk':>5} {'Rev':>5} {'Tot':>5} {'Vol24':>12} {'Signals'}")
print(f"  {'-'*90}")
brk_sorted = sorted(results, key=lambda x: x["breakout"], reverse=True)[:15]
for i, r in enumerate(brk_sorted, 1):
    sigs = " ".join(r["signals"][:4])
    print(f"  {i:<5} {r['symbol']:<18} {r['price']:>10.6g} {r['breakout']:>5} {r['reversal']:>5} {r['total']:>5} {r['vol24']:>11,.0f} {sigs}")

print(f"\n  TOP 15 REVERSAL:")
print(f"  {'Rank':<5} {'Symbol':<18} {'Price':>10} {'Brk':>5} {'Rev':>5} {'Tot':>5} {'Funding':>8} {'Signals'}")
print(f"  {'-'*90}")
rev_sorted = sorted(results, key=lambda x: x["reversal"], reverse=True)[:15]
for i, r in enumerate(rev_sorted, 1):
    sigs = " ".join(r["signals"][:4])
    print(f"  {i:<5} {r['symbol']:<18} {r['price']:>10.6g} {r['reversal']:>5} {r['breakout']:>5} {r['total']:>5} {r['funding']:>+7.3f}% {sigs}")

# ─── PHASE 5: Top 3 absolute with entry/TP/SL ───
print(f"\n  {'='*70}")
print(f"  TOP 3 ABSOLUS — ENTRY / TP / SL")
print(f"  {'='*70}")

top3 = results[:3]
top3_data = []
for r in top3:
    sym = r["symbol"]
    p = r["price"]

    # Determine direction from signals
    is_long = r["breakout"] >= r["reversal"] or r["buy_pct"] > 55

    # Find support/resistance from orderbook data
    cd_match = next((cd for cd in coin_data if cd["symbol"] == sym), None)
    support = p * 0.97
    resistance = p * 1.03

    if cd_match and cd_match["ob"]:
        bids = [(float(b[0]), float(b[1])) for b in cd_match["ob"].get("bids", [])]
        asks = [(float(a[0]), float(a[1])) for a in cd_match["ob"].get("asks", [])]
        avg_bid = sum(v for _, v in bids) / max(len(bids), 1)
        avg_ask = sum(v for _, v in asks) / max(len(asks), 1)
        bid_walls = sorted([(p2, v) for p2, v in bids if v > avg_bid * 2], key=lambda x: x[1], reverse=True)
        ask_walls = sorted([(p2, v) for p2, v in asks if v > avg_ask * 2], key=lambda x: x[1], reverse=True)
        if bid_walls:
            support = bid_walls[0][0]
        if ask_walls:
            resistance = ask_walls[0][0]

    # BB bands for targets
    if cd_match and "1H" in cd_match["tf"]:
        closes = cd_match["tf"]["1H"]["closes"]
        bl, bm, bh = bb(closes)
        if bl > 0 and bh > 0:
            if is_long:
                support = max(support, bl)
                resistance = bh
            else:
                support = bl
                resistance = min(resistance, bh)

    if is_long:
        entry = p  # market or limit at current
        tp = resistance
        sl = support * 0.995
        direction = "LONG"
    else:
        entry = p
        tp = support
        sl = resistance * 1.005
        direction = "SHORT"

    tp_pct = abs(tp / entry - 1) * 100
    sl_pct = abs(sl / entry - 1) * 100
    rr = tp_pct / sl_pct if sl_pct > 0 else 0

    top3_data.append({
        "symbol": sym, "direction": direction, "entry": entry,
        "tp": tp, "sl": sl, "tp_pct": tp_pct, "sl_pct": sl_pct,
        "rr": rr, "signals": r["signals"], "total": r["total"],
        "breakout": r["breakout"], "reversal": r["reversal"],
        "funding": r["funding"], "buy_pct": r["buy_pct"]
    })

    print(f"\n  #{top3.index(r)+1} {sym} — {direction}")
    print(f"     Score: {r['total']} (breakout={r['breakout']} reversal={r['reversal']})")
    print(f"     Signaux: {', '.join(r['signals'])}")
    print(f"     Entry:   {entry:.6g} USDT")
    print(f"     TP:      {tp:.6g} USDT ({tp_pct:+.2f}%)")
    print(f"     SL:      {sl:.6g} USDT ({sl_pct:.2f}%)")
    print(f"     R:R      {rr:.1f}:1")
    print(f"     OB:      Buy {r['buy_pct']:.0f}%  Funding: {r['funding']:+.4f}%")

# Summary
elapsed = time.time() - START
market_avg = sum(r["chg24"] for r in results) / len(results) if results else 0
bull_count = sum(1 for r in results if r["chg24"] > 0)
bear_count = sum(1 for r in results if r["chg24"] < 0)

print(f"\n  {'='*70}")
print(f"  RESUME MARCHE")
print(f"  {'='*70}")
print(f"  Coins analyses: {len(results)}")
print(f"  Marche: {'BULL' if bull_count > bear_count else 'BEAR'} ({bull_count} hausse / {bear_count} baisse)")
print(f"  Chg24h moyen: {market_avg:+.2f}%")
print(f"  Temps total: {elapsed:.1f}s")

# Save JSON
os.makedirs("F:/BUREAU/TRADING_V2_PRODUCTION/data", exist_ok=True)
out = {
    "timestamp": datetime.now().isoformat(),
    "market": {"bull": bull_count, "bear": bear_count, "avg_chg": market_avg},
    "top3": top3_data,
    "top15_breakout": brk_sorted[:15],
    "top15_reversal": rev_sorted[:15],
    "total_scanned": len(results),
    "elapsed_s": elapsed
}
with open(f"F:/BUREAU/TRADING_V2_PRODUCTION/data/prepump_{datetime.now().strftime('%Y%m%d_%H%M')}.json", "w") as f:
    json.dump(out, f, indent=2, default=str)
print(f"  Rapport sauve dans data/prepump_*.json")
print(f"\n{'='*70}")
