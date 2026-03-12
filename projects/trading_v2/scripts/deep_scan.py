"""Deep scan d'un symbole MEXC Futures — multi-TF + orderbook + liquidite + patterns."""
import json, urllib.request, sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
SYM = sys.argv[1] if len(sys.argv) > 1 else "ALCH_USDT"


def fetch(url, timeout=10):
    try:
        return json.loads(urllib.request.urlopen(url, timeout=timeout).read())
    except Exception as e:
        return {"error": str(e)}


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


def bb(closes, period=20):
    if len(closes) < period:
        return 0, 0, 0
    sma = sum(closes[-period:]) / period
    std = (sum((c - sma) ** 2 for c in closes[-period:]) / period) ** 0.5
    return sma - 2 * std, sma, sma + 2 * std


def bb_width(closes, period=20):
    if len(closes) < period:
        return 99
    sma = sum(closes[-period:]) / period
    std = (sum((c - sma) ** 2 for c in closes[-period:]) / period) ** 0.5
    return (std / sma * 100) if sma > 0 else 99


print(f"{'='*70}")
print(f"  DEEP SCAN — {SYM}")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*70}")

# Ticker
ticker = fetch("https://contract.mexc.com/api/v1/contract/ticker")
coin = None
if ticker and "data" in ticker:
    for t in ticker["data"]:
        if t.get("symbol") == SYM:
            coin = t
            break
if not coin:
    print(f"  ERREUR: {SYM} non trouve")
    sys.exit(1)

price = float(coin.get("lastPrice", 0))
chg24 = float(coin.get("riseFallRate", 0)) * 100
vol24 = float(coin.get("amount24", 0))
high24 = float(coin.get("high24Price", 0))
low24 = float(coin.get("low24Price", 0))
oi = float(coin.get("holdVol", 0))
funding = float(coin.get("fundingRate", 0)) * 100

print(f"\n  PRIX:          {price} USDT")
print(f"  Chg 24h:       {chg24:+.2f}%")
print(f"  High/Low 24h:  {high24} / {low24}")
print(f"  Volume 24h:    {vol24:,.0f} USDT")
print(f"  Open Interest: {oi:,.0f} contrats")
print(f"  Funding Rate:  {funding:+.4f}%")

# Multi-TF
timeframes = [
    ("Min1", 120, "1min"),
    ("Min5", 100, "5min"),
    ("Min15", 100, "15min"),
    ("Min60", 100, "1H"),
    ("Hour4", 100, "4H"),
    ("Day1", 50, "1D"),
]

print(f"\n  {'='*66}")
print(f"  ANALYSE MULTI-TIMEFRAME")
print(f"  {'='*66}")
print(f"  {'TF':<6} {'Close':>10} {'RSI':>6} {'BB_w':>6} {'BB_pos':>7} {'EMA9':>10} {'EMA21':>10} {'EMA50':>10} {'Trend':>7}")

tf_data = {}
for interval, limit, label in timeframes:
    data = fetch(f"https://contract.mexc.com/api/v1/contract/kline/{SYM}?interval={interval}&limit={limit}")
    if not data or "data" not in data or "error" in data:
        print(f"  {label:<6} {'N/A':>10}")
        continue
    d = data["data"]
    closes = [float(x) for x in d.get("close", [])]
    highs = [float(x) for x in d.get("high", [])]
    lows = [float(x) for x in d.get("low", [])]
    vols = [float(x) for x in d.get("vol", [])]
    if not closes:
        continue

    r = rsi(closes)
    bw = bb_width(closes)
    bl, bm, bh = bb(closes)
    bp = (closes[-1] - bl) / (bh - bl) * 100 if (bh - bl) > 0 else 50
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    e50 = ema(closes, 50) if len(closes) >= 50 else 0
    trend = "UP" if closes[-1] > e9 > e21 else ("DOWN" if closes[-1] < e9 < e21 else "MIXED")

    tf_data[label] = {"closes": closes, "vols": vols, "highs": highs, "lows": lows,
                       "rsi": r, "bb_w": bw, "bb_pos": bp, "ema9": e9, "ema21": e21}
    e50_s = f"{e50:>10.6g}" if e50 else f"{'N/A':>10}"
    print(f"  {label:<6} {closes[-1]:>10.6g} {r:>5.1f} {bw:>5.2f}% {bp:>6.1f}% {e9:>10.6g} {e21:>10.6g} {e50_s} {trend:>7}")

# Volume profile
print(f"\n  {'='*66}")
print(f"  VOLUME PROFILE & MOMENTUM")
print(f"  {'='*66}")
for label in ["1min", "5min", "15min", "1H"]:
    if label not in tf_data:
        continue
    vols = tf_data[label]["vols"]
    closes = tf_data[label]["closes"]
    if len(vols) < 12:
        continue
    avg_vol = sum(vols[:-6]) / max(len(vols) - 6, 1)
    recent_vol = sum(vols[-6:]) / 6
    ratio = recent_vol / avg_vol if avg_vol > 0 else 1
    chg_short = (closes[-1] / closes[-6] - 1) * 100 if closes[-6] > 0 else 0
    chg_long = (closes[-1] / closes[-12] - 1) * 100 if len(closes) >= 12 and closes[-12] > 0 else 0
    vol_1st = sum(vols[: len(vols) // 2]) / max(len(vols) // 2, 1)
    vol_2nd = sum(vols[len(vols) // 2 :]) / max(len(vols) - len(vols) // 2, 1)
    vt = "GROWING" if vol_2nd > vol_1st * 1.3 else ("DECLINING" if vol_2nd < vol_1st * 0.7 else "STABLE")
    tag = "SPIKE" if ratio > 3 else ("ELEVATED" if ratio > 1.5 else ("NORMAL" if ratio > 0.5 else "DRY"))
    print(f"  {label}: vol_ratio={ratio:.1f}x [{tag}] mom_short={chg_short:+.3f}% mom_long={chg_long:+.3f}% trend={vt}")

# Orderbook profond
print(f"\n  {'='*66}")
print(f"  ORDERBOOK PROFOND (depth 50)")
print(f"  {'='*66}")
ob = fetch(f"https://contract.mexc.com/api/v1/contract/depth/{SYM}?limit=50")
buy_pct = 50
if ob and "data" in ob:
    dd = ob["data"]
    bids = [(float(b[0]), float(b[1])) for b in dd.get("bids", [])]
    asks = [(float(a[0]), float(a[1])) for a in dd.get("asks", [])]
    total_bids = sum(b[1] for b in bids)
    total_asks = sum(a[1] for a in asks)
    total = total_bids + total_asks
    buy_pct = total_bids / total * 100 if total > 0 else 50
    spread = (asks[0][0] - bids[0][0]) / asks[0][0] * 100 if asks and bids else 0

    print(f"  Buy pressure:  {buy_pct:.1f}% | Sell pressure: {100-buy_pct:.1f}%")
    print(f"  Spread:        {spread:.4f}%")
    print(f"  Total bids:    {total_bids:,.0f} | Total asks: {total_asks:,.0f}")
    if bids:
        print(f"  Best bid:      {bids[0][0]} ({bids[0][1]:,.0f})")
    if asks:
        print(f"  Best ask:      {asks[0][0]} ({asks[0][1]:,.0f})")

    avg_bid = total_bids / len(bids) if bids else 1
    avg_ask = total_asks / len(asks) if asks else 1
    bid_walls = [(p, v) for p, v in bids if v > avg_bid * 2.5]
    ask_walls = [(p, v) for p, v in asks if v > avg_ask * 2.5]

    if bid_walls:
        print(f"\n  BID WALLS (support):")
        for p, v in bid_walls[:6]:
            dist = (price - p) / price * 100
            bar = "#" * min(int(v / avg_bid), 40)
            print(f"    {p:.6g} ({v:>10,.0f}) dist={dist:+.2f}% {bar}")
    if ask_walls:
        print(f"\n  ASK WALLS (resistance):")
        for p, v in ask_walls[:6]:
            dist = (p - price) / price * 100
            bar = "#" * min(int(v / avg_ask), 40)
            print(f"    {p:.6g} ({v:>10,.0f}) dist=+{dist:.2f}% {bar}")

    print(f"\n  IMBALANCE PAR TRANCHE:")
    for pct in [0.25, 0.5, 1.0, 2.0, 3.0, 5.0]:
        b_sum = sum(v for p, v in bids if p >= price * (1 - pct / 100))
        a_sum = sum(v for p, v in asks if p <= price * (1 + pct / 100))
        ratio = b_sum / a_sum if a_sum > 0 else 99
        bias = "BUY" if ratio > 1.3 else ("SELL" if ratio < 0.7 else "NEUTRAL")
        print(f"    {pct:>5.2f}%: bids={b_sum:>10,.0f} asks={a_sum:>10,.0f} ratio={ratio:.2f} [{bias}]")

    # Liquidation clusters
    print(f"\n  LIQUIDATION CLUSTERS (zones 0.5%):")
    zone_size = price * 0.005
    bid_zones, ask_zones = {}, {}
    for p, v in bids:
        z = round(p / zone_size) * zone_size
        bid_zones[z] = bid_zones.get(z, 0) + v
    for p, v in asks:
        z = round(p / zone_size) * zone_size
        ask_zones[z] = ask_zones.get(z, 0) + v
    print(f"    SUPPORT:")
    for z, vol in sorted(bid_zones.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"      {z:.6g} ({vol:>10,.0f}) dist={(price-z)/price*100:+.2f}%")
    print(f"    RESISTANCE:")
    for z, vol in sorted(ask_zones.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"      {z:.6g} ({vol:>10,.0f}) dist=+{(z-price)/price*100:.2f}%")

# Verdict
print(f"\n  {'='*66}")
print(f"  VERDICT TECHNIQUE")
print(f"  {'='*66}")

bull, bear = [], []
squeeze_count = sum(1 for lb in ["15min", "1H", "4H"] if lb in tf_data and tf_data[lb]["bb_w"] < 2.0)
if squeeze_count >= 3:
    bull.append(f"BB SQUEEZE TRIPLE-TF ({squeeze_count}/3)")
elif squeeze_count >= 2:
    bull.append(f"BB SQUEEZE {squeeze_count}/3")
for lb in ["1H", "4H"]:
    if lb in tf_data:
        r = tf_data[lb]["rsi"]
        if r < 30:
            bull.append(f"RSI SURVENDU {lb} ({r:.0f})")
        elif r > 70:
            bear.append(f"RSI SURACHETE {lb} ({r:.0f})")
if buy_pct > 58:
    bull.append(f"ORDERBOOK ACHETEUR ({buy_pct:.0f}%)")
elif buy_pct < 42:
    bear.append(f"ORDERBOOK VENDEUR ({buy_pct:.0f}%)")
if funding < -0.005:
    bull.append(f"FUNDING NEGATIF ({funding:+.4f}%)")
elif funding > 0.01:
    bear.append(f"FUNDING ELEVE ({funding:+.4f}%)")

# Volume spikes
for lb in ["5min", "15min"]:
    if lb in tf_data:
        vols = tf_data[lb]["vols"]
        if len(vols) > 6:
            avg = sum(vols[:-6]) / max(len(vols) - 6, 1)
            recent = sum(vols[-6:]) / 6
            if avg > 0 and recent / avg > 3:
                bull.append(f"VOL SPIKE {lb} ({recent/avg:.0f}x)")

# EMA cross
if "15min" in tf_data:
    td = tf_data["15min"]
    if td["ema9"] > td["ema21"] and td["closes"][-1] > td["ema9"]:
        bull.append("EMA9 > EMA21 (bullish cross 15min)")
    elif td["ema9"] < td["ema21"] and td["closes"][-1] < td["ema9"]:
        bear.append("EMA9 < EMA21 (bearish cross 15min)")

print(f"  BULLISH ({len(bull)}):")
for s in bull:
    print(f"    + {s}")
print(f"  BEARISH ({len(bear)}):")
for s in bear:
    print(f"    - {s}")

verdict = "LONG" if len(bull) > len(bear) + 1 else ("SHORT" if len(bear) > len(bull) + 1 else "NEUTRAL")
print(f"\n  => VERDICT: {verdict}")
print(f"  => Bull/Bear ratio: {len(bull)}/{len(bear)}")
print(f"\n{'='*70}")
print(f"  FIN DEEP SCAN {SYM}")
print(f"{'='*70}")
