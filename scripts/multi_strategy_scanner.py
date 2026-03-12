#!/usr/bin/env python3
"""
Multi-Strategy Scanner — 100+ variantes backtestees sur tous les coins MEXC.

Pipeline:
1. Fetch tous les tickers MEXC Futures (volume > seuil)
2. Pre-filtre: volatilite, volume, spread
3. Run 100+ strategies sur chaque coin
4. Score et ranking progressif
5. Output: pool finale de coins + meilleures strategies par coin

Usage:
    python scripts/multi_strategy_scanner.py                     # Full scan
    python scripts/multi_strategy_scanner.py --top 30            # Top 30 coins only
    python scripts/multi_strategy_scanner.py --strategies 20     # 20 premieres strategies
    python scripts/multi_strategy_scanner.py --candles 1000      # Plus de bougies
    python scripts/multi_strategy_scanner.py --save              # Sauvegarder en DB
"""

import json, math, sys, time, urllib.request, argparse, sqlite3
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "strategy_lab.db"

# ═══════════════════════════════════════════════════════════════════════
#  INDICATEURS TECHNIQUES (stdlib only)
# ═══════════════════════════════════════════════════════════════════════

def ema(data, period):
    if len(data) < period:
        return [None] * len(data)
    result = [None] * (period - 1)
    k = 2.0 / (period + 1)
    result.append(sum(data[:period]) / period)
    for i in range(period, len(data)):
        result.append(data[i] * k + result[-1] * (1 - k))
    return result

def sma(data, period):
    result = [None] * (period - 1)
    for i in range(period - 1, len(data)):
        result.append(sum(data[i - period + 1:i + 1]) / period)
    return result

def rsi(closes, period=14):
    if len(closes) < period + 1:
        return [None] * len(closes)
    result = [None] * period
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    result.append(100.0 if al == 0 else 100.0 - 100.0 / (1 + ag / al))
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
        result.append(100.0 if al == 0 else 100.0 - 100.0 / (1 + ag / al))
    return result

def stochastic(closes, highs, lows, length=14):
    result = [None] * (length - 1)
    for i in range(length - 1, len(closes)):
        hh = max(highs[i - length + 1:i + 1])
        ll = min(lows[i - length + 1:i + 1])
        result.append(50.0 if hh == ll else (closes[i] - ll) / (hh - ll) * 100)
    return result

def atr(highs, lows, closes, period=14):
    if len(closes) < 2:
        return [None] * len(closes)
    trs = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])))
    result = [None] * (period - 1)
    avg = sum(trs[:period]) / period
    result.append(avg)
    for i in range(period, len(trs)):
        avg = (avg * (period - 1) + trs[i]) / period
        result.append(avg)
    return result

def macd(closes, fast=12, slow=26, signal=9):
    ema_f = ema(closes, fast)
    ema_s = ema(closes, slow)
    macd_line = []
    for i in range(len(closes)):
        if ema_f[i] is not None and ema_s[i] is not None:
            macd_line.append(ema_f[i] - ema_s[i])
        else:
            macd_line.append(None)
    valid = [v for v in macd_line if v is not None]
    sig = ema(valid, signal) if len(valid) >= signal else [None] * len(valid)
    # Align signal back
    signal_line = [None] * (len(macd_line) - len(sig)) + sig
    histogram = []
    for i in range(len(macd_line)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram.append(macd_line[i] - signal_line[i])
        else:
            histogram.append(None)
    return macd_line, signal_line, histogram

def bollinger(closes, period=20, std_mult=2.0):
    mid = sma(closes, period)
    upper, lower = [], []
    for i in range(len(closes)):
        if mid[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            s = math.sqrt(sum((closes[j] - mid[i])**2 for j in range(i-period+1, i+1)) / period)
            upper.append(mid[i] + std_mult * s)
            lower.append(mid[i] - std_mult * s)
    return mid, upper, lower

def vwap_calc(highs, lows, closes, volumes):
    """Simplified session VWAP (rolling)."""
    result = []
    cum_vol = 0
    cum_tp_vol = 0
    for i in range(len(closes)):
        tp = (highs[i] + lows[i] + closes[i]) / 3
        cum_vol += volumes[i]
        cum_tp_vol += tp * volumes[i]
        result.append(cum_tp_vol / cum_vol if cum_vol > 0 else closes[i])
    return result

def adx_calc(highs, lows, closes, period=14):
    """Average Directional Index."""
    if len(closes) < period * 2:
        return [None] * len(closes)
    plus_dm = []
    minus_dm = []
    tr_list = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        up = highs[i] - highs[i-1]
        down = lows[i-1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)
        tr_list.append(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])))
    # Smooth with Wilder's
    atr_s = sum(tr_list[:period]) / period
    plus_s = sum(plus_dm[:period-1]) / period
    minus_s = sum(minus_dm[:period-1]) / period
    adx_vals = [None] * (period * 2)
    dx_list = []
    for i in range(period, len(tr_list)):
        atr_s = (atr_s * (period-1) + tr_list[i]) / period
        if i - 1 < len(plus_dm):
            plus_s = (plus_s * (period-1) + plus_dm[i-1]) / period
            minus_s = (minus_s * (period-1) + minus_dm[i-1]) / period
        plus_di = (plus_s / atr_s * 100) if atr_s > 0 else 0
        minus_di = (minus_s / atr_s * 100) if atr_s > 0 else 0
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
        dx_list.append(dx)
    # ADX = smoothed DX
    if len(dx_list) >= period:
        adx = sum(dx_list[:period]) / period
        result = [None] * (len(closes) - len(dx_list) + period - 1)
        result.append(adx)
        for i in range(period, len(dx_list)):
            adx = (adx * (period-1) + dx_list[i]) / period
            result.append(adx)
        while len(result) < len(closes):
            result.append(result[-1] if result else None)
        return result[:len(closes)]
    return [None] * len(closes)

def obv_calc(closes, volumes):
    """On-Balance Volume."""
    result = [0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            result.append(result[-1] + volumes[i])
        elif closes[i] < closes[i-1]:
            result.append(result[-1] - volumes[i])
        else:
            result.append(result[-1])
    return result


# ═══════════════════════════════════════════════════════════════════════
#  STRATEGY DEFINITIONS — 100+ variantes
# ═══════════════════════════════════════════════════════════════════════

def _safe(arr, i):
    return arr[i] if i < len(arr) and arr[i] is not None else None

def build_strategies():
    """Build 100+ strategy variants from the base template."""
    strategies = []
    sid = 0

    # ── GROUP 1: EMA Crossover Variants (20 strategies) ──
    for ema_s, ema_l in [(3,8),(5,13),(5,21),(8,21),(8,34),(10,30),(12,26),(13,34),(15,40),(20,50)]:
        for tp, sl in [(1.0,1.0),(1.5,1.0)]:
            sid += 1
            strategies.append({
                "id": sid, "name": f"EMA_{ema_s}_{ema_l}_TP{tp}_SL{sl}",
                "group": "EMA_CROSS",
                "params": {"ema_s": ema_s, "ema_l": ema_l, "rsi_len": 7, "tp": tp, "sl": sl,
                           "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True},
            })

    # ── GROUP 2: RSI Threshold Variants (12 strategies) ──
    for rsi_ob, rsi_os in [(65,35),(70,30),(75,25),(80,20)]:
        for rsi_len in [7, 10, 14]:
            sid += 1
            strategies.append({
                "id": sid, "name": f"RSI_{rsi_len}_OB{rsi_ob}_OS{rsi_os}",
                "group": "RSI_TUNE",
                "params": {"ema_s": 5, "ema_l": 13, "rsi_len": rsi_len, "tp": 1.0, "sl": 1.0,
                           "rsi_ob": rsi_ob, "rsi_os": rsi_os, "stoch_len": 14, "use_stoch": True},
            })

    # ── GROUP 3: Stochastic Variants (8 strategies) ──
    for stoch_len in [9, 14, 21]:
        for stoch_hi, stoch_lo in [(80,20),(70,30)]:
            sid += 1
            strategies.append({
                "id": sid, "name": f"STOCH_{stoch_len}_H{stoch_hi}_L{stoch_lo}",
                "group": "STOCH_TUNE",
                "params": {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": 1.0, "sl": 1.0,
                           "rsi_ob": 70, "rsi_os": 30, "stoch_len": stoch_len, "use_stoch": True,
                           "stoch_hi": stoch_hi, "stoch_lo": stoch_lo},
            })

    # ── GROUP 4: TP/SL ATR Multiplier Grid (15 strategies) ──
    for tp in [0.5, 0.75, 1.0, 1.5, 2.0]:
        for sl in [0.5, 1.0, 1.5]:
            sid += 1
            strategies.append({
                "id": sid, "name": f"ATR_TP{tp}_SL{sl}",
                "group": "ATR_GRID",
                "params": {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": tp, "sl": sl,
                           "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True},
            })

    # ── GROUP 5: MACD Filter (6 strategies) ──
    for fast, slow, sig in [(8,17,9),(12,26,9),(5,13,5)]:
        for tp in [1.0, 1.5]:
            sid += 1
            strategies.append({
                "id": sid, "name": f"MACD_{fast}_{slow}_{sig}_TP{tp}",
                "group": "MACD",
                "params": {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": tp, "sl": 1.0,
                           "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                           "use_macd": True, "macd_fast": fast, "macd_slow": slow, "macd_sig": sig},
            })

    # ── GROUP 6: Bollinger Band Filter (6 strategies) ──
    for bb_period in [15, 20]:
        for bb_std in [1.5, 2.0, 2.5]:
            sid += 1
            strategies.append({
                "id": sid, "name": f"BB_{bb_period}_STD{bb_std}",
                "group": "BOLLINGER",
                "params": {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": 1.0, "sl": 1.0,
                           "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                           "use_bb": True, "bb_period": bb_period, "bb_std": bb_std},
            })

    # ── GROUP 7: Volume Filter (4 strategies) ──
    for vol_mult in [1.2, 1.5, 2.0, 3.0]:
        sid += 1
        strategies.append({
            "id": sid, "name": f"VOL_FILTER_x{vol_mult}",
            "group": "VOLUME",
            "params": {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": 1.0, "sl": 1.0,
                       "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                       "use_vol_filter": True, "vol_mult": vol_mult},
        })

    # ── GROUP 8: ADX Trend Filter (4 strategies) ──
    for adx_min in [15, 20, 25, 30]:
        sid += 1
        strategies.append({
            "id": sid, "name": f"ADX_MIN{adx_min}",
            "group": "ADX",
            "params": {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": 1.0, "sl": 1.0,
                       "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                       "use_adx": True, "adx_min": adx_min},
        })

    # ── GROUP 9: VWAP Filter (3 strategies) ──
    for tp in [1.0, 1.5, 2.0]:
        sid += 1
        strategies.append({
            "id": sid, "name": f"VWAP_TP{tp}",
            "group": "VWAP",
            "params": {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": tp, "sl": 1.0,
                       "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                       "use_vwap": True},
        })

    # ── GROUP 10: LONG ONLY (5 strategies) ──
    for ema_s, ema_l in [(5,13),(8,21),(3,8),(10,30),(12,26)]:
        sid += 1
        strategies.append({
            "id": sid, "name": f"LONG_ONLY_EMA{ema_s}_{ema_l}",
            "group": "LONG_ONLY",
            "params": {"ema_s": ema_s, "ema_l": ema_l, "rsi_len": 7, "tp": 1.0, "sl": 1.0,
                       "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                       "long_only": True},
        })

    # ── GROUP 11: SHORT ONLY (5 strategies) ──
    for ema_s, ema_l in [(5,13),(8,21),(3,8),(10,30),(12,26)]:
        sid += 1
        strategies.append({
            "id": sid, "name": f"SHORT_ONLY_EMA{ema_s}_{ema_l}",
            "group": "SHORT_ONLY",
            "params": {"ema_s": ema_s, "ema_l": ema_l, "rsi_len": 7, "tp": 1.0, "sl": 1.0,
                       "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                       "short_only": True},
        })

    # ── GROUP 12: OBV Momentum (3 strategies) ──
    for tp in [1.0, 1.5, 2.0]:
        sid += 1
        strategies.append({
            "id": sid, "name": f"OBV_MOM_TP{tp}",
            "group": "OBV",
            "params": {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": tp, "sl": 1.0,
                       "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                       "use_obv": True},
        })

    # ── GROUP 13: No Stoch (pure EMA+RSI) (5 strategies) ──
    for ema_s, ema_l in [(5,13),(8,21),(3,8),(10,30),(5,21)]:
        sid += 1
        strategies.append({
            "id": sid, "name": f"NO_STOCH_EMA{ema_s}_{ema_l}",
            "group": "NO_STOCH",
            "params": {"ema_s": ema_s, "ema_l": ema_l, "rsi_len": 7, "tp": 1.0, "sl": 1.0,
                       "rsi_ob": 70, "rsi_os": 30, "use_stoch": False},
        })

    # ── GROUP 14: Trailing Stop (4 strategies) ──
    for trail in [0.5, 0.75, 1.0, 1.5]:
        sid += 1
        strategies.append({
            "id": sid, "name": f"TRAIL_{trail}ATR",
            "group": "TRAILING",
            "params": {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": 2.0, "sl": 1.0,
                       "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True,
                       "trailing": True, "trail_atr": trail},
        })

    # ── GROUP 15: Multi-Confirm (combos) (5 strategies) ──
    combos = [
        ("MACD+BB", {"use_macd": True, "macd_fast": 12, "macd_slow": 26, "macd_sig": 9, "use_bb": True, "bb_period": 20, "bb_std": 2.0}),
        ("MACD+VOL", {"use_macd": True, "macd_fast": 12, "macd_slow": 26, "macd_sig": 9, "use_vol_filter": True, "vol_mult": 1.5}),
        ("BB+ADX", {"use_bb": True, "bb_period": 20, "bb_std": 2.0, "use_adx": True, "adx_min": 20}),
        ("VWAP+VOL", {"use_vwap": True, "use_vol_filter": True, "vol_mult": 1.5}),
        ("ALL_IN", {"use_macd": True, "macd_fast": 12, "macd_slow": 26, "macd_sig": 9,
                    "use_bb": True, "bb_period": 20, "bb_std": 2.0,
                    "use_adx": True, "adx_min": 20, "use_vol_filter": True, "vol_mult": 1.5}),
    ]
    for name, extra in combos:
        sid += 1
        p = {"ema_s": 5, "ema_l": 13, "rsi_len": 7, "tp": 1.0, "sl": 1.0,
             "rsi_ob": 70, "rsi_os": 30, "stoch_len": 14, "use_stoch": True}
        p.update(extra)
        strategies.append({"id": sid, "name": name, "group": "COMBO", "params": p})

    return strategies


# ═══════════════════════════════════════════════════════════════════════
#  STRATEGY ENGINE
# ═══════════════════════════════════════════════════════════════════════

def precompute_indicators(candles):
    """Pre-compute all indicators once per coin."""
    closes = [c["c"] for c in candles]
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    volumes = [c.get("v", 0) for c in candles]

    cache = {"closes": closes, "highs": highs, "lows": lows, "volumes": volumes}

    # EMA variants
    for p in [3,5,8,10,12,13,15,20,21,26,30,34,40,50]:
        cache[f"ema_{p}"] = ema(closes, p)

    # RSI
    for p in [7, 10, 14]:
        cache[f"rsi_{p}"] = rsi(closes, p)

    # Stochastic
    for p in [9, 14, 21]:
        raw = stochastic(closes, highs, lows, p)
        cache[f"stoch_raw_{p}"] = raw
        cache[f"stoch_k_{p}"] = sma([v if v is not None else 50 for v in raw], 3)

    # ATR
    cache["atr_14"] = atr(highs, lows, closes, 14)

    # MACD variants
    for fast, slow, sig in [(8,17,9),(12,26,9),(5,13,5)]:
        ml, sl_line, hist = macd(closes, fast, slow, sig)
        cache[f"macd_{fast}_{slow}_{sig}"] = (ml, sl_line, hist)

    # Bollinger
    for p in [15, 20]:
        for std in [1.5, 2.0, 2.5]:
            mid, upper, lower = bollinger(closes, p, std)
            cache[f"bb_{p}_{std}"] = (mid, upper, lower)

    # Volume SMA (for volume filter)
    cache["vol_sma_20"] = sma(volumes, 20)

    # ADX
    cache["adx_14"] = adx_calc(highs, lows, closes, 14)

    # VWAP
    cache["vwap"] = vwap_calc(highs, lows, closes, volumes)

    # OBV
    cache["obv"] = obv_calc(closes, volumes)
    cache["obv_ema_10"] = ema(cache["obv"], 10)

    return cache


def run_single_strategy(cache, strat):
    """Run a single strategy using pre-computed indicators."""
    p = strat["params"]
    closes = cache["closes"]
    highs = cache["highs"]
    lows = cache["lows"]
    volumes = cache["volumes"]
    n = len(closes)

    ema_s = cache.get(f"ema_{p['ema_s']}")
    ema_l = cache.get(f"ema_{p['ema_l']}")
    rsi_vals = cache.get(f"rsi_{p['rsi_len']}")
    stoch_len = p.get("stoch_len", 14)
    stoch_k = cache.get(f"stoch_k_{stoch_len}")
    atr_vals = cache["atr_14"]

    if not ema_s or not ema_l or not rsi_vals:
        return []

    stoch_hi = p.get("stoch_hi", 80)
    stoch_lo = p.get("stoch_lo", 20)
    tp_mult = p["tp"]
    sl_mult = p["sl"]
    use_stoch = p.get("use_stoch", True)
    long_only = p.get("long_only", False)
    short_only = p.get("short_only", False)

    # Optional filters
    use_macd = p.get("use_macd", False)
    use_bb = p.get("use_bb", False)
    use_vol = p.get("use_vol_filter", False)
    use_adx = p.get("use_adx", False)
    use_vwap = p.get("use_vwap", False)
    use_obv = p.get("use_obv", False)
    trailing = p.get("trailing", False)

    macd_data = None
    if use_macd:
        key = f"macd_{p.get('macd_fast',12)}_{p.get('macd_slow',26)}_{p.get('macd_sig',9)}"
        macd_data = cache.get(key)

    bb_data = None
    if use_bb:
        key = f"bb_{p.get('bb_period',20)}_{p.get('bb_std',2.0)}"
        bb_data = cache.get(key)

    vol_sma = cache.get("vol_sma_20") if use_vol else None
    adx_vals = cache.get("adx_14") if use_adx else None
    vwap_vals = cache.get("vwap") if use_vwap else None
    obv_vals = cache.get("obv") if use_obv else None
    obv_ema = cache.get("obv_ema_10") if use_obv else None

    trades = []
    position = None
    start = max(p["ema_l"], p["rsi_len"], stoch_len, 14) + 5

    for i in range(start, n):
        if any(_safe(x, i) is None for x in [ema_s, ema_l, rsi_vals, atr_vals]):
            continue
        if use_stoch and _safe(stoch_k, i) is None:
            continue

        # ── Check exit ──
        if position is not None:
            hit = None
            exit_price = None

            if trailing:
                # Update trailing stop
                trail_dist = atr_vals[i] * p.get("trail_atr", 1.0)
                if position["dir"] == "LONG":
                    new_trail = closes[i] - trail_dist
                    if new_trail > position["sl"]:
                        position["sl"] = new_trail
                else:
                    new_trail = closes[i] + trail_dist
                    if new_trail < position["sl"]:
                        position["sl"] = new_trail

            if position["dir"] == "LONG":
                if lows[i] <= position["sl"]:
                    hit, exit_price = "SL", position["sl"]
                elif highs[i] >= position["tp"]:
                    hit, exit_price = "TP", position["tp"]
            else:
                if highs[i] >= position["sl"]:
                    hit, exit_price = "SL", position["sl"]
                elif lows[i] <= position["tp"]:
                    hit, exit_price = "TP", position["tp"]

            if hit:
                pnl = ((exit_price - position["entry"]) / position["entry"] * 100
                       if position["dir"] == "LONG"
                       else (position["entry"] - exit_price) / position["entry"] * 100)
                trades.append({"dir": position["dir"], "result": hit, "pnl": pnl,
                               "bars": i - position["bar"]})
                position = None

        # ── Check entry ──
        if position is not None:
            continue

        ema_cross_up = ema_s[i-1] <= ema_l[i-1] and ema_s[i] > ema_l[i]
        ema_cross_down = ema_s[i-1] >= ema_l[i-1] and ema_s[i] < ema_l[i]

        rsi_val = rsi_vals[i]
        stoch_val = _safe(stoch_k, i) if use_stoch else 50

        atr_val = atr_vals[i]
        if atr_val == 0 or atr_val is None:
            continue

        # Base conditions
        long_ok = ema_cross_up and rsi_val < p["rsi_ob"]
        short_ok = ema_cross_down and rsi_val > p["rsi_os"]

        if use_stoch:
            long_ok = long_ok and stoch_val < stoch_hi
            short_ok = short_ok and stoch_val > stoch_lo

        # Optional filters
        if use_macd and macd_data:
            ml, sl_line, hist = macd_data
            if _safe(hist, i) is not None:
                long_ok = long_ok and hist[i] > 0
                short_ok = short_ok and hist[i] < 0

        if use_bb and bb_data:
            mid, upper, lower = bb_data
            if _safe(lower, i) is not None:
                long_ok = long_ok and closes[i] <= mid[i]  # Near or below mid
                short_ok = short_ok and closes[i] >= mid[i]  # Near or above mid

        if use_vol and vol_sma:
            vs = _safe(vol_sma, i)
            if vs is not None and vs > 0:
                long_ok = long_ok and volumes[i] > vs * p.get("vol_mult", 1.5)
                short_ok = short_ok and volumes[i] > vs * p.get("vol_mult", 1.5)

        if use_adx and adx_vals:
            adx_v = _safe(adx_vals, i)
            if adx_v is not None:
                long_ok = long_ok and adx_v >= p.get("adx_min", 20)
                short_ok = short_ok and adx_v >= p.get("adx_min", 20)

        if use_vwap and vwap_vals:
            vw = _safe(vwap_vals, i)
            if vw is not None:
                long_ok = long_ok and closes[i] > vw  # Above VWAP for long
                short_ok = short_ok and closes[i] < vw  # Below VWAP for short

        if use_obv and obv_vals and obv_ema:
            ov = _safe(obv_vals, i)
            oe = _safe(obv_ema, i)
            if ov is not None and oe is not None:
                long_ok = long_ok and ov > oe  # OBV above its EMA = bullish
                short_ok = short_ok and ov < oe

        if long_only:
            short_ok = False
        if short_only:
            long_ok = False

        if long_ok:
            position = {
                "dir": "LONG", "entry": closes[i],
                "tp": closes[i] + atr_val * tp_mult,
                "sl": closes[i] - atr_val * sl_mult,
                "bar": i
            }
        elif short_ok:
            position = {
                "dir": "SHORT", "entry": closes[i],
                "tp": closes[i] - atr_val * tp_mult,
                "sl": closes[i] + atr_val * sl_mult,
                "bar": i
            }

    return trades


# ═══════════════════════════════════════════════════════════════════════
#  DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════

def fetch_top_coins(min_vol_24h=500000, max_coins=100):
    """Fetch top futures coins by volume."""
    try:
        req = urllib.request.Request("https://contract.mexc.com/api/v1/contract/ticker")
        with urllib.request.urlopen(req, timeout=20) as resp:
            tickers = json.loads(resp.read()).get("data", [])
    except Exception as e:
        print(f"  [ERR] Ticker fetch: {e}")
        return []

    coins = []
    for t in tickers:
        sym = t.get("symbol", "")
        vol24 = float(t.get("volume24", 0))
        price = float(t.get("lastPrice", 0))
        change = float(t.get("riseFallRate", 0)) * 100
        if vol24 * price < min_vol_24h:
            continue
        if price <= 0:
            continue
        coins.append({
            "symbol": sym, "price": price, "vol_usd": vol24 * price,
            "change_24h": change, "vol_raw": vol24
        })

    coins.sort(key=lambda x: x["vol_usd"], reverse=True)
    return coins[:max_coins]


def fetch_klines(symbol, limit=500):
    """Fetch 1min klines from MEXC futures."""
    url = f"https://contract.mexc.com/api/v1/contract/kline/{symbol}?interval=Min1&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        raw = data.get("data", {})
        if isinstance(raw, dict):
            times = raw.get("time", [])
            opens = raw.get("open", [])
            highs_r = raw.get("high", [])
            lows_r = raw.get("low", [])
            closes_r = raw.get("close", [])
            vols_r = raw.get("vol", [])
            candles = []
            for i in range(len(times)):
                candles.append({
                    "t": times[i], "o": float(opens[i]), "h": float(highs_r[i]),
                    "l": float(lows_r[i]), "c": float(closes_r[i]),
                    "v": float(vols_r[i]) if i < len(vols_r) else 0
                })
            return candles
        return []
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════
#  COIN QUALITY FILTER
# ═══════════════════════════════════════════════════════════════════════

def assess_coin_quality(candles):
    """Pre-filter coin quality before running strategies."""
    if len(candles) < 100:
        return None, "too_few_candles"

    closes = [c["c"] for c in candles]
    volumes = [c.get("v", 0) for c in candles]
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]

    # Volatility (ATR / price ratio)
    atr_vals = atr(highs, lows, closes, 14)
    valid_atr = [a for a in atr_vals if a is not None]
    if not valid_atr:
        return None, "no_atr"
    avg_atr = sum(valid_atr) / len(valid_atr)
    avg_price = sum(closes) / len(closes)
    volatility = avg_atr / avg_price * 100 if avg_price > 0 else 0

    # Volume consistency
    avg_vol = sum(volumes) / len(volumes) if volumes else 0
    zero_vol_bars = sum(1 for v in volumes if v == 0)
    vol_ratio = zero_vol_bars / len(volumes)

    # Spread (avg high-low / close)
    spreads = [(h - l) / c * 100 if c > 0 else 0 for h, l, c in zip(highs, lows, closes)]
    avg_spread = sum(spreads) / len(spreads)

    quality = {
        "volatility_pct": volatility,
        "avg_volume": avg_vol,
        "zero_vol_ratio": vol_ratio,
        "avg_spread_pct": avg_spread,
        "candle_count": len(candles),
    }

    # Reject criteria
    if volatility < 0.01:
        return quality, "too_low_volatility"
    if vol_ratio > 0.3:
        return quality, "too_many_zero_vol"
    if avg_vol < 10:
        return quality, "too_low_volume"

    return quality, "OK"


# ═══════════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════════

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scan_runs (
        id INTEGER PRIMARY KEY, timestamp TEXT, coins_scanned INT, strategies_run INT,
        total_trades INT, best_strategy TEXT, best_wr REAL, best_pnl REAL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS coin_scores (
        id INTEGER PRIMARY KEY, run_id INT, symbol TEXT, best_strategy TEXT,
        best_wr REAL, best_pnl REAL, avg_wr REAL, avg_pnl REAL,
        volatility REAL, volume REAL, grade TEXT,
        UNIQUE(run_id, symbol)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS strategy_results (
        id INTEGER PRIMARY KEY, run_id INT, symbol TEXT, strategy_id INT,
        strategy_name TEXT, strategy_group TEXT,
        total_trades INT, wins INT, losses INT, wr REAL, pnl REAL,
        avg_pnl REAL, avg_bars REAL, long_wr REAL, short_wr REAL,
        UNIQUE(run_id, symbol, strategy_id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS coin_pool (
        symbol TEXT PRIMARY KEY, grade TEXT, best_strategy TEXT,
        best_wr REAL, best_pnl REAL, volatility REAL, volume REAL,
        updated_at TEXT
    )""")
    db.commit()
    return db


# ═══════════════════════════════════════════════════════════════════════
#  MAIN SCANNER
# ═══════════════════════════════════════════════════════════════════════

def scan_coin(symbol, candles_limit, strategies):
    """Scan a single coin with all strategies. Returns results dict."""
    candles = fetch_klines(symbol, limit=candles_limit)
    if not candles:
        return {"symbol": symbol, "status": "no_data", "results": []}

    quality, status = assess_coin_quality(candles)
    if status != "OK":
        return {"symbol": symbol, "status": status, "quality": quality, "results": []}

    cache = precompute_indicators(candles)
    results = []

    for strat in strategies:
        trades = run_single_strategy(cache, strat)
        if not trades:
            continue
        closed = [t for t in trades if t["result"] != "OPEN"]
        if not closed:
            continue
        wins = [t for t in closed if t["result"] == "TP"]
        losses = [t for t in closed if t["result"] == "SL"]
        total_pnl = sum(t["pnl"] for t in closed)
        wr = len(wins) / len(closed) * 100
        avg_pnl = total_pnl / len(closed)
        avg_bars = sum(t["bars"] for t in closed) / len(closed)

        longs = [t for t in closed if t["dir"] == "LONG"]
        shorts = [t for t in closed if t["dir"] == "SHORT"]
        long_wins = [t for t in longs if t["result"] == "TP"]
        short_wins = [t for t in shorts if t["result"] == "TP"]

        results.append({
            "strategy_id": strat["id"],
            "strategy_name": strat["name"],
            "strategy_group": strat["group"],
            "total": len(closed), "wins": len(wins), "losses": len(losses),
            "wr": wr, "pnl": total_pnl, "avg_pnl": avg_pnl, "avg_bars": avg_bars,
            "long_wr": len(long_wins)/len(longs)*100 if longs else 0,
            "short_wr": len(short_wins)/len(shorts)*100 if shorts else 0,
        })

    return {"symbol": symbol, "status": "OK", "quality": quality, "results": results}


def main():
    parser = argparse.ArgumentParser(description="Multi-Strategy Scanner")
    parser.add_argument("--top", type=int, default=50, help="Top N coins by volume")
    parser.add_argument("--strategies", type=int, default=0, help="Limit strategies (0=all)")
    parser.add_argument("--candles", type=int, default=1000, help="Candles per coin")
    parser.add_argument("--min-vol", type=float, default=500000, help="Min 24h volume USD")
    parser.add_argument("--save", action="store_true", help="Save to DB")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    args = parser.parse_args()

    strategies = build_strategies()
    if args.strategies > 0:
        strategies = strategies[:args.strategies]

    print("=" * 70)
    print("  MULTI-STRATEGY SCANNER — JARVIS")
    print("=" * 70)
    print(f"  Strategies:  {len(strategies)}")
    print(f"  Candles:     {args.candles} (1min)")
    print(f"  Min volume:  ${args.min_vol:,.0f}")
    print(f"  Workers:     {args.workers}")
    print()

    # Step 1: Fetch top coins
    print("[1/4] Fetching top coins by volume...")
    coins = fetch_top_coins(min_vol_24h=args.min_vol, max_coins=args.top)
    print(f"  Found {len(coins)} coins above ${args.min_vol:,.0f} vol")
    if not coins:
        print("  No coins found!")
        return

    # Step 2: Scan each coin
    print(f"\n[2/4] Scanning {len(coins)} coins x {len(strategies)} strategies...")
    all_results = []
    rejected = {"no_data": 0, "too_low_volatility": 0, "too_many_zero_vol": 0,
                "too_low_volume": 0, "too_few_candles": 0, "no_atr": 0}
    t0 = time.time()

    for idx, coin in enumerate(coins):
        sym = coin["symbol"]
        pct = (idx + 1) / len(coins) * 100
        print(f"  [{idx+1}/{len(coins)}] {sym:<22} ${coin['vol_usd']:>12,.0f} vol  ", end="", flush=True)
        result = scan_coin(sym, args.candles, strategies)
        if result["status"] != "OK":
            rejected[result["status"]] = rejected.get(result["status"], 0) + 1
            print(f"SKIP ({result['status']})")
            continue
        n_results = len(result["results"])
        if n_results == 0:
            print("SKIP (no trades)")
            continue
        best = max(result["results"], key=lambda r: r["pnl"])
        print(f"{n_results:>3} strats | Best: {best['strategy_name']:<25} WR:{best['wr']:.0f}% PnL:{best['pnl']:+.2f}%")
        all_results.append(result)
        time.sleep(0.1)  # Rate limiting

    elapsed = time.time() - t0
    print(f"\n  Scanned in {elapsed:.1f}s | {len(all_results)} coins OK | {sum(rejected.values())} rejected")
    for reason, count in rejected.items():
        if count > 0:
            print(f"    {reason}: {count}")

    if not all_results:
        print("  No results!")
        return

    # Step 3: Rank and grade coins
    print(f"\n[3/4] Ranking coins...")
    coin_grades = []
    for result in all_results:
        sym = result["symbol"]
        strats = result["results"]
        if not strats:
            continue
        best = max(strats, key=lambda r: r["pnl"])
        avg_wr = sum(r["wr"] for r in strats) / len(strats)
        avg_pnl = sum(r["avg_pnl"] for r in strats) / len(strats)
        profitable = sum(1 for r in strats if r["pnl"] > 0)
        pct_profitable = profitable / len(strats) * 100

        # Grade: A (>60% profitable strats), B (>40%), C (>20%), D (<20%)
        if pct_profitable >= 60 and best["wr"] >= 55:
            grade = "A"
        elif pct_profitable >= 40 and best["wr"] >= 50:
            grade = "B"
        elif pct_profitable >= 20:
            grade = "C"
        else:
            grade = "D"

        coin_grades.append({
            "symbol": sym, "grade": grade,
            "best_strategy": best["strategy_name"], "best_group": best["strategy_group"],
            "best_wr": best["wr"], "best_pnl": best["pnl"], "best_avg_pnl": best["avg_pnl"],
            "avg_wr": avg_wr, "avg_pnl": avg_pnl,
            "profitable_strats": profitable, "total_strats": len(strats),
            "pct_profitable": pct_profitable,
            "volatility": result["quality"]["volatility_pct"],
            "volume": result["quality"]["avg_volume"],
            "all_results": strats,
        })

    coin_grades.sort(key=lambda x: ({"A":4,"B":3,"C":2,"D":1}[x["grade"]], x["best_pnl"]), reverse=True)

    # Step 4: Display results
    print(f"\n[4/4] Results")
    print()
    print("=" * 70)
    print("  COIN POOL — RANKING PAR GRADE")
    print("=" * 70)

    for grade in ["A", "B", "C", "D"]:
        graded = [c for c in coin_grades if c["grade"] == grade]
        if not graded:
            continue
        print(f"\n  --- GRADE {grade} ({len(graded)} coins) ---")
        for c in graded[:15]:  # Top 15 per grade
            print(f"  {c['symbol']:<22} | Best: {c['best_strategy']:<25} "
                  f"WR:{c['best_wr']:>5.1f}% PnL:{c['best_pnl']:>+7.2f}% | "
                  f"Profitable: {c['pct_profitable']:.0f}% ({c['profitable_strats']}/{c['total_strats']}) | "
                  f"Vol:{c['volatility']:.3f}%")

    # Best strategies globally
    print()
    print("=" * 70)
    print("  TOP STRATEGIES GLOBALES")
    print("=" * 70)
    strat_global = {}
    for result in all_results:
        for r in result["results"]:
            sid = r["strategy_name"]
            if sid not in strat_global:
                strat_global[sid] = {"name": sid, "group": r["strategy_group"],
                                     "coins": 0, "wins": 0, "total_pnl": 0, "total_trades": 0}
            strat_global[sid]["coins"] += 1
            strat_global[sid]["wins"] += 1 if r["pnl"] > 0 else 0
            strat_global[sid]["total_pnl"] += r["pnl"]
            strat_global[sid]["total_trades"] += r["total"]

    strat_list = sorted(strat_global.values(), key=lambda x: x["total_pnl"], reverse=True)
    print(f"\n  {'Strategy':<30} {'Group':<12} {'Coins':>5} {'Win%':>6} {'PnL':>10} {'Trades':>7}")
    print(f"  {'-'*30} {'-'*12} {'-'*5} {'-'*6} {'-'*10} {'-'*7}")
    for s in strat_list[:20]:
        coin_wr = s["wins"] / s["coins"] * 100 if s["coins"] > 0 else 0
        print(f"  {s['name']:<30} {s['group']:<12} {s['coins']:>5} {coin_wr:>5.0f}% {s['total_pnl']:>+9.2f}% {s['total_trades']:>7}")

    # Final pool
    pool = [c for c in coin_grades if c["grade"] in ("A", "B")]
    print()
    print("=" * 70)
    print(f"  POOL FINALE: {len(pool)} COINS (Grade A+B)")
    print("=" * 70)
    for c in pool:
        # Top 3 strategies for this coin
        top3 = sorted(c["all_results"], key=lambda r: r["pnl"], reverse=True)[:3]
        strats_str = " | ".join(f"{t['strategy_name']}({t['wr']:.0f}%)" for t in top3)
        print(f"  [{c['grade']}] {c['symbol']:<22} Top: {strats_str}")

    # Save to DB
    if args.save:
        print(f"\n  Saving to {DB_PATH}...")
        db = init_db()
        run_ts = datetime.now().isoformat()
        best_overall = coin_grades[0] if coin_grades else None
        cur = db.execute(
            "INSERT INTO scan_runs (timestamp, coins_scanned, strategies_run, total_trades, "
            "best_strategy, best_wr, best_pnl) VALUES (?,?,?,?,?,?,?)",
            (run_ts, len(all_results), len(strategies),
             sum(sum(r["total"] for r in res["results"]) for res in all_results),
             best_overall["best_strategy"] if best_overall else "",
             best_overall["best_wr"] if best_overall else 0,
             best_overall["best_pnl"] if best_overall else 0)
        )
        run_id = cur.lastrowid

        for c in coin_grades:
            db.execute(
                "INSERT OR REPLACE INTO coin_scores "
                "(run_id, symbol, best_strategy, best_wr, best_pnl, avg_wr, avg_pnl, "
                "volatility, volume, grade) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, c["symbol"], c["best_strategy"], c["best_wr"], c["best_pnl"],
                 c["avg_wr"], c["avg_pnl"], c["volatility"], c["volume"], c["grade"])
            )
            for r in c["all_results"]:
                db.execute(
                    "INSERT OR REPLACE INTO strategy_results "
                    "(run_id, symbol, strategy_id, strategy_name, strategy_group, "
                    "total_trades, wins, losses, wr, pnl, avg_pnl, avg_bars, long_wr, short_wr) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run_id, c["symbol"], r["strategy_id"], r["strategy_name"],
                     r["strategy_group"], r["total"], r["wins"], r["losses"],
                     r["wr"], r["pnl"], r["avg_pnl"], r["avg_bars"],
                     r["long_wr"], r["short_wr"])
                )

        # Update coin pool
        for c in pool:
            db.execute(
                "INSERT OR REPLACE INTO coin_pool "
                "(symbol, grade, best_strategy, best_wr, best_pnl, volatility, volume, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (c["symbol"], c["grade"], c["best_strategy"], c["best_wr"],
                 c["best_pnl"], c["volatility"], c["volume"], run_ts)
            )

        db.commit()
        db.close()
        print(f"  Saved: {len(coin_grades)} coins, {len(pool)} in pool")

    print()
    print(f"  Scan complete: {len(all_results)} coins, {len(strategies)} strategies")
    print(f"  Pool: {len(pool)} coins Grade A+B")
    print("=" * 70)


if __name__ == "__main__":
    main()
