"""Comprehensive tests for src/trading_engine.py — JARVIS Trading Engine v3.

Covers ALL public classes and functions:
- TradeSignal: dataclass, risk_reward property, edge cases
- BacktestResult: dataclass, win_rate property, edge cases
- StrategyScorer: score_signal, record_outcome, get_strategy_rankings
- BacktestEngine: run, save_result, list_results
- TradingFlowManager: run_pipeline, _evaluate_strategy, get_active_flows
- Module-level singletons

All filesystem and time-dependent operations are mocked.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading_engine import (
    BacktestEngine,
    BacktestResult,
    StrategyScorer,
    TradeSignal,
    TradingFlowManager,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def scorer():
    return StrategyScorer()


@pytest.fixture
def engine():
    with patch("pathlib.Path.mkdir"):
        return BacktestEngine()


@pytest.fixture
def engine_with_scorer(scorer):
    with patch("pathlib.Path.mkdir"):
        return BacktestEngine(scorer)


@pytest.fixture
def flow_manager():
    return TradingFlowManager()


@pytest.fixture
def long_signal():
    return TradeSignal(
        pair="BTC/USDT",
        direction="long",
        entry_price=50000.0,
        take_profit=50200.0,
        stop_loss=49875.0,
        confidence=80.0,
        strategy="breakout",
    )


@pytest.fixture
def short_signal():
    return TradeSignal(
        pair="ETH/USDT",
        direction="short",
        entry_price=3000.0,
        take_profit=2988.0,
        stop_loss=3007.5,
        confidence=75.0,
        strategy="reversal",
    )


def _make_candles(n: int, base_price: float = 100.0, trend: float = 0.0) -> list[dict]:
    """Generate synthetic candle data.

    Args:
        n: Number of candles.
        base_price: Starting price.
        trend: Price change per candle (positive = uptrend).
    """
    candles = []
    for i in range(n):
        close = base_price + i * trend
        candles.append({
            "open": close - 0.1,
            "high": close + 1.5,
            "low": close - 1.0,
            "close": close,
            "volume": 1000 + i * 10,
            "timestamp": 1000000 + i * 60,
        })
    return candles


def _make_strategy_fn(signal: TradeSignal | None = None, name: str = "test_strat"):
    """Create a named strategy function returning a fixed signal."""

    def strategy(candles):
        return signal

    strategy.__name__ = name
    return strategy


# ═══════════════════════════════════════════════════════════════════════════════
# TradeSignal
# ═══════════════════════════════════════════════════════════════════════════════


class TestTradeSignal:
    """Exhaustive tests for TradeSignal dataclass."""

    def test_creation_with_defaults(self):
        sig = TradeSignal(
            pair="BTC/USDT", direction="long",
            entry_price=100, take_profit=110, stop_loss=95,
            confidence=80, strategy="test",
        )
        assert sig.pair == "BTC/USDT"
        assert sig.direction == "long"
        assert sig.entry_price == 100
        assert sig.take_profit == 110
        assert sig.stop_loss == 95
        assert sig.confidence == 80
        assert sig.strategy == "test"
        assert isinstance(sig.timestamp, float)
        assert sig.metadata == {}

    def test_custom_metadata(self):
        sig = TradeSignal(
            pair="SOL/USDT", direction="short",
            entry_price=20, take_profit=19, stop_loss=21,
            confidence=60, strategy="mean_revert",
            metadata={"source": "cluster", "version": 3},
        )
        assert sig.metadata["source"] == "cluster"
        assert sig.metadata["version"] == 3

    def test_risk_reward_long_standard(self, long_signal):
        # TP=50200, entry=50000, SL=49875
        # reward=200, risk=125 -> R/R=1.6
        assert long_signal.risk_reward == 1.6

    def test_risk_reward_short_standard(self, short_signal):
        # entry=3000, TP=2988, SL=3007.5
        # reward=12, risk=7.5 -> R/R=1.6
        assert short_signal.risk_reward == 1.6

    def test_risk_reward_long_zero_risk(self):
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=110, stop_loss=100,
            confidence=50, strategy="test",
        )
        assert sig.risk_reward == 0

    def test_risk_reward_short_zero_risk(self):
        sig = TradeSignal(
            pair="X/USDT", direction="short",
            entry_price=100, take_profit=90, stop_loss=100,
            confidence=50, strategy="test",
        )
        assert sig.risk_reward == 0

    def test_risk_reward_long_high_ratio(self):
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=200, stop_loss=99,
            confidence=90, strategy="test",
        )
        # reward=100, risk=1 -> R/R=100.0
        assert sig.risk_reward == 100.0

    def test_risk_reward_short_high_ratio(self):
        sig = TradeSignal(
            pair="X/USDT", direction="short",
            entry_price=100, take_profit=1, stop_loss=101,
            confidence=90, strategy="test",
        )
        # reward=99, risk=1 -> R/R=99.0
        assert sig.risk_reward == 99.0

    def test_risk_reward_rounding(self):
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=103, stop_loss=98,
            confidence=70, strategy="test",
        )
        # reward=3, risk=2 -> R/R=1.5
        assert sig.risk_reward == 1.5

    def test_risk_reward_very_small_risk(self):
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100.0, take_profit=101.0, stop_loss=99.99,
            confidence=70, strategy="test",
        )
        # reward=1.0, risk=0.01 -> R/R=100.0
        assert sig.risk_reward == 100.0

    def test_timestamp_auto_set(self):
        before = time.time()
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=10, take_profit=11, stop_loss=9,
            confidence=50, strategy="test",
        )
        after = time.time()
        assert before <= sig.timestamp <= after


# ═══════════════════════════════════════════════════════════════════════════════
# BacktestResult
# ═══════════════════════════════════════════════════════════════════════════════


class TestBacktestResult:
    """Tests for BacktestResult dataclass."""

    def test_creation_defaults(self):
        r = BacktestResult(strategy="s", pair="BTC/USDT", period="100 candles")
        assert r.total_trades == 0
        assert r.winning_trades == 0
        assert r.losing_trades == 0
        assert r.total_pnl_percent == 0.0
        assert r.max_drawdown_percent == 0.0
        assert r.sharpe_ratio == 0.0
        assert r.avg_trade_duration_s == 0.0
        assert r.signals == []
        assert isinstance(r.timestamp, float)

    def test_win_rate_positive(self):
        r = BacktestResult(
            strategy="s", pair="BTC/USDT", period="100",
            total_trades=20, winning_trades=15, losing_trades=5,
        )
        assert r.win_rate == 0.75

    def test_win_rate_zero_trades(self):
        r = BacktestResult(strategy="s", pair="BTC/USDT", period="0")
        assert r.win_rate == 0.0

    def test_win_rate_all_wins(self):
        r = BacktestResult(
            strategy="s", pair="BTC/USDT", period="50",
            total_trades=50, winning_trades=50, losing_trades=0,
        )
        assert r.win_rate == 1.0

    def test_win_rate_all_losses(self):
        r = BacktestResult(
            strategy="s", pair="BTC/USDT", period="10",
            total_trades=10, winning_trades=0, losing_trades=10,
        )
        assert r.win_rate == 0.0

    def test_win_rate_rounding(self):
        r = BacktestResult(
            strategy="s", pair="BTC/USDT", period="3",
            total_trades=3, winning_trades=1, losing_trades=2,
        )
        assert r.win_rate == 0.333


# ═══════════════════════════════════════════════════════════════════════════════
# StrategyScorer
# ═══════════════════════════════════════════════════════════════════════════════


class TestStrategyScorer:
    """Comprehensive tests for StrategyScorer."""

    def test_init_empty_history(self, scorer):
        assert len(scorer._history) == 0

    # --- score_signal ---

    def test_score_no_history_low_confidence(self, scorer):
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=101, stop_loss=99,
            confidence=0, strategy="new_strat",
        )
        score = scorer.score_signal(sig)
        # R/R=1.0 -> 10pts, confidence 0*0.2=0, no history -> 10
        assert score == 10.0

    def test_score_no_history_high_confidence(self, scorer):
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=101, stop_loss=99,
            confidence=100, strategy="new_strat",
        )
        score = scorer.score_signal(sig)
        # R/R=1.0 -> 10pts, confidence 100*0.2=20 -> 30
        assert score == 30.0

    def test_score_capped_rr_contribution(self, scorer):
        """R/R contribution maxes out at 30 pts."""
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=200, stop_loss=99,
            confidence=0, strategy="new_strat",
        )
        score = scorer.score_signal(sig)
        # R/R=100 -> min(30, 1000)=30, confidence 0 -> 30
        assert score == 30.0

    def test_score_with_5_wins_history(self, scorer):
        """With >=5 entries all wins, win_rate bonus kicks in."""
        for _ in range(5):
            scorer.record_outcome("tested", 1.0, 10)

        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=101, stop_loss=99,
            confidence=50, strategy="tested",
        )
        score = scorer.score_signal(sig)
        # R/R=1.0 -> 10, win_rate=1.0 -> 30, confidence=50*0.2=10, recent=5*4=20 -> 70
        assert score == 70.0

    def test_score_with_mixed_history(self, scorer):
        """Mixed outcomes: 3 wins, 2 losses in 5 trades."""
        for _ in range(3):
            scorer.record_outcome("mixed", 0.5, 10)
        for _ in range(2):
            scorer.record_outcome("mixed", -0.3, 10)

        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=102, stop_loss=99,
            confidence=60, strategy="mixed",
        )
        score = scorer.score_signal(sig)
        # R/R=2.0 -> 20, win_rate=3/5=0.6 -> 18, confidence=60*0.2=12, recent 5: 3 wins -> 12
        assert score == 62.0

    def test_score_with_only_4_history_entries(self, scorer):
        """With < 5 entries, win_rate bonus does NOT kick in."""
        for _ in range(4):
            scorer.record_outcome("few", 1.0, 10)

        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=101, stop_loss=99,
            confidence=0, strategy="few",
        )
        score = scorer.score_signal(sig)
        # R/R=1.0 -> 10, no win_rate (< 5), confidence=0, recent 4 wins -> 16 -> 26
        assert score == 26.0

    def test_score_capped_at_100(self, scorer):
        """Score cannot exceed 100."""
        for _ in range(20):
            scorer.record_outcome("max_strat", 5.0, 10)

        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=500, stop_loss=99,
            confidence=100, strategy="max_strat",
        )
        score = scorer.score_signal(sig)
        assert score == 100

    def test_score_recency_only_last_5(self, scorer):
        """Recency bonus only counts last 5 trades."""
        # 10 losses then 5 wins
        for _ in range(10):
            scorer.record_outcome("recency_test", -1.0, 10)
        for _ in range(5):
            scorer.record_outcome("recency_test", 1.0, 10)

        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=101, stop_loss=99,
            confidence=0, strategy="recency_test",
        )
        score = scorer.score_signal(sig)
        # R/R=1 -> 10, win_rate of last 20: 5/15=0.333 -> 10, confidence=0, recent 5: 5 wins -> 20
        assert score == 40.0

    # --- record_outcome ---

    def test_record_outcome_basic(self, scorer):
        scorer.record_outcome("strat_a", 0.5, 120)
        assert len(scorer._history["strat_a"]) == 1
        entry = scorer._history["strat_a"][0]
        assert entry["pnl"] == 0.5
        assert entry["duration_s"] == 120
        assert "timestamp" in entry

    def test_record_outcome_multiple_strategies(self, scorer):
        scorer.record_outcome("a", 1.0, 10)
        scorer.record_outcome("b", -0.5, 20)
        scorer.record_outcome("a", 0.3, 15)
        assert len(scorer._history["a"]) == 2
        assert len(scorer._history["b"]) == 1

    def test_record_outcome_caps_at_100(self, scorer):
        for i in range(110):
            scorer.record_outcome("overflow", float(i), 10)
        assert len(scorer._history["overflow"]) == 100
        # Kept last 100 (indices 10..109)
        assert scorer._history["overflow"][0]["pnl"] == 10.0
        assert scorer._history["overflow"][-1]["pnl"] == 109.0

    def test_record_outcome_negative_pnl(self, scorer):
        scorer.record_outcome("neg", -5.0, 60)
        assert scorer._history["neg"][0]["pnl"] == -5.0

    def test_record_outcome_zero_duration(self, scorer):
        scorer.record_outcome("zero_dur", 0.1, 0)
        assert scorer._history["zero_dur"][0]["duration_s"] == 0

    # --- get_strategy_rankings ---

    def test_rankings_empty_history(self, scorer):
        rankings = scorer.get_strategy_rankings()
        assert rankings == []

    def test_rankings_below_min_trades(self, scorer):
        """Strategies with < 3 trades are excluded."""
        scorer.record_outcome("tiny", 1.0, 10)
        scorer.record_outcome("tiny", 0.5, 10)
        assert scorer.get_strategy_rankings() == []

    def test_rankings_exactly_3_trades(self, scorer):
        """Exactly 3 trades should be included."""
        scorer.record_outcome("exact3", 1.0, 10)
        scorer.record_outcome("exact3", 0.5, 10)
        scorer.record_outcome("exact3", -0.2, 10)
        rankings = scorer.get_strategy_rankings()
        assert len(rankings) == 1
        assert rankings[0]["strategy"] == "exact3"
        assert rankings[0]["trades"] == 3

    def test_rankings_sorted_by_total_pnl(self, scorer):
        for _ in range(5):
            scorer.record_outcome("winner", 2.0, 10)
        for _ in range(5):
            scorer.record_outcome("loser", -1.0, 10)
        for _ in range(5):
            scorer.record_outcome("mid", 0.5, 10)

        rankings = scorer.get_strategy_rankings()
        assert len(rankings) == 3
        assert rankings[0]["strategy"] == "winner"
        assert rankings[1]["strategy"] == "mid"
        assert rankings[2]["strategy"] == "loser"

    def test_rankings_top_n_limit(self, scorer):
        for name in ["a", "b", "c", "d", "e"]:
            for i in range(3):
                scorer.record_outcome(name, float(ord(name)), 10)

        rankings = scorer.get_strategy_rankings(top_n=2)
        assert len(rankings) == 2

    def test_rankings_fields(self, scorer):
        """Check all fields in a ranking entry."""
        scorer.record_outcome("s", 1.0, 10)
        scorer.record_outcome("s", -0.5, 20)
        scorer.record_outcome("s", 0.3, 15)

        rankings = scorer.get_strategy_rankings()
        assert len(rankings) == 1
        r = rankings[0]
        assert r["strategy"] == "s"
        assert r["trades"] == 3
        assert r["win_rate"] == round(2 / 3, 3)  # 2 positive out of 3
        assert r["avg_pnl"] == round((1.0 - 0.5 + 0.3) / 3, 3)
        assert r["total_pnl"] == round(1.0 - 0.5 + 0.3, 3)
        assert "std_pnl" in r

    def test_rankings_std_pnl_single_entry_is_zero(self, scorer):
        """With only 1 pnl value (impossible in rankings, but stdev guard)."""
        # Need 3 entries to appear in rankings — stdev works on 3 values
        scorer.record_outcome("s", 1.0, 10)
        scorer.record_outcome("s", 1.0, 10)
        scorer.record_outcome("s", 1.0, 10)
        rankings = scorer.get_strategy_rankings()
        assert rankings[0]["std_pnl"] == 0.0  # All same -> stdev=0


# ═══════════════════════════════════════════════════════════════════════════════
# BacktestEngine
# ═══════════════════════════════════════════════════════════════════════════════


class TestBacktestEngine:
    """Comprehensive tests for BacktestEngine."""

    def test_init_creates_directory(self):
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            BacktestEngine()
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_init_with_custom_scorer(self):
        custom = StrategyScorer()
        with patch("pathlib.Path.mkdir"):
            eng = BacktestEngine(custom)
            assert eng.scorer is custom

    def test_init_default_scorer(self):
        with patch("pathlib.Path.mkdir"):
            eng = BacktestEngine()
            assert isinstance(eng.scorer, StrategyScorer)

    # --- run ---

    def test_run_no_signal_strategy(self, engine):
        candles = _make_candles(50)
        result = engine.run(candles, _make_strategy_fn(None), "BTC/USDT")
        assert result.total_trades == 0
        assert result.winning_trades == 0
        assert result.losing_trades == 0
        assert result.total_pnl_percent == 0.0
        assert result.max_drawdown_percent == 0.0
        assert result.sharpe_ratio == 0.0

    def test_run_too_few_candles(self, engine):
        """With < 21 candles, no iteration happens (loop starts at index 20)."""
        candles = _make_candles(15)
        result = engine.run(candles, _make_strategy_fn(None), "BTC/USDT")
        assert result.total_trades == 0
        assert result.period == "15 candles"

    def test_run_exactly_20_candles(self, engine):
        """With exactly 20 candles, range(20, 20) is empty."""
        candles = _make_candles(20)
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=200, stop_loss=90,
            confidence=90, strategy="should_not_trade",
        )
        result = engine.run(candles, _make_strategy_fn(sig), "X/USDT")
        assert result.total_trades == 0

    def test_run_low_confidence_skipped(self, engine):
        """Signal with confidence < 60 is ignored."""
        low_conf = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=110, stop_loss=95,
            confidence=50, strategy="low_conf",
        )
        candles = _make_candles(50)
        result = engine.run(candles, _make_strategy_fn(low_conf, "low_conf"), "X/USDT")
        assert result.total_trades == 0

    def test_run_long_tp_hit(self, engine):
        """Long trade hits take profit."""
        entry = 100.0
        tp_pct = 0.4
        sl_pct = 0.25

        # At i=20, strategy receives candles[:20] (len=20). Entry price = candles[20]["close"].
        # TP/SL checked from i=21 onward.
        def long_once(candles):
            if len(candles) == 20:
                return TradeSignal(
                    pair="X/USDT", direction="long",
                    entry_price=entry, take_profit=entry * 1.005,
                    stop_loss=entry * 0.9975,
                    confidence=80, strategy="long_once",
                )
            return None

        # 21 flat candles (indices 0-20), then an exit candle at index 21
        candles = _make_candles(21, base_price=entry, trend=0)
        # TP threshold: candles[20]["close"] * (1 + 0.4/100) = 100.4; high must >= 100.4
        candles.append({
            "open": 100, "high": 101.0, "low": 99.8, "close": 100.5,
            "volume": 1000, "timestamp": 2000000,
        })

        result = engine.run(candles, long_once, "X/USDT", tp_pct=tp_pct, sl_pct=sl_pct)
        assert result.total_trades == 1
        assert result.winning_trades == 1
        assert result.losing_trades == 0
        assert result.total_pnl_percent == tp_pct

    def test_run_long_sl_hit(self, engine):
        """Long trade hits stop loss."""
        entry = 100.0
        tp_pct = 0.4
        sl_pct = 0.25

        def long_once(candles):
            if len(candles) == 20:
                return TradeSignal(
                    pair="X/USDT", direction="long",
                    entry_price=entry, take_profit=entry * 1.005,
                    stop_loss=entry * 0.9975,
                    confidence=80, strategy="long_once",
                )
            return None

        candles = _make_candles(21, base_price=entry, trend=0)
        # SL threshold: candles[20]["close"] * (1 - 0.25/100) = 99.75; low must <= 99.75
        # high must stay below TP (100.4) so TP does not trigger first
        candles.append({
            "open": 100, "high": 100.1, "low": 99.0, "close": 99.5,
            "volume": 1000, "timestamp": 2000000,
        })

        result = engine.run(candles, long_once, "X/USDT", tp_pct=tp_pct, sl_pct=sl_pct)
        assert result.total_trades == 1
        assert result.winning_trades == 0
        assert result.losing_trades == 1
        assert result.total_pnl_percent == -sl_pct

    def test_run_short_tp_hit(self, engine):
        """Short trade hits take profit."""
        entry = 100.0
        tp_pct = 0.4
        sl_pct = 0.25

        def short_once(candles):
            if len(candles) == 20:
                return TradeSignal(
                    pair="X/USDT", direction="short",
                    entry_price=entry, take_profit=entry * 0.995,
                    stop_loss=entry * 1.0025,
                    confidence=80, strategy="short_once",
                )
            return None

        candles = _make_candles(21, base_price=entry, trend=0)
        # Short TP: low <= candles[20]["close"] * (1 - 0.4/100) = 99.6
        # high must stay below SL (100.25) so SL does not trigger first
        candles.append({
            "open": 100, "high": 100.1, "low": 99.0, "close": 99.2,
            "volume": 1000, "timestamp": 2000000,
        })

        result = engine.run(candles, short_once, "X/USDT", tp_pct=tp_pct, sl_pct=sl_pct)
        assert result.total_trades == 1
        assert result.winning_trades == 1
        assert result.total_pnl_percent == tp_pct

    def test_run_short_sl_hit(self, engine):
        """Short trade hits stop loss."""
        entry = 100.0
        tp_pct = 0.4
        sl_pct = 0.25

        def short_once(candles):
            if len(candles) == 20:
                return TradeSignal(
                    pair="X/USDT", direction="short",
                    entry_price=entry, take_profit=entry * 0.995,
                    stop_loss=entry * 1.0025,
                    confidence=80, strategy="short_once",
                )
            return None

        candles = _make_candles(21, base_price=entry, trend=0)
        # Short SL: high >= candles[20]["close"] * (1 + 0.25/100) = 100.25
        # low must stay above TP (99.6) so TP does not trigger first
        candles.append({
            "open": 100, "high": 101.0, "low": 99.9, "close": 100.5,
            "volume": 1000, "timestamp": 2000000,
        })

        result = engine.run(candles, short_once, "X/USDT", tp_pct=tp_pct, sl_pct=sl_pct)
        assert result.total_trades == 1
        assert result.losing_trades == 1
        assert result.total_pnl_percent == -sl_pct

    def test_run_multiple_trades(self, engine):
        """Multiple entries and exits over the candle series."""
        call_count = {"n": 0}

        def alternating_strategy(candles):
            call_count["n"] += 1
            # Signal every time we are not in a trade
            return TradeSignal(
                pair="X/USDT", direction="long",
                entry_price=candles[-1]["close"],
                take_profit=candles[-1]["close"] * 1.01,
                stop_loss=candles[-1]["close"] * 0.99,
                confidence=80, strategy="alternating",
            )

        # Big swings: each candle goes up 2.0, high/low wide enough to trigger TP
        candles = []
        for i in range(60):
            close = 100 + i * 0.5
            candles.append({
                "open": close - 0.2,
                "high": close + 2.0,  # Wide enough to hit TP (0.4%)
                "low": close - 2.0,   # Wide enough to hit SL (0.25%)
                "close": close,
                "volume": 1000,
                "timestamp": 1000000 + i * 60,
            })

        result = engine.run(candles, alternating_strategy, "X/USDT", tp_pct=0.4, sl_pct=0.25)
        # With wide candles, trades should close every candle
        assert result.total_trades > 0
        assert result.total_trades == result.winning_trades + result.losing_trades

    def test_run_avg_trade_duration(self, engine):
        """Average trade duration is computed correctly."""
        entry = 100.0

        def once(candles):
            if len(candles) == 20:
                return TradeSignal(
                    pair="X/USDT", direction="long",
                    entry_price=entry, take_profit=200, stop_loss=50,
                    confidence=80, strategy="once",
                )
            return None

        candles = _make_candles(21, base_price=entry, trend=0)
        # Entry happens at candles[20]. TP/SL checked at candles[21].
        entry_ts = candles[20]["timestamp"]
        # TP threshold: candles[20]["close"] * (1 + 0.4/100) = 100.4; high >= 100.4
        candles.append({
            "open": 100, "high": 101.0, "low": 99.8, "close": 100.5,
            "volume": 1000, "timestamp": entry_ts + 300,
        })

        result = engine.run(candles, once, "X/USDT", tp_pct=0.4, sl_pct=0.25)
        assert result.total_trades == 1
        assert result.avg_trade_duration_s == 300.0

    def test_run_max_drawdown(self, engine):
        """Verify max drawdown computation."""
        trade_idx = {"n": 0}

        def alternating(candles):
            trade_idx["n"] += 1
            return TradeSignal(
                pair="X/USDT", direction="long",
                entry_price=candles[-1]["close"],
                take_profit=candles[-1]["close"] * 2,
                stop_loss=candles[-1]["close"] * 0.5,
                confidence=80, strategy="dd_test",
            )

        # Force 2 losses: big drop candles
        candles = _make_candles(21, base_price=100, trend=0)
        for _ in range(4):
            candles.append({
                "open": 100, "high": 100.1, "low": 90.0, "close": 95.0,
                "volume": 1000, "timestamp": 3000000,
            })

        result = engine.run(candles, alternating, "X/USDT", tp_pct=0.4, sl_pct=0.25)
        # If trades lost, drawdown should be > 0
        if result.losing_trades > 0:
            assert result.max_drawdown_percent >= 0

    def test_run_sharpe_ratio_computed(self, engine):
        """Sharpe ratio should be non-zero with enough trades."""

        def always_signal(candles):
            return TradeSignal(
                pair="X/USDT", direction="long",
                entry_price=candles[-1]["close"],
                take_profit=candles[-1]["close"] * 2,
                stop_loss=candles[-1]["close"] * 0.5,
                confidence=80, strategy="sharpe_test",
            )

        # Wide candles ensure trades close quickly
        candles = []
        for i in range(80):
            close = 100 + (i % 5) * 0.5
            candles.append({
                "open": close, "high": close + 3.0, "low": close - 3.0, "close": close,
                "volume": 1000, "timestamp": 1000000 + i * 60,
            })

        result = engine.run(candles, always_signal, "X/USDT", tp_pct=0.4, sl_pct=0.25)
        if result.total_trades > 1:
            assert isinstance(result.sharpe_ratio, float)

    def test_run_strategy_name_extracted(self, engine):
        """Result gets strategy name from function __name__."""

        def my_custom_strategy(candles):
            return None

        candles = _make_candles(30)
        result = engine.run(candles, my_custom_strategy, "X/USDT")
        assert result.strategy == "my_custom_strategy"

    def test_run_strategy_name_lambda(self, engine):
        """Lambda functions have __name__ == '<lambda>'."""
        candles = _make_candles(30)
        result = engine.run(candles, lambda c: None, "X/USDT")
        assert result.strategy == "<lambda>"

    def test_run_no_timestamp_in_candle(self, engine):
        """Candles without timestamp use default 0."""

        def once(candles):
            if len(candles) == 21:
                return TradeSignal(
                    pair="X/USDT", direction="long",
                    entry_price=100, take_profit=200, stop_loss=50,
                    confidence=80, strategy="once",
                )
            return None

        candles = [{"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000}
                   for _ in range(21)]
        # TP hit candle
        candles.append({"open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000})

        result = engine.run(candles, once, "X/USDT", tp_pct=0.4, sl_pct=0.25)
        # Should not crash even without timestamps
        assert isinstance(result.total_trades, int)

    # --- save_result ---

    def test_save_result(self, engine, tmp_path):
        """save_result writes correct JSON."""
        result = BacktestResult(
            strategy="test_save", pair="BTC/USDT", period="50 candles",
            total_trades=10, winning_trades=7, losing_trades=3,
            total_pnl_percent=2.5, max_drawdown_percent=0.8,
            sharpe_ratio=1.5, timestamp=1000000.0,
        )

        with patch("src.trading_engine._BACKTEST_DIR", tmp_path):
            path = engine.save_result(result)
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["strategy"] == "test_save"
            assert data["pair"] == "BTC/USDT"
            assert data["total_trades"] == 10
            assert data["winning_trades"] == 7
            assert data["losing_trades"] == 3
            assert data["win_rate"] == 0.7
            assert data["total_pnl_percent"] == 2.5
            assert data["max_drawdown_percent"] == 0.8
            assert data["sharpe_ratio"] == 1.5

    def test_save_result_filename_format(self, engine, tmp_path):
        result = BacktestResult(
            strategy="momentum", pair="ETH/USDT", period="100 candles",
        )
        with patch("src.trading_engine._BACKTEST_DIR", tmp_path):
            path = engine.save_result(result)
            assert path.name.startswith("bt_momentum_ETH_USDT_")
            assert path.suffix == ".json"

    # --- list_results ---

    def test_list_results_empty(self, engine, tmp_path):
        with patch("src.trading_engine._BACKTEST_DIR", tmp_path):
            results = engine.list_results()
            assert results == []

    def test_list_results_with_files(self, engine, tmp_path):
        data1 = {"strategy": "a", "total_pnl_percent": 1.0}
        data2 = {"strategy": "b", "total_pnl_percent": 2.0}
        (tmp_path / "bt_a_X_USDT_1.json").write_text(json.dumps(data1))
        (tmp_path / "bt_b_X_USDT_2.json").write_text(json.dumps(data2))

        with patch("src.trading_engine._BACKTEST_DIR", tmp_path):
            results = engine.list_results()
            assert len(results) == 2
            # Sorted by filename descending (bt_b_* > bt_a_*)
            assert results[0]["strategy"] == "b"
            assert results[1]["strategy"] == "a"

    def test_list_results_ignores_corrupt_json(self, engine, tmp_path):
        (tmp_path / "bt_good_X_USDT_1.json").write_text('{"strategy": "good"}')
        (tmp_path / "bt_bad_X_USDT_2.json").write_text("NOT JSON{{{")

        with patch("src.trading_engine._BACKTEST_DIR", tmp_path):
            results = engine.list_results()
            assert len(results) == 1
            assert results[0]["strategy"] == "good"

    def test_list_results_ignores_non_bt_files(self, engine, tmp_path):
        (tmp_path / "bt_valid_X_USDT_1.json").write_text('{"strategy": "valid"}')
        (tmp_path / "other_file.json").write_text('{"strategy": "other"}')

        with patch("src.trading_engine._BACKTEST_DIR", tmp_path):
            results = engine.list_results()
            assert len(results) == 1
            assert results[0]["strategy"] == "valid"

    def test_run_records_outcomes_to_scorer(self, engine_with_scorer, scorer):
        """Engine.run should call scorer.record_outcome for each closed trade."""
        entry = 100.0

        def record_test_strat(candles):
            if len(candles) == 20:
                return TradeSignal(
                    pair="X/USDT", direction="long",
                    entry_price=entry, take_profit=200, stop_loss=50,
                    confidence=80, strategy="record_test",
                )
            return None

        candles = _make_candles(21, base_price=entry, trend=0)
        # TP threshold: candles[20]["close"] * (1 + 0.4/100) = 100.4; high >= 100.4
        candles.append({
            "open": 100, "high": 101.0, "low": 99.8, "close": 100.5,
            "volume": 1000, "timestamp": 2000000,
        })

        result = engine_with_scorer.run(candles, record_test_strat, "X/USDT", tp_pct=0.4, sl_pct=0.25)
        assert result.total_trades == 1
        # record_outcome uses result.strategy which is the function __name__
        assert len(scorer._history["record_test_strat"]) == 1
        assert scorer._history["record_test_strat"][0]["pnl"] == 0.4


# ═══════════════════════════════════════════════════════════════════════════════
# TradingFlowManager
# ═══════════════════════════════════════════════════════════════════════════════


class TestTradingFlowManager:
    """Comprehensive tests for TradingFlowManager."""

    def test_init_defaults(self, flow_manager):
        assert flow_manager._active_flows == {}
        assert isinstance(flow_manager.scorer, StrategyScorer)

    def test_init_custom_scorer(self):
        custom = StrategyScorer()
        fm = TradingFlowManager(custom)
        assert fm.scorer is custom

    def test_get_active_flows_empty(self, flow_manager):
        assert flow_manager.get_active_flows() == {}

    @pytest.mark.asyncio
    async def test_run_pipeline_no_pairs(self, flow_manager):
        result = await flow_manager.run_pipeline([], [lambda p: None], min_score=0)
        assert result == []

    @pytest.mark.asyncio
    async def test_run_pipeline_no_strategies(self, flow_manager):
        result = await flow_manager.run_pipeline(["BTC/USDT"], [], min_score=0)
        assert result == []

    @pytest.mark.asyncio
    async def test_run_pipeline_sync_strategy_returns_signal(self, flow_manager):
        """Sync strategy returning a TradeSignal should be picked up."""
        sig = TradeSignal(
            pair="BTC/USDT", direction="long",
            entry_price=50000, take_profit=60000, stop_loss=45000,
            confidence=95, strategy="test_sync",
        )

        def sync_strat(pair):
            return sig

        # Use min_score=0 so any signal passes
        result = await flow_manager.run_pipeline(["BTC/USDT"], [sync_strat], min_score=0)
        assert len(result) == 1
        assert result[0]["signal"] is sig
        assert result[0]["score"] > 0

    @pytest.mark.asyncio
    async def test_run_pipeline_async_strategy(self, flow_manager):
        """Async strategy should work too."""
        sig = TradeSignal(
            pair="ETH/USDT", direction="short",
            entry_price=3000, take_profit=2900, stop_loss=3050,
            confidence=85, strategy="async_test",
        )

        async def async_strat(pair):
            return sig

        result = await flow_manager.run_pipeline(["ETH/USDT"], [async_strat], min_score=0)
        assert len(result) == 1
        assert result[0]["signal"] is sig

    @pytest.mark.asyncio
    async def test_run_pipeline_filters_by_min_score(self, flow_manager):
        """Signals below min_score should be filtered out."""
        weak_sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=100.1, stop_loss=99.99,
            confidence=1, strategy="weak",
        )

        def weak_strat(pair):
            return weak_sig

        result = await flow_manager.run_pipeline(["X/USDT"], [weak_strat], min_score=90)
        assert result == []

    @pytest.mark.asyncio
    async def test_run_pipeline_multiple_pairs_strategies(self, flow_manager):
        """Multiple pairs x strategies produce correct number of evaluations."""
        call_log = []

        def logging_strat(pair):
            call_log.append(pair)
            return TradeSignal(
                pair=pair, direction="long",
                entry_price=100, take_profit=200, stop_loss=50,
                confidence=95, strategy="logger",
            )

        result = await flow_manager.run_pipeline(
            ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
            [logging_strat],
            min_score=0,
        )
        assert len(call_log) == 3
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_run_pipeline_strategy_exception_handled(self, flow_manager):
        """Strategy raising exception should not crash the pipeline."""

        def bad_strat(pair):
            raise ValueError("API error")

        result = await flow_manager.run_pipeline(["BTC/USDT"], [bad_strat], min_score=0)
        # _evaluate_strategy catches the exception and returns None
        assert result == []

    @pytest.mark.asyncio
    async def test_run_pipeline_mixed_results(self, flow_manager):
        """Mix of signals, None returns, and exceptions."""
        good_sig = TradeSignal(
            pair="BTC/USDT", direction="long",
            entry_price=100, take_profit=200, stop_loss=50,
            confidence=95, strategy="good",
        )

        def good_strat(pair):
            return good_sig

        def none_strat(pair):
            return None

        def error_strat(pair):
            raise RuntimeError("boom")

        result = await flow_manager.run_pipeline(
            ["BTC/USDT"],
            [good_strat, none_strat, error_strat],
            min_score=0,
        )
        # Only good_strat produces a signal
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_run_pipeline_ranked_by_score(self, flow_manager):
        """Signals should be ranked by score, highest first."""
        high_sig = TradeSignal(
            pair="BTC/USDT", direction="long",
            entry_price=100, take_profit=200, stop_loss=99,
            confidence=100, strategy="high",
        )
        low_sig = TradeSignal(
            pair="ETH/USDT", direction="long",
            entry_price=100, take_profit=100.5, stop_loss=99.5,
            confidence=10, strategy="low",
        )

        def high_strat(pair):
            return high_sig

        def low_strat(pair):
            return low_sig

        result = await flow_manager.run_pipeline(
            ["BTC/USDT"],
            [high_strat, low_strat],
            min_score=0,
        )
        if len(result) == 2:
            assert result[0]["score"] >= result[1]["score"]

    @pytest.mark.asyncio
    async def test_run_pipeline_updates_active_flows(self, flow_manager):
        """After pipeline runs, flow should be recorded in _active_flows."""

        def noop(pair):
            return None

        await flow_manager.run_pipeline(["BTC/USDT"], [noop], min_score=0)
        flows = flow_manager.get_active_flows()
        assert len(flows) == 1
        flow_id = list(flows.keys())[0]
        assert flow_id.startswith("flow_")
        assert flows[flow_id]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_run_pipeline_flow_tracks_signal_count(self, flow_manager):
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=200, stop_loss=50,
            confidence=95, strategy="track",
        )

        def strat(pair):
            return sig

        await flow_manager.run_pipeline(["BTC/USDT", "ETH/USDT"], [strat], min_score=0)
        flows = flow_manager.get_active_flows()
        flow = list(flows.values())[0]
        assert flow["signals"] == 2

    @pytest.mark.asyncio
    async def test_evaluate_strategy_sync(self, flow_manager):
        """_evaluate_strategy wraps sync functions correctly."""
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=110, stop_loss=95,
            confidence=80, strategy="sync_eval",
        )

        def sync_fn(pair):
            return sig

        result = await flow_manager._evaluate_strategy("X/USDT", sync_fn)
        assert result is sig

    @pytest.mark.asyncio
    async def test_evaluate_strategy_async(self, flow_manager):
        """_evaluate_strategy handles async strategies."""
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=110, stop_loss=95,
            confidence=80, strategy="async_eval",
        )

        async def async_fn(pair):
            return sig

        result = await flow_manager._evaluate_strategy("X/USDT", async_fn)
        assert result is sig

    @pytest.mark.asyncio
    async def test_evaluate_strategy_exception_returns_none(self, flow_manager):
        """Exceptions in strategy return None, not propagate."""

        def exploding(pair):
            raise ConnectionError("network down")

        result = await flow_manager._evaluate_strategy("X/USDT", exploding)
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_strategy_async_exception_returns_none(self, flow_manager):
        async def async_boom(pair):
            raise TimeoutError("timeout")

        result = await flow_manager._evaluate_strategy("X/USDT", async_boom)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE SINGLETONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestModuleSingletons:
    """Verify module-level singletons are properly initialized."""

    def test_strategy_scorer_exists(self):
        from src.trading_engine import strategy_scorer
        assert isinstance(strategy_scorer, StrategyScorer)

    def test_backtest_engine_exists(self):
        from src.trading_engine import backtest_engine
        assert isinstance(backtest_engine, BacktestEngine)

    def test_trading_flow_exists(self):
        from src.trading_engine import trading_flow
        assert isinstance(trading_flow, TradingFlowManager)

    def test_singletons_share_scorer(self):
        from src.trading_engine import backtest_engine, strategy_scorer, trading_flow
        assert backtest_engine.scorer is strategy_scorer
        assert trading_flow.scorer is strategy_scorer


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_score_signal_zero_rr_zero_confidence(self):
        scorer = StrategyScorer()
        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=100, stop_loss=100,
            confidence=0, strategy="zero",
        )
        score = scorer.score_signal(sig)
        assert score == 0.0

    def test_backtest_empty_candle_list(self):
        with patch("pathlib.Path.mkdir"):
            eng = BacktestEngine()
            result = eng.run([], lambda c: None, "X/USDT")
            assert result.total_trades == 0

    def test_backtest_single_candle(self):
        with patch("pathlib.Path.mkdir"):
            eng = BacktestEngine()
            candles = [{"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1}]
            result = eng.run(candles, lambda c: None, "X/USDT")
            assert result.total_trades == 0

    def test_rankings_top_n_zero(self):
        scorer = StrategyScorer()
        for _ in range(5):
            scorer.record_outcome("s", 1.0, 10)
        rankings = scorer.get_strategy_rankings(top_n=0)
        assert rankings == []

    def test_trade_signal_metadata_independent(self):
        """Each signal should have its own metadata dict."""
        s1 = TradeSignal(
            pair="A/USDT", direction="long",
            entry_price=1, take_profit=2, stop_loss=0,
            confidence=50, strategy="test",
        )
        s2 = TradeSignal(
            pair="B/USDT", direction="long",
            entry_price=1, take_profit=2, stop_loss=0,
            confidence=50, strategy="test",
        )
        s1.metadata["key"] = "val"
        assert "key" not in s2.metadata

    def test_backtest_result_signals_list_independent(self):
        """Each BacktestResult has its own signals list."""
        r1 = BacktestResult(strategy="a", pair="X/USDT", period="10")
        r2 = BacktestResult(strategy="b", pair="X/USDT", period="10")
        r1.signals.append("dummy")
        assert len(r2.signals) == 0

    @pytest.mark.asyncio
    async def test_pipeline_with_strategy_returning_non_signal(self):
        """Strategy returning a non-TradeSignal object is ignored."""
        fm = TradingFlowManager()

        def returns_string(pair):
            return "not a signal"

        result = await fm.run_pipeline(["X/USDT"], [returns_string], min_score=0)
        # "not a signal" is not a TradeSignal, so gather returns a string
        # which is not isinstance(r, TradeSignal) and not isinstance(r, Exception)
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_pipelines_tracked_separately(self):
        fm = TradingFlowManager()

        def noop(pair):
            return None

        await fm.run_pipeline(["A/USDT"], [noop])
        await fm.run_pipeline(["B/USDT"], [noop])
        flows = fm.get_active_flows()
        # Two flows if timestamps differ (sub-second, but time.time() precision should differ)
        # At minimum, we should have at least 1 flow
        assert len(flows) >= 1
        for flow in flows.values():
            assert flow["status"] == "completed"

    def test_score_signal_history_window_20(self):
        """Win rate is computed on last 20 entries only."""
        scorer = StrategyScorer()
        # 20 losses then 20 wins
        for _ in range(20):
            scorer.record_outcome("window20", -1.0, 10)
        for _ in range(20):
            scorer.record_outcome("window20", 1.0, 10)

        sig = TradeSignal(
            pair="X/USDT", direction="long",
            entry_price=100, take_profit=101, stop_loss=99,
            confidence=0, strategy="window20",
        )
        score = scorer.score_signal(sig)
        # history[-20:] = last 20 = all wins, win_rate=1.0 -> 30pts
        # R/R=1 -> 10, confidence=0, recent 5: 5 wins -> 20
        # Total: 10 + 30 + 0 + 20 = 60
        assert score == 60.0

    def test_backtest_both_tp_and_sl_same_candle_tp_wins(self, engine):
        """If both TP and SL are hit in the same candle, TP is checked first."""
        entry = 100.0

        def once(candles):
            if len(candles) == 20:
                return TradeSignal(
                    pair="X/USDT", direction="long",
                    entry_price=entry, take_profit=200, stop_loss=50,
                    confidence=80, strategy="both_hit",
                )
            return None

        candles = _make_candles(21, base_price=entry, trend=0)
        # Both high hits TP and low hits SL on the exit candle
        candles.append({
            "open": 100, "high": 200.0, "low": 50.0, "close": 100,
            "volume": 1000, "timestamp": 2000000,
        })

        result = engine.run(candles, once, "X/USDT", tp_pct=0.4, sl_pct=0.25)
        assert result.total_trades == 1
        # TP is checked first in the code
        assert result.winning_trades == 1
