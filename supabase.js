/**
 * Supabase JS client + API base URL configuration.
 * Reads from localStorage for user-configured settings.
 */

const CONFIG = {
  // Replace with your deployed backend URL
  API_BASE: localStorage.getItem('api_base') || 'https://macd-rsi-index-intra.onrender.com',
  REFRESH_INTERVAL: 15 * 60 * 1000, // 15 minutes
};

// ── API Helper ──────────────────────────────────────────────────────────────

async function apiGet(path, params = {}) {
  const url = new URL(`${CONFIG.API_BASE}${path}`);
  Object.entries(params).forEach(([k, v]) => v != null && url.searchParams.set(k, v));
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function apiPost(path, body = {}) {
  const res = await fetch(`${CONFIG.API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ── Formatters ──────────────────────────────────────────────────────────────

function fmtPrice(n) {
  if (n == null) return '—';
  return new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
}

function fmtINR(n) {
  if (n == null) return '—';
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : n > 0 ? '+' : '';
  return `${sign}₹${new Intl.NumberFormat('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(abs)}`;
}

function fmtPts(n) {
  if (n == null) return '—';
  const sign = n > 0 ? '+' : '';
  return `${sign}${Number(n).toFixed(2)} pts`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
}

function gradeCls(g) {
  if (g === 'A+') return 'aplus';
  if (g === 'A') return 'a';
  if (g === 'B+') return 'bplus';
  return '';
}

function statusBadge(status) {
  const map = {
    OPEN: 'badge-open',
    CLOSED: 'badge-closed',
    SL_HIT: 'badge-sl',
    SIGNAL: 'badge-signal',
    TP_HIT: 'badge-signal',
  };
  return `<span class="badge ${map[status] || 'badge-closed'}">${status || '—'}</span>`;
}

// ── Nav active state ─────────────────────────────────────────────────────────

function setNavActive() {
  const page = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-link').forEach(a => {
    a.classList.toggle('active', a.getAttribute('href') === page || (page === '' && a.getAttribute('href') === 'index.html'));
  });
}

document.addEventListener('DOMContentLoaded', setNavActive);
