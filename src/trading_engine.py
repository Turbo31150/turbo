"""JARVIS Trading Engine v3 — Async pipeline with backtest support.

Components:
- BacktestEngine: Replay historical data through strategies
- StrategyScorer: Score trading setups with confidence intervals
- FlowManager: Async orchestration of trading pipeline stages
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "StrategyScorer",
    "TradeSignal",
    "TradingFlowManager",
]

logger = logging.getLogger("jarvis.trading_engine")

_DATA_DIR = Path(__file__).parent.parent / "data"
_BACKTEST_DIR = _DATA_DIR / "backtests"


# ═══════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TradeSignal:
    """A trading signal from strategy evaluation."""
    pair: str
    direction: str  # "long" or "short"
    entry_price: float
    take_profit: float
    stop_loss: float
    confidence: float  # 0-100
    strategy: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    @property
    def risk_reward(self) -> float:
        if self.direction == "long":
            reward = abs(self.take_profit - self.entry_price)
            risk = abs(self.entry_price - self.stop_loss)
        else:
            reward = abs(self.entry_price - self.take_profit)
            risk = abs(self.stop_loss - self.entry_price)
        return round(reward / risk, 2) if risk > 0 else 0


@dataclass
class BacktestResult:
    """Result of a backtest run."""
    strategy: str
    pair: str
    period: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_percent: float = 0.0
    max_drawdown_percent: float = 0.0
    sharpe_ratio: float = 0.0
    avg_trade_duration_s: float = 0.0
    signals: list[TradeSignal] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def win_rate(self) -> float:
        return round(self.winning_trades / self.total_trades, 3) if self.total_trades > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════════
# STRATEGY SCORER — Evaluate and rank trading setups
# ═══════════════════════════════════════════════════════════════════════════

class StrategyScorer:
    """Score trading signals with confidence intervals."""

    def __init__(self):
        self._history: dict[str, list[dict]] = defaultdict(list)  # strategy -> results

    def score_signal(self, signal: TradeSignal) -> float:
        """Score a signal 0-100 based on multiple factors."""
        score = 0.0

        # Risk/reward ratio (max 30 pts)
        rr = signal.risk_reward
        score += min(30, rr * 10)

        # Historical win rate for this strategy (max 30 pts)
        history = self._history.get(signal.strategy, [])
        if len(history) >= 5:
            wins = sum(1 for h in history[-20:] if h.get("pnl", 0) > 0)
            win_rate = wins / len(history[-20:])
            score += win_rate * 30

        # Confidence from strategy (max 20 pts)
        score += signal.confidence * 0.2

        # Recency bonus — strategies that worked recently get a boost (max 20 pts)
        recent_wins = sum(1 for h in history[-5:] if h.get("pnl", 0) > 0)
        score += recent_wins * 4

        return min(100, round(score, 1))

    def record_outcome(self, strategy: str, pnl_percent: float, duration_s: float = 0):
        """Record trade outcome for learning."""
        self._history[strategy].append({
            "pnl": pnl_percent,
            "duration_s": duration_s,
            "timestamp": time.time(),
        })
        # Keep last 100 per strategy
        if len(self._history[strategy]) > 100:
            self._history[strategy] = self._history[strategy][-100:]

    def get_strategy_rankings(self, top_n: int = 10) -> list[dict]:
        """Rank strategies by historical performance."""
        rankings = []
        for strategy, history in self._history.items():
            if len(history) < 3:
                continue
            pnls = [h["pnl"] for h in history]
            rankings.append({
                "strategy": strategy,
                "trades": len(history),
                "win_rate": round(sum(1 for p in pnls if p > 0) / len(pnls), 3),
                "avg_pnl": round(statistics.mean(pnls), 3),
                "total_pnl": round(sum(pnls), 3),
                "std_pnl": round(statistics.stdev(pnls), 3) if len(pnls) > 1 else 0,
            })
        return sorted(rankings, key=lambda x: x["total_pnl"], reverse=True)[:top_n]


# ═══════════════════════════════════════════════════════════════════════════
# BACKTEST ENGINE — Replay historical candle data
# ═══════════════════════════════════════════════════════════════════════════

class BacktestEngine:
    """Backtest trading strategies against historical data."""

    def __init__(self, scorer: StrategyScorer | None = None):
        self.scorer = scorer or StrategyScorer()
        _BACKTEST_DIR.mkdir(parents=True, exist_ok=True)

    def run(self, candles: list[dict], strategy_fn, pair: str = "BTC/USDT",
            tp_pct: float = 0.4, sl_pct: float = 0.25) -> BacktestResult:
        """Run a backtest on historical candle data.

        Args:
            candles: List of {open, high, low, close, volume, timestamp}
            strategy_fn: Function(candles[:i]) -> TradeSignal | None
            pair: Trading pair name
            tp_pct: Take profit percentage
            sl_pct: Stop loss percentage

        Returns: BacktestResult
        """
        result = BacktestResult(
            strategy=getattr(strategy_fn, "__name__", "custom"),
            pair=pair,
            period=f"{len(candles)} candles",
        )

        pnl_curve = []
        in_trade = False
        entry_price = 0.0
        direction = ""
        entry_time = 0.0

        for i in range(20, len(candles)):  # Need at least 20 candles history
            if not in_trade:
                signal = strategy_fn(candles[:i])
                if signal and signal.confidence >= 60:
                    in_trade = True
                    entry_price = candles[i]["close"]
                    direction = signal.direction
                    entry_time = candles[i].get("timestamp", time.time())
                    result.signals.append(signal)
            else:
                candle = candles[i]
                close = candle["close"]
                high = candle["high"]
                low = candle["low"]

                if direction == "long":
                    tp_hit = high >= entry_price * (1 + tp_pct / 100)
                    sl_hit = low <= entry_price * (1 - sl_pct / 100)
                else:
                    tp_hit = low <= entry_price * (1 - tp_pct / 100)
                    sl_hit = high >= entry_price * (1 + sl_pct / 100)

                if tp_hit:
                    pnl = tp_pct
                    result.winning_trades += 1
                    in_trade = False
                elif sl_hit:
                    pnl = -sl_pct
                    result.losing_trades += 1
                    in_trade = False
                else:
                    continue

                result.total_trades += 1
                result.total_pnl_percent += pnl
                pnl_curve.append(result.total_pnl_percent)
                duration = candle.get("timestamp", 0) - entry_time
                result.avg_trade_duration_s += duration
                self.scorer.record_outcome(result.strategy, pnl, duration)

        if result.total_trades > 0:
            result.avg_trade_duration_s /= result.total_trades

        # Max drawdown
        if pnl_curve:
            peak = pnl_curve[0]
            max_dd = 0.0
            for p in pnl_curve:
                peak = max(peak, p)
                dd = peak - p
                max_dd = max(max_dd, dd)
            result.max_drawdown_percent = round(max_dd, 3)

        # Sharpe ratio (simplified)
        if len(pnl_curve) > 1:
            returns = [pnl_curve[i] - pnl_curve[i - 1] for i in range(1, len(pnl_curve))]
            avg_ret = statistics.mean(returns) if returns else 0
            std_ret = statistics.stdev(returns) if len(returns) > 1 else 1
            result.sharpe_ratio = round(avg_ret / std_ret, 3) if std_ret > 0 else 0

        return result

    def save_result(self, result: BacktestResult) -> Path:
        """Save backtest result to JSON file."""
        filename = f"bt_{result.strategy}_{result.pair.replace('/', '_')}_{int(time.time())}.json"
        path = _BACKTEST_DIR / filename
        data = {
            "strategy": result.strategy,
            "pair": result.pair,
            "period": result.period,
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "win_rate": result.win_rate,
            "total_pnl_percent": result.total_pnl_percent,
            "max_drawdown_percent": result.max_drawdown_percent,
            "sharpe_ratio": result.sharpe_ratio,
            "timestamp": result.timestamp,
        }
        path.write_text(json.dumps(data, indent=2))
        return path

    def list_results(self) -> list[dict]:
        """List saved backtest results."""
        results = []
        for f in sorted(_BACKTEST_DIR.glob("bt_*.json"), reverse=True):
            try:
                results.append(json.loads(f.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        return results


# ═══════════════════════════════════════════════════════════════════════════
# FLOW MANAGER — Async trading pipeline orchestration
# ═══════════════════════════════════════════════════════════════════════════

class TradingFlowManager:
    """Async orchestration of trading pipeline stages."""

    def __init__(self, scorer: StrategyScorer | None = None):
        self.scorer = scorer or StrategyScorer()
        self._active_flows: dict[str, dict] = {}

    async def run_pipeline(self, pairs: list[str],
                           strategies: list[Any],
                           min_score: float = 70) -> list[dict]:
        """Run full trading pipeline: scan -> score -> filter -> rank.

        Strategies are evaluated in parallel per pair.
        """
        flow_id = f"flow_{int(time.time())}"
        self._active_flows[flow_id] = {"status": "running", "started": time.time()}

        try:
            # Phase 1: Parallel strategy evaluation
            tasks = []
            for pair in pairs:
                for strategy in strategies:
                    tasks.append(self._evaluate_strategy(pair, strategy))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Phase 2: Collect valid signals
            signals = []
            for r in results:
                if isinstance(r, TradeSignal):
                    score = self.scorer.score_signal(r)
                    if score >= min_score:
                        signals.append({"signal": r, "score": score})
                elif isinstance(r, Exception):
                    logger.debug("Strategy evaluation error: %s", r)

            # Phase 3: Rank by score
            signals.sort(key=lambda x: x["score"], reverse=True)

            self._active_flows[flow_id]["status"] = "completed"
            self._active_flows[flow_id]["signals"] = len(signals)
            return signals

        except Exception as e:
            self._active_flows[flow_id]["status"] = "failed"
            self._active_flows[flow_id]["error"] = str(e)
            raise

    async def _evaluate_strategy(self, pair: str, strategy) -> TradeSignal | None:
        """Evaluate a single strategy for a pair (async wrapper)."""
        try:
            if asyncio.iscoroutinefunction(strategy):
                return await strategy(pair)
            else:
                return await asyncio.to_thread(strategy, pair)
        except Exception as e:
            logger.debug("Strategy error for %s: %s", pair, e)
            return None

    def get_active_flows(self) -> dict:
        return dict(self._active_flows)


# Global singletons
strategy_scorer = StrategyScorer()
backtest_engine = BacktestEngine(strategy_scorer)
trading_flow = TradingFlowManager(strategy_scorer)
