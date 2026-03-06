"""Tests for src/signal_formatter.py — signal parsing and formatting."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.signal_formatter import (
    _fmt_vol,
    _pct,
    _r,
    _risk_reward,
    format_chat_signals,
    format_telegram_signals,
    parse_sniper_json,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_signal():
    """A single well-formed signal dict."""
    return {
        "symbol": "BTCUSDT",
        "direction": "long",
        "score": 85,
        "entry": 50000.0,
        "tp": 51000.0,
        "sl": 49500.0,
        "strategies": ["RSI_Divergence", "MACD_Cross"],
        "rsi": 42.3,
        "adx": 28.7,
        "macd_signal": "bullish",
        "mfi": 55.1,
        "williams_r": -35.6,
        "regime": "trending",
        "volume_24h": 12500000,
        "change_24h": 2.35,
        "funding_rate": 0.0003,
        "reasons": ["RSI oversold bounce", "MACD golden cross"],
    }


@pytest.fixture
def sample_data(sample_signal):
    """Full data dict with signals + meta."""
    return {
        "signals": [sample_signal],
        "meta": {
            "version": "3.5",
            "signals_found": 1,
            "coins_scanned": 150,
            "scan_time_s": 4.2,
            "gpu": "RTX2060",
        },
    }


@pytest.fixture
def multi_signal_data(sample_signal):
    """Data with multiple signals for truncation / iteration tests."""
    signals = []
    for i in range(12):
        s = dict(sample_signal)
        s["symbol"] = f"COIN{i}USDT"
        s["score"] = 90 - i
        signals.append(s)
    return {
        "signals": signals,
        "meta": {
            "version": "3.5",
            "signals_found": 12,
            "coins_scanned": 200,
            "scan_time_s": 6.1,
            "gpu": "RTX3090",
        },
    }


# ---------------------------------------------------------------------------
# Tests: parse_sniper_json
# ---------------------------------------------------------------------------

class TestParseSniperJson:
    """Tests for parse_sniper_json."""

    def test_parse_clean_json(self):
        raw = '{"signals": [{"symbol": "BTC"}], "meta": {}}'
        result = parse_sniper_json(raw)
        assert result is not None
        assert "signals" in result
        assert result["signals"][0]["symbol"] == "BTC"

    def test_parse_json_with_log_prefix(self):
        raw = (
            "[INFO] Loading models...\n"
            "[INFO] Scanning 150 coins...\n"
            '{"signals": [{"symbol": "ETH"}], "meta": {}}'
        )
        result = parse_sniper_json(raw)
        assert result is not None
        assert result["signals"][0]["symbol"] == "ETH"

    def test_parse_empty_string_returns_none(self):
        assert parse_sniper_json("") is None

    def test_parse_no_json_returns_none(self):
        assert parse_sniper_json("just some random log output\nno json here") is None

    def test_parse_invalid_json_returns_none(self):
        assert parse_sniper_json("{broken json [[[") is None

    def test_parse_json_on_last_line(self):
        """Fallback: JSON is on the very last line after garbage."""
        raw = (
            "random garbage\n"
            "more garbage {not json\n"
            '{"signals": [], "meta": {"version": "1.0"}}'
        )
        result = parse_sniper_json(raw)
        assert result is not None
        assert result["meta"]["version"] == "1.0"

    def test_parse_json_without_signals_key(self):
        """A generic JSON object without the 'signals' key still parses."""
        raw = '{"status": "ok", "count": 5}'
        result = parse_sniper_json(raw)
        assert result is not None
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Tests: _risk_reward
# ---------------------------------------------------------------------------

class TestRiskReward:
    """Tests for _risk_reward helper."""

    def test_normal_long(self):
        # entry=100, tp=110, sl=95 -> risk=5, reward=10 -> 1:2.0
        assert _risk_reward(100, 110, 95) == "1:2.0"

    def test_normal_short(self):
        # entry=100, tp=90, sl=105 -> risk=5, reward=10 -> 1:2.0
        assert _risk_reward(100, 90, 105) == "1:2.0"

    def test_zero_risk_returns_na(self):
        # entry == sl => risk = 0
        assert _risk_reward(100, 110, 100) == "N/A"

    def test_equal_tp_and_entry(self):
        # reward = 0, risk = 5 -> 1:0.0
        assert _risk_reward(100, 100, 95) == "1:0.0"

    def test_fractional_values(self):
        result = _risk_reward(1.5, 2.0, 1.0)
        # risk=0.5, reward=0.5 -> 1:1.0
        assert result == "1:1.0"


# ---------------------------------------------------------------------------
# Tests: _pct
# ---------------------------------------------------------------------------

class TestPct:
    """Tests for _pct helper."""

    def test_normal_percentage(self):
        # |110 - 100| / 100 * 100 = 10.00%
        assert _pct(110, 100) == "10.00%"

    def test_zero_ref_returns_zero(self):
        assert _pct(50, 0) == "0%"

    def test_negative_ref_returns_zero(self):
        assert _pct(50, -10) == "0%"

    def test_same_value(self):
        assert _pct(100, 100) == "0.00%"

    def test_small_fraction(self):
        result = _pct(100.5, 100)
        assert result == "0.50%"


# ---------------------------------------------------------------------------
# Tests: _r (round helper)
# ---------------------------------------------------------------------------

class TestRoundHelper:
    """Tests for _r helper."""

    def test_none_returns_dash(self):
        assert _r(None) == "-"

    def test_int_value(self):
        assert _r(42) == "42.0"

    def test_float_value(self):
        assert _r(3.14159) == "3.1"

    def test_string_passthrough(self):
        assert _r("bullish") == "bullish"

    def test_zero(self):
        assert _r(0) == "0.0"


# ---------------------------------------------------------------------------
# Tests: _fmt_vol
# ---------------------------------------------------------------------------

class TestFmtVol:
    """Tests for _fmt_vol helper."""

    def test_millions(self):
        assert _fmt_vol(12_500_000) == "12.5M"

    def test_thousands(self):
        assert _fmt_vol(5_400) == "5K"

    def test_small_value(self):
        assert _fmt_vol(999) == "999"

    def test_exactly_one_million(self):
        assert _fmt_vol(1_000_000) == "1.0M"

    def test_exactly_one_thousand(self):
        assert _fmt_vol(1_000) == "1K"

    def test_zero(self):
        assert _fmt_vol(0) == "0"


# ---------------------------------------------------------------------------
# Tests: format_telegram_signals
# ---------------------------------------------------------------------------

class TestFormatTelegramSignals:
    """Tests for format_telegram_signals."""

    def test_no_signals(self):
        result = format_telegram_signals({"signals": [], "meta": {}})
        assert "Aucun signal" in result

    def test_empty_signals_key(self):
        result = format_telegram_signals({"meta": {}})
        assert "Aucun signal" in result

    def test_single_signal(self, sample_data):
        result = format_telegram_signals(sample_data)
        assert "BTCUSDT" in result
        assert "LONG" in result
        assert "85/100" in result
        assert "3.5" in result  # version
        assert "150" in result  # coins_scanned
        assert "Entry:" in result
        assert "TP:" in result
        assert "SL:" in result

    def test_signal_strategies_shown(self, sample_data):
        result = format_telegram_signals(sample_data)
        assert "RSI_Divergence" in result
        assert "MACD_Cross" in result

    def test_max_10_signals_in_telegram(self, multi_signal_data):
        result = format_telegram_signals(multi_signal_data)
        # The 11th and 12th signals should NOT appear
        assert "COIN0USDT" in result
        assert "COIN9USDT" in result
        assert "COIN10USDT" not in result
        assert "COIN11USDT" not in result

    def test_short_direction_maps_arrow(self, sample_data):
        sample_data["signals"][0]["direction"] = "short"
        result = format_telegram_signals(sample_data)
        assert "\u2B07" in result  # down arrow

    def test_long_direction_maps_arrow(self, sample_data):
        result = format_telegram_signals(sample_data)
        assert "\u2B06" in result  # up arrow

    def test_truncation_at_4000(self):
        """Messages longer than 4000 chars get trimmed."""
        signals = []
        for i in range(10):
            signals.append({
                "symbol": f"VERYLONGSYMBOL{i}USDT",
                "direction": "long",
                "score": 99,
                "entry": 100000.123456789,
                "tp": 200000.987654321,
                "sl": 50000.111111111,
                "strategies": [f"strategy_{j}" for j in range(20)],
            })
        data = {"signals": signals, "meta": {"version": "test"}}
        result = format_telegram_signals(data)
        assert len(result) <= 4096
        if len(result) > 3990:
            assert result.endswith("...")

    def test_missing_fields_use_defaults(self):
        """Signal with almost no fields still formats without errors."""
        data = {"signals": [{}], "meta": {}}
        result = format_telegram_signals(data)
        assert "?" in result  # default direction/symbol
        assert "Entry:" in result

    def test_meta_defaults(self):
        """Missing meta fields fall back to '?'."""
        data = {"signals": [{"symbol": "X", "direction": "long"}], "meta": {}}
        result = format_telegram_signals(data)
        assert "?" in result  # version, coins_scanned, scan_time_s


# ---------------------------------------------------------------------------
# Tests: format_chat_signals
# ---------------------------------------------------------------------------

class TestFormatChatSignals:
    """Tests for format_chat_signals."""

    def test_no_signals(self):
        result = format_chat_signals({"signals": [], "meta": {}})
        assert "Aucun signal" in result
        assert "**SCAN SNIPER**" in result

    def test_empty_signals_key(self):
        result = format_chat_signals({"meta": {}})
        assert "Aucun signal" in result

    def test_single_signal_full(self, sample_data):
        result = format_chat_signals(sample_data)
        assert "**SCAN SNIPER**" in result
        assert "SIGNAL:BTCUSDT:LONG:" in result
        assert "Entry: 50000.0" in result
        assert "TP: 51000.0" in result
        assert "SL: 49500.0" in result
        assert "RSI: 42.3" in result
        assert "ADX: 28.7" in result
        assert "MACD: bullish" in result
        assert "MFI: 55.1" in result
        assert "Regime: trending" in result
        assert "RTX2060" in result

    def test_strategies_in_chat(self, sample_data):
        result = format_chat_signals(sample_data)
        assert "Strategies: RSI_Divergence, MACD_Cross" in result

    def test_reasons_in_chat(self, sample_data):
        result = format_chat_signals(sample_data)
        assert "Raisons:" in result
        assert "RSI oversold bounce" in result

    def test_no_strategies_omits_line(self):
        data = {
            "signals": [{"symbol": "X", "direction": "long", "entry": 1, "tp": 2, "sl": 0.5}],
            "meta": {},
        }
        result = format_chat_signals(data)
        assert "Strategies:" not in result

    def test_no_reasons_omits_line(self):
        data = {
            "signals": [{"symbol": "X", "direction": "long", "entry": 1, "tp": 2, "sl": 0.5}],
            "meta": {},
        }
        result = format_chat_signals(data)
        assert "Raisons:" not in result

    def test_all_signals_included_in_chat(self, multi_signal_data):
        """Unlike Telegram, chat format includes ALL signals."""
        result = format_chat_signals(multi_signal_data)
        for i in range(12):
            assert f"COIN{i}USDT" in result

    def test_sections_separated_by_dashes(self, multi_signal_data):
        result = format_chat_signals(multi_signal_data)
        assert "---" in result

    def test_missing_indicator_fields(self):
        """Signals missing rsi/adx/mfi/williams_r show '-'."""
        data = {
            "signals": [{"symbol": "Y", "direction": "short", "entry": 10, "tp": 8, "sl": 11}],
            "meta": {},
        }
        result = format_chat_signals(data)
        assert "RSI: -" in result
        assert "ADX: -" in result
        assert "MFI: -" in result
        assert "Williams: -" in result

    def test_volume_formatting_in_chat(self, sample_data):
        result = format_chat_signals(sample_data)
        assert "12.5M" in result  # 12500000 -> 12.5M

    def test_funding_rate_precision(self, sample_data):
        result = format_chat_signals(sample_data)
        assert "0.0003" in result

    def test_change_24h_one_decimal(self, sample_data):
        result = format_chat_signals(sample_data)
        assert "2.3%" in result or "2.4%" in result  # 2.35 rounded to 1 decimal


# ---------------------------------------------------------------------------
# Tests: edge cases & integration
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases and integration scenarios."""

    def test_parse_then_format_telegram(self):
        """End-to-end: raw stdout -> parse -> telegram format."""
        raw = json.dumps({
            "signals": [
                {"symbol": "SOLUSDT", "direction": "long", "score": 72,
                 "entry": 25.0, "tp": 26.0, "sl": 24.5, "strategies": ["Breakout"]}
            ],
            "meta": {"version": "3.5", "signals_found": 1, "coins_scanned": 50, "scan_time_s": 1.0}
        })
        data = parse_sniper_json(raw)
        assert data is not None
        msg = format_telegram_signals(data)
        assert "SOLUSDT" in msg
        assert "72/100" in msg

    def test_parse_then_format_chat(self):
        """End-to-end: raw stdout -> parse -> chat format."""
        raw = json.dumps({
            "signals": [
                {"symbol": "ETHUSDT", "direction": "short", "score": 60,
                 "entry": 3000.0, "tp": 2900.0, "sl": 3050.0,
                 "rsi": 78.2, "adx": 15.0, "macd_signal": "bearish",
                 "mfi": 80.0, "williams_r": -10.0, "regime": "ranging",
                 "volume_24h": 500000, "change_24h": -1.5, "funding_rate": -0.0001}
            ],
            "meta": {"version": "3.5", "signals_found": 1, "coins_scanned": 100,
                     "scan_time_s": 2.0, "gpu": "CPU"}
        })
        data = parse_sniper_json(raw)
        assert data is not None
        msg = format_chat_signals(data)
        assert "SIGNAL:ETHUSDT:SHORT:" in msg
        assert "RSI: 78.2" in msg
        assert "CPU" in msg

    def test_completely_empty_data(self):
        """Empty dict should not crash."""
        assert "Aucun signal" in format_telegram_signals({})
        assert "Aucun signal" in format_chat_signals({})

    def test_signal_with_zero_values(self):
        """All-zero numeric fields should not crash."""
        data = {
            "signals": [{
                "symbol": "ZERO",
                "direction": "long",
                "score": 0,
                "entry": 0,
                "tp": 0,
                "sl": 0,
                "rsi": 0,
                "adx": 0,
                "mfi": 0,
                "williams_r": 0,
                "volume_24h": 0,
                "change_24h": 0,
                "funding_rate": 0,
            }],
            "meta": {},
        }
        tg = format_telegram_signals(data)
        assert "ZERO" in tg
        chat = format_chat_signals(data)
        assert "ZERO" in chat

    def test_reasons_limited_to_five(self):
        """Chat format truncates reasons to 5 items."""
        data = {
            "signals": [{
                "symbol": "X",
                "direction": "long",
                "entry": 1, "tp": 2, "sl": 0.5,
                "reasons": [f"reason_{i}" for i in range(10)],
            }],
            "meta": {},
        }
        result = format_chat_signals(data)
        assert "reason_4" in result
        assert "reason_5" not in result

    def test_strategies_limited_to_five_in_telegram(self):
        """Telegram format truncates strategies to 5 items."""
        data = {
            "signals": [{
                "symbol": "X",
                "direction": "long",
                "entry": 1, "tp": 2, "sl": 0.5,
                "strategies": [f"strat_{i}" for i in range(10)],
            }],
            "meta": {},
        }
        result = format_telegram_signals(data)
        assert "strat_4" in result
        assert "strat_5" not in result
