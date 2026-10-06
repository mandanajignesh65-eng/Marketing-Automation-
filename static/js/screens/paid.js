import { html } from '../html.js';
import * as f from '../format.js';
import { segmented, pageHead, lines, dot } from '../ui.js';

const COLS = 'minmax(0,2.3fr) 76px repeat(6,minmax(0,0.8fr))';
const metrics = r => html`<span class="medium">${f.money(r.spend)}</span><span class="muted">${f.num(r.impressions)}</span><span>${f.num(r.clicks)}</span>
  <span class="muted">${r.impressions ? f.pct(r.clicks / r.impressions * 100) : '—'}</span><span class="medium">${f.num(r.leads)}</span><span>${r.leads ? f.money2(r.spend / r.leads) : '—'}</span>`;

function pacing(p, month) {
  if (!p.plan) return html`<div class="card pad stack" style="gap:10px"><span class="title">Budget pacing</span><span class="small muted">${p.note}</span></div>`;
  const top = Math.max(p.plan, p.projected) * 1.1;
  const y = v => (100 - v / top * 100).toFixed(2);
  const x = day => (day / p.days_in_month * 300).toFixed(1);
  const above = p.projected >= p.plan;  // the higher line carries its label above, the lower one below, so they never collide
  const chart = lines([
    { points: `0,100 300,${y(p.plan)}`, color: 'var(--ink3)', dash: '3 3', width: 1 },
    { points: '0,100 ' + p.cumulative.map((v, i) => `${x(i + 1)},${y(v)}`).join(' '), color: 'var(--ink)', width: 1.75 },
    { points: `${x(p.day)},${y(p.spent)} 300,${y(p.projected)}`, color: 'var(--ink2)', dash: '2 3', width: 1.25 },
  ]);
  return html`<div class="card pad stack" style="gap:14px">
    <div class="baseline"><span class="title">Budget pacing</span><span class="small medium" style="color:var(--${p.tone})">${p.status}</span></div>
    <div class="stack" style="gap:2px"><div class="row" style="align-items:baseline;gap:6px"><span style="font-size:30px;font-weight:600;letter-spacing:-0.025em">${f.money(p.spent)}</span><span class="faint">of ${f.money(p.plan)}</span></div>
      <span class="small muted">${(p.spent / p.plan * 100).toFixed(1)}% of plan spent · ${Math.round(p.elapsed_pct)}% of month elapsed</span></div>
    <div style="position:relative;height:130px;margin:8px 0 2px">
      ${chart}
      <div style="position:absolute;left:${p.elapsed_pct}%;top:0;bottom:0;width:1px;background:var(--line)"></div>
      <span class="tiny faint" style="position:absolute;right:0;top:${y(p.plan)}%;transform:translateY(${above ? '30%' : '-130%'})">Plan ${f.money(p.plan)}</span>
      <span class="tiny muted" style="position:absolute;right:0;top:${y(p.projected)}%;transform:translateY(${above ? '-130%' : '30%'})">Projected ${f.money(p.projected)}</span>
    </div>
    <div class="micro faint" style="position:relative;height:13px"><span style="position:absolute;left:0">1 ${month}</span>
      <span style="position:absolute;left:${p.elapsed_pct}%;transform:translateX(-50%)">Today</span><span style="position:absolute;right:0">${p.days_in_month} ${month}</span></div>
    <div class="small muted pretty" style="padding-top:12px;border-top:1px solid var(--line2)">${p.note}</div>
  </div>`;
}

export default {
  uses: { range: true },
  load: ctx => ctx.api.get('paid', ctx.rangeParams()),

  render(d, ctx) {
    const ui = ctx.ui();
    const platform = d.platforms.find(p => p.id === ui.tab) || d.platforms.find(p => p.id === 'li') || d.platforms[0];
    const camps = platform.campaigns;
    const idx = Math.min(ui.camp || 0, Math.max(0, camps.length - 1));
    const camp = camps[idx];
    const total = camps.reduce((a, c) => ({ spend: a.spend + c.spend, impressions: a.impressions + c.impressions, clicks: a.clicks + c.clicks, leads: a.leads + c.leads }),
      { spend: 0, impressions: 0, clicks: 0, leads: 0 });
    const creatives = camp ? camp.creatives : [];
    const best = Math.min(...creatives.filter(c => c.leads).map(c => c.spend / c.leads));
    const tabs = d.platforms.map(p => ({ arg: p.id, label: p.label, on: p.id === platform.id }));

    return html`
    ${pageHead(d.sub, 'Paid ads', segmented(tabs, 'tab', 18))}
    <div class="grid start" style="grid-template-columns:minmax(0,1fr) 336px">
      <div class="card clipped" style="--cols:${COLS}">
        <div class="thead right"><span style="text-align:left">Campaign</span><span style="text-align:left">Status</span><span>Spend</span><span>Impressions</span><span>Clicks</span><span>CTR</span><span>Leads</span><span>Per lead</span></div>
        ${camps.map((c, i) => html`<div class="trow right ${i ? '' : 'first'} ${i === idx ? 'sel' : ''}" style="padding:12px 16px" data-act="camp" data-arg="${i}">
          <span class="clip" style="text-align:left;font-weight:${i === idx ? 600 : 500}">${c.name}</span>
          <span class="row small muted" style="gap:6px">${dot(c.status === 'Active' ? 'var(--pos)' : 'var(--ink3)')}${c.status}</span>${metrics(c)}</div>`)}
        ${camps.length ? html`<div class="trow right tfoot" style="padding:12px 16px"><span style="text-align:left">Total</span><span></span>${metrics(total)}</div>`
          : html`<div class="small muted" style="padding:18px 16px">No campaigns synced for ${platform.label} yet.</div>`}
      </div>
      ${pacing(platform.pacing, d.month)}
    </div>
    ${camp ? html`
    <div class="baseline" style="margin-top:10px"><span class="title">Creatives in “${camp.name}”</span><span class="small faint">Pick a campaign above to drill in</span></div>
    <div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
      ${creatives.map(c => html`<div class="card clipped stack">
        <div style="aspect-ratio:1.91;background:repeating-linear-gradient(135deg, var(--track) 0 6px, var(--surface2) 6px 12px);display:grid;place-items:center;position:relative">
          <span class="tiny muted" style="font-family:ui-monospace,Menlo,monospace;background:var(--surface);padding:3px 8px;border-radius:5px">ad creative · 1200 × 628</span>
          ${c.leads && c.spend / c.leads === best && creatives.length > 1 ? html`<span class="tiny semi" style="position:absolute;top:10px;left:10px;padding:3px 8px;border-radius:999px;background:var(--surface);color:var(--pos)">Lowest cost per lead</span>` : ''}
        </div>
        <div class="stack" style="padding:14px 16px 16px;gap:12px">
          <div class="stack" style="gap:1px"><span class="semi">${c.headline}</span><span class="small muted">${c.format}</span></div>
          <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px">
            ${[[f.money(c.spend), 'Spend'], [c.impressions ? f.pct(c.clicks / c.impressions * 100) : '—', 'CTR'], [f.num(c.leads), 'Leads'], [c.leads ? f.money2(c.spend / c.leads) : '—', 'Per lead']]
              .map(([v, l]) => html`<div class="stack"><span class="medium">${v}</span><span class="tiny faint">${l}</span></div>`)}
          </div>
        </div>
      </div>`)}
    </div>` : ''}`;
  },

  actions: {
    tab(ctx, d) { Object.assign(ctx.ui(), { tab: d.arg, camp: 0 }); ctx.render(); },
    camp(ctx, d) { ctx.ui().camp = Number(d.arg); ctx.render(); },
  },
};
