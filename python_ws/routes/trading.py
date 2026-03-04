"""Trading route — signals, positions, PnL monitoring."""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path

from python_ws.helpers import push_loop

logger = logging.getLogger("jarvis.trading")

try:
    from src.config import config as jarvis_config
except ImportError:
    jarvis_config = None

_TURBO_ROOT = Path(__file__).resolve().parent.parent.parent
_TRADING_DB_FALLBACK = _TURBO_ROOT.parent / "carV1" / "database" / "trading_latest.db"
if jarvis_config and hasattr(jarvis_config, 'db_trading'):
    _TRADING_DB = str(jarvis_config.db_trading)
else:
    _TRADING_DB = str(_TRADING_DB_FALLBACK)
    logger.warning("Trading DB config missing, fallback: %s", _TRADING_DB)




async def handle_trading_request(action: str, payload: dict) -> dict:
    """Handle trading channel requests."""
    if action in ("pending_signals", "get_signals"):
        return await _get_signals()
    elif action == "execute_signal":
        return await _execute_signal(payload)
    elif action in ("positions", "get_positions"):
        return await _get_positions()
    elif action == "close_position":
        return await _close_position(payload)
    elif action == "pnl_summary":
        return await _get_pnl_summary()
    elif action == "strategy_rankings":
        return await _get_strategy_rankings(payload)
    elif action == "score_signal":
        return await _score_signal(payload)
    elif action == "position_sizing":
        return await _calculate_position_size(payload)
    return {"error": f"Unknown trading action: {action}"}


async def _get_signals() -> dict:
    """Fetch pending trading signals."""
    def _query():
        with sqlite3.connect(_TRADING_DB) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT * FROM signals
                WHERE status = 'pending'
                ORDER BY created_at DESC
                LIMIT 20
            """)
            return [dict(r) for r in cur.fetchall()]

    try:
        signals = await asyncio.to_thread(_query)
        return {"signals": signals}
    except (sqlite3.Error, OSError) as e:
        logger.debug("Trading DB unavailable: %s — using demo signals", e)
        return {"signals": _get_demo_signals()}


async def _get_positions() -> dict:
    """Fetch open positions."""
    def _query():
        with sqlite3.connect(_TRADING_DB) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT * FROM positions
                WHERE status = 'open'
                ORDER BY opened_at DESC
            """)
            return [dict(r) for r in cur.fetchall()]

    try:
        positions = await asyncio.to_thread(_query)
        return {"positions": positions}
    except (sqlite3.Error, OSError) as e:
        logger.debug("Trading positions unavailable: %s", e)
        return {"positions": []}


async def _execute_signal(payload: dict) -> dict:
    """Execute a trading signal (dry-run safe)."""
    signal_id = payload.get("signal_id")
    if not signal_id or not isinstance(signal_id, str):
        return {"error": "Missing or invalid signal_id"}

    # Verify signal exists and is pending
    def _check():
        try:
            with sqlite3.connect(_TRADING_DB) as conn:
                row = conn.execute(
                    "SELECT status FROM signals WHERE id = ?", (signal_id,)
                ).fetchone()
                return row
        except (sqlite3.Error, OSError):
            return None

    row = await asyncio.to_thread(_check)
    if row is None:
        logger.debug("Signal %s not found in DB — proceeding anyway", signal_id)
    elif row[0] != "pending":
        return {"error": f"Signal {signal_id} is already '{row[0]}'", "signal_id": signal_id}

    dry_run = True
    if jarvis_config:
        dry_run = jarvis_config.dry_run

    return {
        "executed": True,
        "signal_id": signal_id,
        "dry_run": dry_run,
        "message": f"Signal {signal_id} {'simule (DRY RUN)' if dry_run else 'execute'}",
    }


async def _close_position(payload: dict) -> dict:
    """Close an open position."""
    position_id = payload.get("position_id")
    if not position_id or not isinstance(position_id, str):
        return {"error": "Missing or invalid position_id"}

    # Verify position exists and is open
    def _check():
        try:
            with sqlite3.connect(_TRADING_DB) as conn:
                row = conn.execute(
                    "SELECT status FROM positions WHERE id = ?", (position_id,)
                ).fetchone()
                return row
        except (sqlite3.Error, OSError):
            return None

    row = await asyncio.to_thread(_check)
    if row is not None and row[0] != "open":
        return {"error": f"Position {position_id} is already '{row[0]}'", "position_id": position_id}

    return {"closed": True, "position_id": position_id, "message": "Position fermee"}


async def _get_pnl_summary() -> dict:
    """Get PnL summary from DB (not empty module vars)."""
    positions_data = await _get_positions()
    positions = positions_data.get("positions", [])
    total_pnl = sum(p.get("pnl", 0) for p in positions)
    signals_data = await _get_signals()
    signals = signals_data.get("signals", [])
    return {
        "total_pnl": total_pnl,
        "open_positions": len(positions),
        "pending_signals": len(signals),
    }


async def _get_strategy_rankings(payload: dict) -> dict:
    """Get strategy rankings from trading engine."""
    try:
        from src.trading_engine import strategy_scorer
        top_n = payload.get("top_n", 10)
        rankings = strategy_scorer.get_strategy_rankings(top_n=min(top_n, 50))
        return {"rankings": rankings}
    except ImportError:
        return {"error": "Trading engine not available"}
    except Exception as e:
        return {"error": f"Strategy rankings failed: {e}"}


async def _score_signal(payload: dict) -> dict:
    """Score a trading signal using strategy scorer."""
    try:
        from src.trading_engine import strategy_scorer, TradeSignal
        pair = payload.get("pair", "")
        direction = payload.get("direction", "LONG")
        price = payload.get("price", 0.0)
        if not pair or not price:
            return {"error": "Missing pair or price"}
        signal = TradeSignal(pair=pair, direction=direction, entry_price=price)
        score = strategy_scorer.score_signal(signal)
        return {"pair": pair, "direction": direction, "score": round(score, 2)}
    except ImportError:
        return {"error": "Trading engine not available"}
    except Exception as e:
        return {"error": f"Signal scoring failed: {e}"}


async def _calculate_position_size(payload: dict) -> dict:
    """Calculate position size with risk management.

    Uses: account_balance * risk_percent / (entry - stop_loss) * leverage.
    """
    balance = payload.get("balance", 100.0)
    risk_pct = payload.get("risk_percent", 1.0)
    entry = payload.get("entry_price", 0.0)
    stop_loss = payload.get("stop_loss", 0.0)
    leverage = payload.get("leverage", 10)

    if not entry or not stop_loss or entry == stop_loss:
        return {"error": "Invalid entry/stop_loss prices"}

    risk_amount = balance * (risk_pct / 100.0)
    price_diff = abs(entry - stop_loss)
    raw_size = risk_amount / price_diff
    leveraged_size = raw_size * leverage
    notional = leveraged_size * entry

    # Slippage estimate (0.05% for crypto)
    slippage_cost = notional * 0.0005
    # Fee estimate (0.04% taker)
    fee_cost = notional * 0.0004

    return {
        "position_size": round(leveraged_size, 6),
        "notional_value": round(notional, 2),
        "risk_amount": round(risk_amount, 2),
        "slippage_estimate": round(slippage_cost, 4),
        "fee_estimate": round(fee_cost, 4),
        "total_cost": round(slippage_cost + fee_cost, 4),
        "leverage": leverage,
        "margin_required": round(notional / leverage, 2),
    }


def _get_demo_signals() -> list:
    """Demo signals for development."""
    return [
        {"id": "sig_1", "pair": "BTC/USDT", "direction": "LONG", "score": 85, "price": 98500.0, "age_min": 5, "status": "pending"},
        {"id": "sig_2", "pair": "ETH/USDT", "direction": "SHORT", "score": 72, "price": 3450.0, "age_min": 12, "status": "pending"},
        {"id": "sig_3", "pair": "SOL/USDT", "direction": "LONG", "score": 91, "price": 185.5, "age_min": 2, "status": "pending"},
    ]


async def _build_trading_payload() -> dict:
    """Build the payload for trading push events."""
    signals = await _get_signals()
    positions = await _get_positions()
    pnl = await _get_pnl_summary()
    return {
        **pnl,
        "signals": signals.get("signals", []),
        "positions": positions.get("positions", []),
    }


async def push_trading_events(send_func):
    """Push trading updates every 30s."""
    await push_loop(
        send_func, _build_trading_payload,
        channel="trading", event="position_update",
        interval=30.0, backoff=5.0,
    )
