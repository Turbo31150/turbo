"""
JARVIS Sniper Scanner — Breakout Imminent Detection + Full Cluster Consensus
Scans ALL MEXC Futures, detects pre-breakout setups, provides Entry/TP1/TP2/TP3/SL.

Usage:
  python cowork/dev/sniper_scanner.py --once          # Single scan
  python cowork/dev/sniper_scanner.py --loop           # Continuous (5min interval)
  python cowork/dev/sniper_scanner.py --top 50         # Scan top 50 by volume
  python cowork/dev/sniper_scanner.py --notify         # Send results to Telegram
  python cowork/dev/sniper_scanner.py --chat-id 12345  # Send to specific chat
"""

import json
import math
import os
import sys
import time
import sqlite3
import argparse
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── Config ──────────────────────────────────────────────────────────────────

MEXC_FUTURES = "https://contract.mexc.com"
MEXC_SPOT = "https://api.mexc.com"
TURBO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = TURBO_ROOT / "data" / "sniper_scan.db"
SCAN_INTERVAL = 300  # 5 min
MAX_KLINE_BARS = 200  # 200 candles x 15min = 50h lookback
TOP_N = 100  # Top coins by volume to deep-scan (0 = ALL)

# Cluster nodes for AI consensus
CLUSTER_NODES = [
    {"id": "gpt-oss", "url": "http://127.0.0.1:11434/api/chat", "model": "gpt-oss:120b-cloud", "type": "ollama", "weight": 1.9},
    {"id": "M1", "url": "http://127.0.0.1:1234/v1/chat/completions", "model": "qwen3-8b", "type": "lmstudio", "weight": 1.8},
    {"id": "devstral", "url": "http://127.0.0.1:11434/api/chat", "model": "devstral-2:123b-cloud", "type": "ollama", "weight": 1.5},
    {"id": "M2", "url": "http://192.168.1.26:1234/v1/chat/completions", "model": "deepseek-coder-v2-lite-instruct", "type": "lmstudio", "weight": 1.4},
    {"id": "OL1", "url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b", "type": "ollama", "weight": 1.3},
]

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT", "2010747443")

# ─── HTTP helper (no deps) ──────────────────────────────────────────────────

import urllib.request
import urllib.error

def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def http_post(url, data, timeout=60, headers=None):
    body = json.dumps(data).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ─── Database ────────────────────────────────────────────────────────────────

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.executescript("""
        CREATE TABLE IF NOT EXISTS scan_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            symbol TEXT, direction TEXT, score REAL,
            entry REAL, tp1 REAL, tp2 REAL, tp3 REAL, sl REAL,
            atr REAL, rsi REAL, volume_ratio REAL, bb_squeeze REAL,
            pattern TEXT, consensus TEXT, cluster_nodes TEXT,
            gpu_confidence REAL, gpu_strategies TEXT, gpu_regime TEXT
        );
        CREATE TABLE IF NOT EXISTS scan_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            coins_scanned INTEGER, signals_found INTEGER,
            breakouts INTEGER, duration_s REAL,
            phase1_ms REAL, phase2_ms REAL, phase3_ms REAL
        );
        CREATE TABLE IF NOT EXISTS coin_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            scan_id INTEGER,
            symbol TEXT,
            price REAL,
            volume_24h REAL,
            change_24h REAL,
            rsi REAL,
            atr REAL,
            bb_squeeze REAL,
            volume_ratio REAL,
            sentiment TEXT,
            score REAL DEFAULT 0,
            direction TEXT,
            patterns TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_symbol ON coin_snapshots(symbol);
        CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON coin_snapshots(ts);
        CREATE INDEX IF NOT EXISTS idx_snapshots_scan ON coin_snapshots(scan_id);

        -- Suivi des resultats des signaux emis
        CREATE TABLE IF NOT EXISTS signal_tracker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            tp1 REAL, tp2 REAL, tp3 REAL, sl REAL,
            score REAL,
            validations INTEGER DEFAULT 0,
            emitted_at TEXT,
            checked_at TEXT,
            current_price REAL,
            tp1_hit INTEGER DEFAULT 0,
            tp2_hit INTEGER DEFAULT 0,
            tp3_hit INTEGER DEFAULT 0,
            sl_hit INTEGER DEFAULT 0,
            pnl_pct REAL DEFAULT 0,
            status TEXT DEFAULT 'OPEN'
        );
        CREATE INDEX IF NOT EXISTS idx_tracker_symbol ON signal_tracker(symbol);
        CREATE INDEX IF NOT EXISTS idx_tracker_status ON signal_tracker(status);

        -- Registre de tous les coins connus (nom propre, derniere MAJ)
        CREATE TABLE IF NOT EXISTS coin_registry (
            symbol TEXT PRIMARY KEY,
            clean_name TEXT,
            first_seen TEXT,
            last_seen TEXT,
            last_price REAL, last_volume REAL, last_change REAL,
            scan_count INTEGER DEFAULT 1,
            avg_score REAL DEFAULT 0,
            best_score REAL DEFAULT 0,
            best_direction TEXT
        );
    """)
    c.close()


def update_coin_registry(db, tickers):
    """Met a jour le registre de tous les coins — noms, prix, validation."""
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym or not sym.endswith("_USDT"):
            continue
        price = float(t.get("lastPrice", 0))
        vol = float(t.get("volume24", t.get("amount24", 0)))
        change = float(t.get("riseFallRate", 0)) * 100
        clean = sym.replace("_USDT", "")

        # Validation: skip coins with bad data
        if price <= 0 or not clean:
            continue

        now = datetime.now().isoformat(timespec='seconds')
        existing = db.execute("SELECT scan_count FROM coin_registry WHERE symbol=?", (sym,)).fetchone()
        if existing:
            db.execute(
                "UPDATE coin_registry SET last_seen=?, last_price=?, last_volume=?, last_change=?, scan_count=scan_count+1, clean_name=? WHERE symbol=?",
                (now, price, vol, change, clean, sym)
            )
        else:
            db.execute(
                "INSERT INTO coin_registry (symbol, clean_name, first_seen, last_seen, last_price, last_volume, last_change) VALUES (?,?,?,?,?,?,?)",
                (sym, clean, now, now, price, vol, change)
            )


def update_registry_scores(db, symbol, score, direction):
    """Met a jour les scores dans le registre."""
    db.execute(
        "UPDATE coin_registry SET avg_score = (avg_score * (scan_count - 1) + ?) / scan_count, "
        "best_score = MAX(best_score, ?), best_direction = CASE WHEN ? > best_score THEN ? ELSE best_direction END "
        "WHERE symbol=?",
        (score, score, score, direction, symbol)
    )


def get_hot_coins_from_db(db, min_scans=2, min_avg_score=30, limit=50):
    """Recupere les coins chauds depuis le registre (historique)."""
    rows = db.execute(
        "SELECT symbol, avg_score, best_score, last_price, last_change "
        "FROM coin_registry WHERE scan_count >= ? AND avg_score >= ? "
        "ORDER BY avg_score DESC LIMIT ?",
        (min_scans, min_avg_score, limit)
    ).fetchall()
    return [{"symbol": r[0], "avg_score": r[1], "best_score": r[2], "price": r[3], "change": r[4]} for r in rows]


def get_previous_snapshot(db, symbol):
    """Retrouve le dernier snapshot d'un coin pour comparaison."""
    row = db.execute(
        "SELECT ts, price, rsi, sentiment, score, direction "
        "FROM coin_snapshots WHERE symbol=? ORDER BY id DESC LIMIT 1",
        (symbol,)
    ).fetchone()
    if row:
        return {"ts": row[0], "price": row[1], "rsi": row[2],
                "sentiment": row[3], "score": row[4], "direction": row[5]}
    return None


def save_coin_snapshots(db, scan_id, results, tickers_map):
    """Sauvegarde le snapshot de chaque coin analyse."""
    for r in results:
        sym = r["symbol"]
        ticker = tickers_map.get(sym, {})
        vol_24h = float(ticker.get("amount24", ticker.get("volume24", 0)))
        change_24h = float(ticker.get("riseFallRate", 0)) * 100

        # Determine sentiment from score + direction
        if r["score"] >= 70:
            sentiment = "fort_" + r["direction"].lower()
        elif r["score"] >= 50:
            sentiment = "modere_" + r["direction"].lower()
        elif r["score"] >= 30:
            sentiment = "faible"
        else:
            sentiment = "neutre"

        db.execute(
            "INSERT INTO coin_snapshots (scan_id, symbol, price, volume_24h, change_24h, "
            "rsi, atr, bb_squeeze, volume_ratio, sentiment, score, direction, patterns) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (scan_id, sym, r.get("price", 0), vol_24h, change_24h,
             r.get("rsi", 50), r.get("atr", 0), r.get("bb_squeeze", 0),
             r.get("volume_ratio", 1), sentiment, r["score"], r["direction"],
             ",".join(r.get("patterns", [])))
        )

# ─── MEXC Data Fetching ─────────────────────────────────────────────────────

def fetch_all_tickers():
    """Fetch ALL futures tickers in one call."""
    data = http_get(f"{MEXC_FUTURES}/api/v1/contract/ticker")
    tickers = data.get("data", [])
    # Filter active USDT pairs
    return [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

def fetch_klines(symbol, interval="Min15", limit=MAX_KLINE_BARS):
    """Fetch candlestick data for a symbol."""
    url = f"{MEXC_FUTURES}/api/v1/contract/kline/{symbol}?interval={interval}&limit={limit}"
    data = http_get(url, timeout=10)
    kd = data.get("data", {})
    if not kd or not kd.get("close"):
        return None
    n = len(kd["close"])
    candles = []
    for i in range(n):
        candles.append({
            "o": float(kd["open"][i]),
            "h": float(kd["high"][i]),
            "l": float(kd["low"][i]),
            "c": float(kd["close"][i]),
            "v": float(kd["vol"][i]),
        })
    return candles

def fetch_depth(symbol, limit=20):
    """Fetch order book depth."""
    url = f"{MEXC_FUTURES}/api/v1/contract/depth/{symbol}?limit={limit}"
    data = http_get(url, timeout=8)
    d = data.get("data", {})
    bids = d.get("bids", [])
    asks = d.get("asks", [])
    bid_vol = sum(float(b[1]) for b in bids) if bids else 0
    ask_vol = sum(float(a[1]) for a in asks) if asks else 0
    total = bid_vol + ask_vol
    imbalance = (bid_vol - ask_vol) / total if total > 0 else 0
    return {"bid_vol": bid_vol, "ask_vol": ask_vol, "imbalance": imbalance}

# ─── Technical Indicators ────────────────────────────────────────────────────

def ema(values, period):
    if len(values) < period:
        return values[:]
    result = [0.0] * len(values)
    k = 2.0 / (period + 1)
    result[period - 1] = sum(values[:period]) / period
    for i in range(period, len(values)):
        result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result

def sma(values, period):
    result = [0.0] * len(values)
    for i in range(period - 1, len(values)):
        result[i] = sum(values[i - period + 1:i + 1]) / period
    return result

def rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def atr(candles, period=14):
    if len(candles) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        tr = max(
            candles[i]["h"] - candles[i]["l"],
            abs(candles[i]["h"] - candles[i - 1]["c"]),
            abs(candles[i]["l"] - candles[i - 1]["c"])
        )
        trs.append(tr)
    if not trs:
        return 0.0
    atr_val = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr_val = (atr_val * (period - 1) + trs[i]) / period
    return atr_val

def bollinger_bands(closes, period=20, std_mult=2.0):
    if len(closes) < period:
        return None
    mid = sma(closes, period)
    last_mid = mid[-1]
    window = closes[-period:]
    std = (sum((x - last_mid) ** 2 for x in window) / period) ** 0.5
    upper = last_mid + std_mult * std
    lower = last_mid - std_mult * std
    bandwidth = (upper - lower) / last_mid if last_mid > 0 else 0
    return {"mid": last_mid, "upper": upper, "lower": lower, "bandwidth": bandwidth, "std": std}

def volume_profile(candles, lookback=20):
    """Detect volume spikes vs average."""
    if len(candles) < lookback + 5:
        return 1.0
    recent_vol = sum(c["v"] for c in candles[-5:]) / 5
    avg_vol = sum(c["v"] for c in candles[-lookback - 5:-5]) / lookback
    return recent_vol / avg_vol if avg_vol > 0 else 1.0

def detect_consolidation(candles, lookback=20):
    """Detect tight range (pre-breakout squeeze)."""
    if len(candles) < lookback:
        return 0.0
    recent = candles[-lookback:]
    highs = [c["h"] for c in recent]
    lows = [c["l"] for c in recent]
    range_pct = (max(highs) - min(lows)) / ((max(highs) + min(lows)) / 2) if (max(highs) + min(lows)) > 0 else 0
    # Tight range = low range_pct = high squeeze score
    squeeze = max(0, 1 - range_pct * 10)  # 0-1, higher = tighter
    return squeeze

def compute_adx(candles, period=14):
    """Calculate ADX (Average Directional Index) — trend strength 0-100."""
    if len(candles) < period * 2 + 1:
        return 25.0  # Default neutral
    plus_dm = []
    minus_dm = []
    tr_list = []
    for i in range(1, len(candles)):
        high_diff = candles[i]["h"] - candles[i-1]["h"]
        low_diff = candles[i-1]["l"] - candles[i]["l"]
        plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0)
        minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0)
        tr = max(
            candles[i]["h"] - candles[i]["l"],
            abs(candles[i]["h"] - candles[i-1]["c"]),
            abs(candles[i]["l"] - candles[i-1]["c"])
        )
        tr_list.append(tr)
    # Smooth with EMA
    def smooth(values, p):
        s = sum(values[:p])
        result = [s]
        for v in values[p:]:
            s = s - s/p + v
            result.append(s)
        return result
    str_list = smooth(tr_list, period)
    sp_dm = smooth(plus_dm, period)
    sm_dm = smooth(minus_dm, period)
    dx_list = []
    for i in range(len(str_list)):
        if str_list[i] == 0:
            continue
        plus_di = 100 * sp_dm[i] / str_list[i]
        minus_di = 100 * sm_dm[i] / str_list[i]
        di_sum = plus_di + minus_di
        if di_sum > 0:
            dx_list.append(100 * abs(plus_di - minus_di) / di_sum)
    if len(dx_list) < period:
        return 25.0
    adx = sum(dx_list[-period:]) / period
    return min(adx, 100)


def compute_vwap(candles):
    """Calculate VWAP (Volume Weighted Average Price) — institutional reference."""
    cum_vol = 0
    cum_pv = 0
    for c in candles:
        typical = (c["h"] + c["l"] + c["c"]) / 3
        cum_pv += typical * c["v"]
        cum_vol += c["v"]
    return cum_pv / cum_vol if cum_vol > 0 else candles[-1]["c"]


def detect_ema_alignment(candles):
    """Check EMA stack alignment (trend strength)."""
    closes = [c["c"] for c in candles]
    ema8 = ema(closes, 8)
    ema21 = ema(closes, 21)
    ema55 = ema(closes, 55)
    if len(closes) < 55:
        return 0, "neutral"
    e8, e21, e55 = ema8[-1], ema21[-1], ema55[-1]
    if e8 > e21 > e55:
        return 1, "bullish_stack"
    elif e8 < e21 < e55:
        return -1, "bearish_stack"
    return 0, "mixed"

# ─── Breakout Pattern Detection ──────────────────────────────────────────────

def analyze_coin(symbol, candles, ticker, depth_info):
    """Full analysis of a single coin — returns signal dict or None."""
    if not candles or len(candles) < 60:
        return None

    closes = [c["c"] for c in candles]
    price = closes[-1]
    if price <= 0:
        return None

    # --- Indicators ---
    cur_rsi = rsi(closes)
    cur_atr = atr(candles)
    bb = bollinger_bands(closes)
    vol_ratio = volume_profile(candles)
    squeeze = detect_consolidation(candles)
    ema_dir, ema_pattern = detect_ema_alignment(candles)
    cur_adx = compute_adx(candles)
    cur_vwap = compute_vwap(candles)
    imbalance = depth_info.get("imbalance", 0) if depth_info else 0

    # --- Scoring (0-100) ---
    score = 0
    patterns = []

    # 1. Bollinger Squeeze (pre-breakout)
    if bb and bb["bandwidth"] < 0.03:
        score += 20
        patterns.append("BB_SQUEEZE")
    elif bb and bb["bandwidth"] < 0.05:
        score += 10
        patterns.append("bb_tightening")

    # 2. Volume spike (accumulation)
    if vol_ratio > 3.0:
        score += 20
        patterns.append("VOL_SPIKE_3x")
    elif vol_ratio > 2.0:
        score += 15
        patterns.append("VOL_SPIKE_2x")
    elif vol_ratio > 1.5:
        score += 8
        patterns.append("vol_above_avg")

    # 3. RSI momentum
    if 55 <= cur_rsi <= 70:
        score += 10
        patterns.append("rsi_momentum")
    elif 30 <= cur_rsi <= 45:
        score += 10
        patterns.append("rsi_oversold_bounce")
    elif cur_rsi > 75:
        score += 5
        patterns.append("rsi_overbought")
    elif cur_rsi < 25:
        score += 5
        patterns.append("rsi_extreme_oversold")

    # 4. EMA alignment
    if ema_dir != 0:
        score += 12
        patterns.append(ema_pattern)

    # 4b. ADX trend strength
    if cur_adx > 30:
        score += 10
        patterns.append("STRONG_TREND")
    elif cur_adx > 20:
        score += 5
        patterns.append("trend_ok")
    # ADX < 15 = pas de tendance = penalite
    elif cur_adx < 15:
        score -= 5

    # 5. Consolidation squeeze
    if squeeze > 0.7:
        score += 18
        patterns.append("TIGHT_RANGE")
    elif squeeze > 0.4:
        score += 8
        patterns.append("range_compress")

    # 6. Order book imbalance
    if abs(imbalance) > 0.3:
        score += 10
        patterns.append(f"OB_{'BUY' if imbalance > 0 else 'SELL'}_pressure")
    elif abs(imbalance) > 0.15:
        score += 5
        patterns.append(f"ob_{'bid' if imbalance > 0 else 'ask'}_lean")

    # 7. Price near Bollinger Band (breakout proximity)
    if bb:
        dist_upper = (bb["upper"] - price) / price
        dist_lower = (price - bb["lower"]) / price
        if dist_upper < 0.005:
            score += 12
            patterns.append("NEAR_BB_UPPER")
        elif dist_lower < 0.005:
            score += 12
            patterns.append("NEAR_BB_LOWER")

    # 7b. VWAP position — price above VWAP = bullish, below = bearish
    if cur_vwap > 0:
        vwap_dist = (price - cur_vwap) / cur_vwap
        if vwap_dist > 0.005:  # Above VWAP
            score += 8
            patterns.append("ABOVE_VWAP")
        elif vwap_dist < -0.005:  # Below VWAP
            score += 8
            patterns.append("BELOW_VWAP")

    # 8. 24h momentum from ticker
    change_24h = float(ticker.get("riseFallRate", 0)) * 100
    if 2 < abs(change_24h) < 8:
        score += 5
        patterns.append(f"momentum_{change_24h:+.1f}%")

    # 9. Momentum acceleration (3 dernieres bougies accelerent)
    if len(candles) >= 5:
        last3 = [c["c"] - c["o"] for c in candles[-3:]]  # body size signe
        prev2 = [c["c"] - c["o"] for c in candles[-5:-3]]
        avg_last = sum(abs(b) for b in last3) / 3
        avg_prev = sum(abs(b) for b in prev2) / 2 if prev2 else 0
        same_dir = all(b > 0 for b in last3) or all(b < 0 for b in last3)
        if same_dir and avg_prev > 0 and avg_last > avg_prev * 2:
            score += 15
            patterns.append("MOMENTUM_ACCEL")
        elif same_dir and avg_last > cur_atr * 0.5:
            score += 8
            patterns.append("momentum_push")

    # 9b. Momentum streak — count consecutive same-direction candles from end
    if len(candles) >= 6:
        streak = 0
        streak_dir = 1 if candles[-1]["c"] > candles[-1]["o"] else -1
        for c in reversed(candles[-10:]):
            body_dir = 1 if c["c"] > c["o"] else -1
            if body_dir == streak_dir:
                streak += 1
            else:
                break
        if streak >= 5:
            score += 12
            patterns.append(f"STREAK_{streak}")
        elif streak >= 3:
            score += 6
            patterns.append(f"streak_{streak}")

    # 10. Volume climax (derniere bougie = pic de volume absolu)
    if len(candles) >= 20:
        last_vol = candles[-1]["v"]
        max_vol_20 = max(c["v"] for c in candles[-20:])
        if last_vol >= max_vol_20 * 0.9 and last_vol > 0:
            score += 12
            patterns.append("VOLUME_CLIMAX")

    # 11. Grosse bougie directionnelle (corps > 1.5x ATR = force)
    if len(candles) >= 2 and cur_atr > 0:
        last_body = abs(candles[-1]["c"] - candles[-1]["o"])
        if last_body > cur_atr * 1.5:
            score += 10
            patterns.append("BIG_CANDLE")
        # Wick rejection (meche longue = rejet de niveau)
        last_wick_up = candles[-1]["h"] - max(candles[-1]["c"], candles[-1]["o"])
        last_wick_dn = min(candles[-1]["c"], candles[-1]["o"]) - candles[-1]["l"]
        if last_wick_dn > last_body * 2 and last_wick_dn > cur_atr * 0.5:
            score += 8
            patterns.append("HAMMER_REJECT")
        elif last_wick_up > last_body * 2 and last_wick_up > cur_atr * 0.5:
            score += 8
            patterns.append("SHOOTING_STAR")

    # --- Direction ---
    bull_signals = sum(1 for p in patterns if p in [
        "rsi_momentum", "bullish_stack", "NEAR_BB_UPPER",
        "rsi_oversold_bounce", "rsi_extreme_oversold", "ABOVE_VWAP"
    ]) + (1 if imbalance > 0.15 else 0)
    bear_signals = sum(1 for p in patterns if p in [
        "rsi_overbought", "bearish_stack", "NEAR_BB_LOWER", "BELOW_VWAP"
    ]) + (1 if imbalance < -0.15 else 0)

    if bull_signals > bear_signals:
        direction = "LONG"
    elif bear_signals > bull_signals:
        direction = "SHORT"
    elif ema_dir > 0:
        direction = "LONG"
    elif ema_dir < 0:
        direction = "SHORT"
    elif change_24h > 0:
        direction = "LONG"
    else:
        direction = "SHORT"

    # --- TP/SL based on ATR + score-adjusted R:R ---
    atr_val = cur_atr if cur_atr > 0 else price * 0.005
    # Score > 80: TPs plus agressifs (confiance haute)
    # Score < 60: TPs conservateurs
    confidence = min(score, 100) / 100
    sl_mult = 1.2 + (1 - confidence) * 0.6  # 1.2 (high) to 1.8 (low)
    tp1_mult = 0.8 + confidence * 0.5   # 0.8 to 1.3
    tp2_mult = 1.5 + confidence * 1.0   # 1.5 to 2.5
    tp3_mult = 2.5 + confidence * 2.0   # 2.5 to 4.5

    if direction == "LONG":
        entry = price
        sl = price - atr_val * sl_mult
        tp1 = price + atr_val * tp1_mult
        tp2 = price + atr_val * tp2_mult
        tp3 = price + atr_val * tp3_mult
    else:
        entry = price
        sl = price + atr_val * sl_mult
        tp1 = price - atr_val * tp1_mult
        tp2 = price - atr_val * tp2_mult
        tp3 = price - atr_val * tp3_mult

    return {
        "symbol": symbol,
        "direction": direction,
        "score": min(score, 100),
        "price": price,
        "entry": entry,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "sl": sl,
        "atr": atr_val,
        "rsi": cur_rsi,
        "volume_ratio": vol_ratio,
        "bb_squeeze": squeeze,
        "bb_bandwidth": bb["bandwidth"] if bb else 0,
        "imbalance": imbalance,
        "change_24h": change_24h,
        "adx": cur_adx,
        "vwap": cur_vwap,
        "patterns": patterns,
        "ema_pattern": ema_pattern,
    }

# ─── Cluster AI Consensus ────────────────────────────────────────────────────

def query_cluster_node(node, prompt):
    """Query a single cluster node."""
    try:
        if node["type"] == "ollama":
            resp = http_post(node["url"], {
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False
            }, timeout=30)
            text = resp.get("message", {}).get("content", "")
        else:
            resp = http_post(node["url"], {
                "model": node["model"],
                "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}],
                "temperature": 0.2, "max_tokens": 512, "stream": False
            }, timeout=30)
            choices = resp.get("choices", [])
            text = choices[0]["message"]["content"] if choices else ""
        # Clean thinking tokens
        import re
        text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
        return {"node": node["id"], "text": text, "weight": node["weight"]}
    except Exception as e:
        return {"node": node["id"], "text": "", "error": str(e), "weight": node["weight"]}

def cluster_consensus(signal):
    """Get AI consensus from all cluster nodes on a signal."""
    sym = signal["symbol"].replace("_USDT", "")
    prompt = (
        f"Signal trading {sym}/USDT: prix={signal['price']:.6g}, "
        f"direction={signal['direction']}, RSI={signal['rsi']:.1f}, "
        f"volume_ratio={signal['volume_ratio']:.1f}x, "
        f"BB_squeeze={signal['bb_squeeze']:.2f}, "
        f"patterns={','.join(signal['patterns'][:5])}, "
        f"change_24h={signal['change_24h']:+.1f}%, "
        f"orderbook_imbalance={signal['imbalance']:+.2f}.\n"
        f"Entry={signal['entry']:.6g}, TP1={signal['tp1']:.6g}, TP2={signal['tp2']:.6g}, TP3={signal['tp3']:.6g}, SL={signal['sl']:.6g}.\n"
        f"Reponds UNIQUEMENT: AGREE ou DISAGREE suivi de ta raison en 1 ligne. "
        f"AGREE si le setup est bon, DISAGREE si trop risque."
    )
    results = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(query_cluster_node, node, prompt): node for node in CLUSTER_NODES}
        for f in as_completed(futs, timeout=35):
            try:
                results.append(f.result())
            except Exception:
                pass

    agree_weight = 0
    disagree_weight = 0
    nodes_used = []
    reasons = []
    for r in results:
        if not r.get("text"):
            continue
        nodes_used.append(r["node"])
        t = r["text"].upper()
        if "AGREE" in t and "DISAGREE" not in t:
            agree_weight += r["weight"]
            reasons.append(f"[{r['node']}] AGREE")
        elif "DISAGREE" in t:
            disagree_weight += r["weight"]
            reasons.append(f"[{r['node']}] DISAGREE")
        else:
            reasons.append(f"[{r['node']}] UNCLEAR")

    total = agree_weight + disagree_weight
    consensus_pct = agree_weight / total if total > 0 else 0
    return {
        "consensus": "AGREE" if consensus_pct >= 0.6 else "DISAGREE",
        "consensus_pct": consensus_pct,
        "nodes_used": nodes_used,
        "reasons": reasons,
    }

# ─── Main Scanner ────────────────────────────────────────────────────────────

def compute_history_bonus(prev, current):
    """Calcule un bonus de score a partir de l'historique du coin."""
    if not prev:
        return 0, []
    bonus = 0
    h_patterns = []

    # 1. Score monte: le coin gagne en force
    if prev.get("score", 0) >= 40 and current.get("score", 0) > prev["score"]:
        bonus += 10
        h_patterns.append("SCORE_MONTE")

    # 2. Direction confirmee: meme direction = conviction
    if prev.get("direction") and prev["direction"] == current.get("direction"):
        bonus += 5
        h_patterns.append("DIRECTION_CONFIRMEE")

    # 3. Retournement: changement de direction avec force
    if prev.get("direction") and prev["direction"] != current.get("direction", ""):
        if current.get("score", 0) >= 50:
            bonus += 8
            h_patterns.append("RETOURNEMENT")

    # 4. Prix en mouvement depuis dernier scan
    if prev.get("price", 0) > 0 and current.get("price", 0) > 0:
        price_change = (current["price"] - prev["price"]) / prev["price"] * 100
        if abs(price_change) > 2:
            bonus += 5
            h_patterns.append(f"MOUVEMENT_{price_change:+.1f}%")
        # MOUVEMENT RAPIDE: >1% en 60s = explosion en cours
        if abs(price_change) > 1:
            bonus += 12
            h_patterns.append("EXPLOSION_EN_COURS")
        elif abs(price_change) > 0.5:
            bonus += 5
            h_patterns.append("MOUVEMENT_RAPIDE")

    # 5. Volume en acceleration
    if prev.get("volume_ratio", 1) > 0 and current.get("volume_ratio", 1) > prev.get("volume_ratio", 1) * 1.5:
        bonus += 8
        h_patterns.append("VOL_ACCELERATION")

    return min(bonus, 30), h_patterns  # Cap a 30 points


def try_gpu_pipeline(symbols, max_coins=30):
    """Tente d'utiliser le GPU pipeline (strategies.py) si disponible."""
    try:
        sys.path.insert(0, str(TURBO_ROOT / "scripts" / "trading_v2"))
        from data_fetcher import fetch_batch_klines, build_tensor_3d
        from strategies import compute_final_scores
        log(f"  GPU Pipeline: fetching klines for {len(symbols)} coins...")
        klines = fetch_batch_klines(symbols[:max_coins], limit=200, max_workers=8)
        if not klines:
            return {}
        tensor, sym_list = build_tensor_3d(klines, time_window=200)
        log(f"  GPU Pipeline: computing 100 strategies on tensor {list(tensor.shape)}...")
        results = compute_final_scores(tensor)
        gpu_data = {}
        for i, sym in enumerate(sym_list):
            gpu_data[sym] = {
                "confidence": float(results["confidences"][i]),
                "direction": int(results["directions"][i]),
                "regime": str(results["market_regimes"][i]) if i < len(results.get("market_regimes", [])) else "unknown",
                "strategies": results.get("triggered_strategies", {}).get(i, []),
                "atr": float(results["atr"][i]) if "atr" in results else 0,
            }
        log(f"  GPU Pipeline: {len(gpu_data)} coins traites")
        return gpu_data
    except Exception as e:
        log(f"  GPU Pipeline indisponible: {e}")
        return {}


def scan(top_n=TOP_N, with_consensus=True):
    """Pipeline complet en 3 phases — scan ALL, deep analyse, consensus cluster."""
    t_start = time.time()
    db = sqlite3.connect(str(DB_PATH))

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 1 — Scan rapide ALL tickers → registre SQL
    # ═══════════════════════════════════════════════════════════════════════════
    t1 = time.time()
    log(f"PHASE 1: Scan ALL tickers MEXC Futures...")
    tickers = fetch_all_tickers()
    log(f"  {len(tickers)} paires trouvees")

    # Validation + nettoyage
    valid_tickers = []
    for t in tickers:
        sym = t.get("symbol", "")
        price = float(t.get("lastPrice", 0))
        if not sym.endswith("_USDT") or price <= 0:
            continue
        valid_tickers.append(t)
    log(f"  {len(valid_tickers)} paires valides (prix > 0)")

    # Enregistrer TOUS les coins dans le registre SQL
    update_coin_registry(db, valid_tickers)
    db.commit()

    # Pre-filtrage par volume pour le deep scan
    valid_tickers.sort(key=lambda t: float(t.get("volume24", t.get("amount24", 0))), reverse=True)
    scan_tickers = valid_tickers if top_n <= 0 else valid_tickers[:top_n]
    tickers_map = {t["symbol"]: t for t in scan_tickers}

    # Ajouter les coins chauds de la DB (historiquement performants) pas deja dans la liste
    hot_coins = get_hot_coins_from_db(db, min_scans=2, min_avg_score=35, limit=30)
    scan_symbols = {t["symbol"] for t in scan_tickers}
    added_hot = 0
    for hc in hot_coins:
        if hc["symbol"] not in scan_symbols:
            # Retrouver le ticker original
            for t in valid_tickers:
                if t["symbol"] == hc["symbol"]:
                    scan_tickers.append(t)
                    tickers_map[t["symbol"]] = t
                    added_hot += 1
                    break
    if added_hot:
        log(f"  +{added_hot} coins chauds ajoutes depuis historique DB")

    phase1_ms = (time.time() - t1) * 1000
    log(f"  Phase 1: {len(valid_tickers)} enregistres, {len(scan_tickers)} a analyser ({phase1_ms:.0f}ms)")

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 2 — Deep scan: klines + indicateurs + order book
    # ═══════════════════════════════════════════════════════════════════════════
    t2 = time.time()
    log(f"PHASE 2: Deep scan {len(scan_tickers)} coins (klines + indicateurs)...")

    all_results = []
    def process_ticker(t):
        sym = t["symbol"]
        try:
            candles = fetch_klines(sym)
            depth = None
            try:
                depth = fetch_depth(sym)
            except Exception:
                pass
            if candles:
                return analyze_coin(sym, candles, t, depth)
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = {pool.submit(process_ticker, t): t for t in scan_tickers}
        for f in as_completed(futs, timeout=300):
            try:
                result = f.result()
                if result:
                    all_results.append(result)
            except Exception:
                pass

    log(f"  {len(all_results)} coins analyses avec indicateurs")

    # Phase 2.5 — Multi-timeframe confirmation (5min) sur top candidats
    mtf_candidates = [r for r in all_results if r["score"] >= 55]
    if mtf_candidates:
        mtf_boosts = 0
        def check_5min(r):
            try:
                candles_5m = fetch_klines(r["symbol"], interval="Min5", limit=60)
                if not candles_5m or len(candles_5m) < 20:
                    return r
                closes_5m = [c["c"] for c in candles_5m]
                rsi_5m = rsi(closes_5m)
                ema8_5m = ema(closes_5m, 8)
                ema21_5m = ema(closes_5m, 21)
                dir_5m = "LONG" if ema8_5m[-1] > ema21_5m[-1] else "SHORT"
                # Convergence: meme direction sur 15min et 5min = +10
                if dir_5m == r["direction"]:
                    r["score"] = min(r["score"] + 10, 100)
                    r["patterns"].append("MTF_CONFIRM")
                # RSI 5min aligne = +5
                if r["direction"] == "LONG" and 45 < rsi_5m < 70:
                    r["score"] = min(r["score"] + 5, 100)
                elif r["direction"] == "SHORT" and 30 < rsi_5m < 55:
                    r["score"] = min(r["score"] + 5, 100)
                r["rsi_5m"] = rsi_5m
                r["dir_5m"] = dir_5m
            except Exception:
                pass
            return r
        with ThreadPoolExecutor(max_workers=12) as pool:
            mtf_futs = [pool.submit(check_5min, r) for r in mtf_candidates]
            for f in as_completed(mtf_futs, timeout=60):
                try:
                    result = f.result()
                    if result and "MTF_CONFIRM" in result.get("patterns", []):
                        mtf_boosts += 1
                except Exception:
                    pass
        log(f"  MTF 5min: {mtf_boosts}/{len(mtf_candidates)} confirmes")

    # Enrichissement historique
    history_boosts = 0
    signals = []
    for r in all_results:
        prev = get_previous_snapshot(db, r["symbol"])
        bonus, h_pats = compute_history_bonus(prev, r)
        if bonus > 0:
            r["score"] = min(r["score"] + bonus, 100)
            r["patterns"].extend(h_pats)
            history_boosts += 1
        if prev:
            price_delta = (r["price"] - prev["price"]) / prev["price"] * 100 if prev["price"] > 0 else 0
            r["prev_price"] = prev["price"]
            r["prev_sentiment"] = prev.get("sentiment", "")
            r["prev_score"] = prev.get("score", 0)
            r["prev_direction"] = prev.get("direction", "")
            r["prev_ts"] = prev.get("ts", "")
            r["price_evolution"] = price_delta
        if r["score"] >= 50:
            signals.append(r)

    signals.sort(key=lambda s: s["score"], reverse=True)
    phase2_ms = (time.time() - t2) * 1000
    log(f"  Phase 2: {len(signals)} signaux score>=50 ({history_boosts} boostes) ({phase2_ms:.0f}ms)")

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3 — GPU strategies (100 strats) + cluster IA consensus
    # ═══════════════════════════════════════════════════════════════════════════
    t3 = time.time()
    top_symbols = [s["symbol"] for s in signals[:30]]

    # GPU pipeline sur les top signaux
    if top_symbols:
        log(f"PHASE 3: GPU 100 strategies + Cluster consensus...")
        gpu_data = try_gpu_pipeline(top_symbols)
        for sig in signals:
            gd = gpu_data.get(sig["symbol"])
            if gd:
                sig["gpu_confidence"] = gd["confidence"]
                sig["gpu_regime"] = gd["regime"]
                sig["gpu_strategies"] = gd["strategies"][:5]
                # Boost score with GPU confidence
                gpu_bonus = int(gd["confidence"] * 15)
                sig["score"] = min(sig["score"] + gpu_bonus, 100)
                if gd["strategies"]:
                    sig["patterns"].append(f"GPU_{len(gd['strategies'])}strats")

    # Cluster consensus sur les top 8
    if with_consensus and signals:
        top_for_consensus = signals[:8]
        log(f"  Cluster consensus sur top {len(top_for_consensus)} signaux...")
        for sig in top_for_consensus:
            try:
                cons = cluster_consensus(sig)
                sig["consensus"] = cons["consensus"]
                sig["consensus_pct"] = cons["consensus_pct"]
                sig["cluster_nodes"] = cons["nodes_used"]
                sig["reasons"] = cons["reasons"]
            except Exception:
                sig["consensus"] = "SKIP"
                sig["cluster_nodes"] = []

    # Re-trier apres GPU boost
    signals.sort(key=lambda s: s["score"], reverse=True)
    phase3_ms = (time.time() - t3) * 1000
    duration = time.time() - t_start
    log(f"  Phase 3: GPU + consensus ({phase3_ms:.0f}ms)")
    log(f"  TOTAL: {duration:.1f}s | {len(valid_tickers)} coins registres | {len(all_results)} analyses | {len(signals)} signaux")

    # Check signaux trackes precedents (TP/SL touches ?)
    try:
        tracker = check_tracked_signals(db, tickers_map)
        if tracker["checked"] > 0:
            log(f"  Tracker: {tracker['checked']} signaux verifies | TP1:{tracker['tp1_hits']} TP2:{tracker['tp2_hits']} TP3:{tracker['tp3_hits']} SL:{tracker['sl_hits']}")
    except Exception:
        pass

    # ═══════════════════════════════════════════════════════════════════════════
    # SAVE — Tout en base SQL
    # ═══════════════════════════════════════════════════════════════════════════
    try:
        cur = db.execute(
            "INSERT INTO scan_runs (coins_scanned, signals_found, breakouts, duration_s, phase1_ms, phase2_ms, phase3_ms) VALUES (?,?,?,?,?,?,?)",
            (len(scan_tickers), len(signals),
             sum(1 for s in signals if "BB_SQUEEZE" in s.get("patterns", []) or "TIGHT_RANGE" in s.get("patterns", [])),
             duration, phase1_ms, phase2_ms, phase3_ms)
        )
        scan_id = cur.lastrowid

        # Snapshots de TOUS les coins analyses
        save_coin_snapshots(db, scan_id, all_results, tickers_map)

        # Mise a jour des scores dans le registre
        for r in all_results:
            update_registry_scores(db, r["symbol"], r["score"], r["direction"])

        # Top signaux detailles
        for sig in signals[:20]:
            db.execute(
                "INSERT INTO scan_signals (symbol, direction, score, entry, tp1, tp2, tp3, sl, atr, rsi, volume_ratio, bb_squeeze, pattern, consensus, cluster_nodes, gpu_confidence, gpu_strategies, gpu_regime) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sig["symbol"], sig["direction"], sig["score"], sig["entry"],
                 sig["tp1"], sig["tp2"], sig["tp3"], sig["sl"], sig["atr"],
                 sig["rsi"], sig["volume_ratio"], sig["bb_squeeze"],
                 ",".join(sig["patterns"]), sig.get("consensus", ""),
                 ",".join(sig.get("cluster_nodes", [])),
                 sig.get("gpu_confidence", 0),
                 ",".join(sig.get("gpu_strategies", [])[:5]),
                 sig.get("gpu_regime", ""))
            )
        db.commit()
        log(f"  DB: scan #{scan_id} | {len(all_results)} snapshots | {len(signals)} signaux")
    except Exception as e:
        log(f"  DB error: {e}")
    finally:
        db.close()

    return {"signals": signals, "total_coins": len(scan_tickers), "total_analyzed": len(all_results)}

# ─── Telegram Formatting ─────────────────────────────────────────────────────

def format_signal(sig, rank=1):
    """Format signal pour Telegram — clair, compact, lisible."""
    raw = sig["symbol"].replace("_USDT", "")
    pair = f"{raw}/USDT"
    d = "LONG" if sig["direction"] == "LONG" else "SHORT"
    emoji = "🟢" if d == "LONG" else "🔴"
    cons = sig.get("consensus", "")
    cons_tag = " ✅" if cons == "AGREE" else " ⚠️" if cons == "DISAGREE" else ""

    def fmt(v):
        if v >= 1000: return f"{v:.2f}"
        if v >= 1: return f"{v:.4f}"
        if v >= 0.01: return f"{v:.6f}"
        return f"{v:.8f}"

    entry = sig['entry']
    risk_pct = abs(sig['sl'] - entry) / entry * 100
    tp1_pct = abs(sig['tp1'] - entry) / entry * 100
    tp2_pct = abs(sig['tp2'] - entry) / entry * 100
    tp3_pct = abs(sig['tp3'] - entry) / entry * 100
    rr = tp2_pct / risk_pct if risk_pct > 0 else 0

    patterns_clean = []
    for p in sig.get("patterns", [])[:3]:
        p_map = {
            "BB_SQUEEZE": "Squeeze BB", "TIGHT_RANGE": "Range serre",
            "VOL_SPIKE_3x": "Vol x3", "VOL_SPIKE_2x": "Vol x2",
            "vol_above_avg": "Vol+", "rsi_momentum": "RSI force",
            "rsi_oversold_bounce": "RSI rebond", "bullish_stack": "EMA bull",
            "bearish_stack": "EMA bear", "NEAR_BB_UPPER": "BB haute",
            "NEAR_BB_LOWER": "BB basse", "bb_tightening": "BB compress",
        }
        patterns_clean.append(p_map.get(p, p))

    lines = [
        f"{emoji} {rank}. {pair} — {d} {sig['score']}/100{cons_tag}",
        f"   Entry   {fmt(entry)}",
        f"   TP1     {fmt(sig['tp1'])}  (+{tp1_pct:.1f}%)",
        f"   TP2     {fmt(sig['tp2'])}  (+{tp2_pct:.1f}%)",
        f"   TP3     {fmt(sig['tp3'])}  (+{tp3_pct:.1f}%)",
        f"   SL      {fmt(sig['sl'])}  (-{risk_pct:.1f}%)",
        f"   R:R {rr:.1f}x | RSI {sig['rsi']:.0f} | Vol x{sig['volume_ratio']:.1f} | 24h {sig['change_24h']:+.1f}%",
    ]
    if patterns_clean:
        lines.append(f"   {' | '.join(patterns_clean)}")
    if sig.get("cluster_nodes"):
        nodes = ', '.join(sig['cluster_nodes'][:3])
        lines.append(f"   Cluster: {nodes} ({sig.get('consensus_pct', 0)*100:.0f}%)")
    if sig.get("prev_price"):
        evo = sig["price_evolution"]
        prev_dir = sig.get("prev_direction", "?")
        prev_score = sig.get("prev_score", 0)
        lines.append(f"   Hist: {evo:+.2f}% | avant {prev_dir} {prev_score:.0f}pts")
    return "\n".join(lines)

def format_scan_report(signals, coins_total=0):
    """Format rapport scan complet pour Telegram — clair et compact."""
    if not signals:
        return "🔍 Scan termine — aucun signal score > 50."

    now = datetime.now().strftime('%H:%M')
    breakouts = sum(1 for s in signals if any(p in s.get("patterns", []) for p in ["BB_SQUEEZE", "TIGHT_RANGE"]))
    longs = sum(1 for s in signals if s["direction"] == "LONG")
    shorts = len(signals) - longs

    header = f"🎯 SNIPER SCAN — {now}\n"
    if coins_total > 0:
        header += f"📊 {coins_total} coins | "
    header += f"{len(signals)} signaux ({longs}L/{shorts}S) | {breakouts} breakouts\n"
    header += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    blocks = [header]
    for i, sig in enumerate(signals[:10]):
        blocks.append("")
        blocks.append(format_signal(sig, i + 1))

    blocks.append("")
    blocks.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    blocks.append("⚠️ Analyse IA — pas un conseil financier")
    return "\n".join(blocks)

def _alerts_enabled():
    """Check if trading alerts are enabled (shared flag with Telegram bot)."""
    flag = TURBO_ROOT / "data" / ".trading_alerts_off"
    return not flag.exists()

def send_telegram(text, chat_id=None):
    """Send message to Telegram. Respects global alert flag."""
    if not _alerts_enabled():
        log("  [MUTED] Telegram alert suppressed (alertoff active)")
        return
    token = TELEGRAM_TOKEN
    if not token:
        # Load from .env
        env_path = TURBO_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("TELEGRAM_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                elif line.startswith("TELEGRAM_CHAT=") and not chat_id:
                    chat_id = line.split("=", 1)[1].strip()
    if not token:
        log("No TELEGRAM_TOKEN found")
        return
    cid = chat_id or TELEGRAM_CHAT
    # Split long messages
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        try:
            http_post(f"https://api.telegram.org/bot{token}/sendMessage", {
                "chat_id": cid, "text": chunk, "parse_mode": "Markdown"
            }, timeout=10)
        except Exception as e:
            # Retry without parse_mode
            try:
                http_post(f"https://api.telegram.org/bot{token}/sendMessage", {
                    "chat_id": cid, "text": chunk
                }, timeout=10)
            except Exception:
                log(f"Telegram send failed: {e}")

def send_voice_summary(signals, chat_id=None):
    """Generate TTS voice summary of top signals and send via Telegram."""
    if not signals or not _alerts_enabled():
        return
    n = len(signals)
    longs = sum(1 for s in signals if s["direction"] == "LONG")
    shorts = n - longs
    lines = [f"Alerte sniper. {n} signaux detectes, {longs} achats et {shorts} ventes."]
    for i, sig in enumerate(signals[:3]):
        sym = sig["symbol"].replace("_USDT", "")
        d = "achat" if sig["direction"] == "LONG" else "vente"
        v = sig.get("validations", 0)
        tp1_pct = abs(sig['tp1'] - sig['entry']) / sig['entry'] * 100 if sig['entry'] > 0 else 0
        lines.append(f"Numero {i+1}. {sym}, {d}, score {sig['score']:.0f} sur 100, {v} validations.")
        lines.append(f"Objectif un a plus {tp1_pct:.1f} pour cent.")
        pats = sig.get("patterns", [])
        if "MTF_CONFIRM" in pats:
            lines.append("Multi timeframe confirme.")
        if "MOMENTUM_ACCEL" in pats:
            lines.append("Acceleration du momentum en cours.")
        if "VOLUME_CLIMAX" in pats:
            lines.append("Pic de volume detecte.")
        evo = sig.get("price_evolution")
        if evo is not None and abs(evo) > 0.5:
            direction_evo = "hausse" if evo > 0 else "baisse"
            lines.append(f"Evolution de {abs(evo):.1f} pour cent en {direction_evo} depuis le dernier scan.")
        if sig.get("confirmed_by_history"):
            lines.append("Direction confirmee par l'historique.")
    lines.append("Fin du rapport sniper.")
    text = " ".join(lines)
    tts_script = str(TURBO_ROOT / "scripts" / "tts_stdin.py")
    tts_args = ["python", tts_script, "--telegram"]
    if chat_id:
        tts_args.append(f"--chat-id={chat_id}")
    try:
        proc = subprocess.run(tts_args, input=text, capture_output=True, text=True, timeout=45)
        if proc.returncode == 0:
            log("  Voice summary sent via Telegram")
        else:
            log(f"  TTS error: {proc.stderr[:200]}")
    except Exception as e:
        log(f"  TTS failed: {e}")


# ─── Micro-Backtest — validate signal quality on recent klines ────────────────

def micro_backtest(candles, direction, entry_idx=-1, tp1_mult=0.6, sl_mult=1.0):
    """Quick backtest: would this signal have worked on last N candles?
    Returns win_rate (0-1) based on similar setups in recent history.
    """
    if not candles or len(candles) < 40:
        return 0.5  # Neutral if not enough data

    closes = [c["c"] for c in candles]
    cur_atr = atr(candles)
    if cur_atr <= 0:
        return 0.5

    wins = 0
    tests = 0
    # Test last 20 candles as hypothetical entries
    for i in range(max(20, len(candles) - 20), len(candles) - 3):
        entry_price = candles[i]["c"]
        tp1 = entry_price + cur_atr * tp1_mult if direction == "LONG" else entry_price - cur_atr * tp1_mult
        sl = entry_price - cur_atr * sl_mult if direction == "LONG" else entry_price + cur_atr * sl_mult

        # Check next 3 candles
        hit_tp = False
        hit_sl = False
        for j in range(i + 1, min(i + 4, len(candles))):
            if direction == "LONG":
                if candles[j]["h"] >= tp1:
                    hit_tp = True
                    break
                if candles[j]["l"] <= sl:
                    hit_sl = True
                    break
            else:
                if candles[j]["l"] <= tp1:
                    hit_tp = True
                    break
                if candles[j]["h"] >= sl:
                    hit_sl = True
                    break
        if hit_tp:
            wins += 1
        tests += 1

    return wins / tests if tests > 0 else 0.5


# ─── Sniper Auto Mode ────────────────────────────────────────────────────────

def filter_sniper_signals(signals, min_score=85):
    """Filtre ultra-strict pour mode sniper — multi-validation obligatoire.

    Un signal sniper doit avoir:
    - Score >= min_score (85 par defaut)
    - Au moins 3 patterns convergents
    - Volume eleve (ratio > 1.5)
    - Consensus cluster AGREE (si disponible)
    - Direction confirmee par historique (si disponible)
    """
    sniper = []
    for sig in signals:
        if sig["score"] < min_score:
            continue
        # Au moins 3 patterns convergents
        if len(sig.get("patterns", [])) < 3:
            continue
        # Volume minimum
        if sig.get("volume_ratio", 0) < 1.5:
            continue
        # Consensus doit etre AGREE (si on a fait le consensus)
        if sig.get("consensus") and sig["consensus"] != "AGREE":
            continue
        # Bonus: direction confirmee par historique
        confirmed = sig.get("prev_direction") == sig.get("direction")

        pats = sig.get("patterns", [])

        # Calcul confiance multi-validation
        validations = 0
        if sig["score"] >= 85: validations += 1
        if sig.get("volume_ratio", 0) >= 2.0: validations += 1
        if "BB_SQUEEZE" in pats or "TIGHT_RANGE" in pats: validations += 1
        if sig.get("consensus") == "AGREE": validations += 1
        if confirmed: validations += 1
        if sig.get("gpu_confidence", 0) >= 0.7: validations += 1
        # Indicateurs de mouvement imminent
        if "MOMENTUM_ACCEL" in pats: validations += 1
        if "VOLUME_CLIMAX" in pats: validations += 1
        if "BIG_CANDLE" in pats: validations += 1
        if "MTF_CONFIRM" in pats: validations += 1  # Multi-timeframe = tres fiable
        if "STRONG_TREND" in pats: validations += 1  # ADX > 30 = tendance forte
        # VWAP alignment
        if (sig["direction"] == "LONG" and "ABOVE_VWAP" in pats) or \
           (sig["direction"] == "SHORT" and "BELOW_VWAP" in pats): validations += 1
        # Momentum streak
        if any(p.startswith("STREAK_") for p in pats): validations += 1

        # Bonus imminence: si momentum + volume = c'est maintenant
        imminent = sum(1 for p in pats if p in [
            "MOMENTUM_ACCEL", "VOLUME_CLIMAX", "BIG_CANDLE",
            "VOL_SPIKE_3x", "HAMMER_REJECT", "SHOOTING_STAR",
            "EXPLOSION_EN_COURS", "MOUVEMENT_RAPIDE"
        ])
        sig["imminent_score"] = imminent

        sig["validations"] = validations
        sig["confirmed_by_history"] = confirmed
        if validations >= 3:
            sniper.append(sig)

    sniper.sort(key=lambda s: (s["validations"], s.get("imminent_score", 0), s["score"]), reverse=True)
    return sniper


def format_sniper_alert(signals):
    """Format alerte sniper pour mouvement explosif detecte."""
    if not signals:
        return ""
    now = datetime.now().strftime('%H:%M')

    def fmt(val):
        if val >= 1000: return f"{val:.2f}"
        if val >= 1: return f"{val:.4f}"
        if val >= 0.01: return f"{val:.6f}"
        return f"{val:.8f}"

    lines = [
        f"🚨 ALERTE SNIPER — {now}",
        f"{len(signals)} signaux explosifs multi-valides",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for i, sig in enumerate(signals[:5]):
        pair = sig["symbol"].replace("_USDT", "") + "/USDT"
        d = "LONG" if sig["direction"] == "LONG" else "SHORT"
        emoji = "🟢" if d == "LONG" else "🔴"
        v = sig.get("validations", 0)
        entry = sig['entry']
        risk_pct = abs(sig['sl'] - entry) / entry * 100
        tp1_pct = abs(sig['tp1'] - entry) / entry * 100
        tp2_pct = abs(sig['tp2'] - entry) / entry * 100
        tp3_pct = abs(sig['tp3'] - entry) / entry * 100
        rr = tp2_pct / risk_pct if risk_pct > 0 else 0

        lines.append(f"")
        lines.append(f"{emoji} {i+1}. {pair} — {d} {sig['score']:.0f}/100 ({v} valid.)")
        lines.append(f"   Entry   {fmt(entry)}")
        lines.append(f"   TP1     {fmt(sig['tp1'])}  (+{tp1_pct:.1f}%)")
        lines.append(f"   TP2     {fmt(sig['tp2'])}  (+{tp2_pct:.1f}%)")
        lines.append(f"   TP3     {fmt(sig['tp3'])}  (+{tp3_pct:.1f}%)")
        lines.append(f"   SL      {fmt(sig['sl'])}  (-{risk_pct:.1f}%)")
        lines.append(f"   R:R {rr:.1f}x | RSI {sig.get('rsi', 0):.0f} | Vol x{sig.get('volume_ratio', 0):.1f}")

        reasons = []
        if "BB_SQUEEZE" in sig.get("patterns", []): reasons.append("Squeeze BB")
        if sig.get("volume_ratio", 0) >= 2.0: reasons.append(f"Vol x{sig['volume_ratio']:.1f}")
        if sig.get("consensus") == "AGREE": reasons.append("Cluster OK")
        if sig.get("confirmed_by_history"): reasons.append("Hist. confirme")
        if sig.get("gpu_confidence", 0) >= 0.7: reasons.append(f"GPU {sig['gpu_confidence']:.0%}")
        if "MTF_CONFIRM" in sig.get("patterns", []): reasons.append("Multi-TF OK")
        imm = sig.get("imminent_score", 0)
        if imm >= 2: reasons.append(f"IMMINENT({imm})")
        if reasons:
            lines.append(f"   {' | '.join(reasons)}")

        if sig.get("price_evolution") is not None:
            lines.append(f"   Hist: {sig['price_evolution']:+.2f}% depuis dernier scan")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ Signal sniper — pas un conseil financier")
    return "\n".join(lines)


def emit_tracked_signal(db, sig):
    """Enregistre un signal sniper emis pour suivi de performance."""
    now = datetime.now().isoformat(timespec='seconds')
    db.execute(
        "INSERT INTO signal_tracker (symbol, direction, entry_price, tp1, tp2, tp3, sl, "
        "score, validations, emitted_at, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (sig["symbol"], sig["direction"], sig["entry"],
         sig["tp1"], sig["tp2"], sig["tp3"], sig["sl"],
         sig["score"], sig.get("validations", 0), now, "OPEN")
    )
    db.commit()


def check_tracked_signals(db, tickers_map):
    """Verifie les signaux ouverts — TP/SL touches ? Expire apres 2h."""
    open_sigs = db.execute(
        "SELECT id, symbol, direction, entry_price, tp1, tp2, tp3, sl, emitted_at FROM signal_tracker WHERE status='OPEN'"
    ).fetchall()
    now = datetime.now().isoformat(timespec='seconds')
    now_ts = time.time()
    results = {"tp1_hits": 0, "tp2_hits": 0, "tp3_hits": 0, "sl_hits": 0, "checked": 0, "expired": 0}

    for row in open_sigs:
        sid, sym, direction, entry, tp1, tp2, tp3, sl, emitted_at = row

        # Auto-expire signals older than 2h
        try:
            emit_dt = datetime.fromisoformat(emitted_at)
            age_s = (datetime.now() - emit_dt).total_seconds()
            if age_s > 7200:  # 2 hours
                db.execute("UPDATE signal_tracker SET status='EXPIRED', checked_at=? WHERE id=?", (now, sid))
                results["expired"] += 1
                continue
        except Exception:
            pass

        ticker = tickers_map.get(sym)
        if not ticker:
            continue
        cur_price = float(ticker.get("lastPrice", 0))
        if cur_price <= 0:
            continue
        results["checked"] += 1

        pnl = (cur_price - entry) / entry * 100 if direction == "LONG" else (entry - cur_price) / entry * 100
        tp1_hit = (cur_price >= tp1) if direction == "LONG" else (cur_price <= tp1)
        tp2_hit = (cur_price >= tp2) if direction == "LONG" else (cur_price <= tp2)
        tp3_hit = (cur_price >= tp3) if direction == "LONG" else (cur_price <= tp3)
        sl_hit = (cur_price <= sl) if direction == "LONG" else (cur_price >= sl)

        status = "OPEN"
        if tp1_hit: results["tp1_hits"] += 1
        if tp2_hit: results["tp2_hits"] += 1
        if tp3_hit:
            results["tp3_hits"] += 1
            status = "TP3_HIT"
        elif sl_hit:
            results["sl_hits"] += 1
            status = "SL_HIT"
        elif tp2_hit:
            status = "TP2_HIT"
        elif tp1_hit:
            status = "TP1_HIT"

        db.execute(
            "UPDATE signal_tracker SET checked_at=?, current_price=?, tp1_hit=?, tp2_hit=?, tp3_hit=?, sl_hit=?, pnl_pct=?, status=? WHERE id=?",
            (now, cur_price, int(tp1_hit), int(tp2_hit), int(tp3_hit), int(sl_hit), pnl, status, sid)
        )
    db.commit()
    return results


def periodic_report(scan_count, total_alerts, chat_id=None):
    """Rapport periodique envoye sur Telegram — resume marche."""
    try:
        db = sqlite3.connect(str(DB_PATH))
        reg_count = db.execute("SELECT COUNT(*) FROM coin_registry").fetchone()[0]
        snap_count = db.execute("SELECT COUNT(*) FROM coin_snapshots").fetchone()[0]
        # Top 5 coins les plus chauds actuellement
        hot = db.execute(
            "SELECT clean_name, avg_score, best_score, best_direction, last_change "
            "FROM coin_registry WHERE avg_score > 40 ORDER BY avg_score DESC LIMIT 5"
        ).fetchall()
        # Dernier scan stats
        last = db.execute(
            "SELECT signals_found, breakouts, duration_s FROM scan_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        db.close()

        now = datetime.now().strftime('%H:%M')
        lines = [
            f"RAPPORT PERIODIQUE {now}",
            f"Scans effectues: {scan_count} | Alertes envoyees: {total_alerts}",
            f"Coins en registry: {reg_count} | Snapshots: {snap_count}",
        ]
        if last:
            lines.append(f"Dernier scan: {last[0]} signaux, {last[1]} breakouts, {last[2]:.0f}s")
        if hot:
            lines.append("")
            lines.append("Coins les plus chauds:")
            for h in hot:
                d = "achat" if h[3] == "LONG" else "vente" if h[3] == "SHORT" else "?"
                lines.append(f"  {h[0]} — avg {h[1]:.0f}, best {h[2]:.0f}, {d}, 24h {h[4]:+.1f}%")

        # Performance tracker
        try:
            total_tracked = db.execute("SELECT COUNT(*) FROM signal_tracker").fetchone()[0]
            if total_tracked > 0:
                tp1_wins = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE tp1_hit=1").fetchone()[0]
                sl_losses = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE sl_hit=1").fetchone()[0]
                avg_pnl = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE status != 'OPEN'").fetchone()[0] or 0
                lines.append("")
                lines.append(f"Performance: {total_tracked} signaux trackes")
                lines.append(f"  TP1 touches: {tp1_wins} ({tp1_wins*100//total_tracked}%)")
                lines.append(f"  SL touches: {sl_losses} ({sl_losses*100//total_tracked}%)")
                lines.append(f"  PnL moyen: {avg_pnl:+.2f}%")
        except Exception:
            pass

        lines.append("")
        lines.append("Scanner permanent actif.")
        text = "\n".join(lines)
        send_telegram(text, chat_id=chat_id)
        log(f"  Periodic report sent (scan #{scan_count})")
    except Exception as e:
        log(f"  Periodic report error: {e}")


# ─── REALTIME MODE — Catch the Wave ──────────────────────────────────────────

def realtime_loop(notify=True, voice=True, chat_id=None, min_move=0.4, interval=30):
    """Mode temps reel — detecte les mouvements explosifs EN COURS.

    Cycle rapide (30s):
    1. Fetch ALL tickers (1 appel, <1s)
    2. Compare avec snapshot precedent (delta prix en 30s)
    3. Si un coin bouge > 0.4% en 30s avec volume → deep scan immediat
    4. Multi-validation: klines + indicateurs + MTF + cluster consensus
    5. Si tout converge → ALERTE avec TP1 serre (rapide a toucher)
    """
    log(f"REALTIME MODE — detecte mouvements > {min_move}% en {interval}s")
    log(f"  Notify: {notify} | Voice: {voice}")

    prev_prices = {}  # symbol -> (price, volume, ts)
    scan_count = 0
    total_alerts = 0
    db = sqlite3.connect(str(DB_PATH))
    cooldowns = {}  # symbol -> last_alert_ts (evite spam)

    while True:
        scan_count += 1
        t0 = time.time()
        try:
            # 1. Fetch ALL tickers (1 appel API, <1s)
            tickers = fetch_all_tickers()
            tickers_map = {t["symbol"]: t for t in tickers}
            now = time.time()

            # 2. Detecter les movers (delta prix rapide)
            movers = []
            for t in tickers:
                sym = t["symbol"]
                price = float(t.get("lastPrice", 0))
                vol = float(t.get("volume24", t.get("amount24", 0)))
                if price <= 0:
                    continue

                if sym in prev_prices:
                    prev_p, prev_v, prev_ts = prev_prices[sym]
                    elapsed = now - prev_ts
                    if elapsed < 5:
                        continue  # Trop rapide
                    delta_pct = (price - prev_p) / prev_p * 100
                    vol_change = vol / prev_v if prev_v > 0 else 1

                    # Mouvement significatif detecte
                    if abs(delta_pct) >= min_move:
                        # Cooldown: pas alerter le meme coin dans les 5 minutes
                        if sym in cooldowns and (now - cooldowns[sym]) < 300:
                            continue
                        movers.append({
                            "symbol": sym,
                            "price": price,
                            "prev_price": prev_p,
                            "delta_pct": delta_pct,
                            "vol_change": vol_change,
                            "direction": "LONG" if delta_pct > 0 else "SHORT",
                            "elapsed": elapsed,
                            "ticker": t,
                        })

                prev_prices[sym] = (price, vol, now)

            fetch_ms = (time.time() - t0) * 1000

            if not movers:
                if scan_count % 20 == 0:
                    log(f"  [{scan_count}] {len(tickers)} tickers, 0 movers (>{min_move}%) ({fetch_ms:.0f}ms)")
                time.sleep(interval)
                continue

            # Trier par amplitude du mouvement
            movers.sort(key=lambda m: abs(m["delta_pct"]), reverse=True)
            log(f"  [{scan_count}] {len(movers)} MOVERS detectes en {fetch_ms:.0f}ms:")
            for m in movers[:5]:
                log(f"    {m['symbol'].replace('_USDT','')} {m['delta_pct']:+.2f}% en {m['elapsed']:.0f}s")

            # 3. Deep scan des movers (klines + indicateurs + depth)
            confirmed = []
            def deep_scan_mover(m):
                sym = m["symbol"]
                try:
                    candles = fetch_klines(sym, interval="Min5", limit=60)
                    if not candles or len(candles) < 20:
                        return None
                    depth = None
                    try:
                        depth = fetch_depth(sym)
                    except Exception:
                        pass
                    result = analyze_coin(sym, candles, m["ticker"], depth)
                    if not result:
                        return None
                    # Override entry to current price (market order)
                    result["entry"] = m["price"]
                    result["realtime_delta"] = m["delta_pct"]
                    result["realtime_elapsed"] = m["elapsed"]
                    result["prev_price"] = m["prev_price"]
                    result["price_evolution"] = m["delta_pct"]

                    # FORCE direction from actual price movement (realtime truth)
                    realtime_dir = "LONG" if m["delta_pct"] > 0 else "SHORT"
                    if result["direction"] != realtime_dir:
                        # Indicators disagree with actual movement — trust the move
                        # but penalize score slightly (divergence = less reliable)
                        result["direction"] = realtime_dir
                        result["score"] = max(result["score"] - 5, 0)
                        result["patterns"].append("DIR_OVERRIDE")

                    # TP serre pour realtime (TP1 rapide a toucher)
                    atr_val = result["atr"] if result["atr"] > 0 else m["price"] * 0.003
                    if result["direction"] == "LONG":
                        result["tp1"] = m["price"] + atr_val * 0.6   # TP1 rapide
                        result["tp2"] = m["price"] + atr_val * 1.2
                        result["tp3"] = m["price"] + atr_val * 2.0
                        result["sl"] = m["price"] - atr_val * 1.0
                    else:
                        result["tp1"] = m["price"] - atr_val * 0.6
                        result["tp2"] = m["price"] - atr_val * 1.2
                        result["tp3"] = m["price"] - atr_val * 2.0
                        result["sl"] = m["price"] + atr_val * 1.0

                    # Bonus realtime: le mouvement est en cours
                    result["score"] = min(result["score"] + 15, 100)
                    result["patterns"].append("REALTIME_MOVE")

                    # Check MTF 15min pour confirmation
                    try:
                        candles_15m = fetch_klines(sym, interval="Min15", limit=30)
                        if candles_15m and len(candles_15m) >= 15:
                            closes_15m = [c["c"] for c in candles_15m]
                            ema8_15 = ema(closes_15m, 8)
                            ema21_15 = ema(closes_15m, 21)
                            dir_15m = "LONG" if ema8_15[-1] > ema21_15[-1] else "SHORT"
                            if dir_15m == result["direction"]:
                                result["score"] = min(result["score"] + 10, 100)
                                result["patterns"].append("MTF_15M_OK")
                    except Exception:
                        pass

                    # Micro-backtest: would similar setups have worked recently?
                    try:
                        bt_rate = micro_backtest(candles, result["direction"])
                        result["backtest_rate"] = bt_rate
                        if bt_rate >= 0.6:
                            result["score"] = min(result["score"] + 8, 100)
                            result["patterns"].append("BACKTEST_OK")
                        elif bt_rate < 0.3:
                            result["score"] = max(result["score"] - 10, 0)
                            result["patterns"].append("BACKTEST_WARN")
                    except Exception:
                        pass

                    return result
                except Exception:
                    return None

            with ThreadPoolExecutor(max_workers=8) as pool:
                futs = {pool.submit(deep_scan_mover, m): m for m in movers[:10]}
                for f in as_completed(futs, timeout=30):
                    try:
                        r = f.result()
                        if r and r["score"] >= 70:
                            confirmed.append(r)
                    except Exception:
                        pass

            if not confirmed:
                log(f"  Aucun mover confirme (score < 70)")
                time.sleep(interval)
                continue

            confirmed.sort(key=lambda s: s["score"], reverse=True)
            log(f"  {len(confirmed)} movers confirmes!")

            # 4. Cluster consensus sur les top 3
            for sig in confirmed[:3]:
                try:
                    cons = cluster_consensus(sig)
                    sig["consensus"] = cons["consensus"]
                    sig["consensus_pct"] = cons["consensus_pct"]
                    sig["cluster_nodes"] = cons["nodes_used"]
                except Exception:
                    sig["consensus"] = "SKIP"
                    sig["cluster_nodes"] = []

            # 5. Filtre final: score >= 75 + consensus OK
            alerts = []
            for sig in confirmed:
                if sig["score"] < 75:
                    continue
                if sig.get("consensus") == "DISAGREE":
                    continue
                # Compter validations
                pats = sig.get("patterns", [])
                v = 0
                if sig["score"] >= 80: v += 1
                if "REALTIME_MOVE" in pats: v += 1
                if "MTF_15M_OK" in pats: v += 1
                if sig.get("consensus") == "AGREE": v += 1
                if sig.get("volume_ratio", 0) >= 1.5: v += 1
                if "STRONG_TREND" in pats: v += 1
                if abs(sig.get("realtime_delta", 0)) >= 0.8: v += 1
                # VWAP alignment (price above VWAP for LONG, below for SHORT)
                if (sig["direction"] == "LONG" and "ABOVE_VWAP" in pats) or \
                   (sig["direction"] == "SHORT" and "BELOW_VWAP" in pats): v += 1
                # Momentum streak (3+ candles same direction)
                if any(p.startswith("STREAK_") or p.startswith("streak_") for p in pats): v += 1
                # Micro-backtest validation
                if "BACKTEST_OK" in pats: v += 1
                sig["validations"] = v
                if v >= 3:
                    alerts.append(sig)
                    cooldowns[sig["symbol"]] = now

            if alerts:
                alerts.sort(key=lambda s: (s["validations"], s["score"]), reverse=True)
                total_alerts += len(alerts)
                log(f"  REALTIME ALERT: {len(alerts)} signaux valides!")

                # Format et envoie
                report = format_realtime_alert(alerts)
                print(report)
                if notify:
                    send_telegram(report, chat_id=chat_id)
                if voice:
                    send_voice_summary(alerts[:3], chat_id=chat_id)

                # Track les signaux
                try:
                    for sig in alerts[:5]:
                        emit_tracked_signal(db, sig)
                except Exception:
                    pass

            # Check signaux ouverts
            try:
                tracker = check_tracked_signals(db, tickers_map)
                if tracker["checked"] > 0 and (tracker["tp1_hits"] > 0 or tracker["sl_hits"] > 0):
                    log(f"  Tracker: TP1:{tracker['tp1_hits']} TP2:{tracker['tp2_hits']} SL:{tracker['sl_hits']}")
            except Exception:
                pass

        except Exception as e:
            log(f"  Realtime error: {e}")

        elapsed = time.time() - t0
        wait = max(1, interval - elapsed)
        time.sleep(wait)


def format_realtime_alert(signals):
    """Format alerte realtime — mouvement EN COURS detecte."""
    if not signals:
        return ""
    now = datetime.now().strftime('%H:%M:%S')

    def fmt(val):
        if val >= 1000: return f"{val:.2f}"
        if val >= 1: return f"{val:.4f}"
        if val >= 0.01: return f"{val:.6f}"
        return f"{val:.8f}"

    lines = [
        f"MOUVEMENT DETECTE {now}",
        f"{len(signals)} signaux en temps reel",
        "",
    ]
    for i, sig in enumerate(signals[:5]):
        sym = sig["symbol"].replace("_USDT", "")
        d = "LONG" if sig["direction"] == "LONG" else "SHORT"
        v = sig.get("validations", 0)
        entry = sig["entry"]
        delta = sig.get("realtime_delta", 0)
        elapsed_s = sig.get("realtime_elapsed", 0)
        risk_pct = abs(sig['sl'] - entry) / entry * 100
        tp1_pct = abs(sig['tp1'] - entry) / entry * 100

        lines.append(f"{i+1}. {sym} {d} score {sig['score']:.0f}/100 ({v} valid.)")
        lines.append(f"   Mouvement: {delta:+.2f}% en {elapsed_s:.0f}s")
        lines.append(f"   Entry  {fmt(entry)}")
        lines.append(f"   TP1    {fmt(sig['tp1'])} (+{tp1_pct:.2f}%)")
        lines.append(f"   TP2    {fmt(sig['tp2'])}")
        lines.append(f"   SL     {fmt(sig['sl'])} (-{risk_pct:.2f}%)")

        reasons = []
        if sig.get("consensus") == "AGREE": reasons.append("Cluster OK")
        if "MTF_15M_OK" in sig.get("patterns", []): reasons.append("MTF 15m OK")
        if "STRONG_TREND" in sig.get("patterns", []): reasons.append("Trend fort")
        if sig.get("volume_ratio", 0) >= 2: reasons.append(f"Vol x{sig['volume_ratio']:.1f}")
        if "BACKTEST_OK" in sig.get("patterns", []): reasons.append(f"Backtest {sig.get('backtest_rate', 0)*100:.0f}%")
        if "ABOVE_VWAP" in sig.get("patterns", []) or "BELOW_VWAP" in sig.get("patterns", []): reasons.append("VWAP OK")
        streak_pat = [p for p in sig.get("patterns", []) if p.startswith("STREAK_")]
        if streak_pat: reasons.append(f"Streak {streak_pat[0].split('_')[1]}")
        if reasons:
            lines.append(f"   {' | '.join(reasons)}")
        lines.append("")

    lines.append("Mouvement en cours. Pas un conseil financier.")
    return "\n".join(lines)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="JARVIS Sniper Scanner")
    parser.add_argument("--once", action="store_true", help="Single scan")
    parser.add_argument("--loop", action="store_true", help="Continuous scanning")
    parser.add_argument("--realtime", action="store_true", help="Realtime mode: detect moves in progress")
    parser.add_argument("--top", type=int, default=TOP_N, help="Top N coins by volume (0=ALL)")
    parser.add_argument("--all", action="store_true", help="Scan ALL coins (equivalent to --top 0)")
    parser.add_argument("--notify", action="store_true", help="Send to Telegram")
    parser.add_argument("--chat-id", type=str, help="Telegram chat ID")
    parser.add_argument("--no-consensus", action="store_true", help="Skip cluster consensus")
    parser.add_argument("--voice", action="store_true", help="Send voice via TTS + Telegram")
    parser.add_argument("--sniper", action="store_true", help="Sniper auto mode: only ultra-high confidence signals")
    parser.add_argument("--min-score", type=int, default=50, help="Minimum score to report (default 50, sniper=85)")
    parser.add_argument("--min-move", type=float, default=0.4, help="Min move % for realtime detection (default 0.4)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--interval", type=int, default=SCAN_INTERVAL, help="Scan interval in seconds (default 300)")
    args = parser.parse_args()

    init_db()

    top_n = 0 if args.all else args.top
    min_score = 85 if args.sniper else args.min_score
    interval = 60 if args.sniper else args.interval  # Sniper = scan every 60s

    def run_scan():
        result = scan(top_n=top_n, with_consensus=not args.no_consensus)
        signals = result["signals"]
        total = result["total_coins"]

        # Sniper mode: filtre strict multi-validation
        if args.sniper:
            sniper_signals = filter_sniper_signals(signals, min_score=min_score)
            if sniper_signals:
                report = format_sniper_alert(sniper_signals)
                print(report)
                send_telegram(report, chat_id=args.chat_id)
                send_voice_summary(sniper_signals[:3], chat_id=args.chat_id)
                # Tracker les signaux emis
                try:
                    db = sqlite3.connect(str(DB_PATH))
                    for sig in sniper_signals[:5]:
                        emit_tracked_signal(db, sig)
                    db.close()
                    log(f"  {len(sniper_signals[:5])} signaux enregistres pour suivi")
                except Exception:
                    pass
                log(f"  SNIPER ALERT: {len(sniper_signals)} signaux explosifs envoyes")
            else:
                log(f"  Sniper: aucun signal >= {min_score} multi-valide ({len(signals)} candidats)")
        else:
            if args.json:
                print(json.dumps([{k: v for k, v in s.items() if k != "reasons"} for s in signals[:10]], indent=2, default=str))
            else:
                report = format_scan_report(signals, coins_total=total)
                print(report)
            if args.notify or args.chat_id:
                report = format_scan_report(signals, coins_total=total)
                send_telegram(report, chat_id=args.chat_id)
                log(f"  Telegram sent to {args.chat_id or TELEGRAM_CHAT}")
            if args.voice and signals:
                send_voice_summary(signals[:5], chat_id=args.chat_id)
        return signals

    if args.realtime:
        realtime_loop(
            notify=args.notify or bool(args.chat_id),
            voice=args.voice,
            chat_id=args.chat_id,
            min_move=args.min_move,
            interval=30,
        )
    elif args.loop or args.sniper:
        mode = "SNIPER AUTO" if args.sniper else "CONTINU"
        log(f"Scanner mode {mode} (interval {interval}s, min_score {min_score})")
        scan_count = 0
        total_alerts = 0
        while True:
            scan_count += 1
            try:
                log(f"--- Scan #{scan_count} ---")
                sigs = run_scan()
                if sigs and args.sniper:
                    total_alerts += len([s for s in sigs if s.get("validations", 0) >= 3 and s["score"] >= min_score])

                # Rapport periodique toutes les 10 scans en sniper mode
                if args.sniper and scan_count % 10 == 0:
                    periodic_report(scan_count, total_alerts, chat_id=args.chat_id)
            except Exception as e:
                log(f"Scan error: {e}")
            time.sleep(interval)
    else:
        run_scan()

if __name__ == "__main__":
    main()
