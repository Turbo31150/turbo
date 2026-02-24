"""
JARVIS Scan Sniper v3 — Detecteur pre-pump ultra-avance
30+ strategies: Chaikin, CMF, OBV, ADL, MFI, Williams %R, ADX,
Volume Profile, orderbook minutieux (gradient, absorption, spoofing, voids).

Commande vocale: "scan sniper"
Usage: python scripts/scan_sniper.py [--json] [--top N] [--min-score N]
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
TOP_VOLUME = 100
MIN_VOL_24H = 500_000
TP_MULT = 1.5
SL_MULT = 1.0
MIN_SCORE = 40


@dataclass
class Signal:
    symbol: str
    direction: str
    score: int
    last_price: float
    entry: float
    tp: float
    sl: float
    strategies: list
    reasons: list
    volume_24h: float
    change_24h: float
    funding_rate: float
    liquidity_bias: str
    liquidity_clusters: list = field(default_factory=list)
    ob_analysis: dict = field(default_factory=dict)
    atr: float = 0.0
    rsi: float = 50.0
    chaikin_osc: float = 0.0
    cmf: float = 0.0
    obv_trend: str = ""
    mfi: float = 50.0
    williams_r: float = -50.0
    adx: float = 0.0
    macd_signal: str = ""
    bb_squeeze: bool = False
    regime: str = "unknown"
    open_interest_chg: float = 0.0


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
    usdt = [t for t in data if t["symbol"].endswith("_USDT") and t.get("amount24", 0) >= MIN_VOL_24H]
    usdt.sort(key=lambda t: t.get("amount24", 0), reverse=True)
    return usdt[:TOP_VOLUME]


async def get_klines(client, symbol, interval="Min15", limit=96):
    return await fetch_json(client, f"{BASE}/kline/{symbol}?interval={interval}&limit={limit}")


async def get_depth(client, symbol, limit=50):
    return await fetch_json(client, f"{BASE}/depth/{symbol}?limit={limit}")


async def get_open_interest(client, symbol):
    return await fetch_json(client, f"{BASE}/open_interest/{symbol}")


# ========== INDICATEURS CLASSIQUES ==========

def calc_sma(data, period):
    if len(data) < period:
        return data[-1] if data else 0
    return sum(data[-period:]) / period


def calc_ema(data, period):
    if not data:
        return []
    alpha = 2.0 / (period + 1)
    ema = [data[0]]
    for i in range(1, len(data)):
        ema.append(alpha * data[i] + (1 - alpha) * ema[-1])
    return ema


def calc_rsi(closes, period=14):
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
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def calc_stoch_rsi(closes, rsi_period=14, stoch_period=14):
    if len(closes) < rsi_period + stoch_period + 2:
        return 50.0
    rsi_values = []
    for i in range(stoch_period + 1):
        idx = len(closes) - stoch_period - 1 + i
        sub = closes[max(0, idx - rsi_period):idx + 1]
        rsi_values.append(calc_rsi(sub, rsi_period))
    mn, mx = min(rsi_values), max(rsi_values)
    if mx - mn < 0.01:
        return 50.0
    return (rsi_values[-1] - mn) / (mx - mn) * 100


def calc_macd(closes):
    if len(closes) < 35:
        return 0, 0, 0
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    macd_line = [ema12[i] - ema26[i] for i in range(len(closes))]
    sig = calc_ema(macd_line[26:], 9)
    if not sig:
        return 0, 0, 0
    return macd_line[-1], sig[-1], macd_line[-1] - sig[-1]


def calc_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return 0
    trs = []
    for i in range(-period, 0):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return sum(trs) / period


def calc_bollinger(closes, period=20, mult=2.0):
    if len(closes) < period:
        return 0, 0, 0, 0
    w = closes[-period:]
    mid = sum(w) / period
    std = math.sqrt(sum((x - mid) ** 2 for x in w) / period)
    up = mid + mult * std
    lo = mid - mult * std
    return up, mid, lo, (up - lo) / mid * 100 if mid > 0 else 0


def calc_vwap(closes, volumes, period=20):
    if len(closes) < period:
        return closes[-1] if closes else 0
    pv = sum(closes[-i] * volumes[-i] for i in range(1, period + 1))
    v = sum(volumes[-period:])
    return pv / v if v > 0 else closes[-1]


# ========== NOUVEAUX INDICATEURS AVANCES ==========

def calc_adl(highs, lows, closes, volumes):
    """Accumulation/Distribution Line — flux de capitaux."""
    adl = [0.0]
    for i in range(len(closes)):
        hl = highs[i] - lows[i]
        if hl > 0:
            mfm = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / hl
        else:
            mfm = 0
        mfv = mfm * volumes[i]
        adl.append(adl[-1] + mfv)
    return adl[1:]


def calc_chaikin_oscillator(highs, lows, closes, volumes):
    """Chaikin Oscillator = EMA(3, ADL) - EMA(10, ADL).
    Positif = accumulation (inflow), Negatif = distribution (outflow)."""
    adl = calc_adl(highs, lows, closes, volumes)
    if len(adl) < 10:
        return 0.0, adl
    ema3 = calc_ema(adl, 3)
    ema10 = calc_ema(adl, 10)
    return ema3[-1] - ema10[-1], adl


def calc_cmf(highs, lows, closes, volumes, period=20):
    """Chaikin Money Flow — pression achat/vente normalisee [-1, +1].
    >0 = inflow dominant, <0 = outflow dominant."""
    n = len(closes)
    if n < period:
        return 0.0
    mfv_sum = 0
    vol_sum = 0
    for i in range(n - period, n):
        hl = highs[i] - lows[i]
        if hl > 0:
            mfm = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / hl
        else:
            mfm = 0
        mfv_sum += mfm * volumes[i]
        vol_sum += volumes[i]
    return mfv_sum / vol_sum if vol_sum > 0 else 0.0


def calc_obv(closes, volumes):
    """On-Balance Volume — proxy inflow/outflow cumulatif."""
    obv = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    return obv


def calc_obv_trend(closes, volumes, period=20):
    """Tendance OBV: divergence prix vs OBV = signal fort."""
    obv = calc_obv(closes, volumes)
    if len(obv) < period:
        return "neutral", 0
    obv_slope = (obv[-1] - obv[-period]) / (abs(obv[-period]) + 1e-12)
    price_slope = (closes[-1] - closes[-period]) / (closes[-period] + 1e-12)
    if obv_slope > 0.05 and price_slope < -0.01:
        return "bullish_divergence", obv_slope
    elif obv_slope < -0.05 and price_slope > 0.01:
        return "bearish_divergence", obv_slope
    elif obv_slope > 0.05:
        return "accumulation", obv_slope
    elif obv_slope < -0.05:
        return "distribution", obv_slope
    return "neutral", obv_slope


def calc_mfi(highs, lows, closes, volumes, period=14):
    """Money Flow Index — RSI pondere par le volume [0-100].
    <20 = survendu, >80 = suracheté."""
    n = len(closes)
    if n < period + 1:
        return 50.0
    tp = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]
    pos_flow = 0
    neg_flow = 0
    for i in range(n - period, n):
        mf = tp[i] * volumes[i]
        if tp[i] > tp[i - 1]:
            pos_flow += mf
        else:
            neg_flow += mf
    if neg_flow < 1e-12:
        return 100.0 if pos_flow > 0 else 50.0
    ratio = pos_flow / neg_flow
    return 100.0 - (100.0 / (1.0 + ratio))


def calc_williams_r(highs, lows, closes, period=14):
    """Williams %R [-100, 0]. <-80 = survendu, >-20 = suracheté."""
    if len(closes) < period:
        return -50.0
    hh = max(highs[-period:])
    ll = min(lows[-period:])
    if hh == ll:
        return -50.0
    return -100 * (hh - closes[-1]) / (hh - ll)


def calc_adx(highs, lows, closes, period=14):
    """Average Directional Index — force de tendance [0-100].
    >25 = tendance forte, <20 = range."""
    n = len(closes)
    if n < period * 2:
        return 0.0
    plus_dm = []
    minus_dm = []
    tr_list = []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_list.append(tr)

    if len(tr_list) < period:
        return 0.0

    atr_val = sum(tr_list[:period]) / period
    plus_di_smooth = sum(plus_dm[:period]) / period
    minus_di_smooth = sum(minus_dm[:period]) / period

    alpha = 1.0 / period
    for i in range(period, len(tr_list)):
        atr_val = atr_val * (1 - alpha) + tr_list[i] * alpha
        plus_di_smooth = plus_di_smooth * (1 - alpha) + plus_dm[i] * alpha
        minus_di_smooth = minus_di_smooth * (1 - alpha) + minus_dm[i] * alpha

    if atr_val < 1e-12:
        return 0.0
    plus_di = 100 * plus_di_smooth / atr_val
    minus_di = 100 * minus_di_smooth / atr_val
    di_sum = plus_di + minus_di
    if di_sum < 1e-12:
        return 0.0
    dx = 100 * abs(plus_di - minus_di) / di_sum
    return dx


def calc_volume_profile_poc(closes, volumes, bins=20):
    """Volume Profile: Point of Control (prix avec le plus de volume echange).
    Retourne (poc_price, concentration_pct)."""
    if not closes or not volumes:
        return 0, 0
    mn, mx = min(closes), max(closes)
    if mx == mn:
        return closes[-1], 100
    bin_size = (mx - mn) / bins
    vol_bins = [0.0] * bins
    for i in range(len(closes)):
        idx = min(int((closes[i] - mn) / bin_size), bins - 1)
        vol_bins[idx] += volumes[i]
    max_idx = vol_bins.index(max(vol_bins))
    poc = mn + (max_idx + 0.5) * bin_size
    total_vol = sum(vol_bins)
    concentration = vol_bins[max_idx] / total_vol * 100 if total_vol > 0 else 0
    return poc, concentration


# ========== ORDERBOOK ULTRA-DETAILLE ==========

def analyze_depth_ultra(depth_data: dict, last_price: float) -> dict:
    """Analyse minutieuse du carnet d'ordres: gradient, absorption,
    spoofing, voids, clusters, heatmap, spread."""
    default = {"bias": "neutral", "clusters": [], "reasons": [], "imbalance": 0,
               "spread_pct": 0, "gradient_score": 0, "absorption": "none",
               "spoofing_risk": False, "void_zones": [], "ob_score": 0}
    if not depth_data:
        return default

    bids = depth_data.get("bids", [])
    asks = depth_data.get("asks", [])
    if not bids or not asks:
        return default

    bid_vol = sum(b[1] for b in bids)
    ask_vol = sum(a[1] for a in asks)
    total = bid_vol + ask_vol
    reasons = []
    clusters = []
    ob_score = 0

    # --- 1. Imbalance global ---
    imbalance = (bid_vol - ask_vol) / total if total > 0 else 0

    if total > 0:
        bid_pct = bid_vol / total
        if bid_pct > 0.70:
            bias = "strong_bullish"
            reasons.append(f"Imbalance OB tres forte achat {bid_pct:.0%}")
            ob_score += 15
        elif bid_pct > 0.60:
            bias = "bullish"
            reasons.append(f"Pression acheteuse {bid_pct:.0%}")
            ob_score += 8
        elif bid_pct < 0.30:
            bias = "strong_bearish"
            reasons.append(f"Imbalance OB tres forte vente {1-bid_pct:.0%}")
            ob_score += 15
        elif bid_pct < 0.40:
            bias = "bearish"
            reasons.append(f"Pression vendeuse {1-bid_pct:.0%}")
            ob_score += 8
        else:
            bias = "neutral"
    else:
        bias = "neutral"

    # --- 2. Spread analysis ---
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    spread = best_ask - best_bid
    spread_pct = spread / last_price * 100 if last_price > 0 else 0
    if spread_pct < 0.02:
        reasons.append(f"Spread ultra-serré ({spread_pct:.4f}%) — liquidite haute")
        ob_score += 5
    elif spread_pct > 0.1:
        reasons.append(f"Spread large ({spread_pct:.3f}%) — liquidite faible")
        ob_score -= 3

    # --- 3. Gradient de liquidite (distribution par niveaux) ---
    # Bid gradient: compare top 5 vs bottom 5 niveaux
    bid_top5 = sum(b[1] for b in bids[:5]) if len(bids) >= 5 else bid_vol
    bid_bot5 = sum(b[1] for b in bids[-5:]) if len(bids) >= 10 else 0
    ask_top5 = sum(a[1] for a in asks[:5]) if len(asks) >= 5 else ask_vol
    ask_bot5 = sum(a[1] for a in asks[-5:]) if len(asks) >= 10 else 0

    # Front-loaded bids = support fort immédiat
    gradient_score = 0
    if bid_vol > 0 and bid_top5 > bid_vol * 0.5:
        gradient_score += 2
        reasons.append(f"Bids concentres pres du prix ({bid_top5/bid_vol:.0%} dans top 5)")
    if ask_vol > 0 and ask_top5 > ask_vol * 0.5:
        gradient_score -= 2
        reasons.append(f"Asks concentres pres du prix ({ask_top5/ask_vol:.0%} dans top 5)")

    # --- 4. Detection murs (walls) + clusters ---
    avg_bid_size = bid_vol / len(bids) if bids else 0
    avg_ask_size = ask_vol / len(asks) if asks else 0

    for b in bids[:20]:
        price, vol = b[0], b[1]
        if avg_bid_size > 0 and vol > avg_bid_size * 4:
            pct = (last_price - price) / last_price * 100
            clusters.append({"side": "bid", "price": price, "volume": vol,
                             "pct_away": round(pct, 2), "type": "wall"})
            reasons.append(f"MUR BID {price:.6g} ({vol:,.0f} lots, -{pct:.2f}%) — 4x moyenne")
            ob_score += 5

    for a in asks[:20]:
        price, vol = a[0], a[1]
        if avg_ask_size > 0 and vol > avg_ask_size * 4:
            pct = (price - last_price) / last_price * 100
            clusters.append({"side": "ask", "price": price, "volume": vol,
                             "pct_away": round(pct, 2), "type": "wall"})
            reasons.append(f"MUR ASK {price:.6g} ({vol:,.0f} lots, +{pct:.2f}%) — 4x moyenne")
            ob_score += 5

    # --- 5. Detection absorption (gros volume pres du prix qui "absorbe") ---
    absorption = "none"
    if bids and avg_bid_size > 0:
        top3_bid_vol = sum(b[1] for b in bids[:3])
        if top3_bid_vol > bid_vol * 0.40:
            absorption = "bid_absorption"
            reasons.append(f"Absorption BID: top 3 = {top3_bid_vol/bid_vol:.0%} du total (buyers absorbent)")
            ob_score += 8
    if asks and avg_ask_size > 0:
        top3_ask_vol = sum(a[1] for a in asks[:3])
        if top3_ask_vol > ask_vol * 0.40:
            if absorption == "bid_absorption":
                absorption = "both"
            else:
                absorption = "ask_absorption"
            reasons.append(f"Absorption ASK: top 3 = {top3_ask_vol/ask_vol:.0%} du total (sellers absorbent)")
            ob_score += 8

    # --- 6. Detection spoofing (ordres suspects: tres gros, tres loin) ---
    spoofing_risk = False
    for b in bids[10:]:
        if avg_bid_size > 0 and b[1] > avg_bid_size * 8:
            pct = (last_price - b[0]) / last_price * 100
            if pct > 1.0:
                spoofing_risk = True
                reasons.append(f"SPOOFING suspect: bid {b[0]:.6g} ({b[1]:,.0f}x, -{pct:.1f}%) — 8x moyenne, loin du prix")
                break
    for a in asks[10:]:
        if avg_ask_size > 0 and a[1] > avg_ask_size * 8:
            pct = (a[0] - last_price) / last_price * 100
            if pct > 1.0:
                spoofing_risk = True
                reasons.append(f"SPOOFING suspect: ask {a[0]:.6g} ({a[1]:,.0f}x, +{pct:.1f}%) — 8x moyenne, loin du prix")
                break

    # --- 7. Detection voids (zones sans liquidite = gaps exploitables) ---
    void_zones = []
    for i in range(1, min(15, len(bids))):
        gap_pct = (bids[i - 1][0] - bids[i][0]) / last_price * 100
        if gap_pct > 0.1:
            void_zones.append({"side": "bid", "from": bids[i][0], "to": bids[i - 1][0],
                                "gap_pct": round(gap_pct, 3)})
    for i in range(1, min(15, len(asks))):
        gap_pct = (asks[i][0] - asks[i - 1][0]) / last_price * 100
        if gap_pct > 0.1:
            void_zones.append({"side": "ask", "from": asks[i - 1][0], "to": asks[i][0],
                                "gap_pct": round(gap_pct, 3)})
    if void_zones:
        biggest = max(void_zones, key=lambda v: v["gap_pct"])
        reasons.append(f"VOID {biggest['side'].upper()} {biggest['from']:.6g}→{biggest['to']:.6g} ({biggest['gap_pct']:.3f}%)")
        ob_score += 3

    # --- 8. Bid/Ask depth at 0.5%, 1%, 2% ---
    depth_levels = {}
    for pct_level in [0.5, 1.0, 2.0]:
        bid_at = sum(b[1] for b in bids if b[0] >= last_price * (1 - pct_level / 100))
        ask_at = sum(a[1] for a in asks if a[0] <= last_price * (1 + pct_level / 100))
        depth_levels[pct_level] = {"bid": bid_at, "ask": ask_at}
        ratio = bid_at / (ask_at + 1e-12)
        if ratio > 2.0:
            reasons.append(f"Depth {pct_level}%: bids {ratio:.1f}x les asks (fort support)")
            ob_score += 4
        elif ratio < 0.5:
            reasons.append(f"Depth {pct_level}%: asks {1/ratio:.1f}x les bids (forte resistance)")
            ob_score += 4

    return {
        "bias": bias, "clusters": clusters, "reasons": reasons,
        "imbalance": imbalance, "spread_pct": spread_pct,
        "gradient_score": gradient_score, "absorption": absorption,
        "spoofing_risk": spoofing_risk, "void_zones": void_zones[:3],
        "ob_score": ob_score, "depth_levels": depth_levels,
    }


# ========== 30+ STRATEGIES PRE-PUMP ==========

def analyze_klines_advanced(kdata: dict) -> dict:
    """30+ strategies de detection pre-pump avec indicateurs avances."""
    empty = {"strategies": [], "reasons": [], "score": 0, "trend": "unknown",
             "rsi": 50, "atr": 0, "macd_signal": "", "bb_squeeze": False,
             "chaikin_osc": 0, "cmf": 0, "obv_trend": "neutral", "mfi": 50,
             "williams_r": -50, "adx": 0, "poc": 0, "poc_conc": 0}
    if not kdata or "close" not in kdata:
        return empty

    closes = kdata["close"]
    highs = kdata["high"]
    lows = kdata["low"]
    volumes = kdata["vol"]
    opens = kdata.get("open", closes)
    n = len(closes)
    if n < 30:
        return empty

    strategies = []
    reasons = []
    scores = []
    last = closes[-1]
    prev = closes[-2]

    # ===== Indicateurs classiques =====
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

    ema8 = calc_ema(closes, 8)[-1]
    ema13 = calc_ema(closes, 13)[-1]
    ema21 = calc_ema(closes, 21)[-1]
    ema55 = calc_ema(closes, 55)[-1] if n >= 55 else sma50

    # ===== Nouveaux indicateurs avances =====
    chaikin_osc, adl = calc_chaikin_oscillator(highs, lows, closes, volumes)
    cmf = calc_cmf(highs, lows, closes, volumes, 20)
    obv_trend, obv_slope = calc_obv_trend(closes, volumes, 20)
    mfi = calc_mfi(highs, lows, closes, volumes, 14)
    williams_r = calc_williams_r(highs, lows, closes, 14)
    adx = calc_adx(highs, lows, closes, 14)
    poc, poc_conc = calc_volume_profile_poc(closes[-50:], volumes[-50:], 25)

    # Trend
    if last > sma20 > sma50:
        trend = "bullish"
    elif last < sma20 < sma50:
        trend = "bearish"
    elif last > sma20:
        trend = "recovery"
    else:
        trend = "range"

    # ==========================================
    #   STRATEGIES 1-18 (existantes)
    # ==========================================

    r20_high = max(highs[-20:])
    r20_low = min(lows[-20:])

    # 1. Breakout resistance
    if last > r20_high * 0.998 and vol_ratio > 1.3:
        strategies.append("breakout_resistance")
        reasons.append(f"Casse resistance 20P ({r20_high:.6g}) vol x{vol_ratio:.1f}")
        scores.append(20)

    # 2. Breakout support
    if last < r20_low * 1.002 and vol_ratio > 1.3:
        strategies.append("breakout_support")
        reasons.append(f"Casse support 20P ({r20_low:.6g}) vol x{vol_ratio:.1f}")
        scores.append(20)

    # 3. Volume spike
    if vol_ratio > 2.0:
        strategies.append("volume_spike")
        reasons.append(f"Volume spike x{vol_ratio:.1f}")
        scores.append(min(20, int(vol_ratio * 5)))

    # 4. Volume dry-up → expansion
    if n >= 15:
        recent_avg = sum(volumes[-5:]) / 5
        older_avg = sum(volumes[-15:-5]) / 10
        if older_avg > 0 and recent_avg < older_avg * 0.4 and last_vol > recent_avg * 2:
            strategies.append("volume_dryup_expansion")
            reasons.append("Volume dry-up → expansion (accumulation)")
            scores.append(18)

    # 5. RSI survendu
    if rsi < 30:
        strategies.append("rsi_oversold")
        reasons.append(f"RSI survendu ({rsi:.0f})")
        scores.append(15)

    # 6. Stoch RSI
    if stoch_rsi < 20:
        strategies.append("stoch_rsi_oversold")
        reasons.append(f"StochRSI survendu ({stoch_rsi:.0f})")
        scores.append(12)
    elif stoch_rsi > 80:
        strategies.append("stoch_rsi_overbought")
        reasons.append(f"StochRSI suracheté ({stoch_rsi:.0f})")
        scores.append(8)

    # 7-8. MACD cross
    if macd_hist > 0 and n >= 36:
        prev_macd = calc_macd(closes[:-1])
        if prev_macd[2] <= 0:
            strategies.append("macd_bullish_cross")
            reasons.append("MACD cross haussier")
            scores.append(15)
    if macd_hist < 0 and n >= 36:
        prev_macd = calc_macd(closes[:-1])
        if prev_macd[2] >= 0:
            strategies.append("macd_bearish_cross")
            reasons.append("MACD cross baissier")
            scores.append(12)

    # 9. Bollinger squeeze
    bb_squeeze = False
    if n >= 40:
        prev_bb = calc_bollinger(closes[:-5])
        if prev_bb[3] > 0 and bb_width < prev_bb[3] * 0.6:
            bb_squeeze = True
            strategies.append("bollinger_squeeze")
            reasons.append(f"Bollinger squeeze ({bb_width:.2f}% < {prev_bb[3]:.2f}%)")
            scores.append(15)

    # 10. Bollinger bounce
    if last < bb_low * 1.005 and trend != "bearish":
        strategies.append("bollinger_bounce_low")
        reasons.append(f"Touche bande basse BB ({bb_low:.6g})")
        scores.append(12)

    # 11. EMA ribbon
    if ema8 > ema13 > ema21 > ema55:
        strategies.append("ema_ribbon_bullish")
        reasons.append("EMA ribbon haussier (8>13>21>55)")
        scores.append(12)
    elif ema8 < ema13 < ema21 < ema55:
        strategies.append("ema_ribbon_bearish")
        reasons.append("EMA ribbon baissier")
        scores.append(10)

    # 12. EMA55 cross
    if n >= 56:
        prev_ema55 = calc_ema(closes[:-1], 55)[-1]
        if prev < prev_ema55 and last > ema55:
            strategies.append("ema55_cross_up")
            reasons.append(f"Cross EMA55 haussier ({ema55:.6g})")
            scores.append(18)

    # 13. VWAP position
    if last > vwap * 1.005 and trend in ("bullish", "recovery"):
        strategies.append("above_vwap")
        reasons.append(f"Au-dessus VWAP ({vwap:.6g})")
        scores.append(8)

    # 14-15. Candlestick patterns
    if n >= 3:
        body_last = abs(closes[-1] - opens[-1])
        wick_low = min(closes[-1], opens[-1]) - lows[-1]
        wick_high = highs[-1] - max(closes[-1], opens[-1])
        if wick_low > body_last * 2.5 and body_last > 0:
            strategies.append("hammer")
            reasons.append("Hammer (longue meche basse)")
            scores.append(12 if trend == "bearish" else 6)
        if wick_high > body_last * 2.5 and body_last > 0:
            strategies.append("shooting_star")
            reasons.append("Shooting star (longue meche haute)")
            scores.append(10 if trend == "bullish" else 5)

        # Engulfing
        body_prev = abs(closes[-2] - opens[-2])
        if closes[-1] > opens[-1] and closes[-2] < opens[-2] and body_last > body_prev * 1.3:
            strategies.append("bullish_engulfing")
            reasons.append("Engulfing haussier")
            scores.append(14)
        elif closes[-1] < opens[-1] and closes[-2] > opens[-2] and body_last > body_prev * 1.3:
            strategies.append("bearish_engulfing")
            reasons.append("Engulfing baissier")
            scores.append(12)

    # 16. Range compression
    if n >= 20:
        recent_range = max(highs[-5:]) - min(lows[-5:])
        older_range = max(highs[-20:-5]) - min(lows[-20:-5])
        if older_range > 0 and recent_range < older_range * 0.35:
            strategies.append("range_compression")
            reasons.append(f"Compression extreme ({recent_range/older_range:.0%} du range)")
            scores.append(15)

    # 17. Momentum acceleration
    if n >= 10:
        mom_5 = (closes[-1] - closes[-5]) / closes[-5] * 100
        mom_10 = (closes[-5] - closes[-10]) / closes[-10] * 100
        if mom_5 > 0 and mom_5 > mom_10 * 2 and mom_5 > 1.0:
            strategies.append("momentum_acceleration")
            reasons.append(f"Acceleration momentum ({mom_5:+.2f}% vs {mom_10:+.2f}%)")
            scores.append(12)

    # ==========================================
    #   STRATEGIES 19-30+ (NOUVELLES)
    # ==========================================

    # 19. Chaikin Oscillator — flux de capitaux
    if chaikin_osc > 0 and len(adl) >= 5:
        prev_co = calc_ema(adl[:-1], 3)[-1] - calc_ema(adl[:-1], 10)[-1] if len(adl) > 10 else 0
        if prev_co <= 0:
            strategies.append("chaikin_bullish_cross")
            reasons.append(f"Chaikin Oscillator cross haussier (inflow detecte, CO={chaikin_osc:+.0f})")
            scores.append(14)
    elif chaikin_osc < 0 and len(adl) >= 5:
        prev_co = calc_ema(adl[:-1], 3)[-1] - calc_ema(adl[:-1], 10)[-1] if len(adl) > 10 else 0
        if prev_co >= 0:
            strategies.append("chaikin_bearish_cross")
            reasons.append(f"Chaikin Oscillator cross baissier (outflow, CO={chaikin_osc:+.0f})")
            scores.append(10)

    # 20. Chaikin Money Flow — pression directionnelle
    if cmf > 0.15:
        strategies.append("cmf_strong_inflow")
        reasons.append(f"CMF fort inflow ({cmf:+.2f}) — acheteurs dominants")
        scores.append(12)
    elif cmf < -0.15:
        strategies.append("cmf_strong_outflow")
        reasons.append(f"CMF fort outflow ({cmf:+.2f}) — vendeurs dominants")
        scores.append(10)

    # 21. CMF divergence (prix baisse mais CMF monte = accumulation cachee)
    if n >= 10:
        price_down = closes[-1] < closes[-10]
        if price_down and cmf > 0.05:
            strategies.append("cmf_bullish_divergence")
            reasons.append(f"DIVERGENCE CMF: prix baisse mais inflow positif ({cmf:+.2f}) — accumulation cachee")
            scores.append(18)
        price_up = closes[-1] > closes[-10]
        if price_up and cmf < -0.05:
            strategies.append("cmf_bearish_divergence")
            reasons.append(f"DIVERGENCE CMF: prix monte mais outflow ({cmf:+.2f}) — distribution cachee")
            scores.append(15)

    # 22. OBV trend — proxy inflow/outflow
    if obv_trend == "bullish_divergence":
        strategies.append("obv_bullish_divergence")
        reasons.append(f"OBV divergence haussiere: volume entre (inflow) malgre prix en baisse")
        scores.append(18)
    elif obv_trend == "bearish_divergence":
        strategies.append("obv_bearish_divergence")
        reasons.append(f"OBV divergence baissiere: volume sort (outflow) malgre prix en hausse")
        scores.append(15)
    elif obv_trend == "accumulation":
        strategies.append("obv_accumulation")
        reasons.append(f"OBV accumulation: inflow cumulatif en hausse")
        scores.append(8)

    # 23. MFI (Money Flow Index) — RSI pondere volume
    if mfi < 20:
        strategies.append("mfi_oversold")
        reasons.append(f"MFI survendu ({mfi:.0f}) — money flow a sec, rebond probable")
        scores.append(15)
    elif mfi > 80:
        strategies.append("mfi_overbought")
        reasons.append(f"MFI suracheté ({mfi:.0f}) — exces de capitaux")
        scores.append(8)

    # 24. MFI divergence
    if n >= 15:
        mfi_prev = calc_mfi(highs[:-5], lows[:-5], closes[:-5], volumes[:-5], 14)
        if mfi > mfi_prev + 10 and closes[-1] < closes[-6]:
            strategies.append("mfi_bullish_divergence")
            reasons.append(f"DIVERGENCE MFI: flux monte ({mfi_prev:.0f}→{mfi:.0f}) mais prix baisse")
            scores.append(14)

    # 25. Williams %R
    if williams_r < -80:
        strategies.append("williams_oversold")
        reasons.append(f"Williams %R survendu ({williams_r:.0f})")
        scores.append(10)
    elif williams_r > -20:
        strategies.append("williams_overbought")
        reasons.append(f"Williams %R suracheté ({williams_r:.0f})")
        scores.append(6)

    # 26. ADX — force de la tendance
    if adx > 30:
        strategies.append("adx_strong_trend")
        reasons.append(f"ADX fort ({adx:.0f}) — tendance puissante confirmee")
        scores.append(10)
    elif adx < 15:
        strategies.append("adx_no_trend")
        reasons.append(f"ADX faible ({adx:.0f}) — range, breakout imminent possible")
        scores.append(5)

    # 27. ADX + direction
    if adx > 25 and trend == "bullish":
        strategies.append("adx_bullish_trend")
        reasons.append(f"Tendance haussiere confirmee ADX={adx:.0f}")
        scores.append(8)

    # 28. Volume Profile — POC
    if poc > 0:
        poc_dist = abs(last - poc) / last * 100
        if poc_dist < 0.5:
            strategies.append("near_poc")
            reasons.append(f"Prix pres du POC ({poc:.6g}, {poc_dist:.2f}%) — zone haute activite")
            scores.append(6)
        elif last > poc and trend in ("bullish", "recovery"):
            strategies.append("above_poc")
            reasons.append(f"Prix au-dessus POC ({poc:.6g}) — support volume")
            scores.append(5)

    # 29. Accumulation/Distribution Line trend
    if len(adl) >= 10:
        adl_slope = (adl[-1] - adl[-10]) / (abs(adl[-10]) + 1e-12)
        if adl_slope > 0.1 and trend != "bullish":
            strategies.append("adl_hidden_accumulation")
            reasons.append(f"ADL en hausse ({adl_slope:+.2f}) malgre prix stagnant — accumulation discrete")
            scores.append(12)

    # 30. Triple confirmation (RSI + MFI + Williams allignes survendu)
    if rsi < 35 and mfi < 30 and williams_r < -75:
        strategies.append("triple_oversold")
        reasons.append(f"TRIPLE survendu: RSI={rsi:.0f} MFI={mfi:.0f} W%R={williams_r:.0f}")
        scores.append(20)

    # 31. Smart Money: CMF + OBV + Chaikin alignes
    if cmf > 0.1 and obv_trend in ("accumulation", "bullish_divergence") and chaikin_osc > 0:
        strategies.append("smart_money_inflow")
        reasons.append(f"SMART MONEY: CMF({cmf:+.2f}) + OBV({obv_trend}) + Chaikin(+) alignes → inflow massif")
        scores.append(20)

    macd_signal = "bullish" if macd_hist > 0 else "bearish" if macd_hist < 0 else "neutral"

    return {
        "strategies": strategies, "reasons": reasons,
        "score": min(100, sum(scores)), "trend": trend,
        "rsi": rsi, "atr": atr, "macd_signal": macd_signal,
        "bb_squeeze": bb_squeeze, "chaikin_osc": chaikin_osc,
        "cmf": cmf, "obv_trend": obv_trend, "mfi": mfi,
        "williams_r": williams_r, "adx": adx, "poc": poc, "poc_conc": poc_conc,
    }


# ========== ANALYSE COMPLETE ==========

async def analyze_pair(client: httpx.AsyncClient, ticker: dict) -> Signal | None:
    symbol = ticker["symbol"]

    klines_data, depth_data = await asyncio.gather(
        get_klines(client, symbol, "Min15", 96),
        get_depth(client, symbol, 50),
    )

    kline = analyze_klines_advanced(klines_data)
    last_price = ticker["lastPrice"]
    depth = analyze_depth_ultra(depth_data, last_price)

    all_strategies = list(kline["strategies"])
    all_reasons = list(kline["reasons"]) + depth["reasons"]
    score = kline["score"] + depth["ob_score"]

    # Bonus convergence liquidite + tendance
    if depth["bias"] in ("bullish", "strong_bullish") and kline["trend"] in ("bullish", "recovery"):
        score += 10
        all_strategies.append("liquidity_convergence_long")
        all_reasons.append("Liquidite + tendance convergent LONG")
    elif depth["bias"] in ("bearish", "strong_bearish") and kline["trend"] == "bearish":
        score += 10
        all_strategies.append("liquidity_convergence_short")
        all_reasons.append("Liquidite + tendance convergent SHORT")

    # Extreme imbalance
    if abs(depth["imbalance"]) > 0.4:
        score += 8
        side = "bid" if depth["imbalance"] > 0 else "ask"
        all_strategies.append(f"extreme_imbalance_{side}")
        all_reasons.append(f"Desequilibre extreme carnet ({depth['imbalance']:+.0%})")

    # Absorption detection
    if depth["absorption"] == "bid_absorption" and kline["trend"] != "bearish":
        score += 6
        all_strategies.append("bid_absorption")
        all_reasons.append("Absorption acheteuse detectee (buyers accumulent)")

    # Funding rate
    funding = ticker.get("fundingRate", 0)
    if funding < -0.0005 and kline["trend"] != "bearish":
        score += 8
        all_strategies.append("negative_funding")
        all_reasons.append(f"Funding negatif ({funding:.6f}) — shorts paieront")
    elif funding > 0.001 and kline["trend"] != "bullish":
        score += 6
        all_strategies.append("high_funding")
        all_reasons.append(f"Funding eleve ({funding:.6f}) — longs paieront")

    if score < MIN_SCORE or not all_strategies:
        return None

    # Direction
    long_kw = ["bullish", "oversold", "bounce_low", "resistance", "cross_up",
               "hammer", "acceleration", "dryup", "spike", "convergence_long",
               "negative_funding", "above_vwap", "above_poc", "inflow", "accumulation",
               "bid_absorption", "smart_money"]
    short_kw = ["bearish", "overbought", "bounce_high", "support", "cross_down",
                "shooting_star", "convergence_short", "high_funding", "outflow", "distribution"]

    long_c = sum(1 for s in all_strategies if any(x in s for x in long_kw))
    short_c = sum(1 for s in all_strategies if any(x in s for x in short_kw))

    direction = "LONG" if long_c > short_c else "SHORT" if short_c > long_c else (
        "LONG" if ticker.get("riseFallRate", 0) > 0 else "SHORT")

    # Entry / TP / SL dynamiques ATR
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
        pct_e, pct_t, pct_s = 0.001, 0.004, 0.0025
        if direction == "LONG":
            entry = round(last_price * (1 - pct_e), dec)
            tp = round(entry * (1 + pct_t), dec)
            sl = round(entry * (1 - pct_s), dec)
        else:
            entry = round(last_price * (1 + pct_e), dec)
            tp = round(entry * (1 - pct_t), dec)
            sl = round(entry * (1 + pct_s), dec)

    regime = ("strong_signal" if score >= 70 else "squeeze" if kline["bb_squeeze"]
              else "trending" if kline["trend"] in ("bullish", "bearish") else "ranging")

    return Signal(
        symbol=symbol, direction=direction, score=min(100, score),
        last_price=last_price, entry=entry, tp=tp, sl=sl,
        strategies=all_strategies, reasons=all_reasons,
        volume_24h=ticker.get("amount24", 0),
        change_24h=ticker.get("riseFallRate", 0) * 100,
        funding_rate=funding, liquidity_bias=depth["bias"],
        liquidity_clusters=depth["clusters"][:5],
        ob_analysis={"spread_pct": depth["spread_pct"],
                     "absorption": depth["absorption"],
                     "spoofing_risk": depth["spoofing_risk"],
                     "gradient": depth["gradient_score"],
                     "voids": len(depth["void_zones"])},
        atr=atr, rsi=kline["rsi"], chaikin_osc=kline["chaikin_osc"],
        cmf=kline["cmf"], obv_trend=kline["obv_trend"],
        mfi=kline["mfi"], williams_r=kline["williams_r"],
        adx=kline["adx"], macd_signal=kline["macd_signal"],
        bb_squeeze=kline["bb_squeeze"], regime=regime,
    )


def _price_decimals(price):
    if price > 1000: return 1
    elif price > 10: return 2
    elif price > 1: return 3
    elif price > 0.01: return 5
    elif price > 0.0001: return 7
    else: return 10


# ========== SCAN ==========

async def scan_sniper(top_n=3, min_score=MIN_SCORE):
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=30)) as client:
        print(f"[1/3] Recuperation tickers MEXC Futures...", file=sys.stderr)
        tickers = await get_all_tickers(client)
        if not tickers:
            print("Erreur: aucun ticker MEXC", file=sys.stderr)
            return []
        print(f"[1/3] {len(tickers)} coins (vol > {MIN_VOL_24H:,} USDT)", file=sys.stderr)

        print(f"[2/3] Analyse 31 strategies + orderbook ultra...", file=sys.stderr)
        all_signals = []
        batch_size = 20
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            tasks = [analyze_pair(client, t) for t in batch]
            results = await asyncio.gather(*tasks)
            for s in results:
                if s is not None and s.score >= min_score:
                    all_signals.append(s)
            if i + batch_size < len(tickers):
                await asyncio.sleep(0.3)

        all_signals.sort(key=lambda s: s.score, reverse=True)
        print(f"[3/3] {len(all_signals)} signaux, top {top_n}", file=sys.stderr)
        return all_signals[:top_n]


# ========== AFFICHAGE ==========

def format_signal(s: Signal, rank: int) -> str:
    coin = s.symbol.replace("_USDT", "")
    rr = abs(s.tp - s.entry) / abs(s.entry - s.sl) if abs(s.entry - s.sl) > 0 else 0

    lines = [
        "",
        f"{'='*56}",
        f"  #{rank}  {coin}  |  {s.direction}  |  Score {s.score}/100  |  {s.regime.upper()}",
        f"{'='*56}",
        f"  Prix:    {s.last_price} USDT",
        f"  Entree:  {s.entry} USDT",
        f"  TP:      {s.tp} USDT  (R:R {rr:.1f})",
        f"  SL:      {s.sl} USDT",
        f"  ATR:     {s.atr:.6g}",
        f"",
        f"  --- Indicateurs ---",
        f"  RSI: {s.rsi:.0f}  |  MFI: {s.mfi:.0f}  |  W%R: {s.williams_r:.0f}  |  ADX: {s.adx:.0f}",
        f"  MACD: {s.macd_signal}  |  BB squeeze: {'OUI' if s.bb_squeeze else 'non'}",
        f"  Chaikin: {s.chaikin_osc:+.0f}  |  CMF: {s.cmf:+.3f}  |  OBV: {s.obv_trend}",
        f"",
        f"  --- Marche ---",
        f"  Var 24h: {s.change_24h:+.2f}%  |  Funding: {s.funding_rate:.6f}",
        f"  Liquidite: {s.liquidity_bias}",
    ]
    if s.ob_analysis:
        ob = s.ob_analysis
        lines.append(f"  OB: spread {ob.get('spread_pct',0):.4f}%  |  absorption: {ob.get('absorption','none')}  |  spoofing: {'OUI' if ob.get('spoofing_risk') else 'non'}  |  voids: {ob.get('voids',0)}")

    lines.append(f"")
    lines.append(f"  --- Strategies ({len(s.strategies)}) ---")
    for st in s.strategies:
        lines.append(f"    + {st}")

    lines.append(f"")
    lines.append(f"  --- Raisons ---")
    for r in s.reasons:
        lines.append(f"    - {r}")

    if s.liquidity_clusters:
        lines.append(f"")
        lines.append(f"  --- Clusters Liquidite ---")
        for c in s.liquidity_clusters:
            side = "BID" if c["side"] == "bid" else "ASK"
            ctype = f" [{c.get('type','')}]" if c.get('type') else ""
            lines.append(f"    [{side}] {c['price']:.6g} ({c['volume']:,.0f} lots, {c['pct_away']:+.2f}%){ctype}")

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
        print(json.dumps({
            "signals": [asdict(s) for s in signals],
            "meta": {"scan_time_s": round(elapsed, 1), "coins_scanned": TOP_VOLUME,
                     "signals_found": len(signals), "min_score": min_score,
                     "strategies_count": 31, "version": "v3"}
        }, indent=2, ensure_ascii=False))
    else:
        if not signals:
            print(f"\nAucun signal >= {min_score}/100 sur {TOP_VOLUME} coins ({elapsed:.1f}s)")
            return
        print(f"\n{'#'*56}")
        print(f"  SCAN SNIPER v3 MEXC — Top {len(signals)} Pre-Pump")
        print(f"  {TOP_VOLUME} coins | {elapsed:.1f}s | 31 strategies")
        print(f"  Chaikin + CMF + OBV + MFI + ADX + OrderBook Ultra")
        print(f"{'#'*56}")
        for i, s in enumerate(signals, 1):
            print(format_signal(s, i))
        print(f"\n{'='*56}")
        print(f"  Config: Levier 10x | TP ATRx{TP_MULT} | SL ATRx{SL_MULT}")
        print(f"{'='*56}")


if __name__ == "__main__":
    main()
