"""
Data Fetcher — MEXC Futures API + Order Book
Trading AI System v2.2 | Adapte cluster JARVIS
"""

import time
import json
import logging
import requests
import numpy as np
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("data_fetcher")

# --- Config MEXC ---
MEXC_BASE = "https://contract.mexc.com"
MEXC_SPOT = "https://api.mexc.com"

# Paires cibles (Futures USDT-M)
DEFAULT_PAIRS = [
    "BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "PEPE_USDT",
    "DOGE_USDT", "XRP_USDT", "ADA_USDT", "AVAX_USDT", "LINK_USDT",
    "WIF_USDT", "BONK_USDT", "FET_USDT", "NEAR_USDT", "INJ_USDT",
    "ARB_USDT", "OP_USDT", "TIA_USDT", "SEI_USDT", "JUP_USDT",
]

# Timeframes
KLINE_INTERVAL = "Min15"  # 15 min par defaut
TIME_WINDOW = 512         # Bougies par coin


def fetch_all_futures_symbols() -> list[str]:
    """Recupere tous les symboles Futures USDT-M actifs sur MEXC."""
    try:
        r = requests.get(f"{MEXC_BASE}/api/v1/contract/detail", timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        symbols = [
            d["symbol"] for d in data
            if d.get("quoteCoin") == "USDT" and d.get("state") == 0
        ]
        logger.info(f"MEXC Futures: {len(symbols)} paires actives")
        return symbols
    except Exception as e:
        logger.error(f"Erreur fetch symboles: {e}")
        return []


def fetch_klines(symbol: str, interval: str = KLINE_INTERVAL,
                 limit: int = TIME_WINDOW) -> Optional[np.ndarray]:
    """
    Recupere les klines MEXC Futures.
    Retourne ndarray shape (N, 6): [timestamp, open, high, low, close, volume]
    Precision float32 obligatoire.
    """
    try:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(f"{MEXC_BASE}/api/v1/contract/kline/{symbol}",
                         params=params, timeout=15)
        r.raise_for_status()
        data = r.json().get("data", {})

        if isinstance(data, dict):
            # Format MEXC: {"time":[], "open":[], "high":[], ...}
            times = data.get("time", [])
            opens = data.get("open", [])
            highs = data.get("high", [])
            lows = data.get("low", [])
            closes = data.get("close", [])
            vols = data.get("vol", [])
            n = min(len(times), len(opens), len(highs), len(lows), len(closes), len(vols))
            if n == 0:
                return None
            arr = np.zeros((n, 6), dtype=np.float32)
            arr[:, 0] = np.array(times[:n], dtype=np.float32)
            arr[:, 1] = np.array(opens[:n], dtype=np.float32)
            arr[:, 2] = np.array(highs[:n], dtype=np.float32)
            arr[:, 3] = np.array(lows[:n], dtype=np.float32)
            arr[:, 4] = np.array(closes[:n], dtype=np.float32)
            arr[:, 5] = np.array(vols[:n], dtype=np.float32)
            return arr
        elif isinstance(data, list):
            if len(data) == 0:
                return None
            arr = np.array(data, dtype=np.float32)
            if arr.ndim == 2 and arr.shape[1] >= 6:
                return arr[:, :6]
            return None
        return None
    except Exception as e:
        logger.warning(f"Klines {symbol}: {e}")
        return None


def fetch_depth(symbol: str, limit: int = 20) -> Optional[dict]:
    """
    Recupere le carnet d'ordres MEXC Futures.
    Retourne: {"bids": ndarray(N,2), "asks": ndarray(N,2), "imbalance": float}
    """
    try:
        r = requests.get(f"{MEXC_BASE}/api/v1/contract/depth/{symbol}",
                         params={"limit": limit}, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", {})

        bids_raw = data.get("bids", [])
        asks_raw = data.get("asks", [])

        bids = np.array(bids_raw, dtype=np.float32) if bids_raw else np.zeros((1, 2), dtype=np.float32)
        asks = np.array(asks_raw, dtype=np.float32) if asks_raw else np.zeros((1, 2), dtype=np.float32)

        # Assurer 2D
        if bids.ndim == 1:
            bids = bids.reshape(-1, 2)
        if asks.ndim == 1:
            asks = asks.reshape(-1, 2)

        bid_vol = np.sum(bids[:, 1]) if bids.shape[0] > 0 else 0.0
        ask_vol = np.sum(asks[:, 1]) if asks.shape[0] > 0 else 0.0
        imbalance = float((bid_vol - ask_vol) / (bid_vol + ask_vol + 1e-8))

        return {"bids": bids, "asks": asks, "imbalance": imbalance}
    except Exception as e:
        logger.warning(f"Depth {symbol}: {e}")
        return None


def fetch_ticker(symbol: str) -> Optional[dict]:
    """Recupere le ticker 24h pour un symbole."""
    try:
        r = requests.get(f"{MEXC_BASE}/api/v1/contract/ticker",
                         params={"symbol": symbol}, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", {})
        if isinstance(data, list):
            for d in data:
                if d.get("symbol") == symbol:
                    return d
            return data[0] if data else None
        return data
    except Exception as e:
        logger.warning(f"Ticker {symbol}: {e}")
        return None


def fetch_batch_klines(symbols: list[str], interval: str = KLINE_INTERVAL,
                       limit: int = TIME_WINDOW, max_workers: int = 8
                       ) -> dict[str, np.ndarray]:
    """
    Fetch klines en parallele pour N symboles.
    Retourne dict {symbol: ndarray(N,6)} en float32.
    """
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(fetch_klines, sym, interval, limit): sym
            for sym in symbols
        }
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                arr = fut.result()
                if arr is not None and arr.shape[0] >= 20:
                    results[sym] = arr
            except Exception as e:
                logger.warning(f"Batch kline {sym}: {e}")

    logger.info(f"Batch klines: {len(results)}/{len(symbols)} OK")
    return results


def fetch_batch_depth(symbols: list[str], max_workers: int = 8
                      ) -> dict[str, dict]:
    """Fetch order books en parallele."""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(fetch_depth, sym): sym
            for sym in symbols
        }
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                ob = fut.result()
                if ob is not None:
                    results[sym] = ob
            except Exception:
                pass

    logger.info(f"Batch depth: {len(results)}/{len(symbols)} OK")
    return results


def build_tensor_3d(klines_dict: dict[str, np.ndarray],
                    time_window: int = TIME_WINDOW
                    ) -> tuple[np.ndarray, list[str]]:
    """
    Construit le tenseur 3D [coins x temps x features].
    Features: [open, high, low, close, volume] = 5 colonnes.
    Pad avec zeros si < time_window.
    Retourne (tensor float32, liste symboles).
    """
    symbols = sorted(klines_dict.keys())
    n_coins = len(symbols)
    n_features = 5  # OHLCV

    tensor = np.zeros((n_coins, time_window, n_features), dtype=np.float32)

    for i, sym in enumerate(symbols):
        arr = klines_dict[sym]
        # Colonnes 1-5 = OHLCV (colonne 0 = timestamp)
        ohlcv = arr[:, 1:6] if arr.shape[1] >= 6 else arr[:, :5]
        n = min(ohlcv.shape[0], time_window)
        tensor[i, :n, :] = ohlcv[-n:]  # Dernieres N bougies

    logger.info(f"Tenseur 3D: {tensor.shape} ({n_coins} coins x {time_window} temps x {n_features} features)")
    return tensor, symbols


def scan_top_volume(n: int = 200) -> list[str]:
    """Scan les top N symboles par volume 24h sur MEXC Futures."""
    try:
        r = requests.get(f"{MEXC_BASE}/api/v1/contract/ticker", timeout=15)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not isinstance(data, list):
            return DEFAULT_PAIRS[:n]

        # Trier par volume 24h decroissant
        valid = [d for d in data if d.get("symbol", "").endswith("_USDT")]
        valid.sort(key=lambda x: float(x.get("volume24", 0)), reverse=True)

        symbols = [d["symbol"] for d in valid[:n]]
        logger.info(f"Top {n} volume: {symbols[:5]}...")
        return symbols
    except Exception as e:
        logger.error(f"Scan top volume: {e}")
        return DEFAULT_PAIRS[:n]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== Data Fetcher Test ===")

    # Test: top 10 par volume
    top = scan_top_volume(10)
    print(f"Top 10: {top}")

    # Test: klines batch
    klines = fetch_batch_klines(top[:5], limit=100)
    for sym, arr in klines.items():
        print(f"  {sym}: {arr.shape} | last close={arr[-1, 4]:.4f}")

    # Test: tenseur 3D
    tensor, syms = build_tensor_3d(klines, time_window=100)
    print(f"Tenseur: {tensor.shape} dtype={tensor.dtype}")
