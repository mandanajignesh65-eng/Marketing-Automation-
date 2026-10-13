import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, info, switcher } from '../ui.js';

const SPANS = [['all', 'All time'], ['24', '24 months'], ['12', '12 months']];
const METRICS = {
  win_rate: ['Win rate', v => Math.round(v) + '%', 'closed'],
  avg_value: ['Median deal value', f.moneyShort, 'won'],
  median_days: ['Sales cycle', v => f.num(v) + ' d', 'won'],
  won_value: ['Closed-won value', f.moneyShort, 'won'],
};
const TIPS = {
  winRate: 'Out of every 100 deals that finished, how many we won. Open deals are not counted.',
  value: 'The middle won deal: half were bigger, half were smaller. The middle is used, not the average, so one very large deal cannot bend the number.',
  cycle: 'For won deals: the middle number of days from opening the deal to winning it.',
  coverage: 'How many won deals have the company’s industry written down. Below about 70%, treat every split on this page as a hint, not a fact.',
  chart: 'One bar for each group. The dashed line is the figure for all deals together. A bar above the line beats the average. Faded bars rest on too few deals to trust.',
  profile: 'The group that wins most often on each measure, among groups with at least 10 finished deals. Lift is how many times better it does than all deals together: 1.4× means 40% better.',
  low: 'Groups with at least 15 finished deals that win far less often than the rest. They take sales time and rarely pay it back.',
  matrix: 'Each box is one industry at one company size. The number is the win rate, and the small number is how many deals finished. Darker green wins more often. Empty boxes have too few deals.',
  years: 'Deals grouped by the year they were opened. It shows whether we are getting better at choosing who to sell to.',
  table: 'Every group with its full numbers. Grey numbers rest on too few deals to trust.',
  lift: 'Win rate of this group divided by the win rate of all deals. Above 1× is better than average.',
};
const pc = v => (v == null ? '—' : Math.round(v) + '%');
const lift = (r, base) => (r.win_rate == null || !base ? null : r.win_rate / base);
const liftText = x => (x == null ? '—' : x.toFixed(1) + '×');
const liftTone = x => (x == null ? 'ink3' : x >= 1.2 ? 'pos' : x < 0.6 ? 'neg' : 'ink2');
const muted = r => r.name === 'Not recorded' || r.name.startsWith('Other (');

// Upright bars with a dashed line at the all-deals figure. rows: [{ name, value, n, weak, off, target }]
function chart(rows, base, fmt) {
  const top = Math.max(...rows.map(r => r.value || 0), base || 0, 1) * 1.12;
  return html`<div style="position:relative;height:230px;margin-top:6px">
    ${base ? html`<div style="position:absolute;left:0;right:0;bottom:${base / top * 100}%;border-top:1.5px dashed var(--ink3);z-index:1"></div>
      <span class="tiny muted" style="position:absolute;right:0;bottom:${base / top * 100}%;transform:translateY(-3px);background:var(--surface);padding:0 4px;z-index:2">All deals ${fmt(base)}</span>` : ''}
    <div style="position:absolute;inset:0;display:flex;align-items:flex-end;gap:14px;padding-right:96px">
      ${rows.map(r => html`<div class="stack" style="flex:1;min-width:0;height:100%;justify-content:flex-end;align-items:center;gap:4px" title="${r.name}: ${r.value == null ? 'no figure' : fmt(r.value)} · ${f.num(r.n)} deals">
        <span class="small ${r.weak ? 'faint' : 'semi'}">${r.value == null ? '—' : fmt(r.value)}</span>
        <div style="width:100%;max-width:64px;height:${r.value ? Math.max(r.value / top * 100, 1) : 0}%;border-radius:6px 6px 1px 1px;opacity:${r.weak ? 0.35 : 1};
          background:${r.off ? 'var(--ink3)' : base && r.value >= base * 1.2 ? 'var(--pos)' : base && r.value < base * 0.6 ? 'var(--neg)' : 'var(--ink)'}"></div></div>`)}
    </div></div>
  <div style="display:flex;gap:14px;padding-right:96px;margin-top:8px">${rows.map(r => html`<div class="stack" style="flex:1;min-width:0;align-items:center;gap:1px">
    <span class="tiny ${r.off ? 'muted' : 'medium'} clip" style="max-width:100%" title="${r.name}">${r.name}</span><span class="micro faint">n = ${f.num(r.n)}</span></div>`)}</div>`;
}

export default {
  uses: {},
  load: ctx => ctx.api.get('icp', { span: ctx.ui().span || 'all' }),

  render(d, ctx) {
    const ui = ctx.ui(), t = d.total, base = t.win_rate || 0;
    const dim = d.dimensions[ui.dim] ? ui.dim : 'industry';
    const metric = METRICS[ui.metric] ? ui.metric : 'win_rate';
    const [mLabel, mFmt, mFloor] = METRICS[metric];
    const coverage = d.won ? d.recorded.industry / d.won * 100 : 0;
    const kpi = (value, label, tip, sub = '', end = false) => html`<div class="card kpi" style="padding:16px 18px"><span class="kpi-v md">${value}</span>
      <span class="row eyebrow" style="gap:7px">${label}${info(tip, { end })}</span><span class="kpi-d faint">${sub}</span></div>`;
    const floor = r => (mFloor === 'closed' ? r.closed >= d.min_closed : r.won >= d.min_won);
    const groups = d.tables[dim];
    const shown = [...groups.filter(r => !muted(r)).slice(0, 9), ...groups.filter(r => r.name === 'Not recorded')];
    const bars = shown.map(r => ({ name: r.name, value: r[metric], n: r.deals, weak: !floor(r), off: muted(r), target: r.target }));
    const low = d.answers.avoid;
    const top = Math.max(...d.matrix.flatMap(m => m.cells.map(c => (c.closed >= 5 ? c.win_rate || 0 : 0))), 1);
    const yTop = Math.max(...d.years.map(y => y.win_rate || 0), 1) * 1.15;
    const cols = 'minmax(0,1.7fr) 60px 52px 52px 52px minmax(110px,1fr) 64px 96px 96px 70px';

    return html`
    ${pageHead(`Built from ${f.num(t.deals)} CRM deals · ${f.num(t.closed)} closed · ${f.num(t.open)} open`, 'Ideal customer profile', switcher(SPANS.map(([arg, label]) => ({ arg, label, on: d.span === arg })), 'span'))}
    ${t.deals ? html`
    <div class="grid" style="grid-template-columns:repeat(5,minmax(0,1fr))">
      ${kpi(pc(t.win_rate), 'Win rate', TIPS.winRate, `${f.num(t.won)} won of ${f.num(t.closed)} closed`)}
      ${kpi(f.orDash(t.avg_value, f.moneyShort), 'Median deal value', TIPS.value, t.largest ? `largest ${f.moneyShort(t.largest)}` : '')}
      ${kpi(t.median_days == null ? '—' : `${f.num(t.median_days)} days`, 'Sales cycle', TIPS.cycle, 'median, open to won')}
      ${kpi(f.moneyShort(t.won_value), 'Closed-won value', 'The total value of every deal we won in this period.', `${f.num(t.won)} deals`)}
      <div class="card kpi" style="padding:16px 18px"><span class="kpi-v md" style="color:var(--${coverage >= 70 ? 'pos' : coverage >= 40 ? 'warn' : 'neg'})">${pc(coverage)}</span>
        <span class="row eyebrow" style="gap:7px">Data coverage${info(TIPS.coverage, { end: true })}</span>
        <div class="track" style="height:6px;border-radius:3px;margin-top:8px"><div class="fill" style="width:${coverage}%;background:var(--${coverage >= 70 ? 'pos' : coverage >= 40 ? 'warn' : 'neg'})"></div></div>
        <span class="kpi-d faint">${f.num(d.recorded.industry)} of ${f.num(d.won)} won deals labelled</span></div>
    </div>

    <div class="card" style="padding:18px 24px 18px">
      <div class="baseline" style="gap:16px;flex-wrap:wrap"><span class="row" style="gap:8px"><span class="title">${mLabel} by ${d.dimensions[dim].toLowerCase()}</span>${info(TIPS.chart)}</span>
        <div class="row" style="gap:10px;flex-wrap:wrap">${switcher(Object.entries(METRICS).map(([arg, v]) => ({ arg: `metric=${arg}`, label: v[0], on: metric === arg })), 'set')}
          ${switcher(Object.entries(d.dimensions).map(([arg, label]) => ({ arg: `dim=${arg}`, label, on: dim === arg })), 'set')}</div></div>
      ${chart(bars, metric === 'won_value' ? null : t[metric], mFmt)}
    </div>

    <div class="grid start" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
      <div class="card clipped" style="--cols:120px minmax(0,1fr) 70px 60px 70px">
        <div class="row" style="gap:8px;padding:16px 16px 10px"><span class="title">Best-fit profile</span>${info(TIPS.profile)}</div>
        <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Attribute</span><span style="text-align:left">Strongest segment</span><span>Win rate</span><span class="row" style="gap:5px;justify-content:flex-end">Lift${info(TIPS.lift, { end: true })}</span><span>Closed</span></div>
        ${d.fit.map(r => html`<div class="trow right"><span class="muted" style="text-align:left">${r.label}</span><span class="semi clip" style="text-align:left" title="${r.name}">${r.name}</span>
          <span class="medium">${pc(r.win_rate)}</span><span style="color:var(--${liftTone(lift(r, base))})">${liftText(lift(r, base))}</span><span class="${r.closed < 30 ? 'faint' : 'muted'}">${f.num(r.closed)}</span></div>`)}
        ${d.fit.length ? '' : html`<div class="small muted" style="padding:14px 16px">Too few closed deals carry these details to name a profile.</div>`}
      </div>
      <div class="card clipped" style="--cols:120px minmax(0,1fr) 70px 60px 70px">
        <div class="row" style="gap:8px;padding:16px 16px 10px"><span class="title">Low-fit segments</span>${info(TIPS.low)}</div>
        <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Attribute</span><span style="text-align:left">Segment</span><span>Win rate</span><span>Lift</span><span>Closed</span></div>
        ${low.map(r => html`<div class="trow right"><span class="muted" style="text-align:left">${r.dim}</span><span class="semi clip" style="text-align:left" title="${r.name}">${r.name}</span>
          <span class="medium" style="color:var(--neg)">${pc(r.win_rate)}</span><span style="color:var(--neg)">${liftText(lift(r, base))}</span><span class="muted">${f.num(r.closed)}</span></div>`)}
        ${low.length ? '' : html`<div class="small muted" style="padding:14px 16px">No segment with 15 or more closed deals falls far below the average.</div>`}
      </div>
    </div>

    <div class="grid start" style="grid-template-columns:minmax(0,1.5fr) minmax(0,1fr)">
      <div class="card" style="padding:18px 24px 20px">
        <div class="row" style="gap:8px;margin-bottom:14px"><span class="title">Win rate: industry × company size</span>${info(TIPS.matrix)}</div>
        ${d.matrix.length ? html`<div style="display:grid;grid-template-columns:minmax(120px,1.2fr) repeat(${d.sizes.length},minmax(0,1fr));gap:6px;align-items:stretch">
          <span></span>${d.sizes.map(s => html`<span class="tiny muted" style="text-align:center;padding-bottom:2px">${s}</span>`)}
          ${d.matrix.map(m => html`<span class="row small medium" style="gap:6px;min-width:0"><span class="clip" title="${m.name}">${m.name}</span>${m.target ? html`<span class="pill sm" style="flex:none">target</span>` : ''}</span>
            ${m.cells.map(c => { const ok = c.closed >= 5, strength = ok ? Math.round((c.win_rate || 0) / top * 78) : 0; return html`<div class="stack" title="${m.name}, ${c.size}: ${f.num(c.won)} won of ${f.num(c.closed)} closed"
              style="align-items:center;justify-content:center;gap:0;height:54px;border-radius:8px;background:${ok ? `color-mix(in oklch, var(--pos) ${strength}%, var(--surface2))` : 'var(--surface2)'};color:${strength > 48 ? '#fff' : 'var(--ink)'}">
              <span class="${ok ? 'semi' : 'faint'}" style="font-size:15px">${ok ? pc(c.win_rate) : '·'}</span><span class="micro" style="opacity:0.75">${c.closed ? `${f.num(c.closed)} closed` : ''}</span></div>`; })}`)}
        </div>` : html`<div class="small muted">Too few deals have an industry recorded to draw this.</div>`}
      </div>
      <div class="card" style="padding:18px 24px 18px">
        <div class="row" style="gap:8px"><span class="title">Win rate by year opened</span>${info(TIPS.years)}</div>
        <div style="height:190px;display:flex;align-items:flex-end;gap:14px;margin-top:10px">
          ${d.years.map(y => html`<div class="stack" style="flex:1;height:100%;justify-content:flex-end;align-items:center;gap:4px" title="${y.name}: ${f.num(y.won)} won of ${f.num(y.closed)} closed">
            <span class="small semi">${pc(y.win_rate)}</span><div style="width:100%;max-width:56px;height:${(y.win_rate || 0) / yTop * 100}%;min-height:2px;border-radius:6px 6px 1px 1px;background:var(--ink)"></div></div>`)}
        </div>
        <div style="display:flex;gap:14px;margin-top:8px">${d.years.map(y => html`<div class="stack" style="flex:1;align-items:center;gap:1px"><span class="tiny medium">${y.name}</span><span class="micro faint">${f.num(y.closed)} closed</span></div>`)}</div>
      </div>
    </div>

    <div class="card clipped" style="--cols:${cols}">
      <div class="baseline" style="padding:16px 16px 10px;gap:16px;flex-wrap:wrap"><span class="row" style="gap:8px"><span class="title">Segments by ${d.dimensions[dim].toLowerCase()}</span>${info(TIPS.table)}</span>
        ${switcher(Object.entries(d.dimensions).map(([arg, label]) => ({ arg: `dim=${arg}`, label, on: dim === arg })), 'set')}</div>
      <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">${d.dimensions[dim]}</span><span>Deals</span><span>Won</span><span>Lost</span><span>Open</span>
        <span style="text-align:left">Win rate</span><span>Lift</span><span>Median value</span><span>Won value</span><span>Cycle</span></div>
      ${groups.map(r => { const enough = r.closed >= d.min_closed, x = lift(r, base), max = Math.max(...groups.map(g => g.win_rate || 0), 1); return html`<div class="trow right">
        <span class="row" style="gap:8px;text-align:left;min-width:0"><span class="clip ${muted(r) ? 'muted' : 'medium'}" title="${r.name}">${r.name}</span>${r.target ? html`<span class="pill sm" style="flex:none">target</span>` : ''}</span>
        <span class="medium">${f.num(r.deals)}</span><span>${f.num(r.won)}</span><span class="muted">${f.num(r.lost)}</span><span class="faint">${f.num(r.open)}</span>
        <div class="row" style="gap:8px"><div class="track" style="flex:1;height:8px;border-radius:4px"><div class="fill" style="width:${r.win_rate ? Math.max(r.win_rate / max * 100, 2) : 0}%;opacity:${enough ? 1 : 0.35};background:var(--${enough ? liftTone(x) === 'ink2' ? 'ink' : liftTone(x) : 'ink3'})"></div></div>
          <span class="${enough ? 'medium' : 'faint'}" style="width:38px;text-align:right">${pc(r.win_rate)}</span></div>
        <span class="${enough ? '' : 'faint'}" style="${enough ? `color:var(--${liftTone(x)})` : ''}">${liftText(x)}</span>
        <span class="${r.won >= d.min_won ? '' : 'faint'}">${f.orDash(r.avg_value, f.moneyShort)}</span><span class="muted">${r.won_value ? f.moneyShort(r.won_value) : '—'}</span>
        <span class="${r.won >= d.min_won ? 'muted' : 'faint'}">${r.median_days == null ? '—' : f.num(r.median_days) + ' d'}</span></div>`; })}
      <div class="trow right tfoot"><span style="text-align:left">All deals</span><span>${f.num(t.deals)}</span><span>${f.num(t.won)}</span><span>${f.num(t.lost)}</span><span>${f.num(t.open)}</span>
        <span style="text-align:right">${pc(base)}</span><span>1.0×</span><span>${f.orDash(t.avg_value, f.moneyShort)}</span><span>${f.moneyShort(t.won_value)}</span><span>${t.median_days == null ? '—' : f.num(t.median_days) + ' d'}</span></div>
    </div>` : html`<div class="card pad small muted">No deals in this period.</div>`}`;
  },

  actions: {
    set(ctx, d) { const at = d.arg.indexOf('='); ctx.ui()[d.arg.slice(0, at)] = d.arg.slice(at + 1) || null; ctx.render(); },
    span(ctx, d) { ctx.ui().span = d.arg; ctx.reload(); },
  },
};
