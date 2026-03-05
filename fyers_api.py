"""
Fyers API v3 connection and data fetching module.
Handles authentication, token refresh, and OHLCV data retrieval.
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from fyers_apiv3 import fyersModel
    FYERS_AVAILABLE = True
except ImportError:
    FYERS_AVAILABLE = False
    logger.warning("fyers-apiv3 not installed. Running in MOCK mode.")


class FyersClient:
    def __init__(self):
        self.app_id = os.getenv("FYERS_APP_ID", "")
        self.secret_key = os.getenv("FYERS_SECRET_KEY", "")
        self.access_token = os.getenv("FYERS_ACCESS_TOKEN", "")
        self.client = None
        self._mock_mode = not FYERS_AVAILABLE or not self.access_token

        if not self._mock_mode:
            self._init_client()

    def _init_client(self):
        try:
            self.client = fyersModel.FyersModel(
                client_id=self.app_id,
                is_async=False,
                token=self.access_token,
                log_path=""
            )
            logger.info("Fyers client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to init Fyers client: {e}")
            self._mock_mode = True

    def get_candles(
        self,
        symbol: str,
        resolution: str = "15",
        lookback_days: int = 5
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV candles for a symbol.
        Returns DataFrame with columns: datetime, open, high, low, close, volume
        """
        if self._mock_mode:
            return self._generate_mock_data(symbol, resolution, lookback_days)

        try:
            date_format = "%Y-%m-%d"
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            data = {
                "symbol": symbol,
                "resolution": resolution,
                "date_format": "1",  # epoch
                "range_from": start_date.strftime(date_format),
                "range_to": end_date.strftime(date_format),
                "cont_flag": "1"
            }

            response = self.client.history(data=data)

            if response.get("s") != "ok":
                logger.error(f"Fyers API error for {symbol}: {response}")
                return None

            candles = response["candles"]
            df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
            df = df.drop(columns=["timestamp"])
            df = df.sort_values("datetime").reset_index(drop=True)
            return df

        except Exception as e:
            logger.error(f"Error fetching candles for {symbol}: {e}")
            return None

    def get_quote(self, symbol: str) -> Optional[dict]:
        """Get current quote for a symbol."""
        if self._mock_mode:
            return {"ltp": 22000 + (hash(symbol) % 500)}

        try:
            response = self.client.quotes(data={"symbols": symbol})
            if response.get("s") == "ok":
                d = response["d"][0]["v"]
                return {"ltp": d.get("lp", 0), "volume": d.get("volume", 0)}
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
        return None

    def _generate_mock_data(self, symbol: str, resolution: str, lookback_days: int) -> pd.DataFrame:
        """Generate realistic mock OHLCV data for testing."""
        import numpy as np
        np.random.seed(hash(symbol) % 1000)

        # Base prices per instrument
        base_prices = {
            "NSE:NIFTY50-INDEX": 22000,
            "NSE:NIFTYBANK-INDEX": 48000,
            "BSE:SENSEX-INDEX": 73000,
        }
        base = base_prices.get(symbol, 22000)

        periods_per_day = int(375 / int(resolution))  # market minutes / resolution
        total_candles = periods_per_day * lookback_days

        # Simulate price walk
        returns = np.random.normal(0, 0.002, total_candles)
        closes = base * np.cumprod(1 + returns)

        highs = closes * (1 + abs(np.random.normal(0, 0.003, total_candles)))
        lows = closes * (1 - abs(np.random.normal(0, 0.003, total_candles)))
        opens = np.roll(closes, 1)
        opens[0] = closes[0]

        # Generate timestamps (market hours 9:15 to 15:30)
        start = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        start -= timedelta(days=lookback_days)
        timestamps = []
        current = start
        for _ in range(total_candles):
            if current.hour >= 15 and current.minute >= 30:
                current += timedelta(days=1)
                current = current.replace(hour=9, minute=15)
            timestamps.append(current)
            current += timedelta(minutes=int(resolution))

        df = pd.DataFrame({
            "datetime": pd.to_datetime(timestamps),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": np.random.randint(1000, 50000, total_candles),
        })
        return df


# Singleton
_client: Optional[FyersClient] = None


def get_fyers_client() -> FyersClient:
    global _client
    if _client is None:
        _client = FyersClient()
    return _client
