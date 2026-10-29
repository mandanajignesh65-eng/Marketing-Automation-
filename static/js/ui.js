// Small shared pieces of markup.
import { html } from './html.js';
import * as f from './format.js';

export const sq = (color, size = 8, radius = 2) =>
  html`<span class="sq" style="width:${size}px;height:${size}px;border-radius:${radius}px;background:${color}"></span>`;

export const dot = color => html`<span class="dot" style="background:${color}"></span>`;

// Meridian's Qualified: the score reaches the threshold, or the lead was marked by hand (scoring.qualified_sql).
export const qualifiedPill = yes => html`<span class="pill">${dot(yes ? 'var(--pos)' : 'var(--ink3)')}${yes ? 'Qualified' : 'Not qualified'}</span>`;

export const avatar = (initials, size = 28) =>
  html`<div class="avatar" style="width:${size}px;height:${size}px;font-size:${size >= 40 ? 14 : 10}px">${initials}</div>`;

// items: [{ label, on, arg }]
export const segmented = (items, act, pad = 12) => html`<div class="seg">${items.map(i =>
  html`<div class="${i.on ? 'on' : ''}" data-act="${act}" data-arg="${i.arg}" style="padding:4px ${pad}px">${i.label}</div>`)}</div>`;

// The same control with an optional colour square per choice, for switching what a chart shows. options: [{ label, on, arg, color }]
// Leads, Quality and Ideal customer share one place in the sidebar; this row moves between them.
export const leadsSwitch = current => html`<div style="display:flex;margin-bottom:-8px">${segmented([['leads', 'All leads'], ['quality', 'Quality'], ['icp', 'Ideal customer']]
  .map(([arg, label]) => ({ arg, label, on: arg === current })), 'openScreen')}</div>`;
// What a channel is made of: one row per lead source. Shown on the channel pages and on Leads when a channel group is picked.
export const sourcesCard = inside => (inside ? html`<div class="card clipped" style="--cols:minmax(0,2fr) 80px 80px 100px 120px">
  <div class="baseline" style="padding:16px 16px 12px"><span class="title">Sources inside</span><span class="small muted">One row per lead source</span></div>
  <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Source</span><span>Leads</span><span>Qualified</span><span>Deals started</span><span>Value of new deals</span></div>
  ${inside.length ? inside.map(r => html`<div class="trow right"><span class="clip medium" style="text-align:left" title="${r.source}">${r.source}</span>
    <span class="medium">${f.num(r.leads)}</span><span>${f.num(r.qualified)}</span><span>${f.num(r.deals)}</span><span>${r.pipeline ? f.moneyShort(r.pipeline) : '—'}</span></div>`)
    : html`<div class="small muted" style="padding:12px 16px 16px">No leads from this channel in the period.</div>`}
</div>` : '');
export const switcher = (options, act) => html`<div class="seg wrap">${options.map(o =>
  html`<div class="${o.on ? 'on' : ''}" data-act="${act}" data-arg="${o.arg}">${o.color ? html`<span class="sq" style="width:9px;height:9px;border-radius:3px;background:${o.color}"></span>` : ''}${o.label}</div>`)}</div>`;

export const toggle = (on, act, arg = '') =>
  html`<div class="switch ${on ? 'on' : ''}" data-act="${act}" data-arg="${arg}" role="switch" aria-checked="${on ? 'true' : 'false'}"><i></i></div>`;

export const stepper = (value, act, arg = '', width = 30) => html`<div class="stepper">
  <span data-act="${act}" data-arg="${arg}" data-step="-1">−</span><b style="width:${width}px">${value}</b><span data-act="${act}" data-arg="${arg}" data-step="1">+</span>
</div>`;

export const bar = (pctWidth, color = 'var(--ink)', height = 6) => html`<div class="track" style="height:${height}px;border-radius:${height / 2}px">
  <div class="fill" style="width:${Math.max(0, Math.min(100, pctWidth))}%;background:${color}"></div></div>`;

// "▲ 9.1% vs 744" under a KPI. d = { value, prev, pct }
export function deltaLine(d, { mode = 'up', fmt = f.num, show = true, short = false } = {}) {
  if (!show || d.pct == null) return '';
  return html`<div class="kpi-d" style="color:${f.tone(d.pct, mode)}">${(short ? f.arrowShort : f.arrow)(d.pct)} <span class="faint">vs ${fmt(d.prev)}</span></div>`;
}

// Screens used to hang a small "i" with an explanation on most figures. They are gone: a figure that needs explaining gets a clearer name instead.
export const info = () => '';

export const pageHead = (eyebrow, title, right = '') => html`<div class="page-head">
  <div class="stack" style="gap:6px"><div class="eyebrow">${eyebrow}</div><h1 class="h1">${title}</h1></div>${right}</div>`;

// Polyline chart in a 300x100 box that stretches to its container. lines: [{ points, color, width, dash }]
export const lines = list => html`<svg class="lines" viewBox="0 0 300 100" preserveAspectRatio="none">${list.map(l =>
  html`<polyline points="${l.points}" style="stroke:${l.color};stroke-width:${l.width || 1.5};stroke-dasharray:${l.dash || 'none'}"></polyline>`)}</svg>`;

export const menu = (items, act, { right = false } = {}) => html`<div class="menu ${right ? 'right-edge' : ''}" data-menu>${items.map(i =>
  i.heading ? html`<div class="menu-label">${i.heading}</div>`
    : html`<div class="menu-item ${i.on ? 'on' : ''}" data-act="${act}" data-arg="${i.arg}">${i.color ? sq(i.color) : ''}${i.label}</div>`)}</div>`;
