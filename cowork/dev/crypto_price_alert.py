#!/usr/bin/env python3
"""crypto_price_alert.py — Smart crypto price monitoring with Telegram alerts.

Monitors prices from MEXC API. Sends alerts ONLY when:
- Price drops >3% vs last check (or custom threshold)
- Price drops >5% in 24h
- Price hits new 24h low
Regular price summary every N minutes (configurable).

CLI:
    --once         : fetch and send prices once
    --watch        : continuous smart monitoring (default 5 min)
    --interval N   : check every N minutes (default 5)
    --drop-pct N   : alert threshold for drop between checks (default 3)
    --pairs X,Y    : comma-separated pairs (default: IPUSDT,ASTERUSDT)
    --stats        : show price history

Stdlib-only (json, argparse, urllib, sqlite3, time).
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TURBO_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"

def _alerts_enabled():
    return not (TURBO_ROOT / "data" / ".trading_alerts_off").exists()

MEXC_TICKER_URL = "https://api.mexc.com/api/v3/ticker/24hr"

# Thresholds
DEFAULT_DROP_PCT = 3.0      # Alert if price drops > X% vs last check
DROP_24H_ALERT = 5.0        # Alert if 24h change exceeds this
SUMMARY_EVERY = 6           # Send summary every N checks (e.g., every 30 min if interval=5)


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS crypto_price_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        pair TEXT NOT NULL,
        price REAL,
        change_24h_pct REAL,
        volume_24h REAL,
        high_24h REAL,
        low_24h REAL
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def fetch_price(pair):
    """Fetch ticker from MEXC API."""
    url = f"{MEXC_TICKER_URL}?symbol={pair}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return {
            "pair": pair,
            "price": float(data.get("lastPrice", 0)),
            "change_24h_pct": float(data.get("priceChangePercent", 0)),
            "volume_24h": float(data.get("quoteVolume", 0)),
            "high_24h": float(data.get("highPrice", 0)),
            "low_24h": float(data.get("lowPrice", 0)),
            "bid": float(data.get("bidPrice", 0)),
            "ask": float(data.get("askPrice", 0)),
        }
    except Exception as e:
        return {"pair": pair, "error": str(e)[:100]}


def send_telegram(text):
    """Send message to Telegram. Respects global alert flag."""
    if not _alerts_enabled():
        return 0
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        resp = urllib.request.urlopen(req, timeout=10)
        r = json.loads(resp.read())
        return r.get("result", {}).get("message_id", 0)
    except Exception:
        try:
            data2 = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
            req2 = urllib.request.Request(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data2
            )
            urllib.request.urlopen(req2, timeout=10)
        except Exception:
            pass
    return 0


def fmt_price(price):
    """Format price with appropriate decimal places."""
    if price < 0.001:
        return f"{price:.8f}"
    elif price < 0.01:
        return f"{price:.6f}"
    elif price < 1:
        return f"{price:.4f}"
    elif price < 100:
        return f"{price:.3f}"
    return f"{price:.2f}"


def fmt_vol(vol):
    """Format volume."""
    if vol > 1_000_000:
        return f"{vol / 1_000_000:.1f}M"
    elif vol > 1_000:
        return f"{vol / 1_000:.1f}K"
    return f"{vol:.0f}"


def get_last_price(conn, pair):
    """Get the last recorded price for a pair."""
    row = conn.execute("""
        SELECT price FROM crypto_price_alerts
        WHERE pair = ? ORDER BY id DESC LIMIT 1
    """, (pair,)).fetchone()
    return row["price"] if row else None


def store_price(conn, pair, data):
    """Store price data."""
    conn.execute("""
        INSERT INTO crypto_price_alerts
        (timestamp, pair, price, change_24h_pct, volume_24h, high_24h, low_24h)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), pair, data["price"],
          data["change_24h_pct"], data["volume_24h"],
          data["high_24h"], data["low_24h"]))


def check_and_alert(pairs, drop_threshold):
    """Check prices, detect drops, send alerts if needed."""
    conn = get_db()
    alerts = []
    prices = []

    for pair in pairs:
        p = fetch_price(pair)
        if "error" in p:
            prices.append(p)
            continue

        prices.append(p)
        last_price = get_last_price(conn, pair)
        store_price(conn, pair, p)

        # Check for drops
        if last_price and last_price > 0:
            change_vs_last = (p["price"] - last_price) / last_price * 100
            if change_vs_last < -drop_threshold:
                alerts.append({
                    "pair": pair,
                    "type": "drop_vs_last",
                    "price": p["price"],
                    "last_price": last_price,
                    "change_pct": change_vs_last,
                })

        # Check 24h drop
        if p["change_24h_pct"] < -DROP_24H_ALERT:
            alerts.append({
                "pair": pair,
                "type": "drop_24h",
                "price": p["price"],
                "change_24h": p["change_24h_pct"],
            })

        # Check new 24h low
        if p["price"] <= p["low_24h"] * 1.002:  # Within 0.2% of 24h low
            alerts.append({
                "pair": pair,
                "type": "near_low",
                "price": p["price"],
                "low_24h": p["low_24h"],
            })

    conn.commit()
    conn.close()
    return prices, alerts


def format_drop_alert(alerts):
    """Format urgent drop alert."""
    ts = datetime.now().strftime("%H:%M:%S")
    lines = [f"<b>ALERTE PRIX</b>  <code>{ts}</code>", ""]

    for a in alerts:
        pair = a["pair"]
        if a["type"] == "drop_vs_last":
            lines.append(f"<b>{pair}</b> CHUTE {a['change_pct']:.1f}%")
            lines.append(f"  ${fmt_price(a['last_price'])} -> ${fmt_price(a['price'])}")
        elif a["type"] == "drop_24h":
            lines.append(f"<b>{pair}</b> -24h: {a['change_24h']:.1f}%")
            lines.append(f"  Prix: ${fmt_price(a['price'])}")
        elif a["type"] == "near_low":
            lines.append(f"<b>{pair}</b> PROCHE DU BAS 24h")
            lines.append(f"  Prix: ${fmt_price(a['price'])} | Low: ${fmt_price(a['low_24h'])}")
        lines.append("")

    return "\n".join(lines)


def format_summary(prices):
    """Format regular price summary."""
    ts = datetime.now().strftime("%H:%M:%S")
    lines = [f"<b>Prix</b> <code>{ts}</code>"]

    for p in prices:
        if "error" in p:
            continue
        change = p["change_24h_pct"]
        arrow = "++" if change > 3 else "+" if change > 0 else "--" if change < -3 else "-" if change < 0 else "="
        lines.append(f"  {p['pair']} {arrow} ${fmt_price(p['price'])} ({change:+.1f}%) vol ${fmt_vol(p['volume_24h'])}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Smart Crypto Price Alert")
    parser.add_argument("--once", action="store_true", help="Fetch and send once")
    parser.add_argument("--watch", action="store_true", help="Smart continuous monitoring")
    parser.add_argument("--interval", type=int, default=5, help="Check interval (minutes)")
    parser.add_argument("--drop-pct", type=float, default=DEFAULT_DROP_PCT,
                        help=f"Drop threshold for alert (default {DEFAULT_DROP_PCT}%%)")
    parser.add_argument("--pairs", type=str, default="IPUSDT,ASTERUSDT",
                        help="Comma-separated pairs")
    parser.add_argument("--stats", action="store_true", help="Price history")
    args = parser.parse_args()

    if not any([args.once, args.watch, args.stats]):
        parser.print_help()
        sys.exit(1)

    pairs = [p.strip().upper() for p in args.pairs.split(",")]

    if args.stats:
        conn = get_db()
        rows = conn.execute("""
            SELECT pair, price, change_24h_pct, timestamp
            FROM crypto_price_alerts
            ORDER BY id DESC LIMIT 30
        """).fetchall()
        conn.close()
        print(json.dumps({"history": [dict(r) for r in rows]}, indent=2))
        return

    if args.watch:
        print(f"Smart watch: {', '.join(pairs)} every {args.interval}m | drop alert >{args.drop_pct}%")
        check_count = 0
        while True:
            prices, alerts = check_and_alert(pairs, args.drop_pct)
            check_count += 1
            ts = datetime.now().strftime("%H:%M:%S")

            # Always send alerts immediately
            if alerts:
                msg = format_drop_alert(alerts)
                send_telegram(msg)
                print(f"  [{ts}] ALERT: {len(alerts)} alertes envoyees")
                for a in alerts:
                    print(f"    {a['pair']} {a['type']}: {a.get('change_pct', a.get('change_24h', '')):.1f}%")

            # Send summary every N checks
            if check_count % SUMMARY_EVERY == 0:
                msg = format_summary(prices)
                send_telegram(msg)
                print(f"  [{ts}] Summary sent")

            # Log
            for p in prices:
                if "error" not in p:
                    print(f"  [{ts}] {p['pair']}: ${p['price']} ({p['change_24h_pct']:+.2f}%)")

            time.sleep(args.interval * 60)
    else:
        # --once: fetch, store, send summary + any alerts
        prices, alerts = check_and_alert(pairs, args.drop_pct)

        if alerts:
            send_telegram(format_drop_alert(alerts))

        msg = format_summary(prices)
        mid = send_telegram(msg)

        result = {
            "timestamp": datetime.now().isoformat(),
            "pairs": prices,
            "alerts": alerts,
            "telegram_sent": True,
            "message_id": mid,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
