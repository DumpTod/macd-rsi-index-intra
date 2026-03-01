"""
Supabase client for database operations.
Handles all CRUD for trades, daily_summary, and backtest_trades tables.
"""

import os
import logging
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import uuid

logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("supabase-py not installed. Running in in-memory mock mode.")


class SupabaseClient:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL", "")
        self.key = os.getenv("SUPABASE_KEY", "")
        self.client: Optional[Any] = None
        self._mock = not SUPABASE_AVAILABLE or not self.url

        # In-memory store for mock mode
        self._mock_trades: List[Dict] = []
        self._mock_backtest: List[Dict] = []
        self._mock_summary: List[Dict] = []

        if not self._mock:
            try:
                self.client = create_client(self.url, self.key)
                logger.info("Supabase client initialized.")
            except Exception as e:
                logger.error(f"Supabase init failed: {e}")
                self._mock = True

    # ------------------------------------------------------------------
    # Trades table
    # ------------------------------------------------------------------

    def insert_trade(self, trade: Dict) -> Optional[Dict]:
        trade.setdefault("id", str(uuid.uuid4()))
        trade.setdefault("status", "OPEN")
        if self._mock:
            self._mock_trades.append(trade)
            return trade
        try:
            res = self.client.table("trades").insert(trade).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"insert_trade error: {e}")
            return None

    def update_trade(self, trade_id: str, updates: Dict) -> bool:
        if self._mock:
            for t in self._mock_trades:
                if t["id"] == trade_id:
                    t.update(updates)
                    return True
            return False
        try:
            self.client.table("trades").update(updates).eq("id", trade_id).execute()
            return True
        except Exception as e:
            logger.error(f"update_trade error: {e}")
            return False

    def get_open_trades(self) -> List[Dict]:
        if self._mock:
            return [t for t in self._mock_trades if t.get("status") == "OPEN"]
        try:
            res = self.client.table("trades").select("*").eq("status", "OPEN").execute()
            return res.data or []
        except Exception as e:
            logger.error(f"get_open_trades error: {e}")
            return []

    def get_trades(
        self,
        instrument: Optional[str] = None,
        grade: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 200
    ) -> List[Dict]:
        if self._mock:
            results = self._mock_trades[:]
            if instrument:
                results = [t for t in results if t.get("instrument") == instrument]
            if grade:
                results = [t for t in results if t.get("grade") == grade]
            if status:
                results = [t for t in results if t.get("status") == status]
            return results[-limit:]

        try:
            q = self.client.table("trades").select("*").order("entry_time", desc=True).limit(limit)
            if instrument:
                q = q.eq("instrument", instrument)
            if grade:
                q = q.eq("grade", grade)
            if status:
                q = q.eq("status", status)
            if date_from:
                q = q.gte("entry_time", date_from)
            if date_to:
                q = q.lte("entry_time", date_to)
            res = q.execute()
            return res.data or []
        except Exception as e:
            logger.error(f"get_trades error: {e}")
            return []

    def get_today_trades(self, instrument: Optional[str] = None) -> List[Dict]:
        today = date.today().isoformat()
        return self.get_trades(instrument=instrument, date_from=today)

    # ------------------------------------------------------------------
    # Daily summary table
    # ------------------------------------------------------------------

    def upsert_daily_summary(self, summary: Dict) -> bool:
        if self._mock:
            for i, s in enumerate(self._mock_summary):
                if s["date"] == summary["date"] and s["instrument"] == summary["instrument"]:
                    self._mock_summary[i].update(summary)
                    return True
            self._mock_summary.append(summary)
            return True
        try:
            self.client.table("daily_summary").upsert(summary, on_conflict="date,instrument").execute()
            return True
        except Exception as e:
            logger.error(f"upsert_daily_summary error: {e}")
            return False

    def get_daily_summary(self, instrument: Optional[str] = None) -> List[Dict]:
        if self._mock:
            if instrument:
                return [s for s in self._mock_summary if s.get("instrument") == instrument]
            return self._mock_summary
        try:
            q = self.client.table("daily_summary").select("*").order("date", desc=True).limit(100)
            if instrument:
                q = q.eq("instrument", instrument)
            res = q.execute()
            return res.data or []
        except Exception as e:
            logger.error(f"get_daily_summary error: {e}")
            return []

    # ------------------------------------------------------------------
    # Backtest trades table
    # ------------------------------------------------------------------

    def get_backtest_trades(self, instrument: Optional[str] = None) -> List[Dict]:
        if self._mock:
            if instrument:
                return [t for t in self._mock_backtest if t.get("instrument") == instrument]
            return self._mock_backtest
        try:
            q = self.client.table("backtest_trades").select("*").order("entry_time", desc=True)
            if instrument:
                q = q.eq("instrument", instrument)
            res = q.execute()
            return res.data or []
        except Exception as e:
            logger.error(f"get_backtest_trades error: {e}")
            return []


# Singleton
_db: Optional[SupabaseClient] = None


def get_db() -> SupabaseClient:
    global _db
    if _db is None:
        _db = SupabaseClient()
    return _db
