"""
Strategies — 100 strategies logiques vectorisees PyTorch multi-GPU
Trading AI System v2.3 | Adapte cluster JARVIS

INTERDIT: boucles Python sur bougies, rolling() Python
TOUT en batch PyTorch GPU (5 GPU paralleles)
Fallback NumPy si CUDA non dispo
"""

import numpy as np
from enum import Enum
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

# GPU: PyTorch CUDA multi-GPU si dispo, sinon NumPy
try:
    import torch
    if torch.cuda.is_available():
        GPU_AVAILABLE = True
        GPU_COUNT = torch.cuda.device_count()
        GPU_DEVICES = [torch.device(f"cuda:{i}") for i in range(GPU_COUNT)]
        # Identifier le GPU le plus rapide (plus de VRAM = RTX 3080)
        _vrams = []
        for i in range(GPU_COUNT):
            _, total = torch.cuda.mem_get_info(i)
            _vrams.append(total)
        PRIMARY_GPU = GPU_DEVICES[_vrams.index(max(_vrams))]
    else:
        GPU_AVAILABLE = False
        GPU_COUNT = 0
        GPU_DEVICES = []
        PRIMARY_GPU = None
except ImportError:
    torch = None
    GPU_AVAILABLE = False
    GPU_COUNT = 0
    GPU_DEVICES = []
    PRIMARY_GPU = None


class SignalType(Enum):
    LONG = 1
    SHORT = -1
    HOLD = 0


class MarketRegime(Enum):
    TREND = "trend"
    RANGE = "range"
    TRANSITION = "transition"


# --- Indicateurs vectorises (batch sur tenseur) ---
# Toutes les fonctions acceptent torch.Tensor (GPU) ou np.ndarray (CPU)

def _xp(arr):
    """Retourne le module (torch ou numpy) selon le type."""
    if torch is not None and isinstance(arr, torch.Tensor):
        return torch
    return np


def _zeros_like(arr):
    xp = _xp(arr)
    return xp.zeros_like(arr) if xp == torch else np.zeros_like(arr)


def _where(cond, a, b):
    xp = _xp(cond)
    return xp.where(cond, a, b) if xp == torch else np.where(cond, a, b)


def ema_batch(close, period: int):
    """EMA vectorisee sur axe temps (axe=1). Shape: [coins, time]"""
    alpha = 2.0 / (period + 1)
    result = _zeros_like(close)
    result[:, 0] = close[:, 0]
    for t in range(1, close.shape[1]):
        result[:, t] = alpha * close[:, t] + (1 - alpha) * result[:, t - 1]
    return result


def rsi_batch(close, period: int = 14):
    """RSI vectorise sur axe temps. Shape: [coins, time]"""
    xp = _xp(close)
    if xp == torch:
        delta = close[:, 1:] - close[:, :-1]
    else:
        delta = np.diff(close, axis=1)
    gain = _where(delta > 0, delta, 0.0 if xp == np else torch.tensor(0.0, device=close.device))
    loss = _where(delta < 0, -delta, 0.0 if xp == np else torch.tensor(0.0, device=close.device))

    avg_gain = _zeros_like(close)
    avg_loss = _zeros_like(close)

    if close.shape[1] <= period:
        if xp == torch:
            return torch.full_like(close, 50.0)
        return np.full_like(close, 50.0)

    if xp == torch:
        avg_gain[:, period] = torch.mean(gain[:, :period], dim=1)
        avg_loss[:, period] = torch.mean(loss[:, :period], dim=1)
    else:
        avg_gain[:, period] = np.mean(gain[:, :period], axis=1)
        avg_loss[:, period] = np.mean(loss[:, :period], axis=1)

    alpha_r = 1.0 / period
    for t in range(period + 1, close.shape[1]):
        avg_gain[:, t] = (1 - alpha_r) * avg_gain[:, t - 1] + alpha_r * gain[:, t - 1]
        avg_loss[:, t] = (1 - alpha_r) * avg_loss[:, t - 1] + alpha_r * loss[:, t - 1]

    rs = avg_gain / (avg_loss + 1e-8)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def atr_batch(high, low, close, period: int = 14):
    """ATR vectorise. Shape: [coins, time]"""
    xp = _xp(close)
    tr1 = high[:, 1:] - low[:, 1:]
    if xp == torch:
        tr2 = torch.abs(high[:, 1:] - close[:, :-1])
        tr3 = torch.abs(low[:, 1:] - close[:, :-1])
        tr = torch.maximum(torch.maximum(tr1, tr2), tr3)
    else:
        tr2 = np.abs(high[:, 1:] - close[:, :-1])
        tr3 = np.abs(low[:, 1:] - close[:, :-1])
        tr = np.maximum(np.maximum(tr1, tr2), tr3)

    atr = _zeros_like(close)
    if close.shape[1] <= period:
        return atr

    if xp == torch:
        atr[:, period] = torch.mean(tr[:, :period], dim=1)
    else:
        atr[:, period] = np.mean(tr[:, :period], axis=1)
    alpha_a = 1.0 / period
    for t in range(period + 1, close.shape[1]):
        atr[:, t] = (1 - alpha_a) * atr[:, t - 1] + alpha_a * tr[:, t - 1]
    return atr


def bollinger_batch(close, period: int = 20, std_mult: float = 2.0):
    """Bollinger Bands. Retourne (upper, middle, lower)."""
    xp = _xp(close)

    if xp == torch:
        # Conv1d pour SMA
        kernel = torch.ones(1, 1, period, device=close.device, dtype=close.dtype) / period
        padded = torch.nn.functional.pad(close.unsqueeze(1), (period // 2, period - period // 2 - 1), mode='replicate')
        middle = torch.nn.functional.conv1d(padded, kernel).squeeze(1)
    else:
        kernel = np.ones(period, dtype=np.float32) / period
        middle = np.zeros_like(close)
        for i in range(close.shape[0]):
            middle[i] = np.convolve(close[i], kernel, mode="same")

    std = _zeros_like(close)
    for t in range(period, close.shape[1]):
        window = close[:, t - period:t]
        if xp == torch:
            std[:, t] = torch.std(window, dim=1)
        else:
            std[:, t] = np.std(window, axis=1)

    upper = middle + std_mult * std
    lower = middle - std_mult * std
    return upper, middle, lower


def vwap_batch(close, volume):
    """VWAP cumulatif. Shape: [coins, time]"""
    xp = _xp(close)
    if xp == torch:
        cum_vol = torch.cumsum(volume, dim=1)
        cum_pv = torch.cumsum(close * volume, dim=1)
    else:
        cum_vol = np.cumsum(volume, axis=1)
        cum_pv = np.cumsum(close * volume, axis=1)
    return cum_pv / (cum_vol + 1e-8)


def volume_sma_batch(volume, period: int = 20):
    """SMA du volume via convolution."""
    xp = _xp(volume)
    if xp == torch:
        kernel = torch.ones(1, 1, period, device=volume.device, dtype=volume.dtype) / period
        padded = torch.nn.functional.pad(volume.unsqueeze(1), (period // 2, period - period // 2 - 1), mode='replicate')
        return torch.nn.functional.conv1d(padded, kernel).squeeze(1)
    else:
        kernel = np.ones(period, dtype=np.float32) / period
        result = np.zeros_like(volume)
        for i in range(volume.shape[0]):
            result[i] = np.convolve(volume[i], kernel, mode="same")
        return result


def macd_batch(close):
    """MACD (12, 26, 9). Retourne (macd_line, signal_line, histogram)."""
    ema12 = ema_batch(close, 12)
    ema26 = ema_batch(close, 26)
    macd_line = ema12 - ema26
    signal = ema_batch(macd_line, 9)
    histogram = macd_line - signal
    return macd_line, signal, histogram


def stoch_rsi_batch(close, period: int = 14):
    """Stochastic RSI."""
    xp = _xp(close)
    rsi = rsi_batch(close, period)
    result = _zeros_like(rsi)
    for t in range(period, rsi.shape[1]):
        window = rsi[:, t - period:t]
        if xp == torch:
            rsi_min = torch.min(window, dim=1).values
            rsi_max = torch.max(window, dim=1).values
        else:
            rsi_min = np.min(window, axis=1)
            rsi_max = np.max(window, axis=1)
        result[:, t] = (rsi[:, t] - rsi_min) / (rsi_max - rsi_min + 1e-8)
    return result


# --- 100 Strategies logiques ---

def compute_all_indicators(tensor) -> dict:
    """
    Calcule TOUS les indicateurs sur le tenseur 3D.
    tensor shape: [coins, time, 5] = [OHLCV]
    """
    o = tensor[:, :, 0]
    h = tensor[:, :, 1]
    l = tensor[:, :, 2]
    c = tensor[:, :, 3]
    v = tensor[:, :, 4]

    ind = {
        "open": o, "high": h, "low": l, "close": c, "volume": v,
        "ema_8": ema_batch(c, 8),
        "ema_21": ema_batch(c, 21),
        "ema_55": ema_batch(c, 55),
        "rsi_14": rsi_batch(c, 14),
        "atr_14": atr_batch(h, l, c, 14),
        "vwap": vwap_batch(c, v),
        "vol_sma_20": volume_sma_batch(v, 20),
        "vol_sma_10": volume_sma_batch(v, 10),
    }

    bb_upper, bb_mid, bb_lower = bollinger_batch(c, 20)
    ind["bb_upper"] = bb_upper
    ind["bb_mid"] = bb_mid
    ind["bb_lower"] = bb_lower

    macd_line, macd_signal, macd_hist = macd_batch(c)
    ind["macd_line"] = macd_line
    ind["macd_signal"] = macd_signal
    ind["macd_hist"] = macd_hist

    ind["stoch_rsi"] = stoch_rsi_batch(c, 14)

    return ind


def _last(arr, offset=0):
    """Valeur a la derniere position (ou -1-offset)."""
    idx = -1 - offset
    return arr[:, idx]


def _max_axis1(arr, slc):
    """Max sur axe 1 compatible torch/numpy."""
    xp = _xp(arr)
    if xp == torch:
        return torch.max(slc, dim=1).values
    return np.max(slc, axis=1)


def _min_axis1(arr, slc):
    """Min sur axe 1 compatible torch/numpy."""
    xp = _xp(arr)
    if xp == torch:
        return torch.min(slc, dim=1).values
    return np.min(slc, axis=1)


def _mean_axis1(arr, slc):
    """Mean sur axe 1 compatible torch/numpy."""
    xp = _xp(arr)
    if xp == torch:
        return torch.mean(slc, dim=1)
    return np.mean(slc, axis=1)


def _abs(arr):
    xp = _xp(arr)
    return torch.abs(arr) if xp == torch else np.abs(arr)


def evaluate_strategies(ind: dict, ob_imbalances=None) -> tuple:
    """
    Evalue 100 strategies sur les indicateurs.
    Retourne (scores [coins, 100], names [100])
    """
    c = ind["close"]
    h = ind["high"]
    l = ind["low"]
    v = ind["volume"]
    xp = _xp(c)
    n_coins = c.shape[0]

    close = _last(c)
    high_last = _last(h)
    low_last = _last(l)
    vol_last = _last(v)
    ema8 = _last(ind["ema_8"])
    ema21 = _last(ind["ema_21"])
    ema55 = _last(ind["ema_55"])
    rsi = _last(ind["rsi_14"])
    atr = _last(ind["atr_14"])
    vwap = _last(ind["vwap"])
    vol_sma20 = _last(ind["vol_sma_20"])
    vol_sma10 = _last(ind["vol_sma_10"])
    bb_upper = _last(ind["bb_upper"])
    bb_lower = _last(ind["bb_lower"])
    bb_mid = _last(ind["bb_mid"])
    macd_line = _last(ind["macd_line"])
    macd_signal = _last(ind["macd_signal"])
    macd_hist = _last(ind["macd_hist"])
    stoch = _last(ind["stoch_rsi"])

    res_20 = _max_axis1(h, h[:, -20:])
    sup_20 = _min_axis1(l, l[:, -20:])

    if ob_imbalances is None:
        if xp == torch:
            ob_imb = torch.zeros(n_coins, device=c.device, dtype=c.dtype)
        else:
            ob_imb = np.zeros(n_coins, dtype=np.float32)
    else:
        if xp == torch:
            ob_imb = torch.as_tensor(ob_imbalances, device=c.device, dtype=c.dtype)
        else:
            ob_imb = np.asarray(ob_imbalances, dtype=np.float32)

    if xp == torch:
        scores = torch.zeros((n_coins, 100), device=c.device, dtype=c.dtype)
    else:
        scores = np.zeros((n_coins, 100), dtype=np.float32)
    names = []

    def s(idx, name, long_cond, short_cond):
        names.append(name)
        if xp == torch:
            scores[:, idx] = torch.where(long_cond, torch.tensor(1.0, device=c.device),
                                          torch.where(short_cond, torch.tensor(-1.0, device=c.device),
                                                      torch.tensor(0.0, device=c.device)))
        else:
            scores[:, idx] = np.where(long_cond, 1.0, np.where(short_cond, -1.0, 0.0))

    # === BREAKOUT (0-19) ===
    s(0, "breakout_ema21_res20",
      (close > ema21) & (close > res_20) & (vol_last > vol_sma20 * 1.5) & (rsi > 50) & (rsi < 70),
      (close < ema21) & (close < sup_20) & (vol_last > vol_sma20 * 1.5) & (rsi < 50) & (rsi > 30))

    s(1, "breakout_bb_upper",
      (close > bb_upper) & (vol_last > vol_sma20 * 1.5),
      (close < bb_lower) & (vol_last > vol_sma20 * 1.5))

    s(2, "breakout_ema55",
      (close > ema55) & (ema8 > ema21) & (ema21 > ema55),
      (close < ema55) & (ema8 < ema21) & (ema21 < ema55))

    s(3, "breakout_volume_spike",
      (vol_last > vol_sma20 * 3.0) & (close > _last(ind["open"])),
      (vol_last > vol_sma20 * 3.0) & (close < _last(ind["open"])))

    s(4, "breakout_atr_expansion",
      (atr > _last(ind["atr_14"], 1) * 1.5) & (close > ema21),
      (atr > _last(ind["atr_14"], 1) * 1.5) & (close < ema21))

    s(5, "breakout_range_squeeze",
      (atr < _mean_axis1(c, ind["atr_14"][:, -20:]) * 0.6) & (close > ema21),
      (atr < _mean_axis1(c, ind["atr_14"][:, -20:]) * 0.6) & (close < ema21))

    s(6, "breakout_high_5",
      (close > _max_axis1(h, h[:, -5:])) & (rsi < 75),
      (close < _min_axis1(l, l[:, -5:])) & (rsi > 25))

    s(7, "breakout_high_10",
      (close > _max_axis1(h, h[:, -10:])) & (vol_last > vol_sma10),
      (close < _min_axis1(l, l[:, -10:])) & (vol_last > vol_sma10))

    s(8, "breakout_vwap_cross_up",
      (close > vwap) & (_last(c, 1) < _last(ind["vwap"], 1)),
      (close < vwap) & (_last(c, 1) > _last(ind["vwap"], 1)))

    s(9, "breakout_macd_cross",
      (macd_line > macd_signal) & (_last(ind["macd_line"], 1) < _last(ind["macd_signal"], 1)),
      (macd_line < macd_signal) & (_last(ind["macd_line"], 1) > _last(ind["macd_signal"], 1)))

    for i in range(10, 20):
        period = 20 + (i - 10) * 5
        actual_p = min(period, c.shape[1])
        s(i, f"breakout_high_{actual_p}",
          (close > _max_axis1(h, h[:, -actual_p:])),
          (close < _min_axis1(l, l[:, -actual_p:])))

    # === REVERSAL (20-39) ===
    s(20, "reversal_rsi_ob",
      (rsi < 30) & (close < bb_lower) & (vol_last > vol_sma10 * 2) & (ob_imb > 0.6),
      (rsi > 70) & (close > bb_upper) & (vol_last > vol_sma10 * 2) & (ob_imb < -0.6))

    s(21, "reversal_stoch_rsi",
      (stoch < 0.2) & (rsi < 35),
      (stoch > 0.8) & (rsi > 65))

    s(22, "reversal_bb_bounce",
      (close < bb_lower) & (close > _last(c, 1)),
      (close > bb_upper) & (close < _last(c, 1)))

    s(23, "reversal_hammer",
      ((close - low_last) > 2 * (high_last - close)) & (close > _last(c, 1)),
      ((high_last - close) > 2 * (close - low_last)) & (close < _last(c, 1)))

    s(24, "reversal_double_bottom",
      (_abs(_min_axis1(l, l[:, -10:-5]) - _min_axis1(l, l[:, -5:])) < atr * 0.5) & (rsi < 40),
      (_abs(_max_axis1(h, h[:, -10:-5]) - _max_axis1(h, h[:, -5:])) < atr * 0.5) & (rsi > 60))

    s(25, "reversal_divergence_rsi",
      (close < _last(c, 5)) & (rsi > _last(ind["rsi_14"], 5)),
      (close > _last(c, 5)) & (rsi < _last(ind["rsi_14"], 5)))

    s(26, "reversal_ema_retest",
      (_abs(close - ema21) < atr * 0.3) & (close > ema55),
      (_abs(close - ema21) < atr * 0.3) & (close < ema55))

    s(27, "reversal_volume_dry",
      (vol_last < vol_sma20 * 0.3) & (rsi < 40),
      (vol_last < vol_sma20 * 0.3) & (rsi > 60))

    s(28, "reversal_macd_divergence",
      (macd_hist > 0) & (_last(ind["macd_hist"], 1) < 0) & (rsi < 45),
      (macd_hist < 0) & (_last(ind["macd_hist"], 1) > 0) & (rsi > 55))

    s(29, "reversal_extreme_rsi",
      (rsi < 20),
      (rsi > 80))

    for i in range(30, 40):
        threshold = 25 + (i - 30)
        s(i, f"reversal_rsi_{threshold}",
          (rsi < threshold) & (close < bb_lower),
          (rsi > (100 - threshold)) & (close > bb_upper))

    # === MOMENTUM (40-59) ===
    s(40, "momentum_ema_stack",
      (ema8 > ema21) & (ema21 > ema55) & (rsi > 50),
      (ema8 < ema21) & (ema21 < ema55) & (rsi < 50))

    s(41, "momentum_rsi_trend",
      (rsi > 55) & (rsi < 70) & (close > ema21),
      (rsi < 45) & (rsi > 30) & (close < ema21))

    s(42, "momentum_macd_positive",
      (macd_hist > 0) & (macd_line > 0),
      (macd_hist < 0) & (macd_line < 0))

    s(43, "momentum_volume_trend",
      (vol_last > vol_sma20) & (close > ema8),
      (vol_last > vol_sma20) & (close < ema8))

    s(44, "momentum_price_accel",
      ((close - _last(c, 3)) > ((_last(c, 3) - _last(c, 6)) * 1.5)),
      ((close - _last(c, 3)) < ((_last(c, 3) - _last(c, 6)) * 1.5)))

    s(45, "momentum_vwap_trend",
      (close > vwap) & (ema8 > ema21),
      (close < vwap) & (ema8 < ema21))

    s(46, "momentum_bb_width",
      ((bb_upper - bb_lower) / (bb_mid + 1e-8) > 0.04) & (close > bb_mid),
      ((bb_upper - bb_lower) / (bb_mid + 1e-8) > 0.04) & (close < bb_mid))

    s(47, "momentum_close_vs_range",
      ((close - low_last) / (high_last - low_last + 1e-8) > 0.7),
      ((close - low_last) / (high_last - low_last + 1e-8) < 0.3))

    s(48, "momentum_3_green",
      (c[:, -1] > c[:, -2]) & (c[:, -2] > c[:, -3]) & (c[:, -3] > c[:, -4]),
      (c[:, -1] < c[:, -2]) & (c[:, -2] < c[:, -3]) & (c[:, -3] < c[:, -4]))

    s(49, "momentum_atr_ratio",
      (atr / (close + 1e-8) > 0.02) & (close > ema21),
      (atr / (close + 1e-8) > 0.02) & (close < ema21))

    for i in range(50, 60):
        ema_p = 10 + (i - 50) * 5
        ema_v = ema_batch(c, ema_p)
        s(i, f"momentum_ema{ema_p}_cross",
          (close > _last(ema_v)) & (_last(c, 1) < _last(ema_v, 1)),
          (close < _last(ema_v)) & (_last(c, 1) > _last(ema_v, 1)))

    # === MEAN REVERSION (60-79) ===
    s(60, "mean_rev_bb_lower",
      (close < bb_lower) & (rsi < 35),
      (close > bb_upper) & (rsi > 65))

    s(61, "mean_rev_vwap_dist",
      ((vwap - close) / (vwap + 1e-8) > 0.02) & (rsi < 40),
      ((close - vwap) / (vwap + 1e-8) > 0.02) & (rsi > 60))

    s(62, "mean_rev_ema21_dist",
      ((ema21 - close) / (ema21 + 1e-8) > 0.03),
      ((close - ema21) / (ema21 + 1e-8) > 0.03))

    s(63, "mean_rev_zscore",
      ((close - bb_mid) / ((bb_upper - bb_lower) / 2 + 1e-8) < -2),
      ((close - bb_mid) / ((bb_upper - bb_lower) / 2 + 1e-8) > 2))

    s(64, "mean_rev_vol_exhaustion",
      (vol_last < vol_sma20 * 0.4) & (_abs(close - bb_mid) > atr),
      (vol_last < vol_sma20 * 0.4) & (_abs(close - bb_mid) > atr))

    s(65, "mean_rev_rsi_ema_divergence",
      (rsi < 35) & (close > ema55),
      (rsi > 65) & (close < ema55))

    s(66, "mean_rev_atr_contraction",
      (atr < _last(ind["atr_14"], 5) * 0.6) & (close < bb_mid),
      (atr < _last(ind["atr_14"], 5) * 0.6) & (close > bb_mid))

    s(67, "mean_rev_close_vs_ema8",
      ((ema8 - close) / (ema8 + 1e-8) > 0.01),
      ((close - ema8) / (ema8 + 1e-8) > 0.01))

    for i in range(68, 80):
        pct = 0.01 + (i - 68) * 0.005
        s(i, f"mean_rev_dist_{int(pct*100)}pct",
          ((ema21 - close) / (ema21 + 1e-8) > pct),
          ((close - ema21) / (ema21 + 1e-8) > pct))

    # === ORDER BOOK / HYBRID (80-99) ===
    s(80, "ob_strong_bid",
      (ob_imb > 0.5) & (rsi < 60),
      (ob_imb < -0.5) & (rsi > 40))

    s(81, "ob_extreme_imbalance",
      (ob_imb > 0.7),
      (ob_imb < -0.7))

    s(82, "ob_bid_momentum",
      (ob_imb > 0.3) & (close > ema8),
      (ob_imb < -0.3) & (close < ema8))

    s(83, "hybrid_ob_breakout",
      (ob_imb > 0.4) & (close > res_20) & (vol_last > vol_sma20),
      (ob_imb < -0.4) & (close < sup_20) & (vol_last > vol_sma20))

    s(84, "hybrid_ob_reversal",
      (ob_imb > 0.5) & (rsi < 30),
      (ob_imb < -0.5) & (rsi > 70))

    s(85, "hybrid_full_confluence",
      (close > ema21) & (rsi > 50) & (rsi < 70) & (vol_last > vol_sma20) & (ob_imb > 0.3) & (macd_hist > 0),
      (close < ema21) & (rsi < 50) & (rsi > 30) & (vol_last > vol_sma20) & (ob_imb < -0.3) & (macd_hist < 0))

    s(86, "hybrid_vwap_ob",
      (close > vwap) & (ob_imb > 0.3),
      (close < vwap) & (ob_imb < -0.3))

    s(87, "hybrid_squeeze_ob",
      (atr < _mean_axis1(c, ind["atr_14"][:, -20:]) * 0.5) & (ob_imb > 0.4),
      (atr < _mean_axis1(c, ind["atr_14"][:, -20:]) * 0.5) & (ob_imb < -0.4))

    for i in range(88, 100):
        imb_thresh = 0.3 + (i - 88) * 0.05
        s(i, f"ob_imbalance_{int(imb_thresh*100)}",
          (ob_imb > imb_thresh) & (close > ema21),
          (ob_imb < -imb_thresh) & (close < ema21))

    return scores, names


def apply_weights(scores, epsilon: float = 0.05):
    """Ponderation adaptive par percentiles avec garde-fou epsilon."""
    xp = _xp(scores)

    if xp == torch:
        mean_scores = torch.mean(scores, dim=1)
        max_abs = torch.max(torch.abs(mean_scores)).item()
    else:
        mean_scores = np.mean(scores, axis=1)
        max_abs = float(np.max(np.abs(mean_scores)))

    if max_abs < epsilon:
        return _zeros_like(scores)

    # Percentiles
    if xp == torch:
        mean_np = mean_scores.cpu().numpy()
    else:
        mean_np = mean_scores
    p10 = float(np.percentile(mean_np, 10))
    p30 = float(np.percentile(mean_np, 30))
    p70 = float(np.percentile(mean_np, 70))

    if xp == torch:
        weights = torch.ones(scores.shape[0], device=scores.device, dtype=scores.dtype)
        weights = torch.where(mean_scores < p10, torch.tensor(0.0, device=scores.device), weights)
        weights = torch.where((mean_scores >= p10) & (mean_scores < p30), torch.tensor(0.5, device=scores.device), weights)
        weights = torch.where(mean_scores > p70, torch.tensor(1.5, device=scores.device), weights)
        return scores * weights.unsqueeze(1)
    else:
        weights = np.ones(scores.shape[0], dtype=np.float32)
        weights = np.where(mean_scores < p10, 0.0, weights)
        weights = np.where((mean_scores >= p10) & (mean_scores < p30), 0.5, weights)
        weights = np.where(mean_scores > p70, 1.5, weights)
        return scores * weights[:, None]


def _compute_chunk_on_gpu(tensor_chunk, ob_chunk, device):
    """Compute indicators + strategies pour un chunk de coins sur un GPU specifique."""
    t = torch.tensor(tensor_chunk, dtype=torch.float32, device=device)

    ind = compute_all_indicators(t)

    if ob_chunk is not None:
        ob_t = torch.tensor(ob_chunk, dtype=torch.float32, device=device)
    else:
        ob_t = None

    raw_scores, strategy_names = evaluate_strategies(ind, ob_t)
    weighted = apply_weights(raw_scores, epsilon=0.05)

    mean_scores = torch.mean(weighted, dim=1)
    directions = torch.sign(mean_scores)
    abs_scores = torch.abs(mean_scores)
    max_abs = torch.max(abs_scores).item()
    confidences = abs_scores / max_abs if max_abs > 0 else torch.zeros_like(abs_scores)

    atr_vals = _last(ind["atr_14"])

    # Transfert GPU → CPU
    return {
        "weighted_scores": weighted.cpu().numpy(),
        "mean_scores": mean_scores.cpu().numpy(),
        "directions": directions.cpu().numpy(),
        "confidences": confidences.cpu().numpy(),
        "atr": atr_vals.cpu().numpy(),
        "strategy_names": strategy_names,
    }


def compute_final_scores(tensor, ob_imbalances=None) -> dict:
    """
    Pipeline complet MULTI-GPU: split coins across GPUs, compute in parallel, merge.
    tensor shape: [coins, time, 5] (OHLCV float32, numpy)
    """
    n_coins = tensor.shape[0]

    if GPU_AVAILABLE and GPU_COUNT > 0:
        # Multi-GPU: split coins across available GPUs
        chunk_size = max(1, n_coins // GPU_COUNT)
        chunks = []
        for i in range(GPU_COUNT):
            start = i * chunk_size
            end = start + chunk_size if i < GPU_COUNT - 1 else n_coins
            if start >= n_coins:
                break
            t_chunk = tensor[start:end]
            ob_chunk = ob_imbalances[start:end] if ob_imbalances is not None else None
            chunks.append((t_chunk, ob_chunk, GPU_DEVICES[i]))

        # Parallel GPU execution
        results = []
        with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
            futures = [executor.submit(_compute_chunk_on_gpu, tc, oc, dev)
                       for tc, oc, dev in chunks]
            for f in futures:
                results.append(f.result())

        # Merge results
        all_weighted = np.concatenate([r["weighted_scores"] for r in results], axis=0)
        all_mean = np.concatenate([r["mean_scores"] for r in results], axis=0)
        all_dirs = np.concatenate([r["directions"] for r in results], axis=0)
        all_conf = np.concatenate([r["confidences"] for r in results], axis=0)
        all_atr = np.concatenate([r["atr"] for r in results], axis=0)
        strategy_names = results[0]["strategy_names"]

        # Re-normalize confidences globally
        max_abs = np.max(np.abs(all_mean))
        if max_abs > 0:
            all_conf = np.abs(all_mean) / max_abs

        # Clean GPU memory
        for i in range(GPU_COUNT):
            torch.cuda.empty_cache()

    else:
        # CPU NumPy fallback
        ind = compute_all_indicators(tensor)
        raw_scores, strategy_names = evaluate_strategies(ind, ob_imbalances)
        all_weighted = apply_weights(raw_scores, epsilon=0.05)
        all_mean = np.mean(all_weighted, axis=1)
        all_dirs = np.sign(all_mean)
        abs_scores = np.abs(all_mean)
        max_abs = np.max(abs_scores)
        all_conf = abs_scores / max_abs if max_abs > 0 else np.zeros_like(abs_scores)
        all_atr = _last(ind["atr_14"])

    # Strategies declenchees par coin
    triggered = {}
    for i in range(all_weighted.shape[0]):
        active = []
        for j in range(min(all_weighted.shape[1], len(strategy_names))):
            if abs(all_weighted[i, j]) > 0:
                active.append(strategy_names[j])
        if active:
            triggered[i] = active

    # Market regime
    regimes = []
    for i in range(n_coins):
        conf = float(all_conf[i])
        if conf > 0.8:
            regimes.append(MarketRegime.TREND)
        elif conf > 0.5:
            regimes.append(MarketRegime.RANGE)
        else:
            regimes.append(MarketRegime.TRANSITION)

    return {
        "weighted_scores": all_weighted,
        "mean_scores": all_mean,
        "directions": all_dirs,
        "confidences": all_conf,
        "triggered_strategies": triggered,
        "market_regimes": regimes,
        "strategy_names": strategy_names,
        "atr": all_atr,
    }
