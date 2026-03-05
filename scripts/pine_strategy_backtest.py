#!/usr/bin/env python3
"""
Backtest de la strategie Pine Script 1Min Amelioree - TP Dynamique
Traduit de TradingView en Python pour comparaison avec sniper_scanner.

Indicateurs:
- EMA 8/21 crossover
- RSI 14 filtre
- Stochastic 14/3/3 filtre
- TP/SL dynamique base sur ATR(14) * 1.5

Usage:
    python scripts/pine_strategy_backtest.py                    # Backtest top 10 paires
    python scripts/pine_strategy_backtest.py --pairs BTC,ETH    # Paires specifiques
    python scripts/pine_strategy_backtest.py --candles 500       # Plus de bougies
    python scripts/pine_strategy_backtest.py --live              # Signaux live actuels
"""

import json, math, sys, urllib.request, argparse
from datetime import datetime, timezone
from pathlib import Path

# === CONFIG (adapte au 1min selon Pine Script v2) ===
EMA_SHORT = 5       # 5 sur 1min (8 sur 5min, 10 sur 1h)
EMA_LONG = 13       # 13 sur 1min (21 sur 5min, 30 sur 1h)
RSI_LENGTH = 7      # 7 sur 1min (10 sur 5min, 12 sur 1h)
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
STOCH_LENGTH = 14
STOCH_K_SMOOTH = 3
STOCH_D_SMOOTH = 3
TP_MULTIPLIER = 1.0  # 1.0 sur 1min (1.2 sur 5min, 1.5 sur 1h)
SL_MULTIPLIER = 1.0  # 1.0 sur 1min (1.3 sur 5min, 1.6 sur 1h)
ATR_LENGTH = 14

DEFAULT_PAIRS = [
    "BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "PEPE_USDT",
    "DOGE_USDT", "XRP_USDT", "ADA_USDT", "AVAX_USDT", "LINK_USDT"
]


# === INDICATEURS (calcul manuel, stdlib only) ===

def ema(data, period):
    """Exponential Moving Average."""
    if len(data) < period:
        return [None] * len(data)
    result = [None] * (period - 1)
    k = 2.0 / (period + 1)
    result.append(sum(data[:period]) / period)
    for i in range(period, len(data)):
        result.append(data[i] * k + result[-1] * (1 - k))
    return result


def sma(data, period):
    """Simple Moving Average."""
    result = [None] * (period - 1)
    for i in range(period - 1, len(data)):
        result.append(sum(data[i - period + 1:i + 1]) / period)
    return result


def rsi(closes, period=14):
    """Relative Strength Index."""
    if len(closes) < period + 1:
        return [None] * len(closes)
    result = [None] * period
    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100.0 - 100.0 / (1 + rs))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - 100.0 / (1 + rs))
    return result


def stochastic(closes, highs, lows, length=14):
    """%K raw stochastic."""
    result = [None] * (length - 1)
    for i in range(length - 1, len(closes)):
        hh = max(highs[i - length + 1:i + 1])
        ll = min(lows[i - length + 1:i + 1])
        if hh == ll:
            result.append(50.0)
        else:
            result.append((closes[i] - ll) / (hh - ll) * 100)
    return result


def atr(highs, lows, closes, period=14):
    """Average True Range."""
    if len(closes) < 2:
        return [None] * len(closes)
    trs = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)
    # RMA (Wilder's smoothing) for ATR
    result = [None] * (period - 1)
    avg = sum(trs[:period]) / period
    result.append(avg)
    for i in range(period, len(trs)):
        avg = (avg * (period - 1) + trs[i]) / period
        result.append(avg)
    return result


# === DATA FETCHING ===

def fetch_klines_mexc(symbol, interval="Min1", limit=500):
    """Fetch klines from MEXC futures API."""
    url = f"https://contract.mexc.com/api/v1/contract/kline/{symbol}?interval={interval}&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())

        candles = []
        raw = data.get("data", {})

        # MEXC futures kline format
        if isinstance(raw, dict):
            times = raw.get("time", [])
            opens = raw.get("open", [])
            highs = raw.get("high", [])
            lows = raw.get("low", [])
            closes = raw.get("close", [])
            vols = raw.get("vol", [])

            for i in range(len(times)):
                candles.append({
                    "t": times[i],
                    "o": float(opens[i]),
                    "h": float(highs[i]),
                    "l": float(lows[i]),
                    "c": float(closes[i]),
                    "v": float(vols[i]) if i < len(vols) else 0
                })
        elif isinstance(raw, list):
            for k in raw:
                if isinstance(k, list) and len(k) >= 5:
                    candles.append({
                        "t": k[0], "o": float(k[1]), "h": float(k[2]),
                        "l": float(k[3]), "c": float(k[4]),
                        "v": float(k[5]) if len(k) > 5 else 0
                    })

        return candles
    except Exception as e:
        # Try spot API fallback
        try:
            spot_sym = symbol.replace("_", "")
            url2 = f"https://api.mexc.com/api/v3/klines?symbol={spot_sym}&interval=1m&limit={limit}"
            req2 = urllib.request.Request(url2, headers={"User-Agent": "JARVIS/1.0"})
            with urllib.request.urlopen(req2, timeout=20) as resp2:
                raw2 = json.loads(resp2.read())
            candles = []
            for k in raw2:
                candles.append({
                    "t": k[0], "o": float(k[1]), "h": float(k[2]),
                    "l": float(k[3]), "c": float(k[4]), "v": float(k[5])
                })
            return candles
        except Exception as e2:
            print(f"  [ERR] {symbol}: {e} / {e2}")
            return []


# === STRATEGY ENGINE ===

def run_strategy(candles, symbol="?", tp_mult=None, sl_mult=None):
    """Run the Pine Script strategy on candle data. Returns list of trades."""
    if tp_mult is None:
        tp_mult = TP_MULTIPLIER
    if sl_mult is None:
        sl_mult = SL_MULTIPLIER

    if len(candles) < max(EMA_LONG, RSI_LENGTH, STOCH_LENGTH, ATR_LENGTH) + 5:
        return []

    closes = [c["c"] for c in candles]
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]

    # Calculate indicators
    ema_s = ema(closes, EMA_SHORT)
    ema_l = ema(closes, EMA_LONG)
    rsi_vals = rsi(closes, RSI_LENGTH)
    stoch_raw = stochastic(closes, highs, lows, STOCH_LENGTH)
    stoch_k = sma([v if v is not None else 50 for v in stoch_raw], STOCH_K_SMOOTH)
    atr_vals = atr(highs, lows, closes, ATR_LENGTH)

    trades = []
    position = None  # None or {"dir": "LONG"/"SHORT", "entry": price, "tp": price, "sl": price, "bar": idx}

    start = max(EMA_LONG, RSI_LENGTH, STOCH_LENGTH, ATR_LENGTH) + 2

    for i in range(start, len(candles)):
        # Check if any indicator is None
        if any(v is None for v in [ema_s[i], ema_s[i-1], ema_l[i], ema_l[i-1],
                                     rsi_vals[i], stoch_k[i], atr_vals[i]]):
            continue

        # If in position, check TP/SL
        if position is not None:
            hit = None
            exit_price = None

            if position["dir"] == "LONG":
                # Check SL first (worst case)
                if lows[i] <= position["sl"]:
                    hit = "SL"
                    exit_price = position["sl"]
                elif highs[i] >= position["tp"]:
                    hit = "TP"
                    exit_price = position["tp"]
            else:  # SHORT
                if highs[i] >= position["sl"]:
                    hit = "SL"
                    exit_price = position["sl"]
                elif lows[i] <= position["tp"]:
                    hit = "TP"
                    exit_price = position["tp"]

            if hit:
                pnl = ((exit_price - position["entry"]) / position["entry"] * 100
                       if position["dir"] == "LONG"
                       else (position["entry"] - exit_price) / position["entry"] * 100)
                trades.append({
                    "symbol": symbol,
                    "dir": position["dir"],
                    "entry": position["entry"],
                    "exit": exit_price,
                    "tp_target": position["tp"],
                    "sl_target": position["sl"],
                    "result": hit,
                    "pnl": pnl,
                    "entry_bar": position["bar"],
                    "exit_bar": i,
                    "bars_held": i - position["bar"],
                    "entry_time": candles[position["bar"]].get("t", 0),
                    "exit_time": candles[i].get("t", 0),
                    "atr": position["atr_val"],
                    "rsi": position["rsi_val"],
                    "stoch": position["stoch_val"],
                })
                position = None

        # Entry conditions (only if flat)
        if position is None:
            # EMA crossover
            ema_cross_up = ema_s[i - 1] <= ema_l[i - 1] and ema_s[i] > ema_l[i]
            ema_cross_down = ema_s[i - 1] >= ema_l[i - 1] and ema_s[i] < ema_l[i]

            atr_val = atr_vals[i]
            rsi_val = rsi_vals[i]
            stoch_val = stoch_k[i]

            # LONG: EMA cross up + RSI < overbought + Stoch < 80
            if ema_cross_up and rsi_val < RSI_OVERBOUGHT and stoch_val < 80:
                tp_price = closes[i] + atr_val * tp_mult
                sl_price = closes[i] - atr_val * sl_mult
                position = {
                    "dir": "LONG", "entry": closes[i],
                    "tp": tp_price, "sl": sl_price, "bar": i,
                    "atr_val": atr_val, "rsi_val": rsi_val, "stoch_val": stoch_val
                }

            # SHORT: EMA cross down + RSI > oversold + Stoch > 20
            elif ema_cross_down and rsi_val > RSI_OVERSOLD and stoch_val > 20:
                tp_price = closes[i] - atr_val * tp_mult
                sl_price = closes[i] + atr_val * sl_mult
                position = {
                    "dir": "SHORT", "entry": closes[i],
                    "tp": tp_price, "sl": sl_price, "bar": i,
                    "atr_val": atr_val, "rsi_val": rsi_val, "stoch_val": stoch_val
                }

    # Close any remaining open position at last close
    if position is not None:
        last_close = closes[-1]
        pnl = ((last_close - position["entry"]) / position["entry"] * 100
               if position["dir"] == "LONG"
               else (position["entry"] - last_close) / position["entry"] * 100)
        trades.append({
            "symbol": symbol, "dir": position["dir"],
            "entry": position["entry"], "exit": last_close,
            "tp_target": position["tp"], "sl_target": position["sl"],
            "result": "OPEN", "pnl": pnl,
            "entry_bar": position["bar"], "exit_bar": len(candles) - 1,
            "bars_held": len(candles) - 1 - position["bar"],
            "entry_time": candles[position["bar"]].get("t", 0),
            "exit_time": candles[-1].get("t", 0),
            "atr": position["atr_val"], "rsi": position["rsi_val"],
            "stoch": position["stoch_val"],
        })

    return trades


# === REPORTING ===

def print_report(all_trades, sniper_stats=None):
    """Print comprehensive backtest report."""
    if not all_trades:
        print("Aucun trade genere.")
        return

    closed = [t for t in all_trades if t["result"] != "OPEN"]
    wins = [t for t in closed if t["result"] == "TP"]
    losses = [t for t in closed if t["result"] == "SL"]
    opens = [t for t in all_trades if t["result"] == "OPEN"]

    total_pnl = sum(t["pnl"] for t in closed)
    avg_pnl = total_pnl / len(closed) if closed else 0
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
    winrate = len(wins) / len(closed) * 100 if closed else 0
    avg_bars = sum(t["bars_held"] for t in closed) / len(closed) if closed else 0

    longs = [t for t in closed if t["dir"] == "LONG"]
    shorts = [t for t in closed if t["dir"] == "SHORT"]
    long_wins = [t for t in longs if t["result"] == "TP"]
    short_wins = [t for t in shorts if t["result"] == "TP"]
    long_wr = len(long_wins) / len(longs) * 100 if longs else 0
    short_wr = len(short_wins) / len(shorts) * 100 if shorts else 0

    print()
    print("=" * 70)
    print("  BACKTEST — Strategie Pine Script 1Min (EMA 8/21 + RSI + Stoch + ATR)")
    print("=" * 70)
    print(f"  Trades total:      {len(all_trades)} ({len(closed)} clotures, {len(opens)} ouverts)")
    print(f"  TP touches:        {len(wins):>4} ({len(wins)/len(all_trades)*100:.1f}%)")
    print(f"  SL touches:        {len(losses):>4} ({len(losses)/len(all_trades)*100:.1f}%)")
    print()
    print(f"  WIN RATE:          {winrate:.1f}%")
    print(f"  PnL total:         {total_pnl:+.3f}%")
    print(f"  PnL moyen:         {avg_pnl:+.3f}%")
    print(f"  PnL moyen WIN:     {avg_win:+.3f}%")
    print(f"  PnL moyen LOSS:    {avg_loss:+.3f}%")
    ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    print(f"  Ratio R:R:         {ratio:.2f}x")
    print(f"  Duree moy (bars):  {avg_bars:.1f} bougies 1min")
    print()
    print(f"  LONG:  {len(longs):>3} trades | WR: {long_wr:.1f}% ({len(long_wins)}W/{len(longs)-len(long_wins)}L)")
    print(f"  SHORT: {len(shorts):>3} trades | WR: {short_wr:.1f}% ({len(short_wins)}W/{len(shorts)-len(short_wins)}L)")

    # Per-symbol breakdown
    print()
    print("-" * 70)
    print("  PAR SYMBOLE")
    print("-" * 70)
    symbols = {}
    for t in closed:
        s = t["symbol"]
        if s not in symbols:
            symbols[s] = {"trades": 0, "wins": 0, "pnl": 0}
        symbols[s]["trades"] += 1
        symbols[s]["pnl"] += t["pnl"]
        if t["result"] == "TP":
            symbols[s]["wins"] += 1

    for sym, st in sorted(symbols.items(), key=lambda x: x[1]["pnl"], reverse=True):
        wr = st["wins"] / st["trades"] * 100 if st["trades"] > 0 else 0
        avg = st["pnl"] / st["trades"]
        print(f"  {sym:<18} {st['trades']:>3} trades | WR: {wr:.0f}% | PnL: {st['pnl']:+.3f}% (avg {avg:+.3f}%)")

    # Top trades
    if wins:
        best = max(wins, key=lambda t: t["pnl"])
        print(f"\n  Meilleur trade: {best['symbol']} {best['dir']} +{best['pnl']:.3f}% ({best['bars_held']} bars)")
    if losses:
        worst = min(losses, key=lambda t: t["pnl"])
        print(f"  Pire trade:     {worst['symbol']} {worst['dir']} {worst['pnl']:.3f}% ({worst['bars_held']} bars)")

    # === COMPARISON vs SNIPER ===
    print()
    print("=" * 70)
    print("  COMPARAISON: Pine Script vs Sniper Scanner")
    print("=" * 70)

    if sniper_stats:
        print(f"  {'Metrique':<25} {'Pine Script':>15} {'Sniper':>15} {'Diff':>10}")
        print(f"  {'-'*25} {'-'*15} {'-'*15} {'-'*10}")

        pine_wr = winrate
        sniper_wr = sniper_stats.get("winrate", 0)
        print(f"  {'Win Rate':<25} {pine_wr:>14.1f}% {sniper_wr:>14.1f}% {pine_wr-sniper_wr:>+9.1f}%")

        pine_pnl = avg_pnl
        sniper_pnl = sniper_stats.get("avg_pnl", 0)
        print(f"  {'PnL moyen':<25} {pine_pnl:>+14.3f}% {sniper_pnl:>+14.3f}% {pine_pnl-sniper_pnl:>+9.3f}%")

        pine_ratio = ratio
        sniper_ratio = sniper_stats.get("ratio", 0)
        print(f"  {'Ratio R:R':<25} {pine_ratio:>14.2f}x {sniper_ratio:>14.2f}x {pine_ratio-sniper_ratio:>+9.2f}x")

        pine_lwr = long_wr
        sniper_lwr = sniper_stats.get("long_wr", 0)
        print(f"  {'WR LONG':<25} {pine_lwr:>14.1f}% {sniper_lwr:>14.1f}% {pine_lwr-sniper_lwr:>+9.1f}%")

        pine_swr = short_wr
        sniper_swr = sniper_stats.get("short_wr", 0)
        print(f"  {'WR SHORT':<25} {pine_swr:>14.1f}% {sniper_swr:>14.1f}% {pine_swr-sniper_swr:>+9.1f}%")

        print()
        if pine_wr > sniper_wr and pine_pnl > sniper_pnl:
            print("  >>> PINE SCRIPT GAGNE sur les deux metriques")
        elif pine_wr > sniper_wr:
            print("  >>> PINE SCRIPT meilleur Win Rate, mais PnL inferieur")
        elif pine_pnl > sniper_pnl:
            print("  >>> PINE SCRIPT meilleur PnL, mais Win Rate inferieur")
        else:
            print("  >>> SNIPER SCANNER gagne sur les deux metriques")
    else:
        print("  (Pas de stats sniper pour comparaison)")

    # Live signals (open positions)
    if opens:
        print()
        print("-" * 70)
        print("  SIGNAUX LIVE (positions ouvertes)")
        print("-" * 70)
        for t in opens:
            sign = "+" if t["pnl"] >= 0 else ""
            print(f"  {t['symbol']:<18} {t['dir']:>5} | Entry: {t['entry']:<12.6g} | "
                  f"TP: {t['tp_target']:<12.6g} | SL: {t['sl_target']:<12.6g} | "
                  f"PnL: {sign}{t['pnl']:.2f}%")

    print("=" * 70)


def get_sniper_stats():
    """Load sniper scanner stats from DB for comparison."""
    import sqlite3
    db_path = Path(__file__).resolve().parent.parent / "data" / "sniper_scan.db"
    if not db_path.exists():
        return None
    try:
        db = sqlite3.connect(str(db_path))
        total = db.execute("SELECT COUNT(*) FROM signal_tracker").fetchone()[0]
        closed = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status != 'OPEN'").fetchone()[0]
        tp = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE tp1_hit=1 OR tp2_hit=1 OR tp3_hit=1").fetchone()[0]
        sl = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE sl_hit=1").fetchone()[0]
        avg_pnl = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE status != 'OPEN'").fetchone()[0] or 0
        avg_win = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE tp1_hit=1 OR tp2_hit=1 OR tp3_hit=1").fetchone()[0] or 0
        avg_loss = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE sl_hit=1").fetchone()[0] or 0

        long_total = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE direction='LONG' AND status != 'OPEN'").fetchone()[0]
        long_wins = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE direction='LONG' AND (tp1_hit=1 OR tp2_hit=1 OR tp3_hit=1)").fetchone()[0]
        short_total = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE direction='SHORT' AND status != 'OPEN'").fetchone()[0]
        short_wins = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE direction='SHORT' AND (tp1_hit=1 OR tp2_hit=1 OR tp3_hit=1)").fetchone()[0]

        db.close()
        return {
            "total": total, "closed": closed,
            "winrate": (tp / closed * 100) if closed > 0 else 0,
            "avg_pnl": avg_pnl,
            "ratio": abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            "long_wr": (long_wins / long_total * 100) if long_total > 0 else 0,
            "short_wr": (short_wins / short_total * 100) if short_total > 0 else 0,
        }
    except Exception as e:
        print(f"  [WARN] Sniper DB: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Pine Script Strategy Backtest")
    parser.add_argument("--pairs", type=str, default=None, help="Comma-separated pairs (e.g., BTC,ETH)")
    parser.add_argument("--candles", type=int, default=500, help="Number of 1min candles (default: 500)")
    parser.add_argument("--live", action="store_true", help="Show live signals only")
    parser.add_argument("--tp", type=float, default=1.0, help="TP ATR multiplier")
    parser.add_argument("--sl", type=float, default=1.0, help="SL ATR multiplier")
    args = parser.parse_args()

    tp_mult = args.tp
    sl_mult = args.sl

    if args.pairs:
        pairs = [p.strip().upper() + ("_USDT" if "_USDT" not in p.upper() else "") for p in args.pairs.split(",")]
    else:
        pairs = DEFAULT_PAIRS

    print(f"Pine Script 1Min Strategy Backtest")
    print(f"Paires: {', '.join(pairs)}")
    print(f"Bougies: {args.candles} (1min)")
    print(f"TP: ATR x {tp_mult} | SL: ATR x {sl_mult}")
    print()

    all_trades = []
    for pair in pairs:
        print(f"  Fetching {pair}...", end=" ", flush=True)
        candles = fetch_klines_mexc(pair, limit=args.candles)
        if not candles:
            print("SKIP (no data)")
            continue
        print(f"{len(candles)} candles", end=" -> ", flush=True)
        trades = run_strategy(candles, symbol=pair, tp_mult=tp_mult, sl_mult=sl_mult)
        closed = [t for t in trades if t["result"] != "OPEN"]
        wins = [t for t in closed if t["result"] == "TP"]
        print(f"{len(trades)} trades ({len(wins)} TP / {len(closed) - len(wins)} SL)")
        all_trades.extend(trades)

    # Load sniper stats for comparison
    sniper_stats = get_sniper_stats()

    print_report(all_trades, sniper_stats)


if __name__ == "__main__":
    main()
