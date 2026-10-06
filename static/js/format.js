// Number and delta formatting, matching the design's conventions.

// The currency comes from the server (see meridian/money.py): symbol, locale for digit grouping,
// and units as [threshold, suffix, decimals] for compact figures.
let cur = { symbol: '$', locale: 'en-US', units: [[1e9, 'B', 2], [1e6, 'M', 2], [1e3, 'k', 1]] };
export function setCurrency(c) { if (c) cur = c; }
export const symbol = () => cur.symbol;

export const num = n => Math.round(n).toLocaleString(cur.locale);
export const money = n => cur.symbol + Math.round(n).toLocaleString(cur.locale);
export const money2 = n => cur.symbol + n.toLocaleString(cur.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const moneyAuto = n => (n < 100 ? money2(n) : money(n));
// ₹48.6K, ₹18.6L, ₹1.86Cr (or $48.6k, $1.86M): compact money for headline figures
export function moneyShort(n) {
  for (const [threshold, suffix, decimals] of cur.units) {
    if (Math.abs(n) >= threshold) {
      const v = n / threshold;
      return cur.symbol + (v >= 100 ? Math.round(v) : v.toFixed(decimals)) + suffix;
    }
  }
  return money(n);
}
export const big = n => (n >= 1e6 ? (n / 1e6).toFixed(2) + 'M' : num(n));
export const pct = r => (r < 10 ? r.toFixed(2) : r.toFixed(1)) + '%';
export const arrow = p => (p >= 0 ? '▲ ' : '▼ ') + Math.abs(p).toFixed(1).replace(/\.0$/, '') + '%';
// Whole numbers from 10% up, for tight spaces: ▼ 20%, ▲ 9.1%
export const arrowShort = p => (p >= 0 ? '▲ ' : '▼ ') + Math.abs(p).toFixed(Math.abs(p) >= 9.95 ? 0 : 1).replace(/\.0$/, '') + '%';
export const orDash = (v, f) => (v == null || Number.isNaN(v) ? '—' : f(v));

// Colour for a change: 'up' means an increase is good, 'down' means a decrease is good.
export function tone(p, mode = 'up') {
  if (mode === 'neutral' || p == null) return 'var(--ink2)';
  return (p >= 0) === (mode === 'up') ? 'var(--pos)' : 'var(--neg)';
}

export const tv = t => `var(--${t})`;

// A round axis maximum and step for three gridline intervals.
export function axis(max, steps = 3) {
  const rough = Math.max(max, 1) / steps;
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  const step = [1, 2, 2.5, 4, 5, 8, 10].map(m => m * mag).find(s => s >= rough);
  return { step, max: step * steps, ticks: Array.from({ length: steps + 1 }, (_, i) => i * step) };
}
