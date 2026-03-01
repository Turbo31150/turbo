"""Signal Formatter — Parse scan_sniper JSON, format for Telegram + Chat."""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger("jarvis.signal_formatter")


def parse_sniper_json(raw_output: str) -> dict | None:
    """Extract JSON object from scan_sniper stdout (may contain log lines before JSON)."""
    # Find the first '{' that starts the JSON block
    idx = raw_output.find('{"signals"')
    if idx == -1:
        # Try finding any top-level JSON object
        idx = raw_output.find('{')
    if idx == -1:
        return None
    try:
        return json.loads(raw_output[idx:])
    except json.JSONDecodeError:
        # Try line-by-line (JSON might be on the last line)
        for line in reversed(raw_output.splitlines()):
            line = line.strip()
            if line.startswith('{'):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        return None


def _risk_reward(entry: float, tp: float, sl: float) -> str:
    """Compute R:R ratio string."""
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk <= 0:
        return "N/A"
    rr = reward / risk
    return f"1:{rr:.1f}"


def _pct(val: float, ref: float) -> str:
    """Percent distance from ref."""
    if ref <= 0:
        return "0%"
    return f"{abs(val - ref) / ref * 100:.2f}%"


def format_telegram_signals(data: dict) -> str:
    """Plain text message for Telegram (< 4096 chars)."""
    signals = data.get("signals", [])
    meta = data.get("meta", {})
    if not signals:
        return "SCAN SNIPER — Aucun signal detecte."

    lines = [
        f"SCAN SNIPER {meta.get('version', '?')} — "
        f"{meta.get('signals_found', len(signals))} signaux "
        f"/ {meta.get('coins_scanned', '?')} coins "
        f"({meta.get('scan_time_s', '?')}s)",
        "",
    ]
    for i, s in enumerate(signals[:10], 1):  # Max 10 for Telegram
        direction = s.get("direction", "?").upper()
        arrow = "\u2B06" if direction == "LONG" else "\u2B07"
        entry = s.get("entry", 0)
        tp = s.get("tp", 0)
        sl = s.get("sl", 0)
        rr = _risk_reward(entry, tp, sl)
        lines.append(
            f"{arrow} #{i} {s.get('symbol', '?')} {direction} "
            f"Score:{s.get('score', 0)}/100 R:R {rr}"
        )
        lines.append(
            f"   Entry: {entry}  TP: {tp} ({_pct(tp, entry)})  "
            f"SL: {sl} ({_pct(sl, entry)})"
        )
        strats = s.get("strategies", [])
        if strats:
            lines.append(f"   Strats: {', '.join(str(x) for x in strats[:5])}")
        lines.append("")

    # Trim to < 4096
    msg = "\n".join(lines)
    if len(msg) > 4000:
        msg = msg[:3990] + "\n..."
    return msg


def format_chat_signals(data: dict) -> str:
    """Structured text for Electron chat rendering (parsed by SniperRenderer)."""
    signals = data.get("signals", [])
    meta = data.get("meta", {})
    if not signals:
        return "**SCAN SNIPER** — Aucun signal detecte."

    parts = [
        f"**SCAN SNIPER** {meta.get('version', '?')} — "
        f"{meta.get('signals_found', len(signals))} signaux "
        f"/ {meta.get('coins_scanned', '?')} coins "
        f"({meta.get('scan_time_s', '?')}s, "
        f"{meta.get('gpu', 'CPU')})"
    ]

    for s in signals:
        direction = s.get("direction", "?").upper()
        entry = s.get("entry", 0)
        tp = s.get("tp", 0)
        sl = s.get("sl", 0)
        rr = _risk_reward(entry, tp, sl)

        block_lines = [
            f"SIGNAL:{s.get('symbol', '?')}:{direction}:"
            f"{s.get('score', 0)}:{rr}",
            f"Entry: {entry}",
            f"TP: {tp} ({_pct(tp, entry)})",
            f"SL: {sl} ({_pct(sl, entry)})",
            f"RSI: {_r(s.get('rsi'))} | ADX: {_r(s.get('adx'))} | "
            f"MACD: {s.get('macd_signal', '-')}",
            f"MFI: {_r(s.get('mfi'))} | Williams: {_r(s.get('williams_r'))} | "
            f"Regime: {s.get('regime', '-')}",
            f"Vol24h: {_fmt_vol(s.get('volume_24h', 0))} | "
            f"Chg24h: {s.get('change_24h', 0):.1f}% | "
            f"Funding: {s.get('funding_rate', 0):.4f}",
        ]
        strats = s.get("strategies", [])
        if strats:
            block_lines.append(f"Strategies: {', '.join(str(x) for x in strats)}")
        reasons = s.get("reasons", [])
        if reasons:
            block_lines.append(f"Raisons: {'; '.join(str(r) for r in reasons[:5])}")

        parts.append("\n".join(block_lines))

    return "\n---\n".join(parts)


def _r(v) -> str:
    """Round numeric value to 1 decimal, pass-through strings."""
    if v is None:
        return "-"
    if isinstance(v, (int, float)):
        return f"{v:.1f}"
    return str(v)


def _fmt_vol(v: float) -> str:
    """Format volume with K/M suffix."""
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.0f}K"
    return f"{v:.0f}"
