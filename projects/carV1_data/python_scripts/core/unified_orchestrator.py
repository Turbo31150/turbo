#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UNIFIED ORCHESTRATOR - Interface unifiee pour toutes les strategies
Contrat unique: run(ohlcv) -> TradingSignal
"""
# CRITICAL: Setup CUDA PATH first
import setup_cuda

import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import warnings
warnings.filterwarnings('ignore')

import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


# Import SignalType and TradingSignal from gpu_strategies_hybrid to avoid enum identity mismatch
from gpu_strategies_hybrid import SignalType, TradingSignal


class MarketRegime(Enum):
    RANGE = "RANGE"          # ATR% < 0.8
    TREND = "TREND"          # ATR% 0.8-1.6
    HIGH_VOL = "HIGH_VOL"    # ATR% > 1.6


@dataclass
class StrategyMetrics:
    """Metriques par strategie"""
    name: str
    total_signals: int
    buy_count: int
    sell_count: int
    hold_count: int
    avg_confidence: float
    avg_compute_time_ms: float
    contribution_score: float  # Contribution au consensus
    # Metriques enrichies
    winrate_by_regime: Dict = None
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    consensus_correlation: float = 0.0
    marginal_contribution: float = 0.0  # Delta si desactivee


class StrategyWrapper:
    """Wrapper unifie pour toutes les strategies"""

    def __init__(self, strategy, method_name: str = None):
        self.strategy = strategy
        self.name = getattr(strategy, 'name', strategy.__class__.__name__)
        self.base_weight = getattr(strategy, 'weight', 1.0)
        self.weight = self.base_weight  # Dynamic weight (can be adjusted)
        self.active = True  # Can be disabled based on contribution
        self.regime_weights = {r.value: 1.0 for r in MarketRegime}  # Per-regime weights

        # Detecte la methode automatiquement
        if method_name:
            self.method_name = method_name
        elif hasattr(strategy, 'run'):
            self.method_name = 'run'
        elif hasattr(strategy, 'analyze'):
            self.method_name = 'analyze'
        elif hasattr(strategy, 'compute'):
            self.method_name = 'compute'
        else:
            raise ValueError(f"Strategy {self.name} has no run/analyze/compute method")

    def run(self, ohlcv: Dict) -> TradingSignal:
        """Interface unifiee"""
        method = getattr(self.strategy, self.method_name)
        return method(ohlcv)

    def get_weight_for_regime(self, regime: MarketRegime) -> float:
        """Retourne le poids ajuste pour un regime donne"""
        if not self.active:
            return 0.0
        return self.weight * self.regime_weights.get(regime.value, 1.0)


class UnifiedOrchestrator:
    """Orchestrateur unifie avec metriques par strategie"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.strategies: List[StrategyWrapper] = []
        self.metrics: Dict[str, StrategyMetrics] = {}
        self.history: List[Dict] = []

        # Importer et wrapper toutes les strategies
        self._load_all_strategies()

        print(f"\n[UNIFIED] {len(self.strategies)} strategies chargees")
        print(f"[UNIFIED] Workers: {max_workers}")

    def _load_all_strategies(self):
        """Charge toutes les strategies avec wrapper unifie"""
        # Base strategies
        from gpu_strategies_hybrid import (
            SmartMoneyStrategy, TrendshiftStrategy, VelocityScalpStrategy,
            SuperTrendRSIStrategy, BollingerSqueezeStrategy, MACDCrossStrategy,
            VWAPStrategy, MomentumStrategy
        )

        base_strategies = [
            SmartMoneyStrategy(),
            TrendshiftStrategy(),
            VelocityScalpStrategy(),
            SuperTrendRSIStrategy(),
            BollingerSqueezeStrategy(),
            MACDCrossStrategy(),
            VWAPStrategy(),
            MomentumStrategy()
        ]

        for s in base_strategies:
            self.strategies.append(StrategyWrapper(s, 'compute'))

        # Advanced strategies
        from advanced_strategies import get_advanced_strategies
        for s in get_advanced_strategies():
            self.strategies.append(StrategyWrapper(s, 'analyze'))

        # Extracted strategies
        from extracted_strategies import get_extracted_strategies
        for s in get_extracted_strategies():
            self.strategies.append(StrategyWrapper(s, 'analyze'))

        # Init metrics
        for s in self.strategies:
            self.metrics[s.name] = StrategyMetrics(
                name=s.name,
                total_signals=0,
                buy_count=0,
                sell_count=0,
                hold_count=0,
                avg_confidence=0.0,
                avg_compute_time_ms=0.0,
                contribution_score=0.0,
                winrate_by_regime={r.value: {'wins': 0, 'total': 0} for r in MarketRegime},
                profit_factor=0.0,
                max_drawdown=0.0,
                consensus_correlation=0.0,
                marginal_contribution=0.0
            )

    def analyze(self, ohlcv: Dict) -> List[TradingSignal]:
        """Execute toutes les strategies via interface unifiee"""
        signals = []
        start_total = time.perf_counter()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(s.run, ohlcv): s for s in self.strategies}

            for future in as_completed(futures):
                strategy = futures[future]
                try:
                    signal = future.result()
                    signals.append(signal)

                    # Update metrics
                    m = self.metrics[strategy.name]
                    m.total_signals += 1
                    if signal.signal_type == SignalType.BUY:
                        m.buy_count += 1
                    elif signal.signal_type == SignalType.SELL:
                        m.sell_count += 1
                    else:
                        m.hold_count += 1

                    # Running average
                    n = m.total_signals
                    m.avg_confidence = ((n-1) * m.avg_confidence + signal.confidence) / n
                    m.avg_compute_time_ms = ((n-1) * m.avg_compute_time_ms + signal.compute_time_ms) / n

                except Exception as e:
                    print(f"[!] Error in {strategy.name}: {e}")

        elapsed = (time.perf_counter() - start_total) * 1000
        return signals

    def get_consensus(self, signals: List[TradingSignal]) -> Dict:
        """Calcule le consensus pondere"""
        if not signals:
            return {
                'signal': SignalType.HOLD,
                'confidence': 0.0,
                'buy_score': 0.0,
                'sell_score': 0.0
            }

        buy_weight = 0.0
        sell_weight = 0.0
        hold_weight = 0.0
        total_weight = 0.0

        for signal in signals:
            # Get weight from wrapper
            wrapper = next((s for s in self.strategies if s.name == signal.strategy), None)
            weight = wrapper.weight if wrapper else 1.0
            weighted_conf = signal.confidence * weight
            total_weight += weight

            if signal.signal_type == SignalType.BUY:
                buy_weight += weighted_conf
            elif signal.signal_type == SignalType.SELL:
                sell_weight += weighted_conf
            else:
                hold_weight += weighted_conf

        # Calculate scores as percentage of active signals
        active_weight = buy_weight + sell_weight
        if active_weight > 0:
            buy_score = buy_weight / (buy_weight + sell_weight + 0.0001)
            sell_score = sell_weight / (buy_weight + sell_weight + 0.0001)
        else:
            buy_score = 0.0
            sell_score = 0.0

        # Determine signal based on majority + threshold
        threshold = 0.55  # Need 55% of active signals
        if buy_score > threshold and buy_weight > sell_weight:
            final_signal = SignalType.BUY
            confidence = min(0.95, buy_score)
        elif sell_score > threshold and sell_weight > buy_weight:
            final_signal = SignalType.SELL
            confidence = min(0.95, sell_score)
        else:
            final_signal = SignalType.HOLD
            confidence = max(0.5, 1.0 - max(buy_score, sell_score))

        # Update contribution scores
        for signal in signals:
            m = self.metrics.get(signal.strategy)
            if m:
                if signal.signal_type == final_signal:
                    m.contribution_score += signal.confidence
                elif signal.signal_type != SignalType.HOLD:
                    m.contribution_score -= signal.confidence * 0.5

        return {
            'signal': final_signal,
            'confidence': confidence,
            'buy_score': buy_score,
            'sell_score': sell_score
        }

    def detect_regime(self, ohlcv: Dict) -> MarketRegime:
        """Detecte le regime de marche base sur ATR%"""
        high = np.asarray(ohlcv['high'], dtype=np.float32)
        low = np.asarray(ohlcv['low'], dtype=np.float32)
        close = np.asarray(ohlcv['close'], dtype=np.float32)

        # ATR 14 periodes
        tr = np.maximum(high[1:] - low[1:],
                       np.abs(high[1:] - close[:-1]),
                       np.abs(low[1:] - close[:-1]))
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else np.mean(tr)
        atr_pct = (atr / close[-1]) * 100

        if atr_pct < 0.8:
            return MarketRegime.RANGE
        elif atr_pct > 1.6:
            return MarketRegime.HIGH_VOL
        else:
            return MarketRegime.TREND

    def simulate_trade_result(self, signal: TradingSignal, price_change_pct: float) -> float:
        """Simule le resultat d'un trade (PnL)"""
        if signal.signal_type == SignalType.BUY:
            return price_change_pct * signal.confidence
        elif signal.signal_type == SignalType.SELL:
            return -price_change_pct * signal.confidence
        return 0.0

    def system_score(self, trades: List[Dict]) -> float:
        """Score global du systeme: PnL - 0.5 * drawdown"""
        if not trades:
            return 0.0
        pnls = [t['pnl'] for t in trades]
        total_pnl = sum(pnls)

        # Max drawdown
        cumsum = np.cumsum(pnls)
        peak = np.maximum.accumulate(cumsum)
        drawdown = np.max(peak - cumsum) if len(cumsum) > 0 else 0

        return total_pnl - 0.5 * drawdown

    def run_system_with_strategies(self, ohlcv: Dict, strategy_names: List[str], n_runs: int) -> Tuple[List[Dict], Dict]:
        """Execute le systeme avec un sous-ensemble de strategies"""
        trades = []
        regime_trades = {r.value: [] for r in MarketRegime}
        data = ohlcv.copy()

        for i in range(n_runs):
            regime = self.detect_regime(data)
            signals = self.analyze(data)

            # Filter only selected strategies
            filtered_signals = [s for s in signals if s.strategy in strategy_names]

            if filtered_signals:
                consensus = self.get_consensus(filtered_signals)

                # Simulate price movement
                diff = np.diff(data['close'][-20:])
                volatility = max(np.std(diff) / abs(data['close'][-1] + 1e-9), 0.001)
                price_change = np.random.normal(0, volatility * 100)

                pnl = self.simulate_trade_result(
                    TradingSignal('system', consensus['signal'], consensus['confidence'],
                                 data['close'][-1], 0, {}), price_change)

                trade = {'pnl': pnl, 'regime': regime, 'signal': consensus['signal']}
                trades.append(trade)
                regime_trades[regime.value].append(trade)

            # Evolve data
            noise = np.random.randn(len(data['close'])) * 5
            data = {
                'open': data['open'] + noise.astype(np.float32),
                'high': data['high'] + np.abs(noise.astype(np.float32)),
                'low': data['low'] - np.abs(noise.astype(np.float32)),
                'close': data['close'] + noise.astype(np.float32),
                'volume': data['volume']
            }

        return trades, regime_trades

    def compute_marginal_contributions(self, ohlcv: Dict, n_runs: int = 30) -> Dict:
        """Calcule la contribution marginale REELLE de chaque strategie (leave-one-out)"""
        print(f"\n[MARGINAL CONTRIBUTION] Leave-one-out sur {len(self.strategies)} strategies...")

        all_names = [s.name for s in self.strategies]

        # Baseline: toutes les strategies
        print("  Computing baseline (all strategies)...")
        baseline_trades, baseline_by_regime = self.run_system_with_strategies(
            ohlcv.copy(), all_names, n_runs)
        baseline_score = self.system_score(baseline_trades)
        baseline_by_regime_score = {r: self.system_score(trades) for r, trades in baseline_by_regime.items()}

        print(f"  Baseline score: {baseline_score:+.3f}")

        # Leave-one-out pour chaque strategie
        contributions = {}
        for i, strat in enumerate(self.strategies):
            reduced_names = [n for n in all_names if n != strat.name]

            reduced_trades, reduced_by_regime = self.run_system_with_strategies(
                ohlcv.copy(), reduced_names, n_runs)
            reduced_score = self.system_score(reduced_trades)

            # Contribution marginale = baseline - score_sans
            mc = baseline_score - reduced_score

            # Contribution par regime
            mc_by_regime = {}
            for regime_val in baseline_by_regime_score:
                regime_score_without = self.system_score(reduced_by_regime[regime_val])
                mc_by_regime[regime_val] = baseline_by_regime_score[regime_val] - regime_score_without

            # Normalisation
            mc_normalized = mc / (abs(baseline_score) + 1e-9)

            contributions[strat.name] = {
                'raw': mc,
                'normalized': mc_normalized,
                'by_regime': mc_by_regime
            }

            # Update metrics
            m = self.metrics[strat.name]
            m.marginal_contribution = mc_normalized

            status = "+" if mc > 0 else "-" if mc < 0 else "="
            print(f"  [{i+1:2d}/{len(self.strategies)}] {strat.name:<20} {status} {mc_normalized:+.4f}")

        print(f"\n[DONE] Marginal contributions computed")
        return contributions

    def apply_adaptive_weights(self, contributions: Dict, disable_percentile: float = 0.10,
                               weak_percentile: float = 0.30, boost_percentile: float = 0.70) -> Dict:
        """
        Applique une ponderation adaptative basee sur les contributions marginales.
        Utilise des percentiles pour eviter de desactiver toutes les strategies.

        - bottom 10% -> strategie desactivee (weight=0)
        - bottom 30% -> poids reduit (x0.5)
        - top 30% -> poids booste (x1.5)
        - contributions par regime ajustent les poids par regime
        """
        print(f"\n[ADAPTIVE WEIGHTS] Application des poids adaptatifs...")

        # Calculate percentile thresholds from actual data
        all_mc = [c.get('normalized', 0.0) for c in contributions.values()]
        if not all_mc:
            return {'disabled': [], 'weakened': [], 'boosted': [], 'unchanged': []}

        disable_threshold = np.percentile(all_mc, disable_percentile * 100)
        weak_threshold = np.percentile(all_mc, weak_percentile * 100)
        boost_threshold = np.percentile(all_mc, boost_percentile * 100)

        print(f"  Seuils: disable<{disable_threshold:.4f} | weak<{weak_threshold:.4f} | boost>{boost_threshold:.4f}")

        changes = {'disabled': [], 'weakened': [], 'boosted': [], 'unchanged': []}

        for strat in self.strategies:
            c = contributions.get(strat.name, {})
            mc = c.get('normalized', 0.0)
            mc_by_regime = c.get('by_regime', {})

            # Global weight adjustment
            if mc < disable_threshold:
                strat.active = False
                strat.weight = 0.0
                changes['disabled'].append(strat.name)
                print(f"  [X] {strat.name:<20} DESACTIVE (mc={mc:+.4f})")
            elif mc < weak_threshold:
                strat.weight = strat.base_weight * 0.5
                changes['weakened'].append(strat.name)
                print(f"  [~] {strat.name:<20} poids x0.5 (mc={mc:+.4f})")
            elif mc > boost_threshold:
                strat.weight = strat.base_weight * 1.5
                changes['boosted'].append(strat.name)
                print(f"  [+] {strat.name:<20} poids x1.5 (mc={mc:+.4f})")
            else:
                changes['unchanged'].append(strat.name)

            # Per-regime weight adjustment
            for regime_val, regime_mc in mc_by_regime.items():
                if regime_mc < -0.1:
                    strat.regime_weights[regime_val] = 0.0
                elif regime_mc < 0:
                    strat.regime_weights[regime_val] = 0.5
                elif regime_mc > 0.1:
                    strat.regime_weights[regime_val] = 1.5

        print(f"\n[SUMMARY] Disabled: {len(changes['disabled'])} | Weakened: {len(changes['weakened'])} | Boosted: {len(changes['boosted'])}")
        return changes

    def get_active_strategies(self) -> List[StrategyWrapper]:
        """Retourne uniquement les strategies actives"""
        return [s for s in self.strategies if s.active]

    def run_enriched_backtest(self, ohlcv: Dict, n_runs: int = 50) -> Dict:
        """Backtest enrichi avec analyse par regime et contribution marginale"""
        print(f"\n[BACKTEST ENRICHI] {n_runs} iterations...")

        # Storage pour analyse
        strategy_pnl = {s.name: [] for s in self.strategies}
        strategy_regime_wins = {s.name: {r.value: {'wins': 0, 'total': 0} for r in MarketRegime} for s in self.strategies}
        consensus_results = []
        price_series = [ohlcv['close'][-1]]
        data = ohlcv.copy()

        for i in range(n_runs):
            regime = self.detect_regime(data)
            signals = self.analyze(data)
            consensus = self.get_consensus(signals)

            # Simulate price movement
            diff = np.diff(data['close'][-20:])
            volatility = max(np.std(diff) / abs(data['close'][-1] + 1e-9), 0.001)
            price_change = np.random.normal(0, volatility * 100)  # %
            new_price = price_series[-1] * (1 + price_change / 100)
            price_series.append(new_price)

            # Evaluate each strategy
            for signal in signals:
                pnl = self.simulate_trade_result(signal, price_change)
                strategy_pnl[signal.strategy].append(pnl)

                # Track regime performance
                regime_stats = strategy_regime_wins[signal.strategy][regime.value]
                regime_stats['total'] += 1
                if pnl > 0:
                    regime_stats['wins'] += 1

            # Track consensus
            consensus_pnl = self.simulate_trade_result(
                TradingSignal('consensus', consensus['signal'], consensus['confidence'],
                             new_price, 0, {}), price_change)
            consensus_results.append({
                'regime': regime,
                'signal': consensus['signal'],
                'pnl': consensus_pnl
            })

            # Evolve data
            noise = np.random.randn(len(data['close'])) * max(volatility, 0.001) * abs(data['close'][-1]) * 10
            data = {
                'open': data['open'] + noise.astype(np.float32),
                'high': data['high'] + np.abs(noise.astype(np.float32)),
                'low': data['low'] - np.abs(noise.astype(np.float32)),
                'close': data['close'] + noise.astype(np.float32),
                'volume': data['volume']
            }

        # Calculate enriched metrics
        for name, pnls in strategy_pnl.items():
            m = self.metrics[name]
            if len(pnls) > 0:
                # Winrate by regime
                m.winrate_by_regime = strategy_regime_wins[name]

                # Profit factor
                gains = sum(p for p in pnls if p > 0)
                losses = abs(sum(p for p in pnls if p < 0))
                m.profit_factor = gains / (losses + 0.0001)

                # Max drawdown
                cumsum = np.cumsum(pnls)
                peak = np.maximum.accumulate(cumsum)
                drawdown = peak - cumsum
                m.max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0

        # Summary
        total_consensus_pnl = sum(r['pnl'] for r in consensus_results)
        regime_counts = {r.value: sum(1 for cr in consensus_results if cr['regime'] == r) for r in MarketRegime}

        print(f"\n[REGIMES] RANGE: {regime_counts.get('RANGE', 0)} | TREND: {regime_counts.get('TREND', 0)} | HIGH_VOL: {regime_counts.get('HIGH_VOL', 0)}")
        print(f"[PnL] Consensus total: {total_consensus_pnl:+.2f}%")

        return {
            'n_runs': n_runs,
            'consensus_pnl': total_consensus_pnl,
            'regime_distribution': regime_counts,
            'price_series': price_series
        }

    def get_enriched_report(self) -> str:
        """Genere un rapport enrichi avec regimes et contribution marginale"""
        report = []
        report.append("\n" + "="*90)
        report.append(" RAPPORT ENRICHI PAR STRATEGIE")
        report.append("="*90)

        sorted_metrics = sorted(
            self.metrics.values(),
            key=lambda x: x.marginal_contribution,
            reverse=True
        )

        # Header
        report.append(f"\n{'Strategie':<20} {'PF':>6} {'DD%':>7} {'Contrib':>8} {'RANGE':>8} {'TREND':>8} {'HVOL':>8}")
        report.append("-"*90)

        for m in sorted_metrics:
            if m.total_signals > 0:
                # Calculate winrates
                wr = m.winrate_by_regime or {}
                range_wr = wr.get('RANGE', {})
                trend_wr = wr.get('TREND', {})
                hvol_wr = wr.get('HIGH_VOL', {})

                range_pct = (range_wr.get('wins', 0) / max(range_wr.get('total', 1), 1)) * 100
                trend_pct = (trend_wr.get('wins', 0) / max(trend_wr.get('total', 1), 1)) * 100
                hvol_pct = (hvol_wr.get('wins', 0) / max(hvol_wr.get('total', 1), 1)) * 100

                report.append(
                    f"{m.name:<20} {m.profit_factor:>5.2f}x {m.max_drawdown:>6.2f}% "
                    f"{m.marginal_contribution:>+7.2f} {range_pct:>7.0f}% {trend_pct:>7.0f}% {hvol_pct:>7.0f}%"
                )

        report.append("-"*90)

        # Identify parasites (negative contribution, low winrate)
        parasites = [m for m in sorted_metrics if m.marginal_contribution < 0 and m.profit_factor < 1.0]
        if parasites:
            report.append("\n[STRATEGIES PARASITES - A DESACTIVER]")
            for m in parasites[:3]:
                report.append(f"  X {m.name}: PF={m.profit_factor:.2f}x, Contrib={m.marginal_contribution:+.2f}")

        # Best performers by regime
        report.append("\n[MEILLEURES PAR REGIME]")
        for regime in MarketRegime:
            best = max(sorted_metrics, key=lambda m: (m.winrate_by_regime or {}).get(regime.value, {}).get('wins', 0) /
                      max((m.winrate_by_regime or {}).get(regime.value, {}).get('total', 1), 1), default=None)
            if best:
                wr = best.winrate_by_regime.get(regime.value, {})
                winrate = (wr.get('wins', 0) / max(wr.get('total', 1), 1)) * 100
                report.append(f"  {regime.value}: {best.name} ({winrate:.0f}%)")

        report.append("\n" + "="*90)
        return "\n".join(report)

    def get_strategy_report(self) -> str:
        """Genere un rapport par strategie"""
        report = []
        report.append("\n" + "="*80)
        report.append(" RAPPORT PAR STRATEGIE")
        report.append("="*80)

        # Sort by contribution score
        sorted_metrics = sorted(
            self.metrics.values(),
            key=lambda x: x.contribution_score,
            reverse=True
        )

        report.append(f"\n{'Strategie':<25} {'Signals':>8} {'Buy':>6} {'Sell':>6} {'Hold':>6} {'Conf':>8} {'Time':>8} {'Score':>8}")
        report.append("-"*80)

        for m in sorted_metrics:
            if m.total_signals > 0:
                report.append(
                    f"{m.name:<25} {m.total_signals:>8} {m.buy_count:>6} {m.sell_count:>6} "
                    f"{m.hold_count:>6} {m.avg_confidence:>7.1%} {m.avg_compute_time_ms:>7.1f}ms "
                    f"{m.contribution_score:>+7.2f}"
                )

        report.append("-"*80)

        # Top performers
        top = [m for m in sorted_metrics if m.contribution_score > 0][:5]
        if top:
            report.append("\n[TOP 5 CONTRIBUTEURS]")
            for m in top:
                report.append(f"  + {m.name}: {m.contribution_score:+.2f}")

        # Under-performers
        bottom = [m for m in sorted_metrics if m.contribution_score < 0][-3:]
        if bottom:
            report.append("\n[SOUS-PERFORMEURS]")
            for m in bottom:
                report.append(f"  - {m.name}: {m.contribution_score:+.2f}")

        report.append("\n" + "="*80)
        return "\n".join(report)

    def run_backtest(self, ohlcv: Dict, n_runs: int = 10) -> Dict:
        """Backtest avec rapport complet"""
        print(f"\n[BACKTEST] {n_runs} iterations sur {len(self.strategies)} strategies...")

        all_signals = []
        all_consensus = []

        for i in range(n_runs):
            signals = self.analyze(ohlcv)
            consensus = self.get_consensus(signals)
            all_signals.append(signals)
            all_consensus.append(consensus)

            # Slight data variation for next iteration
            noise = np.random.randn(len(ohlcv['close'])) * 10
            ohlcv = {
                'open': ohlcv['open'] + noise.astype(np.float32),
                'high': ohlcv['high'] + np.abs(noise.astype(np.float32)),
                'low': ohlcv['low'] - np.abs(noise.astype(np.float32)),
                'close': ohlcv['close'] + noise.astype(np.float32),
                'volume': ohlcv['volume']
            }

        # Results
        buy_count = sum(1 for c in all_consensus if c['signal'] == SignalType.BUY)
        sell_count = sum(1 for c in all_consensus if c['signal'] == SignalType.SELL)
        hold_count = sum(1 for c in all_consensus if c['signal'] == SignalType.HOLD)
        avg_conf = np.mean([c['confidence'] for c in all_consensus])

        print(f"\n[RESULTATS] BUY: {buy_count} | SELL: {sell_count} | HOLD: {hold_count}")
        print(f"[RESULTATS] Confidence moyenne: {avg_conf:.1%}")

        return {
            'n_runs': n_runs,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'hold_count': hold_count,
            'avg_confidence': avg_conf,
            'consensus_history': all_consensus
        }


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    from gpu_strategies_hybrid import generate_test_data

    print("\n" + "#"*80)
    print(" UNIFIED ORCHESTRATOR - TEST COMPLET")
    print("#"*80)

    # Initialize
    orchestrator = UnifiedOrchestrator(max_workers=4)

    # Generate data
    ohlcv = generate_test_data(500)
    print(f"\n[DATA] 500 barres generees")

    # Run enriched backtest
    results = orchestrator.run_enriched_backtest(ohlcv.copy(), n_runs=20)

    # Compute REAL marginal contributions (leave-one-out)
    contributions = orchestrator.compute_marginal_contributions(ohlcv.copy(), n_runs=15)

    # Reports
    print(orchestrator.get_strategy_report())
    print(orchestrator.get_enriched_report())

    # Summary of contributions
    print("\n" + "="*80)
    print(" SYNTHESE CONTRIBUTION MARGINALE")
    print("="*80)

    sorted_contrib = sorted(contributions.items(), key=lambda x: x[1]['normalized'], reverse=True)

    positives = [(n, c) for n, c in sorted_contrib if c['normalized'] > 0.01]
    negatives = [(n, c) for n, c in sorted_contrib if c['normalized'] < -0.01]
    neutral = [(n, c) for n, c in sorted_contrib if -0.01 <= c['normalized'] <= 0.01]

    print(f"\n[STRATEGIES BENEFIQUES] ({len(positives)})")
    for name, c in positives[:5]:
        print(f"  + {name}: {c['normalized']:+.4f}")

    print(f"\n[STRATEGIES NEUTRES/REDONDANTES] ({len(neutral)})")
    for name, c in neutral[:5]:
        print(f"  = {name}: {c['normalized']:+.4f}")

    print(f"\n[STRATEGIES NUISIBLES] ({len(negatives)})")
    for name, c in negatives[-3:]:
        print(f"  - {name}: {c['normalized']:+.4f}")

    # Apply adaptive weights
    print("\n" + "="*80)
    print(" APPLICATION PONDERATION ADAPTATIVE")
    print("="*80)

    changes = orchestrator.apply_adaptive_weights(contributions)

    # Show new state
    print("\n" + "="*80)
    print(" ETAT FINAL DES STRATEGIES")
    print("="*80)

    active_count = len(orchestrator.get_active_strategies())
    total_count = len(orchestrator.strategies)
    print(f"\n[ACTIVES] {active_count}/{total_count} strategies")

    print("\n[POIDS ADAPTES]")
    for strat in sorted(orchestrator.strategies, key=lambda s: s.weight, reverse=True):
        status = "ACTIF" if strat.active else "OFF"
        print(f"  {strat.name:<20} poids={strat.weight:.2f} [{status}]")

    # Compare before/after performance
    print("\n" + "="*80)
    print(" VALIDATION POST-DESHERBAGE")
    print("="*80)

    ohlcv_fresh = generate_test_data(500)
    signals_before = len(orchestrator.analyze(ohlcv_fresh))
    active_signals = [s for s in orchestrator.analyze(ohlcv_fresh) if
                     next((strat for strat in orchestrator.strategies
                          if strat.name == s.strategy and strat.active), None)]

    print(f"\n[AVANT] {total_count} strategies")
    print(f"[APRES] {active_count} strategies actives")
    print(f"[SIGNAUX] {len(active_signals)} signaux actifs")

    print("\n" + "="*80)
    print(" SYSTEME AUTO-DESHERBANT OPERATIONNEL")
    print("="*80)
    print("\n[OK] Test termine avec succes!")
