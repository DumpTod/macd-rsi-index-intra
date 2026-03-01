"""
APScheduler-based 15-minute scan scheduler.
Fires at exact candle close times: 9:30, 9:45, 10:00 ... 15:15 IST
"""

import logging
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")
_scheduler: BackgroundScheduler = None
_latest_signals = []


def _run_scan():
    global _latest_signals
    from scanner import get_scanner
    scanner = get_scanner()
    try:
        signals = scanner.run_scan()
        if signals:
            _latest_signals = signals
            for s in signals:
                _log_signal(s)
    except Exception as e:
        logger.error(f"Scheduler scan error: {e}")


def _log_signal(trade: dict):
    direction = "🟢 BUY" if trade["signal"] == "BUY" else "🔴 SELL SHORT"
    logger.info(f"""
=====================================
{direction} SIGNAL — {trade['instrument']}  [{trade['grade']}]
=====================================
Time        : {trade['entry_time']}
Entry Price : {trade['entry_price']:,.2f}
Trail SL    : {trade.get('trail_sl', 'N/A')}
MACD Hist   : {trade['macd_hist']}
RSI Smooth  : {trade['rsi_smooth']}
ATR         : {trade['atr']}
Grade       : {trade['grade']}
Lot Size    : {trade['lot_size']}
=====================================
""")


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone=IST)

    # Fire at :00 and :15 and :30 and :45 of every hour, during market hours
    _scheduler.add_job(
        _run_scan,
        CronTrigger(
            minute="0,15,30,45",
            hour="9,10,11,12,13,14,15",
            day_of_week="mon-fri",
            timezone=IST
        ),
        id="market_scan",
        replace_existing=True,
        misfire_grace_time=60,
    )

    _scheduler.start()
    logger.info("Scheduler started — scanning every 15 minutes during market hours.")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Scheduler stopped.")


def get_latest_signals():
    return _latest_signals
