"""
JARVIS Scan Sniper v2 — Detecteur pre-pump avance
Analyse TOUS les futures MEXC: breakout, retournement, liquidite, clusters, indicateurs.
Retourne le top 3 avec entry optimal + TP en USDT.

Commande vocale: "scan sniper"
Usage: python scripts/scan_sniper.py [--json] [--top N] [--all] [--min-score N]
"""
import asyncio
import httpx
import sys
import json
import math
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

BASE = "https://contract.mexc.com/api/v1/contract"

# Config
TOP_VOLUME = 100        # Scanner les N coins les plus actifs
MIN_VOL_24H = 500_000   # Volume min 24h en USDT
TP_MULT = 1.5           # TP = ATR * mult
SL_MULT = 1.0           # SL = ATR * mult
MIN_SCORE = 40          # Score min pour retourner un signal


@dataclass
class Signal:
    symbol: str
    direction: str               # LONG ou SHORT
    score: int                   # 0-100
    last_price: float
    entry: float
    tp: float
    sl: float
    strategies: list             # noms des strategies declenchees
    reasons: list                # raisons detaillees
    volume_24h: float
    change_24h: float
    funding_rate: float
    liquidity_bias: str          # bullish / bearish / neutral
    liquidity_clusters: list = field(default_factory=list)
    atr: float = 0.0
    rsi: float = 50.0
    macd_signal: str = ""
    bb_squeeze: bool = False
    regime: str = "unknown"


# ========== FETCH ==========

async def fetch_json(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        r = await client.get(url, timeout=12)
        data = r.json()
        if data.get("success"):
            return data.get("data")
    except Exception:
        pass
    return None


async def get_all_tickers(client: httpx.AsyncClient) -> list[dict]:
    data = await fetch_json(client, f"{BASE}/ticker")
    if not data:
        return []
    # Filtrer USDT futures avec volume minimum
    usdt = [t for t in data if t["symbol"].endswith("_USDT") and t.get("amount24", 0) >= MIN_VOL_24H]
    usdt.sort(key=lambda t: t.get("amount24", 0), reverse=True)
    return usdt[:TOP_VOLUME]


async def get_klines(client: httpx.AsyncClient, symbol: str, interval: str = "Min15", limit: int = 96) -> dict | None:
    return await fetch_json(client, f"{BASE}/kline/{symbol}?interval={interval}&limit={limit}")


async def get_depth(client: httpx.AsyncClient, symbol: str, limit: int = 30) -> dict | None:
    return await fetch_json(client, f"{BASE}/depth/{symbol}?limit={limit}")


# ========== INDICATEURS ==========

def calc_sma(data: list, period: int) -> float:
    if len(data) < period:
        return data[-1] if data else 0
    return sum(data[-period:]) / period


def calc_ema(data: list, period: int) -> list:
    if not data:
        return []
    alpha = 2.0 / (period + 1)
    ema = [data[0]]
    for i in range(1, len(data)):
        ema.append(alpha * data[i] + (1 - alpha) * ema[-1])
    return ema


def calc_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0, diff))
        losses.append(max(0, -diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss < 1e-12:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calc_stoch_rsi(closes: list, rsi_period: int = 14, stoch_period: int = 14) -> float:
    """Stochastic RSI: RSI normalise sur sa propre plage."""
    if len(closes) < rsi_period + stoch_period + 2:
        return 50.0
    rsi_values = []
    for i in range(stoch_period + 1):
        idx = len(closes) - stoch_period - 1 + i
        sub = closes[max(0, idx - rsi_period):idx + 1]
        rsi_values.append(calc_rsi(sub, rsi_period))
    min_rsi = min(rsi_values)
    max_rsi = max(rsi_values)
    if max_rsi - min_rsi < 0.01:
        return 50.0
    return (rsi_values[-1] - min_rsi) / (max_rsi - min_rsi) * 100


def calc_macd(closes: list) -> tuple:
    """MACD (12,26,9). Retourne (macd_line, signal_line, histogram)."""
    if len(closes) < 35:
        return 0, 0, 0
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    macd_line = [ema12[i] - ema26[i] for i in range(len(closes))]
    signal_line = calc_ema(macd_line[26:], 9)
    if not signal_line:
        return 0, 0, 0
    m = macd_line[-1]
    s = signal_line[-1]
    return m, s, m - s


def calc_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 0
    trs = []
    for i in range(-period, 0):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)
    return sum(trs) / period


def calc_bollinger(closes: list, period: int = 20, mult: float = 2.0) -> tuple:
    """Retourne (upper, middle, lower, width_pct)."""
    if len(closes) < period:
        return 0, 0, 0, 0
    window = closes[-period:]
    middle = sum(window) / period
    variance = sum((x - middle) ** 2 for x in window) / period
    std = math.sqrt(variance)
    upper = middle + mult * std
    lower = middle - mult * std
    width_pct = (upper - lower) / middle * 100 if middle > 0 else 0
    return upper, middle, lower, width_pct


def calc_vwap(closes: list, volumes: list, period: int = 20) -> float:
    if len(closes) < period:
        return closes[-1] if closes else 0
    pv = sum(closes[-i] * volumes[-i] for i in range(1, period + 1))
    v = sum(volumes[-period:])
    return pv / v if v > 0 else closes[-1]


# ========== STRATEGIES PRE-PUMP ==========

def analyze_klines_advanced(kdata: dict) -> dict:
    """15+ strategies de detection pre-pump."""
    if not kdata or "close" not in kdata:
        return {"strategies": [], "reasons": [], "score": 0, "trend": "unknown",
                "rsi": 50, "atr": 0, "macd_signal": "", "bb_squeeze": False}

    closes = kdata["close"]
    highs = kdata["high"]
    lows = kdata["low"]
    volumes = kdata["vol"]
    opens = kdata.get("open", closes)
    n = len(closes)
    if n < 30:
        return {"strategies": [], "reasons": [], "score": 0, "trend": "unknown",
                "rsi": 50, "atr": 0, "macd_signal": "", "bb_squeeze": False}

    strategies = []
    reasons = []
    scores = []
    last = closes[-1]
    prev = closes[-2]

    # Indicateurs de base
    sma20 = calc_sma(closes, 20)
    sma50 = calc_sma(closes, 50)
    rsi = calc_rsi(closes, 14)
    stoch_rsi = calc_stoch_rsi(closes)
    macd_val, macd_sig, macd_hist = calc_macd(closes)
    atr = calc_atr(highs, lows, closes, 14)
    bb_up, bb_mid, bb_low, bb_width = calc_bollinger(closes)
    vwap = calc_vwap(closes, volumes)
    avg_vol = sum(volumes[-20:]) / 20
    last_vol = volumes[-1]
    vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1

    # EMA ribbon
    ema8 = calc_ema(closes, 8)[-1]
    ema13 = calc_ema(closes, 13)[-1]
    ema21 = calc_ema(closes, 21)[-1]
    ema55 = calc_ema(closes, 55)[-1] if n >= 55 else sma50

    # Trend
    if last > sma20 > sma50:
        trend = "bullish"
    elif last < sma20 < sma50:
        trend = "bearish"
    elif last > sma20:
        trend = "recovery"
    else:
        trend = "range"

    # --- 1. BREAKOUT RESISTANCE 20P ---
    r20_high = max(highs[-20:])
    r20_low = min(lows[-20:])
    if last > r20_high * 0.998 and vol_ratio > 1.3:
        strategies.append("breakout_resistance")
        reasons.append(f"Casse resistance 20P ({r20_high:.6g}) + vol x{vol_ratio:.1f}")
        scores.append(20)

    # --- 2. BREAKOUT SUPPORT (SHORT) ---
    if last < r20_low * 1.002 and vol_ratio > 1.3:
        strategies.append("breakout_support")
        reasons.append(f"Casse support 20P ({r20_low:.6g}) + vol x{vol_ratio:.1f}")
        scores.append(20)

    # --- 3. VOLUME SPIKE PRE-PUMP ---
    if vol_ratio > 2.0:
        strategies.append("volume_spike")
        reasons.append(f"Volume spike x{vol_ratio:.1f} (pre-pump)")
        scores.append(min(20, int(vol_ratio * 5)))

    # --- 4. VOLUME DRY-UP → EXPANSION ---
    if n >= 10:
        recent_avg = sum(volumes[-5:]) / 5
        older_avg = sum(volumes[-15:-5]) / 10 if n >= 15 else avg_vol
        if older_avg > 0 and recent_avg < older_avg * 0.4 and last_vol > recent_avg * 2:
            strategies.append("volume_dryup_expansion")
            reasons.append("Volume dry-up puis expansion (accumulation → breakout)")
            scores.append(18)

    # --- 5. RSI SURVENDU (retournement) ---
    if rsi < 30:
        strategies.append("rsi_oversold")
        reasons.append(f"RSI survendu ({rsi:.0f}) — retournement probable")
        scores.append(15)

    # --- 6. STOCHASTIC RSI CROSS ---
    if stoch_rsi < 20:
        strategies.append("stoch_rsi_oversold")
        reasons.append(f"Stochastic RSI survendu ({stoch_rsi:.0f})")
        scores.append(12)
    elif stoch_rsi > 80:
        strategies.append("stoch_rsi_overbought")
        reasons.append(f"Stochastic RSI suracheté ({stoch_rsi:.0f})")
        scores.append(8)

    # --- 7. MACD CROSS HAUSSIER ---
    if macd_hist > 0 and n >= 36:
        prev_macd = calc_macd(closes[:-1])
        if prev_macd[2] <= 0:
            strategies.append("macd_bullish_cross")
            reasons.append("MACD cross haussier (signal achat)")
            scores.append(15)

    # --- 8. MACD CROSS BAISSIER ---
    if macd_hist < 0 and n >= 36:
        prev_macd = calc_macd(closes[:-1])
        if prev_macd[2] >= 0:
            strategies.append("macd_bearish_cross")
            reasons.append("MACD cross baissier (signal vente)")
            scores.append(12)

    # --- 9. BOLLINGER SQUEEZE ---
    bb_squeeze = False
    if n >= 40:
        prev_bb = calc_bollinger(closes[:-5])
        if prev_bb[3] > 0 and bb_width < prev_bb[3] * 0.6:
            bb_squeeze = True
            strategies.append("bollinger_squeeze")
            reasons.append(f"Bollinger squeeze ({bb_width:.2f}% < {prev_bb[3]:.2f}%)")
            scores.append(15)

    # --- 10. BOLLINGER BOUNCE ---
    if last < bb_low * 1.005 and trend != "bearish":
        strategies.append("bollinger_bounce_low")
        reasons.append(f"Prix touche bande basse BB ({bb_low:.6g})")
        scores.append(12)
    elif last > bb_up * 0.995 and trend != "bullish":
        strategies.append("bollinger_bounce_high")
        reasons.append(f"Prix touche bande haute BB ({bb_up:.6g})")
        scores.append(8)

    # --- 11. EMA RIBBON STACK (alignement = forte tendance) ---
    if ema8 > ema13 > ema21 > ema55:
        strategies.append("ema_ribbon_bullish")
        reasons.append("EMA ribbon aligné haussier (8>13>21>55)")
        scores.append(12)
    elif ema8 < ema13 < ema21 < ema55:
        strategies.append("ema_ribbon_bearish")
        reasons.append("EMA ribbon aligné baissier (8<13<21<55)")
        scores.append(10)

    # --- 12. EMA55 CROSS (breakout majeur) ---
    if n >= 56:
        prev_ema55 = calc_ema(closes[:-1], 55)[-1]
        if prev < prev_ema55 and last > ema55:
            strategies.append("ema55_cross_up")
            reasons.append(f"Cross EMA55 haussier ({ema55:.6g})")
            scores.append(18)
        elif prev > prev_ema55 and last < ema55:
            strategies.append("ema55_cross_down")
            reasons.append(f"Cross EMA55 baissier ({ema55:.6g})")
            scores.append(15)

    # --- 13. VWAP POSITION ---
    if last > vwap * 1.005 and trend in ("bullish", "recovery"):
        strategies.append("above_vwap")
        reasons.append(f"Prix au-dessus VWAP ({vwap:.6g})")
        scores.append(8)

    # --- 14. HAMMER / REVERSAL ---
    if n >= 3:
        body_last = abs(closes[-1] - opens[-1])
        wick_low = min(closes[-1], opens[-1]) - lows[-1]
        wick_high = highs[-1] - max(closes[-1], opens[-1])

        if wick_low > body_last * 2.5 and body_last > 0:
            strategies.append("hammer")
            reasons.append("Pattern hammer (longue meche basse)")
            scores.append(12 if trend == "bearish" else 6)

        if wick_high > body_last * 2.5 and body_last > 0:
            strategies.append("shooting_star")
            reasons.append("Pattern shooting star (longue meche haute)")
            scores.append(10 if trend == "bullish" else 5)

    # --- 15. ENGULFING ---
    if n >= 3:
        body_prev = abs(closes[-2] - opens[-2])
        body_last = abs(closes[-1] - opens[-1])
        # Bullish engulfing
        if closes[-1] > opens[-1] and closes[-2] < opens[-2] and body_last > body_prev * 1.3:
            strategies.append("bullish_engulfing")
            reasons.append("Engulfing haussier")
            scores.append(14)
        # Bearish engulfing
        elif closes[-1] < opens[-1] and closes[-2] > opens[-2] and body_last > body_prev * 1.3:
            strategies.append("bearish_engulfing")
            reasons.append("Engulfing baissier")
            scores.append(12)

    # --- 16. RANGE COMPRESSION (SQUEEZE PRE-BREAKOUT) ---
    if n >= 20:
        recent_range = max(highs[-5:]) - min(lows[-5:])
        older_range = max(highs[-20:-5]) - min(lows[-20:-5])
        if older_range > 0 and recent_range < older_range * 0.35:
            strategies.append("range_compression")
            reasons.append(f"Compression extreme ({recent_range/older_range:.0%} du range)")
            scores.append(15)

    # --- 17. MOMENTUM ACCELERATION ---
    if n >= 10:
        mom_5 = (closes[-1] - closes[-5]) / closes[-5] * 100
        mom_10 = (closes[-5] - closes[-10]) / closes[-10] * 100
        if mom_5 > 0 and mom_5 > mom_10 * 2 and mom_5 > 1.0:
            strategies.append("momentum_acceleration")
            reasons.append(f"Acceleration momentum ({mom_5:+.2f}% vs {mom_10:+.2f}%)")
            scores.append(12)

    # --- 18. FUNDING RATE DIVERGENCE (via ticker, ajoute dans analyze_pair) ---
    # Gere au niveau du ticker, pas ici

    macd_signal = "bullish" if macd_hist > 0 else "bearish" if macd_hist < 0 else "neutral"

    return {
        "strategies": strategies,
        "reasons": reasons,
        "score": min(100, sum(scores)),
        "trend": trend,
        "rsi": rsi,
        "atr": atr,
        "macd_signal": macd_signal,
        "bb_squeeze": bb_squeeze,
    }


# ========== ANALYSE LIQUIDITE ==========

def analyze_depth_advanced(depth_data: dict, last_price: float) -> dict:
    """Analyse carnet d'ordres: liquidite, clusters, murs, imbalance."""
    if not depth_data:
        return {"bias": "neutral", "clusters": [], "reasons": [], "imbalance": 0}

    bids = depth_data.get("bids", [])
    asks = depth_data.get("asks", [])

    bid_vol = sum(b[1] for b in bids) if bids else 0
    ask_vol = sum(a[1] for a in asks) if asks else 0
    total = bid_vol + ask_vol

    reasons = []
    clusters = []

    # Imbalance
    imbalance = (bid_vol - ask_vol) / total if total > 0 else 0

    if total > 0:
        bid_pct = bid_vol / total
        if bid_pct > 0.65:
            bias = "bullish"
            reasons.append(f"Pression acheteuse forte {bid_pct:.0%}")
        elif bid_pct < 0.35:
            bias = "bearish"
            reasons.append(f"Pression vendeuse forte {1-bid_pct:.0%}")
        elif bid_pct > 0.55:
            bias = "slightly_bullish"
        elif bid_pct < 0.45:
            bias = "slightly_bearish"
        else:
            bias = "neutral"
    else:
        bias = "neutral"

    # Detecter clusters de liquidite (groupes de gros ordres)
    # Bids: niveaux de support potentiels
    for i, b in enumerate(bids[:15]):
        price, vol = b[0], b[1]
        if bid_vol > 0 and vol > bid_vol * 0.10:
            pct_away = (last_price - price) / last_price * 100
            clusters.append({
                "side": "bid",
                "price": price,
                "volume": vol,
                "pct_away": round(pct_away, 2),
            })
            reasons.append(f"Mur bid {price:.6g} ({vol:,.0f} lots, -{pct_away:.1f}%)")

    # Asks: niveaux de resistance potentiels
    for i, a in enumerate(asks[:15]):
        price, vol = a[0], a[1]
        if ask_vol > 0 and vol > ask_vol * 0.10:
            pct_away = (price - last_price) / last_price * 100
            clusters.append({
                "side": "ask",
                "price": price,
                "volume": vol,
                "pct_away": round(pct_away, 2),
            })
            reasons.append(f"Mur ask {price:.6g} ({vol:,.0f} lots, +{pct_away:.1f}%)")

    # Liquidation zones estimation (spread entre clusters)
    if len(clusters) >= 2:
        bid_clusters = [c for c in clusters if c["side"] == "bid"]
        ask_clusters = [c for c in clusters if c["side"] == "ask"]
        if bid_clusters and ask_clusters:
            nearest_support = bid_clusters[0]["price"]
            nearest_resist = ask_clusters[0]["price"]
            gap_pct = (nearest_resist - nearest_support) / last_price * 100
            if gap_pct < 0.5:
                reasons.append(f"Zone de liquidite serree ({gap_pct:.2f}%)")

    return {"bias": bias, "clusters": clusters, "reasons": reasons, "imbalance": imbalance}


# ========== ANALYSE COMPLETE ==========

async def analyze_pair(client: httpx.AsyncClient, ticker: dict) -> Signal | None:
    """Analyse complete multi-indicateurs d'une paire."""
    symbol = ticker["symbol"]

    klines_data, depth_data = await asyncio.gather(
        get_klines(client, symbol, "Min15", 96),
        get_depth(client, symbol, 30),
    )

    kline = analyze_klines_advanced(klines_data)
    last_price = ticker["lastPrice"]
    depth = analyze_depth_advanced(depth_data, last_price)

    all_strategies = list(kline["strategies"])
    all_reasons = list(kline["reasons"]) + depth["reasons"]
    score = kline["score"]

    # Bonus liquidite convergente
    if depth["bias"] in ("bullish", "slightly_bullish") and kline["trend"] in ("bullish", "recovery"):
        score += 10
        all_strategies.append("liquidity_convergence_long")
        all_reasons.append("Liquidite + tendance convergent LONG")
    elif depth["bias"] in ("bearish", "slightly_bearish") and kline["trend"] == "bearish":
        score += 10
        all_strategies.append("liquidity_convergence_short")
        all_reasons.append("Liquidite + tendance convergent SHORT")

    # Bonus extreme imbalance
    if abs(depth["imbalance"]) > 0.4:
        score += 8
        side = "bid" if depth["imbalance"] > 0 else "ask"
        all_strategies.append(f"extreme_imbalance_{side}")
        all_reasons.append(f"Desequilibre extreme carnet ({depth['imbalance']:+.0%})")

    # Funding rate divergence
    funding = ticker.get("fundingRate", 0)
    if funding < -0.0005 and kline["trend"] != "bearish":
        score += 8
        all_strategies.append("negative_funding")
        all_reasons.append(f"Funding negatif ({funding:.6f}) — shorts paieront")
    elif funding > 0.001 and kline["trend"] != "bullish":
        score += 6
        all_strategies.append("high_funding")
        all_reasons.append(f"Funding eleve ({funding:.6f}) — longs paieront")

    # Filtrer signaux trop faibles
    if score < MIN_SCORE or not all_strategies:
        return None

    # Direction
    long_strats = sum(1 for s in all_strategies if any(x in s for x in
        ["bullish", "oversold", "bounce_low", "resistance", "cross_up",
         "hammer", "acceleration", "dryup", "spike", "convergence_long",
         "negative_funding", "above_vwap"]))
    short_strats = sum(1 for s in all_strategies if any(x in s for x in
        ["bearish", "overbought", "bounce_high", "support", "cross_down",
         "shooting_star", "convergence_short", "high_funding"]))

    if long_strats > short_strats:
        direction = "LONG"
    elif short_strats > long_strats:
        direction = "SHORT"
    else:
        direction = "LONG" if ticker.get("riseFallRate", 0) > 0 else "SHORT"

    # Entry / TP / SL dynamiques basees sur ATR
    atr = kline["atr"]
    dec = _price_decimals(last_price)

    if atr > 0:
        if direction == "LONG":
            entry = round(last_price - atr * 0.3, dec)
            tp = round(entry + atr * TP_MULT, dec)
            sl = round(entry - atr * SL_MULT, dec)
        else:
            entry = round(last_price + atr * 0.3, dec)
            tp = round(entry - atr * TP_MULT, dec)
            sl = round(entry + atr * SL_MULT, dec)
    else:
        # Fallback pourcentage
        pct_entry = 0.001
        pct_tp = 0.004
        pct_sl = 0.0025
        if direction == "LONG":
            entry = round(last_price * (1 - pct_entry), dec)
            tp = round(entry * (1 + pct_tp), dec)
            sl = round(entry * (1 - pct_sl), dec)
        else:
            entry = round(last_price * (1 + pct_entry), dec)
            tp = round(entry * (1 - pct_tp), dec)
            sl = round(entry * (1 + pct_sl), dec)

    # Regime
    if score >= 70:
        regime = "strong_signal"
    elif kline["bb_squeeze"]:
        regime = "squeeze"
    elif kline["trend"] in ("bullish", "bearish"):
        regime = "trending"
    else:
        regime = "ranging"

    return Signal(
        symbol=symbol,
        direction=direction,
        score=min(100, score),
        last_price=last_price,
        entry=entry,
        tp=tp,
        sl=sl,
        strategies=all_strategies,
        reasons=all_reasons,
        volume_24h=ticker.get("amount24", 0),
        change_24h=ticker.get("riseFallRate", 0) * 100,
        funding_rate=funding,
        liquidity_bias=depth["bias"],
        liquidity_clusters=depth["clusters"][:4],
        atr=atr,
        rsi=kline["rsi"],
        macd_signal=kline["macd_signal"],
        bb_squeeze=kline["bb_squeeze"],
        regime=regime,
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
    elif price > 0.0001:
        return 7
    else:
        return 10


# ========== SCAN PRINCIPAL ==========

async def scan_sniper(top_n: int = 3, min_score: int = MIN_SCORE) -> list[Signal]:
    """Scan complet: top volume → klines+depth → 18 strategies → top N."""
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=30)) as client:
        print(f"[1/3] Recuperation tickers MEXC Futures...", file=sys.stderr)
        tickers = await get_all_tickers(client)
        if not tickers:
            print("Erreur: aucun ticker MEXC disponible", file=sys.stderr)
            return []
        print(f"[1/3] {len(tickers)} coins (vol > {MIN_VOL_24H:,} USDT)", file=sys.stderr)

        # Analyser par batch de 20 pour eviter rate-limit
        print(f"[2/3] Analyse multi-indicateurs...", file=sys.stderr)
        all_signals = []
        batch_size = 20
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            tasks = [analyze_pair(client, t) for t in batch]
            results = await asyncio.gather(*tasks)
            for s in results:
                if s is not None and s.score >= min_score:
                    all_signals.append(s)
            # Petite pause anti rate-limit
            if i + batch_size < len(tickers):
                await asyncio.sleep(0.3)

        all_signals.sort(key=lambda s: s.score, reverse=True)
        print(f"[3/3] {len(all_signals)} signaux trouves, top {top_n} selectionnes", file=sys.stderr)
        return all_signals[:top_n]


# ========== AFFICHAGE ==========

def format_signal(s: Signal, rank: int) -> str:
    coin = s.symbol.replace("_USDT", "")
    rr = abs(s.tp - s.entry) / abs(s.entry - s.sl) if abs(s.entry - s.sl) > 0 else 0

    lines = [
        "",
        f"{'='*50}",
        f"  #{rank}  {coin}  |  {s.direction}  |  Score {s.score}/100  |  {s.regime.upper()}",
        f"{'='*50}",
        f"  Prix actuel:  {s.last_price} USDT",
        f"  Entree:       {s.entry} USDT",
        f"  TP:           {s.tp} USDT  (R:R {rr:.1f})",
        f"  SL:           {s.sl} USDT",
        f"  ATR:          {s.atr:.6g}",
        f"",
        f"  RSI: {s.rsi:.0f}  |  MACD: {s.macd_signal}  |  BB squeeze: {'OUI' if s.bb_squeeze else 'non'}",
        f"  Var 24h: {s.change_24h:+.2f}%  |  Funding: {s.funding_rate:.6f}  |  Liquidite: {s.liquidity_bias}",
        f"",
        f"  Strategies ({len(s.strategies)}):",
    ]
    for st in s.strategies:
        lines.append(f"    + {st}")
    lines.append(f"")
    lines.append(f"  Raisons:")
    for r in s.reasons:
        lines.append(f"    - {r}")

    if s.liquidity_clusters:
        lines.append(f"")
        lines.append(f"  Clusters de liquidite:")
        for c in s.liquidity_clusters:
            side = "BID" if c["side"] == "bid" else "ASK"
            lines.append(f"    [{side}] {c['price']:.6g} ({c['volume']:,.0f} lots, {c['pct_away']:+.1f}%)")

    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    output_json = "--json" in args
    top_n = 3
    min_score = MIN_SCORE
    for i, a in enumerate(args):
        if a == "--top" and i + 1 < len(args):
            top_n = int(args[i + 1])
        elif a == "--min-score" and i + 1 < len(args):
            min_score = int(args[i + 1])

    t0 = time.time()
    signals = asyncio.run(scan_sniper(top_n=top_n, min_score=min_score))
    elapsed = time.time() - t0

    if output_json:
        out = {
            "signals": [asdict(s) for s in signals],
            "meta": {
                "scan_time_s": round(elapsed, 1),
                "coins_scanned": TOP_VOLUME,
                "signals_found": len(signals),
                "min_score": min_score,
            }
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        if not signals:
            print(f"\nAucun signal >= {min_score}/100 sur les {TOP_VOLUME} coins scannes ({elapsed:.1f}s)")
            return

        print(f"\n{'#'*50}")
        print(f"  SCAN SNIPER MEXC — Top {len(signals)} Pre-Pump")
        print(f"  {TOP_VOLUME} coins scannes en {elapsed:.1f}s")
        print(f"  18 strategies | Liquidite + Clusters + Indicateurs")
        print(f"{'#'*50}")

        for i, s in enumerate(signals, 1):
            print(format_signal(s, i))

        print(f"\n{'='*50}")
        print(f"  Config: Levier 10x | TP ATRx{TP_MULT} | SL ATRx{SL_MULT}")
        print(f"{'='*50}")


if __name__ == "__main__":
    main()
