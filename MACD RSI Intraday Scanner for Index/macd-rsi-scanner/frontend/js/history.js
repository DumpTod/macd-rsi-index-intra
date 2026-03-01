/**
 * history.js — Trade history page with filter, rescan, and export.
 */

let allTrades = [];
let filteredTrades = [];

document.addEventListener('DOMContentLoaded', () => {
  loadHistory();
  setupFilters();
});

// ── Load ──────────────────────────────────────────────────────────────────────

async function loadHistory() {
  try {
    showTableLoading(true);
    const params = getFilterParams();
    const res = await apiGet('/api/trades', params);
    allTrades = res.trades || [];
    filteredTrades = [...allTrades];
    renderTable(filteredTrades);
  } catch (e) {
    console.error(e);
    showTableError('Failed to load trade history.');
  } finally {
    showTableLoading(false);
  }
}

function getFilterParams() {
  return {
    instrument: document.getElementById('filter-inst')?.value || null,
    grade: document.getElementById('filter-grade')?.value || null,
    status: document.getElementById('filter-status')?.value || null,
    date_from: document.getElementById('filter-from')?.value || null,
    date_to: document.getElementById('filter-to')?.value || null,
  };
}

// ── Filters ───────────────────────────────────────────────────────────────────

function setupFilters() {
  ['filter-inst', 'filter-grade', 'filter-status', 'filter-from', 'filter-to'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', loadHistory);
  });
}

// ── Render ────────────────────────────────────────────────────────────────────

function renderTable(trades) {
  const tbody = document.getElementById('history-tbody');
  if (!tbody) return;

  if (!trades.length) {
    tbody.innerHTML = `<tr><td colspan="12">
      <div class="empty-state">
        <div class="empty-icon">📊</div>
        <div class="empty-text">No trades found matching your filters</div>
      </div>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = trades.map(t => {
    const pnl = t.pnl_rupees;
    const rowCls = pnl == null ? '' : pnl >= 0 ? 'profit-row' : 'loss-row';
    const isBuy = t.signal === 'BUY';

    return `
      <tr class="${rowCls}">
        <td class="text-mono" style="color:var(--text-secondary)">${fmtDate(t.entry_time)}</td>
        <td><strong>${t.instrument}</strong></td>
        <td>
          <span class="grade-badge ${gradeCls(t.grade)}">${t.grade}</span>
        </td>
        <td>
          <span class="signal-badge ${isBuy ? 'buy' : 'sell'}" style="font-size:0.65rem;padding:3px 8px">
            ${isBuy ? '▲ BUY' : '▼ SELL'}
          </span>
        </td>
        <td class="text-mono">${fmtPrice(t.entry_price)}</td>
        <td class="text-mono">${fmtPrice(t.exit_price)}</td>
        <td class="text-mono" style="color:var(--text-secondary)">${t.exit_type || '—'}</td>
        <td class="text-mono ${pnl >= 0 ? 'text-profit' : 'text-loss'}">${fmtPts(t.pnl_points)}</td>
        <td class="text-mono ${pnl >= 0 ? 'text-profit' : 'text-loss'}">${fmtINR(pnl)}</td>
        <td>${statusBadge(t.status)}</td>
        <td>
          ${t.status === 'OPEN' ? `<button class="btn btn-outline btn-sm" onclick="rescanTrade('${t.id}', this)">⟳ Rescan</button>` : '—'}
        </td>
      </tr>
    `;
  }).join('');

  // Update counter
  const el = document.getElementById('trade-count');
  if (el) el.textContent = `${trades.length} trade${trades.length !== 1 ? 's' : ''}`;
}

// ── Rescan ─────────────────────────────────────────────────────────────────────

async function rescanTrade(tradeId, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  try {
    const res = await apiPost('/api/trades/rescan', { trade_id: tradeId });
    showRescanResult(tradeId, res);
    await loadHistory();
  } catch (e) {
    alert('Rescan failed: ' + e.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '⟳ Rescan'; }
  }
}

async function rescanAll() {
  const btn = document.getElementById('rescan-all-btn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Rescanning...'; }
  try {
    const res = await apiPost('/api/trades/rescan-all');
    const results = res.results || [];
    const summary = results.map(r => `${r.instrument}: ${r.status}`).join('\n');
    alert(`Rescan complete:\n${summary || 'No open trades.'}`);
    await loadHistory();
  } catch (e) {
    alert('Rescan all failed: ' + e.message);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '⟳ Rescan All Open'; }
  }
}

function showRescanResult(tradeId, res) {
  const msgMap = {
    ENTRY_NOT_MET: '⚠️ Entry price not reached',
    SL_HIT: `🔴 SL Hit at ${fmtPrice(res.exit_price)} | PnL: ${fmtINR(res.pnl_rupees)}`,
    SIGNAL_EXIT: `🟢 Signal exit | PnL: ${fmtINR(res.pnl_rupees)}`,
    IN_PROFIT: `📈 Currently in profit at ${fmtPrice(res.current_price)}`,
    IN_LOSS: `📉 Currently in loss at ${fmtPrice(res.current_price)}`,
  };
  alert(msgMap[res.status] || `Status: ${res.status}`);
}

// ── Export ─────────────────────────────────────────────────────────────────────

function exportCSV() {
  if (!filteredTrades.length) { alert('No trades to export'); return; }

  const headers = ['Date', 'Instrument', 'Grade', 'Signal', 'Entry', 'Exit', 'Exit Type', 'PnL (pts)', 'PnL (₹)', 'Status'];
  const rows = filteredTrades.map(t => [
    fmtDate(t.entry_time), t.instrument, t.grade, t.signal,
    t.entry_price, t.exit_price, t.exit_type,
    t.pnl_points, t.pnl_rupees, t.status,
  ]);

  const csv = [headers, ...rows].map(r => r.map(v => `"${v ?? ''}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `trades_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function showTableLoading(show) {
  const el = document.getElementById('table-loading');
  if (el) el.style.display = show ? 'block' : 'none';
}

function showTableError(msg) {
  const tbody = document.getElementById('history-tbody');
  if (tbody) tbody.innerHTML = `<tr><td colspan="12" style="text-align:center;color:var(--loss);padding:40px">${msg}</td></tr>`;
}
