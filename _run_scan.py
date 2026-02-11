"""Lightweight breakout scan using MEXC API directly — no numpy needed.
Inserts fresh signals into trading_latest.db, then tests the pipeline.
"""
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import sqlite3
import urllib.request
from datetime import datetime

sys.path.insert(0, "F:/BUREAU/turbo")

DB_PATH = "F:/BUREAU/carV1/database/trading_latest.db"
MEXC_BASE = "https://contract.mexc.com/api/v1/contract"

SYMBOLS = [
    "BTC_USDT", "ETH_USDT", "SOL_USDT", "XRP_USDT", "DOGE_USDT",
    "SUI_USDT", "AVAX_USDT", "LINK_USDT", "ADA_USDT", "PEPE_USDT",
    "OP_USDT", "ARB_USDT", "NEAR_USDT", "APT_USDT", "INJ_USDT",
    "SEI_USDT", "FET_USDT", "TAO_USDT", "HBAR_USDT", "TIA_USDT",
]


def fetch_ticker(symbol):
    """Fetch ticker data from MEXC Futures API."""
    try:
        url = f"{MEXC_BASE}/ticker?symbol={symbol}"
        resp = urllib.request.urlopen(url, timeout=10)
        data = json.loads(resp.read())
        return data.get("data")
    except Exception as e:
        print(f"  [ERR] {symbol}: {e}")
        return None


def analyze(symbol, ticker):
    """Simple breakout analysis from ticker data."""
    price = float(ticker["lastPrice"])
    high24 = float(ticker["high24Price"])
    low24 = float(ticker["lower24Price"])
    volume = float(ticker["volume24"])
    change = float(ticker["riseFallRate"]) * 100  # percent

    range_24h = high24 - low24 if high24 > low24 else 0.0001
    range_pos = (price - low24) / range_24h  # 0=bottom, 1=top

    # Score components
    score = 0
    reasons = []

    # Momentum (strong move)
    abs_change = abs(change)
    if abs_change > 5:
        score += 30
        reasons.append("STRONG_MOVE")
    elif abs_change > 3:
        score += 20
        reasons.append("MOMENTUM")
    elif abs_change > 1.5:
        score += 10
        reasons.append("TREND")

    # Range position (breakout detection)
    if range_pos > 0.85:
        score += 25
        reasons.append("NEAR_HIGH")
    elif range_pos < 0.15:
        score += 25
        reasons.append("NEAR_LOW")
    elif 0.4 < range_pos < 0.6:
        score += 5
        reasons.append("MID_RANGE")

    # Volume
    if volume > 1_000_000:
        score += 15
        reasons.append("HIGH_VOL")
    elif volume > 100_000:
        score += 10
        reasons.append("OK_VOL")

    # Direction
    if change > 0 and range_pos > 0.7:
        direction = "LONG"
        score += 15
        reasons.append("BULL_BREAKOUT")
    elif change < 0 and range_pos < 0.3:
        direction = "SHORT"
        score += 15
        reasons.append("BEAR_BREAKOUT")
    elif change > 1:
        direction = "LONG"
        score += 5
    elif change < -1:
        direction = "SHORT"
        score += 5
    else:
        direction = "LONG" if change >= 0 else "SHORT"

    # Clamp score
    score = min(score, 100)

    # TP/SL calculation (based on ATR proxy = range_24h)
    atr_proxy = range_24h * 0.3  # ~30% of daily range as ATR proxy

    if direction == "LONG":
        tp1 = price + atr_proxy * 1.0
        tp2 = price + atr_proxy * 1.618
        tp3 = price + atr_proxy * 2.618
        sl = price - atr_proxy * 0.75
    else:
        tp1 = price - atr_proxy * 1.0
        tp2 = price - atr_proxy * 1.618
        tp3 = price - atr_proxy * 2.618
        sl = price + atr_proxy * 0.75

    return {
        "symbol": symbol.replace("_", "/"),
        "direction": direction,
        "price": price,
        "score": score,
        "volume": volume,
        "volume_m": round(volume / 1_000_000, 2),
        "change_24h": round(change, 2),
        "range_position": round(range_pos, 4),
        "reasons": json.dumps(reasons),
        "tp1": round(tp1, 8),
        "tp2": round(tp2, 8),
        "tp3": round(tp3, 8),
        "sl": round(sl, 8),
    }


def main():
    print(f"\n{'='*60}")
    print(f"  SCAN BREAKOUT → DB SIGNALS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    signals = []
    for sym in SYMBOLS:
        ticker = fetch_ticker(sym)
        if ticker:
            sig = analyze(sym, ticker)
            signals.append(sig)
            marker = "*" if sig["score"] >= 50 else " "
            print(f"  {marker} {sig['symbol']:12s} {sig['direction']:5s} score={sig['score']:3d} "
                  f"price={sig['price']:.6f} chg={sig['change_24h']:+.1f}% "
                  f"{'  '.join(json.loads(sig['reasons']))}")

    print(f"\n[SCAN] {len(signals)} coins analyses")

    # Insert into DB
    conn = sqlite3.connect(DB_PATH)
    inserted = 0
    for sig in signals:
        try:
            conn.execute(
                """INSERT INTO signals
                   (symbol, direction, price, score, volume, volume_m,
                    change_24h, range_position, reasons, tp1, tp2, tp3, sl,
                    source, executed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'BREAKOUT_DETECTOR', 0, CURRENT_TIMESTAMP)""",
                (sig["symbol"], sig["direction"], sig["price"], sig["score"],
                 sig["volume"], sig["volume_m"], sig["change_24h"], sig["range_position"],
                 sig["reasons"], sig["tp1"], sig["tp2"], sig["tp3"], sig["sl"]),
            )
            inserted += 1
        except Exception as e:
            print(f"  [ERR] Insert {sig['symbol']}: {e}")
    conn.commit()
    conn.close()

    print(f"[DB] {inserted} signaux frais inseres")

    # Test pipeline
    print(f"\n{'='*60}")
    print("  TEST PIPELINE TRADING")
    print(f"{'='*60}")

    from src.trading import get_pending_signals, pipeline_status, validate_signal

    pending = get_pending_signals(min_score=30, max_age_min=5, limit=10)
    print(f"\n[PENDING] {len(pending)} signaux (score>=30, <5min):")
    for s in pending:
        valid, reason = validate_signal(s)
        tag = "OK" if valid else f"REJECT({reason})"
        print(f"  #{s['id']} {s['symbol']:12s} {s['direction']:5s} "
              f"score={s['score']:3d} entry={s['price']:.6f} [{tag}]")

    status = pipeline_status()
    print(f"\n[STATUS]")
    print(f"  Total signals:   {status['pipeline']['total_signals']}")
    print(f"  Pending (fresh): {status['pipeline']['pending_signals']}")
    print(f"  Trades open:     {status['trades']['open']}")
    print(f"  Dry run:         {status['config']['dry_run']}")

    print("\nDone!")


if __name__ == "__main__":
    main()
