import { html } from '../html.js';
import * as f from '../format.js';
import { sq, deltaLine, switcher, avatar } from '../ui.js';


// only: a channel id to show by itself, or null for every channel stacked.
function chart(d, ctx, only) {
  const order = [...ctx.app.shell.channels, ctx.channel('unmapped')].filter(c => !only || c.id === only);
  const count = x => (only ? (x.segs.find(g => g.id === only) || { n: 0 }).n : x.total);
  const ax = f.axis(Math.max(...d.chart.map(count), 1));
  const every = d.chart.length <= 10;
  const label = (x, i) => (x.partial ? 'Today' : i === 0 ? `${x.day} ${x.month}` : every || x.day % 7 === 0 ? x.day : '');
  return html`<div class="stack" style="flex:1;min-width:0;gap:6px">
    <div style="position:relative;height:216px">
      ${ax.ticks.map(t => html`<div class="row" style="position:absolute;left:0;right:0;bottom:${t / ax.max * 100}%;gap:8px">
        <span class="micro faint right" style="width:18px;transform:translateY(50%)">${t}</span><div style="flex:1;height:1px;background:var(--grid)"></div></div>`)}
      <div style="position:absolute;left:26px;right:0;top:0;bottom:0;display:flex;align-items:flex-end;gap:4px">
        ${d.chart.map(x => html`<div title="${x.day} ${x.month} · ${count(x)} leads${x.partial ? ' (so far)' : ''}"
          style="flex:1;height:${count(x) / ax.max * 100}%;display:flex;flex-direction:column-reverse;gap:1px;opacity:${x.partial ? 0.45 : 1};border-radius:3px 3px 1px 1px;overflow:hidden">
          ${order.map(c => { const s = x.segs.find(g => g.id === c.id); return s ? html`<div style="height:${s.n / count(x) * 100}%;background:${c.color};flex:none"></div>` : ''; })}
        </div>`)}
      </div>
    </div>
    <div style="display:flex;gap:4px;margin-left:26px">${d.chart.map((x, i) => html`<div class="micro faint nowrap" style="flex:1;text-align:center">${label(x, i)}</div>`)}</div>
  </div>`;
}

function legend(d, ctx) {
  const rows = Object.entries(d.by_channel).map(([id, n]) => ({ c: ctx.channel(id), id, n })).sort((x, y) => y.n - x.n);
  const all = rows.reduce((t, r) => t + r.n, 0);
  return html`<div class="stack" style="width:210px;flex:none;gap:5px">
    <div class="between tiny faint medium" style="margin-bottom:2px"><span>By channel</span><span>${f.num(all)}</span></div>
    ${rows.map(r => html`<div class="row small ${r.id === 'unmapped' ? '' : 'menu-item'}" style="gap:8px;padding:1px 4px;margin:0 -4px;font-size:12px" ${r.id === 'unmapped' ? '' : html`data-act="openChannel" data-arg="${r.id}"`}>
      ${sq(r.c.color)}<span style="flex:1" class="nowrap">${r.id === 'unmapped' ? 'Unattributed' : r.c.name}</span><span class="medium">${f.num(r.n)}</span><span class="faint" style="width:44px;text-align:right">${all ? Math.round(r.n / all * 100) + '%' : ''}</span></div>`)}
    ${rows.length ? '' : html`<span class="small muted">No leads in this period yet.</span>`}
  </div>`;
}

export default {
  uses: { range: true, compare: true },
  load: ctx => ctx.api.get('overview', ctx.rangeParams()),

  render(d, ctx) {
    const show = ctx.app.compare;
    const k = d.kpis, t = d.team;
    const kpis = [
      ['Leads', f.num(d.leads.value), deltaLine(d.leads, { show, short: true }), 'leads'],
      ['Qualified leads', f.num(k.qualified.value), deltaLine(k.qualified, { show, short: true }), 'quality'],
      ['Deals started', f.num(d.deals.value), deltaLine(d.deals, { show, short: true }), 'funnel'],
      ['Deals won', f.num(d.won.value), deltaLine(d.won, { show, short: true }), 'funnel'],
      ['Value of new deals', k.pipeline.value ? f.moneyShort(k.pipeline.value) : '—', deltaLine(k.pipeline, { show, short: true, fmt: f.moneyShort }), 'funnel'],
    ];
    // The daily chart shows every channel stacked, or just the one picked with the buttons above it.
    const present = Object.keys(d.by_channel).filter(id => id !== 'unmapped').map(id => ctx.channel(id)).sort((a, b) => d.by_channel[b.id] - d.by_channel[a.id]);
    const only = present.some(c => c.id === ctx.ui().only) ? ctx.ui().only : null;
    const TO = { organic: 'web', outbound: 'outbound', paid: 'paid' };
    const cols = 'minmax(0,1fr) 72px 80px 64px 64px 80px';
    const n = v => (v ? f.num(v) : html`<span class="faint">—</span>`);
    return html`
    <div class="page-head"><div class="stack" style="gap:6px"><div class="eyebrow">${d.date_line}</div><h1 class="h1">Overview</h1></div></div>

    <div class="grid" style="grid-template-columns:repeat(5,minmax(0,1fr))">
      ${kpis.map(([label, value, change, to]) => html`<a class="card kpi" href="#/${to}" style="color:inherit;text-decoration:none"><div class="kpi-v">${value}</div>
        <div class="eyebrow">${label}</div>${change}</a>`)}
    </div>

    <div class="grid" style="grid-template-columns:${t.demo ? 'minmax(0,1fr)' : 'minmax(0,1fr) 336px'}">
      <div class="card stack" style="padding:18px 20px 16px;gap:16px">
        <div class="baseline" style="gap:16px;flex-wrap:wrap"><span class="title">${only ? `Leads from ${ctx.channel(only).name}` : 'Leads per day'}</span>
          ${present.length > 1 ? switcher([{ arg: '', label: 'All together', on: !only }, ...present.map(c => ({ arg: c.id, label: c.name, color: c.color, on: only === c.id }))], 'only') : ''}</div>
        <div style="display:flex;gap:28px">${chart(d, ctx, only)}${legend(d, ctx)}</div>
      </div>
      ${t.demo ? '' : html`<div class="card pad stack" style="gap:14px">
        <div class="baseline"><span class="title">Team targets</span><a class="link" href="#/targets" style="text-decoration:none">All targets</a></div>
        <div class="small faint" style="margin-top:-8px">This week</div>
        ${t.people.map(p => html`<div class="stack" style="gap:6px">
          <div class="between" style="gap:8px"><span class="row" style="gap:9px;min-width:0">${avatar(p.name.split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase(), 24)}<span class="medium clip">${p.name}</span></span>
            <span class="small muted nowrap">${p.targets ? html`<span class="ink medium">${p.on_track}</span> of ${p.targets} on track` : 'No targets yet'}</span></div>
          ${p.targets ? html`<div class="track"><div class="fill" style="width:${p.pct}%;background:var(--${p.on_track === p.targets ? 'pos' : p.on_track ? 'warn' : 'neg'})"></div><div class="mark" style="left:${p.pace}%" title="Where it should be by today"></div></div>` : ''}</div>`)}
        ${t.people.length ? '' : html`<div class="small muted">Nobody has targets yet.</div>`}
        ${t.blockers ? html`<a href="#/targets?view=blockers" class="small" style="color:var(--warn);text-decoration:none;padding-top:10px;border-top:1px solid var(--line2)">${t.blockers} open blocker${t.blockers === 1 ? '' : 's'} →</a>` : ''}
      </div>`}
    </div>

    <div class="grid start" style="grid-template-columns:minmax(0,1.35fr) minmax(0,1fr)">
      <div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:16px 16px 12px"><span class="title">Results by source</span></div>
        <div class="thead" style="border-top:1px solid var(--line)"><span></span><span class="right">Leads</span><span class="right">Qualified</span><span class="right">Deals</span><span class="right">Won</span><span class="right">Spend</span></div>
        ${d.by_kind.map(r => html`<a class="trow" ${TO[r.key] ? html`href="#/${TO[r.key]}"` : ''} style="color:inherit;text-decoration:none"><span class="medium">${r.name}</span>
          <span class="right medium">${f.num(r.leads)}</span>
          <span class="right">${n(r.qualified)}</span><span class="right">${n(r.deals)}</span><span class="right">${n(r.won)}</span><span class="right">${r.spend ? f.moneyShort(r.spend) : html`<span class="faint">—</span>`}</span></a>`)}
      </div>
      <div class="card stack" style="padding:18px 20px 8px">
        <div class="baseline" style="margin-bottom:6px"><span class="title">Alerts</span><a class="link" href="#/alerts" style="text-decoration:none">All alerts</a></div>
        ${d.alerts.length ? d.alerts.map((a, i) => html`<div style="display:flex;gap:12px;padding:11px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
          <span class="dot" style="width:7px;height:7px;background:var(--${a.tone});margin-top:6px"></span>
          <div class="between" style="flex:1;min-width:0;gap:12px"><span class="medium clip" title="${a.detail}">${a.title}</span><span class="tiny faint nowrap">${a.when}</span></div></div>`)
          : html`<div class="small muted" style="padding:10px 0 14px">No open alerts.</div>`}
      </div>
    </div>`;
  },

  actions: {
    openChannel: (ctx, d) => ctx.go('channels', { channel: d.arg }),
    only(ctx, d) { ctx.ui().only = d.arg || null; ctx.render(); },
  },
};
