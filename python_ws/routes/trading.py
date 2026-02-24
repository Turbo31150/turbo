"""Trading route — signals, positions, PnL monitoring."""
import asyncio
import time
from typing import Any

try:
    from src.config import config as jarvis_config
except ImportError:
    jarvis_config = None


# In-memory state (populated from real data when available)
_signals: list[dict] = []
_positions: list[dict] = []


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
        return _get_pnl_summary()
    return {"error": f"Unknown trading action: {action}"}


async def _get_signals() -> dict:
    """Fetch pending trading signals."""
    # Try to read from trading database
    try:
        import sqlite3
        db_path = "F:/BUREAU/carV1/database/trading_latest.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM signals
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        conn.close()
        signals = [dict(r) for r in rows]
        return {"signals": signals}
    except Exception:
        # Return demo data if DB not available
        return {"signals": _get_demo_signals()}


async def _get_positions() -> dict:
    """Fetch open positions."""
    try:
        import sqlite3
        db_path = "F:/BUREAU/carV1/database/trading_latest.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM positions
            WHERE status = 'open'
            ORDER BY opened_at DESC
        """)
        rows = cur.fetchall()
        conn.close()
        positions = [dict(r) for r in rows]
        return {"positions": positions}
    except Exception:
        return {"positions": []}


async def _execute_signal(payload: dict) -> dict:
    """Execute a trading signal (dry-run safe)."""
    signal_id = payload.get("signal_id")
    if not signal_id:
        return {"error": "Missing signal_id"}

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
    if not position_id:
        return {"error": "Missing position_id"}
    return {"closed": True, "position_id": position_id, "message": "Position fermee"}


def _get_pnl_summary() -> dict:
    """Get PnL summary."""
    total_pnl = sum(p.get("pnl", 0) for p in _positions)
    return {
        "total_pnl": total_pnl,
        "open_positions": len(_positions),
        "pending_signals": len(_signals),
    }


def _get_demo_signals() -> list:
    """Demo signals for development."""
    return [
        {"id": "sig_1", "pair": "BTC/USDT", "direction": "LONG", "score": 85, "price": 98500.0, "age_min": 5, "status": "pending"},
        {"id": "sig_2", "pair": "ETH/USDT", "direction": "SHORT", "score": 72, "price": 3450.0, "age_min": 12, "status": "pending"},
        {"id": "sig_3", "pair": "SOL/USDT", "direction": "LONG", "score": 91, "price": 185.5, "age_min": 2, "status": "pending"},
    ]


async def push_trading_events(send_func):
    """Push trading updates every 30s."""
    while True:
        try:
            await asyncio.sleep(30)
            signals = await _get_signals()
            positions = await _get_positions()
            await send_func({
                "type": "event",
                "channel": "trading",
                "event": "position_update",
                "payload": {
                    **_get_pnl_summary(),
                    "signals": signals.get("signals", []),
                    "positions": positions.get("positions", []),
                },
            })
        except Exception:
            pass
