"""
JARVIS Scan Sniper v4 — GPU Multi-GPU + 31 strategies pre-pump
PyTorch batch sur 5 GPU (RTX 3080 + RTX 2060 + 3x GTX 1660S = 40GB VRAM)
31 strategies: Chaikin, CMF, OBV, ADL, MFI, Williams %R, ADX,
Volume Profile, orderbook ultra (gradient, absorption, spoofing, voids).

Commande vocale: "scan sniper"
Usage: python scripts/scan_sniper.py [--json] [--top N] [--cycles N] [--interval N]
"""
import asyncio
import httpx
import sys
import json
import math
import time
import subprocess
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

# ========== GPU SETUP ==========
try:
    import torch
    if torch.cuda.is_available():
        GPU_AVAILABLE = True
        GPU_COUNT = torch.cuda.device_count()
        GPU_DEVICES = [torch.device(f"cuda:{i}") for i in range(GPU_COUNT)]
        _vrams = [torch.cuda.get_device_properties(i).total_memory for i in range(GPU_COUNT)]
        PRIMARY_GPU = torch.device(f"cuda:{_vrams.index(max(_vrams))}")
    else:
        GPU_AVAILABLE = False
        GPU_COUNT = 0
        GPU_DEVICES = []
        PRIMARY_GPU = None
except ImportError:
    torch = None
    GPU_AVAILABLE = False
    GPU_COUNT = 0
    GPU_DEVICES = []
    PRIMARY_GPU = None

# Force UTF-8 stdout (Windows cp1252 crashe sur caracteres speciaux)
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE = "https://contract.mexc.com/api/v1/contract"

# Config
TOP_VOLUME = 100
MIN_VOL_24H = 500_000
TP_MULT = 1.5
SL_MULT = 1.0
MIN_SCORE = 40
DB_PATH = Path("F:/BUREAU/turbo/data/sniper.db")


@dataclass
class Signal:
    symbol: str
    direction: str
    score: int
    last_price: float
    entry: float
    tp: float
    sl: float
    strategies: list
    reasons: list
    volume_24h: float
    change_24h: float
    funding_rate: float
    liquidity_bias: str
    liquidity_clusters: list = field(default_factory=list)
    ob_analysis: dict = field(default_factory=dict)
    atr: float = 0.0
    rsi: float = 50.0
    chaikin_osc: float = 0.0
    cmf: float = 0.0
    obv_trend: str = ""
    mfi: float = 50.0
    williams_r: float = -50.0
    adx: float = 0.0
    macd_signal: str = ""
    bb_squeeze: bool = False
    regime: str = "unknown"
    open_interest_chg: float = 0.0


# ========== SQL DATABASE ==========

def init_db(db_path=DB_PATH):
    """Cree/ouvre la base sniper.db avec toutes les tables."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript("""
        -- Coins: fiche maitre par symbole, categorie, stats aggregees
        CREATE TABLE IF NOT EXISTS coins (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            category TEXT DEFAULT 'unknown',
            sub_category TEXT DEFAULT '',
            first_seen TEXT,
            last_seen TEXT,
            scan_count INTEGER DEFAULT 0,
            signal_count INTEGER DEFAULT 0,
            avg_score REAL DEFAULT 0,
            max_score INTEGER DEFAULT 0,
            dominant_direction TEXT DEFAULT '',
            long_count INTEGER DEFAULT 0,
            short_count INTEGER DEFAULT 0,
            avg_volume_24h REAL DEFAULT 0,
            best_strategies TEXT DEFAULT '[]',
            regime_history TEXT DEFAULT '[]',
            notes TEXT DEFAULT ''
        );

        -- Signals: chaque signal detecte par cycle
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle INTEGER,
            timestamp TEXT,
            symbol TEXT,
            direction TEXT,
            score INTEGER,
            last_price REAL,
            entry REAL,
            tp REAL,
            sl REAL,
            atr REAL,
            rsi REAL,
            mfi REAL,
            williams_r REAL,
            adx REAL,
            cmf REAL,
            chaikin_osc REAL,
            obv_trend TEXT,
            macd_signal TEXT,
            bb_squeeze INTEGER,
            regime TEXT,
            funding_rate REAL,
            change_24h REAL,
            volume_24h REAL,
            liquidity_bias TEXT,
            strategies TEXT,
            reasons TEXT,
            ob_analysis TEXT,
            FOREIGN KEY (symbol) REFERENCES coins(symbol)
        );

        -- Categories: definitions des categories de coins
        CREATE TABLE IF NOT EXISTS categories (
            id TEXT PRIMARY KEY,
            label TEXT,
            description TEXT,
            keywords TEXT,
            color TEXT DEFAULT '#888'
        );

        -- Scans: meta-donnees par cycle de scan
        CREATE TABLE IF NOT EXISTS scans (
            cycle INTEGER PRIMARY KEY,
            timestamp TEXT,
            coins_scanned INTEGER,
            signals_found INTEGER,
            scan_time_s REAL,
            gpu_used INTEGER,
            gpu_count INTEGER,
            top1_symbol TEXT,
            top1_score INTEGER,
            thermal_max INTEGER DEFAULT 0
        );

        -- Index pour rapidite
        CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
        CREATE INDEX IF NOT EXISTS idx_signals_cycle ON signals(cycle);
        CREATE INDEX IF NOT EXISTS idx_signals_score ON signals(score DESC);
        CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(timestamp);
        CREATE INDEX IF NOT EXISTS idx_coins_category ON coins(category);
        CREATE INDEX IF NOT EXISTS idx_coins_score ON coins(avg_score DESC);
    """)

    # Insert default categories
    default_cats = [
        ("blue_chip", "Blue Chip", "BTC, ETH, majeurs haute liquidite", "BTC,ETH,BNB,SOL,XRP", "#3B82F6"),
        ("defi", "DeFi", "Finance decentralisee, DEX, lending", "UNI,AAVE,COMP,MKR,CRV,SUSHI,DYDX,SNX,1INCH,CAKE,JUP", "#8B5CF6"),
        ("layer1", "Layer 1", "Blockchains principales", "SOL,ADA,AVAX,DOT,ATOM,NEAR,APT,SUI,SEI,TIA,ICP,FTM,ALGO", "#10B981"),
        ("layer2", "Layer 2", "Scaling solutions Ethereum", "ARB,OP,MATIC,STRK,ZK,MANTA,BLAST,MODE,SCROLL", "#06B6D4"),
        ("meme", "Meme", "Memecoins haute volatilite", "DOGE,SHIB,PEPE,FLOKI,BONK,WIF,BRETT,NEIRO,TURBO,MOODENG,PNUT", "#F59E0B"),
        ("ai", "AI & Data", "Intelligence artificielle, compute", "FET,RENDER,TAO,RNDR,AGIX,OCEAN,AKT,AI16Z,VIRTUAL,GRIFFAIN", "#EC4899"),
        ("gaming", "Gaming & Metaverse", "Jeux, NFT, metaverse", "IMX,GALA,AXS,SAND,MANA,ILV,PIXEL,PORTAL,RONIN,PRIME", "#F97316"),
        ("infra", "Infrastructure", "Oracles, storage, bridges", "LINK,FIL,GRT,PYTH,RENDER,AR,THETA,HNT,STX,W", "#6366F1"),
        ("rwa", "RWA", "Real World Assets, commodities", "XAUT,SILVER,ONDO,MKR,PAXG", "#D4A843"),
        ("exchange", "Exchange", "Tokens de plateformes", "BNB,OKB,CRO,GT,MX,KCS", "#EF4444"),
        ("unknown", "Non classe", "Coins pas encore categorises", "", "#6B7280"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO categories (id, label, description, keywords, color) VALUES (?,?,?,?,?)",
        default_cats
    )
    conn.commit()
    return conn


def classify_coin(symbol: str, conn: sqlite3.Connection) -> str:
    """Classe un coin dans sa categorie via les keywords des categories."""
    coin = symbol.replace("_USDT", "")
    rows = conn.execute("SELECT id, keywords FROM categories WHERE keywords != ''").fetchall()
    for cat_id, keywords in rows:
        if coin in [k.strip() for k in keywords.split(",")]:
            return cat_id
    return "unknown"


def save_signals_to_db(signals: list, cycle: int, scan_time: float,
                       coins_scanned: int, thermal_max: int = 0, conn=None):
    """Sauvegarde les signaux d'un cycle dans la DB."""
    close_after = False
    if conn is None:
        conn = init_db()
        close_after = True

    now = datetime.now(timezone.utc).isoformat()

    # Save scan meta
    top1 = signals[0] if signals else None
    conn.execute("""
        INSERT OR REPLACE INTO scans (cycle, timestamp, coins_scanned, signals_found,
            scan_time_s, gpu_used, gpu_count, top1_symbol, top1_score, thermal_max)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (cycle, now, coins_scanned, len(signals), round(scan_time, 2),
          1 if GPU_AVAILABLE else 0, GPU_COUNT,
          top1.symbol if top1 else None, top1.score if top1 else 0, thermal_max))

    for s in signals:
        # Save signal
        conn.execute("""
            INSERT INTO signals (cycle, timestamp, symbol, direction, score, last_price,
                entry, tp, sl, atr, rsi, mfi, williams_r, adx, cmf, chaikin_osc,
                obv_trend, macd_signal, bb_squeeze, regime, funding_rate, change_24h,
                volume_24h, liquidity_bias, strategies, reasons, ob_analysis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cycle, now, s.symbol, s.direction, s.score, s.last_price,
              s.entry, s.tp, s.sl, s.atr, s.rsi, s.mfi, s.williams_r, s.adx,
              s.cmf, s.chaikin_osc, s.obv_trend, s.macd_signal,
              1 if s.bb_squeeze else 0, s.regime, s.funding_rate, s.change_24h,
              s.volume_24h, s.liquidity_bias,
              json.dumps(s.strategies), json.dumps(s.reasons, ensure_ascii=False),
              json.dumps(s.ob_analysis)))

        # Upsert coin master record
        category = classify_coin(s.symbol, conn)
        existing = conn.execute("SELECT scan_count, signal_count, avg_score, max_score, "
                                "long_count, short_count, avg_volume_24h, best_strategies "
                                "FROM coins WHERE symbol = ?", (s.symbol,)).fetchone()
        if existing:
            sc, sig_c, avg_sc, max_sc, lc, shc, avg_v, best_str = existing
            new_sig_c = sig_c + 1
            new_avg = (avg_sc * sig_c + s.score) / new_sig_c
            new_max = max(max_sc, s.score)
            new_lc = lc + (1 if s.direction == "LONG" else 0)
            new_shc = shc + (1 if s.direction == "SHORT" else 0)
            new_avg_v = (avg_v * sig_c + s.volume_24h) / new_sig_c
            dom = "LONG" if new_lc > new_shc else "SHORT" if new_shc > new_lc else "MIXED"
            # Merge best strategies
            try:
                old_strats = json.loads(best_str) if best_str else []
            except (json.JSONDecodeError, TypeError):
                old_strats = []
            merged = list(set(old_strats + s.strategies))[:20]
            conn.execute("""
                UPDATE coins SET last_seen=?, scan_count=scan_count+1, signal_count=?,
                    avg_score=?, max_score=?, long_count=?, short_count=?,
                    dominant_direction=?, avg_volume_24h=?, best_strategies=?, category=?
                WHERE symbol=?
            """, (now, new_sig_c, round(new_avg, 1), new_max, new_lc, new_shc,
                  dom, round(new_avg_v, 0), json.dumps(merged), category, s.symbol))
        else:
            conn.execute("""
                INSERT INTO coins (symbol, name, category, first_seen, last_seen,
                    scan_count, signal_count, avg_score, max_score, dominant_direction,
                    long_count, short_count, avg_volume_24h, best_strategies)
                VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?, ?, ?)
            """, (s.symbol, s.symbol.replace("_USDT", ""), category, now, now,
                  s.score, s.score, s.direction,
                  1 if s.direction == "LONG" else 0,
                  1 if s.direction == "SHORT" else 0,
                  round(s.volume_24h, 0), json.dumps(s.strategies)))

    conn.commit()
    if close_after:
        conn.close()


def get_db_summary(conn=None) -> str:
    """Resume rapide de la DB pour affichage."""
    close_after = False
    if conn is None:
        conn = init_db()
        close_after = True

    lines = []
    # Stats globales
    total_coins = conn.execute("SELECT COUNT(*) FROM coins").fetchone()[0]
    total_signals = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    total_scans = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]

    lines.append(f"\n  DB: {total_coins} coins | {total_signals} signaux | {total_scans} scans")

    # Par categorie
    cats = conn.execute("""
        SELECT c.category, cat.label, COUNT(*) as cnt, ROUND(AVG(c.avg_score),0) as avg,
               MAX(c.max_score) as best, SUM(c.signal_count) as sigs
        FROM coins c LEFT JOIN categories cat ON c.category = cat.id
        GROUP BY c.category ORDER BY avg DESC
    """).fetchall()
    if cats:
        lines.append(f"  {'Categorie':<16} {'Coins':>5} {'Avg':>5} {'Best':>5} {'Signaux':>8}")
        lines.append(f"  {'-'*45}")
        for cat_id, label, cnt, avg, best, sigs in cats:
            lines.append(f"  {(label or cat_id):<16} {cnt:>5} {avg:>5.0f} {best:>5} {sigs:>8}")

    # Top 10 coins par score moyen
    top = conn.execute("""
        SELECT symbol, category, avg_score, max_score, signal_count,
               dominant_direction, best_strategies
        FROM coins ORDER BY avg_score DESC LIMIT 10
    """).fetchall()
    if top:
        lines.append(f"\n  --- Top 10 Coins ---")
        lines.append(f"  {'Coin':<12} {'Cat':<10} {'Avg':>5} {'Max':>5} {'Sigs':>5} {'Dir':<6}")
        lines.append(f"  {'-'*48}")
        for sym, cat, avg, mx, sigs, dir_, _ in top:
            coin = sym.replace("_USDT", "")
            lines.append(f"  {coin:<12} {(cat or '?'):<10} {avg:>5.0f} {mx:>5} {sigs:>5} {dir_:<6}")

    # Strategies les plus frequentes
    all_strats = conn.execute("SELECT strategies FROM signals ORDER BY id DESC LIMIT 500").fetchall()
    strat_count = {}
    for (strats_json,) in all_strats:
        try:
            for s in json.loads(strats_json):
                strat_count[s] = strat_count.get(s, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    if strat_count:
        sorted_strats = sorted(strat_count.items(), key=lambda x: -x[1])[:10]
        lines.append(f"\n  --- Top Strategies ---")
        for strat, cnt in sorted_strats:
            lines.append(f"    {strat:<35} {cnt:>4}x")

    result = "\n".join(lines)
    if close_after:
        conn.close()
    return result


def get_coin_history(symbol: str, conn=None) -> str:
    """Historique detaille d'un coin specifique."""
    close_after = False
    if conn is None:
        conn = init_db()
        close_after = True

    coin = conn.execute("SELECT * FROM coins WHERE symbol = ?", (symbol,)).fetchone()
    if not coin:
        if close_after: conn.close()
        return f"  Coin {symbol} non trouve dans la DB"

    lines = [f"\n  === {symbol} ==="]
    lines.append(f"  Categorie: {coin[2]} | First: {coin[4][:10]} | Last: {coin[5][:10]}")
    lines.append(f"  Scans: {coin[6]} | Signaux: {coin[7]} | Avg: {coin[8]:.0f} | Max: {coin[9]}")
    lines.append(f"  Direction: {coin[10]} (L:{coin[11]} S:{coin[12]}) | Vol: {coin[13]:,.0f}")

    # Last 5 signals
    sigs = conn.execute("""
        SELECT cycle, timestamp, direction, score, last_price, regime, strategies
        FROM signals WHERE symbol = ? ORDER BY id DESC LIMIT 5
    """, (symbol,)).fetchall()
    if sigs:
        lines.append(f"\n  Derniers signaux:")
        for cy, ts, dir_, sc, price, regime, strats in sigs:
            n_strats = len(json.loads(strats)) if strats else 0
            lines.append(f"    C{cy} {ts[:16]} {dir_:<5} {sc}/100 {price:.6g} {regime} ({n_strats} strats)")

    result = "\n".join(lines)
    if close_after: conn.close()
    return result


# ========== GPU THERMAL ==========

GPU_TEMP_WARNING = 75
GPU_TEMP_CRITICAL = 85

def check_gpu_thermal() -> dict:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return {"status": "unavailable", "gpus": []}
        gpus = []
        max_temp = 0
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                temp = int(parts[2])
                max_temp = max(max_temp, temp)
                gpus.append({"index": int(parts[0]), "name": parts[1], "temp_c": temp,
                             "util_pct": int(parts[3]), "mem_used_mb": int(parts[4]),
                             "mem_total_mb": int(parts[5])})
        status = "critical" if max_temp >= GPU_TEMP_CRITICAL else "warning" if max_temp >= GPU_TEMP_WARNING else "ok"
        return {"status": status, "max_temp": max_temp, "gpus": gpus}
    except Exception:
        return {"status": "unavailable", "gpus": []}


# ========== GPU BATCH INDICATOR ENGINE ==========

class GpuBatchEngine:
    """Calcule TOUS les indicateurs de N coins simultanement sur GPU PyTorch.
    Tensor shape: [N_coins, T_candles] pour chaque serie (close, high, low, vol, open).
    Multi-GPU: coins repartis equitablement sur tous les GPU disponibles."""

    def __init__(self):
        self.device = PRIMARY_GPU if GPU_AVAILABLE else torch.device("cpu") if torch is not None else None

    def _to_tensor(self, data_list, device=None):
        """Convertit une liste de listes en tenseur GPU [N, T]."""
        if device is None:
            device = self.device
        max_len = max(len(d) for d in data_list) if data_list else 0
        padded = []
        for d in data_list:
            if len(d) < max_len:
                d = [d[0]] * (max_len - len(d)) + d
            padded.append(d)
        return torch.tensor(padded, dtype=torch.float32, device=device)

    def batch_ema(self, close, period):
        """EMA batch. close shape [N, T], retourne [N, T]."""
        alpha = 2.0 / (period + 1)
        result = torch.zeros_like(close)
        result[:, 0] = close[:, 0]
        for t in range(1, close.shape[1]):
            result[:, t] = alpha * close[:, t] + (1 - alpha) * result[:, t - 1]
        return result

    def batch_sma(self, close, period):
        """SMA batch via cumsum trick. [N, T] -> [N]."""
        if close.shape[1] < period:
            return close[:, -1]
        cs = close.cumsum(dim=1)
        sma = (cs[:, period - 1:] - torch.cat([torch.zeros(close.shape[0], 1, device=close.device), cs[:, :-period]], dim=1)) / period
        return sma[:, -1]

    def batch_rsi(self, close, period=14):
        """RSI batch. [N, T] -> [N]."""
        deltas = close[:, 1:] - close[:, :-1]
        gains = torch.clamp(deltas[:, -period:], min=0).mean(dim=1)
        losses = torch.clamp(-deltas[:, -period:], min=0).mean(dim=1)
        rs = gains / (losses + 1e-12)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def batch_atr(self, high, low, close, period=14):
        """ATR batch. [N, T] -> [N]."""
        tr1 = high[:, 1:] - low[:, 1:]
        tr2 = (high[:, 1:] - close[:, :-1]).abs()
        tr3 = (low[:, 1:] - close[:, :-1]).abs()
        tr = torch.max(torch.max(tr1, tr2), tr3)
        return tr[:, -period:].mean(dim=1)

    def batch_bollinger(self, close, period=20, mult=2.0):
        """Bollinger batch. [N, T] -> (upper[N], mid[N], lower[N], width[N])."""
        w = close[:, -period:]
        mid = w.mean(dim=1)
        std = w.std(dim=1)
        upper = mid + mult * std
        lower = mid - mult * std
        width = (upper - lower) / (mid + 1e-12) * 100
        return upper, mid, lower, width

    def batch_macd(self, close):
        """MACD batch. [N, T] -> (macd[N], signal[N], hist[N])."""
        ema12 = self.batch_ema(close, 12)
        ema26 = self.batch_ema(close, 26)
        macd_line = ema12 - ema26
        signal = self.batch_ema(macd_line[:, 26:], 9)
        macd_val = macd_line[:, -1]
        sig_val = signal[:, -1] if signal.shape[1] > 0 else torch.zeros(close.shape[0], device=close.device)
        hist = macd_val - sig_val
        return macd_val, sig_val, hist

    def batch_cmf(self, high, low, close, volume, period=20):
        """Chaikin Money Flow batch. [N, T] -> [N]."""
        hl = high - low
        mfm = torch.where(hl > 0, ((close - low) - (high - close)) / hl, torch.zeros_like(hl))
        mfv = mfm * volume
        cmf = mfv[:, -period:].sum(dim=1) / (volume[:, -period:].sum(dim=1) + 1e-12)
        return cmf

    def batch_obv(self, close, volume):
        """OBV batch. [N, T] -> [N, T]."""
        sign = torch.sign(close[:, 1:] - close[:, :-1])
        signed_vol = sign * volume[:, 1:]
        obv = torch.cumsum(signed_vol, dim=1)
        return torch.cat([torch.zeros(close.shape[0], 1, device=close.device), obv], dim=1)

    def batch_mfi(self, high, low, close, volume, period=14):
        """Money Flow Index batch. [N, T] -> [N]."""
        tp = (high + low + close) / 3
        tp_diff = tp[:, 1:] - tp[:, :-1]
        mf = tp[:, 1:] * volume[:, 1:]
        pos = torch.where(tp_diff > 0, mf, torch.zeros_like(mf))[:, -period:]
        neg = torch.where(tp_diff <= 0, mf, torch.zeros_like(mf))[:, -period:]
        pos_sum = pos.sum(dim=1)
        neg_sum = neg.sum(dim=1)
        ratio = pos_sum / (neg_sum + 1e-12)
        return 100.0 - (100.0 / (1.0 + ratio))

    def batch_williams_r(self, high, low, close, period=14):
        """Williams %R batch. [N, T] -> [N]."""
        hh = high[:, -period:].max(dim=1).values
        ll = low[:, -period:].min(dim=1).values
        wr = -100 * (hh - close[:, -1]) / (hh - ll + 1e-12)
        return wr

    def batch_adl(self, high, low, close, volume):
        """ADL batch. [N, T] -> [N, T]."""
        hl = high - low
        mfm = torch.where(hl > 0, ((close - low) - (high - close)) / hl, torch.zeros_like(hl))
        mfv = mfm * volume
        return torch.cumsum(mfv, dim=1)

    def batch_chaikin_osc(self, high, low, close, volume):
        """Chaikin Oscillator batch. [N, T] -> [N]."""
        adl = self.batch_adl(high, low, close, volume)
        ema3 = self.batch_ema(adl, 3)
        ema10 = self.batch_ema(adl, 10)
        return (ema3[:, -1] - ema10[:, -1])

    def compute_all(self, klines_dict):
        """Calcule TOUS les indicateurs pour N coins en batch GPU.
        klines_dict: {symbol: {"close": [...], "high": [...], "low": [...], "vol": [...], "open": [...]}}
        Retourne: {symbol: {rsi, atr, bb_width, macd_hist, cmf, mfi, williams_r, chaikin_osc, ...}}
        """
        if not klines_dict or self.device is None:
            return {}

        symbols = list(klines_dict.keys())
        n = len(symbols)
        if n == 0:
            return {}

        # Build tensors
        closes_list = [klines_dict[s]["close"] for s in symbols]
        highs_list = [klines_dict[s]["high"] for s in symbols]
        lows_list = [klines_dict[s]["low"] for s in symbols]
        vols_list = [klines_dict[s]["vol"] for s in symbols]
        opens_list = [klines_dict[s].get("open", klines_dict[s]["close"]) for s in symbols]

        # Multi-GPU: split across devices
        if GPU_AVAILABLE and GPU_COUNT > 1:
            return self._compute_multi_gpu(symbols, closes_list, highs_list, lows_list, vols_list, opens_list)

        # Single GPU/CPU
        close = self._to_tensor(closes_list)
        high = self._to_tensor(highs_list)
        low = self._to_tensor(lows_list)
        vol = self._to_tensor(vols_list)

        return self._compute_on_device(symbols, close, high, low, vol)

    def _compute_on_device(self, symbols, close, high, low, vol):
        """Compute all indicators on a single device."""
        n = len(symbols)
        results = {}

        with torch.no_grad():
            rsi = self.batch_rsi(close)
            atr = self.batch_atr(high, low, close)
            bb_up, bb_mid, bb_lo, bb_width = self.batch_bollinger(close)
            macd_val, macd_sig, macd_hist = self.batch_macd(close)
            cmf = self.batch_cmf(high, low, close, vol)
            mfi = self.batch_mfi(high, low, close, vol)
            wr = self.batch_williams_r(high, low, close)
            chaikin = self.batch_chaikin_osc(high, low, close, vol)
            obv = self.batch_obv(close, vol)
            sma20 = self.batch_sma(close, 20)
            sma50 = self.batch_sma(close, 50)

            # EMA ribbon
            ema8 = self.batch_ema(close, 8)[:, -1]
            ema13 = self.batch_ema(close, 13)[:, -1]
            ema21 = self.batch_ema(close, 21)[:, -1]
            ema55 = self.batch_ema(close, 55)[:, -1] if close.shape[1] >= 55 else sma50

            # Volume ratio
            avg_vol = vol[:, -20:].mean(dim=1)
            vol_ratio = vol[:, -1] / (avg_vol + 1e-12)

            # OBV trend (slope)
            if obv.shape[1] >= 20:
                obv_slope = (obv[:, -1] - obv[:, -20]) / (obv[:, -20].abs() + 1e-12)
            else:
                obv_slope = torch.zeros(n, device=close.device)

            # Price slope for divergence detection
            price_slope = (close[:, -1] - close[:, -20]) / (close[:, -20] + 1e-12) if close.shape[1] >= 20 else torch.zeros(n, device=close.device)

        # Convert to per-symbol dict
        for i, sym in enumerate(symbols):
            # OBV trend classification
            os_val = obv_slope[i].item()
            ps_val = price_slope[i].item()
            if os_val > 0.05 and ps_val < -0.01:
                obv_t = "bullish_divergence"
            elif os_val < -0.05 and ps_val > 0.01:
                obv_t = "bearish_divergence"
            elif os_val > 0.05:
                obv_t = "accumulation"
            elif os_val < -0.05:
                obv_t = "distribution"
            else:
                obv_t = "neutral"

            results[sym] = {
                "rsi": rsi[i].item(), "atr": atr[i].item(),
                "bb_up": bb_up[i].item(), "bb_mid": bb_mid[i].item(),
                "bb_lo": bb_lo[i].item(), "bb_width": bb_width[i].item(),
                "macd_val": macd_val[i].item(), "macd_sig": macd_sig[i].item(),
                "macd_hist": macd_hist[i].item(),
                "cmf": cmf[i].item(), "mfi": mfi[i].item(),
                "williams_r": wr[i].item(), "chaikin_osc": chaikin[i].item(),
                "obv_trend": obv_t, "obv_slope": os_val,
                "sma20": sma20[i].item(), "sma50": sma50[i].item(),
                "ema8": ema8[i].item(), "ema13": ema13[i].item(),
                "ema21": ema21[i].item(), "ema55": ema55[i].item(),
                "vol_ratio": vol_ratio[i].item(),
            }

        return results

    def _compute_multi_gpu(self, symbols, closes_list, highs_list, lows_list, vols_list, opens_list):
        """Distribute computation across all available GPUs."""
        n = len(symbols)
        chunk_size = max(1, n // GPU_COUNT)
        results = {}

        def compute_chunk(gpu_idx, start, end):
            device = GPU_DEVICES[gpu_idx]
            chunk_syms = symbols[start:end]
            close = self._to_tensor(closes_list[start:end], device)
            high = self._to_tensor(highs_list[start:end], device)
            low = self._to_tensor(lows_list[start:end], device)
            vol = self._to_tensor(vols_list[start:end], device)
            return self._compute_on_device(chunk_syms, close, high, low, vol)

        with ThreadPoolExecutor(max_workers=GPU_COUNT) as pool:
            futures = []
            for g in range(GPU_COUNT):
                start = g * chunk_size
                end = min(start + chunk_size, n) if g < GPU_COUNT - 1 else n
                if start < end:
                    futures.append(pool.submit(compute_chunk, g, start, end))
            for f in futures:
                results.update(f.result())

        return results


# GPU engine singleton
_gpu_engine = GpuBatchEngine() if torch is not None else None


# ========== FETCH ==========

async def fetch_json(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        r = await client.get(url, timeout=12)
        data = r.json()
        if data.get("success"):
            return data.get("data")
    except Exception:
        pass
    return None


async def get_all_tickers(client: httpx.AsyncClient) -> list[dict]:
    data = await fetch_json(client, f"{BASE}/ticker")
    if not data:
        return []
    usdt = [t for t in data if t["symbol"].endswith("_USDT") and t.get("amount24", 0) >= MIN_VOL_24H]
    usdt.sort(key=lambda t: t.get("amount24", 0), reverse=True)
    return usdt[:TOP_VOLUME]


async def get_klines(client, symbol, interval="Min15", limit=96):
    return await fetch_json(client, f"{BASE}/kline/{symbol}?interval={interval}&limit={limit}")


async def get_depth(client, symbol, limit=50):
    return await fetch_json(client, f"{BASE}/depth/{symbol}?limit={limit}")


async def get_open_interest(client, symbol):
    return await fetch_json(client, f"{BASE}/open_interest/{symbol}")


# ========== INDICATEURS CLASSIQUES ==========

def calc_sma(data, period):
    if len(data) < period:
        return data[-1] if data else 0
    return sum(data[-period:]) / period


def calc_ema(data, period):
    if not data:
        return []
    alpha = 2.0 / (period + 1)
    ema = [data[0]]
    for i in range(1, len(data)):
        ema.append(alpha * data[i] + (1 - alpha) * ema[-1])
    return ema


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0, diff))
        losses.append(max(0, -diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss < 1e-12:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def calc_stoch_rsi(closes, rsi_period=14, stoch_period=14):
    if len(closes) < rsi_period + stoch_period + 2:
        return 50.0
    rsi_values = []
    for i in range(stoch_period + 1):
        idx = len(closes) - stoch_period - 1 + i
        sub = closes[max(0, idx - rsi_period):idx + 1]
        rsi_values.append(calc_rsi(sub, rsi_period))
    mn, mx = min(rsi_values), max(rsi_values)
    if mx - mn < 0.01:
        return 50.0
    return (rsi_values[-1] - mn) / (mx - mn) * 100


def calc_macd(closes):
    if len(closes) < 35:
        return 0, 0, 0
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    macd_line = [ema12[i] - ema26[i] for i in range(len(closes))]
    sig = calc_ema(macd_line[26:], 9)
    if not sig:
        return 0, 0, 0
    return macd_line[-1], sig[-1], macd_line[-1] - sig[-1]


def calc_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return 0
    trs = []
    for i in range(-period, 0):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return sum(trs) / period


def calc_bollinger(closes, period=20, mult=2.0):
    if len(closes) < period:
        return 0, 0, 0, 0
    w = closes[-period:]
    mid = sum(w) / period
    std = math.sqrt(sum((x - mid) ** 2 for x in w) / period)
    up = mid + mult * std
    lo = mid - mult * std
    return up, mid, lo, (up - lo) / mid * 100 if mid > 0 else 0


def calc_vwap(closes, volumes, period=20):
    if len(closes) < period:
        return closes[-1] if closes else 0
    pv = sum(closes[-i] * volumes[-i] for i in range(1, period + 1))
    v = sum(volumes[-period:])
    return pv / v if v > 0 else closes[-1]


# ========== NOUVEAUX INDICATEURS AVANCES ==========

def calc_adl(highs, lows, closes, volumes):
    """Accumulation/Distribution Line — flux de capitaux."""
    adl = [0.0]
    for i in range(len(closes)):
        hl = highs[i] - lows[i]
        if hl > 0:
            mfm = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / hl
        else:
            mfm = 0
        mfv = mfm * volumes[i]
        adl.append(adl[-1] + mfv)
    return adl[1:]


def calc_chaikin_oscillator(highs, lows, closes, volumes):
    """Chaikin Oscillator = EMA(3, ADL) - EMA(10, ADL).
    Positif = accumulation (inflow), Negatif = distribution (outflow)."""
    adl = calc_adl(highs, lows, closes, volumes)
    if len(adl) < 10:
        return 0.0, adl
    ema3 = calc_ema(adl, 3)
    ema10 = calc_ema(adl, 10)
    return ema3[-1] - ema10[-1], adl


def calc_cmf(highs, lows, closes, volumes, period=20):
    """Chaikin Money Flow — pression achat/vente normalisee [-1, +1].
    >0 = inflow dominant, <0 = outflow dominant."""
    n = len(closes)
    if n < period:
        return 0.0
    mfv_sum = 0
    vol_sum = 0
    for i in range(n - period, n):
        hl = highs[i] - lows[i]
        if hl > 0:
            mfm = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / hl
        else:
            mfm = 0
        mfv_sum += mfm * volumes[i]
        vol_sum += volumes[i]
    return mfv_sum / vol_sum if vol_sum > 0 else 0.0


def calc_obv(closes, volumes):
    """On-Balance Volume — proxy inflow/outflow cumulatif."""
    obv = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    return obv


def calc_obv_trend(closes, volumes, period=20):
    """Tendance OBV: divergence prix vs OBV = signal fort."""
    obv = calc_obv(closes, volumes)
    if len(obv) < period:
        return "neutral", 0
    obv_slope = (obv[-1] - obv[-period]) / (abs(obv[-period]) + 1e-12)
    price_slope = (closes[-1] - closes[-period]) / (closes[-period] + 1e-12)
    if obv_slope > 0.05 and price_slope < -0.01:
        return "bullish_divergence", obv_slope
    elif obv_slope < -0.05 and price_slope > 0.01:
        return "bearish_divergence", obv_slope
    elif obv_slope > 0.05:
        return "accumulation", obv_slope
    elif obv_slope < -0.05:
        return "distribution", obv_slope
    return "neutral", obv_slope


def calc_mfi(highs, lows, closes, volumes, period=14):
    """Money Flow Index — RSI pondere par le volume [0-100].
    <20 = survendu, >80 = suracheté."""
    n = len(closes)
    if n < period + 1:
        return 50.0
    tp = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]
    pos_flow = 0
    neg_flow = 0
    for i in range(n - period, n):
        mf = tp[i] * volumes[i]
        if tp[i] > tp[i - 1]:
            pos_flow += mf
        else:
            neg_flow += mf
    if neg_flow < 1e-12:
        return 100.0 if pos_flow > 0 else 50.0
    ratio = pos_flow / neg_flow
    return 100.0 - (100.0 / (1.0 + ratio))


def calc_williams_r(highs, lows, closes, period=14):
    """Williams %R [-100, 0]. <-80 = survendu, >-20 = suracheté."""
    if len(closes) < period:
        return -50.0
    hh = max(highs[-period:])
    ll = min(lows[-period:])
    if hh == ll:
        return -50.0
    return -100 * (hh - closes[-1]) / (hh - ll)


def calc_adx(highs, lows, closes, period=14):
    """Average Directional Index — force de tendance [0-100].
    >25 = tendance forte, <20 = range."""
    n = len(closes)
    if n < period * 2:
        return 0.0
    plus_dm = []
    minus_dm = []
    tr_list = []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_list.append(tr)

    if len(tr_list) < period:
        return 0.0

    atr_val = sum(tr_list[:period]) / period
    plus_di_smooth = sum(plus_dm[:period]) / period
    minus_di_smooth = sum(minus_dm[:period]) / period

    alpha = 1.0 / period
    for i in range(period, len(tr_list)):
        atr_val = atr_val * (1 - alpha) + tr_list[i] * alpha
        plus_di_smooth = plus_di_smooth * (1 - alpha) + plus_dm[i] * alpha
        minus_di_smooth = minus_di_smooth * (1 - alpha) + minus_dm[i] * alpha

    if atr_val < 1e-12:
        return 0.0
    plus_di = 100 * plus_di_smooth / atr_val
    minus_di = 100 * minus_di_smooth / atr_val
    di_sum = plus_di + minus_di
    if di_sum < 1e-12:
        return 0.0
    dx = 100 * abs(plus_di - minus_di) / di_sum
    return dx


def calc_volume_profile_poc(closes, volumes, bins=20):
    """Volume Profile: Point of Control (prix avec le plus de volume echange).
    Retourne (poc_price, concentration_pct)."""
    if not closes or not volumes:
        return 0, 0
    mn, mx = min(closes), max(closes)
    if mx == mn:
        return closes[-1], 100
    bin_size = (mx - mn) / bins
    vol_bins = [0.0] * bins
    for i in range(len(closes)):
        idx = min(int((closes[i] - mn) / bin_size), bins - 1)
        vol_bins[idx] += volumes[i]
    max_idx = vol_bins.index(max(vol_bins))
    poc = mn + (max_idx + 0.5) * bin_size
    total_vol = sum(vol_bins)
    concentration = vol_bins[max_idx] / total_vol * 100 if total_vol > 0 else 0
    return poc, concentration


# ========== ORDERBOOK ULTRA-DETAILLE ==========

def analyze_depth_ultra(depth_data: dict, last_price: float) -> dict:
    """Analyse minutieuse du carnet d'ordres: gradient, absorption,
    spoofing, voids, clusters, heatmap, spread."""
    default = {"bias": "neutral", "clusters": [], "reasons": [], "imbalance": 0,
               "spread_pct": 0, "gradient_score": 0, "absorption": "none",
               "spoofing_risk": False, "void_zones": [], "ob_score": 0}
    if not depth_data:
        return default

    bids = depth_data.get("bids", [])
    asks = depth_data.get("asks", [])
    if not bids or not asks:
        return default

    bid_vol = sum(b[1] for b in bids)
    ask_vol = sum(a[1] for a in asks)
    total = bid_vol + ask_vol
    reasons = []
    clusters = []
    ob_score = 0

    # --- 1. Imbalance global ---
    imbalance = (bid_vol - ask_vol) / total if total > 0 else 0

    if total > 0:
        bid_pct = bid_vol / total
        if bid_pct > 0.70:
            bias = "strong_bullish"
            reasons.append(f"Imbalance OB tres forte achat {bid_pct:.0%}")
            ob_score += 15
        elif bid_pct > 0.60:
            bias = "bullish"
            reasons.append(f"Pression acheteuse {bid_pct:.0%}")
            ob_score += 8
        elif bid_pct < 0.30:
            bias = "strong_bearish"
            reasons.append(f"Imbalance OB tres forte vente {1-bid_pct:.0%}")
            ob_score += 15
        elif bid_pct < 0.40:
            bias = "bearish"
            reasons.append(f"Pression vendeuse {1-bid_pct:.0%}")
            ob_score += 8
        else:
            bias = "neutral"
    else:
        bias = "neutral"

    # --- 2. Spread analysis ---
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    spread = best_ask - best_bid
    spread_pct = spread / last_price * 100 if last_price > 0 else 0
    if spread_pct < 0.02:
        reasons.append(f"Spread ultra-serré ({spread_pct:.4f}%) — liquidite haute")
        ob_score += 5
    elif spread_pct > 0.1:
        reasons.append(f"Spread large ({spread_pct:.3f}%) — liquidite faible")
        ob_score -= 3

    # --- 3. Gradient de liquidite (distribution par niveaux) ---
    # Bid gradient: compare top 5 vs bottom 5 niveaux
    bid_top5 = sum(b[1] for b in bids[:5]) if len(bids) >= 5 else bid_vol
    bid_bot5 = sum(b[1] for b in bids[-5:]) if len(bids) >= 10 else 0
    ask_top5 = sum(a[1] for a in asks[:5]) if len(asks) >= 5 else ask_vol
    ask_bot5 = sum(a[1] for a in asks[-5:]) if len(asks) >= 10 else 0

    # Front-loaded bids = support fort immédiat
    gradient_score = 0
    if bid_vol > 0 and bid_top5 > bid_vol * 0.5:
        gradient_score += 2
        reasons.append(f"Bids concentres pres du prix ({bid_top5/bid_vol:.0%} dans top 5)")
    if ask_vol > 0 and ask_top5 > ask_vol * 0.5:
        gradient_score -= 2
        reasons.append(f"Asks concentres pres du prix ({ask_top5/ask_vol:.0%} dans top 5)")

    # --- 4. Detection murs (walls) + clusters ---
    avg_bid_size = bid_vol / len(bids) if bids else 0
    avg_ask_size = ask_vol / len(asks) if asks else 0

    for b in bids[:20]:
        price, vol = b[0], b[1]
        if avg_bid_size > 0 and vol > avg_bid_size * 4:
            pct = (last_price - price) / last_price * 100
            clusters.append({"side": "bid", "price": price, "volume": vol,
                             "pct_away": round(pct, 2), "type": "wall"})
            reasons.append(f"MUR BID {price:.6g} ({vol:,.0f} lots, -{pct:.2f}%) — 4x moyenne")
            ob_score += 5

    for a in asks[:20]:
        price, vol = a[0], a[1]
        if avg_ask_size > 0 and vol > avg_ask_size * 4:
            pct = (price - last_price) / last_price * 100
            clusters.append({"side": "ask", "price": price, "volume": vol,
                             "pct_away": round(pct, 2), "type": "wall"})
            reasons.append(f"MUR ASK {price:.6g} ({vol:,.0f} lots, +{pct:.2f}%) — 4x moyenne")
            ob_score += 5

    # --- 5. Detection absorption (gros volume pres du prix qui "absorbe") ---
    absorption = "none"
    if bids and avg_bid_size > 0:
        top3_bid_vol = sum(b[1] for b in bids[:3])
        if top3_bid_vol > bid_vol * 0.40:
            absorption = "bid_absorption"
            reasons.append(f"Absorption BID: top 3 = {top3_bid_vol/bid_vol:.0%} du total (buyers absorbent)")
            ob_score += 8
    if asks and avg_ask_size > 0:
        top3_ask_vol = sum(a[1] for a in asks[:3])
        if top3_ask_vol > ask_vol * 0.40:
            if absorption == "bid_absorption":
                absorption = "both"
            else:
                absorption = "ask_absorption"
            reasons.append(f"Absorption ASK: top 3 = {top3_ask_vol/ask_vol:.0%} du total (sellers absorbent)")
            ob_score += 8

    # --- 6. Detection spoofing (ordres suspects: tres gros, tres loin) ---
    spoofing_risk = False
    for b in bids[10:]:
        if avg_bid_size > 0 and b[1] > avg_bid_size * 8:
            pct = (last_price - b[0]) / last_price * 100
            if pct > 1.0:
                spoofing_risk = True
                reasons.append(f"SPOOFING suspect: bid {b[0]:.6g} ({b[1]:,.0f}x, -{pct:.1f}%) — 8x moyenne, loin du prix")
                break
    for a in asks[10:]:
        if avg_ask_size > 0 and a[1] > avg_ask_size * 8:
            pct = (a[0] - last_price) / last_price * 100
            if pct > 1.0:
                spoofing_risk = True
                reasons.append(f"SPOOFING suspect: ask {a[0]:.6g} ({a[1]:,.0f}x, +{pct:.1f}%) — 8x moyenne, loin du prix")
                break

    # --- 7. Detection voids (zones sans liquidite = gaps exploitables) ---
    void_zones = []
    for i in range(1, min(15, len(bids))):
        gap_pct = (bids[i - 1][0] - bids[i][0]) / last_price * 100
        if gap_pct > 0.1:
            void_zones.append({"side": "bid", "from": bids[i][0], "to": bids[i - 1][0],
                                "gap_pct": round(gap_pct, 3)})
    for i in range(1, min(15, len(asks))):
        gap_pct = (asks[i][0] - asks[i - 1][0]) / last_price * 100
        if gap_pct > 0.1:
            void_zones.append({"side": "ask", "from": asks[i - 1][0], "to": asks[i][0],
                                "gap_pct": round(gap_pct, 3)})
    if void_zones:
        biggest = max(void_zones, key=lambda v: v["gap_pct"])
        reasons.append(f"VOID {biggest['side'].upper()} {biggest['from']:.6g}->{biggest['to']:.6g} ({biggest['gap_pct']:.3f}%)")
        ob_score += 3

    # --- 8. Bid/Ask depth at 0.5%, 1%, 2% ---
    depth_levels = {}
    for pct_level in [0.5, 1.0, 2.0]:
        bid_at = sum(b[1] for b in bids if b[0] >= last_price * (1 - pct_level / 100))
        ask_at = sum(a[1] for a in asks if a[0] <= last_price * (1 + pct_level / 100))
        depth_levels[pct_level] = {"bid": bid_at, "ask": ask_at}
        ratio = bid_at / (ask_at + 1e-12)
        if ratio > 2.0:
            reasons.append(f"Depth {pct_level}%: bids {ratio:.1f}x les asks (fort support)")
            ob_score += 4
        elif 0 < ratio < 0.5:
            reasons.append(f"Depth {pct_level}%: asks {1/ratio:.1f}x les bids (forte resistance)")
            ob_score += 4

    return {
        "bias": bias, "clusters": clusters, "reasons": reasons,
        "imbalance": imbalance, "spread_pct": spread_pct,
        "gradient_score": gradient_score, "absorption": absorption,
        "spoofing_risk": spoofing_risk, "void_zones": void_zones[:3],
        "ob_score": ob_score, "depth_levels": depth_levels,
    }


# ========== 30+ STRATEGIES PRE-PUMP ==========

def analyze_klines_advanced(kdata: dict) -> dict:
    """30+ strategies de detection pre-pump avec indicateurs avances."""
    empty = {"strategies": [], "reasons": [], "score": 0, "trend": "unknown",
             "rsi": 50, "atr": 0, "macd_signal": "", "bb_squeeze": False,
             "chaikin_osc": 0, "cmf": 0, "obv_trend": "neutral", "mfi": 50,
             "williams_r": -50, "adx": 0, "poc": 0, "poc_conc": 0}
    if not kdata or "close" not in kdata:
        return empty

    closes = kdata["close"]
    highs = kdata["high"]
    lows = kdata["low"]
    volumes = kdata["vol"]
    opens = kdata.get("open", closes)
    n = len(closes)
    if n < 30:
        return empty

    strategies = []
    reasons = []
    scores = []
    last = closes[-1]
    prev = closes[-2]

    # ===== Indicateurs classiques =====
    sma20 = calc_sma(closes, 20)
    sma50 = calc_sma(closes, 50)
    rsi = calc_rsi(closes, 14)
    stoch_rsi = calc_stoch_rsi(closes)
    macd_val, macd_sig, macd_hist = calc_macd(closes)
    atr = calc_atr(highs, lows, closes, 14)
    bb_up, bb_mid, bb_low, bb_width = calc_bollinger(closes)
    vwap = calc_vwap(closes, volumes)
    avg_vol = sum(volumes[-20:]) / 20
    last_vol = volumes[-1]
    vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1

    ema8 = calc_ema(closes, 8)[-1]
    ema13 = calc_ema(closes, 13)[-1]
    ema21 = calc_ema(closes, 21)[-1]
    ema55 = calc_ema(closes, 55)[-1] if n >= 55 else sma50

    # ===== Nouveaux indicateurs avances =====
    chaikin_osc, adl = calc_chaikin_oscillator(highs, lows, closes, volumes)
    cmf = calc_cmf(highs, lows, closes, volumes, 20)
    obv_trend, obv_slope = calc_obv_trend(closes, volumes, 20)
    mfi = calc_mfi(highs, lows, closes, volumes, 14)
    williams_r = calc_williams_r(highs, lows, closes, 14)
    adx = calc_adx(highs, lows, closes, 14)
    poc, poc_conc = calc_volume_profile_poc(closes[-50:], volumes[-50:], 25)

    # Trend
    if last > sma20 > sma50:
        trend = "bullish"
    elif last < sma20 < sma50:
        trend = "bearish"
    elif last > sma20:
        trend = "recovery"
    else:
        trend = "range"

    # ==========================================
    #   STRATEGIES 1-18 (existantes)
    # ==========================================

    r20_high = max(highs[-20:])
    r20_low = min(lows[-20:])

    # 1. Breakout resistance
    if last > r20_high * 0.998 and vol_ratio > 1.3:
        strategies.append("breakout_resistance")
        reasons.append(f"Casse resistance 20P ({r20_high:.6g}) vol x{vol_ratio:.1f}")
        scores.append(20)

    # 2. Breakout support
    if last < r20_low * 1.002 and vol_ratio > 1.3:
        strategies.append("breakout_support")
        reasons.append(f"Casse support 20P ({r20_low:.6g}) vol x{vol_ratio:.1f}")
        scores.append(20)

    # 3. Volume spike
    if vol_ratio > 2.0:
        strategies.append("volume_spike")
        reasons.append(f"Volume spike x{vol_ratio:.1f}")
        scores.append(min(20, int(vol_ratio * 5)))

    # 4. Volume dry-up -> expansion
    if n >= 15:
        recent_avg = sum(volumes[-5:]) / 5
        older_avg = sum(volumes[-15:-5]) / 10
        if older_avg > 0 and recent_avg < older_avg * 0.4 and last_vol > recent_avg * 2:
            strategies.append("volume_dryup_expansion")
            reasons.append("Volume dry-up -> expansion (accumulation)")
            scores.append(18)

    # 5. RSI survendu
    if rsi < 30:
        strategies.append("rsi_oversold")
        reasons.append(f"RSI survendu ({rsi:.0f})")
        scores.append(15)

    # 6. Stoch RSI
    if stoch_rsi < 20:
        strategies.append("stoch_rsi_oversold")
        reasons.append(f"StochRSI survendu ({stoch_rsi:.0f})")
        scores.append(12)
    elif stoch_rsi > 80:
        strategies.append("stoch_rsi_overbought")
        reasons.append(f"StochRSI suracheté ({stoch_rsi:.0f})")
        scores.append(8)

    # 7-8. MACD cross
    if macd_hist > 0 and n >= 36:
        prev_macd = calc_macd(closes[:-1])
        if prev_macd[2] <= 0:
            strategies.append("macd_bullish_cross")
            reasons.append("MACD cross haussier")
            scores.append(15)
    if macd_hist < 0 and n >= 36:
        prev_macd = calc_macd(closes[:-1])
        if prev_macd[2] >= 0:
            strategies.append("macd_bearish_cross")
            reasons.append("MACD cross baissier")
            scores.append(12)

    # 9. Bollinger squeeze
    bb_squeeze = False
    if n >= 40:
        prev_bb = calc_bollinger(closes[:-5])
        if prev_bb[3] > 0 and bb_width < prev_bb[3] * 0.6:
            bb_squeeze = True
            strategies.append("bollinger_squeeze")
            reasons.append(f"Bollinger squeeze ({bb_width:.2f}% < {prev_bb[3]:.2f}%)")
            scores.append(15)

    # 10. Bollinger bounce
    if last < bb_low * 1.005 and trend != "bearish":
        strategies.append("bollinger_bounce_low")
        reasons.append(f"Touche bande basse BB ({bb_low:.6g})")
        scores.append(12)

    # 11. EMA ribbon
    if ema8 > ema13 > ema21 > ema55:
        strategies.append("ema_ribbon_bullish")
        reasons.append("EMA ribbon haussier (8>13>21>55)")
        scores.append(12)
    elif ema8 < ema13 < ema21 < ema55:
        strategies.append("ema_ribbon_bearish")
        reasons.append("EMA ribbon baissier")
        scores.append(10)

    # 12. EMA55 cross
    if n >= 56:
        prev_ema55 = calc_ema(closes[:-1], 55)[-1]
        if prev < prev_ema55 and last > ema55:
            strategies.append("ema55_cross_up")
            reasons.append(f"Cross EMA55 haussier ({ema55:.6g})")
            scores.append(18)

    # 13. VWAP position
    if last > vwap * 1.005 and trend in ("bullish", "recovery"):
        strategies.append("above_vwap")
        reasons.append(f"Au-dessus VWAP ({vwap:.6g})")
        scores.append(8)

    # 14-15. Candlestick patterns
    if n >= 3:
        body_last = abs(closes[-1] - opens[-1])
        wick_low = min(closes[-1], opens[-1]) - lows[-1]
        wick_high = highs[-1] - max(closes[-1], opens[-1])
        if wick_low > body_last * 2.5 and body_last > 0:
            strategies.append("hammer")
            reasons.append("Hammer (longue meche basse)")
            scores.append(12 if trend == "bearish" else 6)
        if wick_high > body_last * 2.5 and body_last > 0:
            strategies.append("shooting_star")
            reasons.append("Shooting star (longue meche haute)")
            scores.append(10 if trend == "bullish" else 5)

        # Engulfing
        body_prev = abs(closes[-2] - opens[-2])
        if closes[-1] > opens[-1] and closes[-2] < opens[-2] and body_last > body_prev * 1.3:
            strategies.append("bullish_engulfing")
            reasons.append("Engulfing haussier")
            scores.append(14)
        elif closes[-1] < opens[-1] and closes[-2] > opens[-2] and body_last > body_prev * 1.3:
            strategies.append("bearish_engulfing")
            reasons.append("Engulfing baissier")
            scores.append(12)

    # 16. Range compression
    if n >= 20:
        recent_range = max(highs[-5:]) - min(lows[-5:])
        older_range = max(highs[-20:-5]) - min(lows[-20:-5])
        if older_range > 0 and recent_range < older_range * 0.35:
            strategies.append("range_compression")
            reasons.append(f"Compression extreme ({recent_range/older_range:.0%} du range)")
            scores.append(15)

    # 17. Momentum acceleration
    if n >= 10:
        mom_5 = (closes[-1] - closes[-5]) / closes[-5] * 100
        mom_10 = (closes[-5] - closes[-10]) / closes[-10] * 100
        if mom_5 > 0 and mom_5 > mom_10 * 2 and mom_5 > 1.0:
            strategies.append("momentum_acceleration")
            reasons.append(f"Acceleration momentum ({mom_5:+.2f}% vs {mom_10:+.2f}%)")
            scores.append(12)

    # ==========================================
    #   STRATEGIES 19-30+ (NOUVELLES)
    # ==========================================

    # 19. Chaikin Oscillator — flux de capitaux
    if chaikin_osc > 0 and len(adl) >= 5:
        prev_co = calc_ema(adl[:-1], 3)[-1] - calc_ema(adl[:-1], 10)[-1] if len(adl) > 10 else 0
        if prev_co <= 0:
            strategies.append("chaikin_bullish_cross")
            reasons.append(f"Chaikin Oscillator cross haussier (inflow detecte, CO={chaikin_osc:+.0f})")
            scores.append(14)
    elif chaikin_osc < 0 and len(adl) >= 5:
        prev_co = calc_ema(adl[:-1], 3)[-1] - calc_ema(adl[:-1], 10)[-1] if len(adl) > 10 else 0
        if prev_co >= 0:
            strategies.append("chaikin_bearish_cross")
            reasons.append(f"Chaikin Oscillator cross baissier (outflow, CO={chaikin_osc:+.0f})")
            scores.append(10)

    # 20. Chaikin Money Flow — pression directionnelle
    if cmf > 0.15:
        strategies.append("cmf_strong_inflow")
        reasons.append(f"CMF fort inflow ({cmf:+.2f}) — acheteurs dominants")
        scores.append(12)
    elif cmf < -0.15:
        strategies.append("cmf_strong_outflow")
        reasons.append(f"CMF fort outflow ({cmf:+.2f}) — vendeurs dominants")
        scores.append(10)

    # 21. CMF divergence (prix baisse mais CMF monte = accumulation cachee)
    if n >= 10:
        price_down = closes[-1] < closes[-10]
        if price_down and cmf > 0.05:
            strategies.append("cmf_bullish_divergence")
            reasons.append(f"DIVERGENCE CMF: prix baisse mais inflow positif ({cmf:+.2f}) — accumulation cachee")
            scores.append(18)
        price_up = closes[-1] > closes[-10]
        if price_up and cmf < -0.05:
            strategies.append("cmf_bearish_divergence")
            reasons.append(f"DIVERGENCE CMF: prix monte mais outflow ({cmf:+.2f}) — distribution cachee")
            scores.append(15)

    # 22. OBV trend — proxy inflow/outflow
    if obv_trend == "bullish_divergence":
        strategies.append("obv_bullish_divergence")
        reasons.append(f"OBV divergence haussiere: volume entre (inflow) malgre prix en baisse")
        scores.append(18)
    elif obv_trend == "bearish_divergence":
        strategies.append("obv_bearish_divergence")
        reasons.append(f"OBV divergence baissiere: volume sort (outflow) malgre prix en hausse")
        scores.append(15)
    elif obv_trend == "accumulation":
        strategies.append("obv_accumulation")
        reasons.append(f"OBV accumulation: inflow cumulatif en hausse")
        scores.append(8)

    # 23. MFI (Money Flow Index) — RSI pondere volume
    if mfi < 20:
        strategies.append("mfi_oversold")
        reasons.append(f"MFI survendu ({mfi:.0f}) — money flow a sec, rebond probable")
        scores.append(15)
    elif mfi > 80:
        strategies.append("mfi_overbought")
        reasons.append(f"MFI suracheté ({mfi:.0f}) — exces de capitaux")
        scores.append(8)

    # 24. MFI divergence
    if n >= 15:
        mfi_prev = calc_mfi(highs[:-5], lows[:-5], closes[:-5], volumes[:-5], 14)
        if mfi > mfi_prev + 10 and closes[-1] < closes[-6]:
            strategies.append("mfi_bullish_divergence")
            reasons.append(f"DIVERGENCE MFI: flux monte ({mfi_prev:.0f}->{mfi:.0f}) mais prix baisse")
            scores.append(14)

    # 25. Williams %R
    if williams_r < -80:
        strategies.append("williams_oversold")
        reasons.append(f"Williams %R survendu ({williams_r:.0f})")
        scores.append(10)
    elif williams_r > -20:
        strategies.append("williams_overbought")
        reasons.append(f"Williams %R suracheté ({williams_r:.0f})")
        scores.append(6)

    # 26. ADX — force de la tendance
    if adx > 30:
        strategies.append("adx_strong_trend")
        reasons.append(f"ADX fort ({adx:.0f}) — tendance puissante confirmee")
        scores.append(10)
    elif adx < 15:
        strategies.append("adx_no_trend")
        reasons.append(f"ADX faible ({adx:.0f}) — range, breakout imminent possible")
        scores.append(5)

    # 27. ADX + direction
    if adx > 25 and trend == "bullish":
        strategies.append("adx_bullish_trend")
        reasons.append(f"Tendance haussiere confirmee ADX={adx:.0f}")
        scores.append(8)

    # 28. Volume Profile — POC
    if poc > 0:
        poc_dist = abs(last - poc) / last * 100
        if poc_dist < 0.5:
            strategies.append("near_poc")
            reasons.append(f"Prix pres du POC ({poc:.6g}, {poc_dist:.2f}%) — zone haute activite")
            scores.append(6)
        elif last > poc and trend in ("bullish", "recovery"):
            strategies.append("above_poc")
            reasons.append(f"Prix au-dessus POC ({poc:.6g}) — support volume")
            scores.append(5)

    # 29. Accumulation/Distribution Line trend
    if len(adl) >= 10:
        adl_slope = (adl[-1] - adl[-10]) / (abs(adl[-10]) + 1e-12)
        if adl_slope > 0.1 and trend != "bullish":
            strategies.append("adl_hidden_accumulation")
            reasons.append(f"ADL en hausse ({adl_slope:+.2f}) malgre prix stagnant — accumulation discrete")
            scores.append(12)

    # 30. Triple confirmation (RSI + MFI + Williams allignes survendu)
    if rsi < 35 and mfi < 30 and williams_r < -75:
        strategies.append("triple_oversold")
        reasons.append(f"TRIPLE survendu: RSI={rsi:.0f} MFI={mfi:.0f} W%R={williams_r:.0f}")
        scores.append(20)

    # 31. Smart Money: CMF + OBV + Chaikin alignes
    if cmf > 0.1 and obv_trend in ("accumulation", "bullish_divergence") and chaikin_osc > 0:
        strategies.append("smart_money_inflow")
        reasons.append(f"SMART MONEY: CMF({cmf:+.2f}) + OBV({obv_trend}) + Chaikin(+) alignes -> inflow massif")
        scores.append(20)

    macd_signal = "bullish" if macd_hist > 0 else "bearish" if macd_hist < 0 else "neutral"

    return {
        "strategies": strategies, "reasons": reasons,
        "score": min(100, sum(scores)), "trend": trend,
        "rsi": rsi, "atr": atr, "macd_signal": macd_signal,
        "bb_squeeze": bb_squeeze, "chaikin_osc": chaikin_osc,
        "cmf": cmf, "obv_trend": obv_trend, "mfi": mfi,
        "williams_r": williams_r, "adx": adx, "poc": poc, "poc_conc": poc_conc,
    }


# ========== ANALYSE COMPLETE ==========

async def analyze_pair(client: httpx.AsyncClient, ticker: dict,
                       gpu_indicators: dict = None, klines_cache: dict = None) -> Signal | None:
    symbol = ticker["symbol"]

    # Si klines pre-fetched (mode GPU batch), utiliser le cache
    if klines_cache and symbol in klines_cache:
        klines_data = klines_cache[symbol]
    else:
        klines_data = await get_klines(client, symbol, "Min15", 96)

    depth_data = await get_depth(client, symbol, 50)

    kline = analyze_klines_advanced(klines_data)
    last_price = ticker["lastPrice"]
    depth = analyze_depth_ultra(depth_data, last_price)

    # Override indicateurs avec calcul GPU batch si disponible
    if gpu_indicators and symbol in gpu_indicators:
        gi = gpu_indicators[symbol]
        kline["rsi"] = gi["rsi"]
        kline["atr"] = gi["atr"]
        kline["cmf"] = gi["cmf"]
        kline["mfi"] = gi["mfi"]
        kline["williams_r"] = gi["williams_r"]
        kline["chaikin_osc"] = gi["chaikin_osc"]
        kline["obv_trend"] = gi["obv_trend"]
        if gi["macd_hist"] > 0:
            kline["macd_signal"] = "bullish"
        elif gi["macd_hist"] < 0:
            kline["macd_signal"] = "bearish"
        else:
            kline["macd_signal"] = "neutral"

    all_strategies = list(kline["strategies"])
    all_reasons = list(kline["reasons"]) + depth["reasons"]
    score = kline["score"] + depth["ob_score"]

    # Bonus convergence liquidite + tendance
    if depth["bias"] in ("bullish", "strong_bullish") and kline["trend"] in ("bullish", "recovery"):
        score += 10
        all_strategies.append("liquidity_convergence_long")
        all_reasons.append("Liquidite + tendance convergent LONG")
    elif depth["bias"] in ("bearish", "strong_bearish") and kline["trend"] == "bearish":
        score += 10
        all_strategies.append("liquidity_convergence_short")
        all_reasons.append("Liquidite + tendance convergent SHORT")

    # Extreme imbalance
    if abs(depth["imbalance"]) > 0.4:
        score += 8
        side = "bid" if depth["imbalance"] > 0 else "ask"
        all_strategies.append(f"extreme_imbalance_{side}")
        all_reasons.append(f"Desequilibre extreme carnet ({depth['imbalance']:+.0%})")

    # Absorption detection
    if depth["absorption"] == "bid_absorption" and kline["trend"] != "bearish":
        score += 6
        all_strategies.append("bid_absorption")
        all_reasons.append("Absorption acheteuse detectee (buyers accumulent)")

    # Funding rate
    funding = ticker.get("fundingRate", 0)
    if funding < -0.0005 and kline["trend"] != "bearish":
        score += 8
        all_strategies.append("negative_funding")
        all_reasons.append(f"Funding negatif ({funding:.6f}) — shorts paieront")
    elif funding > 0.001 and kline["trend"] != "bullish":
        score += 6
        all_strategies.append("high_funding")
        all_reasons.append(f"Funding eleve ({funding:.6f}) — longs paieront")

    if score < MIN_SCORE or not all_strategies:
        return None

    # Direction
    long_kw = ["bullish", "oversold", "bounce_low", "resistance", "cross_up",
               "hammer", "acceleration", "dryup", "spike", "convergence_long",
               "negative_funding", "above_vwap", "above_poc", "inflow", "accumulation",
               "bid_absorption", "smart_money"]
    short_kw = ["bearish", "overbought", "bounce_high", "support", "cross_down",
                "shooting_star", "convergence_short", "high_funding", "outflow", "distribution"]

    long_c = sum(1 for s in all_strategies if any(x in s for x in long_kw))
    short_c = sum(1 for s in all_strategies if any(x in s for x in short_kw))

    direction = "LONG" if long_c > short_c else "SHORT" if short_c > long_c else (
        "LONG" if ticker.get("riseFallRate", 0) > 0 else "SHORT")

    # Entry / TP / SL dynamiques ATR
    atr = kline["atr"]
    dec = _price_decimals(last_price)
    if atr > 0:
        if direction == "LONG":
            entry = round(last_price - atr * 0.3, dec)
            tp = round(entry + atr * TP_MULT, dec)
            sl = round(entry - atr * SL_MULT, dec)
        else:
            entry = round(last_price + atr * 0.3, dec)
            tp = round(entry - atr * TP_MULT, dec)
            sl = round(entry + atr * SL_MULT, dec)
    else:
        pct_e, pct_t, pct_s = 0.001, 0.004, 0.0025
        if direction == "LONG":
            entry = round(last_price * (1 - pct_e), dec)
            tp = round(entry * (1 + pct_t), dec)
            sl = round(entry * (1 - pct_s), dec)
        else:
            entry = round(last_price * (1 + pct_e), dec)
            tp = round(entry * (1 - pct_t), dec)
            sl = round(entry * (1 + pct_s), dec)

    regime = ("strong_signal" if score >= 70 else "squeeze" if kline["bb_squeeze"]
              else "trending" if kline["trend"] in ("bullish", "bearish") else "ranging")

    return Signal(
        symbol=symbol, direction=direction, score=min(100, score),
        last_price=last_price, entry=entry, tp=tp, sl=sl,
        strategies=all_strategies, reasons=all_reasons,
        volume_24h=ticker.get("amount24", 0),
        change_24h=ticker.get("riseFallRate", 0) * 100,
        funding_rate=funding, liquidity_bias=depth["bias"],
        liquidity_clusters=depth["clusters"][:5],
        ob_analysis={"spread_pct": depth["spread_pct"],
                     "absorption": depth["absorption"],
                     "spoofing_risk": depth["spoofing_risk"],
                     "gradient": depth["gradient_score"],
                     "voids": len(depth["void_zones"])},
        atr=atr, rsi=kline["rsi"], chaikin_osc=kline["chaikin_osc"],
        cmf=kline["cmf"], obv_trend=kline["obv_trend"],
        mfi=kline["mfi"], williams_r=kline["williams_r"],
        adx=kline["adx"], macd_signal=kline["macd_signal"],
        bb_squeeze=kline["bb_squeeze"], regime=regime,
    )


def _price_decimals(price):
    if price > 1000: return 1
    elif price > 10: return 2
    elif price > 1: return 3
    elif price > 0.01: return 5
    elif price > 0.0001: return 7
    else: return 10


# ========== SCAN ==========

async def fetch_all_klines(client, tickers, batch_size=40):
    """Fetch toutes les klines en parallele haute cadence."""
    klines_cache = {}
    symbols = [t["symbol"] for t in tickers]
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        tasks = [get_klines(client, s, "Min15", 96) for s in batch]
        results = await asyncio.gather(*tasks)
        for sym, data in zip(batch, results):
            if data:
                klines_cache[sym] = data
        if i + batch_size < len(symbols):
            await asyncio.sleep(0.15)
    return klines_cache


async def scan_sniper(top_n=3, min_score=MIN_SCORE, use_gpu=True):
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=50, max_keepalive_connections=30)) as client:
        gpu_label = f"PyTorch {GPU_COUNT}xGPU" if GPU_AVAILABLE and use_gpu else "CPU"
        print(f"[1/4] Recuperation tickers MEXC Futures...", file=sys.stderr)
        tickers = await get_all_tickers(client)
        if not tickers:
            print("Erreur: aucun ticker MEXC", file=sys.stderr)
            return []
        print(f"[1/4] {len(tickers)} coins (vol > {MIN_VOL_24H:,} USDT)", file=sys.stderr)

        # Phase 2: Fetch toutes les klines en parallele (haute concurrence)
        t_fetch = time.time()
        print(f"[2/4] Fetch klines batch (concurrence x50)...", file=sys.stderr)
        klines_cache = await fetch_all_klines(client, tickers, batch_size=40)
        fetch_ms = int((time.time() - t_fetch) * 1000)
        print(f"[2/4] {len(klines_cache)} klines recuperees ({fetch_ms}ms)", file=sys.stderr)

        # Phase 3: GPU batch indicators
        gpu_indicators = {}
        gpu_ms = 0
        if GPU_AVAILABLE and use_gpu and _gpu_engine and klines_cache:
            t_gpu = time.time()
            # Build format pour GPU engine
            gpu_klines = {}
            for sym, kdata in klines_cache.items():
                if kdata and "close" in kdata and len(kdata["close"]) >= 30:
                    gpu_klines[sym] = kdata
            if gpu_klines:
                print(f"[3/4] GPU batch {len(gpu_klines)} coins sur {GPU_COUNT} GPU...", file=sys.stderr)
                gpu_indicators = _gpu_engine.compute_all(gpu_klines)
                gpu_ms = int((time.time() - t_gpu) * 1000)
                print(f"[3/4] GPU batch: {len(gpu_indicators)} coins en {gpu_ms}ms ({gpu_label})", file=sys.stderr)
        else:
            print(f"[3/4] GPU: desactive, mode CPU", file=sys.stderr)

        # Phase 4: Strategies + Orderbook (async)
        print(f"[4/4] Strategies 31 + orderbook ultra...", file=sys.stderr)
        all_signals = []
        batch_size = 30
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            tasks = [analyze_pair(client, t, gpu_indicators=gpu_indicators, klines_cache=klines_cache) for t in batch]
            results = await asyncio.gather(*tasks)
            for s in results:
                if s is not None and s.score >= min_score:
                    all_signals.append(s)
            if i + batch_size < len(tickers):
                await asyncio.sleep(0.1)

        all_signals.sort(key=lambda s: s.score, reverse=True)
        total_strats = sum(len(s.strategies) for s in all_signals)
        print(f"[4/4] {len(all_signals)} signaux ({total_strats} triggers) | fetch {fetch_ms}ms + GPU {gpu_ms}ms", file=sys.stderr)
        return all_signals[:top_n]


# ========== AFFICHAGE ==========

def format_signal(s: Signal, rank: int) -> str:
    coin = s.symbol.replace("_USDT", "")
    rr = abs(s.tp - s.entry) / abs(s.entry - s.sl) if abs(s.entry - s.sl) > 0 else 0

    lines = [
        "",
        f"{'='*56}",
        f"  #{rank}  {coin}  |  {s.direction}  |  Score {s.score}/100  |  {s.regime.upper()}",
        f"{'='*56}",
        f"  Prix:    {s.last_price} USDT",
        f"  Entree:  {s.entry} USDT",
        f"  TP:      {s.tp} USDT  (R:R {rr:.1f})",
        f"  SL:      {s.sl} USDT",
        f"  ATR:     {s.atr:.6g}",
        f"",
        f"  --- Indicateurs ---",
        f"  RSI: {s.rsi:.0f}  |  MFI: {s.mfi:.0f}  |  W%R: {s.williams_r:.0f}  |  ADX: {s.adx:.0f}",
        f"  MACD: {s.macd_signal}  |  BB squeeze: {'OUI' if s.bb_squeeze else 'non'}",
        f"  Chaikin: {s.chaikin_osc:+.0f}  |  CMF: {s.cmf:+.3f}  |  OBV: {s.obv_trend}",
        f"",
        f"  --- Marche ---",
        f"  Var 24h: {s.change_24h:+.2f}%  |  Funding: {s.funding_rate:.6f}",
        f"  Liquidite: {s.liquidity_bias}",
    ]
    if s.ob_analysis:
        ob = s.ob_analysis
        lines.append(f"  OB: spread {ob.get('spread_pct',0):.4f}%  |  absorption: {ob.get('absorption','none')}  |  spoofing: {'OUI' if ob.get('spoofing_risk') else 'non'}  |  voids: {ob.get('voids',0)}")

    lines.append(f"")
    lines.append(f"  --- Strategies ({len(s.strategies)}) ---")
    for st in s.strategies:
        lines.append(f"    + {st}")

    lines.append(f"")
    lines.append(f"  --- Raisons ---")
    for r in s.reasons:
        lines.append(f"    - {r}")

    if s.liquidity_clusters:
        lines.append(f"")
        lines.append(f"  --- Clusters Liquidite ---")
        for c in s.liquidity_clusters:
            side = "BID" if c["side"] == "bid" else "ASK"
            ctype = f" [{c.get('type','')}]" if c.get('type') else ""
            lines.append(f"    [{side}] {c['price']:.6g} ({c['volume']:,.0f} lots, {c['pct_away']:+.2f}%){ctype}")

    return "\n".join(lines)


def print_banner(cycle=0, total_cycles=0):
    gpu_label = f"PyTorch {GPU_COUNT}xGPU" if GPU_AVAILABLE else "CPU"
    thermal = check_gpu_thermal()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'#'*60}")
    print(f"  SCAN SNIPER v4 — GPU Multi-GPU + 31 Strategies Pre-Pump")
    print(f"  {ts} | {gpu_label} | {TOP_VOLUME} coins")
    if cycle > 0:
        print(f"  Cycle {cycle}/{total_cycles}" if total_cycles else f"  Cycle {cycle} (continu)")
    if thermal["gpus"]:
        temps = " | ".join(f"GPU{g['index']}:{g['temp_c']}C/{g['util_pct']}%" for g in thermal["gpus"])
        print(f"  Thermal: {temps}")
        if thermal["status"] == "critical":
            print(f"  *** ALERTE CRITIQUE: {thermal['max_temp']}C — GPU throttle ***")
        elif thermal["status"] == "warning":
            print(f"  *** WARNING: {thermal['max_temp']}C — surveillance ***")
    print(f"{'#'*60}")
    return thermal


def print_results(signals, elapsed, cycle=0):
    if not signals:
        print(f"\n  Aucun signal >= {MIN_SCORE}/100 ({elapsed:.1f}s)")
        return
    gpu_label = f"PyTorch {GPU_COUNT}xGPU" if GPU_AVAILABLE else "CPU"
    print(f"\n{'#'*60}")
    cycle_str = f" | Cycle {cycle}" if cycle else ""
    print(f"  TOP {len(signals)} Pre-Pump | {gpu_label} | {elapsed:.1f}s{cycle_str}")
    print(f"  31 strategies + Chaikin/CMF/OBV/MFI/ADX + OB Ultra")
    print(f"{'#'*60}")
    for i, s in enumerate(signals, 1):
        print(format_signal(s, i))
    print(f"\n{'='*60}")
    print(f"  Config: Levier 10x | TP ATRx{TP_MULT} | SL ATRx{SL_MULT}")
    print(f"{'='*60}")


def run_single(top_n=3, min_score=MIN_SCORE, output_json=False,
               cycle=0, total_cycles=0, db_conn=None):
    """Execute un seul cycle de scan + sauvegarde DB."""
    thermal = print_banner(cycle, total_cycles)
    if thermal["status"] == "critical":
        print("  GPU thermal critique — pause 30s", file=sys.stderr)
        time.sleep(30)

    t0 = time.time()
    signals = asyncio.run(scan_sniper(top_n=top_n, min_score=min_score))
    elapsed = time.time() - t0

    # Sauvegarde DB
    if signals and cycle > 0:
        thermal_max = thermal.get("max_temp", 0)
        save_signals_to_db(signals, cycle, elapsed, TOP_VOLUME, thermal_max, conn=db_conn)

    if output_json:
        gpu_label = f"PyTorch {GPU_COUNT}xGPU" if GPU_AVAILABLE else "CPU"
        print(json.dumps({
            "signals": [asdict(s) for s in signals],
            "meta": {"scan_time_s": round(elapsed, 1), "coins_scanned": TOP_VOLUME,
                     "signals_found": len(signals), "min_score": min_score,
                     "strategies_count": 31, "version": "v4", "gpu": gpu_label,
                     "gpu_count": GPU_COUNT, "cycle": cycle,
                     "thermal": thermal, "db": str(DB_PATH)}
        }, indent=2, ensure_ascii=False))
    else:
        print_results(signals, elapsed, cycle)
    return signals


def main():
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Scan Sniper v4 — GPU Multi-GPU Pre-Pump Detector")
    parser.add_argument("--top", type=int, default=3, help="Top N signaux")
    parser.add_argument("--min-score", type=int, default=MIN_SCORE, help="Score minimum")
    parser.add_argument("--cycles", type=int, default=1, help="Nombre de cycles (0=infini)")
    parser.add_argument("--interval", type=int, default=45, help="Intervalle entre cycles (sec)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--no-gpu", action="store_true", help="Desactiver GPU")
    parser.add_argument("--db-summary", action="store_true", help="Afficher resume DB et quitter")
    parser.add_argument("--coin", type=str, help="Historique d'un coin specifique (ex: BTC_USDT)")
    args = parser.parse_args()

    # Mode consultation DB
    if args.db_summary:
        conn = init_db()
        print(get_db_summary(conn))
        conn.close()
        return
    if args.coin:
        conn = init_db()
        sym = args.coin if "_USDT" in args.coin else f"{args.coin}_USDT"
        print(get_coin_history(sym, conn))
        conn.close()
        return

    if args.no_gpu:
        global GPU_AVAILABLE, GPU_COUNT
        GPU_AVAILABLE = False
        GPU_COUNT = 0

    # Init DB
    db_conn = init_db()
    print(f"  DB: {DB_PATH}", file=sys.stderr)

    if args.cycles == 1:
        run_single(top_n=args.top, min_score=args.min_score,
                   output_json=args.json, cycle=1, db_conn=db_conn)
        # Afficher resume DB apres scan unique
        if not args.json:
            print(get_db_summary(db_conn))
    else:
        cycle = 0
        total = args.cycles if args.cycles > 0 else 0
        cumul_signals = 0
        t_start = time.time()
        print(f"\n{'*'*60}")
        gpu_label = f"PyTorch {GPU_COUNT}xGPU" if GPU_AVAILABLE else "CPU"
        print(f"  SCAN SNIPER v4 — MODE CONTINU + SQL")
        print(f"  {total if total else 'infini'} cycles | interval {args.interval}s | {gpu_label}")
        print(f"  {TOP_VOLUME} coins x 31 strategies | Top {args.top}")
        print(f"  DB: {DB_PATH}")
        print(f"{'*'*60}")

        try:
            while total == 0 or cycle < total:
                cycle += 1
                signals = run_single(top_n=args.top, min_score=args.min_score,
                                     output_json=args.json, cycle=cycle,
                                     total_cycles=total, db_conn=db_conn)
                cumul_signals += len(signals)
                elapsed_total = time.time() - t_start
                avg_per_cycle = elapsed_total / cycle

                # Stats + resume DB toutes les 10 cycles
                print(f"\n  --- Stats: {cycle} cycles | {cumul_signals} signaux cumules | {avg_per_cycle:.1f}s/cycle ---")
                if cycle % 10 == 0 and not args.json:
                    print(get_db_summary(db_conn))

                if total == 0 or cycle < total:
                    thermal = check_gpu_thermal()
                    wait = args.interval
                    if thermal["status"] == "warning":
                        wait = max(wait, 60)
                        print(f"  Thermal warning — interval augmente a {wait}s")
                    elif thermal["status"] == "critical":
                        wait = max(wait, 120)
                        print(f"  Thermal CRITIQUE — pause {wait}s")
                    print(f"  Prochain cycle dans {wait}s...")
                    time.sleep(wait)
        except KeyboardInterrupt:
            elapsed_total = time.time() - t_start
            print(f"\n\n  Arret apres {cycle} cycles | {cumul_signals} signaux | {elapsed_total:.0f}s total")

        # Resume final DB
        print(f"\n{'*'*60}")
        print(f"  SCAN TERMINE: {cycle} cycles | {cumul_signals} signaux | {time.time()-t_start:.0f}s")
        print(f"{'*'*60}")
        print(get_db_summary(db_conn))

    db_conn.close()


if __name__ == "__main__":
    main()
