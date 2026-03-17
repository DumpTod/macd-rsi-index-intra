"""
Core scanner module.
Orchestrates: data fetch → indicators → signal detection → grading → trade management.
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
import pandas as pd
import pytz

from config import INSTRUMENTS, RISK
from indicators import (
    calculate_macd, calculate_rsi, calculate_atr,
    histogram_crossed_above_zero, histogram_crossed_below_zero
)
from grading import grade_signal, is_displayable
from fyers_api import get_fyers_client
from supabase_client import get_db

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")


class InstrumentState:
    """Tracks in-memory state for an instrument during a trading session."""
    def __init__(self, name: str):
        self.name = name
        self.open_trade: Optional[Dict] = None
        self.trades_today: int = 0
        self.realized_pnl_today: float = 0.0
        self.highest_price: Optional[float] = None  # for BUY trailing SL
        self.lowest_price: Optional[float] = None   # for SELL trailing SL
        self.current_trail_sl: Optional[float] = None
        self.enabled: bool = True
        self.last_signal_bar: Optional[int] = None  # index of last signal bar to avoid re-triggering


class Scanner:
    def __init__(self):
        self.fyers = get_fyers_client()
        self.db = get_db()
        self.states: Dict[str, InstrumentState] = {
            name: InstrumentState(name) for name in INSTRUMENTS
        }
        self.daily_loss: float = 0.0
        self.capital: float = float(RISK["starting_capital"])
        self._trading_halted: bool = False

        # Reload open trades from DB on startup
        self._reload_open_trades()

    def _reload_open_trades(self):
        """On startup, reload open trades from DB to resume tracking."""
        open_trades = self.db.get_open_trades()
        for trade in open_trades:
            inst = trade.get("instrument")
            if inst in self.states:
                self.states[inst].open_trade = trade
                self.states[inst].current_trail_sl = trade.get("trail_sl")

    def _is_market_hours(self) -> bool:
        now = datetime.now(IST)
        if now.weekday() >= 5:  # Saturday/Sunday
            return False
        t = now.time()
        from datetime import time
        return time(9, 30) <= t <= time(15, 15)

    def _can_take_new_trade(self, instrument: str) -> bool:
        now = datetime.now(IST).time()
        from datetime import time
        if self._trading_halted:
            return False
        if now >= time(15, 0):
            return False
        state = self.states[instrument]
        if not state.enabled:
            return False
        if state.trades_today >= RISK["max_trades_per_instrument_per_day"]:
            return False
        return True

    def _should_square_off(self) -> bool:
        now = datetime.now(IST).time()
        from datetime import time
        return now >= time(15, 15)

    def run_scan(self) -> List[Dict]:
        """
        Main scan cycle. Returns list of new signals generated this cycle.
        """
        if not self._is_market_hours():
            logger.info("Market closed. Skipping scan.")
            return []

        if self._should_square_off():
            self._square_off_all("EOD")
            return []

        signals = []
        for name, cfg in INSTRUMENTS.items():
            state = self.states[name]
            try:
                result = self._scan_instrument(name, cfg, state)
                if result:
                    signals.append(result)
            except Exception as e:
                logger.error(f"Error scanning {name}: {e}")

        # Check daily loss limit
        if abs(self.daily_loss) >= RISK["max_daily_loss"]:
            logger.warning(f"Daily loss limit hit: {self.daily_loss}. Halting trading.")
            self._trading_halted = True
            self._square_off_all("DAILY_LIMIT")

        return signals

    def _scan_instrument(self, name: str, cfg: Dict, state: InstrumentState) -> Optional[Dict]:
        """
        Scan a single instrument. Returns signal dict if new signal generated, else None.
        """
        # Fetch candles
        df = self.fyers.get_candles(cfg["fyers_symbol"], cfg["timeframe"], lookback_days=10)
        if df is None or len(df) < 50:
            logger.warning(f"Insufficient data for {name}")
            return None

        # Calculate indicators
        macd_data = calculate_macd(
            df["close"], cfg["macd_fast"], cfg["macd_slow"], cfg["macd_signal"],
            cfg["osc_ma_type"], cfg["signal_ma_type"]
        )
        rsi_data = calculate_rsi(df["close"], cfg["rsi_length"], cfg["rsi_smooth_type"], cfg["rsi_smooth_length"])
        atr_series = calculate_atr(df["high"], df["low"], df["close"], cfg["atr_period"] or 10)

        histogram = macd_data["histogram"]
        rsi_smooth = rsi_data["rsi_smooth"]
        atr_current = atr_series.iloc[-1]
        atr_avg_20 = atr_series.iloc[-20:].mean()
        current_price = df["close"].iloc[-1]

        # Update open trade's trailing SL if applicable
        if state.open_trade:
            self._update_trailing_sl(state, df, cfg, atr_series)
            # Check if SL hit
            sl_hit = self._check_sl_hit(state, df)
            if sl_hit:
                return None  # Trade closed, no new signal this bar

        # Check for new signal (only if no open trade or position just closed)
        signal = None
        rsi_val = rsi_smooth.iloc[-1]

        if histogram_crossed_above_zero(histogram) and rsi_val > 40:
            signal = "BUY"
        elif histogram_crossed_below_zero(histogram) and rsi_val < 60:
            signal = "SELL"

        if signal is None:
            return None

        # Handle opposite signal → exit existing trade
        if state.open_trade:
            existing_signal = state.open_trade.get("signal")
            if existing_signal != signal:
                self._close_trade(state, current_price, "SIGNAL", df)

        if not self._can_take_new_trade(name):
            return None

        # Grade the signal
        grade = grade_signal(histogram, rsi_val, atr_current, atr_avg_20, signal)

        # Calculate initial trailing SL
        trail_sl = self._calculate_trail_sl(signal, current_price, atr_current, cfg)

        # Build trade record
        now_ist = datetime.now(IST)
        trade = {
            "instrument": name,
            "signal": signal,
            "grade": grade,
            "entry_price": round(current_price, 2),
            "entry_time": now_ist.isoformat(),
            "trail_sl": round(trail_sl, 2) if trail_sl else None,
            "atr": round(atr_current, 2),
            "macd_hist": round(histogram.iloc[-1], 4),
            "rsi_smooth": round(rsi_val, 2),
            "lot_size": cfg["lot_size"],
            "exit_price": None,
            "exit_time": None,
            "exit_type": None,
            "pnl_points": None,
            "pnl_rupees": None,
            "status": "OPEN",
            "year": now_ist.year,
            "month": now_ist.strftime("%B"),
        }

        # Persist and update state
        saved = self.db.insert_trade(trade)
        trade["id"] = saved["id"] if saved else trade.get("id")
        state.open_trade = trade
        state.trades_today += 1
        state.current_trail_sl = trail_sl
        state.highest_price = current_price if signal == "BUY" else None
        state.lowest_price = current_price if signal == "SELL" else None

        logger.info(f"NEW SIGNAL [{grade}] {signal} {name} @ {current_price}")
        if not is_displayable(grade):
            logger.info(f"{name} signal {signal} graded {grade} — skipped.")
            return None  # Don't display but still save to DB below

    def _calculate_trail_sl(self, signal: str, price: float, atr: float, cfg: Dict) -> Optional[float]:
        if cfg["exit_method"] == "SIGNAL_ONLY":
            return None
        mult = cfg["atr_multiplier"] or 3.0
        if signal == "BUY":
            return price - (mult * atr)
        else:
            return price + (mult * atr)

    def _update_trailing_sl(self, state: InstrumentState, df: pd.DataFrame, cfg: Dict, atr_series: pd.Series):
        if cfg["exit_method"] == "SIGNAL_ONLY":
            return
        if not state.open_trade or not state.current_trail_sl:
            return

        signal = state.open_trade["signal"]
        current_price = df["close"].iloc[-1]
        atr_current = atr_series.iloc[-1]
        mult = cfg.get("atr_multiplier", 3.0)

        if signal == "BUY":
            if state.highest_price is None or current_price > state.highest_price:
                state.highest_price = current_price
            new_sl = state.highest_price - (mult * atr_current)
            if new_sl > state.current_trail_sl:
                state.current_trail_sl = new_sl
                self.db.update_trade(state.open_trade["id"], {"trail_sl": round(new_sl, 2)})
        else:  # SELL
            if state.lowest_price is None or current_price < state.lowest_price:
                state.lowest_price = current_price
            new_sl = state.lowest_price + (mult * atr_current)
            if new_sl < state.current_trail_sl:
                state.current_trail_sl = new_sl
                self.db.update_trade(state.open_trade["id"], {"trail_sl": round(new_sl, 2)})

    def _check_sl_hit(self, state: InstrumentState, df: pd.DataFrame) -> bool:
        if not state.open_trade or state.current_trail_sl is None:
            return False

        current_low = df["low"].iloc[-1]
        current_high = df["high"].iloc[-1]
        signal = state.open_trade["signal"]
        sl = state.current_trail_sl

        if signal == "BUY" and current_low <= sl:
            self._close_trade(state, sl, "TRAIL_SL", df)
            return True
        elif signal == "SELL" and current_high >= sl:
            self._close_trade(state, sl, "TRAIL_SL", df)
            return True
        return False

    def _close_trade(self, state: InstrumentState, exit_price: float, exit_type: str, df: pd.DataFrame):
        if not state.open_trade:
            return

        trade = state.open_trade
        signal = trade["signal"]
        entry = trade["entry_price"]
        lot_size = trade["lot_size"]

        pnl_points = (exit_price - entry) if signal == "BUY" else (entry - exit_price)
        pnl_rupees = pnl_points * lot_size

        now_ist = datetime.now(IST)
        status = "SL_HIT" if "SL" in exit_type else "CLOSED"

        updates = {
            "exit_price": round(exit_price, 2),
            "exit_time": now_ist.isoformat(),
            "exit_type": exit_type,
            "pnl_points": round(pnl_points, 2),
            "pnl_rupees": round(pnl_rupees, 2),
            "status": status,
        }

        self.db.update_trade(trade["id"], updates)
        self.daily_loss += pnl_rupees
        state.open_trade = None
        state.current_trail_sl = None
        state.highest_price = None
        state.lowest_price = None

        logger.info(f"CLOSED {trade['instrument']} {signal} @ {exit_price} | PnL: {pnl_points:.2f} pts | ₹{pnl_rupees:.0f} [{exit_type}]")

        # Update daily summary
        self._update_daily_summary(state, pnl_rupees)

    def _update_daily_summary(self, state: InstrumentState, pnl_rupees: float):
        today = date.today().isoformat()
        summaries = self.db.get_daily_summary(state.name)
        todays = next((s for s in summaries if s["date"] == today), None)

        if todays:
            todays["total_trades"] = todays.get("total_trades", 0) + 1
            todays["wins"] = todays.get("wins", 0) + (1 if pnl_rupees >= 0 else 0)
            todays["losses"] = todays.get("losses", 0) + (1 if pnl_rupees < 0 else 0)
            todays["pnl_rupees"] = todays.get("pnl_rupees", 0) + pnl_rupees
            self.db.upsert_daily_summary(todays)
        else:
            self.db.upsert_daily_summary({
                "date": today,
                "instrument": state.name,
                "total_trades": 1,
                "wins": 1 if pnl_rupees >= 0 else 0,
                "losses": 1 if pnl_rupees < 0 else 0,
                "pnl_points": 0,
                "pnl_rupees": pnl_rupees,
                "capital": self.capital,
            })

    def _square_off_all(self, reason: str):
        for name, state in self.states.items():
            if state.open_trade:
                quote = self.fyers.get_quote(INSTRUMENTS[name]["fyers_symbol"])
                price = quote["ltp"] if quote else state.open_trade["entry_price"]
                self._close_trade(state, price, reason, pd.DataFrame())

    def get_dashboard_data(self) -> Dict:
        """Return all data needed for the live dashboard."""
        instruments_data = []
        total_realized_pnl = 0.0

        for name, cfg in INSTRUMENTS.items():
            state = self.states[name]
            quote = self.fyers.get_quote(cfg["fyers_symbol"])
            ltp = quote["ltp"] if quote else 0

            open_trade = state.open_trade
            unrealized_pnl_pts = 0.0
            unrealized_pnl_inr = 0.0

            if open_trade:
                entry = open_trade["entry_price"]
                signal = open_trade["signal"]
                unrealized_pnl_pts = (ltp - entry) if signal == "BUY" else (entry - ltp)
                unrealized_pnl_inr = unrealized_pnl_pts * cfg["lot_size"]

            today_trades = self.db.get_today_trades(name)
            realized = sum(t.get("pnl_rupees", 0) or 0 for t in today_trades if t.get("status") != "OPEN")
            total_realized_pnl += realized

            instruments_data.append({
                "instrument": name,
                "ltp": round(ltp, 2),
                "open_trade": open_trade,
                "trail_sl": state.current_trail_sl,
                "unrealized_pnl_pts": round(unrealized_pnl_pts, 2),
                "unrealized_pnl_inr": round(unrealized_pnl_inr, 2),
                "trades_today": state.trades_today,
                "realized_pnl": round(realized, 2),
                "enabled": state.enabled,
            })

        return {
            "instruments": instruments_data,
            "total_realized_pnl": round(total_realized_pnl, 2),
            "daily_loss": round(self.daily_loss, 2),
            "daily_loss_limit": RISK["max_daily_loss"],
            "capital": round(self.capital, 2),
            "trading_halted": self._trading_halted,
            "market_open": self._is_market_hours(),
            "timestamp": datetime.now(IST).isoformat(),
        }


# Singleton
_scanner: Optional[Scanner] = None


def get_scanner() -> Scanner:
    global _scanner
    if _scanner is None:
        _scanner = Scanner()
    return _scanner
