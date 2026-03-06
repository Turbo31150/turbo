#!/usr/bin/env python3
"""Trading Intelligence — Autonomous market analysis and signal generation.

Monitors crypto markets, generates trading signals via cluster consensus,
backtests strategies, and sends alerts to Telegram.
"""
import argparse
import json
import sqlite3
import time
import urllib.request
from pathlib import Path

DB_PATH = Path(__file__).parent / "trading_intel.db"
from _paths import TURBO_DIR as TURBO

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT", "PEPEUSDT",
         "DOGEUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT"]

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY, ts REAL, pair TEXT, direction TEXT,
        score INTEGER, entry_price REAL, tp_price REAL, sl_price REAL,
        source TEXT, status TEXT DEFAULT 'pending')""")
    db.execute("""CREATE TABLE IF NOT EXISTS market_data (
        id INTEGER PRIMARY KEY, ts REAL, pair TEXT, price REAL,
        change_24h REAL, volume_24h REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS analysis_runs (
        id INTEGER PRIMARY KEY, ts REAL, pairs_analyzed INTEGER,
        signals_generated INTEGER, cluster_nodes_used TEXT)""")
    db.commit()
    return db

def fetch_prices():
    """Fetch current prices from public API."""
    prices = {}
    try:
        url = "https://api.mexc.com/api/v3/ticker/24hr"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            for item in data:
                symbol = item.get("symbol", "")
                if symbol in PAIRS:
                    prices[symbol] = {
                        "price": float(item.get("lastPrice", 0)),
                        "change_24h": float(item.get("priceChangePercent", 0)),
                        "volume": float(item.get("quoteVolume", 0)),
                    }
    except Exception as e:
        print(f"  Prix API erreur: {e}")
    return prices

def store_prices(db, prices):
    """Store price data."""
    for pair, data in prices.items():
        db.execute(
            "INSERT INTO market_data (ts, pair, price, change_24h, volume_24h) VALUES (?,?,?,?,?)",
            (time.time(), pair, data["price"], data["change_24h"], data["volume"]))
    db.commit()

def analyze_pair_with_cluster(pair, price_data):
    """Ask cluster to analyze a trading pair."""
    prompt = (
        f"/nothink\nAnalyse trading {pair}: prix={price_data['price']}, "
        f"variation_24h={price_data['change_24h']:.2f}%, volume={price_data['volume']:.0f}. "
        f"Donne un score 0-100, direction (LONG/SHORT/NEUTRAL), et justification en 2 lignes. "
        f"Format: SCORE:XX DIRECTION:XXX RAISON:xxx"
    )
    try:
        body = json.dumps({
            "model": "qwen3-8b", "input": prompt,
            "temperature": 0.1, "max_output_tokens": 256, "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:1234/api/v1/chat",
            data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    text = item.get("content", [{}])[0].get("text", "")
                    return parse_signal(text, pair, price_data)
    except Exception:
        pass
    return None

def parse_signal(text, pair, price_data):
    """Parse AI response into a signal."""
    import re
    score_m = re.search(r"SCORE[:\s]*(\d+)", text, re.IGNORECASE)
    dir_m = re.search(r"DIRECTION[:\s]*(LONG|SHORT|NEUTRAL)", text, re.IGNORECASE)
    score = int(score_m.group(1)) if score_m else 50
    direction = dir_m.group(1).upper() if dir_m else "NEUTRAL"

    price = price_data["price"]
    tp_pct = 0.004  # 0.4%
    sl_pct = 0.0025  # 0.25%
    if direction == "LONG":
        tp = price * (1 + tp_pct)
        sl = price * (1 - sl_pct)
    elif direction == "SHORT":
        tp = price * (1 - tp_pct)
        sl = price * (1 + sl_pct)
    else:
        tp = sl = price

    return {
        "pair": pair, "direction": direction, "score": score,
        "entry": price, "tp": tp, "sl": sl, "reason": text[:200],
    }

def send_telegram_signal(signal):
    """Send trading signal to Telegram."""
    try:
        edb = sqlite3.connect(str(TURBO / "data" / "etoile.db"))
        row = edb.execute("SELECT value FROM memories WHERE key='telegram_bot_token'").fetchone()
        token = row[0] if row else ""
        edb.close()
    except Exception:
        return

    if not token:
        return

    icon = {"LONG": "🟢", "SHORT": "🔴", "NEUTRAL": "⚪"}.get(signal["direction"], "⚪")
    msg = (
        f"{icon} *Trading Signal — {signal['pair']}*\n"
        f"Direction: {signal['direction']} | Score: {signal['score']}/100\n"
        f"Entry: {signal['entry']:.4f}\n"
        f"TP: {signal['tp']:.4f} | SL: {signal['sl']:.4f}\n"
        f"Source: M1/qwen3-8b"
    )
    try:
        body = json.dumps({"chat_id": "2010747443", "text": msg, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def run_analysis(db, notify=False):
    """Full market analysis pipeline."""
    prices = fetch_prices()
    if not prices:
        print("  Pas de donnees de prix")
        return 0

    store_prices(db, prices)
    signals = 0

    for pair, data in prices.items():
        signal = analyze_pair_with_cluster(pair, data)
        if signal and signal["score"] >= 70 and signal["direction"] != "NEUTRAL":
            db.execute(
                "INSERT INTO signals (ts, pair, direction, score, entry_price, tp_price, sl_price, source) VALUES (?,?,?,?,?,?,?,?)",
                (time.time(), signal["pair"], signal["direction"], signal["score"],
                 signal["entry"], signal["tp"], signal["sl"], "M1"))
            signals += 1
            icon = {"LONG": "🟢", "SHORT": "🔴"}.get(signal["direction"], "⚪")
            print(f"  {icon} {pair}: {signal['direction']} score={signal['score']}")
            if notify:
                send_telegram_signal(signal)

    db.execute(
        "INSERT INTO analysis_runs (ts, pairs_analyzed, signals_generated, cluster_nodes_used) VALUES (?,?,?,?)",
        (time.time(), len(prices), signals, json.dumps(["M1"])))
    db.commit()
    return signals

def main():
    parser = argparse.ArgumentParser(description="Trading Intelligence")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--notify", action="store_true", help="Send signals to Telegram")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=600, help="Seconds between scans")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    db = init_db()

    if args.stats:
        total = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        longs = db.execute("SELECT COUNT(*) FROM signals WHERE direction='LONG'").fetchone()[0]
        shorts = db.execute("SELECT COUNT(*) FROM signals WHERE direction='SHORT'").fetchone()[0]
        avg_score = db.execute("SELECT AVG(score) FROM signals").fetchone()[0] or 0
        print(f"Signals: {total} total | {longs} LONG | {shorts} SHORT | avg score {avg_score:.0f}")
        return

    if args.once or not args.loop:
        print("=== Trading Intelligence ===")
        signals = run_analysis(db, args.notify)
        print(f"  {signals} signals generes sur {len(PAIRS)} paires")

    if args.loop:
        print("Trading Intelligence en boucle continue...")
        while True:
            try:
                signals = run_analysis(db, args.notify)
                ts = time.strftime('%H:%M')
                print(f"[{ts}] {signals} signals")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
