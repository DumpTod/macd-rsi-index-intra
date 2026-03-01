/**
 * scanner.js — Live dashboard logic
 * Polls API every 15 minutes (at candle close) and updates the UI.
 */

let dashboardData = null;
let countdownTimer = null;
let nextScanTime = null;

// ── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  scheduleNextScan();
  setInterval(updateCountdown, 1000);
});

// ── Data Loading ─────────────────────────────────────────────────────────────

async function loadDashboard() {
  try {
    showLoading(true);
    dashboardData = await apiGet('/api/dashboard');
    renderDashboard(dashboardData);
  } catch (e) {
    showError('Could not connect to scanner backend. Is it running?');
    console.error(e);
  } finally {
    showLoading(false);
  }
}

async function triggerManualScan() {
  const btn = document.getElementById('scan-now-btn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Scanning...';
  }
  try {
    const res = await apiPost('/api/scan/now');
    if (res.signals && res.signals.length > 0) {
      res.signals.forEach(s => showSignalToast(s));
    } else {
      showToastMessage('Scan complete — no new signals', 'neutral');
    }
    await loadDashboard();
  } catch (e) {
    showToastMessage('Scan failed: ' + e.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '⟳ Scan Now';
    }
  }
}

// ── Rendering ─────────────────────────────────────────────────────────────────

function renderDashboard(data) {
  if (!data) return;

  // Market status
  const marketBadge = document.getElementById('market-badge');
  if (marketBadge) {
    marketBadge.className = `market-badge ${data.market_open ? 'open' : 'closed'}`;
    marketBadge.innerHTML = `
      <span class="market-badge-dot"></span>
      ${data.market_open ? 'MARKET OPEN' : 'MARKET CLOSED'}
    `;
  }

  // Stats bar
  setEl('total-pnl', fmtINR(data.total_realized_pnl), data.total_realized_pnl >= 0 ? 'profit' : 'loss');
  setEl('capital', `₹${formatLakh(data.capital)}`, 'primary');
  setEl('last-updated', fmtDate(data.timestamp));
  setEl('halted-badge', data.trading_halted ? '⛔ HALTED' : '');

  // Loss limit bar
  const pct = Math.min((Math.abs(data.daily_loss) / data.daily_loss_limit) * 100, 100);
  const fill = document.getElementById('loss-fill');
  if (fill) {
    fill.style.width = `${pct}%`;
    fill.className = `loss-fill ${pct < 50 ? 'safe' : pct < 80 ? 'warning' : 'danger'}`;
  }
  setInnerHTML('loss-text', `${fmtINR(Math.abs(data.daily_loss))} / ${fmtINR(data.daily_loss_limit)}`);

  // Instrument cards
  const grid = document.getElementById('instrument-grid');
  if (!grid) return;
  grid.innerHTML = '';

  (data.instruments || []).forEach(inst => {
    grid.appendChild(buildInstrumentCard(inst));
  });
}

function buildInstrumentCard(inst) {
  const card = document.createElement('div');
  const hasPosition = !!inst.open_trade;
  const signal = inst.open_trade?.signal;

  card.className = `instrument-card fade-in ${hasPosition ? (signal === 'BUY' ? 'has-buy' : 'has-sell') : ''}`;

  const pnlPts = inst.unrealized_pnl_pts;
  const pnlInr = inst.unrealized_pnl_inr;
  const pnlClass = pnlInr >= 0 ? 'profit' : 'loss';

  const grade = inst.open_trade?.grade;
  const gradeHtml = grade ? `<span class="grade-badge ${gradeCls(grade)}">${grade}</span>` : '';

  const signalHtml = hasPosition
    ? `<span class="signal-badge ${signal === 'BUY' ? 'buy' : 'sell'}">
        ${signal === 'BUY' ? '▲ BUY' : '▼ SELL'}
       </span> ${gradeHtml}`
    : `<span class="signal-badge none">NO POSITION</span>`;

  // Trailing SL percent distance from current price
  let slPct = 50;
  if (hasPosition && inst.trail_sl && inst.ltp) {
    const range = Math.abs(inst.open_trade.entry_price - inst.trail_sl);
    const dist = Math.abs(inst.ltp - inst.trail_sl);
    slPct = range > 0 ? Math.min((dist / range) * 100, 100) : 50;
  }

  card.innerHTML = `
    <div class="inst-header">
      <div>
        <div class="inst-name">${inst.instrument}</div>
        <div class="inst-price">${fmtPrice(inst.ltp)}</div>
        <div class="inst-change ${pnlInr >= 0 ? 'positive' : 'negative'}">
          ${hasPosition ? `${fmtPts(pnlPts)} (${fmtINR(pnlInr)})` : ''}
        </div>
      </div>
      <div style="text-align:right">
        ${signalHtml}
        <div style="margin-top:8px;font-family:var(--font-mono);font-size:0.7rem;color:var(--text-secondary);">
          ${inst.trades_today} trade${inst.trades_today !== 1 ? 's' : ''} today
        </div>
      </div>
    </div>

    <div class="inst-body">
      ${hasPosition ? `
        <div class="indicator-grid">
          <div class="indicator-item">
            <div class="indicator-label">Entry</div>
            <div class="indicator-value">${fmtPrice(inst.open_trade.entry_price)}</div>
          </div>
          <div class="indicator-item">
            <div class="indicator-label">MACD Hist</div>
            <div class="indicator-value ${inst.open_trade.macd_hist > 0 ? 'text-profit' : 'text-loss'}">${Number(inst.open_trade.macd_hist).toFixed(3)}</div>
          </div>
          <div class="indicator-item">
            <div class="indicator-label">RSI Smooth</div>
            <div class="indicator-value">${Number(inst.open_trade.rsi_smooth).toFixed(1)}</div>
          </div>
        </div>

        ${inst.trail_sl ? `
          <div class="sl-bar-wrap">
            <div class="sl-label-row">
              <span class="sl-label">Trail SL Distance</span>
              <span class="sl-val">${fmtPrice(inst.trail_sl)}</span>
            </div>
            <div class="sl-track">
              <div class="sl-fill" style="width:${slPct}%"></div>
            </div>
          </div>
        ` : ''}

        <div class="position-row ${signal === 'BUY' ? 'buy-pos' : 'sell-pos'} mt-8">
          <div>
            <div class="pos-label">Unrealized P&L</div>
            <div class="pos-val ${pnlClass}">${fmtINR(pnlInr)}</div>
          </div>
          <div>
            <div class="pos-label">ATR</div>
            <div class="pos-val neutral">${Number(inst.open_trade.atr || 0).toFixed(1)}</div>
          </div>
          <div>
            <div class="pos-label">Lot Size</div>
            <div class="pos-val neutral">${inst.open_trade.lot_size}</div>
          </div>
          <div>
            <div class="pos-label">Realized Today</div>
            <div class="pos-val ${inst.realized_pnl >= 0 ? 'profit' : 'loss'}">${fmtINR(inst.realized_pnl)}</div>
          </div>
        </div>
      ` : `
        <div class="position-row no-pos">
          <div class="pos-label" style="width:100%;text-align:center">
            Monitoring for signals... next scan ${getNextScanStr()}
          </div>
        </div>
      `}
    </div>
  `;

  return card;
}

// ── Toast Notifications ───────────────────────────────────────────────────────

function showSignalToast(trade) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const isBuy = trade.signal === 'BUY';
  const toast = document.createElement('div');
  toast.className = `toast ${isBuy ? 'buy' : 'sell'}`;
  toast.innerHTML = `
    <div class="toast-header">
      <span class="toast-signal">${isBuy ? '▲ BUY' : '▼ SELL'} — ${trade.instrument}</span>
      <span class="grade-badge ${gradeCls(trade.grade)}" style="margin-left:auto">${trade.grade}</span>
    </div>
    <div class="toast-body">
      Entry: ${fmtPrice(trade.entry_price)}<br>
      Trail SL: ${fmtPrice(trade.trail_sl)}<br>
      RSI: ${trade.rsi_smooth} | MACD: ${trade.macd_hist}
    </div>
  `;

  container.appendChild(toast);
  setTimeout(() => toast.remove(), 8000);
}

function showToastMessage(msg, type = 'neutral') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `<div class="toast-body">${msg}</div>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ── Countdown ────────────────────────────────────────────────────────────────

function scheduleNextScan() {
  const now = new Date();
  const mins = now.getMinutes();
  const nextMin = (Math.ceil((mins + 1) / 15) * 15) % 60;
  nextScanTime = new Date(now);
  nextScanTime.setMinutes(nextMin, 0, 0);
  if (nextScanTime <= now) nextScanTime.setHours(nextScanTime.getHours() + 1);

  // Schedule reload at next candle
  const delay = nextScanTime - now;
  setTimeout(() => {
    loadDashboard();
    scheduleNextScan();
  }, delay);
}

function updateCountdown() {
  if (!nextScanTime) return;
  const remaining = Math.max(0, Math.floor((nextScanTime - new Date()) / 1000));
  const m = Math.floor(remaining / 60);
  const s = remaining % 60;
  const el = document.getElementById('countdown');
  if (el) el.textContent = `${m}:${s.toString().padStart(2, '0')}`;
}

function getNextScanStr() {
  if (!nextScanTime) return '...';
  return nextScanTime.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function setEl(id, text, cls = null) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  if (cls) el.className = `stat-value ${cls}`;
}

function setInnerHTML(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

function formatLakh(n) {
  if (!n) return '0';
  if (n >= 10000000) return `${(n / 10000000).toFixed(2)}Cr`;
  if (n >= 100000) return `${(n / 100000).toFixed(2)}L`;
  return n.toLocaleString('en-IN');
}

function showLoading(show) {
  const el = document.getElementById('loading-overlay');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function showError(msg) {
  const el = document.getElementById('error-msg');
  if (el) { el.textContent = msg; el.style.display = 'block'; }
}
