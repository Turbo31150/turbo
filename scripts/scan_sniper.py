"""
JARVIS Scan Sniper — Detecteur breakout/retournement pre-pump
Analyse les futures MEXC: ticker + klines + depth pour detecter les meilleures opportunites.
Retourne le top 3 avec prix d'entree et TP.

Usage: python scripts/scan_sniper.py [--json] [--pairs N] [--top N]
"""
import asyncio
import httpx
import sys
import json
import math
from dataclasses import dataclass, asdict

BASE = "https://contract.mexc.com/api/v1/contract"
# 10 paires principales
WATCH_PAIRS = [
    "BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "PEPE_USDT",
    "DOGE_USDT", "XRP_USDT", "ADA_USDT", "AVAX_USDT", "LINK_USDT",
]
TP_PCT = 0.004   # 0.4%
SL_PCT = 0.0025  # 0.25%


@dataclass
class Signal:
    symbol: str
    direction: str       # LONG ou SHORT
    score: int           # 0-100
    last_price: float
    entry: float
    tp: float
    sl: float
    reasons: list
    volume_24h: float
    change_24h: float
    funding_rate: float
    liquidity_bias: str  # "bullish" / "bearish" / "neutral"


async def fetch_json(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        r = await client.get(url, timeout=10)
        data = r.json()
        if data.get("success"):
            return data.get("data")
    except Exception:
        pass
    return None


async def get_tickers(client: httpx.AsyncClient) -> list[dict]:
    data = await fetch_json(client, f"{BASE}/ticker")
    if not data:
        return []
    return [t for t in data if t["symbol"] in WATCH_PAIRS]


async def get_klines(client: httpx.AsyncClient, symbol: str, interval: str = "Min15", limit: int = 96) -> dict | None:
    return await fetch_json(client, f"{BASE}/kline/{symbol}?interval={interval}&limit={limit}")


async def get_depth(client: httpx.AsyncClient, symbol: str, limit: int = 20) -> dict | None:
    return await fetch_json(client, f"{BASE}/depth/{symbol}?limit={limit}")


def analyze_klines(kdata: dict) -> dict:
    """Analyse klines pour detecter breakout/retournement."""
    if not kdata or "close" not in kdata:
        return {"breakout": False, "reversal": False, "trend": "unknown", "reasons": []}

    closes = kdata["close"]
    highs = kdata["high"]
    lows = kdata["low"]
    volumes = kdata["vol"]
    n = len(closes)
    if n < 20:
        return {"breakout": False, "reversal": False, "trend": "unknown", "reasons": []}

    reasons = []
    score_parts = []

    # --- SMA 20 & 50 ---
    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-min(50, n):]) / min(50, n)
    last = closes[-1]
    prev = closes[-2] if n > 1 else last

    trend = "bullish" if last > sma20 > sma50 else "bearish" if last < sma20 < sma50 else "range"

    # --- Breakout detection ---
    recent_high = max(highs[-20:])
    recent_low = min(lows[-20:])
    range_size = recent_high - recent_low if recent_high != recent_low else 1

    # Breakout haussier: casse le range haut avec volume
    avg_vol = sum(volumes[-20:]) / 20
    last_vol = volumes[-1]
    vol_surge = last_vol > avg_vol * 1.5

    breakout_up = last > recent_high * 0.998 and vol_surge
    breakout_down = last < recent_low * 1.002 and vol_surge

    if breakout_up:
        reasons.append("Breakout haussier (casse resistance 20 bougies)")
        score_parts.append(25)
    if breakout_down:
        reasons.append("Breakout baissier (casse support 20 bougies)")
        score_parts.append(25)

    # --- Volume surge ---
    if vol_surge:
        ratio = last_vol / avg_vol if avg_vol > 0 else 0
        reasons.append(f"Volume surge x{ratio:.1f}")
        score_parts.append(min(20, int(ratio * 5)))

    # --- RSI approx (14 periodes) ---
    if n >= 15:
        gains, losses = [], []
        for i in range(-14, 0):
            diff = closes[i] - closes[i - 1]
            gains.append(max(0, diff))
            losses.append(max(0, -diff))
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        if avg_loss > 0:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        else:
            rsi = 100

        if rsi < 30:
            reasons.append(f"RSI survendu ({rsi:.0f})")
            score_parts.append(20)
        elif rsi > 70:
            reasons.append(f"RSI suracheté ({rsi:.0f})")
            score_parts.append(15)
        elif 45 < rsi < 55:
            reasons.append(f"RSI neutre ({rsi:.0f})")
    else:
        rsi = 50

    # --- Retournement (hammer/engulfing simplifie) ---
    if n >= 3:
        body_prev = abs(closes[-2] - kdata["open"][-2])
        body_last = abs(closes[-1] - kdata["open"][-1])
        wick_low = min(closes[-1], kdata["open"][-1]) - lows[-1]

        # Hammer: longue meche basse, petit corps
        if wick_low > body_last * 2 and body_last > 0 and trend == "bearish":
            reasons.append("Pattern hammer (retournement potentiel)")
            score_parts.append(15)

        # Engulfing haussier
        if closes[-1] > kdata["open"][-1] and closes[-2] < kdata["open"][-2]:
            if body_last > body_prev * 1.2:
                reasons.append("Engulfing haussier")
                score_parts.append(15)

    # --- Momentum (pente des 5 dernieres bougies) ---
    if n >= 5:
        momentum = (closes[-1] - closes[-5]) / closes[-5] * 100
        if abs(momentum) > 1.5:
            direction = "haussier" if momentum > 0 else "baissier"
            reasons.append(f"Momentum {direction} ({momentum:+.2f}%)")
            score_parts.append(10)

    # --- Compression de range (squeeze) ---
    if n >= 10:
        recent_range = max(highs[-10:]) - min(lows[-10:])
        older_range = max(highs[-20:-10]) - min(lows[-20:-10]) if n >= 20 else recent_range
        if older_range > 0 and recent_range < older_range * 0.5:
            reasons.append("Compression de range (squeeze pre-breakout)")
            score_parts.append(15)

    return {
        "breakout": breakout_up or breakout_down,
        "breakout_direction": "LONG" if breakout_up else "SHORT" if breakout_down else None,
        "reversal": "hammer" in " ".join(reasons).lower() or "engulfing" in " ".join(reasons).lower(),
        "trend": trend,
        "rsi": rsi,
        "vol_surge": vol_surge,
        "reasons": reasons,
        "score": min(100, sum(score_parts)),
    }


def analyze_depth(depth_data: dict) -> dict:
    """Analyse le carnet d'ordres pour la pression achat/vente."""
    if not depth_data:
        return {"bias": "neutral", "bid_wall": 0, "ask_wall": 0, "reasons": []}

    bids = depth_data.get("bids", [])
    asks = depth_data.get("asks", [])

    bid_vol = sum(b[1] for b in bids[:20]) if bids else 0
    ask_vol = sum(a[1] for a in asks[:20]) if asks else 0
    total = bid_vol + ask_vol

    reasons = []
    if total > 0:
        bid_pct = bid_vol / total
        if bid_pct > 0.6:
            bias = "bullish"
            reasons.append(f"Pression acheteuse {bid_pct:.0%} (bid wall)")
        elif bid_pct < 0.4:
            bias = "bearish"
            reasons.append(f"Pression vendeuse {1-bid_pct:.0%} (ask wall)")
        else:
            bias = "neutral"
    else:
        bias = "neutral"

    # Detecter clusters de liquidite (gros ordres)
    for b in bids[:10]:
        if b[1] > bid_vol * 0.15:
            reasons.append(f"Cluster bid a {b[0]} ({b[1]:,.0f} lots)")
            break
    for a in asks[:10]:
        if a[1] > ask_vol * 0.15:
            reasons.append(f"Cluster ask a {a[0]} ({a[1]:,.0f} lots)")
            break

    return {"bias": bias, "bid_vol": bid_vol, "ask_vol": ask_vol, "reasons": reasons}


async def analyze_pair(client: httpx.AsyncClient, ticker: dict) -> Signal | None:
    """Analyse complete d'une paire: klines + depth -> score + signal."""
    symbol = ticker["symbol"]

    # Fetch klines 15min (24h = 96 bougies) et depth en parallele
    klines_data, depth_data = await asyncio.gather(
        get_klines(client, symbol, "Min15", 96),
        get_depth(client, symbol, 20),
    )

    kline_analysis = analyze_klines(klines_data)
    depth_analysis = analyze_depth(depth_data)

    # Fusionner les raisons
    all_reasons = kline_analysis["reasons"] + depth_analysis["reasons"]

    # Score composite
    score = kline_analysis["score"]
    if depth_analysis["bias"] == "bullish" and kline_analysis["trend"] != "bearish":
        score += 10
    elif depth_analysis["bias"] == "bearish" and kline_analysis["trend"] != "bullish":
        score += 10

    if not all_reasons:
        return None

    # Direction
    if kline_analysis.get("breakout_direction"):
        direction = kline_analysis["breakout_direction"]
    elif kline_analysis["trend"] == "bullish" or depth_analysis["bias"] == "bullish":
        direction = "LONG"
    elif kline_analysis["trend"] == "bearish" or depth_analysis["bias"] == "bearish":
        direction = "SHORT"
    else:
        direction = "LONG" if ticker["riseFallRate"] > 0 else "SHORT"

    last_price = ticker["lastPrice"]

    # Prix d'entree optimal: leger retrait du prix actuel
    if direction == "LONG":
        entry = round(last_price * 0.999, _price_decimals(last_price))  # -0.1%
        tp = round(entry * (1 + TP_PCT), _price_decimals(last_price))
        sl = round(entry * (1 - SL_PCT), _price_decimals(last_price))
    else:
        entry = round(last_price * 1.001, _price_decimals(last_price))  # +0.1%
        tp = round(entry * (1 - TP_PCT), _price_decimals(last_price))
        sl = round(entry * (1 + SL_PCT), _price_decimals(last_price))

    return Signal(
        symbol=symbol,
        direction=direction,
        score=score,
        last_price=last_price,
        entry=entry,
        tp=tp,
        sl=sl,
        reasons=all_reasons,
        volume_24h=ticker["amount24"],
        change_24h=ticker["riseFallRate"] * 100,
        funding_rate=ticker["fundingRate"],
        liquidity_bias=depth_analysis["bias"],
    )


def _price_decimals(price: float) -> int:
    if price > 1000:
        return 1
    elif price > 10:
        return 2
    elif price > 1:
        return 3
    elif price > 0.01:
        return 5
    else:
        return 8


async def scan_sniper(top_n: int = 3, all_pairs: bool = False) -> list[Signal]:
    """Scan complet: ticker -> filtre -> klines+depth -> score -> top N."""
    async with httpx.AsyncClient() as client:
        tickers = await get_tickers(client)
        if not tickers:
            print("Erreur: impossible de recuperer les tickers MEXC", file=sys.stderr)
            return []

        # Analyser toutes les paires en parallele
        tasks = [analyze_pair(client, t) for t in tickers]
        results = await asyncio.gather(*tasks)

        # Filtrer et trier par score
        signals = [s for s in results if s is not None and s.score > 0]
        signals.sort(key=lambda s: s.score, reverse=True)

        return signals[:top_n]


def format_signal(s: Signal, rank: int) -> str:
    coin = s.symbol.replace("_USDT", "")
    lines = [
        "-" * 40,
        f"#{rank} {coin} | {s.direction} | Score {s.score}/100",
        f"  Prix actuel: {s.last_price} USDT",
        f"  Entree:      {s.entry} USDT",
        f"  TP:          {s.tp} USDT ({'+' if s.direction == 'LONG' else '-'}{TP_PCT*100:.1f}%)",
        f"  SL:          {s.sl} USDT ({'-' if s.direction == 'LONG' else '+'}{SL_PCT*100:.2f}%)",
        f"  Variation 24h: {s.change_24h:+.2f}%",
        f"  Funding:     {s.funding_rate:.6f}",
        f"  Liquidite:   {s.liquidity_bias}",
        f"  Raisons:",
    ]
    for r in s.reasons:
        lines.append(f"    - {r}")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    output_json = "--json" in args
    top_n = 3
    for i, a in enumerate(args):
        if a == "--top" and i + 1 < len(args):
            top_n = int(args[i + 1])

    signals = asyncio.run(scan_sniper(top_n=top_n))

    if output_json:
        print(json.dumps([asdict(s) for s in signals], indent=2, ensure_ascii=False))
    else:
        if not signals:
            print("Aucun signal detecte sur les 10 paires surveillees.")
            return

        print(f"SCAN SNIPER MEXC - Top {len(signals)} Opportunites")
        print("=" * 40)
        for i, s in enumerate(signals, 1):
            print(format_signal(s, i))
        print("-" * 40)
        print(f"Config: Levier 10x | TP {TP_PCT*100:.1f}% | SL {SL_PCT*100:.2f}% | Taille 10 USDT")


if __name__ == "__main__":
    main()
