-- ============================================================
-- MACD+RSI Scanner — Supabase PostgreSQL Schema
-- Run this in Supabase SQL Editor to create all tables
-- ============================================================

-- ── 1. Trades (live signals) ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS trades (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  instrument    TEXT NOT NULL CHECK (instrument IN ('NIFTY', 'BANKNIFTY', 'SENSEX')),
  signal        TEXT NOT NULL CHECK (signal IN ('BUY', 'SELL')),
  grade         TEXT NOT NULL CHECK (grade IN ('A+', 'A', 'B+')),
  entry_price   FLOAT NOT NULL,
  entry_time    TIMESTAMPTZ NOT NULL DEFAULT now(),
  trail_sl      FLOAT,
  atr           FLOAT,
  macd_hist     FLOAT,
  rsi_smooth    FLOAT,
  lot_size      INT NOT NULL,
  exit_price    FLOAT,
  exit_time     TIMESTAMPTZ,
  exit_type     TEXT CHECK (exit_type IN ('TRAIL_SL', 'SIGNAL', 'MANUAL', 'EOD', 'DAILY_LIMIT')),
  pnl_points    FLOAT,
  pnl_rupees    FLOAT,
  status        TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'SL_HIT', 'TP_HIT')),
  year          INT,
  month         TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Index for fast queries
CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_grade ON trades(grade);

-- ── 2. Backtest Trades ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS backtest_trades (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  instrument    TEXT NOT NULL,
  signal        TEXT NOT NULL,
  entry_price   FLOAT NOT NULL,
  entry_time    TIMESTAMPTZ NOT NULL,
  exit_price    FLOAT NOT NULL,
  exit_time     TIMESTAMPTZ NOT NULL,
  pnl_points    FLOAT NOT NULL,
  pnl_rupees    FLOAT NOT NULL,
  exit_type     TEXT,
  year          INT,
  month         TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bt_instrument ON backtest_trades(instrument);
CREATE INDEX IF NOT EXISTS idx_bt_year ON backtest_trades(year);

-- ── 3. Daily Summary ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS daily_summary (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date          DATE NOT NULL,
  instrument    TEXT NOT NULL,
  total_trades  INT DEFAULT 0,
  wins          INT DEFAULT 0,
  losses        INT DEFAULT 0,
  pnl_points    FLOAT DEFAULT 0,
  pnl_rupees    FLOAT DEFAULT 0,
  capital       FLOAT DEFAULT 0,
  created_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE(date, instrument)
);

CREATE INDEX IF NOT EXISTS idx_summary_date ON daily_summary(date DESC);

-- ── Row Level Security (allow API access) ─────────────────────────────────

ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_summary ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (used by backend)
CREATE POLICY "service_role_trades" ON trades FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_backtest" ON backtest_trades FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_summary" ON daily_summary FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Allow anon read (for frontend direct queries if needed)
CREATE POLICY "anon_read_trades" ON trades FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read_backtest" ON backtest_trades FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read_summary" ON daily_summary FOR SELECT TO anon USING (true);

-- ── Verify ───────────────────────────────────────────────────────────────

SELECT 'Schema created successfully!' AS status;
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
