"""
Indicators module: MACD, RSI, ATR with SMA/EMA/WMA support.
All calculations are vectorized using pandas for performance.
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Moving Averages
# ---------------------------------------------------------------------------

def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def wma(series: pd.Series, period: int) -> pd.Series:
    weights = np.arange(1, period + 1, dtype=float)
    def _wma(x):
        if len(x) < period:
            return np.nan
        return np.dot(x[-period:], weights) / weights.sum()
    return series.rolling(window=period).apply(_wma, raw=True)


def apply_ma(series: pd.Series, period: int, ma_type: str) -> pd.Series:
    ma_type = ma_type.upper()
    if ma_type == "EMA":
        return ema(series, period)
    elif ma_type == "WMA":
        return wma(series, period)
    else:  # SMA default
        return sma(series, period)


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def calculate_macd(
    close: pd.Series,
    fast: int,
    slow: int,
    signal: int,
    osc_ma_type: str = "EMA",   # MA type for fast/slow lines
    signal_ma_type: str = "EMA" # MA type for signal line
) -> dict:
    """
    Returns dict with keys: macd_line, signal_line, histogram
    """
    fast_ma = apply_ma(close, fast, osc_ma_type)
    slow_ma = apply_ma(close, slow, osc_ma_type)
    macd_line = fast_ma - slow_ma
    signal_line = apply_ma(macd_line, signal, signal_ma_type)
    histogram = macd_line - signal_line

    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram,
    }


# ---------------------------------------------------------------------------
# RSI with smoothing
# ---------------------------------------------------------------------------

def calculate_rsi(
    close: pd.Series,
    length: int = 14,
    smooth_type: str = "EMA",
    smooth_length: int = 1
) -> dict:
    """
    Returns dict with keys: rsi, rsi_smooth
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Use Wilder smoothing (RMA = EMA with alpha=1/period)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)

    if smooth_length > 1:
        rsi_smooth = apply_ma(rsi, smooth_length, smooth_type)
    else:
        rsi_smooth = rsi.copy()

    return {"rsi": rsi, "rsi_smooth": rsi_smooth}


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------

def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


# ---------------------------------------------------------------------------
# Signal detection helpers
# ---------------------------------------------------------------------------

def histogram_crossed_above_zero(hist: pd.Series) -> bool:
    """True if last bar's histogram crossed from negative to positive."""
    if len(hist) < 2:
        return False
    return hist.iloc[-2] <= 0 and hist.iloc[-1] > 0


def histogram_crossed_below_zero(hist: pd.Series) -> bool:
    """True if last bar's histogram crossed from positive to negative."""
    if len(hist) < 2:
        return False
    return hist.iloc[-2] >= 0 and hist.iloc[-1] < 0
