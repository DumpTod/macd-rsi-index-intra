"""
FastAPI backend for MACD+RSI Scanner.
All API endpoints for frontend dashboard, history, backtest, and settings.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List
import pytz

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import INSTRUMENTS, RISK
from scanner import get_scanner
from supabase_client import get_db
from scheduler import start_scheduler, stop_scheduler, get_latest_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting MACD+RSI Scanner backend...")
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Scheduler stopped.")


app = FastAPI(
    title="MACD+RSI Intraday Scanner",
    description="Professional intraday scanner for NIFTY, BANKNIFTY, SENSEX",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "time": datetime.now(IST).isoformat(),
        "market_open": get_scanner()._is_market_hours()
    }
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "time": datetime.now(IST).isoformat(),
        "market_open": get_scanner()._is_market_hours()
    }
# ---------------------------------------------------------------------------
# Fyers Token Refresh (visit /refresh in browser each morning)
# ---------------------------------------------------------------------------
import os, hashlib, requests as http_requests
from fastapi.responses import RedirectResponse, HTMLResponse

@app.get("/refresh")
async def refresh_token():
    """Visit this URL each morning to refresh Fyers access token."""
    from fyers_apiv3 import fyersModel
    app_id     = os.getenv("FYERS_APP_ID", "")
    secret_key = os.getenv("FYERS_SECRET_KEY", "")
    redirect = os.getenv("FYERS_REDIRECT_URI", "https://macd-rsi-index-intra.onrender.com/callback")

    session = fyersModel.SessionModel(
        client_id=app_id,
        secret_key=secret_key,
        redirect_uri=redirect,
        response_type="code",
        grant_type="authorization_code"
    )
    auth_url = session.generate_authcode()
    return RedirectResponse(url=auth_url)


@app.get("/callback")
async def fyers_callback(auth_code: str = Query(None, alias="auth_code"),
                         code: str = Query(None)):
    """Fyers redirects here after login. Auto-generates and saves new token."""
    from fyers_apiv3 import fyersModel
    from fyers_api import FyersClient, _client
    import fyers_api as fyers_module

    auth = auth_code or code
    if not auth:
        return HTMLResponse("<h2>❌ No auth code received</h2>", status_code=400)

    try:
        app_id     = os.getenv("FYERS_APP_ID", "")
        secret_key = os.getenv("FYERS_SECRET_KEY", "")
        redirect = os.getenv("FYERS_REDIRECT_URI", "https://macd-rsi-index-intra.onrender.com/callback")

        session = fyersModel.SessionModel(
            client_id=app_id,
            secret_key=secret_key,
            redirect_uri=redirect,
            response_type="code",
            grant_type="authorization_code"
        )
        session.set_token(auth)
        response = session.generate_token()

        if response.get("s") != "ok":
            return HTMLResponse(f"<h2>❌ Token error: {response}</h2>", status_code=400)

        access_token = response["access_token"]

        # Update environment variable in memory
        os.environ["FYERS_ACCESS_TOKEN"] = access_token

        # Reinitialize Fyers client singleton
        fyers_module._client = None  # reset singleton
        new_client = fyers_module.get_fyers_client()  # reinitialize

        # Also reinitialize scanner's fyers client
        from scanner import get_scanner
        scanner = get_scanner()
        scanner.fyers = new_client

        logger.info("Fyers token refreshed successfully via /callback")

        return HTMLResponse("""
        <html>
        <body style="font-family:sans-serif;text-align:center;padding:60px;background:#F8F9FA">
        <h1 style="color:#28A745">✅ Token Refreshed!</h1>
        <p style="color:#2C3E50;font-size:18px">MACD+RSI Scanner is ready for today.</p>
        <p style="color:#666">You can close this tab.</p>
        </body></html>
        """)

    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return HTMLResponse(f"<h2>❌ Error: {e}</h2>", status_code=500)
# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/api/dashboard")
async def get_dashboard():
    """Full dashboard data: open positions, PnL, signals, capital."""
    scanner = get_scanner()
    data = scanner.get_dashboard_data()
    data["latest_signals"] = get_latest_signals()
    return data


@app.post("/api/scan/now")
async def trigger_scan_now():
    """Manually trigger a scan cycle."""
    scanner = get_scanner()
    try:
        signals = scanner.run_scan()
        return {"signals": signals, "count": len(signals)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Trades / History
# ---------------------------------------------------------------------------

@app.get("/api/trades")
async def get_trades(
    instrument: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(200, le=500),
):
    db = get_db()
    trades = db.get_trades(instrument=instrument, grade=grade, status=status,
                           date_from=date_from, date_to=date_to, limit=limit)
    return {"trades": trades, "count": len(trades)}


class RescanRequest(BaseModel):
    trade_id: str


@app.post("/api/trades/rescan")
async def rescan_trade(req: RescanRequest):
    """Rescan a single open trade to update its status."""
    db = get_db()
    trades = db.get_trades()
    trade = next((t for t in trades if t["id"] == req.trade_id), None)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    scanner = get_scanner()
    inst = trade["instrument"]
    cfg = INSTRUMENTS.get(inst)
    if not cfg:
        raise HTTPException(status_code=400, detail="Unknown instrument")

    from fyers_api import get_fyers_client
    fyers = get_fyers_client()
    df = fyers.get_candles(cfg["fyers_symbol"], cfg["timeframe"], lookback_days=10)
    if df is None:
        raise HTTPException(status_code=503, detail="Could not fetch market data")

    # Find entry bar and replay
    entry_price = trade["entry_price"]
    entry_time = trade["entry_time"]
    signal = trade["signal"]
    lot_size = cfg["lot_size"]
    atr_mult = cfg.get("atr_multiplier", 3.0)
    atr_period = cfg.get("atr_period", 10)

    from indicators import calculate_atr
    atr_series = calculate_atr(df["high"], df["low"], df["close"], atr_period)

    # Check if price reached entry
    if signal == "BUY":
        entry_met = (df["low"] <= entry_price).any()
    else:
        entry_met = (df["high"] >= entry_price).any()

    if not entry_met:
        return {"status": "ENTRY_NOT_MET", "message": "Price has not reached entry level"}

    # Replay for SL hits
    highest = entry_price
    lowest = entry_price
    trail_sl = (entry_price - atr_mult * atr_series.iloc[-1]) if signal == "BUY" else (entry_price + atr_mult * atr_series.iloc[-1])

    for _, row in df.iterrows():
        if signal == "BUY":
            if row["high"] > highest:
                highest = row["high"]
                new_sl = highest - atr_mult * atr_series.loc[row.name]
                if new_sl > trail_sl:
                    trail_sl = new_sl
            if row["low"] <= trail_sl:
                pnl_pts = trail_sl - entry_price
                pnl_inr = pnl_pts * lot_size
                db.update_trade(trade["id"], {
                    "exit_price": trail_sl, "exit_type": "TRAIL_SL",
                    "pnl_points": round(pnl_pts, 2), "pnl_rupees": round(pnl_inr, 2),
                    "status": "SL_HIT", "exit_time": datetime.now(IST).isoformat()
                })
                return {"status": "SL_HIT", "exit_price": trail_sl, "pnl_points": pnl_pts, "pnl_rupees": pnl_inr}
        else:
            if row["low"] < lowest:
                lowest = row["low"]
                new_sl = lowest + atr_mult * atr_series.loc[row.name]
                if new_sl < trail_sl:
                    trail_sl = new_sl
            if row["high"] >= trail_sl:
                pnl_pts = entry_price - trail_sl
                pnl_inr = pnl_pts * lot_size
                db.update_trade(trade["id"], {
                    "exit_price": trail_sl, "exit_type": "TRAIL_SL",
                    "pnl_points": round(pnl_pts, 2), "pnl_rupees": round(pnl_inr, 2),
                    "status": "SL_HIT", "exit_time": datetime.now(IST).isoformat()
                })
                return {"status": "SL_HIT", "exit_price": trail_sl, "pnl_points": pnl_pts, "pnl_rupees": pnl_inr}

    # Still open
    ltp = df["close"].iloc[-1]
    direction = "IN_PROFIT" if (signal == "BUY" and ltp > entry_price) or (signal == "SELL" and ltp < entry_price) else "IN_LOSS"
    return {"status": direction, "current_price": ltp, "entry_price": entry_price}


@app.post("/api/trades/rescan-all")
async def rescan_all():
    """Rescan all open trades."""
    db = get_db()
    open_trades = db.get_open_trades()
    results = []
    for trade in open_trades:
        try:
            from pydantic import BaseModel
            result = await rescan_trade(RescanRequest(trade_id=trade["id"]))
            results.append({"trade_id": trade["id"], "instrument": trade["instrument"], **result})
        except Exception as e:
            results.append({"trade_id": trade["id"], "error": str(e)})
    return {"results": results}


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

@app.get("/api/backtest")
async def get_backtest(instrument: Optional[str] = Query(None)):
    db = get_db()
    trades = db.get_backtest_trades(instrument=instrument)

    # Aggregate monthly PnL
    monthly: dict = {}
    for t in trades:
        key = f"{t.get('year', '')}-{t.get('month', '')}"
        inst = t.get("instrument", "")
        k2 = f"{key}-{inst}"
        if k2 not in monthly:
            monthly[k2] = {"year": t.get("year"), "month": t.get("month"),
                           "instrument": inst, "pnl_points": 0, "pnl_rupees": 0,
                           "trades": 0, "wins": 0}
        monthly[k2]["pnl_points"] += t.get("pnl_points", 0)
        monthly[k2]["pnl_rupees"] += t.get("pnl_rupees", 0)
        monthly[k2]["trades"] += 1
        if t.get("pnl_points", 0) > 0:
            monthly[k2]["wins"] += 1

    return {
        "monthly_summary": list(monthly.values()),
        "total_trades": len(trades),
        "backtest_performance": {
            "NIFTY": {"total_pnl_pts": 15465, "total_pnl_inr": 1005248, "win_rate": 47, "profit_months": 21, "loss_months": 3},
            "BANKNIFTY": {"total_pnl_pts": 30212, "total_pnl_inr": 906372, "win_rate": 39, "profit_months": 19, "loss_months": 5},
            "SENSEX": {"total_pnl_pts": 44648, "total_pnl_inr": 892959, "win_rate": 45, "profit_months": 17, "loss_months": 7},
        }
    }


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingsUpdate(BaseModel):
    fyers_app_id: Optional[str] = None
    fyers_secret_key: Optional[str] = None
    fyers_access_token: Optional[str] = None
    scanner_enabled: Optional[bool] = None
    nifty_enabled: Optional[bool] = None
    banknifty_enabled: Optional[bool] = None
    sensex_enabled: Optional[bool] = None
    grade_filter: Optional[List[str]] = None
    daily_loss_limit: Optional[float] = None
    capital: Optional[float] = None


@app.get("/api/settings")
async def get_settings():
    scanner = get_scanner()
    return {
        "scanner_running": True,
        "instruments": {
            name: {"enabled": scanner.states[name].enabled}
            for name in INSTRUMENTS
        },
        "risk": RISK,
        "capital": scanner.capital,
        "daily_loss_limit": RISK["max_daily_loss"],
    }


@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    scanner = get_scanner()
    if settings.nifty_enabled is not None:
        scanner.states["NIFTY"].enabled = settings.nifty_enabled
    if settings.banknifty_enabled is not None:
        scanner.states["BANKNIFTY"].enabled = settings.banknifty_enabled
    if settings.sensex_enabled is not None:
        scanner.states["SENSEX"].enabled = settings.sensex_enabled
    if settings.capital is not None:
        scanner.capital = settings.capital
    return {"message": "Settings updated successfully"}


@app.get("/api/daily-summary")
async def get_daily_summary(instrument: Optional[str] = Query(None)):
    db = get_db()
    return {"summary": db.get_daily_summary(instrument)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
