#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU PIPELINE - Pipeline de calcul GPU/CPU pour stratégies vectorisées
Support CuPy (GPU) avec fallback NumPy (CPU)
"""
import setup_cuda

import numpy as np
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import requests

# ============================================================================
# UTILISER SETUP_CUDA POUR LA DETECTION GPU
# ============================================================================

# Pour le trading (12 coins x 200 candles), CPU est plus rapide
# GPU overhead de transfert > gains de parallélisme pour petites données
# Forcer CPU pour ce use case
if setup_cuda.USE_GPU:
    setup_cuda.force_cpu()

xp = setup_cuda.xp
COMPUTE_MODE = "GPU" if setup_cuda.USE_GPU else "CPU"
print(f"[INFO] Mode de calcul: {COMPUTE_MODE}")


# ============================================================================
# INDICATEURS TECHNIQUES VECTORISES
# ============================================================================

class VectorizedIndicators:
    """Indicateurs techniques optimisés pour GPU/CPU"""

    def __init__(self):
        self.xp = xp  # numpy ou cupy

    def to_array(self, data):
        """Convertit en array du bon type"""
        if self.xp.__name__ == 'cupy':
            return self.xp.asarray(data, dtype=self.xp.float32)
        return np.asarray(data, dtype=np.float32)

    def to_numpy(self, arr):
        """Convertit en numpy pour output"""
        if hasattr(arr, 'get'):
            return arr.get()
        return np.asarray(arr)

    def ema(self, close, period: int):
        """EMA vectorisée"""
        close = self.to_array(close)
        alpha = 2.0 / (period + 1)

        # Utiliser convolve pour approximation rapide
        weights = self.xp.array([(1 - alpha) ** i for i in range(min(period * 3, len(close)))])
        weights = weights / weights.sum()

        ema_values = self.xp.convolve(close, weights[::-1], mode='same')
        return self.to_numpy(ema_values)

    def sma(self, data, period: int):
        """SMA vectorisée"""
        data = self.to_array(data)
        kernel = self.xp.ones(period, dtype=self.xp.float32) / period
        result = self.xp.convolve(data, kernel, mode='same')
        return self.to_numpy(result)

    def rsi(self, close, period: int = 14):
        """RSI vectorisé"""
        close = self.to_array(close)

        # Calcul des variations
        delta = self.xp.diff(close)
        gains = self.xp.where(delta > 0, delta, 0)
        losses = self.xp.where(delta < 0, -delta, 0)

        # Moyenne mobile des gains/pertes
        avg_gain = self.xp.zeros(len(close), dtype=self.xp.float32)
        avg_loss = self.xp.zeros(len(close), dtype=self.xp.float32)

        if len(gains) >= period:
            avg_gain[period] = self.xp.mean(gains[:period])
            avg_loss[period] = self.xp.mean(losses[:period])

            for i in range(period + 1, len(close)):
                avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
                avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period

        rs = avg_gain / self.xp.maximum(avg_loss, 1e-10)
        rsi = 100 - (100 / (1 + rs))

        return self.to_numpy(rsi)

    def macd(self, close, fast: int = 12, slow: int = 26, signal: int = 9):
        """MACD vectorisé"""
        ema_fast = self.ema(close, fast)
        ema_slow = self.ema(close, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self.ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def bollinger(self, close, period: int = 20, std_mult: float = 2.0):
        """Bandes de Bollinger"""
        close = self.to_array(close)

        sma = self.to_array(self.sma(close, period))

        # Calcul std rolling
        std = self.xp.zeros_like(close)
        for i in range(period, len(close)):
            std[i] = self.xp.std(close[i-period:i])

        upper = sma + std_mult * std
        lower = sma - std_mult * std

        return self.to_numpy(sma), self.to_numpy(upper), self.to_numpy(lower)

    def atr(self, high, low, close, period: int = 14):
        """ATR vectorisé"""
        high = self.to_array(high)
        low = self.to_array(low)
        close = self.to_array(close)

        # True Range
        tr = self.xp.zeros(len(close), dtype=self.xp.float32)
        tr[1:] = self.xp.maximum(
            high[1:] - low[1:],
            self.xp.maximum(
                self.xp.abs(high[1:] - close[:-1]),
                self.xp.abs(low[1:] - close[:-1])
            )
        )

        # ATR = SMA du TR
        atr_values = self.to_array(self.sma(tr, period))
        return self.to_numpy(atr_values)

    def stochastic(self, high, low, close, k_period: int = 14, d_period: int = 3):
        """Stochastic %K et %D"""
        high = self.to_array(high)
        low = self.to_array(low)
        close = self.to_array(close)

        k = self.xp.zeros(len(close), dtype=self.xp.float32)

        for i in range(k_period, len(close)):
            highest = self.xp.max(high[i-k_period:i])
            lowest = self.xp.min(low[i-k_period:i])
            if highest - lowest > 0:
                k[i] = ((close[i] - lowest) / (highest - lowest)) * 100

        k_np = self.to_numpy(k)
        d = self.sma(k_np, d_period)

        return k_np, d

    def vwap(self, high, low, close, volume):
        """VWAP"""
        high = self.to_array(high)
        low = self.to_array(low)
        close = self.to_array(close)
        volume = self.to_array(volume)

        typical_price = (high + low + close) / 3
        cum_vol = self.xp.cumsum(volume)
        cum_tp_vol = self.xp.cumsum(typical_price * volume)

        vwap = cum_tp_vol / self.xp.maximum(cum_vol, 1e-10)
        return self.to_numpy(vwap)


# ============================================================================
# STRATEGIES VECTORISEES
# ============================================================================

class VectorizedStrategies:
    """8 stratégies de trading vectorisées"""

    def __init__(self):
        self.indicators = VectorizedIndicators()

    def strategy_ema_cross_rsi(self, ohlcv: Dict) -> Dict:
        """Stratégie 1: EMA Cross + RSI + Volume"""
        close = ohlcv['close']
        volume = ohlcv['volume']

        ema_fast = self.indicators.ema(close, 8)
        ema_slow = self.indicators.ema(close, 21)
        rsi = self.indicators.rsi(close, 14)
        vol_sma = self.indicators.sma(volume, 20)

        # Signaux
        bullish = (ema_fast[-1] > ema_slow[-1]) and (rsi[-1] < 30) and (volume[-1] > vol_sma[-1] * 1.5)
        bearish = (ema_fast[-1] < ema_slow[-1]) and (rsi[-1] > 70) and (volume[-1] > vol_sma[-1] * 1.5)

        return {
            'name': 'EMA_CROSS_RSI',
            'signal': 1 if bullish else (-1 if bearish else 0),
            'confidence': abs(rsi[-1] - 50) / 50
        }

    def strategy_bollinger_breakout(self, ohlcv: Dict) -> Dict:
        """Stratégie 2: Bollinger Breakout"""
        close = ohlcv['close']

        sma, upper, lower = self.indicators.bollinger(close, 20, 2.0)
        rsi = self.indicators.rsi(close, 14)

        # Rebond sur bande inférieure = bullish
        bullish = (close[-1] < lower[-1]) and (rsi[-1] < 30)
        bearish = (close[-1] > upper[-1]) and (rsi[-1] > 70)

        return {
            'name': 'BOLLINGER_BREAKOUT',
            'signal': 1 if bullish else (-1 if bearish else 0),
            'confidence': min(1.0, abs(close[-1] - sma[-1]) / max(upper[-1] - lower[-1], 0.0001))
        }

    def strategy_macd_divergence(self, ohlcv: Dict) -> Dict:
        """Stratégie 3: MACD Cross"""
        close = ohlcv['close']

        macd_line, signal_line, histogram = self.indicators.macd(close)

        # Cross
        bullish_cross = (macd_line[-2] < signal_line[-2]) and (macd_line[-1] > signal_line[-1])
        bearish_cross = (macd_line[-2] > signal_line[-2]) and (macd_line[-1] < signal_line[-1])

        return {
            'name': 'MACD_CROSS',
            'signal': 1 if bullish_cross else (-1 if bearish_cross else 0),
            'confidence': min(1.0, abs(histogram[-1]) / max(abs(macd_line[-1]), 0.0001))
        }

    def strategy_stochastic(self, ohlcv: Dict) -> Dict:
        """Stratégie 4: Stochastic Oversold/Overbought"""
        k, d = self.indicators.stochastic(ohlcv['high'], ohlcv['low'], ohlcv['close'])

        bullish = (k[-1] < 20) and (k[-1] > k[-2])  # Oversold + rebond
        bearish = (k[-1] > 80) and (k[-1] < k[-2])  # Overbought + retournement

        return {
            'name': 'STOCHASTIC',
            'signal': 1 if bullish else (-1 if bearish else 0),
            'confidence': abs(k[-1] - 50) / 50
        }

    def strategy_vwap_bounce(self, ohlcv: Dict) -> Dict:
        """Stratégie 5: VWAP Bounce"""
        close = ohlcv['close']
        vwap = self.indicators.vwap(ohlcv['high'], ohlcv['low'], close, ohlcv['volume'])

        # Bounce depuis en dessous du VWAP
        bullish = (close[-2] < vwap[-2]) and (close[-1] > vwap[-1])
        bearish = (close[-2] > vwap[-2]) and (close[-1] < vwap[-1])

        distance_pct = abs(close[-1] - vwap[-1]) / vwap[-1] * 100

        return {
            'name': 'VWAP_BOUNCE',
            'signal': 1 if bullish else (-1 if bearish else 0),
            'confidence': min(1.0, distance_pct / 2)
        }

    def strategy_atr_breakout(self, ohlcv: Dict) -> Dict:
        """Stratégie 6: ATR Breakout"""
        high = ohlcv['high']
        low = ohlcv['low']
        close = ohlcv['close']

        atr = self.indicators.atr(high, low, close, 14)

        recent_high = np.max(high[-20:-1])
        recent_low = np.min(low[-20:-1])

        # Breakout significatif
        bullish = close[-1] > recent_high + atr[-1]
        bearish = close[-1] < recent_low - atr[-1]

        return {
            'name': 'ATR_BREAKOUT',
            'signal': 1 if bullish else (-1 if bearish else 0),
            'confidence': atr[-1] / close[-1] * 10
        }

    def strategy_momentum_roc(self, ohlcv: Dict) -> Dict:
        """Stratégie 7: Rate of Change Momentum"""
        close = ohlcv['close']

        roc = (close[-1] - close[-11]) / close[-11] * 100 if len(close) > 11 else 0
        roc_prev = (close[-2] - close[-12]) / close[-12] * 100 if len(close) > 12 else 0

        acceleration = roc - roc_prev

        bullish = (roc > 2) and (acceleration > 0)
        bearish = (roc < -2) and (acceleration < 0)

        return {
            'name': 'MOMENTUM_ROC',
            'signal': 1 if bullish else (-1 if bearish else 0),
            'confidence': min(1.0, abs(roc) / 10)
        }

    def strategy_double_ema(self, ohlcv: Dict) -> Dict:
        """Stratégie 8: Double EMA (9/21)"""
        close = ohlcv['close']

        ema9 = self.indicators.ema(close, 9)
        ema21 = self.indicators.ema(close, 21)

        prev_diff = ema9[-2] - ema21[-2]
        curr_diff = ema9[-1] - ema21[-1]

        golden_cross = (prev_diff < 0) and (curr_diff > 0)
        death_cross = (prev_diff > 0) and (curr_diff < 0)

        return {
            'name': 'DOUBLE_EMA',
            'signal': 1 if golden_cross else (-1 if death_cross else 0),
            'confidence': min(1.0, abs(curr_diff) / close[-1] * 100)
        }

    def run_all(self, ohlcv: Dict) -> List[Dict]:
        """Exécute toutes les stratégies"""
        strategies = [
            self.strategy_ema_cross_rsi,
            self.strategy_bollinger_breakout,
            self.strategy_macd_divergence,
            self.strategy_stochastic,
            self.strategy_vwap_bounce,
            self.strategy_atr_breakout,
            self.strategy_momentum_roc,
            self.strategy_double_ema,
        ]

        results = []
        for strategy in strategies:
            try:
                result = strategy(ohlcv)
                results.append(result)
            except Exception as e:
                print(f"[!] Erreur {strategy.__name__}: {e}")

        return results


# ============================================================================
# PIPELINE PRINCIPAL
# ============================================================================

class TradingPipeline:
    """Pipeline de trading GPU/CPU"""

    MEXC_BASE = "https://contract.mexc.com/api/v1"

    def __init__(self):
        self.strategies = VectorizedStrategies()
        self.session = requests.Session()

    def fetch_ohlcv(self, symbol: str, interval: str = "Min60", limit: int = 200) -> Optional[Dict]:
        """Récupère les données OHLCV"""
        try:
            url = f"{self.MEXC_BASE}/contract/kline/{symbol}"
            resp = self.session.get(url, params={'interval': interval, 'limit': limit}, timeout=10)
            data = resp.json()

            if data.get('success'):
                kline = data.get('data', {})
                closes = [float(x) for x in kline.get('close', [])]
                if len(closes) < 50:
                    return None

                return {
                    'open': np.array([float(x) for x in kline.get('open', [])], dtype=np.float32),
                    'high': np.array([float(x) for x in kline.get('high', [])], dtype=np.float32),
                    'low': np.array([float(x) for x in kline.get('low', [])], dtype=np.float32),
                    'close': np.array(closes, dtype=np.float32),
                    'volume': np.array([float(x) for x in kline.get('vol', [])], dtype=np.float32)
                }
        except Exception as e:
            pass
        return None

    def analyze_coin(self, symbol: str) -> Optional[Dict]:
        """Analyse complète d'un coin"""
        ohlcv = self.fetch_ohlcv(symbol)
        if ohlcv is None:
            return None

        # Exécuter les stratégies
        results = self.strategies.run_all(ohlcv)

        # Consensus
        buy_signals = sum(1 for r in results if r['signal'] == 1)
        sell_signals = sum(1 for r in results if r['signal'] == -1)
        total = len(results)

        buy_score = buy_signals / total if total > 0 else 0
        sell_score = sell_signals / total if total > 0 else 0

        # Signal final
        if buy_score >= 0.5:
            final_signal = "BUY"
        elif sell_score >= 0.5:
            final_signal = "SELL"
        else:
            final_signal = "HOLD"

        avg_confidence = np.mean([r['confidence'] for r in results])

        return {
            'symbol': symbol,
            'price': float(ohlcv['close'][-1]),
            'signal': final_signal,
            'buy_score': buy_score,
            'sell_score': sell_score,
            'confidence': avg_confidence,
            'buy_count': buy_signals,
            'sell_count': sell_signals,
            'hold_count': total - buy_signals - sell_signals,
            'strategies': results
        }

    def scan_coins(self, symbols: List[str], max_workers: int = 10) -> List[Dict]:
        """Scanne plusieurs coins en parallèle"""
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            from concurrent.futures import as_completed
            futures = {executor.submit(self.analyze_coin, s): s for s in symbols}

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except:
                    pass

        results.sort(key=lambda x: x['buy_score'], reverse=True)
        return results


# ============================================================================
# BENCHMARK CPU vs GPU
# ============================================================================

def benchmark_compute():
    """Benchmark CPU vs GPU"""
    print("\n" + "="*60)
    print(" BENCHMARK COMPUTE")
    print("="*60)

    # Test data
    n = 10000
    data = np.random.random(n).astype(np.float32)

    # CPU Test
    start = time.perf_counter()
    for _ in range(100):
        _ = np.convolve(data, np.ones(20)/20, mode='same')
        _ = np.diff(data)
        _ = np.cumsum(data)
    cpu_time = time.perf_counter() - start
    print(f" CPU (NumPy):  {cpu_time*1000:.2f} ms pour 100 itérations")

    # GPU Test si disponible
    if COMPUTE_MODE == "GPU":
        import cupy as cp
        data_gpu = cp.asarray(data)

        # Warmup
        _ = cp.convolve(data_gpu, cp.ones(20)/20, mode='same')
        cp.cuda.Stream.null.synchronize()

        start = time.perf_counter()
        for _ in range(100):
            _ = cp.convolve(data_gpu, cp.ones(20)/20, mode='same')
            _ = cp.diff(data_gpu)
            _ = cp.cumsum(data_gpu)
        cp.cuda.Stream.null.synchronize()
        gpu_time = time.perf_counter() - start

        print(f" GPU (CuPy):   {gpu_time*1000:.2f} ms pour 100 itérations")
        print(f" Speedup:      {cpu_time/gpu_time:.1f}x")

    print("="*60)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "#"*70)
    print(" GPU/CPU PIPELINE - STRATEGIES VECTORISEES")
    print("#"*70)
    print(f" Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Mode: {COMPUTE_MODE}")

    # Benchmark
    benchmark_compute()

    # Test pipeline
    pipeline = TradingPipeline()

    symbols = [
        "BTC_USDT", "ETH_USDT", "SOL_USDT", "XRP_USDT",
        "HBAR_USDT", "SUI_USDT", "AVAX_USDT", "LINK_USDT",
        "OP_USDT", "ARB_USDT", "NEAR_USDT", "APT_USDT"
    ]

    print(f"\n[SCAN] Analyse de {len(symbols)} coins avec 8 stratégies...")

    start = time.perf_counter()
    results = pipeline.scan_coins(symbols)
    elapsed = time.perf_counter() - start

    print(f"[PERF] Temps total: {elapsed:.2f}s ({len(results)} coins)")
    print(f"[PERF] Moyenne: {elapsed/len(results)*1000:.0f}ms par coin")

    print("\n" + "="*70)
    print(" RESULTATS")
    print("="*70)

    for r in results[:5]:
        signal_icon = "🟢" if r['signal'] == "BUY" else ("🔴" if r['signal'] == "SELL" else "⚪")
        print(f"\n {signal_icon} {r['symbol']:<12} {r['signal']}")
        print(f"    Prix: {r['price']:.6f}")
        print(f"    Scores: BUY {r['buy_score']:.0%} | SELL {r['sell_score']:.0%}")
        print(f"    Stratégies: {r['buy_count']}B / {r['sell_count']}S / {r['hold_count']}H")

    print("\n" + "="*70)
    print("[OK] Pipeline terminé!")
