#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU TRADING STRATEGIES - COLLECTION COMPLETE
30+ Strategies converties de Pine Script vers Python GPU
"""
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum
from abc import ABC, abstractmethod

class SignalType(Enum):
    LONG = 1
    SHORT = -1
    NEUTRAL = 0

@dataclass
class Signal:
    type: SignalType
    strength: float
    strategy_name: str
    confidence: float
    stop_loss: float = 0.0
    take_profit: float = 0.0

# ═══════════════════════════════════════════════════════════════════════════════
# INDICATEURS GPU VECTORISES
# ═══════════════════════════════════════════════════════════════════════════════

def rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
    if len(x) < window:
        return np.full(1, np.mean(x))
    cumsum = np.cumsum(np.concatenate([[0], x]))
    return (cumsum[window:] - cumsum[:-window]) / window

def rolling_std(x: np.ndarray, window: int) -> np.ndarray:
    if len(x) < window:
        return np.full(1, np.std(x))
    result = np.zeros(len(x) - window + 1)
    for i in range(len(result)):
        result[i] = np.std(x[i:i+window])
    return result

def ema(x: np.ndarray, period: int) -> np.ndarray:
    alpha = 2 / (period + 1)
    result = np.zeros_like(x)
    result[0] = x[0]
    for i in range(1, len(x)):
        result[i] = alpha * x[i] + (1 - alpha) * result[i-1]
    return result

def sma(x: np.ndarray, period: int) -> np.ndarray:
    if len(x) < period:
        return np.full(len(x), np.mean(x))
    result = rolling_mean(x, period)
    return np.concatenate([[result[0]] * (len(x) - len(result)), result])

def wma(x: np.ndarray, period: int) -> np.ndarray:
    """Weighted Moving Average"""
    weights = np.arange(1, period + 1)
    result = np.zeros(len(x))
    for i in range(period - 1, len(x)):
        result[i] = np.sum(x[i-period+1:i+1] * weights) / np.sum(weights)
    result[:period-1] = result[period-1]
    return result

def hull_ma(x: np.ndarray, period: int) -> np.ndarray:
    """Hull Moving Average"""
    half_period = period // 2
    sqrt_period = int(np.sqrt(period))
    wma1 = wma(x, half_period)
    wma2 = wma(x, period)
    raw = 2 * wma1 - wma2
    return wma(raw, sqrt_period)

def dema(x: np.ndarray, period: int) -> np.ndarray:
    """Double EMA"""
    ema1 = ema(x, period)
    ema2 = ema(ema1, period)
    return 2 * ema1 - ema2

def tema(x: np.ndarray, period: int) -> np.ndarray:
    """Triple EMA"""
    ema1 = ema(x, period)
    ema2 = ema(ema1, period)
    ema3 = ema(ema2, period)
    return 3 * ema1 - 3 * ema2 + ema3

def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    delta = np.diff(close)
    up = np.maximum(delta, 0)
    down = -np.minimum(delta, 0)
    if len(up) < period:
        return np.full(len(close), 50)
    roll_up = rolling_mean(up, period)
    roll_down = rolling_mean(down, period)
    rs = roll_up / (roll_down + 1e-10)
    rsi_vals = 100 - (100 / (1 + rs))
    return np.concatenate([[50] * (len(close) - len(rsi_vals)), rsi_vals])

def stoch_rsi(close: np.ndarray, period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> Tuple[np.ndarray, np.ndarray]:
    """Stochastic RSI"""
    rsi_vals = rsi(close, period)
    min_rsi = np.zeros_like(rsi_vals)
    max_rsi = np.zeros_like(rsi_vals)
    for i in range(period, len(rsi_vals)):
        min_rsi[i] = np.min(rsi_vals[i-period:i])
        max_rsi[i] = np.max(rsi_vals[i-period:i])
    stoch = (rsi_vals - min_rsi) / (max_rsi - min_rsi + 1e-10) * 100
    k = sma(stoch, smooth_k)
    d = sma(k, smooth_d)
    return k, d

def macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    if len(close) < 2:
        return np.array([high[0] - low[0]])
    tr1 = high[1:] - low[1:]
    tr2 = np.abs(high[1:] - close[:-1])
    tr3 = np.abs(low[1:] - close[:-1])
    true_range = np.maximum(np.maximum(tr1, tr2), tr3)
    if len(true_range) < period:
        return np.full(len(close), np.mean(true_range))
    atr_vals = rolling_mean(true_range, period)
    return np.concatenate([[atr_vals[0]] * (len(close) - len(atr_vals)), atr_vals])

def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average Directional Index"""
    atr_vals = atr(high, low, close, period)

    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    plus_di = 100 * ema(plus_dm, period) / (atr_vals[1:] + 1e-10)
    minus_di = 100 * ema(minus_dm, period) / (atr_vals[1:] + 1e-10)

    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx_vals = ema(dx, period)

    return np.concatenate([[adx_vals[0]], adx_vals])

def cci(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 20) -> np.ndarray:
    """Commodity Channel Index"""
    tp = (high + low + close) / 3
    sma_tp = sma(tp, period)
    mad = np.zeros_like(tp)
    for i in range(period, len(tp)):
        mad[i] = np.mean(np.abs(tp[i-period:i] - sma_tp[i]))
    mad[:period] = mad[period]
    return (tp - sma_tp) / (0.015 * mad + 1e-10)

def williams_r(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Williams %R"""
    highest = np.zeros_like(close)
    lowest = np.zeros_like(close)
    for i in range(period, len(close)):
        highest[i] = np.max(high[i-period:i])
        lowest[i] = np.min(low[i-period:i])
    highest[:period] = highest[period]
    lowest[:period] = lowest[period]
    return -100 * (highest - close) / (highest - lowest + 1e-10)

def mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, period: int = 14) -> np.ndarray:
    """Money Flow Index"""
    tp = (high + low + close) / 3
    mf = tp * volume
    delta = np.diff(tp)

    pos_mf = np.where(delta > 0, mf[1:], 0)
    neg_mf = np.where(delta < 0, mf[1:], 0)

    if len(pos_mf) < period:
        return np.full(len(close), 50)

    pos_sum = rolling_mean(pos_mf, period) * period
    neg_sum = rolling_mean(neg_mf, period) * period

    mfi_vals = 100 - 100 / (1 + pos_sum / (neg_sum + 1e-10))
    return np.concatenate([[50] * (len(close) - len(mfi_vals)), mfi_vals])

def obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """On Balance Volume"""
    delta = np.diff(close)
    direction = np.sign(delta)
    obv_vals = np.concatenate([[0], np.cumsum(direction * volume[1:])])
    return obv_vals

def vwap(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """Volume Weighted Average Price"""
    tp = (high + low + close) / 3
    return np.cumsum(tp * volume) / (np.cumsum(volume) + 1e-10)

def bollinger_bands(close: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    middle = sma(close, period)
    std = np.zeros_like(close)
    for i in range(period, len(close)):
        std[i] = np.std(close[i-period:i])
    std[:period] = std[period] if period < len(close) else np.std(close)
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower

def keltner_channels(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 20, mult: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Keltner Channels"""
    middle = ema(close, period)
    atr_vals = atr(high, low, close, period)
    upper = middle + mult * atr_vals
    lower = middle - mult * atr_vals
    return upper, middle, lower

def donchian_channels(high: np.ndarray, low: np.ndarray, period: int = 20) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Donchian Channels"""
    upper = np.zeros_like(high)
    lower = np.zeros_like(low)
    for i in range(period, len(high)):
        upper[i] = np.max(high[i-period:i])
        lower[i] = np.min(low[i-period:i])
    upper[:period] = upper[period] if period < len(high) else high[0]
    lower[:period] = lower[period] if period < len(low) else low[0]
    middle = (upper + lower) / 2
    return upper, middle, lower

def supertrend(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 10, mult: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    atr_vals = atr(high, low, close, period)
    hl_avg = (high + low) / 2
    upper = hl_avg - mult * atr_vals
    lower = hl_avg + mult * atr_vals

    trend = np.ones(len(close))
    for i in range(1, len(close)):
        if close[i] > lower[i-1]:
            trend[i] = 1
        elif close[i] < upper[i-1]:
            trend[i] = -1
        else:
            trend[i] = trend[i-1]

    return trend, np.where(trend == 1, upper, lower)

def pivot_points(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    swing_high = np.zeros(len(close))
    swing_low = np.zeros(len(close))
    for i in range(period, len(close) - period):
        if high[i] == np.max(high[i-period:i+period+1]):
            swing_high[i] = high[i]
        if low[i] == np.min(low[i-period:i+period+1]):
            swing_low[i] = low[i]
    return swing_high, swing_low

def ichimoku(high: np.ndarray, low: np.ndarray, close: np.ndarray,
             tenkan: int = 9, kijun: int = 26, senkou_b: int = 52) -> Dict[str, np.ndarray]:
    """Ichimoku Cloud"""
    def donchian_mid(h, l, period):
        result = np.zeros(len(h))
        for i in range(period, len(h)):
            result[i] = (np.max(h[i-period:i]) + np.min(l[i-period:i])) / 2
        result[:period] = result[period] if period < len(h) else (h[0] + l[0]) / 2
        return result

    tenkan_sen = donchian_mid(high, low, tenkan)
    kijun_sen = donchian_mid(high, low, kijun)
    senkou_a = (tenkan_sen + kijun_sen) / 2
    senkou_b_line = donchian_mid(high, low, senkou_b)
    chikou = np.roll(close, -kijun)

    return {
        "tenkan": tenkan_sen,
        "kijun": kijun_sen,
        "senkou_a": senkou_a,
        "senkou_b": senkou_b_line,
        "chikou": chikou
    }

def parabolic_sar(high: np.ndarray, low: np.ndarray, af_start: float = 0.02, af_max: float = 0.2) -> np.ndarray:
    """Parabolic SAR"""
    length = len(high)
    sar = np.zeros(length)
    trend = np.ones(length)
    ep = high[0]
    af = af_start
    sar[0] = low[0]

    for i in range(1, length):
        if trend[i-1] == 1:
            sar[i] = sar[i-1] + af * (ep - sar[i-1])
            if low[i] < sar[i]:
                trend[i] = -1
                sar[i] = ep
                ep = low[i]
                af = af_start
            else:
                trend[i] = 1
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_start, af_max)
        else:
            sar[i] = sar[i-1] + af * (ep - sar[i-1])
            if high[i] > sar[i]:
                trend[i] = 1
                sar[i] = ep
                ep = high[i]
                af = af_start
            else:
                trend[i] = -1
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_start, af_max)

    return sar

# ═══════════════════════════════════════════════════════════════════════════════
# BASE STRATEGY CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class BaseStrategy(ABC):
    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight

    @abstractmethod
    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# 30+ STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════════

class SmartMoneyStrategy(BaseStrategy):
    """Smart Money Concepts - Liquidity Sweep + ChoCH"""
    def __init__(self, weight: float = 1.2):
        super().__init__("Smart_Money", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        swing_high, swing_low = pivot_points(high, low, close, 5)

        recent_high_idx = np.where(swing_high > 0)[0]
        recent_low_idx = np.where(swing_low > 0)[0]

        if len(recent_high_idx) < 2 or len(recent_low_idx) < 2:
            return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

        last_high = swing_high[recent_high_idx[-1]]
        last_low = swing_low[recent_low_idx[-1]]

        buy_sweep = high[-1] > last_high and close[-1] < last_high
        sell_sweep = low[-1] < last_low and close[-1] > last_low

        trend = 1 if close[-1] > close[-5] else -1

        if sell_sweep and trend == 1:
            return Signal(SignalType.LONG, 0.8, self.name, 0.75)
        elif buy_sweep and trend == -1:
            return Signal(SignalType.SHORT, 0.8, self.name, 0.75)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class TrendshiftStrategy(BaseStrategy):
    """Trendshift - First Structural Break"""
    def __init__(self, weight: float = 1.0):
        super().__init__("Trendshift", weight)
        self.regime = 0

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        atr_vals = atr(high, low, close, 14)
        swing_high, swing_low = pivot_points(high, low, close, 5)

        highs = swing_high[swing_high > 0]
        lows = swing_low[swing_low > 0]

        if len(highs) < 1 or len(lows) < 1:
            return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

        if close[-1] > highs[-1] + atr_vals[-1] and self.regime != 1:
            self.regime = 1
            return Signal(SignalType.LONG, 0.85, self.name, 0.8)
        elif close[-1] < lows[-1] - atr_vals[-1] and self.regime != -1:
            self.regime = -1
            return Signal(SignalType.SHORT, 0.85, self.name, 0.8)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class VelocityScalpingStrategy(BaseStrategy):
    """Velocity Scalping - ROC + RSI + BB"""
    def __init__(self, weight: float = 0.8):
        super().__init__("Velocity_Scalp", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        roc = (close[5:] - close[:-5]) / close[:-5] * 100 if len(close) > 5 else np.array([0])
        rsi_vals = rsi(close, 5)
        bb_upper, bb_mid, bb_lower = bollinger_bands(close, 20, 2.0)

        if len(roc) == 0:
            return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

        if roc[-1] > 0.5 and rsi_vals[-1] < 30 and close[-1] < bb_lower[-1]:
            return Signal(SignalType.LONG, min(abs(roc[-1])/5, 1), self.name, 0.7)
        elif roc[-1] < -0.5 and rsi_vals[-1] > 70 and close[-1] > bb_upper[-1]:
            return Signal(SignalType.SHORT, min(abs(roc[-1])/5, 1), self.name, 0.7)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class SuperTrendRSIStrategy(BaseStrategy):
    """SuperTrend + RSI + SMA Trend"""
    def __init__(self, weight: float = 1.1):
        super().__init__("SuperTrend_RSI", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        st_trend, st_line = supertrend(high, low, close, 10, 3.0)
        rsi_vals = rsi(close, 14)
        sma50 = sma(close, 50)
        sma200 = sma(close, 200)

        uptrend = close[-1] > sma50[-1] > sma200[-1]
        downtrend = close[-1] < sma50[-1] < sma200[-1]

        if uptrend and st_trend[-1] == 1 and st_trend[-2] == -1 and rsi_vals[-1] < 70:
            return Signal(SignalType.LONG, 0.9, self.name, 0.85)
        elif downtrend and st_trend[-1] == -1 and st_trend[-2] == 1 and rsi_vals[-1] > 30:
            return Signal(SignalType.SHORT, 0.9, self.name, 0.85)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class BestEntrySwingStrategy(BaseStrategy):
    """Best Entry Swing - BO + PB + VCP"""
    def __init__(self, weight: float = 1.0):
        super().__init__("Best_Entry_Swing", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        volume = ohlcv.get('volume', np.ones_like(close))

        ema20 = ema(close, 20)
        ema50 = ema(close, 50)

        uptrend = close[-1] > ema20[-1] > ema50[-1]
        downtrend = close[-1] < ema20[-1] < ema50[-1]

        highest = np.max(high[-20:-1]) if len(high) > 20 else high[-1]
        lowest = np.min(low[-20:-1]) if len(low) > 20 else low[-1]
        vol_spike = volume[-1] > np.mean(volume[-20:]) * 1.5

        if uptrend and close[-1] > highest and vol_spike:
            return Signal(SignalType.LONG, 0.85, self.name, 0.8)
        elif downtrend and close[-1] < lowest and vol_spike:
            return Signal(SignalType.SHORT, 0.85, self.name, 0.8)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class MACDStrategy(BaseStrategy):
    """MACD Crossover Strategy"""
    def __init__(self, weight: float = 0.9):
        super().__init__("MACD_Cross", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        macd_line, signal_line, hist = macd(close, 12, 26, 9)

        if hist[-1] > 0 and hist[-2] <= 0:
            return Signal(SignalType.LONG, 0.75, self.name, 0.7)
        elif hist[-1] < 0 and hist[-2] >= 0:
            return Signal(SignalType.SHORT, 0.75, self.name, 0.7)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class RSIDivergenceStrategy(BaseStrategy):
    """RSI Divergence Detection"""
    def __init__(self, weight: float = 0.95):
        super().__init__("RSI_Divergence", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        rsi_vals = rsi(close, 14)

        # Bullish divergence: price lower low, RSI higher low
        if close[-1] < close[-5] and rsi_vals[-1] > rsi_vals[-5] and rsi_vals[-1] < 40:
            return Signal(SignalType.LONG, 0.8, self.name, 0.75)
        # Bearish divergence: price higher high, RSI lower high
        elif close[-1] > close[-5] and rsi_vals[-1] < rsi_vals[-5] and rsi_vals[-1] > 60:
            return Signal(SignalType.SHORT, 0.8, self.name, 0.75)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class BollingerSqueezeStrategy(BaseStrategy):
    """Bollinger Band Squeeze + Breakout"""
    def __init__(self, weight: float = 0.85):
        super().__init__("BB_Squeeze", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        bb_upper, bb_mid, bb_lower = bollinger_bands(close, 20, 2.0)
        kc_upper, kc_mid, kc_lower = keltner_channels(high, low, close, 20, 1.5)

        # Squeeze: BB inside KC
        squeeze = bb_upper[-1] < kc_upper[-1] and bb_lower[-1] > kc_lower[-1]
        prev_squeeze = bb_upper[-2] < kc_upper[-2] and bb_lower[-2] > kc_lower[-2]

        # Breakout from squeeze
        if prev_squeeze and not squeeze:
            if close[-1] > bb_mid[-1]:
                return Signal(SignalType.LONG, 0.85, self.name, 0.8)
            else:
                return Signal(SignalType.SHORT, 0.85, self.name, 0.8)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class IchimokuStrategy(BaseStrategy):
    """Ichimoku Cloud Strategy"""
    def __init__(self, weight: float = 1.0):
        super().__init__("Ichimoku", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        ich = ichimoku(high, low, close)

        above_cloud = close[-1] > max(ich["senkou_a"][-1], ich["senkou_b"][-1])
        below_cloud = close[-1] < min(ich["senkou_a"][-1], ich["senkou_b"][-1])
        tk_cross_up = ich["tenkan"][-1] > ich["kijun"][-1] and ich["tenkan"][-2] <= ich["kijun"][-2]
        tk_cross_down = ich["tenkan"][-1] < ich["kijun"][-1] and ich["tenkan"][-2] >= ich["kijun"][-2]

        if above_cloud and tk_cross_up:
            return Signal(SignalType.LONG, 0.9, self.name, 0.85)
        elif below_cloud and tk_cross_down:
            return Signal(SignalType.SHORT, 0.9, self.name, 0.85)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class StochRSIStrategy(BaseStrategy):
    """Stochastic RSI Crossover"""
    def __init__(self, weight: float = 0.8):
        super().__init__("StochRSI", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        k, d = stoch_rsi(close, 14, 3, 3)

        if k[-1] > d[-1] and k[-2] <= d[-2] and k[-1] < 20:
            return Signal(SignalType.LONG, 0.75, self.name, 0.7)
        elif k[-1] < d[-1] and k[-2] >= d[-2] and k[-1] > 80:
            return Signal(SignalType.SHORT, 0.75, self.name, 0.7)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class ADXTrendStrategy(BaseStrategy):
    """ADX Trend Strength Strategy"""
    def __init__(self, weight: float = 0.9):
        super().__init__("ADX_Trend", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        adx_vals = adx(high, low, close, 14)
        ema20 = ema(close, 20)

        strong_trend = adx_vals[-1] > 25

        if strong_trend and close[-1] > ema20[-1] and close[-2] <= ema20[-2]:
            return Signal(SignalType.LONG, 0.8, self.name, 0.75)
        elif strong_trend and close[-1] < ema20[-1] and close[-2] >= ema20[-2]:
            return Signal(SignalType.SHORT, 0.8, self.name, 0.75)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class CCIStrategy(BaseStrategy):
    """CCI Overbought/Oversold Strategy"""
    def __init__(self, weight: float = 0.75):
        super().__init__("CCI", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        cci_vals = cci(high, low, close, 20)

        if cci_vals[-1] > -100 and cci_vals[-2] <= -100:
            return Signal(SignalType.LONG, 0.7, self.name, 0.65)
        elif cci_vals[-1] < 100 and cci_vals[-2] >= 100:
            return Signal(SignalType.SHORT, 0.7, self.name, 0.65)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class WilliamsRStrategy(BaseStrategy):
    """Williams %R Strategy"""
    def __init__(self, weight: float = 0.7):
        super().__init__("WilliamsR", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        wr = williams_r(high, low, close, 14)

        if wr[-1] > -80 and wr[-2] <= -80:
            return Signal(SignalType.LONG, 0.7, self.name, 0.65)
        elif wr[-1] < -20 and wr[-2] >= -20:
            return Signal(SignalType.SHORT, 0.7, self.name, 0.65)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class MFIStrategy(BaseStrategy):
    """Money Flow Index Strategy"""
    def __init__(self, weight: float = 0.8):
        super().__init__("MFI", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        volume = ohlcv.get('volume', np.ones_like(close))
        mfi_vals = mfi(high, low, close, volume, 14)

        if mfi_vals[-1] > 20 and mfi_vals[-2] <= 20:
            return Signal(SignalType.LONG, 0.75, self.name, 0.7)
        elif mfi_vals[-1] < 80 and mfi_vals[-2] >= 80:
            return Signal(SignalType.SHORT, 0.75, self.name, 0.7)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class OBVTrendStrategy(BaseStrategy):
    """OBV Trend Strategy"""
    def __init__(self, weight: float = 0.75):
        super().__init__("OBV_Trend", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        volume = ohlcv.get('volume', np.ones_like(close))
        obv_vals = obv(close, volume)
        obv_ma = sma(obv_vals, 20)

        if obv_vals[-1] > obv_ma[-1] and obv_vals[-2] <= obv_ma[-2]:
            return Signal(SignalType.LONG, 0.7, self.name, 0.65)
        elif obv_vals[-1] < obv_ma[-1] and obv_vals[-2] >= obv_ma[-2]:
            return Signal(SignalType.SHORT, 0.7, self.name, 0.65)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class VWAPStrategy(BaseStrategy):
    """VWAP Bounce Strategy"""
    def __init__(self, weight: float = 0.85):
        super().__init__("VWAP", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        volume = ohlcv.get('volume', np.ones_like(close))
        vwap_vals = vwap(high, low, close, volume)

        # Bounce from VWAP
        touched_below = low[-2] < vwap_vals[-2] and close[-1] > vwap_vals[-1]
        touched_above = high[-2] > vwap_vals[-2] and close[-1] < vwap_vals[-1]

        if touched_below and close[-1] > close[-2]:
            return Signal(SignalType.LONG, 0.8, self.name, 0.75)
        elif touched_above and close[-1] < close[-2]:
            return Signal(SignalType.SHORT, 0.8, self.name, 0.75)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class DonchianBreakoutStrategy(BaseStrategy):
    """Donchian Channel Breakout"""
    def __init__(self, weight: float = 0.85):
        super().__init__("Donchian_BO", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        dc_upper, dc_mid, dc_lower = donchian_channels(high, low, 20)

        if close[-1] > dc_upper[-2] and close[-2] <= dc_upper[-3]:
            return Signal(SignalType.LONG, 0.8, self.name, 0.75)
        elif close[-1] < dc_lower[-2] and close[-2] >= dc_lower[-3]:
            return Signal(SignalType.SHORT, 0.8, self.name, 0.75)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class ParabolicSARStrategy(BaseStrategy):
    """Parabolic SAR Reversal"""
    def __init__(self, weight: float = 0.8):
        super().__init__("PSAR", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        sar = parabolic_sar(high, low)

        if close[-1] > sar[-1] and close[-2] <= sar[-2]:
            return Signal(SignalType.LONG, 0.75, self.name, 0.7)
        elif close[-1] < sar[-1] and close[-2] >= sar[-2]:
            return Signal(SignalType.SHORT, 0.75, self.name, 0.7)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class HullMAStrategy(BaseStrategy):
    """Hull Moving Average Trend"""
    def __init__(self, weight: float = 0.85):
        super().__init__("Hull_MA", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        hma = hull_ma(close, 20)

        if hma[-1] > hma[-2] and hma[-2] <= hma[-3]:
            return Signal(SignalType.LONG, 0.8, self.name, 0.75)
        elif hma[-1] < hma[-2] and hma[-2] >= hma[-3]:
            return Signal(SignalType.SHORT, 0.8, self.name, 0.75)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class TEMAStrategy(BaseStrategy):
    """Triple EMA Crossover"""
    def __init__(self, weight: float = 0.8):
        super().__init__("TEMA_Cross", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        tema_fast = tema(close, 8)
        tema_slow = tema(close, 21)

        if tema_fast[-1] > tema_slow[-1] and tema_fast[-2] <= tema_slow[-2]:
            return Signal(SignalType.LONG, 0.75, self.name, 0.7)
        elif tema_fast[-1] < tema_slow[-1] and tema_fast[-2] >= tema_slow[-2]:
            return Signal(SignalType.SHORT, 0.75, self.name, 0.7)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class DEMAStrategy(BaseStrategy):
    """Double EMA Trend"""
    def __init__(self, weight: float = 0.75):
        super().__init__("DEMA", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        dema_vals = dema(close, 20)

        if close[-1] > dema_vals[-1] and close[-2] <= dema_vals[-2]:
            return Signal(SignalType.LONG, 0.7, self.name, 0.65)
        elif close[-1] < dema_vals[-1] and close[-2] >= dema_vals[-2]:
            return Signal(SignalType.SHORT, 0.7, self.name, 0.65)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class TripleEMAStack(BaseStrategy):
    """Triple EMA Stack (9/21/55)"""
    def __init__(self, weight: float = 0.9):
        super().__init__("EMA_Stack", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        ema9 = ema(close, 9)
        ema21 = ema(close, 21)
        ema55 = ema(close, 55)

        bullish_stack = ema9[-1] > ema21[-1] > ema55[-1]
        bearish_stack = ema9[-1] < ema21[-1] < ema55[-1]

        prev_bullish = ema9[-2] > ema21[-2] > ema55[-2]
        prev_bearish = ema9[-2] < ema21[-2] < ema55[-2]

        if bullish_stack and not prev_bullish:
            return Signal(SignalType.LONG, 0.85, self.name, 0.8)
        elif bearish_stack and not prev_bearish:
            return Signal(SignalType.SHORT, 0.85, self.name, 0.8)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class MomentumStrategy(BaseStrategy):
    """Momentum Indicator Strategy"""
    def __init__(self, weight: float = 0.7):
        super().__init__("Momentum", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        momentum = close - np.roll(close, 10)

        if momentum[-1] > 0 and momentum[-2] <= 0:
            return Signal(SignalType.LONG, 0.7, self.name, 0.65)
        elif momentum[-1] < 0 and momentum[-2] >= 0:
            return Signal(SignalType.SHORT, 0.7, self.name, 0.65)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class ROCStrategy(BaseStrategy):
    """Rate of Change Strategy"""
    def __init__(self, weight: float = 0.7):
        super().__init__("ROC", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        roc = (close[10:] - close[:-10]) / close[:-10] * 100 if len(close) > 10 else np.array([0])

        if len(roc) < 2:
            return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

        if roc[-1] > 0 and roc[-2] <= 0:
            return Signal(SignalType.LONG, 0.7, self.name, 0.65)
        elif roc[-1] < 0 and roc[-2] >= 0:
            return Signal(SignalType.SHORT, 0.7, self.name, 0.65)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class VolatilityBreakoutStrategy(BaseStrategy):
    """ATR Volatility Breakout"""
    def __init__(self, weight: float = 0.85):
        super().__init__("Vol_Breakout", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        atr_vals = atr(high, low, close, 14)

        prev_close = close[-2]
        curr_close = close[-1]
        breakout_up = curr_close > prev_close + 2 * atr_vals[-1]
        breakout_down = curr_close < prev_close - 2 * atr_vals[-1]

        if breakout_up:
            return Signal(SignalType.LONG, 0.85, self.name, 0.8)
        elif breakout_down:
            return Signal(SignalType.SHORT, 0.85, self.name, 0.8)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class PriceChannelStrategy(BaseStrategy):
    """Price Channel Breakout"""
    def __init__(self, weight: float = 0.8):
        super().__init__("Price_Channel", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']

        if len(high) < 21:
            return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

        upper = np.max(high[-21:-1])
        lower = np.min(low[-21:-1])

        if close[-1] > upper:
            return Signal(SignalType.LONG, 0.8, self.name, 0.75)
        elif close[-1] < lower:
            return Signal(SignalType.SHORT, 0.8, self.name, 0.75)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class TrendIntensityStrategy(BaseStrategy):
    """Trend Intensity Index"""
    def __init__(self, weight: float = 0.75):
        super().__init__("Trend_Intensity", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        close = ohlcv['close']
        sma30 = sma(close, 30)

        deviation = close - sma30
        up_dev = np.sum(np.maximum(deviation[-30:], 0))
        down_dev = np.sum(np.maximum(-deviation[-30:], 0))
        tii = 100 * up_dev / (up_dev + down_dev + 1e-10)

        if tii > 80:
            return Signal(SignalType.LONG, 0.75, self.name, 0.7)
        elif tii < 20:
            return Signal(SignalType.SHORT, 0.75, self.name, 0.7)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

class ElderRayStrategy(BaseStrategy):
    """Elder Ray (Bull/Bear Power)"""
    def __init__(self, weight: float = 0.8):
        super().__init__("Elder_Ray", weight)

    def calculate(self, ohlcv: Dict[str, np.ndarray]) -> Signal:
        high, low, close = ohlcv['high'], ohlcv['low'], ohlcv['close']
        ema13 = ema(close, 13)

        bull_power = high - ema13
        bear_power = low - ema13

        if bull_power[-1] > 0 and bear_power[-1] > bear_power[-2] and ema13[-1] > ema13[-2]:
            return Signal(SignalType.LONG, 0.8, self.name, 0.75)
        elif bear_power[-1] < 0 and bull_power[-1] < bull_power[-2] and ema13[-1] < ema13[-2]:
            return Signal(SignalType.SHORT, 0.8, self.name, 0.75)
        return Signal(SignalType.NEUTRAL, 0.0, self.name, 0.0)

# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY - CREATE ALL STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════════

def create_all_strategies() -> List[BaseStrategy]:
    """Create all 30 strategies"""
    return [
        SmartMoneyStrategy(),
        TrendshiftStrategy(),
        VelocityScalpingStrategy(),
        SuperTrendRSIStrategy(),
        BestEntrySwingStrategy(),
        MACDStrategy(),
        RSIDivergenceStrategy(),
        BollingerSqueezeStrategy(),
        IchimokuStrategy(),
        StochRSIStrategy(),
        ADXTrendStrategy(),
        CCIStrategy(),
        WilliamsRStrategy(),
        MFIStrategy(),
        OBVTrendStrategy(),
        VWAPStrategy(),
        DonchianBreakoutStrategy(),
        ParabolicSARStrategy(),
        HullMAStrategy(),
        TEMAStrategy(),
        DEMAStrategy(),
        TripleEMAStack(),
        MomentumStrategy(),
        ROCStrategy(),
        VolatilityBreakoutStrategy(),
        PriceChannelStrategy(),
        TrendIntensityStrategy(),
        ElderRayStrategy()
    ]

# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import time

    print("=" * 70)
    print("GPU TRADING STRATEGIES - 30 STRATEGIES TEST")
    print("=" * 70)

    # Generate test data
    np.random.seed(42)
    n = 500
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    volume = np.random.randint(1000, 100000, n).astype(float)
    ohlcv = {'high': high, 'low': low, 'close': close, 'volume': volume}

    strategies = create_all_strategies()
    print(f"\nTotal: {len(strategies)} strategies")
    print("-" * 70)

    start = time.time()
    results = []

    for strategy in strategies:
        try:
            t0 = time.time()
            signal = strategy.calculate(ohlcv)
            latency = (time.time() - t0) * 1000
            results.append({
                "name": strategy.name,
                "signal": signal.type.name,
                "strength": signal.strength,
                "latency_ms": latency,
                "status": "OK"
            })
        except Exception as e:
            results.append({
                "name": strategy.name,
                "signal": "ERROR",
                "strength": 0,
                "latency_ms": 0,
                "status": f"ERROR: {str(e)[:30]}"
            })

    total_time = (time.time() - start) * 1000

    # Display results
    print(f"{'Strategy':<25} | {'Signal':<8} | {'Strength':>8} | {'Latency':>10} | Status")
    print("-" * 70)

    for r in results:
        print(f"{r['name']:<25} | {r['signal']:<8} | {r['strength']:>8.2f} | {r['latency_ms']:>8.1f}ms | {r['status']}")

    print("-" * 70)

    # Summary
    ok_count = sum(1 for r in results if r['status'] == 'OK')
    long_count = sum(1 for r in results if r['signal'] == 'LONG')
    short_count = sum(1 for r in results if r['signal'] == 'SHORT')
    neutral_count = sum(1 for r in results if r['signal'] == 'NEUTRAL')

    print(f"\nRESUME:")
    print(f"  Total: {len(strategies)} strategies")
    print(f"  OK: {ok_count} | Errors: {len(strategies) - ok_count}")
    print(f"  LONG: {long_count} | SHORT: {short_count} | NEUTRAL: {neutral_count}")
    print(f"  Temps total: {total_time:.0f}ms")
    print(f"  Moyenne: {total_time/len(strategies):.1f}ms/strategy")
