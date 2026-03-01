"""
Instrument configuration: all backtested settings per instrument.
Single source of truth for all indicator params, lot sizes, ATR settings.
"""

INSTRUMENTS = {
    "NIFTY": {
        "fyers_symbol": "NSE:NIFTY50-INDEX",
        "lot_size": 75,
        "timeframe": "15",
        "macd_fast": 16,
        "macd_slow": 34,
        "macd_signal": 12,
        "osc_ma_type": "WMA",
        "signal_ma_type": "EMA",
        "rsi_length": 9,
        "rsi_smooth_type": "EMA",
        "rsi_smooth_length": 5,
        "exit_method": "TRAILING_SL",
        "atr_period": 10,
        "atr_multiplier": 3.0,
    },
    "BANKNIFTY": {
        "fyers_symbol": "NSE:NIFTYBANK-INDEX",
        "lot_size": 30,
        "timeframe": "15",
        "macd_fast": 12,
        "macd_slow": 21,
        "macd_signal": 9,
        "osc_ma_type": "EMA",
        "signal_ma_type": "EMA",
        "rsi_length": 7,
        "rsi_smooth_type": "EMA",
        "rsi_smooth_length": 3,
        "exit_method": "TRAILING_SL",
        "atr_period": 7,
        "atr_multiplier": 3.0,
    },
    "SENSEX": {
        "fyers_symbol": "BSE:SENSEX-INDEX",
        "lot_size": 20,
        "timeframe": "15",
        "macd_fast": 16,
        "macd_slow": 26,
        "macd_signal": 9,
        "osc_ma_type": "WMA",
        "signal_ma_type": "EMA",
        "rsi_length": 7,
        "rsi_smooth_type": "WMA",
        "rsi_smooth_length": 5,
        "exit_method": "SIGNAL_ONLY",
        "atr_period": None,
        "atr_multiplier": None,
    },
}

RISK = {
    "starting_capital": 1_000_000,
    "max_trades_per_instrument_per_day": 3,
    "max_daily_loss": 25_000,
    "max_loss_per_trade_alert": 15_000,
    "scan_start": "09:30",
    "no_new_trades_after": "15:00",
    "square_off_time": "15:15",
}
