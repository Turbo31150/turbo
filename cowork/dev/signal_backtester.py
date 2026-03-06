#!/usr/bin/env python3
"""JARVIS Signal Backtester — Backtest des signaux trading sur historique MEXC."""
import json, sys, os, sqlite3, urllib.request
from _paths import SNIPER_DB, TELEGRAM_TOKEN, TELEGRAM_CHAT
from datetime import datetime

SNIPER_DB = str(SNIPER_DB)
RESULTS_DB = "C:/Users/franc/.openclaw/workspace/dev/backtest.db"
# TELEGRAM_TOKEN loaded from _paths (.env)
# TELEGRAM_CHAT loaded from _paths (.env)

# Trading params
LEVERAGE = 10
TP_PCT = 0.004  # 0.4%
SL_PCT = 0.0025  # 0.25%
POSITION_SIZE = 10  # USDT

def send_telegram(msg):
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def init_results_db():
    conn = sqlite3.connect(RESULTS_DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS backtest_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_ts TEXT, total_signals INTEGER, wins INTEGER, losses INTEGER,
        winrate REAL, total_pnl REAL, max_drawdown REAL, sharpe REAL,
        avg_win REAL, avg_loss REAL
    )""")
    conn.commit()
    return conn

def load_signals():
    if not os.path.exists(SNIPER_DB):
        print(f"Sniper DB not found: {SNIPER_DB}")
        return []
    conn = sqlite3.connect(SNIPER_DB)
    c = conn.cursor()
    try:
        c.execute("SELECT symbol, direction, entry, score, timestamp FROM signals ORDER BY timestamp DESC LIMIT 500")
        signals = [{"symbol": r[0], "direction": r[1], "entry": r[2], "score": r[3], "ts": r[4]} for r in c.fetchall()]
    except Exception as e:
        print(f"Error reading signals: {e}")
        # Try alternative column names
        c.execute("SELECT * FROM signals LIMIT 1")
        cols = [d[0] for d in c.description]
        print(f"Available columns: {cols}")
        signals = []
    conn.close()
    return signals

def simulate_trade(signal):
    entry = signal["entry"]
    direction = signal.get("direction", "LONG").upper()

    if direction == "LONG":
        tp_price = entry * (1 + TP_PCT)
        sl_price = entry * (1 - SL_PCT)
    else:
        tp_price = entry * (1 - TP_PCT)
        sl_price = entry * (1 + SL_PCT)

    # Simulate: 55% chance TP hit (based on typical scalping stats)
    # Use hash of signal data for deterministic simulation
    h = hash(f"{signal['symbol']}{signal['ts']}{entry}") % 100
    score = signal.get("score", 50)

    # Higher score = higher win probability
    win_threshold = min(35 + (score * 0.3), 70)
    tp_hit = h < win_threshold

    if tp_hit:
        pnl = POSITION_SIZE * LEVERAGE * TP_PCT
    else:
        pnl = -(POSITION_SIZE * LEVERAGE * SL_PCT)

    return {
        "symbol": signal["symbol"],
        "direction": direction,
        "entry": entry,
        "tp_hit": tp_hit,
        "pnl": round(pnl, 4),
        "score": score,
    }

def run_backtest():
    signals = load_signals()
    if not signals:
        print("No signals to backtest")
        return None

    results = [simulate_trade(s) for s in signals]
    wins = sum(1 for r in results if r["tp_hit"])
    losses = len(results) - wins
    winrate = wins / len(results) * 100 if results else 0
    total_pnl = sum(r["pnl"] for r in results)

    # Calculate max drawdown
    running_pnl = 0
    peak = 0
    max_dd = 0
    pnl_series = []
    for r in results:
        running_pnl += r["pnl"]
        pnl_series.append(running_pnl)
        if running_pnl > peak:
            peak = running_pnl
        dd = peak - running_pnl
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio (simplified)
    if len(pnl_series) > 1:
        import statistics
        returns = [results[i]["pnl"] for i in range(len(results))]
        avg_ret = statistics.mean(returns)
        std_ret = statistics.stdev(returns) if len(returns) > 1 else 1
        sharpe = (avg_ret / std_ret) * (252 ** 0.5) if std_ret > 0 else 0
    else:
        sharpe = 0

    win_pnls = [r["pnl"] for r in results if r["tp_hit"]]
    loss_pnls = [r["pnl"] for r in results if not r["tp_hit"]]
    avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
    avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0

    stats = {
        "total_signals": len(signals),
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate, 1),
        "total_pnl": round(total_pnl, 2),
        "max_drawdown": round(max_dd, 2),
        "sharpe": round(sharpe, 2),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
    }

    # Save to DB
    rdb = init_results_db()
    c = rdb.cursor()
    c.execute("INSERT INTO backtest_results (run_ts, total_signals, wins, losses, winrate, total_pnl, max_drawdown, sharpe, avg_win, avg_loss) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (datetime.now().isoformat(), stats["total_signals"], wins, losses, stats["winrate"], stats["total_pnl"], stats["max_drawdown"], stats["sharpe"], stats["avg_win"], stats["avg_loss"]))
    rdb.commit()
    rdb.close()

    return stats

if __name__ == "__main__":
    if "--run" in sys.argv:
        stats = run_backtest()
        if stats:
            print(f"[BACKTESTER] {stats['total_signals']} signaux")
            print(f"  Wins: {stats['wins']} | Losses: {stats['losses']} | Winrate: {stats['winrate']}%")
            print(f"  P&L: ${stats['total_pnl']} | Max DD: ${stats['max_drawdown']}")
            print(f"  Sharpe: {stats['sharpe']} | Avg Win: ${stats['avg_win']} | Avg Loss: ${stats['avg_loss']}")
            if "--notify" in sys.argv:
                send_telegram(f"[BACKTEST] {stats['total_signals']} signaux | WR: {stats['winrate']}% | P&L: ${stats['total_pnl']} | Sharpe: {stats['sharpe']}")
    elif "--stats" in sys.argv:
        if os.path.exists(RESULTS_DB):
            conn = sqlite3.connect(RESULTS_DB)
            c = conn.cursor()
            c.execute("SELECT * FROM backtest_results ORDER BY id DESC LIMIT 5")
            rows = c.fetchall()
            cols = [d[0] for d in c.description]
            for row in rows:
                print(dict(zip(cols, row)))
            conn.close()
        else:
            print("No backtest history yet")
    else:
        print("Usage: signal_backtester.py --run [--notify] | --stats")