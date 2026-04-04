#!/usr/bin/env python3
"""RIVER_USDT read-only microstructure scanner for MEXC futures.

This script is intentionally read-only:
- no private API
- no order placement
- no Telegram notifications
- no hardcoded position state

It prints a compact view of 1m market state based on:
- ticker
- top-of-book depth
- recent 1m candles
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE_URL = "https://contract.mexc.com"
DEFAULT_SYMBOL = "RIVER_USDT"


@dataclass
class Snapshot:
    symbol: str
    price: float
    bid1: float
    ask1: float
    spread_abs: float
    spread_bps: float
    bid_depth: float
    ask_depth: float
    imbalance: float
    wall_bid_price: float
    wall_bid_size: float
    wall_ask_price: float
    wall_ask_size: float
    close_1m: float
    ret_1m_pct: float
    ret_3m_pct: float
    range_1m_pct: float
    range_5m_pct: float
    vol_ratio: float
    vol_last: float
    vol_avg_20: float


def fetch_json(path: str, params: dict[str, object] | None = None) -> dict:
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)
    url = f"{BASE_URL}{path}{query}"
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"fetch failed for {url}: {exc}") from exc


def fetch_snapshot(symbol: str, depth_limit: int = 20, kline_limit: int = 30) -> Snapshot:
    ticker = fetch_json("/api/v1/contract/ticker", {"symbol": symbol}).get("data", {})
    kline = fetch_json(
        f"/api/v1/contract/kline/{symbol}",
        {"interval": "Min1", "limit": kline_limit},
    ).get("data", {})
    depth = fetch_json(
        f"/api/v1/contract/depth/{symbol}",
        {"limit": depth_limit},
    ).get("data", {})

    price = float(ticker["lastPrice"])
    bid1 = float(ticker.get("bid1", 0.0))
    ask1 = float(ticker.get("ask1", 0.0))
    spread_abs = max(ask1 - bid1, 0.0)
    spread_bps = (spread_abs / price * 10_000.0) if price else 0.0

    bids = [(float(level[0]), float(level[1])) for level in depth.get("bids", [])[:depth_limit]]
    asks = [(float(level[0]), float(level[1])) for level in depth.get("asks", [])[:depth_limit]]

    bid_depth = sum(size for _, size in bids)
    ask_depth = sum(size for _, size in asks)
    imbalance = ((bid_depth - ask_depth) / (bid_depth + ask_depth)) if (bid_depth + ask_depth) else 0.0

    wall_bid_price, wall_bid_size = max(bids, key=lambda level: level[1]) if bids else (0.0, 0.0)
    wall_ask_price, wall_ask_size = max(asks, key=lambda level: level[1]) if asks else (0.0, 0.0)

    closes = [float(value) for value in kline.get("close", [])]
    highs = [float(value) for value in kline.get("high", [])]
    lows = [float(value) for value in kline.get("low", [])]
    volumes = [float(value) for value in kline.get("vol", [])]

    if len(closes) < 5 or len(highs) < 5 or len(lows) < 5 or len(volumes) < 5:
        raise RuntimeError("not enough kline data for Min1 analysis")

    close_1m = closes[-1]
    prev_close = closes[-2]
    close_3m = closes[-4]
    ret_1m_pct = ((close_1m - prev_close) / prev_close * 100.0) if prev_close else 0.0
    ret_3m_pct = ((close_1m - close_3m) / close_3m * 100.0) if close_3m else 0.0

    high_1m = highs[-1]
    low_1m = lows[-1]
    range_1m_pct = ((high_1m - low_1m) / close_1m * 100.0) if close_1m else 0.0

    high_5m = max(highs[-5:])
    low_5m = min(lows[-5:])
    range_5m_pct = ((high_5m - low_5m) / close_1m * 100.0) if close_1m else 0.0

    vol_last = volumes[-1]
    vol_window = volumes[-20:] if len(volumes) >= 20 else volumes
    vol_avg_20 = statistics.fmean(vol_window) if vol_window else 0.0
    vol_ratio = (vol_last / vol_avg_20) if vol_avg_20 else 0.0

    return Snapshot(
        symbol=symbol,
        price=price,
        bid1=bid1,
        ask1=ask1,
        spread_abs=spread_abs,
        spread_bps=spread_bps,
        bid_depth=bid_depth,
        ask_depth=ask_depth,
        imbalance=imbalance,
        wall_bid_price=wall_bid_price,
        wall_bid_size=wall_bid_size,
        wall_ask_price=wall_ask_price,
        wall_ask_size=wall_ask_size,
        close_1m=close_1m,
        ret_1m_pct=ret_1m_pct,
        ret_3m_pct=ret_3m_pct,
        range_1m_pct=range_1m_pct,
        range_5m_pct=range_5m_pct,
        vol_ratio=vol_ratio,
        vol_last=vol_last,
        vol_avg_20=vol_avg_20,
    )


def print_snapshot(snapshot: Snapshot, cycle: int | None = None) -> None:
    prefix = f"C{cycle:02d} | " if cycle is not None else ""
    print(
        f"{prefix}{snapshot.symbol} | px {snapshot.price:.4f} | "
        f"bid {snapshot.bid1:.4f} ask {snapshot.ask1:.4f} | "
        f"spread {snapshot.spread_abs:.4f} ({snapshot.spread_bps:.2f} bps)"
    )
    print(
        f"  depth20 bid {snapshot.bid_depth:.2f} / ask {snapshot.ask_depth:.2f} | "
        f"imbalance {snapshot.imbalance:+.3f}"
    )
    print(
        f"  walls bid {snapshot.wall_bid_price:.4f} x {snapshot.wall_bid_size:.2f} | "
        f"ask {snapshot.wall_ask_price:.4f} x {snapshot.wall_ask_size:.2f}"
    )
    print(
        f"  1m ret {snapshot.ret_1m_pct:+.2f}% | 3m ret {snapshot.ret_3m_pct:+.2f}% | "
        f"1m range {snapshot.range_1m_pct:.2f}% | 5m range {snapshot.range_5m_pct:.2f}%"
    )
    print(
        f"  vol last {snapshot.vol_last:.2f} | avg20 {snapshot.vol_avg_20:.2f} | "
        f"vol ratio {snapshot.vol_ratio:.2f}x"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only MEXC microstructure scanner")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="MEXC futures symbol, default: RIVER_USDT")
    parser.add_argument("--cycles", type=int, default=1, help="Number of snapshots to print")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between snapshots when cycles > 1")
    parser.add_argument("--depth-limit", type=int, default=20, help="Depth levels to aggregate")
    parser.add_argument("--kline-limit", type=int, default=30, help="Number of Min1 candles to fetch")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for cycle in range(1, args.cycles + 1):
        try:
            snapshot = fetch_snapshot(
                symbol=args.symbol,
                depth_limit=args.depth_limit,
                kline_limit=args.kline_limit,
            )
            print_snapshot(snapshot, cycle if args.cycles > 1 else None)
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 1
        if cycle < args.cycles:
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
