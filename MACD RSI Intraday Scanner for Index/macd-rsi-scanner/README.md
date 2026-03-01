# MACD+RSI Intraday Scanner

> Professional real-time intraday trading scanner for NIFTY, BANKNIFTY & SENSEX using optimized MACD+RSI strategy. Backtested Jan 2024 – Dec 2025 with ₹28L+ combined profit.

---

## 🏗 Architecture

```
Frontend (HTML/CSS/JS)  →  FastAPI Backend  →  Fyers API v3
         ↓                       ↓
   Static on Render       Render Web Service
         ↓                       ↓
              Supabase PostgreSQL DB
```

---

## 📁 Project Structure

```
macd-rsi-scanner/
├── frontend/
│   ├── index.html          # Live scanner dashboard
│   ├── history.html        # Trade history + rescan
│   ├── backtest.html       # Backtest results (2024-2025)
│   ├── settings.html       # Settings & credentials
│   ├── css/style.css       # Dark terminal design system
│   └── js/
│       ├── supabase.js     # API helpers + formatters
│       ├── scanner.js      # Live dashboard logic
│       └── history.js      # History + rescan logic
│
├── backend/
│   ├── main.py             # FastAPI app + all endpoints
│   ├── scanner.py          # Core scanning engine
│   ├── indicators.py       # MACD, RSI, ATR (SMA/EMA/WMA)
│   ├── grading.py          # A+ to D signal grading
│   ├── config.py           # Instrument config (single source of truth)
│   ├── fyers_api.py        # Fyers API v3 client (with mock mode)
│   ├── supabase_client.py  # Supabase CRUD (with mock mode)
│   └── scheduler.py        # 15-min APScheduler
│
├── supabase_schema.sql     # Run in Supabase SQL Editor
├── render.yaml             # Render deployment config
├── requirements.txt        # Python dependencies
└── README.md
```

---

## ⚡ Quick Start (Local Development)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
export FYERS_APP_ID="your_app_id"
export FYERS_SECRET_KEY="your_secret"
export FYERS_ACCESS_TOKEN="your_daily_token"
export SUPABASE_URL="https://xxx.supabase.co"
export SUPABASE_KEY="your_service_role_key"
```

### 3. Run backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 4. Open frontend
```
Open frontend/index.html in your browser
Go to Settings → set API URL to http://localhost:8000
```

> **No Fyers/Supabase credentials?** The system runs in **mock mode** automatically — it generates realistic fake data so you can test the full UI.

---

## 🚀 Deploy to Render (Production)

### Step 1: GitHub
Push all code to a GitHub repository.

### Step 2: Supabase Setup
1. Create a free project at [supabase.com](https://supabase.com)
2. Go to SQL Editor
3. Run the contents of `supabase_schema.sql`
4. Copy your `Project URL` and `service_role` key from Settings → API

### Step 3: Render Backend
1. New → Web Service → Connect GitHub repo
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables:
   - `FYERS_APP_ID`
   - `FYERS_SECRET_KEY`
   - `FYERS_ACCESS_TOKEN`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `PYTHONPATH` = `backend`

### Step 4: Render Frontend
1. New → Static Site → Connect same GitHub repo
2. Publish directory: `frontend`
3. No build command needed

### Step 5: Connect Frontend to Backend
1. Open your deployed frontend URL
2. Go to Settings page
3. Enter your Render backend URL
4. Click "Test Connection" → should show green ✓
5. Save settings

---

## 📊 Strategy Configuration

### Instrument Settings (Backtested & Optimized)

| Instrument | MACD Fast | MACD Slow | Signal | Osc MA | Sig MA | RSI Len | Smooth | Exit Method |
|-----------|-----------|-----------|--------|--------|--------|---------|--------|-------------|
| NIFTY | 16 | 34 | 12 | WMA | EMA | 9 | EMA/5 | Trail SL (10×3.0) |
| BANKNIFTY | 12 | 21 | 9 | EMA | EMA | 7 | EMA/3 | Trail SL (7×3.0) |
| SENSEX | 16 | 26 | 9 | WMA | EMA | 7 | WMA/5 | Signal-based |

### Entry Rules
- **BUY**: MACD histogram crosses above 0 AND RSI smooth > 40
- **SELL**: MACD histogram crosses below 0 AND RSI smooth < 60

### Signal Grading (Only A+, A, B+ shown)
| Score | Grade |
|-------|-------|
| 8 | A+ |
| 6-7 | A |
| 4-5 | B+ |
| ≤3 | Hidden |

---

## 🔑 Fyers Token Update (Daily)

Fyers access tokens expire daily. You must update them each morning before market open.

**Option 1 — Render Dashboard:**
Go to Environment Variables → Update `FYERS_ACCESS_TOKEN` → Save (auto-redeploys)

**Option 2 — API:**
```bash
# Update via Render API (with your Render API key)
curl -X PATCH https://api.render.com/v1/services/{serviceId}/env-vars \
  -H "Authorization: Bearer {renderApiKey}" \
  -d '{"FYERS_ACCESS_TOKEN": "new_token"}'
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/dashboard` | Full dashboard data |
| POST | `/api/scan/now` | Manual scan trigger |
| GET | `/api/trades` | Trade history (filterable) |
| POST | `/api/trades/rescan` | Rescan one trade |
| POST | `/api/trades/rescan-all` | Rescan all open trades |
| GET | `/api/backtest` | Backtest monthly breakdown |
| GET | `/api/settings` | Current settings |
| POST | `/api/settings` | Update settings |
| GET | `/api/daily-summary` | Daily P&L summary |

---

## 📈 Proven Backtest Performance (Jan 2024 – Dec 2025)

| Instrument | PnL (pts) | PnL (₹) | Win Rate | Profit Months | Final Capital |
|-----------|-----------|----------|----------|---------------|---------------|
| NIFTY | +15,465 | +₹10,05,248 | 47% | 21/24 | ₹20,05,248 |
| BANKNIFTY | +30,212 | +₹9,06,372 | 39% | 19/24 | ₹19,06,372 |
| SENSEX | +44,648 | +₹8,92,959 | 45% | 17/24 | ₹18,92,959 |

*1 lot per instrument · ₹10L starting capital each · 15min timeframe*

---

## ⚠️ Risk Disclaimer

This is a trading scanner tool, not financial advice. Past backtest performance does not guarantee future results. Always paper trade first, understand the strategy fully, and manage your own risk.
