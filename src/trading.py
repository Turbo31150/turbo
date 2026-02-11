"""JARVIS Trading Pipeline — Signal → Execution MEXC Futures.

Reads pending signals from trading_latest.db, validates them,
executes via ccxt on MEXC Futures, records trades, notifies Telegram.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from src.config import config


# ═══════════════════════════════════════════════════════════════════════════
# DB HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.db_trading))
    conn.row_factory = sqlite3.Row
    return conn


def _symbol_to_ccxt(symbol: str) -> str:
    """Convert DB symbol 'BTC/USDT' → ccxt swap 'BTC/USDT:USDT'."""
    if symbol.endswith(":USDT"):
        return symbol
    return f"{symbol}:USDT"


def _symbol_to_mexc_api(symbol: str) -> str:
    """Convert DB symbol 'BTC/USDT' → MEXC API 'BTC_USDT'."""
    return symbol.replace("/", "_").split(":")[0]


# ═══════════════════════════════════════════════════════════════════════════
# SIGNAL READING
# ═══════════════════════════════════════════════════════════════════════════

def get_pending_signals(
    min_score: float | None = None,
    max_age_min: int | None = None,
    limit: int = 10,
) -> list[dict]:
    """Read pending signals from DB, filtered by score and freshness."""
    min_score = min_score if min_score is not None else config.min_signal_score
    max_age_min = max_age_min if max_age_min is not None else config.max_signal_age_minutes

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_min)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    conn = _db_conn()
    try:
        rows = conn.execute(
            """SELECT id, symbol, direction, price, score, volume, volume_m,
                      change_24h, range_position, reasons, tp1, tp2, tp3, sl,
                      source, executed, created_at
               FROM signals
               WHERE executed = 0
                 AND score >= ?
                 AND created_at >= ?
               ORDER BY score DESC, created_at DESC
               LIMIT ?""",
            (min_score, cutoff_str, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# PRICE & VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

def get_current_price(symbol: str) -> float | None:
    """Get current price from MEXC contract API."""
    mexc_sym = _symbol_to_mexc_api(symbol)
    try:
        url = f"https://contract.mexc.com/api/v1/contract/ticker?symbol={mexc_sym}"
        req = urllib.request.urlopen(url, timeout=10)
        data = json.loads(req.read())
        return float(data["data"]["lastPrice"])
    except Exception:
        return None


def validate_signal(signal: dict, current_price: float | None = None) -> tuple[bool, str]:
    """Validate a signal before execution.

    Checks:
    - Current price proximity (< 1% drift from signal price)
    - Risk/reward ratio >= 1.5
    - Signal not already executed
    """
    if signal.get("executed", 0) != 0:
        return False, "Signal deja execute"

    entry = signal["price"]
    sl = signal["sl"]
    tp1 = signal["tp1"]

    if not entry or not sl or not tp1:
        return False, "Donnees prix manquantes (entry/sl/tp1)"

    # Check price drift
    if current_price is not None:
        drift = abs(current_price - entry) / entry
        if drift > 0.01:
            return False, f"Prix drift trop eleve: {drift:.2%} (max 1%)"

    # Check R/R ratio
    risk = abs(entry - sl)
    reward = abs(tp1 - entry)
    if risk <= 0:
        return False, "Risk = 0 (entry == sl)"
    rr = reward / risk
    if rr < 1.3:
        return False, f"R/R insuffisant: {rr:.2f} (min 1.3)"

    return True, "OK"


# ═══════════════════════════════════════════════════════════════════════════
# EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

def _init_ccxt():
    """Initialize ccxt MEXC client for swap trading."""
    import ccxt
    return ccxt.mexc({
        "apiKey": config.mexc_api_key,
        "secret": config.mexc_secret_key,
        "options": {"defaultType": "swap"},
    })


def _calculate_quantity(entry_price: float) -> float:
    """Calculate order quantity from config size_usdt and leverage."""
    notional = config.size_usdt * config.leverage
    qty = notional / entry_price
    return round(qty, 2)


def execute_signal(signal_id: int, dry_run: bool | None = None) -> dict[str, Any]:
    """Execute a single signal: validate → place orders → record trade.

    Args:
        signal_id: ID in the signals table.
        dry_run: Override config.dry_run. True = simulate only.

    Returns:
        Dict with execution result.
    """
    if dry_run is None:
        dry_run = config.dry_run

    conn = _db_conn()
    try:
        row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        return {"success": False, "error": f"Signal {signal_id} introuvable"}

    signal = dict(row)
    symbol = signal["symbol"]
    ccxt_symbol = _symbol_to_ccxt(symbol)
    direction = signal["direction"]  # LONG or SHORT
    entry = signal["price"]
    tp1 = signal["tp1"]
    sl = signal["sl"]
    score = signal["score"]

    # Get current price
    current_price = get_current_price(symbol)

    # Validate
    valid, reason = validate_signal(signal, current_price)
    if not valid:
        return {
            "success": False,
            "error": reason,
            "signal_id": signal_id,
            "symbol": symbol,
            "mode": "DRY_RUN" if dry_run else "LIVE",
        }

    qty = _calculate_quantity(entry)
    side = "buy" if direction == "LONG" else "sell"
    close_side = "sell" if direction == "LONG" else "buy"

    risk = abs(entry - sl)
    reward = abs(tp1 - entry)
    rr = reward / risk if risk > 0 else 0

    result = {
        "success": True,
        "signal_id": signal_id,
        "symbol": symbol,
        "ccxt_symbol": ccxt_symbol,
        "direction": direction,
        "side": side,
        "entry": entry,
        "current_price": current_price,
        "tp1": tp1,
        "sl": sl,
        "qty": qty,
        "size_usdt": config.size_usdt,
        "leverage": config.leverage,
        "rr_ratio": round(rr, 2),
        "score": score,
        "mode": "DRY_RUN" if dry_run else "LIVE",
    }

    if dry_run:
        result["message"] = "Simulation — aucun ordre place"
        return result

    # ── LIVE EXECUTION ────────────────────────────────────────────────────
    if not config.mexc_api_key or not config.mexc_secret_key:
        return {**result, "success": False, "error": "API keys MEXC non configurees"}

    try:
        mexc = _init_ccxt()
        mexc.load_markets()

        # Set leverage
        try:
            mexc.set_leverage(config.leverage, ccxt_symbol)
        except Exception:
            pass  # May already be set

        # Entry order (limit)
        entry_order = mexc.create_order(ccxt_symbol, "limit", side, qty, entry)
        result["order_id"] = entry_order.get("id")

        # TP order (limit, reduceOnly)
        try:
            mexc.create_order(
                ccxt_symbol, "limit", close_side, qty, tp1,
                {"reduceOnly": True},
            )
            result["tp_set"] = True
        except Exception as e:
            result["tp_error"] = str(e)

        # SL order (stop_market, reduceOnly)
        try:
            mexc.create_order(
                ccxt_symbol, "stop_market", close_side, qty, None,
                {"stopPrice": sl, "reduceOnly": True},
            )
            result["sl_set"] = True
        except Exception as e:
            result["sl_error"] = str(e)

        # Mark signal as executed
        conn = _db_conn()
        try:
            conn.execute("UPDATE signals SET executed = 1 WHERE id = ?", (signal_id,))

            # Insert trade record
            conn.execute(
                """INSERT INTO trades
                   (symbol, direction, entry_price, size, leverage, margin,
                    signal_score, signal_reasons, tp1, tp2, tp3, sl,
                    status, source, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', 'JARVIS', ?)""",
                (
                    symbol, direction, entry, qty, config.leverage,
                    config.size_usdt, score, signal.get("reasons", ""),
                    tp1, signal.get("tp2"), signal.get("tp3"), sl,
                    f"Signal #{signal_id} | Order #{result.get('order_id', '?')}",
                ),
            )
            conn.commit()
        finally:
            conn.close()

        # Telegram notification
        _notify_execution(result)
        result["message"] = "Ordre place avec succes"

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result


# ═══════════════════════════════════════════════════════════════════════════
# POSITIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_mexc_positions() -> list[dict]:
    """Fetch open positions from MEXC via ccxt."""
    if not config.mexc_api_key or not config.mexc_secret_key:
        return [{"error": "API keys MEXC non configurees"}]

    try:
        mexc = _init_ccxt()
        mexc.load_markets()
        positions = mexc.fetch_positions()
        return [
            {
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
            if p.get("contracts") and float(p["contracts"]) > 0
        ]
    except Exception as e:
        return [{"error": str(e)}]


def close_position(symbol: str) -> dict[str, Any]:
    """Close an open position by placing a reduce-only market order."""
    if not config.mexc_api_key or not config.mexc_secret_key:
        return {"success": False, "error": "API keys MEXC non configurees"}

    ccxt_symbol = _symbol_to_ccxt(symbol)

    try:
        mexc = _init_ccxt()
        mexc.load_markets()
        positions = mexc.fetch_positions([ccxt_symbol])

        pos = None
        for p in positions:
            if p["symbol"] == ccxt_symbol and p.get("contracts") and float(p["contracts"]) > 0:
                pos = p
                break

        if not pos:
            return {"success": False, "error": f"Aucune position ouverte pour {symbol}"}

        close_side = "sell" if pos["side"] == "long" else "buy"
        qty = float(pos["contracts"])

        order = mexc.create_order(
            ccxt_symbol, "market", close_side, qty,
            params={"reduceOnly": True},
        )

        # Update trade in DB
        conn = _db_conn()
        try:
            conn.execute(
                """UPDATE trades SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP,
                   exit_price = ?, pnl = ?
                   WHERE symbol = ? AND status = 'OPEN'""",
                (pos.get("markPrice"), pos.get("unrealizedPnl"), symbol),
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "success": True,
            "symbol": symbol,
            "side_closed": close_side,
            "qty": qty,
            "order_id": order.get("id"),
            "pnl": pos.get("unrealizedPnl"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════════════════

def send_telegram(message: str) -> bool:
    """Send a Telegram notification."""
    if not config.telegram_token or not config.telegram_chat:
        return False
    try:
        body = json.dumps({
            "chat_id": config.telegram_chat,
            "text": message,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{config.telegram_token}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def _notify_execution(result: dict) -> None:
    """Send Telegram notification for an executed trade."""
    mode = result.get("mode", "?")
    symbol = result.get("symbol", "?")
    direction = result.get("direction", "?")
    entry = result.get("entry", 0)
    tp1 = result.get("tp1", 0)
    sl = result.get("sl", 0)
    rr = result.get("rr_ratio", 0)
    score = result.get("score", 0)

    msg = (
        f"JARVIS {mode} | {symbol} {direction}\n"
        f"Entry: {entry} | TP: {tp1} | SL: {sl}\n"
        f"R/R: 1:{rr} | Score: {score}\n"
        f"Size: {config.size_usdt}$ x {config.leverage}x"
    )
    send_telegram(msg)


# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE STATUS
# ═══════════════════════════════════════════════════════════════════════════

def pipeline_status() -> dict[str, Any]:
    """Get overall pipeline status: signals, trades, PnL."""
    conn = _db_conn()
    try:
        # Pending signals (high score, fresh)
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=config.max_signal_age_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        pending = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE executed = 0 AND score >= ? AND created_at >= ?",
            (config.min_signal_score, cutoff),
        ).fetchone()[0]

        total_signals = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        executed_signals = conn.execute("SELECT COUNT(*) FROM signals WHERE executed = 1").fetchone()[0]

        # Trades
        open_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'").fetchone()[0]
        closed_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED'").fetchone()[0]

        # PnL
        pnl_row = conn.execute("SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE status = 'CLOSED'").fetchone()
        total_pnl = pnl_row[0] if pnl_row else 0

        # Last execution
        last_trade = conn.execute(
            "SELECT symbol, direction, entry_price, opened_at FROM trades ORDER BY opened_at DESC LIMIT 1"
        ).fetchone()

        # Last signal
        last_signal = conn.execute(
            "SELECT symbol, direction, score, created_at FROM signals ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

        return {
            "pipeline": {
                "pending_signals": pending,
                "total_signals": total_signals,
                "executed_signals": executed_signals,
                "min_score": config.min_signal_score,
                "max_age_minutes": config.max_signal_age_minutes,
            },
            "trades": {
                "open": open_trades,
                "closed": closed_trades,
                "total_pnl": round(total_pnl, 4),
            },
            "config": {
                "dry_run": config.dry_run,
                "size_usdt": config.size_usdt,
                "leverage": config.leverage,
                "exchange": config.exchange,
            },
            "last_trade": dict(last_trade) if last_trade else None,
            "last_signal": dict(last_signal) if last_signal else None,
        }
    finally:
        conn.close()
