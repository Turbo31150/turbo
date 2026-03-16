"""JARVIS Multi-Exchange Support — Unified interface for MEXC, Binance, Bybit.

Provides a common API for trading operations across exchanges.
Uses ccxt for exchange abstraction.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "ExchangeConfig",
    "UnifiedExchange",
    "get_all_positions",
    "get_best_price",
    "get_enabled_exchanges",
]

logger = logging.getLogger("jarvis.exchanges")


@dataclass
class ExchangeConfig:
    """Configuration for a single exchange."""
    name: str
    api_key: str = ""
    secret_key: str = ""
    passphrase: str = ""  # For some exchanges like OKX
    testnet: bool = False
    leverage: int = 10
    tp_percent: float = 0.4
    sl_percent: float = 0.25
    size_usdt: float = 10.0
    enabled: bool = True


# ── Exchange Registry ────────────────────────────────────────────────────

EXCHANGE_CONFIGS: dict[str, ExchangeConfig] = {
    "mexc": ExchangeConfig(
        name="mexc",
        api_key=os.getenv("MEXC_API_KEY", ""),
        secret_key=os.getenv("MEXC_SECRET_KEY", ""),
        leverage=10,
        tp_percent=0.4,
        sl_percent=0.25,
    ),
    "binance": ExchangeConfig(
        name="binance",
        api_key=os.getenv("BINANCE_API_KEY", ""),
        secret_key=os.getenv("BINANCE_SECRET_KEY", ""),
        leverage=10,
        tp_percent=0.4,
        sl_percent=0.25,
        enabled=bool(os.getenv("BINANCE_API_KEY")),
    ),
    "bybit": ExchangeConfig(
        name="bybit",
        api_key=os.getenv("BYBIT_API_KEY", ""),
        secret_key=os.getenv("BYBIT_SECRET_KEY", ""),
        leverage=10,
        tp_percent=0.4,
        sl_percent=0.25,
        enabled=bool(os.getenv("BYBIT_API_KEY")),
    ),
}


class UnifiedExchange:
    """Unified exchange interface using ccxt.

    Usage:
        exchange = UnifiedExchange("mexc")
        balance = await exchange.get_balance()
        positions = await exchange.get_positions()
        order = await exchange.place_order("BTC/USDT:USDT", "long", 10.0)
    """

    def __init__(self, exchange_name: str):
        self.name = exchange_name
        self.config = EXCHANGE_CONFIGS.get(exchange_name)
        if not self.config:
            raise ValueError(f"Unknown exchange: {exchange_name}")
        self._exchange = None

    def _get_exchange(self):
        """Lazy-initialize the ccxt exchange instance."""
        if self._exchange is not None:
            return self._exchange

        import ccxt

        exchange_class = getattr(ccxt, self.name, None)
        if exchange_class is None:
            raise ValueError(f"ccxt does not support exchange: {self.name}")

        opts: dict[str, Any] = {
            "apiKey": self.config.api_key,
            "secret": self.config.secret_key,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
                "adjustForTimeDifference": True,
            },
        }

        if self.config.passphrase:
            opts["password"] = self.config.passphrase

        if self.config.testnet:
            opts["sandbox"] = True

        self._exchange = exchange_class(opts)
        return self._exchange

    def get_balance(self) -> dict:
        """Get USDT balance."""
        ex = self._get_exchange()
        balance = ex.fetch_balance({"type": "swap"})
        usdt = balance.get("USDT", {})
        return {
            "exchange": self.name,
            "total": usdt.get("total", 0),
            "free": usdt.get("free", 0),
            "used": usdt.get("used", 0),
        }

    def get_positions(self) -> list[dict]:
        """Get all open positions."""
        ex = self._get_exchange()
        positions = ex.fetch_positions()
        return [
            {
                "exchange": self.name,
                "symbol": p["symbol"],
                "side": p["side"],
                "size": p["contracts"],
                "entry_price": p["entryPrice"],
                "mark_price": p["markPrice"],
                "pnl": p["unrealizedPnl"],
                "leverage": p["leverage"],
                "margin": p["initialMargin"],
            }
            for p in positions
            if p["contracts"] and p["contracts"] > 0
        ]

    def get_ticker(self, symbol: str) -> dict:
        """Get current price for a symbol."""
        ex = self._get_exchange()
        ticker = ex.fetch_ticker(symbol)
        return {
            "exchange": self.name,
            "symbol": symbol,
            "last": ticker["last"],
            "bid": ticker["bid"],
            "ask": ticker["ask"],
            "volume": ticker["baseVolume"],
            "change_24h": ticker.get("percentage", 0),
        }

    def place_order(
        self,
        symbol: str,
        side: str,  # "long" or "short"
        size_usdt: float | None = None,
        leverage: int | None = None,
        tp_percent: float | None = None,
        sl_percent: float | None = None,
        dry_run: bool = True,
    ) -> dict:
        """Place a futures order with TP/SL.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT:USDT")
            side: "long" or "short"
            size_usdt: Position size in USDT
            leverage: Leverage multiplier
            tp_percent: Take profit percentage
            sl_percent: Stop loss percentage
            dry_run: If True, simulate only

        Returns:
            Order result dict
        """
        size = size_usdt or self.config.size_usdt
        lev = leverage or self.config.leverage
        tp = tp_percent or self.config.tp_percent
        sl = sl_percent or self.config.sl_percent

        ex = self._get_exchange()

        # Get current price
        ticker = ex.fetch_ticker(symbol)
        price = ticker["last"]

        # Calculate order quantity
        qty = size / price

        # Calculate TP/SL prices
        if side == "long":
            tp_price = price * (1 + tp / 100)
            sl_price = price * (1 - sl / 100)
            order_side = "buy"
        else:
            tp_price = price * (1 - tp / 100)
            sl_price = price * (1 + sl / 100)
            order_side = "sell"

        result = {
            "exchange": self.name,
            "symbol": symbol,
            "side": side,
            "order_side": order_side,
            "size_usdt": size,
            "quantity": qty,
            "price": price,
            "leverage": lev,
            "tp_price": round(tp_price, 6),
            "sl_price": round(sl_price, 6),
            "dry_run": dry_run,
        }

        if dry_run:
            result["status"] = "simulated"
            result["message"] = f"DRY RUN: Would {order_side} {qty:.6f} {symbol} at {price}"
            logger.info("DRY RUN: %s %s on %s", order_side, symbol, self.name)
            return result

        # Set leverage
        try:
            ex.set_leverage(lev, symbol)
        except Exception as e:
            logger.warning("Failed to set leverage on %s: %s", self.name, e)

        # Place market order
        order = ex.create_market_order(symbol, order_side, qty)
        result["order_id"] = order["id"]
        result["status"] = order["status"]

        # Place TP order
        try:
            ex.create_order(
                symbol, "limit", "sell" if side == "long" else "buy",
                qty, tp_price,
                {"reduceOnly": True},
            )
            result["tp_placed"] = True
        except Exception as e:
            result["tp_placed"] = False
            result["tp_error"] = str(e)

        # Place SL order
        try:
            sl_params: dict[str, Any] = {"reduceOnly": True, "stopPrice": sl_price}
            ex.create_order(
                symbol, "stop_market", "sell" if side == "long" else "buy",
                qty, None,
                sl_params,
            )
            result["sl_placed"] = True
        except Exception as e:
            result["sl_placed"] = False
            result["sl_error"] = str(e)

        logger.info("Order placed on %s: %s %s at %s", self.name, order_side, symbol, price)
        return result

    def close_position(self, symbol: str) -> dict:
        """Close an open position."""
        ex = self._get_exchange()
        positions = ex.fetch_positions([symbol])
        active = [p for p in positions if p["contracts"] and p["contracts"] > 0]

        if not active:
            return {"exchange": self.name, "symbol": symbol, "status": "no_position"}

        pos = active[0]
        side = "sell" if pos["side"] == "long" else "buy"
        order = ex.create_market_order(symbol, side, pos["contracts"], params={"reduceOnly": True})

        return {
            "exchange": self.name,
            "symbol": symbol,
            "status": "closed",
            "order_id": order["id"],
            "pnl": pos.get("unrealizedPnl", 0),
        }


# ── Multi-exchange helpers ───────────────────────────────────────────────

def get_enabled_exchanges() -> list[str]:
    """Get list of enabled exchange names."""
    return [name for name, cfg in EXCHANGE_CONFIGS.items() if cfg.enabled and cfg.api_key]


def get_best_price(symbol: str) -> dict:
    """Get the best price across all enabled exchanges."""
    best = None
    for name in get_enabled_exchanges():
        try:
            ex = UnifiedExchange(name)
            ticker = ex.get_ticker(symbol)
            if best is None or ticker["last"] < best["last"]:
                best = ticker
        except Exception as e:
            logger.debug("Failed to get price from %s: %s", name, e)
    return best or {"symbol": symbol, "error": "No exchange available"}


def get_all_positions() -> list[dict]:
    """Get positions from all enabled exchanges."""
    all_pos = []
    for name in get_enabled_exchanges():
        try:
            ex = UnifiedExchange(name)
            all_pos.extend(ex.get_positions())
        except Exception as e:
            logger.debug("Failed to get positions from %s: %s", name, e)
    return all_pos
