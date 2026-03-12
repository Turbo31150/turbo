#!/usr/bin/env python3
"""JARVIS Portfolio Tracker — Suivi portefeuille MEXC temps reel."""
import json, sys, os, sqlite3, time, urllib.request
from datetime import datetime
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT

DB_PATH = "C:/Users/franc/.openclaw/workspace/dev/portfolio.db"
# TELEGRAM_TOKEN loaded from _paths (.env)
# TELEGRAM_CHAT loaded from _paths (.env)
PAIRS = ["BTC_USDT","ETH_USDT","SOL_USDT","SUI_USDT","PEPE_USDT","DOGE_USDT","XRP_USDT","ADA_USDT","AVAX_USDT","LINK_USDT"]
PNL_ALERT_PCT = 1.0

def send_telegram(msg):
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL, direction TEXT DEFAULT 'LONG',
        entry_price REAL NOT NULL, quantity REAL NOT NULL,
        leverage INTEGER DEFAULT 10, opened_at TEXT NOT NULL,
        closed_at TEXT, exit_price REAL, pnl REAL,
        status TEXT DEFAULT 'open'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL, total_value REAL, unrealized_pnl REAL,
        open_positions INTEGER, data TEXT
    )""")
    conn.commit()
    return conn

def fetch_prices():
    req = urllib.request.Request("https://contract.mexc.com/api/v1/contract/ticker")
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    prices = {}
    for t in data.get("data", []):
        if t.get("symbol") in PAIRS:
            prices[t["symbol"]] = float(t.get("lastPrice", 0))
    return prices

def add_position(conn, symbol, direction, entry_price, quantity, leverage=10):
    c = conn.cursor()
    c.execute("INSERT INTO positions (symbol, direction, entry_price, quantity, leverage, opened_at) VALUES (?,?,?,?,?,?)",
              (symbol, direction, entry_price, quantity, leverage, datetime.now().isoformat()))
    conn.commit()
    print(f"Position added: {direction} {symbol} @ {entry_price} x{quantity} (lev {leverage}x)")

def close_position(conn, pos_id, exit_price):
    c = conn.cursor()
    c.execute("SELECT symbol, direction, entry_price, quantity, leverage FROM positions WHERE id=? AND status='open'", (pos_id,))
    row = c.fetchone()
    if not row:
        print(f"Position #{pos_id} not found or already closed")
        return
    symbol, direction, entry, qty, lev = row
    if direction == "LONG":
        pnl = (exit_price - entry) / entry * qty * lev
    else:
        pnl = (entry - exit_price) / entry * qty * lev
    c.execute("UPDATE positions SET status='closed', closed_at=?, exit_price=?, pnl=? WHERE id=?",
              (datetime.now().isoformat(), exit_price, round(pnl, 4), pos_id))
    conn.commit()
    print(f"Closed #{pos_id} {symbol}: P&L = ${round(pnl, 4)}")

def portfolio_snapshot(conn):
    prices = fetch_prices()
    c = conn.cursor()
    c.execute("SELECT id, symbol, direction, entry_price, quantity, leverage FROM positions WHERE status='open'")
    positions = c.fetchall()

    total_pnl = 0
    lines = [f"[PORTFOLIO] {datetime.now().strftime('%H:%M:%S')} — {len(positions)} positions"]

    for pos_id, symbol, direction, entry, qty, lev in positions:
        current = prices.get(symbol, 0)
        if current == 0:
            continue
        if direction == "LONG":
            pnl = (current - entry) / entry * qty * lev
            pnl_pct = (current - entry) / entry * 100 * lev
        else:
            pnl = (entry - current) / entry * qty * lev
            pnl_pct = (entry - current) / entry * 100 * lev

        total_pnl += pnl
        arrow = "+" if pnl >= 0 else ""
        lines.append(f"  #{pos_id} {direction} {symbol}: ${current} ({arrow}{round(pnl_pct,2)}%) P&L: ${round(pnl,4)}")

    lines.append(f"\n  Total unrealized P&L: ${round(total_pnl, 4)}")

    # Save snapshot
    c.execute("INSERT INTO snapshots (ts, total_value, unrealized_pnl, open_positions, data) VALUES (?,?,?,?,?)",
              (datetime.now().isoformat(), total_pnl, total_pnl, len(positions), json.dumps({"prices": {k: v for k, v in prices.items()}})))
    conn.commit()

    return "\n".join(lines), total_pnl

def show_history(conn, limit=10):
    c = conn.cursor()
    c.execute("SELECT ts, unrealized_pnl, open_positions FROM snapshots ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    print(f"[PORTFOLIO HISTORY] Last {len(rows)} snapshots:")
    for ts, pnl, pos in rows:
        arrow = "+" if pnl >= 0 else ""
        print(f"  {ts[:16]}: {arrow}${round(pnl,4)} ({pos} positions)")

if __name__ == "__main__":
    conn = init_db()

    if "--once" in sys.argv:
        text, pnl = portfolio_snapshot(conn)
        print(text)
        if abs(pnl) > 0 and "--notify" in sys.argv:
            send_telegram(text)
    elif "--loop" in sys.argv:
        interval = 300  # 5min
        print(f"Tracking every {interval}s... Ctrl+C to stop")
        while True:
            text, pnl = portfolio_snapshot(conn)
            print(text)
            if abs(pnl) >= PNL_ALERT_PCT:
                send_telegram(text)
            time.sleep(interval)
    elif "--add" in sys.argv:
        idx = sys.argv.index("--add")
        if len(sys.argv) > idx + 3:
            symbol = sys.argv[idx+1].upper()
            direction = sys.argv[idx+2].upper()
            entry = float(sys.argv[idx+3])
            qty = float(sys.argv[idx+4]) if len(sys.argv) > idx+4 else 10.0
            add_position(conn, symbol, direction, entry, qty)
        else:
            print("Usage: --add SYMBOL LONG|SHORT entry_price [quantity]")
    elif "--close" in sys.argv:
        idx = sys.argv.index("--close")
        pos_id = int(sys.argv[idx+1])
        exit_price = float(sys.argv[idx+2])
        close_position(conn, pos_id, exit_price)
    elif "--history" in sys.argv:
        show_history(conn)
    elif "--positions" in sys.argv:
        c = conn.cursor()
        c.execute("SELECT id, symbol, direction, entry_price, quantity, leverage, opened_at FROM positions WHERE status='open'")
        rows = c.fetchall()
        print(f"[OPEN POSITIONS] {len(rows)}")
        for r in rows:
            print(f"  #{r[0]} {r[2]} {r[1]} @ {r[3]} x{r[4]} lev={r[5]} ({r[6][:16]})")
    else:
        print("Usage: portfolio_tracker.py --once | --loop | --history | --positions")
        print("       --add SYMBOL DIRECTION ENTRY [QTY] | --close ID EXIT_PRICE")

    conn.close()