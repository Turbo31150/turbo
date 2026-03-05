#!/usr/bin/env python3
"""JARVIS Risk Manager — Gestion du risque trading: position sizing, drawdown limits."""
import json, sys, os, sqlite3, urllib.request
from datetime import datetime

DB_PATH = "C:/Users/franc/.openclaw/workspace/dev/risk.db"
TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT = "2010747443"

MAX_DRAWDOWN_PCT = 5.0
MAX_POSITION_SIZE = 50
MAX_OPEN_POSITIONS = 5
MAX_DAILY_LOSS = 20
RISK_PER_TRADE_PCT = 1.0
DEFAULT_CAPITAL = 200

def send_telegram(msg):
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS risk_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, action TEXT, symbol TEXT,
        size REAL, risk_pct REAL, approved INTEGER, reason TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS daily_pnl (
        date TEXT PRIMARY KEY, pnl REAL DEFAULT 0, trades INTEGER DEFAULT 0, wins INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)""")
    c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('capital', ?)", (str(DEFAULT_CAPITAL),))
    conn.commit()
    return conn

def get_capital(conn):
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key='capital'")
    row = c.fetchone()
    return float(row[0]) if row else DEFAULT_CAPITAL

def get_daily_pnl(conn, date=None):
    date = date or datetime.now().strftime("%Y-%m-%d")
    c = conn.cursor()
    c.execute("SELECT pnl, trades, wins FROM daily_pnl WHERE date=?", (date,))
    row = c.fetchone()
    return {"pnl": row[0], "trades": row[1], "wins": row[2]} if row else {"pnl": 0, "trades": 0, "wins": 0}

def calculate_position_size(conn, entry_price, sl_price, leverage=10):
    capital = get_capital(conn)
    risk_amount = capital * (RISK_PER_TRADE_PCT / 100)
    sl_distance = abs(entry_price - sl_price) / entry_price
    if sl_distance == 0:
        return 0, "SL distance is zero"
    position_size = min(risk_amount / sl_distance, MAX_POSITION_SIZE)
    return round(position_size, 2), "OK"

def check_trade_approval(conn, symbol, size, direction="LONG"):
    capital = get_capital(conn)
    daily = get_daily_pnl(conn)
    reasons = []
    if daily["pnl"] <= -MAX_DAILY_LOSS:
        reasons.append(f"Daily loss limit: ${daily['pnl']}")
    drawdown_pct = abs(daily["pnl"]) / capital * 100 if daily["pnl"] < 0 else 0
    if drawdown_pct >= MAX_DRAWDOWN_PCT:
        reasons.append(f"Max drawdown: {round(drawdown_pct,1)}%")
    if size > MAX_POSITION_SIZE:
        reasons.append(f"Position too large: ${size} > ${MAX_POSITION_SIZE}")
    portfolio_db = "C:/Users/franc/.openclaw/workspace/dev/portfolio.db"
    if os.path.exists(portfolio_db):
        try:
            pconn = sqlite3.connect(portfolio_db)
            pc = pconn.cursor()
            pc.execute("SELECT COUNT(*) FROM positions WHERE status='open'")
            if pc.fetchone()[0] >= MAX_OPEN_POSITIONS:
                reasons.append(f"Max positions reached")
            pconn.close()
        except: pass
    approved = len(reasons) == 0
    c = conn.cursor()
    c.execute("INSERT INTO risk_log (ts, action, symbol, size, risk_pct, approved, reason) VALUES (?,?,?,?,?,?,?)",
              (datetime.now().isoformat(), direction, symbol, size, round(size/capital*100, 2), int(approved),
               "; ".join(reasons) if reasons else "Approved"))
    conn.commit()
    return approved, reasons

def record_trade_result(conn, pnl, won):
    today = datetime.now().strftime("%Y-%m-%d")
    c = conn.cursor()
    c.execute("""INSERT INTO daily_pnl (date, pnl, trades, wins) VALUES (?, ?, 1, ?)
                 ON CONFLICT(date) DO UPDATE SET pnl=pnl+?, trades=trades+1, wins=wins+?""",
              (today, pnl, int(won), pnl, int(won)))
    capital = get_capital(conn)
    c.execute("UPDATE config SET value=? WHERE key='capital'", (str(round(capital + pnl, 4)),))
    conn.commit()

def show_status(conn):
    capital = get_capital(conn)
    daily = get_daily_pnl(conn)
    drawdown = abs(daily["pnl"]) / capital * 100 if daily["pnl"] < 0 else 0
    can_trade = daily["pnl"] > -MAX_DAILY_LOSS and drawdown < MAX_DRAWDOWN_PCT
    print(f"[RISK MANAGER] Capital: ${capital}")
    print(f"  Daily P&L: ${daily['pnl']} ({daily['trades']} trades, {daily['wins']} wins)")
    print(f"  Drawdown: {round(drawdown, 1)}% (max: {MAX_DRAWDOWN_PCT}%)")
    print(f"  Risk/trade: {RISK_PER_TRADE_PCT}% = ${round(capital * RISK_PER_TRADE_PCT / 100, 2)}")
    print(f"  Trading: {'ALLOWED' if can_trade else 'BLOCKED'}")

if __name__ == "__main__":
    conn = init_db()
    if "--status" in sys.argv:
        show_status(conn)
    elif "--check" in sys.argv:
        idx = sys.argv.index("--check")
        symbol = sys.argv[idx+1] if len(sys.argv) > idx+1 else "BTC_USDT"
        size = float(sys.argv[idx+2]) if len(sys.argv) > idx+2 else 10
        approved, reasons = check_trade_approval(conn, symbol, size)
        print(f"Trade {symbol} ${size}: {'APPROVED' if approved else 'REJECTED'}")
        for r in reasons: print(f"  - {r}")
    elif "--size" in sys.argv:
        idx = sys.argv.index("--size")
        entry = float(sys.argv[idx+1]) if len(sys.argv) > idx+1 else 73000
        sl = float(sys.argv[idx+2]) if len(sys.argv) > idx+2 else 72800
        size, msg = calculate_position_size(conn, entry, sl)
        print(f"Position size: ${size} ({msg})")
    elif "--record" in sys.argv:
        idx = sys.argv.index("--record")
        pnl = float(sys.argv[idx+1]) if len(sys.argv) > idx+1 else 0
        record_trade_result(conn, pnl, pnl > 0)
        print(f"Recorded: ${pnl} ({'WIN' if pnl > 0 else 'LOSS'})")
    elif "--history" in sys.argv:
        c = conn.cursor()
        c.execute("SELECT ts, action, symbol, size, approved, reason FROM risk_log ORDER BY id DESC LIMIT 15")
        for r in c.fetchall():
            print(f"  {r[0][:16]} [{'OK' if r[4] else 'NO'}] {r[1]} {r[2]} ${r[3]} — {r[5][:60]}")
    else:
        print("Usage: risk_manager.py --status | --check SYMBOL SIZE | --size ENTRY SL | --record PNL | --history")
    conn.close()
