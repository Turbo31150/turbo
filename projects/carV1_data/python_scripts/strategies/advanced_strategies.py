#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADVANCED STRATEGIES - Strategies avancees extraites de TradingView
Inclut: Liquidity Maxing, ML SuperTrend, Crypto Momentum, OCC Strategy
"""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum
import time

class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

@dataclass
class TradingSignal:
    strategy: str
    signal_type: SignalType
    confidence: float
    price: float
    compute_time_ms: float
    indicators: Dict

# ============================================================================
# INDICATEURS AVANCES
# ============================================================================

def ema(data: np.ndarray, period: int) -> np.ndarray:
    """EMA vectorise"""
    alpha = 2.0 / (period + 1)
    result = np.zeros_like(data, dtype=np.float32)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
    return result

def sma(data: np.ndarray, period: int) -> np.ndarray:
    """SMA vectorise"""
    kernel = np.ones(period, dtype=np.float32) / period
    result = np.convolve(data, kernel, mode='same')
    for i in range(min(period - 1, len(data))):
        result[i] = np.mean(data[:i+1])
    return result

def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range"""
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0]
    return ema(tr, period)

def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """RSI vectorise"""
    delta = np.diff(close)
    delta = np.concatenate([[0], delta])
    gains = np.where(delta > 0, delta, 0)
    losses = np.where(delta < 0, -delta, 0)
    avg_gain = ema(gains.astype(np.float32), period)
    avg_loss = ema(losses.astype(np.float32), period)
    rs = np.where(avg_loss != 0, avg_gain / avg_loss, 100)
    return 100 - (100 / (1 + rs))

def macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD avec signal et histogramme"""
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def bollinger_bands(close: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger Bands"""
    middle = sma(close, period)
    rolling_std = np.array([np.std(close[max(0, i-period+1):i+1]) for i in range(len(close))], dtype=np.float32)
    upper = middle + std_dev * rolling_std
    lower = middle - std_dev * rolling_std
    return upper, middle, lower

def keltner_channels(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 20, mult: float = 1.5) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Keltner Channels"""
    middle = ema(close, period)
    atr_val = atr(high, low, close, period)
    upper = middle + mult * atr_val
    lower = middle - mult * atr_val
    return upper, middle, lower

def supertrend(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 10, multiplier: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    """SuperTrend indicator"""
    atr_val = atr(high, low, close, period)
    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr_val
    lower_band = hl2 - multiplier * atr_val

    supertrend = np.zeros_like(close)
    direction = np.ones(len(close))  # 1 = up, -1 = down

    for i in range(1, len(close)):
        if close[i] > upper_band[i-1]:
            direction[i] = 1
        elif close[i] < lower_band[i-1]:
            direction[i] = -1
        else:
            direction[i] = direction[i-1]
            if direction[i] == 1:
                lower_band[i] = max(lower_band[i], lower_band[i-1])
            else:
                upper_band[i] = min(upper_band[i], upper_band[i-1])

        supertrend[i] = lower_band[i] if direction[i] == 1 else upper_band[i]

    return supertrend, direction

def hull_ma(data: np.ndarray, period: int = 9) -> np.ndarray:
    """Hull Moving Average - plus reactif"""
    half_period = period // 2
    sqrt_period = int(np.sqrt(period))
    wma1 = sma(data, half_period)  # Simplified WMA
    wma2 = sma(data, period)
    diff = 2 * wma1 - wma2
    return sma(diff, sqrt_period)

def mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, period: int = 14) -> np.ndarray:
    """Money Flow Index"""
    typical_price = (high + low + close) / 3
    raw_money_flow = typical_price * volume

    delta = np.diff(typical_price)
    delta = np.concatenate([[0], delta])

    positive_flow = np.where(delta > 0, raw_money_flow, 0)
    negative_flow = np.where(delta < 0, raw_money_flow, 0)

    pos_sum = np.array([np.sum(positive_flow[max(0, i-period+1):i+1]) for i in range(len(close))], dtype=np.float32)
    neg_sum = np.array([np.sum(negative_flow[max(0, i-period+1):i+1]) for i in range(len(close))], dtype=np.float32)

    money_ratio = np.where(neg_sum != 0, pos_sum / neg_sum, 100)
    return 100 - (100 / (1 + money_ratio))

def pivots(high: np.ndarray, low: np.ndarray, left: int = 5, right: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """Detect pivot highs and lows"""
    pivot_highs = np.zeros_like(high)
    pivot_lows = np.zeros_like(low)

    for i in range(left, len(high) - right):
        is_pivot_high = True
        is_pivot_low = True

        for j in range(1, left + 1):
            if high[i] <= high[i - j]:
                is_pivot_high = False
            if low[i] >= low[i - j]:
                is_pivot_low = False

        for j in range(1, right + 1):
            if high[i] <= high[i + j]:
                is_pivot_high = False
            if low[i] >= low[i + j]:
                is_pivot_low = False

        if is_pivot_high:
            pivot_highs[i] = high[i]
        if is_pivot_low:
            pivot_lows[i] = low[i]

    return pivot_highs, pivot_lows

# ============================================================================
# STRATEGIES AVANCEES
# ============================================================================

class CryptoMomentumStrategy:
    """
    Crypto Momentum Strategy - Optimise pour 5min
    MACD 8/21/5 + EMA 8/21/34 + RSI 21 + BB/Keltner Squeeze
    """
    def __init__(self):
        self.name = "Crypto_Momentum"
        self.weight = 0.15

    def analyze(self, ohlcv: Dict) -> TradingSignal:
        start = time.perf_counter()
        close = ohlcv['close'].astype(np.float32)
        high = ohlcv['high'].astype(np.float32)
        low = ohlcv['low'].astype(np.float32)
        volume = ohlcv['volume'].astype(np.float32)

        # MACD 8/21/5 (crypto optimized)
        macd_line, signal_line, histogram = macd(close, 8, 21, 5)

        # EMA Ribbon 8/21/34
        ema8 = ema(close, 8)
        ema21 = ema(close, 21)
        ema34 = ema(close, 34)

        # RSI 21
        rsi_val = rsi(close, 21)

        # MFI 21
        mfi_val = mfi(high, low, close, volume, 21)

        # BB/Keltner Squeeze
        bb_upper, bb_middle, bb_lower = bollinger_bands(close, 20, 1.5)
        kc_upper, kc_middle, kc_lower = keltner_channels(high, low, close, 20, 1.5)
        squeeze = (bb_upper[-1] < kc_upper[-1]) and (bb_lower[-1] > kc_lower[-1])

        # ATR Volatility Regime
        atr_val = atr(high, low, close, 21)
        atr_pct = (atr_val[-1] / close[-1]) * 100

        # Scoring
        score = 0

        # Trend (EMA ribbon)
        if ema8[-1] > ema21[-1] > ema34[-1]:
            score += 30
        elif ema8[-1] < ema21[-1] < ema34[-1]:
            score -= 30

        # Momentum (MACD)
        if histogram[-1] > 0 and histogram[-1] > histogram[-2]:
            score += 25
        elif histogram[-1] < 0 and histogram[-1] < histogram[-2]:
            score -= 25

        # RSI
        if 55 < rsi_val[-1] < 75:
            score += 15
        elif 25 < rsi_val[-1] < 45:
            score -= 15

        # MFI
        if mfi_val[-1] > 55:
            score += 10
        elif mfi_val[-1] < 45:
            score -= 10

        # Squeeze Release
        if squeeze and histogram[-1] > 0:
            score += 20
        elif squeeze and histogram[-1] < 0:
            score -= 20

        # Signal
        if score >= 50:
            signal = SignalType.BUY
            confidence = min(0.95, 0.5 + score / 200)
        elif score <= -50:
            signal = SignalType.SELL
            confidence = min(0.95, 0.5 + abs(score) / 200)
        else:
            signal = SignalType.HOLD
            confidence = 0.3

        compute_time = (time.perf_counter() - start) * 1000

        return TradingSignal(
            strategy=self.name,
            signal_type=signal,
            confidence=confidence,
            price=float(close[-1]),
            compute_time_ms=compute_time,
            indicators={
                'macd_hist': float(histogram[-1]),
                'rsi': float(rsi_val[-1]),
                'mfi': float(mfi_val[-1]),
                'atr_pct': float(atr_pct),
                'squeeze': squeeze,
                'score': score
            }
        )


class LiquidityMaxingStrategy:
    """
    Liquidity Maxing Strategy - Structure-based
    8-factor scoring, market structure analysis
    """
    def __init__(self):
        self.name = "Liquidity_Maxing"
        self.weight = 0.15

    def analyze(self, ohlcv: Dict) -> TradingSignal:
        start = time.perf_counter()
        close = ohlcv['close'].astype(np.float32)
        high = ohlcv['high'].astype(np.float32)
        low = ohlcv['low'].astype(np.float32)
        volume = ohlcv['volume'].astype(np.float32)

        # Structure Detection
        pivot_highs, pivot_lows = pivots(high, low, 5, 5)

        # Find last valid pivots
        valid_highs = np.where(pivot_highs > 0)[0]
        valid_lows = np.where(pivot_lows > 0)[0]

        last_pivot_high = pivot_highs[valid_highs[-1]] if len(valid_highs) > 0 else high[-10:].max()
        last_pivot_low = pivot_lows[valid_lows[-1]] if len(valid_lows) > 0 else low[-10:].min()

        # Break of Structure (BOS)
        bos_bullish = close[-1] > last_pivot_high
        bos_bearish = close[-1] < last_pivot_low

        # 8-Factor Scoring System
        score = 0

        # 1. Structure alignment
        ema200 = ema(close, 200) if len(close) >= 200 else ema(close, min(50, len(close)))
        if close[-1] > ema200[-1]:
            score += 1  # Bullish structure
        else:
            score -= 1  # Bearish structure

        # 2. RSI bands
        rsi_val = rsi(close, 14)
        if 30 < rsi_val[-1] < 70:
            score += 1 if rsi_val[-1] > 50 else -1

        # 3. MACD momentum
        macd_line, signal_line, histogram = macd(close, 12, 26, 9)
        if histogram[-1] > 0:
            score += 1
        else:
            score -= 1

        # 4. Volume confirmation
        vol_sma = sma(volume, 20)
        if volume[-1] > vol_sma[-1] * 1.2:
            score += 1 if close[-1] > close[-2] else -1

        # 5. Price vs EMA
        ema50 = ema(close, 50) if len(close) >= 50 else ema(close, min(20, len(close)))
        if close[-1] > ema50[-1]:
            score += 1
        else:
            score -= 1

        # 6. ATR volatility
        atr_val = atr(high, low, close, 14)
        atr_sma = sma(atr_val, 14)
        if atr_val[-1] > atr_sma[-1]:
            score += 1  # Expansion

        # 7. Higher TF trend (simplified with 100 EMA)
        ema100 = ema(close, 100) if len(close) >= 100 else ema(close, min(30, len(close)))
        if close[-1] > ema100[-1]:
            score += 1
        else:
            score -= 1

        # 8. BOS confirmation
        if bos_bullish:
            score += 2
        elif bos_bearish:
            score -= 2

        # Signal
        if score >= 5:
            signal = SignalType.BUY
            confidence = min(0.90, 0.5 + score / 16)
        elif score <= -5:
            signal = SignalType.SELL
            confidence = min(0.90, 0.5 + abs(score) / 16)
        else:
            signal = SignalType.HOLD
            confidence = 0.3

        compute_time = (time.perf_counter() - start) * 1000

        return TradingSignal(
            strategy=self.name,
            signal_type=signal,
            confidence=confidence,
            price=float(close[-1]),
            compute_time_ms=compute_time,
            indicators={
                'score': score,
                'bos_bullish': bos_bullish,
                'bos_bearish': bos_bearish,
                'rsi': float(rsi_val[-1]),
                'macd_hist': float(histogram[-1])
            }
        )


class MLAdaptiveSuperTrendStrategy:
    """
    ML Adaptive SuperTrend - K-Means volatility clustering
    Adapte ATR selon regime de volatilite
    """
    def __init__(self):
        self.name = "ML_SuperTrend"
        self.weight = 0.12

    def _kmeans_volatility(self, atr_values: np.ndarray, k: int = 3, max_iter: int = 10) -> Tuple[np.ndarray, int]:
        """Simple K-means for volatility clustering"""
        # Initialize centroids
        sorted_atr = np.sort(atr_values)
        centroids = np.array([
            sorted_atr[len(sorted_atr) // 4],      # Low
            sorted_atr[len(sorted_atr) // 2],      # Medium
            sorted_atr[3 * len(sorted_atr) // 4]   # High
        ])

        for _ in range(max_iter):
            # Assign to nearest centroid
            distances = np.abs(atr_values[:, np.newaxis] - centroids)
            labels = np.argmin(distances, axis=1)

            # Update centroids
            new_centroids = np.array([
                atr_values[labels == i].mean() if np.sum(labels == i) > 0 else centroids[i]
                for i in range(k)
            ])

            if np.allclose(centroids, new_centroids):
                break
            centroids = new_centroids

        # Sort centroids (0=low, 1=medium, 2=high)
        sorted_idx = np.argsort(centroids)
        centroids = centroids[sorted_idx]

        # Current regime
        current_atr = atr_values[-1]
        distances = np.abs(current_atr - centroids)
        current_regime = np.argmin(distances)

        return centroids, current_regime

    def analyze(self, ohlcv: Dict) -> TradingSignal:
        start = time.perf_counter()
        close = ohlcv['close'].astype(np.float32)
        high = ohlcv['high'].astype(np.float32)
        low = ohlcv['low'].astype(np.float32)

        # Calculate ATR
        atr_val = atr(high, low, close, 14)

        # K-Means volatility clustering
        lookback = min(100, len(atr_val))
        centroids, regime = self._kmeans_volatility(atr_val[-lookback:])

        # Adaptive multiplier based on regime
        multipliers = {0: 2.0, 1: 3.0, 2: 4.0}  # Low, Medium, High volatility
        adaptive_mult = multipliers[regime]

        # Calculate SuperTrend with adaptive ATR
        st_line, direction = supertrend(high, low, close, 10, adaptive_mult)

        # Trend confirmation
        ema21 = ema(close, 21)
        trend_bullish = direction[-1] == 1 and close[-1] > ema21[-1]
        trend_bearish = direction[-1] == -1 and close[-1] < ema21[-1]

        # Signal
        if trend_bullish and direction[-2] == -1:  # Flip to bullish
            signal = SignalType.BUY
            confidence = 0.80
        elif trend_bearish and direction[-2] == 1:  # Flip to bearish
            signal = SignalType.SELL
            confidence = 0.80
        elif direction[-1] == 1:
            signal = SignalType.HOLD
            confidence = 0.55
        else:
            signal = SignalType.HOLD
            confidence = 0.45

        compute_time = (time.perf_counter() - start) * 1000

        regime_names = {0: "Low", 1: "Medium", 2: "High"}

        return TradingSignal(
            strategy=self.name,
            signal_type=signal,
            confidence=confidence,
            price=float(close[-1]),
            compute_time_ms=compute_time,
            indicators={
                'supertrend': float(st_line[-1]),
                'direction': int(direction[-1]),
                'regime': regime_names[regime],
                'adaptive_mult': adaptive_mult,
                'atr': float(atr_val[-1])
            }
        )


class OCCStrategy:
    """
    Open Close Cross Strategy - Optimized
    Moving average crossover on Open vs Close
    """
    def __init__(self):
        self.name = "OCC_Cross"
        self.weight = 0.10

    def analyze(self, ohlcv: Dict) -> TradingSignal:
        start = time.perf_counter()
        open_p = ohlcv['open'].astype(np.float32)
        close = ohlcv['close'].astype(np.float32)
        high = ohlcv['high'].astype(np.float32)
        low = ohlcv['low'].astype(np.float32)

        # Moving averages on open and close
        period = 10
        open_ma = sma(open_p, period)
        close_ma = sma(close, period)

        # Crossover detection
        prev_diff = close_ma[-2] - open_ma[-2]
        curr_diff = close_ma[-1] - open_ma[-1]

        bullish_cross = prev_diff <= 0 and curr_diff > 0
        bearish_cross = prev_diff >= 0 and curr_diff < 0

        # Trend filter (EMA 200)
        ema200 = ema(close, min(200, len(close)))
        above_trend = close[-1] > ema200[-1]

        # RSI filter
        rsi_val = rsi(close, 14)
        rsi_ok_long = rsi_val[-1] < 70
        rsi_ok_short = rsi_val[-1] > 30

        # Signal
        if bullish_cross and above_trend and rsi_ok_long:
            signal = SignalType.BUY
            confidence = 0.75
        elif bearish_cross and not above_trend and rsi_ok_short:
            signal = SignalType.SELL
            confidence = 0.75
        elif curr_diff > 0:
            signal = SignalType.HOLD
            confidence = 0.5
        else:
            signal = SignalType.HOLD
            confidence = 0.4

        compute_time = (time.perf_counter() - start) * 1000

        return TradingSignal(
            strategy=self.name,
            signal_type=signal,
            confidence=confidence,
            price=float(close[-1]),
            compute_time_ms=compute_time,
            indicators={
                'open_ma': float(open_ma[-1]),
                'close_ma': float(close_ma[-1]),
                'diff': float(curr_diff),
                'rsi': float(rsi_val[-1]),
                'above_trend': above_trend
            }
        )


class HMASuperTrendStrategy:
    """
    HMA + SuperTrend Combo Strategy
    Hull MA for faster signals + SuperTrend confirmation
    """
    def __init__(self):
        self.name = "HMA_SuperTrend"
        self.weight = 0.12

    def analyze(self, ohlcv: Dict) -> TradingSignal:
        start = time.perf_counter()
        close = ohlcv['close'].astype(np.float32)
        high = ohlcv['high'].astype(np.float32)
        low = ohlcv['low'].astype(np.float32)

        # Hull MA
        hma = hull_ma(close, 9)
        hma_rising = hma[-1] > hma[-2]
        hma_falling = hma[-1] < hma[-2]

        # SuperTrend
        st_line, direction = supertrend(high, low, close, 10, 3.0)
        st_bullish = direction[-1] == 1
        st_bearish = direction[-1] == -1

        # Combined signal
        if hma_rising and st_bullish:
            signal = SignalType.BUY
            confidence = 0.80
        elif hma_falling and st_bearish:
            signal = SignalType.SELL
            confidence = 0.80
        elif st_bullish:
            signal = SignalType.HOLD
            confidence = 0.55
        elif st_bearish:
            signal = SignalType.HOLD
            confidence = 0.45
        else:
            signal = SignalType.HOLD
            confidence = 0.35

        compute_time = (time.perf_counter() - start) * 1000

        return TradingSignal(
            strategy=self.name,
            signal_type=signal,
            confidence=confidence,
            price=float(close[-1]),
            compute_time_ms=compute_time,
            indicators={
                'hma': float(hma[-1]),
                'hma_rising': hma_rising,
                'supertrend': float(st_line[-1]),
                'st_direction': int(direction[-1])
            }
        )


class VolatilityRegimeStrategy:
    """
    ATR Volatility Regime Strategy
    Adapte selon: Compression (<0.8%), Normal (0.8-1.6%), Velocity (>1.6%)
    """
    def __init__(self):
        self.name = "Volatility_Regime"
        self.weight = 0.10

    def analyze(self, ohlcv: Dict) -> TradingSignal:
        start = time.perf_counter()
        close = ohlcv['close'].astype(np.float32)
        high = ohlcv['high'].astype(np.float32)
        low = ohlcv['low'].astype(np.float32)

        # ATR as percentage of price
        atr_val = atr(high, low, close, 21)
        atr_smooth = ema(atr_val, 13)
        atr_pct = (atr_smooth[-1] / close[-1]) * 100

        # Regime classification
        if atr_pct < 0.8:
            regime = "Compression"
            stop_mult = 1.05
            target_mult = 1.6
        elif atr_pct > 1.6:
            regime = "Velocity"
            stop_mult = 2.1
            target_mult = 2.8
        else:
            regime = "Normal"
            stop_mult = 1.55
            target_mult = 2.05

        # Trend
        ema21 = ema(close, 21)
        ema55 = ema(close, 55)
        bullish = close[-1] > ema21[-1] > ema55[-1]
        bearish = close[-1] < ema21[-1] < ema55[-1]

        # MACD for entry timing
        macd_line, signal_line, histogram = macd(close, 8, 21, 5)
        macd_bullish = histogram[-1] > 0 and histogram[-1] > histogram[-2]
        macd_bearish = histogram[-1] < 0 and histogram[-1] < histogram[-2]

        # Signal based on regime
        if bullish and macd_bullish:
            signal = SignalType.BUY
            confidence = 0.70 if regime == "Normal" else 0.60
        elif bearish and macd_bearish:
            signal = SignalType.SELL
            confidence = 0.70 if regime == "Normal" else 0.60
        else:
            signal = SignalType.HOLD
            confidence = 0.35

        compute_time = (time.perf_counter() - start) * 1000

        return TradingSignal(
            strategy=self.name,
            signal_type=signal,
            confidence=confidence,
            price=float(close[-1]),
            compute_time_ms=compute_time,
            indicators={
                'regime': regime,
                'atr_pct': float(atr_pct),
                'stop_mult': stop_mult,
                'target_mult': target_mult,
                'macd_hist': float(histogram[-1])
            }
        )


def get_advanced_strategies() -> List:
    """Retourne toutes les strategies avancees"""
    return [
        CryptoMomentumStrategy(),
        LiquidityMaxingStrategy(),
        MLAdaptiveSuperTrendStrategy(),
        OCCStrategy(),
        HMASuperTrendStrategy(),
        VolatilityRegimeStrategy()
    ]


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print(" STRATEGIES AVANCEES - TEST")
    print("="*60 + "\n")

    # Generate test data
    np.random.seed(42)
    n = 500
    close = 50000 + np.cumsum(np.random.randn(n) * 100)
    high = close + np.abs(np.random.randn(n) * 50)
    low = close - np.abs(np.random.randn(n) * 50)
    open_p = close + np.random.randn(n) * 30
    volume = np.random.uniform(1000, 10000, n)

    ohlcv = {
        'open': open_p.astype(np.float32),
        'high': high.astype(np.float32),
        'low': low.astype(np.float32),
        'close': close.astype(np.float32),
        'volume': volume.astype(np.float32)
    }

    strategies = get_advanced_strategies()
    print(f"[TEST] {len(strategies)} strategies avancees\n")

    total_time = 0
    for strategy in strategies:
        signal = strategy.analyze(ohlcv)
        total_time += signal.compute_time_ms

        icon = {"BUY": "[+]", "SELL": "[-]", "HOLD": "[=]"}
        print(f"{icon.get(signal.signal_type.value, '[?]')} {signal.strategy:20s} | {signal.signal_type.value:4s} | Conf: {signal.confidence:.2f} | {signal.compute_time_ms:.2f}ms")

        # Print key indicators
        for k, v in list(signal.indicators.items())[:3]:
            print(f"    {k}: {v}")
        print()

    print("-"*60)
    print(f"Total compute time: {total_time:.2f}ms")
    print("="*60 + "\n")
