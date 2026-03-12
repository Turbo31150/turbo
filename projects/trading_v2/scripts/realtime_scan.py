"""Scan temps reel MEXC Futures — rafraichissement toutes les 30s."""
import json, urllib.request, sys, time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
SYM = sys.argv[1] if len(sys.argv) > 1 else "ALCH_USDT"
INTERVAL = int(sys.argv[2]) if len(sys.argv) > 2 else 30
CLEAR = "\033[2J\033[H"


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


prev_price = None
prev_rsi_1h = None
prev_buy_pct = None
alerts = []
cycle = 0
start_price = None

try:
    while True:
        cycle += 1
        now = datetime.now().strftime("%H:%M:%S")

        # Ticker
        ticker = fetch("https://contract.mexc.com/api/v1/contract/ticker")
        coin = None
        if ticker and "data" in ticker:
            for t in ticker["data"]:
                if t.get("symbol") == SYM:
                    coin = t
                    break
        if not coin:
            print(f"[{now}] ERREUR: {SYM} non trouve")
            time.sleep(INTERVAL)
            continue

        price = float(coin.get("lastPrice", 0))
        chg24 = float(coin.get("riseFallRate", 0)) * 100
        vol24 = float(coin.get("amount24", 0))
        oi = float(coin.get("holdVol", 0))
        funding = float(coin.get("fundingRate", 0)) * 100

        if start_price is None:
            start_price = price

        chg_session = (price / start_price - 1) * 100 if start_price > 0 else 0

        # Klines multi-TF
        alerts_now = []
        tf_results = {}
        for interval, limit, label in [("Min5", 60, "5m"), ("Min15", 60, "15m"), ("Min60", 60, "1H"), ("Hour4", 60, "4H")]:
            data = fetch(f"https://contract.mexc.com/api/v1/contract/kline/{SYM}?interval={interval}&limit={limit}")
            if not data or "data" not in data or "error" in data:
                continue
            d = data["data"]
            closes = [float(x) for x in d.get("close", [])]
            vols = [float(x) for x in d.get("vol", [])]
            if not closes:
                continue
            r = rsi(closes)
            bw = bb_width(closes)
            bl, bm, bh = bb(closes)
            bp = (closes[-1] - bl) / (bh - bl) * 100 if (bh - bl) > 0 else 50
            e9 = ema(closes, 9)
            e21 = ema(closes, 21)
            trend = "UP" if closes[-1] > e9 > e21 else ("DOWN" if closes[-1] < e9 < e21 else "MIX")

            avg_vol = sum(vols[:-6]) / max(len(vols) - 6, 1) if len(vols) > 6 else 1
            recent_vol = sum(vols[-3:]) / 3 if len(vols) >= 3 else 0
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1

            tf_results[label] = {
                "rsi": r, "bb_w": bw, "bb_pos": bp, "ema9": e9, "ema21": e21,
                "trend": trend, "vol_ratio": vol_ratio, "close": closes[-1]
            }

        # Orderbook
        ob = fetch(f"https://contract.mexc.com/api/v1/contract/depth/{SYM}?limit=30")
        buy_pct = 50
        spread = 0
        if ob and "data" in ob:
            dd = ob["data"]
            bids = [(float(b[0]), float(b[1])) for b in dd.get("bids", [])]
            asks = [(float(a[0]), float(a[1])) for a in dd.get("asks", [])]
            total_bids = sum(b[1] for b in bids)
            total_asks = sum(a[1] for a in asks)
            total = total_bids + total_asks
            buy_pct = total_bids / total * 100 if total > 0 else 50
            spread = (asks[0][0] - bids[0][0]) / asks[0][0] * 100 if asks and bids else 0

        # Alerts detection
        if prev_price is not None:
            chg = (price / prev_price - 1) * 100
            if abs(chg) > 0.5:
                alerts_now.append(f"MOVE {chg:+.2f}% en {INTERVAL}s")

        if "1H" in tf_results:
            r1h = tf_results["1H"]["rsi"]
            if r1h < 25:
                alerts_now.append(f"RSI 1H SURVENDU ({r1h:.0f})")
            elif r1h > 75:
                alerts_now.append(f"RSI 1H SURACHETE ({r1h:.0f})")
            if prev_rsi_1h is not None:
                if prev_rsi_1h < 30 and r1h >= 30:
                    alerts_now.append("RSI 1H SORT DE SURVENTE")
                if prev_rsi_1h > 70 and r1h <= 70:
                    alerts_now.append("RSI 1H SORT DE SURACHAT")
            prev_rsi_1h = r1h

        if prev_buy_pct is not None:
            if buy_pct > 60 and prev_buy_pct <= 60:
                alerts_now.append(f"OB BASCULE ACHETEUR ({buy_pct:.0f}%)")
            elif buy_pct < 40 and prev_buy_pct >= 40:
                alerts_now.append(f"OB BASCULE VENDEUR ({buy_pct:.0f}%)")

        squeeze_tfs = [lb for lb in ["15m", "1H", "4H"] if lb in tf_results and tf_results[lb]["bb_w"] < 2.0]
        if len(squeeze_tfs) >= 2:
            alerts_now.append(f"BB SQUEEZE {'/'.join(squeeze_tfs)}")

        for lb in ["1H"]:
            if lb in tf_results:
                td = tf_results[lb]
                if td["ema9"] > td["ema21"] and td["close"] > td["ema9"]:
                    alerts_now.append(f"BULLISH CROSS {lb}")

        for lb in ["5m", "15m"]:
            if lb in tf_results and tf_results[lb]["vol_ratio"] > 5:
                alerts_now.append(f"VOL SPIKE {lb} ({tf_results[lb]['vol_ratio']:.0f}x)")

        prev_price = price
        prev_buy_pct = buy_pct

        # Scoring
        bull, bear = 0, 0
        if len(squeeze_tfs) >= 2:
            bull += 2
        for lb in ["1H", "4H"]:
            if lb in tf_results:
                if tf_results[lb]["rsi"] < 30:
                    bull += 1
                elif tf_results[lb]["rsi"] > 70:
                    bear += 1
        if buy_pct > 58:
            bull += 1
        elif buy_pct < 42:
            bear += 1
        if funding < -0.005:
            bull += 1
        elif funding > 0.01:
            bear += 1
        for lb in ["5m", "15m"]:
            if lb in tf_results and tf_results[lb]["vol_ratio"] > 3:
                bull += 1

        verdict = "LONG" if bull > bear + 1 else ("SHORT" if bear > bull + 1 else "NEUTRAL")

        # Display
        print(CLEAR, end="")
        print(f"{'='*72}")
        print(f"  REALTIME SCAN — {SYM} — Cycle #{cycle}")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Refresh: {INTERVAL}s")
        print(f"{'='*72}")

        print(f"\n  PRIX:     {price} USDT   chg24h: {chg24:+.2f}%   session: {chg_session:+.3f}%")
        print(f"  Vol24h:   {vol24:,.0f} USDT   OI: {oi:,.0f}   Funding: {funding:+.4f}%")
        print(f"  OB:       Buy {buy_pct:.0f}% / Sell {100-buy_pct:.0f}%   Spread: {spread:.4f}%")

        print(f"\n  {'TF':<5} {'Price':>10} {'RSI':>6} {'BB_w':>6} {'BB%':>6} {'EMA9':>10} {'Trend':>5} {'Vol':>6}")
        print(f"  {'-'*60}")
        for lb in ["5m", "15m", "1H", "4H"]:
            if lb in tf_results:
                t = tf_results[lb]
                vr = f"{t['vol_ratio']:.1f}x"
                flag = "*" if t["rsi"] < 30 or t["rsi"] > 70 else " "
                print(f"  {lb:<5} {t['close']:>10.6g} {t['rsi']:>5.1f}{flag} {t['bb_w']:>5.2f}% {t['bb_pos']:>5.1f}% {t['ema9']:>10.6g} {t['trend']:>5} {vr:>6}")

        print(f"\n  VERDICT: {verdict}  (Bull {bull} / Bear {bear})")

        if alerts_now:
            print(f"\n  {'!'*50}")
            print(f"  ALERTES:")
            for a in alerts_now:
                print(f"    >> {a}")
            print(f"  {'!'*50}")
            alerts.extend([(now, a) for a in alerts_now])

        if alerts:
            print(f"\n  HISTORIQUE ALERTES (last 10):")
            for ts, a in alerts[-10:]:
                print(f"    [{ts}] {a}")

        print(f"\n  [Ctrl+C pour arreter]", flush=True)

        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print(f"\n\n  Scan arrete apres {cycle} cycles.")
    print(f"  Prix debut: {start_price}  |  Prix fin: {price}")
    if start_price and price:
        print(f"  Performance session: {(price/start_price-1)*100:+.3f}%")
    if alerts:
        print(f"  {len(alerts)} alertes generees.")
