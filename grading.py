"""
Trade grading logic: A+ to D based on MACD strength, RSI, and ATR.
Only A+, A, B+ are actionable.
"""

import pandas as pd


GRADE_MAP = {
    8: "A+",
    7: "A",
    6: "A",
    5: "B+",
    4: "B+",
    3: "B",
    2: "C",
    1: "D",
    0: "D",
}

DISPLAY_GRADES = {"A+", "A", "B+"}


def macd_strength_score(histogram: pd.Series) -> int:
    """
    Score 0-3 based on histogram momentum.
    """
    if len(histogram) < 2:
        return 0
    curr = abs(histogram.iloc[-1])
    prev = abs(histogram.iloc[-2])
    if prev == 0:
        return 1
    ratio = curr / prev
    if ratio > 2.0:
        return 3
    elif ratio > 1.0:
        return 2
    else:
        return 1


def rsi_strength_score(rsi_smooth: float, signal: str) -> int:
    """
    Score 0-3 based on RSI smooth value and direction.
    """
    if signal == "BUY":
        if rsi_smooth > 55:
            return 3
        elif rsi_smooth > 50:
            return 2
        elif rsi_smooth > 40:
            return 1
        else:
            return 0
    else:  # SELL
        if rsi_smooth < 45:
            return 3
        elif rsi_smooth < 50:
            return 2
        elif rsi_smooth < 60:
            return 1
        else:
            return 0


def atr_score(atr_current: float, atr_avg_20: float) -> int:
    """
    Score 0-2 based on ATR vs 20-period average.
    """
    if atr_avg_20 <= 0:
        return 0
    ratio = atr_current / atr_avg_20
    if ratio > 1.5:
        return 2
    elif ratio >= 1.0:
        return 1
    else:
        return 0


def grade_signal(
    histogram: pd.Series,
    rsi_smooth: float,
    atr_current: float,
    atr_avg_20: float,
    signal: str
) -> str:
    """
    Returns grade string: A+, A, B+, B, C, D
    """
    total = (
        macd_strength_score(histogram)
        + rsi_strength_score(rsi_smooth, signal)
        + atr_score(atr_current, atr_avg_20)
    )
    return GRADE_MAP.get(total, "D")


def is_displayable(grade: str) -> bool:
    return grade in DISPLAY_GRADES
