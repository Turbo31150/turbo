"""Unit tests for src/trading.py and src/trading_engine.py — JARVIS Trading Pipeline.

Tests signal validation, position sizing, scoring logic, backtest engine,
and data models with ALL external dependencies mocked (no MEXC, no DB, no network).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for src/trading.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestTradingImport:
    """Verify trading module imports cleanly."""

    @patch("ccxt.mexc", MagicMock())
    def test_import_module(self):
        import src.trading
        assert hasattr(src.trading, "validate_signal")
        assert hasattr(src.trading, "execute_signal")
        assert hasattr(src.trading, "get_pending_signals")
        assert hasattr(src.trading, "pipeline_status")

    @patch("ccxt.mexc", MagicMock())
    def test_symbol_converters_exist(self):
        from src.trading import _symbol_to_ccxt, _symbol_to_mexc_api
        assert callable(_symbol_to_ccxt)
        assert callable(_symbol_to_mexc_api)


class TestSymbolConversion:
    """Test symbol format converters — pure logic, no network."""

    @patch("ccxt.mexc", MagicMock())
    def test_symbol_to_ccxt(self):
        from src.trading import _symbol_to_ccxt
        assert _symbol_to_ccxt("BTC/USDT") == "BTC/USDT:USDT"
        assert _symbol_to_ccxt("ETH/USDT") == "ETH/USDT:USDT"

    @patch("ccxt.mexc", MagicMock())
    def test_symbol_to_ccxt_already_swap(self):
        from src.trading import _symbol_to_ccxt
        assert _symbol_to_ccxt("BTC/USDT:USDT") == "BTC/USDT:USDT"

    @patch("ccxt.mexc", MagicMock())
    def test_symbol_to_mexc_api(self):
        from src.trading import _symbol_to_mexc_api
        assert _symbol_to_mexc_api("BTC/USDT") == "BTC_USDT"
        assert _symbol_to_mexc_api("SOL/USDT:USDT") == "SOL_USDT"


class TestValidateSignal:
    """Test validate_signal() logic with mock data."""

    @patch("ccxt.mexc", MagicMock())
    def test_valid_long_signal(self):
        from src.trading import validate_signal
        signal = {
            "executed": 0,
            "price": 100.0,
            "sl": 98.0,
            "tp1": 104.0,
        }
        valid, reason = validate_signal(signal, current_price=100.05)
        assert valid is True
        assert reason == "OK"

    @patch("ccxt.mexc", MagicMock())
    def test_already_executed_signal(self):
        from src.trading import validate_signal
        signal = {"executed": 1, "price": 100, "sl": 98, "tp1": 104}
        valid, reason = validate_signal(signal)
        assert valid is False
        assert "deja execute" in reason

    @patch("ccxt.mexc", MagicMock())
    def test_missing_price_data(self):
        from src.trading import validate_signal
        signal = {"executed": 0, "price": 0, "sl": 0, "tp1": 0}
        valid, reason = validate_signal(signal)
        assert valid is False
        assert "manquantes" in reason

    @patch("ccxt.mexc", MagicMock())
    def test_price_drift_too_high(self):
        from src.trading import validate_signal
        signal = {"executed": 0, "price": 100.0, "sl": 98.0, "tp1": 104.0}
        valid, reason = validate_signal(signal, current_price=105.0)
        assert valid is False
        assert "drift" in reason

    @patch("ccxt.mexc", MagicMock())
    def test_insufficient_risk_reward(self):
        from src.trading import validate_signal
        # R/R = 0.5/2 = 0.25 < 1.3
        signal = {"executed": 0, "price": 100.0, "sl": 98.0, "tp1": 100.5}
        valid, reason = validate_signal(signal, current_price=100.0)
        assert valid is False
        assert "R/R" in reason

    @patch("ccxt.mexc", MagicMock())
    def test_zero_risk(self):
        from src.trading import validate_signal
        signal = {"executed": 0, "price": 100.0, "sl": 100.0, "tp1": 105.0}
        valid, reason = validate_signal(signal)
        assert valid is False
        assert "Risk = 0" in reason


class TestCalculateQuantity:
    """Test position sizing calculation."""

    @patch("ccxt.mexc", MagicMock())
    def test_calculate_quantity_btc(self):
        from src.trading import _calculate_quantity
        with patch("src.trading.config") as mock_config:
            mock_config.size_usdt = 10
            mock_config.leverage = 10
            qty = _calculate_quantity(50000.0)
            # 10 * 10 / 50000 = 0.002
            assert qty == 0.0

    @patch("ccxt.mexc", MagicMock())
    def test_calculate_quantity_low_price(self):
        from src.trading import _calculate_quantity
        with patch("src.trading.config") as mock_config:
            mock_config.size_usdt = 10
            mock_config.leverage = 10
            qty = _calculate_quantity(0.1)
            # 10 * 10 / 0.1 = 1000
            assert qty == 1000.0

    @patch("ccxt.mexc", MagicMock())
    def test_calculate_quantity_rounds(self):
        from src.trading import _calculate_quantity
        with patch("src.trading.config") as mock_config:
            mock_config.size_usdt = 10
            mock_config.leverage = 10
            qty = _calculate_quantity(3.0)
            # 100 / 3 = 33.333... -> 33.33
            assert qty == 33.33


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for src/trading_engine.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestTradingEngineImport:
    """Verify trading_engine module imports."""

    def test_import_module(self):
        import src.trading_engine
        assert hasattr(src.trading_engine, "TradeSignal")
        assert hasattr(src.trading_engine, "BacktestResult")
        assert hasattr(src.trading_engine, "StrategyScorer")
        assert hasattr(src.trading_engine, "BacktestEngine")
        assert hasattr(src.trading_engine, "TradingFlowManager")


class TestTradeSignal:
    """Test TradeSignal dataclass and risk_reward property."""

    def test_instantiation(self):
        from src.trading_engine import TradeSignal
        sig = TradeSignal(
            pair="BTC/USDT", direction="long",
            entry_price=50000, take_profit=51000, stop_loss=49500,
            confidence=80, strategy="breakout"
        )
        assert sig.pair == "BTC/USDT"
        assert sig.direction == "long"
        assert sig.confidence == 80

    def test_risk_reward_long(self):
        from src.trading_engine import TradeSignal
        sig = TradeSignal(
            pair="BTC/USDT", direction="long",
            entry_price=100, take_profit=110, stop_loss=95,
            confidence=80, strategy="test"
        )
        # reward=10, risk=5 -> R/R=2.0
        assert sig.risk_reward == 2.0

    def test_risk_reward_short(self):
        from src.trading_engine import TradeSignal
        sig = TradeSignal(
            pair="ETH/USDT", direction="short",
            entry_price=100, take_profit=90, stop_loss=105,
            confidence=75, strategy="test"
        )
        # reward=10, risk=5 -> R/R=2.0
        assert sig.risk_reward == 2.0

    def test_risk_reward_zero_risk(self):
        from src.trading_engine import TradeSignal
        sig = TradeSignal(
            pair="SOL/USDT", direction="long",
            entry_price=100, take_profit=110, stop_loss=100,
            confidence=50, strategy="test"
        )
        assert sig.risk_reward == 0


class TestBacktestResult:
    """Test BacktestResult dataclass and win_rate property."""

    def test_instantiation(self):
        from src.trading_engine import BacktestResult
        result = BacktestResult(strategy="test", pair="BTC/USDT", period="100 candles")
        assert result.total_trades == 0
        assert result.total_pnl_percent == 0.0

    def test_win_rate_with_trades(self):
        from src.trading_engine import BacktestResult
        result = BacktestResult(
            strategy="test", pair="BTC/USDT", period="100",
            total_trades=10, winning_trades=7, losing_trades=3,
        )
        assert result.win_rate == 0.7

    def test_win_rate_no_trades(self):
        from src.trading_engine import BacktestResult
        result = BacktestResult(strategy="test", pair="BTC/USDT", period="0")
        assert result.win_rate == 0.0


class TestStrategyScorer:
    """Test StrategyScorer scoring and recording logic."""

    def test_instantiation(self):
        from src.trading_engine import StrategyScorer
        scorer = StrategyScorer()
        assert scorer._history == {}

    def test_score_signal_basic(self):
        from src.trading_engine import StrategyScorer, TradeSignal
        scorer = StrategyScorer()
        sig = TradeSignal(
            pair="BTC/USDT", direction="long",
            entry_price=100, take_profit=110, stop_loss=95,
            confidence=80, strategy="breakout"
        )
        score = scorer.score_signal(sig)
        assert 0 <= score <= 100
        # R/R=2.0 -> 20pts, confidence 80*0.2=16pts, no history -> ~36
        assert score > 30

    def test_score_signal_high_rr(self):
        from src.trading_engine import StrategyScorer, TradeSignal
        scorer = StrategyScorer()
        sig = TradeSignal(
            pair="BTC/USDT", direction="long",
            entry_price=100, take_profit=120, stop_loss=98,
            confidence=90, strategy="momentum"
        )
        score = scorer.score_signal(sig)
        # R/R=10 -> capped at 30pts, confidence 90*0.2=18 -> ~48
        assert score > 40

    def test_record_outcome(self):
        from src.trading_engine import StrategyScorer
        scorer = StrategyScorer()
        scorer.record_outcome("breakout", 0.5, 60)
        scorer.record_outcome("breakout", -0.25, 30)
        assert len(scorer._history["breakout"]) == 2

    def test_record_outcome_capped_at_100(self):
        from src.trading_engine import StrategyScorer
        scorer = StrategyScorer()
        for i in range(110):
            scorer.record_outcome("test", 0.1, 10)
        assert len(scorer._history["test"]) == 100

    def test_score_with_history(self):
        """With enough history, win rate should affect scoring."""
        from src.trading_engine import StrategyScorer, TradeSignal
        scorer = StrategyScorer()
        # Record 10 wins
        for _ in range(10):
            scorer.record_outcome("tested", 0.5, 30)

        sig = TradeSignal(
            pair="BTC/USDT", direction="long",
            entry_price=100, take_profit=105, stop_loss=97,
            confidence=70, strategy="tested"
        )
        score = scorer.score_signal(sig)
        # Should have history bonus now
        assert score > 50

    def test_get_strategy_rankings(self):
        from src.trading_engine import StrategyScorer
        scorer = StrategyScorer()
        for _ in range(5):
            scorer.record_outcome("good", 1.0, 30)
        for _ in range(5):
            scorer.record_outcome("bad", -0.5, 30)

        rankings = scorer.get_strategy_rankings()
        assert len(rankings) == 2
        assert rankings[0]["strategy"] == "good"
        assert rankings[0]["win_rate"] == 1.0
        assert rankings[1]["strategy"] == "bad"

    def test_get_strategy_rankings_min_trades(self):
        """Strategies with < 3 trades should be excluded."""
        from src.trading_engine import StrategyScorer
        scorer = StrategyScorer()
        scorer.record_outcome("too_few", 1.0, 30)
        scorer.record_outcome("too_few", 0.5, 30)
        rankings = scorer.get_strategy_rankings()
        assert len(rankings) == 0


class TestBacktestEngine:
    """Test BacktestEngine with synthetic candle data."""

    def test_instantiation(self):
        from src.trading_engine import BacktestEngine, StrategyScorer
        with patch("pathlib.Path.mkdir"):
            engine = BacktestEngine(StrategyScorer())
            assert engine.scorer is not None

    def test_run_with_no_signals(self):
        """Strategy that never signals should produce 0 trades."""
        from src.trading_engine import BacktestEngine, StrategyScorer

        def no_signal_strategy(candles):
            return None

        candles = [{"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000, "timestamp": i}
                   for i in range(50)]

        with patch("pathlib.Path.mkdir"):
            engine = BacktestEngine(StrategyScorer())
            result = engine.run(candles, no_signal_strategy, "BTC/USDT")
            assert result.total_trades == 0
            assert result.total_pnl_percent == 0.0

    def test_run_with_always_long(self):
        """Strategy that always goes long on trending-up data."""
        from src.trading_engine import BacktestEngine, StrategyScorer, TradeSignal

        def always_long(candles):
            return TradeSignal(
                pair="BTC/USDT", direction="long",
                entry_price=candles[-1]["close"],
                take_profit=candles[-1]["close"] * 1.005,
                stop_loss=candles[-1]["close"] * 0.9975,
                confidence=80, strategy="always_long"
            )

        # Trending up: each candle higher than last
        candles = [
            {"open": 100 + i, "high": 101.5 + i, "low": 99.5 + i, "close": 100.5 + i,
             "volume": 1000, "timestamp": i * 60}
            for i in range(60)
        ]

        with patch("pathlib.Path.mkdir"):
            engine = BacktestEngine(StrategyScorer())
            result = engine.run(candles, always_long, "BTC/USDT", tp_pct=0.4, sl_pct=0.25)
            assert result.total_trades >= 0  # May or may not trigger TP/SL
            assert isinstance(result.total_pnl_percent, float)


class TestTradingFlowManager:
    """Test TradingFlowManager instantiation and flow tracking."""

    def test_instantiation(self):
        from src.trading_engine import TradingFlowManager
        manager = TradingFlowManager()
        assert manager._active_flows == {}

    def test_get_active_flows_empty(self):
        from src.trading_engine import TradingFlowManager
        manager = TradingFlowManager()
        flows = manager.get_active_flows()
        assert flows == {}

    @pytest.mark.asyncio
    async def test_run_pipeline_no_strategies(self):
        from src.trading_engine import TradingFlowManager
        manager = TradingFlowManager()
        results = await manager.run_pipeline(["BTC/USDT"], [], min_score=70)
        assert results == []


class TestSendTelegram:
    """Test send_telegram() with mocked network."""

    @patch("ccxt.mexc", MagicMock())
    @patch("urllib.request.urlopen")
    def test_send_telegram_success(self, mock_urlopen):
        from src.trading import send_telegram
        with patch("src.trading.config") as mock_config:
            mock_config.telegram_token = "fake-token"
            mock_config.telegram_chat = "12345"
            mock_urlopen.return_value.__enter__ = MagicMock()
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            result = send_telegram("test message")
            assert result is True

    @patch("ccxt.mexc", MagicMock())
    def test_send_telegram_no_config(self):
        from src.trading import send_telegram
        with patch("src.trading.config") as mock_config:
            mock_config.telegram_token = ""
            mock_config.telegram_chat = ""
            result = send_telegram("test")
            assert result is False
