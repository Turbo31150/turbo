#!/usr/bin/env python3
"""JARVIS Auto Trader — Scanner MEXC Futures avec alertes Telegram."""
import json, os, sys, time, urllib.request
from datetime import datetime
from pathlib import Path
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT

PAIRS = ["BTC_USDT","ETH_USDT","SOL_USDT","SUI_USDT","PEPE_USDT","DOGE_USDT","XRP_USDT","ADA_USDT","AVAX_USDT","LINK_USDT"]
ALERT_THRESHOLD = 2.0  # % variation
# TELEGRAM_TOKEN loaded from _paths (.env)
# TELEGRAM_CHAT loaded from _paths (.env)
TURBO_ROOT = Path(__file__).resolve().parent.parent.parent

def _alerts_enabled():
    return not (TURBO_ROOT / "data" / ".trading_alerts_off").exists()

def send_telegram(msg):
    if not _alerts_enabled():
        return
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def scan_mexc():
    req = urllib.request.Request("https://contract.mexc.com/api/v1/contract/ticker")
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    tickers = data.get("data", [])
    results = []
    for t in tickers:
        symbol = t.get("symbol", "")
        if symbol in PAIRS:
            change = float(t.get("riseFallRate", 0)) * 100
            price = float(t.get("lastPrice", 0))
            volume = float(t.get("volume24", 0))
            results.append({"symbol": symbol, "price": price, "change": round(change, 2), "volume": round(volume)})
    results.sort(key=lambda x: abs(x["change"]), reverse=True)
    return results

def format_scan(results):
    lines = [f"[TRADING SCAN] {datetime.now().strftime('%H:%M:%S')}"]
    alerts = []
    for r in results:
        arrow = "+" if r["change"] > 0 else ""
        line = f"  {r['symbol']}: ${r['price']} ({arrow}{r['change']}%) vol={r['volume']:,}"
        lines.append(line)
        if abs(r["change"]) >= ALERT_THRESHOLD:
            direction = "LONG" if r["change"] > 0 else "SHORT"
            tp = r["price"] * (1 + 0.004 if direction == "LONG" else 1 - 0.004)
            sl = r["price"] * (1 - 0.0025 if direction == "LONG" else 1 + 0.0025)
            alerts.append(f"{r['symbol']} {direction} | Entry: {r['price']} | TP: {round(tp,4)} | SL: {round(sl,4)} | {arrow}{r['change']}%")
    return "\n".join(lines), alerts

if __name__ == "__main__":
    if "--once" in sys.argv:
        results = scan_mexc()
        text, alerts = format_scan(results)
        print(text)
        if alerts:
            alert_msg = "[JARVIS SIGNAL]\n" + "\n".join(alerts)
            print(f"\n{alert_msg}")
            send_telegram(alert_msg)
        else:
            print("\nNo alerts (threshold: +/-2%)")
    elif "--loop" in sys.argv:
        interval = 600
        print(f"Scanning every {interval}s... Ctrl+C to stop")
        while True:
            results = scan_mexc()
            text, alerts = format_scan(results)
            print(text)
            if alerts:
                send_telegram("[JARVIS SIGNAL]\n" + "\n".join(alerts))
            time.sleep(interval)
    else:
        print("Usage: auto_trader.py --once | --loop")